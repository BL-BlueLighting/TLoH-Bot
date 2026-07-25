
import json
import os
import random
import sqlite3
from typing import Any, Dict

import old_file.userInfoClasses as dc

print("TLoH Bot - Userdata 迁移工具")
print("迁移所有 userdata 下 .userdata 文件到 sqlite3 userdata.db")
print("")

_info = print
_erro = print


class Data:
    """Data access layer for migration (standalone version)."""

    def __init__(self, id: str):
        self.id = id
        self.db_path = "./userdata.db"
        self._init_db()

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
            _erro(f"Failed to initialize database: {e}")

    def check(self) -> bool:
        """Check if userdata exists."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT 1 FROM users WHERE ID = ?", (self.id,))
                return cursor.fetchone() is not None
        except sqlite3.Error as e:
            _erro(f"Database check failed: {e}")
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
            _erro(f"Failed to write user data: {e}")

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
            _erro(f"Error: Failed to read data.\nInformation: \n{ex}")
            return {}


class User:
    """User class for migration (standalone version)."""

    def __init__(self, id: str, name: str = "", score: float = 0,
                 boughtItems: list = None):
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
            _erro(f"Error: Failed to read or write data. {ex}")

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
        """Use an item from inventory with effect handling."""
        if item not in self.boughtItems:
            return "你没有该物品。"

        items_data = _safe_read_json("./data/item.json", [])
        item_effect = _find_item_effect(items_data, item)

        # Special override for certain items
        special_items = ["iai", "棍母", "滚木", "BL.BlueLighting"]
        if item in special_items:
            item_effect = f"spe {item}"

        if not item_effect:
            return _random_fallback()

        return _apply_item_effect(self, item, item_effect)

    def aiWarningd(self):
        self.warningd += 1

    def echoWarningd(self):
        self.warningd += 2

    def addScore(self, score: float):
        self.score += score

    def subtScore(self, score: float):
        self.score -= score

    def getScore(self) -> float:
        return self.score

    def isBanned(self) -> bool:
        return self.banned

    def playMode(self) -> bool:
        return "play" in self.boughtItems

    def existsItem(self, item: str) -> bool:
        return item in self.boughtItems


def _safe_read_json(filepath, default=None):
    """Safely read a JSON file."""
    if default is None:
        default = {}
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, FileNotFoundError, OSError) as e:
        _erro(f"Failed to read {filepath}: {e}")
        return default


def _find_item_effect(items_data: list, item_name: str) -> str:
    """Find the effect string for an item."""
    for entry in items_data:
        if entry.get("Name", "") == item_name:
            return entry.get("Effect", "")
    return ""


def _random_fallback() -> str:
    """Generate a random fallback message for items with no effect defined."""
    rv = random.randint(1, 10)
    if rv > 5:
        return "我们在瞎搞"
    elif rv > 7:
        return "窝们在瞎搞"
    elif rv > 9:
        return "窝们载瞎镐"
    return "求 iai 继续更新日期"


def _apply_item_effect(user: User, item: str, effect: str) -> str:
    """Apply an item's effect and return the result message."""
    effect_parts = effect.split(" ")

    if "sign" in effect:
        return _handle_sign_effect(user, item, effect_parts)
    elif "ticket" in effect:
        return _handle_ticket_effect(user, item)
    elif "playmode" in effect:
        return _handle_playmode_effect(user, item, effect_parts)
    elif "spe" in effect:
        return _handle_special_effect(effect)
    return "很抱歉。内部出现错误。"


def _handle_sign_effect(user: User, item: str, parts: list) -> str:
    """Handle sign/签到 boost effect."""
    _info("SIGN MODE")
    try:
        _x = parts[1].replace("x", "")
        boost_val = int(_x)
    except (IndexError, ValueError):
        return "签到倍票数据损坏。"

    boosts = _safe_read_json("./data/boostMorningd.json", [])
    boosts.append({user.id: boost_val})
    try:
        with open("./data/boostMorningd.json", "w", encoding="utf-8") as f:
            json.dump(boosts, f)
    except OSError:
        pass

    if item in user.boughtItems:
        user.boughtItems.remove(item)
    return f"{_x}x 倍票已使用。下次签到将会获得更多积分。"


def _handle_ticket_effect(user: User, item: str) -> str:
    """Handle ticket/lottery effect."""
    _info("TICKET MODE")
    _randomNum = random.randint(1, 1000000000000)
    _randomMoney = random.randint(1, 100)

    if item in user.boughtItems:
        user.boughtItems.remove(item)

    if _randomNum == 114514:
        user.addScore(10000000000.0)
        user.save()
        return "中奖了。获得积分：100,0000,0000。"
    else:
        user.addScore(float(_randomMoney))
        user.save()
        return f"未中奖。但获得安慰奖 {_randomMoney}"


def _handle_playmode_effect(user: User, item: str, parts: list) -> str:
    """Handle playmode toggle effect."""
    if "enable" in parts[0]:
        if item in user.boughtItems:
            user.boughtItems.remove(item)
        user.boughtItems.append("play")
        user.save()
        return "已启用娱乐模式。"
    else:
        if "play" in user.boughtItems:
            user.boughtItems.remove("play")
            user.save()
        return "已关闭娱乐模式。"


def _handle_special_effect(effect: str) -> str:
    """Handle special name-based item effects."""
    if "iai" in effect:
        return "芝士 ARG 作者"
    elif "滚木" in effect or "棍母" in effect:
        return "？请不要使用空白物品谢谢"
    elif "BL.BlueLighting" in effect:
        return "芝士 Bot 主"
    return "???"


# =============================================================================
# Migration entry point
# =============================================================================

def run_migration():
    """Run the userdata migration from old format to SQLite."""
    enter = input("开始迁移？(y/N) ")
    if enter.lower() != "y":
        print("迁移停止。")
        return

    try:
        _userdatas = os.listdir("./userdata")
    except OSError as e:
        print(f"无法读取 userdata 目录: {e}")
        return

    migrated_count = 0
    for filename in _userdatas:
        if filename.endswith(".toolsbot_data"):
            try:
                clean_name = filename.replace(".toolsbot_data", "")
                oldUsr = dc.User(clean_name)
                newUsr = User(oldUsr.id)

                newUsr.score = oldUsr.score
                newUsr.boughtItems = oldUsr.boughtItems
                newUsr.name = oldUsr.name
                newUsr.banned = oldUsr.banned

                newUsr.save()
                print(f"迁移用户 '{oldUsr.id}' 的数据成功。")
                migrated_count += 1
            except Exception as e:
                print(f"迁移用户 '{filename}' 失败: {e}")

    print(f"迁移完毕。共迁移 {migrated_count} 个用户。")


if __name__ == "__main__":
    run_migration()
