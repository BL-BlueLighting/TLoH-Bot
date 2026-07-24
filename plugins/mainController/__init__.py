import json
import random
from pathlib import Path

import requests
from nonebot import get_driver, on_command
from nonebot.adapters import Message
from nonebot.adapters.onebot.v11 import (Bot, GroupMessageEvent,
                                         PrivateMessageEvent)
from nonebot.adapters.onebot.v11.message import MessageSegment
from nonebot.matcher import Matcher
from nonebot.params import CommandArg, EventMessage
from nonebot.permission import SUPERUSER

"""
TLoH Bot
Tools Bot 的第二版。

@author: BL-BlueLighting

mainController
"""

TITLE = "TLoH Bot"

"""
兜底函数
"""
# 获取配置里的 COMMAND_START，默认是 {'/', '!', '／', '！'}
command_starts = get_driver().config.command_start

def is_unmatched_command(msg: Message) -> bool:
    text = msg.extract_plain_text().strip()
    # 消息以 COMMAND_START 开头，并且不为空（避免只有 `/`）
    return bool(text) and any(text.startswith(s) for s in command_starts)

#fallback = on_message(priority=1000000, block=True)

#@fallback.handle()
async def _(msg: Message = EventMessage(), matcher: Matcher = Matcher()):
    if is_unmatched_command(msg):
        await matcher.finish("未知指令，请检查输入是否正确。")

"""
Help 函数
用于基本的介绍

@author: BL-BlueLighting
"""
help_function = on_command("help", aliases={"帮助"}, priority=10)

@help_function.handle()
async def _ (bot: Bot, event: GroupMessageEvent | PrivateMessageEvent):
    msg = TITLE
    # 添加图片
    # 获得绝对路径
    await help_function.finish(MessageSegment.image(Path() / "helpdocuments/PNG/HelpDocument v2.png"))

"""
check 函数
检测 bot 是否存活

@author: BL-BlueLighting
"""

check_function = on_command("check", priority=10)

@check_function.handle()
async def _ (bot: Bot, event: GroupMessageEvent | PrivateMessageEvent, args: Message = CommandArg()):
    await check_function.finish("TLoH Bot 还活着呢，没死。")

"""
^ping & ^pong 函数
和 bot 打乒乓球

@author: BL-BlueLighting
"""
ping_function = on_command("ping", priority=10)
pong_function = on_command("pong", priority=10)

@ping_function.handle()
async def _ (bot: Bot, event: GroupMessageEvent | PrivateMessageEvent):
    # 随机
    if random.randint(1, 10) > 5:
        await check_function.finish("没接住")
    else:
        await check_function.finish("pong")

@pong_function.handle()
async def _ (bot: Bot, event: GroupMessageEvent | PrivateMessageEvent):
    if random.randint(1, 10) > 5:
        await check_function.finish("没接住")
    else:
        await check_function.finish("ping")


"""
^essence 函数
设置精华消息

@author: BL-BlueLighting
"""
set_essence = on_command("essence", priority=5, permission=SUPERUSER)

@set_essence.handle()
async def _(bot: Bot, event: GroupMessageEvent, args: Message = CommandArg()):
    if event.reply:
        msg_id = event.reply.message_id
    else:
        await set_essence.finish("TLoH Bot Essence Set\n    - 请回复一条消息来设为精华")

    try:
        await bot.call_api("set_essence_msg", message_id=msg_id)
    except Exception as e:
        await set_essence.finish(f"TLoH Bot Essence Set\n    - 设置精华失败：{e}")
    else:
        await set_essence.finish("TLoH Bot Essence Set\n    - 已成功将该消息设为精华 ✨")


"""
hitokoto 函数

名言金句函數
@author: BL-BlueLighting
"""

goodsaying_function = on_command("hitokoto", priority=10)

@goodsaying_function.handle()
async def _ (bot: Bot, event: GroupMessageEvent | PrivateMessageEvent, args: Message = CommandArg()):
    msg = TITLE + " 名言金句"
    _msg = args.extract_plain_text()
    url = "https://hitokoto.152710.xyz"

    # request
    message = requests.get(url)

    # get json
    _jsonmessage = json.loads(message.content)

    # apppend
    hitokoto = _jsonmessage.get("hitokoto", "世上本沒有路，但是人走多了，便成了路。")
    _from = _jsonmessage.get("from", "《棍母》")
    creator = _jsonmessage.get("creator", "魯迅: 周樹人")

    # format
    msg += f"""
    {hitokoto}
                —— {_from} --- {creator}"""

    # finish
    await goodsaying_function.finish(msg)