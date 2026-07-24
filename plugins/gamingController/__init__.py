import json
import os

import plugins.userInfoController as uic
from toolsbot.configs import DATA_PATH

from . import mapInterpreter as mapi

"""
TLoH Bot
Tools Bot 的第二版。

@author: BL-BlueLighting

gamingController
"""

TITLE = "TLoH Bot"

class MapUser :
    def __init__(self, user_id: str):
        self.super = uic.User(user_id)
        self.mapSelect = "ToolsBot 区域"
        self.mapKMs = 0
        self.mapRecentKMS = 0
        self.mapKMInstanceNext = 0
        self.locking = [False, {}]
        self.kmNext = 0
        self.mapRecentRedeems = []
        self.gm_data_path = DATA_PATH / "map" / f"{self.super.id}.gmdata"
        self.map_path = DATA_PATH / "map.json"
        self.load()

    def save(self):
        self.super.save()

        """
        {
            "ID": "[UserID]",
            "MapSelect": "ToolsBot 区域",
            "MapKilometres": 999,
            "MapNextRedeem": 1,
            "MapRecentKMetres": 1023,
        }
        """
        mapInfo = {
            "ID": self.super.id,
            "MapSelect": self.mapSelect,
            "MapKilometres": self.mapKMs,
            "MapNextRedeem": self.mapKMInstanceNext,
            "MapRecentKMetres": self.mapRecentKMS,
            "Locking": self.locking,
            "MapNextKM": self.kmNext,
            "MapRecentRedeems": self.mapRecentRedeems
        }

        with open(self.gm_data_path, "w", encoding="utf-8") as f:
            json.dump(mapInfo, f, indent=4, ensure_ascii=False)

    def load(self):
        if os.path.exists(self.gm_data_path):
            with open(self.gm_data_path, "r", encoding="utf-8") as f:
                mapInfo = json.load(f)
                self.mapSelect = mapInfo["MapSelect"]
                self.mapKMs = mapInfo["MapKilometres"]
                self.mapKMInstanceNext = mapInfo["MapNextRedeem"]
                self.mapRecentKMS = mapInfo["MapRecentKMetres"]
                self.locking = mapInfo["Locking"]
                self.kmNext = mapInfo["MapNextKM"]
                self.mapRecentRedeems = mapInfo["MapRecentRedeems"]
        else:
            self.save()

    def mapSelects(self):
        # get maps
        with open(self.map_path, "r", encoding="utf-8") as f:
            maps = json.load(f)

        # get map informations
        mapInfo = []

        for _map, _mapPath in maps ["Maps"].items():
            mapInfo.append(_map)

        return mapInfo

    def setMap(self, map: str):
        if not map in self.mapSelects():
            return False

        self.mapSelect = map
        self.save()
        return True

    def getMapPath(self):
        with open(self.map_path, "r", encoding="utf-8") as f:
            for _map, _mapPath in json.load(f)["Maps"].items():
                if _map == self.mapSelect:
                    return _mapPath

        raise Exception("Invaild map in userdata.")

    def addKMs(self, kms: int):
        self.mapKMs += kms
        self.mapRecentKMS += kms
        self.save()

        # call interpreter
        return mapi.runAndInterpret(self.getMapPath(), self, "addkm", [kms])

    def selectMap(self, map: str):
        if not self.setMap(map):
            return False

        self.mapSelect = map
        return mapi.runAndInterpret(self.getMapPath(), self, "select", [])

    def checkRedeem(self):
        return mapi.runAndInterpret(self.getMapPath(), self, "checkRedeem", [])

    def redeem(self):
        return mapi.runAndInterpret(self.getMapPath(), self, "redeem", [])

    def forceRedeem(self):
        if not self.super.id in ["2733392694"]:
            return False
        return mapi.runAndInterpret(self.getMapPath(), self, "nextRedeem", [])

    def isEnd(self) -> bool:
        return mapi.runAndInterpret(self.getMapPath(), self, "isEnd", [])

"""
map_command = on_command("map", priority=5)

@map_command.handle()
async def _(bot: Bot, event: GroupMessageEvent | PrivateMessageEvent, args: Message = CommandArg()):
    msg = "TLoH Bot - 区域功能 - MAP SKILL\n"
    arg = args.extract_plain_text()
    head = arg.split(" ") [0]
    _iduser = str(event.user_id)
    mapUser = MapUser(_iduser)

    if len(arg) != 1 and len(arg) != 0:
        params = arg.split(" ") [1:]

    if head == "help" or head == "":
        msg += "    - ^map select: 选择地图\n"
        msg += "    - ^map redeem: 尝试领取奖励\n"
        msg += "    - ^map look: 查看跑图情况\n"
        msg += "    - ^map next: (在解锁了的情况下) 前进\n"

    elif head == "forceNext":
        msg += "    - 正在解锁..."
        if mapUser.forceRedeem():
            mapUser.save()
            mapUser.addKMs(999)
            msg += "\n    - 解锁成功。已前进。"
        else:
            msg += "\n    - 解锁失败。"

    elif head == "select":
        if len(params) == 0:
            msg += "    - 请输入地图名。"
        else:
            if mapUser.selectMap(params[0]):
                msg += "    - 已选择地图。"
            else:
                msg += "    - 地图不存在。"

    elif head == "redeem":
        msg += "    - 正在领取奖励..."
        if mapUser.redeem():
            msg += "\n    - 领取成功。"
        else:
            msg += "\n    - 领取失败。"

    elif head == "look":
        msg += "    - 当前地图: " + mapUser.mapSelect
        msg += "\n    - 当前公里数: " + str(mapUser.mapKMs)
        msg += "\n    - 距离下个奖励: " + str(mapUser.mapKMInstanceNext)
        msg += "\n    - 总公里数: " + str(mapUser.mapRecentKMS)

        if mapUser.locking [0] == True:
            msg += "\n    ! MAP IS LOCKING !"
            msg += f"\n    ! {mapUser.locking [1].get("Why")} !"
            msg += "\n    - 您需要解锁您的地图。\n    - 为了解锁您的地图，请完成以下条件："
            msg += "\n    - " + mapUser.locking [1].get("HowUnlock")

    elif head == "next":
        if mapUser.kmNext == 0:
            msg += "\n    - 您还没有获得里程。\n    - 请继续使用 ToolsBot 来获得里程。"
        else:
            msg += "    - 正在前进..."
            if mapUser.addKMs(mapUser.kmNext):
                msg += "\n    - 前进成功。"
                if mapUser.mapKMInstanceNext <= 0:
                    msg += "\n    - ! NEW REDEEM FOUND !\n    - 使用 ^map redeem 来领取奖励。"
            else:
                msg += "\n    - 前进失败。"

    await map_command.finish(msg)


disabled skill, remove comment characters to enable
# 全局 catcher, 犯神经因此我禁用了
global_catcher = on_message(priority=999)

@global_catcher.handle()
async def _(bot: Bot, event: GroupMessageEvent | PrivateMessageEvent):
    _iduser = str(event.user_id)
    mapUser = MapUser(_iduser)

    if random.randint(100, 999) > 150:
        return

    mapUser.kmNext += random.randint(100, 999)
    mapUser.save()


    await global_catcher.send("TLoH Bot - 随机幸运事件\n    - 您的地图跑图进度已增加，可以使用 ^map next 来前进了。")
    global_catcher.skip()

DISABLED GAMING CONTROLLER
"""