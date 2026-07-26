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

"""
TLoH Bot
Tools Bot 的第二版。

@author: BL-BlueLighting

userInfoController
"""

TITLE = "TLoH Bot"


# =============================================================================
# Helper: safe JSON file I/O
# =============================================================================

def _safe_read_json(filepath, default=None) -> list | dict:
    """Safely read a JSON file, returning default on any error."""
    if default is None:
        default = {}
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, FileNotFoundError, OSError) as e:
        _error(f"Failed to read {filepath}: {e}")
        return default


def _safe_write_json(filepath, data):
    """Safely write JSON data to a file."""
    try:
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=4)
    except OSError as e:
        _error(f"Failed to write {filepath}: {e}")


# =============================================================================
# EasyCallQQUserObject
# =============================================================================

class EasyCallQQUserObject:
    """Wrapper around QQ user info dict with convenient accessors."""

    def __init__(self, user_info: dict):
        self.user_info = user_info
        self.userdata = user_info

    def GetNick(self) -> str:
        """获取用户昵称"""
        return self.userdata.get("nick", "<Failed to Fetch>")

    def GetPosition(self) -> str:
        """获取用户地区 (country province city)"""
        country = self.userdata.get('country', '')
        province = self.userdata.get('province', '')
        city = self.userdata.get('city', '')
        parts = [p for p in [country, f"{province}省" if province else "", f"{city}市" if city else ""] if p]
        return " ".join(parts).strip()

    def GetGender(self) -> Literal["male", "female"]:
        """获取用户性别"""
        return self.userdata.get("sex", "male")

    def GetGenderChinese(self) -> str:
        """获取用户性别（中文）"""
        gender = self.GetGender()
        if gender == "male":
            return "男"
        elif gender == "female":
            return "女"
        return "沃尔玛塑料袋"

    def GetVIPType(self) -> str:
        """获取用户 VIP 类型"""
        is_vip = self.userdata.get("is_vip", False)
        is_year_vip = self.userdata.get("is_year_vip", False)
        if is_vip and is_year_vip:
            return "年度 VIP"
        elif is_vip:
            return "月度 VIP"
        elif is_year_vip:
            return "年度 VIP"
        return "非 VIP"


# =============================================================================
# EasyCall
# =============================================================================

class EasyCall:
    """Helper for making Onebot v11 API calls to get user info."""

    def __init__(self, bot: v11bot, event: GroupMessageEvent | PrivateMessageEvent | None):
        self.bot = bot
        self.event = event

    async def GetInformationOfUser(self, user_id: str) -> dict:
        """使用 Onebotv11 API 获取用户信息"""
        try:
            user_info = await self.bot.get_stranger_info(user_id=int(user_id))
            return user_info
        except ActionFailed as e:
            _error(f"获取用户信息失败: {e}")
            return {}
        except (ValueError, TypeError) as e:
            _error(f"Invalid user_id for get_stranger_info: {user_id}, error: {e}")
            return {}

    async def GetUserObject(self, user_id: str) -> EasyCallQQUserObject:
        """获取 EasyCallQQUserObject 对象"""
        user_info = await self.GetInformationOfUser(user_id)
        return EasyCallQQUserObject(user_info)


# =============================================================================
# Database helper
# =============================================================================

class Database:
    """Shared database access helper (used by leaderboard etc.)."""

    def __init__(self):
        self.db_path = DATA_PATH / "userdata.db"

    def run_sql(self, sql: str, params: tuple = ()):
        """Execute a SQL statement and return fetchall results."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute(sql, params)
                conn.commit()
                return cursor.fetchall()
        except sqlite3.Error as e:
            _error(f"Database error: {e}")
            return []


# =============================================================================
# Data access layer
# =============================================================================

class Data:
    """Per-user data access layer backed by SQLite."""

    def __init__(self, id: str):
        self.id = id
        self.db_path = DATA_PATH / "userdata.db"
        self._init_db()

    async def GetQQUserObject(self) -> EasyCallQQUserObject:
        """获取 EasyCallQQUserObject 对象"""
        bot: v11bot = nonebot.get_bot()  # type: ignore
        easy_call = EasyCall(bot, None)
        return await easy_call.GetUserObject(self.id)

    def _init_db(self):
        """初始化数据库和表结构"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS users (
                        ID TEXT PRIMARY KEY,
                        Name TEXT NOT NULL,
                        Score INTEGER DEFAULT 0,
                        boughtItems TEXT DEFAULT '[]',
                        Ban TEXT DEFAULT '[]',
                        Warningd TEXT DEFAULT '[]',
                        DynamicExts TEXT DEFAULT '{}'
                    )
                """)
                conn.commit()
        except sqlite3.Error as e:
            _error(f"Failed to initialize database: {e}")

    def check(self) -> bool:
        """Check if userdata exists."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT 1 FROM users WHERE ID = ?", (self.id,))
                return cursor.fetchone() is not None
        except sqlite3.Error as e:
            _error(f"Database check failed: {e}")
            return False

    def writeData(self, userClass):
        """Write user data to database."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT OR REPLACE INTO users
                    (ID, Name, Score, boughtItems, Ban, Warningd, DynamicExts)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (
                    userClass.id,
                    userClass.name,
                    userClass.score,
                    json.dumps(userClass.boughtItems),
                    json.dumps(userClass.banned),
                    json.dumps(userClass.warningd),
                    json.dumps(getattr(userClass, 'dynamicExts', {}))
                ))
                conn.commit()
        except sqlite3.Error as e:
            _error(f"Failed to write user data: {e}")

    def readData(self) -> Dict[str, Any]:
        """Read user data from database."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT ID, Name, Score, boughtItems, Ban, Warningd, DynamicExts
                    FROM users WHERE ID = ?
                """, (self.id,))
                row = cursor.fetchone()

                if row is None:
                    return {}

                return {
                    "ID": row[0],
                    "Name": row[1],
                    "Score": row[2],
                    "boughtItems": json.loads(row[3]),
                    "Ban": row[4] == "true",
                    "Warningd": int(row[5]),
                    "DynamicExts": json.loads(row[6])
                }
        except (sqlite3.Error, json.JSONDecodeError) as ex:
            _error(f"Error: Failed to read data.\nInformation: \n{ex}")
            return {}


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

"""
TLoH Bot
PILLAR OF SHAME
QQ 3829537708
QQ 3562258276
QQ 287280700 (GROUP)
"""

# =============================================================================
# User class
# =============================================================================

class User:
    """整个 userInfoController 的核心大类"""

    def __init__(self, id: str, name: str = "", score: float = 0,
                 boughtItems: Optional[List[str]] = None):
        self.id = id
        self.name = name
        self.score = score
        self.boughtItems = boughtItems if boughtItems is not None else []
        self.banned = False
        self.data = Data(self.id)
        self.warningd = 0

        try:
            _info("Data Checking.")
            if self.data.check():
                _info("Data Exists.")
                self.jsonData = self.data.readData()
                self.id = self.jsonData.get("ID", "10000")
                self.name = self.jsonData.get("Name", "暂未设置")
                self.score = self.jsonData.get("Score", 0.0)
                self.banned = self.jsonData.get("Ban", False)
                self.boughtItems = self.jsonData.get("boughtItems", [])
                self.warningd = self.jsonData.get("Warningd", 0)
            else:
                _info("Data Not Found.")
                self.data.writeData(self)
        except Exception as ex:
            _error("Error: Failed to read or write data." + str(ex))

        if self.warningd >= 10:
            self.banned = True
            _info(f"User '{self.id}' has been banned because of excessive warnings.")

        if self.score < 0:
            self.banned = True

    def save(self):
        """Save user data."""
        self.data.writeData(self)

    def addItem(self, item: str):
        """Add item to user's inventory."""
        self.boughtItems.append(item)
        self.save()

    def useItem(self, item: str) -> str:
        """Use an item from the user's inventory.

        Returns a string describing the result.
        """
        if item not in self.boughtItems:
            return "你没有该物品。"

        # Load item definitions
        items_data = _safe_read_json(DATA_PATH / "item.json", [])

        # Find item effect
        item_effect = ""
        for entry in items_data:
            if entry.get("Name", "") == item:
                item_effect = entry.get("Effect", "")
                break

        # Special override items
        special_items = ["iai", "棍母", "滚木", "BL.BlueLighting", "小薯"]
        if item in special_items:
            item_effect = f"spe {item}"

        if not item_effect:
            return self._random_fallback_response()

        handler = _ItemEffectHandler(self, item, item_effect)

        if "sign" in item_effect:
            return handler.handle_sign()
        elif "ticket" in item_effect:
            return handler.handle_ticket()
        elif "playmode" in item_effect:
            return handler.handle_playmode()
        elif "spe" in item_effect:
            return handler.handle_special()

        return "很抱歉。内部出现错误。"

    @staticmethod
    def _random_fallback_response() -> str:
        """Generate a random fallback response for items with no effect."""
        rv = random.randint(1, 10)
        if rv > 5:
            return "我们在瞎搞"
        elif rv > 7:
            return "窝们在瞎搞"
        elif rv > 9:
            return "窝们载瞎镐"
        return "求 iai 继续更新日期"

    def aiWarningd(self):
        """Increment AI warning counter."""
        self.warningd += 1

    def echoWarningd(self):
        """Increment echo warning counter by 2."""
        self.warningd += 2

    def addScore(self, score: float):
        """Add score to user."""
        self.score += score

    def subtScore(self, score: float):
        """Subtract score from user."""
        self.score -= score

    def getScore(self) -> float:
        """Get user's current score."""
        return self.score

    def isBanned(self) -> bool:
        """Check if user is banned."""
        return self.banned  # type: ignore

    def playMode(self) -> bool:
        """Check if play mode is enabled."""
        return "play" in self.boughtItems

    def existsItem(self, item: str) -> bool:
        """Check if user owns a specific item."""
        return item in self.boughtItems


# =============================================================================
# At helper
# =============================================================================

def At(data: str) -> list:
    """Parse @mentions from event JSON.

    Returns list of QQ numbers, ['all'] for @all, or [] if none.
    """
    try:
        qq_list: list = []
        data_: dict = json.loads(data)
        for msg in data_.get("message", []):
            if msg.get("type") == "at":
                if 'all' not in str(msg):
                    qq_list.append(msg["data"]["qq"])
                else:
                    return ['all']
        return qq_list
    except (KeyError, json.JSONDecodeError):
        return []


# =============================================================================
# Command: getinfo
# =============================================================================

getinfo_function = on_command("info", aliases={"获取账户信息"}, priority=10)


@getinfo_function.handle()
async def handle_getinfo(bot: v11bot, event: GroupMessageEvent | PrivateMessageEvent,
                          args: Message = CommandArg()):
    """获取用户账户信息"""
    msg = TITLE + " 用户面板"

    try:
        at_target = At(event.json())[0]
    except IndexError:
        at_target = ""

    user = User(event.get_user_id())

    if not user.isBanned():
        if at_target == "":
            target_user = user
        else:
            target_user = User(at_target)
        msg += f"\n   - 用户 ID: {target_user.id}"
        msg += f"\n   - 用户昵称: {target_user.name}"
        msg += f"\n   - 用户积分：{target_user.score}"
    else:
        if user.playMode():
            msg += "\n   - 您他妈被封禁了还来玩？滚"
        else:
            msg += "\n   - 您的账号已被封禁，请联系管理员解封。"

    await getinfo_function.finish(msg)


# =============================================================================
# Command: morning (daily sign-in)
# =============================================================================

BOOST_DATA_PATH = DATA_PATH / "boostMorningd.json"
MORNING_DATA_PATH = DATA_PATH / "morningd.json"

morningToday_function = on_command("morning", aliases={"早上好"}, priority=10)


@morningToday_function.handle()
async def handle_morning(bot: v11bot, event: GroupMessageEvent | PrivateMessageEvent,
                          args: Message = CommandArg()):
    """每日签到功能"""
    msg = f"{TITLE} 签到\n"
    user_id_str = str(event.get_user_id())
    current_user = User(user_id_str)

    if current_user.isBanned():
        if current_user.playMode():
            msg += "    - 您他妈被封禁了还来签到？滚"
        else:
            msg += "    - 您的账号已被封禁，请联系管理员解封。"
        await morningToday_function.finish(msg)

    # Load and apply boost
    applied_boost_value = _load_and_apply_boost(user_id_str)

    # Check sign-in status
    if _has_signed_in_today(user_id_str):
        if current_user.playMode():
            msg += "    - 您他妈掉钱眼子里了？今天已经签到过了，明天再来！"
        else:
            msg += "    - 您今天已经签到过了，请明天再来！"
        await morningToday_function.finish(msg)

    # Record sign-in
    _record_signin(user_id_str)

    # Award points
    earned_money = float(random.randint(70, 100)) * applied_boost_value
    current_user.addScore(earned_money)
    current_user.save()

    msg += "    - 签到成功！"
    msg += f"\n    - 您今天签到获得了 {earned_money:.2f} 积分。"
    msg += f"\n    - 目前您的积分为 {current_user.getScore():.2f}。"

    await morningToday_function.finish(msg)


def _load_and_apply_boost(user_id_str: str) -> float:
    """Load boost data and apply the user's boost if available.

    Returns the boost multiplier (default 1.0).
    """
    boosts = _safe_read_json(BOOST_DATA_PATH, [])
    applied_boost = 1.0
    boost_removed = False

    for i, boost_entry in enumerate(boosts):
        if user_id_str in boost_entry:
            try:
                applied_boost = float(boost_entry[user_id_str])
                del boosts[i]
                boost_removed = True
                break
            except (ValueError, TypeError):
                _error(f"Invalid boost value for user {user_id_str}")
                continue

    if boost_removed:
        _safe_write_json(BOOST_DATA_PATH, boosts)

    return applied_boost


def _has_signed_in_today(user_id_str: str) -> bool:
    """Check if the user has already signed in today."""
    records = _safe_read_json(MORNING_DATA_PATH, [])
    today = datetime.date.today()

    for record in records:
        if record.get("Id") == user_id_str:
            last_date_str = record.get("LastSignDate", "")
            try:
                last_date = datetime.datetime.strptime(last_date_str, "%Y-%m-%d").date()
                return last_date == today
            except (ValueError, TypeError):
                continue
    return False


def _record_signin(user_id_str: str):
    """Record today's sign-in for the user."""
    records = _safe_read_json(MORNING_DATA_PATH, [])
    today_str = datetime.date.today().strftime("%Y-%m-%d")
    found = False

    for record in records:
        if record.get("Id") == user_id_str:
            record["LastSignDate"] = today_str
            found = True
            break

    if not found:
        records.append({"Id": user_id_str, "LastSignDate": today_str})#type: ignore

    _safe_write_json(MORNING_DATA_PATH, records)


# =============================================================================
# Command: setinfo (admin only)
# =============================================================================

setinfo_function = on_command("setinfo", priority=10, permission=SUPERUSER)


@setinfo_function.handle()
async def handle_setinfo(bot: v11bot, event: GroupMessageEvent | PrivateMessageEvent,
                          args: Message = CommandArg()):
    """管理员设置用户信息"""
    msg = TITLE + " 设置信息"

    try:
        at_target = At(event.json())[0]
    except IndexError:
        at_target = ""

    if at_target == "":
        msg += "\n    - 使用方法： ^setinfo [@用户] [项目 (id, name, score, banned)] [值]"
        await setinfo_function.finish(msg)

    user = User(at_target)
    arg_parts = args.extract_plain_text().split(" ")

    if len(arg_parts) < 3:
        msg += "\n    - 参数不足。使用方法： ^setinfo [@用户] [项目] [值]"
        await setinfo_function.finish(msg)

    item = arg_parts[1]
    value = arg_parts[2]

    field_map = {
        "id": lambda u, v: setattr(u, "id", v),
        "name": lambda u, v: setattr(u, "name", v),
        "score": lambda u, v: setattr(u, "score", float(v)),
        "banned": lambda u, v: setattr(u, "banned", v == "true"),
    }

    if item in field_map:
        field_map[item](user, value)
        msg += f"\n    - 用户的 {item} 已设为 {value}"
    else:
        msg += "\n    - 语法错误。"

    user.save()
    await setinfo_function.finish(msg)


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


# =============================================================================
# Command: usecode
# =============================================================================

code_function = on_command("usecode", aliases={"code"}, priority=10)


@code_function.handle()
async def handle_usecode(bot: v11bot, event: GroupMessageEvent | PrivateMessageEvent,
                          args: Message = CommandArg()):
    """兑换码功能"""
    msg = TITLE + " "
    user = User(event.get_user_id())

    if user.isBanned():
        msg += "\nTLoH Bot 兑换码兑换\n    - 您的账户已被封禁。\n"
        await code_function.finish(msg)

    code_text = args.extract_plain_text().strip()
    if code_text == "":
        msg += "\nTLoH Bot 兑换码兑换"
        msg += "\n    - 输入 *usecode [兑换码] 以兑换"
        await code_function.finish(msg)

    code = code_text.split(" ")[0]
    present_codes = _safe_read_json(DATA_PATH / "codes.json", {})

    if code in present_codes:
        user = User(event.get_user_id())
        user.addScore(int(present_codes[code]))#type: ignore
        user.save()
        msg += "\n    - 兑换成功"
        msg += f"\n    - 当前用户积分: {user.getScore()}"
        msg += f"\n    - 兑换码: {code}"
        msg += f"\n    - 兑换积分: {present_codes[code]}"#type: ignore

        del present_codes[code]#type: ignore
        _safe_write_json(DATA_PATH / "codes.json", present_codes)#type: ignore
    else:
        msg += "\n    - 兑换失败: 兑换码无效"
        msg += f"\n    - 兑换码: {code.replace(chr(10) + 'ToolsBot', '')}"
        msg += "\n    - 兑换积分: 0"

    await code_function.finish(msg)


# =============================================================================
# Command: pay
# =============================================================================

pay_eventer = on_command("pay", aliases={"交易", "向对方转钱"}, priority=5)


@pay_eventer.handle()
async def handle_pay(bot: v11bot, event: GroupMessageEvent | PrivateMessageEvent,
                      args: Message = CommandArg()):
    """交易功能 - 向其他用户转钱"""
    msg = f"{TITLE} 交易\n"
    _msg = args.extract_plain_text()

    sender_user = User(str(event.get_user_id()))

    if sender_user.isBanned():
        ban_msg = "您的账号已被封禁，请联系管理员解封。"
        if sender_user.playMode():
            ban_msg = "您他妈被封禁了还想交易？滚"
        msg += f"    - {ban_msg}"
        await pay_eventer.finish(msg)

    if not _msg:
        await pay_eventer.finish(msg + "    - 输入 ^pay [@对方] [金额] 以交易")

    try:
        receiver_id = At(event.json())[0]
        parts = _msg.split()
        money = int(parts[0])
        receiver_user = User(receiver_id)
    except (ValueError, IndexError):
        err_msg = "语法错误或金额不是正整数"
        if sender_user.playMode():
            err_msg = "您他妈语法都不会还想交易？滚"
        msg += f"    - {err_msg}"
        await pay_eventer.finish(msg)
    except Exception:
        err_msg = "发生未知错误，请检查格式"
        if sender_user.playMode():
            err_msg = "您他妈语法都不会还想交易？滚"
        msg += f"    - {err_msg}"
        await pay_eventer.finish(msg)

    # Prevent self-transfer
    if sender_user.id == receiver_user.id:
        err_msg = "你不能给自己转钱"
        if sender_user.playMode():
            err_msg = "您他妈自己给自己转钱？脑子有病吧？"
        msg += f"    - {err_msg}"
        await pay_eventer.finish(msg)

    # Check receiver ban
    if receiver_user.isBanned():
        err_msg = "交易失败: 对方账号已被封禁，无法收款"
        if sender_user.playMode():
            err_msg = "您他妈想给个封禁用户转钱？滚"
        msg += f"    - {err_msg}"
        await pay_eventer.finish(msg)

    # Execute transfer
    if money > 0 and sender_user.getScore() >= money:
        sender_user.subtScore(float(money))
        sender_user.save()
        receiver_user.addScore(float(money))
        receiver_user.save()
        msg += "     - 交易成功\n"
        msg += f"    - {sender_user.name} 当前积分: {sender_user.getScore():.2f}\n"
        msg += f"    - {receiver_user.name} 当前积分: {receiver_user.getScore():.2f}"
    else:
        err_msg = "失败原因: 积分不足或交易金额小于等于零"
        if sender_user.playMode():
            err_msg = "失败原因: 您他妈穷成这样还想转钱？滚"
        msg += f"     - 交易失败\n     - {err_msg}"

    await pay_eventer.finish(msg)


# =============================================================================
# Command: echo
# =============================================================================

echo_eventer = on_command("echo", aliases={"说"}, priority=5)


@echo_eventer.handle()
async def handle_echo(bot: v11bot, event: GroupMessageEvent | PrivateMessageEvent,
                       args: Message = CommandArg()):
    """回声功能 - 让 Bot 复读你说的话"""
    _msg = args.extract_plain_text().strip()
    user = User(str(event.get_user_id()))

    if user.isBanned():
        await echo_eventer.finish(
            f"{TITLE} ECHO\n    - 乐，没想到吧，你被封禁了连 echo 都用不了"
        )

    if not _msg:
        await echo_eventer.finish(f"{TITLE} ECHO\n    - 用法: ^echo [内容]")

    # Load blocked words
    failed_words_data = _safe_read_json(DATA_PATH / "echoFailedWords.json", {})
    failed_words_list = failed_words_data.get("chinese_keywords", [])#type: ignore
    failed_regex_list = failed_words_data.get("regex_patterns", [])#type: ignore
    failed_eng_list = failed_words_data.get("exact_matches", [])#type: ignore

    # Check content against blocked words
    for word in failed_words_list:
        if word in _msg:
            user.echoWarningd()
            await echo_eventer.finish(f"{TITLE} ECHO\n    - 键政大师！滚！")

    for pattern in failed_regex_list:
        try:
            if re.search(pattern, _msg):
                user.echoWarningd()
                await echo_eventer.finish(f"{TITLE} ECHO\n    - 键政大师！滚！")
        except re.error:
            _error(f"Invalid regex pattern in echoFailedWords: {pattern}")
            continue

    for word in failed_eng_list:
        if word in _msg:
            user.echoWarningd()
            await echo_eventer.finish(f"{TITLE} ECHO\n    - 键政大师！滚！")

    # Special blank check (handles empty echo override)
    if _msg in ("棍母", "██"):
        await echo_eventer.finish("  ")

    await echo_eventer.finish(_msg)


# =============================================================================
# Command: cleanwaste
# =============================================================================

wasteTaker_event = on_command("cleanwaste", aliases={"捡垃圾"}, priority=5)


@wasteTaker_event.handle()
async def handle_cleanwaste(bot: v11bot, event: GroupMessageEvent | PrivateMessageEvent,
                             args: Message = CommandArg()):
    """捡垃圾功能"""
    waste_options = [
        ("普通", 1), ("普通", 1), ("普通", 1), ("普通", 1),
        ("垃圾", 0), ("垃圾", 0), ("垃圾", 0), ("垃圾", 0),
        ("垃圾", 0), ("垃圾", 0), ("垃圾", 0), ("垃圾", 0),
        ("中级", 5), ("高级", 10), ("黄金", 100), ("钻石", 10000)
    ]

    waste_name, waste_money = random.choice(waste_options)
    msg = f"{TITLE} - 捡垃圾"

    user = User(str(event.get_user_id()))

    if user.isBanned():
        ban_msg = "您的账号已被封禁，请联系管理员解封。"
        if user.playMode():
            ban_msg = "您他妈被封禁了还想捡垃圾？滚"
        msg += f"\n    - {ban_msg}"
        await wasteTaker_event.finish(msg)

    user.addScore(float(waste_money))
    user.save()

    msg += "\n    - 你没钱了，你来捡垃圾。"
    msg += "\n    - 垃圾属性："
    msg += f"\n          类型：{waste_name}"
    msg += f"\n          赚了：{waste_money}"
    msg += f"\n    - 你现在的积分是: {user.getScore():.2f}"

    await wasteTaker_event.finish(msg)


# =============================================================================
# Command: moneybest (leaderboard)
# =============================================================================

list_eventer = on_command("moneybest", aliases={"排行榜"}, priority=5)


@list_eventer.handle()
async def handle_moneybest(bot: v11bot, event: GroupMessageEvent | PrivateMessageEvent,
                            args: Message = CommandArg()):
    """排行榜功能"""
    msg = f"{TITLE} - 排行榜\n"

    data = Database()
    easyc = EasyCall(bot, event)
    scores = data.run_sql("SELECT * FROM users ORDER BY Score DESC")

    if not scores:
        msg += "    - 当前没有用户数据"
        await list_eventer.finish(msg)

    top_users = scores[:10]
    for rank, user_row in enumerate(top_users, 1):
        try:
            user_obj = await easyc.GetUserObject(user_row[0])
            nick = user_obj.GetNick()
        except Exception as e:
            _error(f"Failed to get user info for leaderboard: {e}")
            nick = "未知用户"
        msg += f"    - {rank}. {nick} | ID: {user_row[0]} | 积分: {user_row[2]:.2f}\n"

    await list_eventer.finish(msg)


# =============================================================================
# Command: ban (admin only)
# =============================================================================

ban_function = on_command("ban", priority=10, permission=SUPERUSER)


@ban_function.handle()
async def handle_ban(bot: v11bot, event: GroupMessageEvent,
                      args: Message = CommandArg()):
    """封禁用户 (仅群聊)"""
    msg = f"{TITLE} 管理系统"
    ats = At(event.json())

    if not ats:
        msg += "\n    - 使用 ^ban [@用户] (可封禁多个)"
    elif len(ats) == 1:
        user = User(ats[0])
        user.banned = True
        user.save()
        msg += f"\n    - 已封禁用户 {user.id}。"
    else:
        for user_id in ats:
            user = User(user_id)
            user.banned = True
            user.save()
            try:
                await bot.call_api("set_group_ban", group_id=event.group_id,
                                   user_id=user.id, duration=2591940)
            except ActionFailed as e:
                _error(f"Failed to set group ban for {user.id}: {e}")
            msg += f"\n    - 已封禁用户 {user.id}。"
        msg += f"\n    - 本次封禁 {len(ats)} 个用户。"

    await ban_function.finish(msg)


# =============================================================================
# Command: pardon (admin only)
# =============================================================================

pardon_function = on_command("pardon", priority=10, permission=SUPERUSER)


@pardon_function.handle()
async def handle_pardon(bot: v11bot, event: GroupMessageEvent | PrivateMessageEvent,
                         args: Message = CommandArg()):
    """解封用户"""
    msg = f"{TITLE} 管理系统"
    ats = At(event.json())

    if not ats:
        msg += "\n    - 使用 ^pardon [@用户] (可解封多个)"
    elif len(ats) == 1:
        user = User(ats[0])
        user.banned = False
        user.save()
        msg += f"\n    - 已解封用户 {user.id}。"
    else:
        for user_id in ats:
            user = User(user_id)
            user.banned = False
            user.save()
            msg += f"\n    - 已解封用户 {user.id}。"
        msg += f"\n    - 本次解封 {len(ats)} 个用户。"

    await pardon_function.finish(msg)


# =============================================================================
# Command: banlist
# =============================================================================

banlist_function = on_command("banlist", priority=10)


@banlist_function.handle()
async def handle_banlist(bot: v11bot, event: GroupMessageEvent | PrivateMessageEvent,
                          args: Message = CommandArg()):
    """查看封禁用户列表"""
    msg = f"{TITLE} 管理系统"

    userdata_dir = DATA_PATH / "userdata"
    if not os.path.exists(userdata_dir):
        msg += "\n    - 当前没有被封禁的用户"
        await banlist_function.finish(msg)

    found_banned = False
    try:
        sql = Database().run_sql("select * from users;")
        for _user in sql:
            user_id = _user [0]
            user = User(str(user_id))
            if user.isBanned():
                qobj = await Data(user.id).GetQQUserObject()
                nick = qobj.GetNick()
                msg += f"    - 用户 ID {user.id} | 用户昵称 {nick} | 已被封禁"
    except OSError as e:
        _error(f"Failed to list userdata directory: {e}")

    if not found_banned:
        msg += "\n    - 当前没有被封禁的用户"

    await banlist_function.finish(msg)


# =============================================================================
# Command: accountstatus
# =============================================================================

accountstatus_function = on_command("accountstatus", aliases={"accountStatus"}, priority=10)


@accountstatus_function.handle()
async def handle_accountstatus(bot: v11bot, event: GroupMessageEvent | PrivateMessageEvent,
                                args: Message = CommandArg()):
    """查看账号封禁状态/权限"""
    msg = f"{TITLE} 当前账号情况"
    at_list = At(event.json())
    superusers = eval(open("./.env.prod", "r").readlines()[3].replace("SUPERUSERS=", ""))

    if not at_list:
        user = User(event.get_user_id())
        ban_status = "封禁" if user.isBanned() else "解禁"
        msg += "\n    - 当前您账号的情况："
        msg += f"\n        - 封禁状态：{ban_status}"
        if user.id in superusers:
            msg += "\n        - 权限：超级用户"
    else:
        user = User(at_list[0])
        ban_status = "封禁" if user.isBanned() else "解禁"
        msg += "\n    - 当前该账号的情况："
        msg += f"\n        - 封禁状态：{ban_status}"
        if user.id in superusers:
            msg += "\n        - 权限：超级用户"

    await accountstatus_function.finish(msg)


# =============================================================================
# Command: redpacket
# =============================================================================

redpacket_function = on_command("redpacket", aliases={"发红包"}, priority=5)


@redpacket_function.handle()
async def handle_redpacket(bot: v11bot, event: GroupMessageEvent | PrivateMessageEvent,
                            args: Message = CommandArg()):
    """发红包功能"""
    msg = f"{TITLE} - 发红包"
    user = User(event.get_user_id())

    if user.isBanned():
        ban_msg = "您的账号已被封禁，请联系管理员解封。"
        if user.playMode():
            ban_msg = "您他妈被封禁了还想发红包？滚"
        msg += f"\n    - {ban_msg}"
        await redpacket_function.finish(msg)

    _msg = args.extract_plain_text().split(" ")

    if len(_msg) < 2:
        msg += "\n    - 使用 ^redpacket [金额] [数量] 来发红包"
        await redpacket_function.finish(msg)

    try:
        money = float(_msg[0])
        number = int(_msg[1])
    except ValueError:
        err_msg = "语法错误或金额不是正整数"
        if user.playMode():
            err_msg = "您他妈语法都不会还想发红包？滚"
        msg += f"\n    - {err_msg}"
        await redpacket_function.finish(msg)

    if money <= 0 or number <= 0:
        err_msg = "语法错误或金额不是正整数"
        if user.playMode():
            err_msg = "您他妈语法都不会还想发红包？滚"
        msg += f"\n    - {err_msg}"
        await redpacket_function.finish(msg)

    if user.getScore() < money:
        err_msg = "余额不足"
        if user.playMode():
            err_msg = "您他妈穷成这样还想发红包？滚"
        msg += f"\n    - {err_msg}"
        await redpacket_function.finish(msg)

    if number > 100:
        err_msg = "发红包数量过大。"
        if user.playMode():
            err_msg = "发红包数量过多。您他妈有钱不如做慈善。"
        msg += f"\n    - {err_msg}"
        await redpacket_function.finish(msg)

    # Execute
    user.subtScore(money)
    user.save()
    per_money = money / number

    msg += f"\n    - 成功发出 {number} 个红包，每个 {per_money:.2f} 积分。请让群友使用 ^openredpacket 来领取。"

    redpacket = {
        "UserID": user.id,
        "Money": per_money,
        "Number": number,
        "TakedUser": []
    }

    redpacket_path = DATA_PATH / "redpackets.json"
    redpackets = _safe_read_json(redpacket_path, [])
    redpackets.append(redpacket)#type: ignore
    _safe_write_json(redpacket_path, redpackets)

    await redpacket_function.finish(msg)


# =============================================================================
# Command: openredpacket
# =============================================================================

openredpacket_function = on_command("openredpacket", aliases={"抢红包"}, priority=5)


@openredpacket_function.handle()
async def handle_openredpacket(bot: v11bot, event: GroupMessageEvent | PrivateMessageEvent,
                                args: Message = CommandArg()):
    """抢红包功能"""
    msg = f"{TITLE} - 抢红包"
    user = User(event.get_user_id())

    if user.isBanned():
        ban_msg = "您的账号已被封禁，请联系管理员解封。"
        if user.playMode():
            ban_msg = "您他妈被封禁了还想抢红包？滚"
        msg += f"\n   - {ban_msg}"
        await openredpacket_function.finish(msg)

    redpacket_path = DATA_PATH / "redpackets.json"
    redpackets = _safe_read_json(redpacket_path, [])

    if not redpackets:
        msg += "\n   - 当前没有可抢的红包。"
        await openredpacket_function.finish(msg)

    selected_index = random.randint(0, len(redpackets) - 1)
    selected = redpackets[selected_index]

    if user.id in selected.get("TakedUser", []):
        dup_msg = "您已经抢过这个红包了，不能重复抢。"
        if user.playMode():
            dup_msg = "您他妈已经抢过这个红包了，再抢就变成██。"
        msg += f"\n   - {dup_msg}"
        await openredpacket_function.finish(msg)

    try:
        reward = float(selected.get("Money", 0))
    except (ValueError, TypeError):
        reward = 0.0

    user.addScore(reward)
    user.save()

    msg += f"\n   - 抢到一个 {reward:.2f} 积分的红包！"
    msg += f"\n   - 目前您的积分为 {user.getScore():.2f}。"

    selected["Number"] = selected.get("Number", 0) - 1
    selected["TakedUser"].append(user.id)

    if selected["Number"] <= 0:
        del redpackets[selected_index]
    else:
        redpackets[selected_index] = selected

    _safe_write_json(redpacket_path, redpackets)
    await openredpacket_function.finish(msg)


# =============================================================================
# Command: fuck (easter egg)
# =============================================================================

fuck_eventer = on_command("fuck")


@fuck_eventer.handle()
async def handle_fuck(bot: v11bot, event: GroupMessageEvent | PrivateMessageEvent,
                       args: Message = CommandArg()):
    """彩蛋功能"""
    try:
        await bot.call_api("send_private_msg", user_id=event.user_id,
                           message="You ****ed " + args.extract_plain_text())
    except ActionFailed:
        await fuck_eventer.finish("彩蛋无法触发。若该群禁止了私聊请先加 Bot 好友。")
    else:
        await fuck_eventer.finish("彩蛋触发。请查看私聊。")


# =============================================================================
# Command: modifyname
# =============================================================================

modifyname_function = on_command("modifyname", priority=10)


@modifyname_function.handle()
async def handle_modifyname(bot: v11bot, event: GroupMessageEvent | PrivateMessageEvent,
                             args: Message = CommandArg()):
    """修改用户昵称"""
    msg = TITLE + " Modify Name"
    user = User(event.get_user_id())
    _msg = args.extract_plain_text()

    user.name = _msg
    msg += "\n    - 名称修改完毕。你现在的新名称为：" + user.name + "。"
    user.save()
    await modifyname_function.finish(msg)


# =============================================================================
# Command: bag
# =============================================================================

bag_function = on_command("bag", aliases=set(), priority=10)


@bag_function.handle()
async def handle_bag(bot: v11bot, event: GroupMessageEvent | PrivateMessageEvent,
                      args: Message = CommandArg()):
    """查看背包"""
    user = User(event.get_user_id())
    msg = "\nTLoH Bot 背包\n    - 目前你包里有："

    items = user.boughtItems
    if not items:
        msg += "\n    - 你包里是空的。"
    else:
        count = Counter(items)
        for item, num in count.items():
            suffix = f" x{num}" if num > 1 else ""
            msg += f"\n    - {item}{suffix}"

    await bag_function.finish(msg)


# =============================================================================
# Command: browsingbottle
# =============================================================================

browsingbottle_function = on_command("browsingbottle", priority=10)


@browsingbottle_function.handle()
async def handle_browsingbottle(bot: v11bot, event: GroupMessageEvent | PrivateMessageEvent,
                                 args: Message = CommandArg()):
    """漂流瓶功能"""
    msg = TITLE + " 漂流瓶 BROWSING BOTTLE"
    user = User(event.get_user_id())
    _msg = args.extract_plain_text()
    arg_parts = _msg.split(" ")
    action = arg_parts[0] if arg_parts else ""
    content_parts = arg_parts[1:] if len(arg_parts) > 1 else []

    bottle_path = DATA_PATH / "bottles.json"

    if action == "throw":
        if not content_parts:
            msg += "\n    - 使用 ^browsingbottle throw [内容] 来扔漂流瓶"
            await browsingbottle_function.finish(msg)

        content = " ".join(content_parts)
        bottles = _safe_read_json(bottle_path, [])
        bottles.append({"UserID": user.id, "Content": content})#type: ignore
        _safe_write_json(bottle_path, bottles)
        msg += "\n    - 你扔下了一个漂流瓶。"
        await browsingbottle_function.finish(msg)

    elif action == "pick":
        bottles = _safe_read_json(bottle_path, [])
        if not bottles:
            msg += "\n    - 目前没有漂流瓶。"
            await browsingbottle_function.finish(msg)

        selected_index = random.randint(0, len(bottles) - 1)
        selected = bottles[selected_index]
        msg += f"\n    - 你捡到了一个漂流瓶，内容是：\n    {selected['Content']}"
        del bottles[selected_index]
        _safe_write_json(bottle_path, bottles)
        await browsingbottle_function.finish(msg)

    else:
        msg += "\n    - 使用 ^browsingbottle throw [内容] 来扔漂流瓶"
        msg += "\n    - 使用 ^browsingbottle pick 来捡漂流瓶"
        await browsingbottle_function.finish(msg)


# =============================================================================
# Command: voting
# =============================================================================

voting_function = on_command("voting", priority=10)


@voting_function.handle()
async def handle_voting(bot: v11bot, event: GroupMessageEvent,
                         args: Message = CommandArg()):
    """投票功能"""
    msg = "TLoH Bot VOTING MODULE."
    user = User(event.get_user_id())
    _msg = args.extract_plain_text()
    arg_parts = _msg.split(" ")

    vote_path = DATA_PATH / "voting.json"
    vote_data = _safe_read_json(vote_path, [])

    if not arg_parts or arg_parts[0] == "":
        msg += "\n    - 使用 ^voting help 来查看帮助。"
        await voting_function.finish(msg)

    action = arg_parts[0]
    params = arg_parts[1:]

    if action == "create":
        msg = await _voting_create(user, params, vote_data, vote_path, msg)#type: ignore
    elif action == "list":
        msg = await _voting_list(vote_data, msg)#type: ignore
    elif action == "status":
        msg = await _voting_status(params, vote_data, msg)#type: ignore
    elif action == "help":
        msg += _VOTING_HELP_TEXT
    elif action == "vote":
        msg = await _voting_vote(bot, event, user, params, vote_data, vote_path, msg)#type: ignore
    else:
        msg += "    - 使用 ^voting help 来查看帮助。"

    await voting_function.finish(msg)


_VOTING_HELP_TEXT = """
使用 ^voting [参数] 来使用投票功能。
参数：
    create: 创建投票，使用 ^voting create [title] [type: kick, normal] [duration: minutes]
    list: 列出所有投票
    status: 查看投票状态，使用 ^voting status [title]
    vote: 投票，使用 ^voting vote [title] [agree, objection, abstain]
    help: 查看帮助
投票类型：
    kick: 踢人投票
    normal: 普通投票
注意事项：
    1. 投票时间单位为分钟，不能超过/等于 1 年
    2. 每人每个投票只能投一次
    3. 投票结束后，kick 类型的投票如果赞成票多于反对票，则会自动踢出发起人指定的用户
"""


async def _voting_create(user: User, params: list, vote_data: list,
                          vote_path, msg: str) -> str:
    """Create a new vote."""
    if len(params) < 3:
        msg += "\n    - 使用 ^voting create [title] [type: kick, normal] [duration: minutes] 来创建投票。"
        return msg

    title, vtype, duration_str = params[0], params[1], params[2]

    if vtype not in ["kick", "normal"]:
        msg += "\n    - 投票类型只能是 kick 或 normal。"
        return msg

    if vtype == "kick" and user.id not in nonebot.get_driver().config.superusers:
        msg += "\n    - 只有超级用户可以创建踢人投票。"
        return msg

    try:
        duration = int(duration_str)
    except ValueError:
        msg += "\n    - 投票时间必须是数字，单位为分钟。"
        return msg

    if duration >= 24 * 60 * 365:
        msg += "\n    - 投票时间不能超过/等于 1 年。"
        return msg

    vote_cfg = {
        "name": title,
        "agree": 0,
        "objection": 0,
        "abstain": 0,
        "status": "进行中",
        "type": vtype,
        "duration": duration,
        "creator": user.id,
        "begintime": str(datetime.datetime.now()),
        "voters": []
    }

    vote_data.append(vote_cfg)
    _safe_write_json(vote_path, vote_data)
    msg += f"\n    - 已创建投票 {title}，类型 {vtype}，时长 {duration} 分钟。"
    return msg


async def _voting_list(vote_data: list, msg: str) -> str:
    """List all votes."""
    if not vote_data:
        msg += "\n    - 目前没有任何投票。"
        return msg

    msg += "\n    - 目前的投票有："
    for vote in vote_data:
        msg += (f"\n        - {vote['name']} (状态: {vote['status']}, "
                f"类型: {vote['type']}, 发起人: {vote['creator']})")
    return msg


async def _voting_status(params: list, vote_data: list, msg: str) -> str:
    """Show vote status."""
    if not params:
        msg += "\n    - 使用 ^voting status [title] 来查看投票状态。"
        return msg

    title = params[0]
    vote = next((v for v in vote_data if v["name"] == title), None)

    if vote is None:
        msg += f"\n    - 未找到投票 {title}"
        return msg

    msg += f"\n    - 投票 {title} 的状态："
    msg += f"\n        - 状态: {vote['status']}。"
    msg += f"\n        - 类型: {vote['type']}。"
    msg += f"\n        - 发起人: {vote['creator']}。"
    msg += f"\n        - 赞成: {vote['agree']} 票。"
    msg += f"\n        - 反对: {vote['objection']} 票。"
    msg += f"\n        - 弃权: {vote['abstain']} 票。"
    msg += f"\n        - 时长: {vote['duration']} 分钟。"
    msg += f"\n        - 已投票人数: {len(vote['voters'])} 人。"
    return msg


async def _voting_vote(bot: v11bot, event: GroupMessageEvent, user: User,
                        params: list, vote_data: list, vote_path, msg: str) -> str:
    """Cast a vote."""
    if len(params) < 2:
        msg += "\n    - 使用 ^voting vote [title] [agree, objection, abstain] 来投票。"
        return msg

    title, choice = params[0], params[1]

    if choice not in ["agree", "objection", "abstain"]:
        msg += "\n    - 投票选项只能是 agree, objection, abstain。"
        return msg

    vote = next((v for v in vote_data if v["name"] == title), None)

    if vote is None:
        msg += f"\n    - 未找到投票 {title}。"
        return msg

    # Check if vote has expired
    try:
        begin_time = datetime.datetime.fromisoformat(vote["begintime"])
        elapsed = (datetime.datetime.now() - begin_time).total_seconds()
        if elapsed > vote["duration"] * 60:
            vote["status"] = "已结束"
            _safe_write_json(vote_path, vote_data)
            msg += f"\n    - 投票 {title} 已结束。"
            # Process kick vote outcome
            if vote["type"] == "kick" and vote["agree"] > vote["objection"]:
                target_user = User(vote["creator"])
                target_user.banned = True
                target_user.save()
                try:
                    admin_info = await bot.call_api(
                        "get_group_member_info",
                        group_id=event.group_id,
                        user_id=bot.self_id
                    )
                    if admin_info.get("role") == "member":
                        msg += f"\n    - 已自动封禁发起人 {vote['creator']}。"
                    else:
                        await bot.call_api("set_group_kick", group_id=event.group_id,
                                           user_id=vote["creator"])
                        msg += f"\n    - 已踢出发起人 {vote['creator']}。"
                except ActionFailed as e:
                    _error(f"Failed to process kick vote: {e}")
            return msg
    except (ValueError, TypeError) as e:
        _error(f"Error parsing vote begin time: {e}")

    if vote["status"] != "进行中":
        msg += f"\n    - 投票 {title} 已结束，无法投票。"
        return msg

    if user.id in [list(v.keys())[0] if isinstance(v, dict) else "" for v in vote["voters"]]:
        msg += f"\n    - 你已在投票 {title} 中投过票，无法重复投票。"
        return msg

    # Record vote
    vote[choice] = vote.get(choice, 0) + 1
    vote["voters"].append({user.id: choice})
    _safe_write_json(vote_path, vote_data)

    msg += f"\n    - 你已在投票 {title} 中投下 {choice} 一票。"
    return msg
