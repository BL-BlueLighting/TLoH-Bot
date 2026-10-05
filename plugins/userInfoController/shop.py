import datetime
import json
import os
import random
import re
import sqlite3
from collections import Counter
from typing import Any, Dict, Literal, Optional, List

import nonebot
import requests
import toml
from nonebot import on_command
from nonebot.adapters import Message
from nonebot.adapters.onebot.v11 import (GroupMessageEvent,
                                         PrivateMessageEvent)
from nonebot.adapters.onebot.v11 import Bot as v11bot
from nonebot.exception import ActionFailed
from nonebot.params import CommandArg
from nonebot.permission import SUPERUSER

from toolsbot.configs import DATA_PATH
from toolsbot.services import _error, _info

from plugins.userInfoController.data import _safe_write_json, _safe_read_json
from plugins.userInfoController.user import User

"""
TLoH Bot
Tools Bot 的第二版。

@author: BL-BlueLighting

userInfoController
"""

TITLE = "TLoH Bot"

# =============================================================================
# Item effect handlers
# =============================================================================

class _ItemEffectHandler:
    """Handles item effect logic for the User.useItem method."""

    def __init__(self, user: 'User', item: str, item_effect: str):
        self.user = user
        self.item = item
        self.item_effect = item_effect

    def handle_sign(self) -> str:
        """Handle sign/签到 boost item."""
        _info("SIGN MODE")
        try:
            _x = self.item_effect.split(" ")[1].replace("x", "")
            boost_value = int(_x)
        except (IndexError, ValueError):
            return "签到倍票数据损坏，请联系管理员。"

        boosts = _safe_read_json(DATA_PATH / "boostMorningd.json", [])
        boosts.append({self.user.id: boost_value}) #type: ignore
        _safe_write_json(DATA_PATH / "boostMorningd.json", boosts)

        if self.item in self.user.boughtItems:
            self.user.boughtItems.remove(self.item)
        return f"{_x}x 倍票已使用。下次签到将会获得更多积分。"

    def handle_ticket(self) -> str:
        """Handle ticket/lottery item."""
        _info("TICKET MODE")
        _randomNum = random.randint(1, 1000000000000)
        _randomMoney = random.randint(1, 100)

        if self.item in self.user.boughtItems:
            self.user.boughtItems.remove(self.item)

        if _randomNum == 114514:
            self.user.addScore(10000000000.0)
            self.user.save()
            return "中奖了。获得积分：100,0000,0000。"
        else:
            self.user.addScore(float(_randomMoney))
            self.user.save()
            return f"未中奖。但获得安慰奖 {_randomMoney}"

    def handle_playmode(self) -> str:
        """Handle playmode toggle item."""
        if "enable" in self.item_effect:
            if self.item in self.user.boughtItems:
                self.user.boughtItems.remove(self.item)
            self.user.boughtItems.append("play")
            self.user.save()
            return "已启用娱乐模式。"
        else:
            if "play" in self.user.boughtItems:
                self.user.boughtItems.remove("play")
                self.user.save()
            return "已关闭娱乐模式。"

    def handle_special(self) -> str:
        """Handle special items (iai, BL.BlueLighting, etc.)."""
        if "iai" in self.item_effect:
            return "芝士 ARG 作者"
        elif "滚木" in self.item_effect or "棍母" in self.item_effect:
            return "？请不要使用空白物品谢谢"
        elif "BL.BlueLighting" in self.item_effect:
            return "芝士 Bot 主"
        elif "小薯" in self.item_effect:
            return "南边的桥梁。"
        return "???"

# =============================================================================
# Command: buy
# =============================================================================

buy_function = on_command("buy", priority=10)


@buy_function.handle()
async def handle_buy(bot: v11bot, event: GroupMessageEvent | PrivateMessageEvent,
                      args: Message = CommandArg()):
    """商店系统 - 购买和使用物品"""
    msg = TITLE + " 商店"
    user = User(event.get_user_id())
    _msg = args.extract_plain_text()

    if user.isBanned():
        msg += "\n    - 滚" if user.playMode() else "\n    - 您的账号已被封禁。"
        await buy_function.finish(msg)

    if _msg == "":
        msg += "\n    - 使用 ^buy list 来查看列表"
        await buy_function.finish(msg)

    items = _safe_read_json(DATA_PATH / "item.json", [])
    arg_parts = _msg.split(" ")

    if arg_parts[0] == "list":
        msg += "\n    - 商店状态：售卖中\n    - 物品："
        for item in items:
            msg += f"\n    - {item.get('Name', '未知')} 价格 {item.get('Cost', 0)}"
        msg += "\n    - 使用 ^buy thing [物品名称] 来购买"

    elif arg_parts[0] == "thing":
        msg = await _handle_buy_thing(user, arg_parts, items, msg)#type: ignore

    elif arg_parts[0] == "use":
        msg = await _handle_buy_use(user, arg_parts, msg)

    await buy_function.finish(msg)


async def _handle_buy_thing(user: User, arg_parts: list, items: list, msg: str) -> str:
    """Handle the 'buy thing' subcommand."""
    msg += "\n   - 购买商品"

    if len(arg_parts) == 2:
        arg_parts.append("1")
    elif len(arg_parts) == 1:
        fail_msg = "购买失败，原因：请填写物品名称"
        if user.playMode():
            fail_msg = "购买失败，原因：您他妈填名字没有就来买？"
        msg += f"\n    - {fail_msg}"
        return msg

    item_name = arg_parts[1]
    quantity = arg_parts[2]
    msg += f"\n    - 购买物品：{item_name}"
    msg += f"\n    - 数量: {quantity}"
    msg += f"\n    - 交付中..."

    try:
        qty = int(quantity)
    except ValueError:
        msg += "\n    - 交付失败，原因：数量必须是数字。"
        return msg

    if qty >= 100:
        fail_msg = "交付失败，原因：购买数量过大。"
        if user.playMode():
            fail_msg = "交付失败，原因：购买数量过大。您他妈买这么多干啥？"
        msg += f"\n    - {fail_msg}"
        return msg

    # Find item cost
    cost = 0.114514  # sentinel for "not found"
    for item in items:
        if item.get("Name") == item_name:
            cost = item.get("Cost", 0.114514)
            break

    if cost == 0.114514 and False: # disable
        fail_msg = "交付失败，原因：该商品不存在。"
        if user.playMode():
            fail_msg = "交付失败，原因：该商品不存在。您他妈买个寂寞？"
        msg += f"\n    - {fail_msg}"
        return msg

    total_cost = qty * cost
    if total_cost < 0:
        total_cost = abs(total_cost)

    if user.score >= total_cost:
        msg += f"\n    - 扣除积分：{total_cost}"
        msg += f"\n    - 交付成功。"
        user.addScore(-total_cost)
        for _ in range(qty):
            user.addItem(item_name)
        user.save()
    else:
        fail_msg = "交付失败，原因：余额不足"
        if user.playMode():
            fail_msg = "交付失败，原因：余额不足。您他妈穷成这样还想买东西？"
        msg += f"\n    - {fail_msg}"

    msg += f"\n    - 购买结束。请使用 ^buy use {item_name} {qty} 来使用商品。"
    return msg


async def _handle_buy_use(user: User, arg_parts: list, msg: str) -> str:
    """Handle the 'buy use' subcommand."""
    if len(arg_parts) == 1:
        fail_msg = "请填写物品"
        if user.playMode():
            fail_msg = "使用失败，原因：您他妈填名字没有就来用？"
        msg += f"\n    - {fail_msg}"
        return msg
    elif len(arg_parts) == 2:
        arg_parts.append("1")

    item_name = arg_parts[1]
    try:
        use_count = int(arg_parts[2])
    except ValueError:
        use_count = 1

    msg += f"\n    - 使用物品 {item_name}"
    msg += f"\n    - 使用数量 {use_count}"

    for _ in range(use_count):
        msg += f"\n    - {user.useItem(item_name)}"

    return msg