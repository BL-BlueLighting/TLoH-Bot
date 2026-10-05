from nonebot import on_command
from nonebot.adapters import Message
from nonebot.adapters.onebot.v11 import Bot as v11bot
from nonebot.adapters.onebot.v11 import GroupMessageEvent, PrivateMessageEvent
from nonebot.internal.matcher import Matcher
from nonebot.params import CommandArg

import PhigrosScoreLibrary as psl
from plugins.phigrosScoringController import render
from plugins.phigrosScoringController.database import (
    LEVEL_NAMES,
    PhigrosUserdataDatabase,
    SnapshotSaveResult,
    make_player_id,
)
from plugins.phigrosScoringController.songs import SongInfo
from plugins.userInfoController.data import _safe_read_json, _safe_write_json
from toolsbot.services import _error, _info

from typing import Optional
from plugins.userInfoController.data import *
from plugins.userInfoController.shop import *

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