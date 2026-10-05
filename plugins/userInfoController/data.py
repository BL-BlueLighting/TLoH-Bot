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
