# 该模块建造了 MapContent 相关内容，作为解释器的主要加载 library.

import json
import os
from typing import Literal, List, Optional, Tuple, Any

from toolsbot.services import _error, _info


class MapContent:
    """Map content container with nested Area, Action, and Redeem classes."""

    def __init__(self):
        self.area = self.Area
        self.act = self.Action
        self.red = self.Redeem

    class Action:
        """An action that can be performed in the map."""

        def __init__(self, Action: str):
            self.act = Action

        def interpret(self) -> str:
            return self.act

    class Redeem:
        """A redeemable reward/checkpoint in the map."""

        def __init__(self, ID: int, Name: str, Need: int,
                     PerfectChallenge: bool = False, ReviewChallenge: bool = False,
                     Challenge: list = None, FinishMessage: str = "",
                     Actions: list = None, End: bool = True):
            self.id = ID
            self.name = Name
            self.need = Need
            self.actions = Actions if Actions is not None else []
            self.perfectChallenge = PerfectChallenge
            self.reviewChallenge = ReviewChallenge
            self.end = End
            self.challenge = Challenge if Challenge is not None else []
            self.finishMessage = FinishMessage

        def interpret(self) -> tuple:
            """Return all Redeem fields as a tuple."""
            return (self.id, self.name, self.need, self.actions,
                    self.perfectChallenge, self.reviewChallenge,
                    self.end, self.challenge, self.finishMessage)

        def __call__(self) -> tuple:
            """Interpret actions and challenges, returning the effect tuple."""
            # Check regular actions first
            for action in self.actions:
                result = self._interpret_action(action)
                if result:
                    return result

            # Check challenge actions
            for action in self.challenge:
                result = self._interpret_action(action)
                if result:
                    return result

            return ()

        @staticmethod
        def _interpret_action(action) -> Optional[tuple]:
            """Interpret a single action, returning effect tuple or None."""
            act_str = action.interpret()
            if not act_str:
                return None

            parts = act_str.split(" ")

            if "points" in act_str:
                if len(parts) >= 3:
                    if "add" in act_str:
                        return ("addpoints", parts[2])
                    elif "del" in act_str:
                        return ("delpoints", parts[2])
                    elif "set" in act_str:
                        return ("setpoints", parts[2])

            elif "lcgodmaker" in act_str:
                if "levelup" in act_str and len(parts) >= 3:
                    return ("perfectChallenge",
                            f"ARG 修仙等级提高 {parts[2]} 级别后，@Bot主 来解除 PERFECT CHALLENGE 锁。")

            elif "send" in act_str:
                if "content" in act_str and len(parts) >= 3:
                    return ("reviewChallenge", parts[2])

            return None

    class Area:
        """A map area with redeems and progress tracking."""

        def __init__(self, MapName: str, MapID: int, Redeems: list,
                     Start: int, AllKMS: int, Finish: int = 0, End: int = 0):
            self.mapName = MapName
            self.mapID = MapID
            self.redeems = Redeems
            self.start = Start
            self.end = End
            self.allKMS = AllKMS
            self.finish = Finish

        def interpret(self) -> tuple:
            return (self.mapName, self.mapID, self.redeems,
                    self.start, self.end, self.allKMS, self.finish)


class MainInterpret:
    """Main interpreter for map content and user actions."""

    def __init__(self, mapEntity: MapContent.Area):
        self.mapName = mapEntity.mapName
        self.mapID = mapEntity.mapID
        self.redeems: List[MapContent.Redeem] = mapEntity.redeems
        self.start = mapEntity.start
        self.end = mapEntity.end
        self.allKMS = mapEntity.allKMS

    def _get_user_map_path(self, user_id: str) -> str:
        """Get the path to a user's map data file."""
        return f'./data/map/{user_id}.gmData'

    def _read_map_data(self, user_id: str) -> dict:
        """Read a user's map data with error handling."""
        path = self._get_user_map_path(user_id)
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError, OSError) as e:
            _error(f"Failed to read map data for {user_id}: {e}")
            return {}

    def _write_map_data(self, user_id: str, data: dict):
        """Write a user's map data with error handling."""
        path = self._get_user_map_path(user_id)
        try:
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=4)
        except OSError as e:
            _error(f"Failed to write map data for {user_id}: {e}")

    def interpret(self, userObject, action: Literal["select", "addkm", "checkredeem",
                   "redeem", "isend", "nextRedeem"], params: list = None):
        """Interpret and execute a map action for a user.

        Args:
            userObject: The user object (with .super access to uic.User).
            action: The action to perform.
            params: Additional parameters for the action.
        """
        if params is None:
            params = []

        user_id = userObject.super.id
        mapData = self._read_map_data(user_id)
        if not mapData:
            return

        if action == "select":
            self._handle_select(mapData, user_id)
        elif action == "addkm":
            self._handle_addkm(mapData, user_id, params)
        elif action == "checkredeem":
            return self._handle_checkredeem(mapData)
        elif action == "redeem":
            self._handle_redeem(mapData, user_id, userObject)
        elif action == "isend":
            return mapData.get("MapKilometres", 0) >= self.end
        elif action == "nextRedeem":
            self._handle_next_redeem(mapData, user_id, params)

        userObject.save()
        userObject.super.save()
        userObject.load()

    def _handle_select(self, mapData: dict, user_id: str):
        """Handle map selection action."""
        mapData["MapSelect"] = self.mapName
        mapData["MapKilometres"] = 0
        mapData["MapNextRedeem"] = self.redeems[0].need if self.redeems else 0
        mapData["MapRecentKMetres"] = 0
        mapData["MapRecentRedeems"] = []
        self._write_map_data(user_id, mapData)

    def _handle_addkm(self, mapData: dict, user_id: str, params: list):
        """Handle adding kilometers action."""
        if not params:
            return
        km = params[0]
        mapData["MapKilometres"] = mapData.get("MapKilometres", 0) + km
        mapData["MapRecentKMetres"] = mapData.get("MapRecentKMetres", 0) + km
        mapData["MapNextRedeem"] = mapData.get("MapNextRedeem", 0) - km
        self._write_map_data(user_id, mapData)

    def _handle_checkredeem(self, mapData: dict) -> bool:
        """Check if next redeem is available."""
        redeemed_count = len(mapData.get("MapRecentRedeems", []))
        next_idx = redeemed_count + 1
        if next_idx < len(self.redeems):
            return mapData.get("MapKilometres", 0) >= self.redeems[next_idx].need
        return False

    def _handle_redeem(self, mapData: dict, user_id: str, userObject):
        """Handle redeem action."""
        redeemed_count = len(mapData.get("MapRecentRedeems", []))
        next_idx = redeemed_count + 1
        if next_idx >= len(self.redeems):
            return

        if mapData.get("MapKilometres", 0) < self.redeems[next_idx].need:
            return

        mapData["MapKilometres"] = mapData.get("MapKilometres", 0) - self.redeems[next_idx].need
        act = self.redeems[next_idx]()

        self._apply_redeem_effect(act, userObject, mapData)

        mapData.setdefault("MapRecentRedeems", []).append(self.redeems[next_idx].id)
        next_next = next_idx + 1
        if next_next < len(self.redeems):
            mapData["MapNextRedeem"] = self.redeems[next_next].need
        self._write_map_data(user_id, mapData)

    def _apply_redeem_effect(self, act: tuple, userObject, mapData: dict):
        """Apply the effect of a redeem action."""
        if not act:
            return

        effect_type = act[0]
        if effect_type == "addpoints":
            try:
                userObject.super.addScore(float(act[1]))
            except (ValueError, IndexError):
                pass
        elif effect_type == "delpoints":
            try:
                userObject.super.subtPoints(float(act[1]))
            except (ValueError, IndexError):
                pass
        elif effect_type == "setpoints":
            try:
                userObject.super.score = float(act[1])
            except (ValueError, IndexError):
                pass
        elif effect_type == "perfectChallenge":
            mapData["Locking"] = [True, {
                "Why": "PERFECT CHALLENGE",
                "HowUnlock": act[1] if len(act) > 1 else ""
            }]
        elif effect_type == "reviewChallenge":
            mapData["Locking"] = [True, {
                "Why": "REVIEW CHALLENGE",
                "HowUnlock": act[1] if len(act) > 1 else ""
            }]
        elif effect_type == "addkm":
            try:
                userObject.addKMs(act[1])
            except (ValueError, IndexError):
                pass

    def _handle_next_redeem(self, mapData: dict, user_id: str, params: list):
        """Handle force-next-redeem action."""
        if not params:
            return
        redeemed = mapData.setdefault("MapRecentRedeems", [])
        target_idx = params[0] + 1
        if target_idx < len(self.redeems):
            redeemed.append(self.redeems[target_idx].id)
            mapData["MapNextRedeem"] = self.redeems[target_idx + 1].need if target_idx + 1 < len(self.redeems) else 0
            self._write_map_data(user_id, mapData)

# end
