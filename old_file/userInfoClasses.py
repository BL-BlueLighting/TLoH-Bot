import json
import logging
import os
import random

logging.basicConfig(
    filename='botlog.log',
    filemode='a',
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

# logging pointers
_info = logging.info
_warn = logging.warning
_error = logging.error
_crit = logging.critical

"""
TLoH Bot
Tools Bot 的第二版。

@author: BL-BlueLighting

userInfoClasses: userInfoController public api
"""

TITLE = "TLoH Bot"

"""
Data 类
User 类的文件管理系统
"""
class Data:
    def __init__(self, id: str):
        """
        Data Class.

        Args:
            id (str): Platform ID.
        """
        # default is ./userdata
        self.dataPath = "./userdata"
        self.id = id
        self.mainPath = self.dataPath + "/" + self.id + ".toolsbot_data"

    def check(self):
        """
        Check userdata exists.
        """
        return os.path.exists(self.mainPath)

    def writeData(self, userClass):
        """
        Write user data.
        Note: Because userClass is a user class, but user is defined after Data class.
        So I will not add type tip to it.
        """
        userData = {
            "ID": userClass.id,
            "Name": userClass.name,
            "Score": userClass.score,
            "boughtItems": userClass.boughtItems,
            "Ban": userClass.banned
        }

        # write in
        with open(self.mainPath, "w", encoding="utf-8") as f:
            f.write(json.dumps(userData))

        # return
        return

    def readData(self) -> dict:
        try:
            with open(self.mainPath, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as ex:
            _error("Error: Failed to read data.\nInformation: \n" + ex.__str__())
            return {}

"""
User 类
整个 userInfoController 的核心大类
"""
class User:
    def __init__(self, id: str, name: str = "", score: float = 0, boughtItems: list[str] = []):
        """
        User Class

        Args:
            id (str): Platform ID.
            name (str, optional): Name of this user. Can be blank. Defaults to "".
            score (int, optional): Score of this user. Default 0. Defaults to 0.
            boughtItems (list[str], optional): BoughtItems. Use 'user.addItem' to add a item for this user. Defaults to [].
        """

        self.id = id
        self.name = name
        self.score = score
        self.boughtItems = boughtItems
        self.banned = False
        self.data = Data(self.id)

        # check
        _info("Data Checking.")
        if self.data.check():
            _info("Data Exists.")
            self.jsonData = self.data.readData()

            # load data from jsonData
            self.id = self.jsonData.get("ID", "10000")
            self.name = self.jsonData.get("Name", "暂未设置")
            self.score = self.jsonData.get("Score", 0.0)
            self.banned = self.jsonData.get("Ban", False)
            self.boughtItems = self.jsonData.get("boughtItems", [])
        else:
            _info("Data Not Found.")
            self.data.writeData(self)

    def save(self):
        """
        Save user data.
        """
        self.data.writeData(self)
        return

    def addItem(self, item: str):
        """
        Add item to user.
        Args:
            item (str): Item name.
        """
        self.boughtItems.append(item)

    def useItem(self, item: str) -> str:
        """
        Use a item from user.
        Args:
            item (str): Item name.
        """
        # load
        with open("./data/item.json", "r", encoding="utf-8") as f:
            itemJson: list[dict] = json.load(f)

        itemEffect = ""
        # fetch
        for _item in itemJson:
            if _item.get("Name", "") == item:
                itemEffect = _item.get("Effect")
                break

        if itemEffect == "":
            return "Not found"

        _info(f"物品：{item} 的效果：" + itemEffect [0]) #type: ignore

        # interpret
        """
        sign = 签到
        ticket = 彩票
        """

        if item not in self.boughtItems:
            return "你没有该物品。"

        if "sign" in itemEffect [0]: #type: ignore
            _info(f"SIGN MODE")
            # get *x
            _x = itemEffect.split(" ") [1] #type: ignore

            # out x
            _x.replace("x", "")

            # read boost
            with open("./data/boostMorningd.json", "r", encoding="utf-8") as f:
                boosts = json.load(f)

            # append boost
            boosts.append({self.id: int(_x)})

            # write boost
            with open("./data/boostMorningd.json", "w", encoding="utf-8") as f:
                json.dump(boosts, f)

            self.boughtItems.remove(item)
            return f"{_x}x 倍票已使用。下次签到将会获得更多积分。"

        elif "ticket" in itemEffect [0]: #type: ignore
            _info(f"TICKET MODE")
            _randomNum = random.randint(1, 1000000000000) # 人：傻逼
            _randomMoney = random.randint(1, 100)
            if _randomNum == 114514:
                self.addScore(10000000000.0)
                self.boughtItems.remove(item)
                self.save()
                return "中奖了。获得积分：100,0000,0000。"
            else:
                self.addScore(float(_randomMoney))
                self.boughtItems.remove(item)
                self.save()
                return f"未中奖。但获得安慰奖 {_randomMoney}"
        else:
            return "很抱歉。内部出现错误。"

    def addScore(self, score: float):
        """
        Add score to user.

        Args:
            score (float): Score.
        """

        self.score += score
        return

    def subtScore(self, score: float):
        """
        Subtract score.

        Args:
            score (float): _description_
        """
        self.score -= score
        return

    def getScore(self) -> float:
        """
        Get score from user
        """
        return self.score

    def isBanned(self) -> bool:
        """
        Is this user banned?
        """
        return self.banned #type: ignore
    