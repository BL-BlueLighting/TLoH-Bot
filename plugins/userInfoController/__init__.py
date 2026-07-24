import datetime
import json
import os
import random
import re
import sqlite3
from collections import Counter
from typing import Any, Dict, Literal

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

class EasyCallQQUserObject:
    def __init__(self, user_info: dict):
        self.user_info = user_info
        self.userdata = user_info

    def GetNick(self) -> str:
        """获取用户昵称"""
        return self.userdata.get("nick", "<Failed to Fetch>")

    def GetPosition(self) -> str:
        """获取用户地区"""
        # 拼接
        """   
        "country": "中国",
        "province": "贵州",
        "city": "遵义",
        """
        return f"{self.userdata.get('country', '')} {self.userdata.get('province', '')}省{self.userdata.get('city', '')}市".strip()

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
        return "沃尔玛塑料袋" # 不是除了男和女还能设置什么，qnmd pylance

    def GetVIPType(self) -> str:
        """获取用户 VIP 类型"""
        # qq vip 接口返回的是月度 vip 与年度 vip，分别使用 is_vip 与 is_year_vip 获取，均为 bool.
        is_vip = self.userdata.get("is_vip", False)
        is_year_vip = self.userdata.get("is_year_vip", False)
        if is_vip and is_year_vip:
            return "年度 VIP"
        elif is_vip:
            return "月度 VIP"
        elif is_year_vip:
            return "年度 VIP"
        else:
            return "非 VIP"

class EasyCall:
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
    
    async def GetUserObject(self, user_id: str) -> EasyCallQQUserObject:
        """获取 EasyCallQQUserObject 对象"""
        user_info = await self.GetInformationOfUser(user_id)
        return EasyCallQQUserObject(user_info)

class Database:
    # 这个 class 是后来加的，Data class 没用这个类
    def __init__(self):
        self.db_path = DATA_PATH / "userdata.db"

    def run_sql(self, sql: str, params: tuple = ()):
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(sql, params)
            conn.commit()
            return cursor.fetchall()

class Data:
    def __init__(self, id: str):
        """
        Data Class.

        Args:
            id (str): Platform ID.
        """
        self.id = id
        self.db_path = DATA_PATH / "userdata.db"
        self._init_db()

    async def GetQQUserObject(self) -> EasyCallQQUserObject:
        """获取 EasyCallQQUserObject 对象"""
        bot: v11bot = nonebot.get_bot() #type:ignore
        easy_call = EasyCall(bot, None)  # 这里的 event 填为 None，因为我们只需要 user_id
        return await easy_call.GetUserObject(self.id)

    def _init_db(self):
        """初始化数据库和表结构"""
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

    def check(self) -> bool:
        """
        Check userdata exists.
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT 1 FROM users WHERE ID = ?", (self.id,))
            return cursor.fetchone() is not None

    def writeData(self, userClass):
        """
        Write user data.
        Note: Because userClass is a user class, but user is defined after Data class.
        So I will not add type tip to it.
        """
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

    def readData(self) -> Dict[str, Any]:
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
        except Exception as ex:
            _error("Error: Failed to read data.\nInformation: \n" + str(ex))
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
        self.warningd = 0

        try:
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
                self.warningd = self.jsonData.get("Warningd", 0)
            else:
                _info("Data Not Found.")
                self.data.writeData(self)
        except Exception as ex:
            _error("Error: Failed to read or write data." + ex.__str__())

        if self.warningd >= 10:
            self.banned = True
            _info(f"User '{self.id}' has been banned because of excessive warnings.")

        if self.score < 0:
            self.banned = True

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
        self.save()

    def useItem(self, item: str) -> str:
        """
        Use a item from user.
        Args:
            item (str): Item name.
        """
        # load
        with open(DATA_PATH / "item.json", "r", encoding="utf-8") as f:
            itemJson: list[dict] = json.load(f)

        itemEffect = ""
        # fetch
        for _item in itemJson:
            if _item.get("Name", "") == item:
                itemEffect = _item.get("Effect")
                break

        if item == "iai" or item == "棍母" or item == "滚木" or item == "BL.BlueLighting" or item == "小薯":
            itemEffect = ["spe "+item]

        #_info(f"物品：{item} 的效果：" + itemEffect [0]) #type: ignore

        # interpret
        """
        sign = 签到
        ticket = 彩票
        """

        if item not in self.boughtItems:
            return "你没有该物品。"

        if itemEffect == "":
            _rv = random.randint(1, 10)
            if _rv > 5:
                return "我们在瞎搞"
            elif _rv > 7:
                return "窝们在瞎搞"
            elif _rv > 9:
                return "窝们载瞎镐"
            else:
                return "求 iai 继续更新日期"

        if "sign" in itemEffect [0]: #type: ignore
            _info(f"SIGN MODE")
            # get *x

            _x = itemEffect [0].split(" ") [1] #type: ignore

            # out x
            _x = _x.replace("x", "")

            # read boost
            with open(DATA_PATH / "boostMorningd.json", "r", encoding="utf-8") as f:
                boosts = json.load(f)

            # append boost
            boosts.append({self.id: int(_x)})

            # write boost
            with open(DATA_PATH / "boostMorningd.json", "w", encoding="utf-8") as f:
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

        elif "playmode" in itemEffect [0]: #type: ignore
            if "enable" in itemEffect [0]: #type: ignore
                self.boughtItems.remove(item)
                self.boughtItems.append("play")
                self.save()
                return "已启用娱乐模式。"
            else:
                if "play" in self.boughtItems:
                    self.boughtItems.remove("play")
                    self.save()
                return "已关闭娱乐模式。"
        elif "spe" in itemEffect [0]:#type: ignore
            if "iai" in itemEffect [0]:#type: ignore
                return "芝士 ARG 作者"
            elif "棍母" or "滚木" in itemEffect [0]:#type: ignore
                return "？请不要使用空白物品谢谢"
            elif "BL.BlueLighting" in itemEffect [0]:#type: ignore
                return "芝士 Bot 主"
            elif "小薯" in itemEffect [0]:#type: ignore
                return "南边的桥梁。" 
            else:
                return "???"
        else:
            return "很抱歉。内部出现错误。"

    def aiWarningd(self):
        self.warningd += 1

    def echoWarningd(self):
        self.warningd += 2


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

    def playMode(self) -> bool:
        """
        Is this user enabled play mode (娱乐模式 \\ 骂人模式？) ?
        """
        return "play" in self.boughtItems

    def existsItem(self, item: str) -> bool:
        """
        Is this user has got this item?
        """
        return item in self.boughtItems

"""
检测at了谁，返回[qq, qq, qq,...]
包含全体成员直接返回['all']
如果没有at任何人，返回[]
:param data: event.json
:return: list

@author: Unk, Not me
"""

def At(data: str):
    try:
        qq_list: list = []
        data_: dict = json.loads(data)
        for msg in data_["message"]:
            if msg["type"] == "at":
                if 'all' not in str(msg):
                    qq_list.append(msg["data"]["qq"])
                else:
                    return ['all']
        return qq_list
    except KeyError:
        return []

"""
GetInfo 函数。
获取该账号 / 其他账号的数据

@author: BL-BlueLighting
"""
getinfo_function = on_command("info", aliases={"获取账户信息"}, priority=10)

@getinfo_function.handle()
async def _ (bot: v11bot, event: GroupMessageEvent | PrivateMessageEvent, args: Message = CommandArg()):
    msg = TITLE + " 用户面板"

    try:
        at = At(event.json()) [0]
    except IndexError:
        at = ""

    user = User(event.get_user_id())

    if not user.isBanned():
        if at == "":
            # see self
            msg += f"\n   - 用户 ID: {user.id}"
            msg += f"\n   - 用户昵称: {user.name}"
            msg += f"\n   - 用户积分：{user.score}"
        else:
            # see another one
            user = User(at)
            msg += f"\n   - 用户 ID: {user.id}"
            msg += f"\n   - 用户昵称: {user.name}"
            msg += f"\n   - 用户积分：{user.score}"
    else:
        if user.playMode():
            msg += "\n   - 你他妈被封禁了还来玩？滚"
        else:
            msg += "\n   - 您的账号已被封禁，请联系管理员解封。"

    await getinfo_function.finish(msg)

"""
每日签到功能

@author: BL-BlueLighting
"""

# 定义数据文件路径
BOOST_DATA_PATH = DATA_PATH / "boostMorningd.json"
MORNING_DATA_PATH = DATA_PATH / "morningd.json"

morningToday_function = on_command("morning", aliases={"早上好"}, priority=10)

@morningToday_function.handle()
async def _(bot: v11bot, event: GroupMessageEvent | PrivateMessageEvent, args: Message = CommandArg()):
    msg = f"{TITLE} 签到\n"
    user_id_str = str(event.get_user_id()) # 确保用户ID是字符串
    current_user = User(user_id_str)

    # 检查用户是否被封禁
    if current_user.isBanned():
        if current_user.playMode():
            msg += "    - 你他妈被封禁了还来签到？滚"
        else:
            msg += "    - 您的账号已被封禁，请联系管理员解封。"

        await morningToday_function.finish(msg)

    # --- 1. 安全加载 Boost 数据 ---
    boosts = []
    if os.path.exists(BOOST_DATA_PATH):
        try:
            with open(BOOST_DATA_PATH, "r", encoding="utf-8") as f:
                boosts = json.load(f)
        except json.JSONDecodeError:
            print(f"Warning: {BOOST_DATA_PATH} is corrupted. Starting with an empty boost list.")
            boosts = []

    applied_boost_value = 1.0 # 默认没有Boost

    # 查找并应用用户专属Boost，同时从列表中移除已应用的Boost
    boost_found_and_removed = False
    for i, boost_entry in enumerate(boosts):
        if user_id_str in boost_entry:
            try:
                # 确保获取到的Boost值是数字类型
                applied_boost_value = float(boost_entry[user_id_str])
                del boosts[i] # 移除已使用的Boost
                boost_found_and_removed = True
                break # 每次签到只消耗一个Boost
            except (ValueError, TypeError):
                print(f"Warning: Invalid boost value found for user {user_id_str} in {BOOST_DATA_PATH}.")
                # 可以选择移除此无效条目，或跳过
                continue

    # 如果有Boost被移除，立即保存Boost文件
    if boost_found_and_removed:
        with open(BOOST_DATA_PATH, "w", encoding="utf-8") as f:
            json.dump(boosts, f, ensure_ascii=False, indent=4)

    # --- 2. 安全加载签到记录数据 ---
    morningd_records = []
    if os.path.exists(MORNING_DATA_PATH):
        try:
            with open(MORNING_DATA_PATH, "r", encoding="utf-8") as f:
                morningd_records = json.load(f)
        except json.JSONDecodeError:
            print(f"Warning: {MORNING_DATA_PATH} is corrupted. Starting with an empty morningd list.")
            morningd_records = []

    # --- 3. 检查用户签到状态 ---
    today = datetime.date.today()
    user_record = None
    user_record_index = -1

    for i, record in enumerate(morningd_records):
        if record.get("Id") == user_id_str:
            user_record = record
            user_record_index = i
            break

    if user_record:
        # 用户有签到记录
        last_sign_date_str = user_record.get("LastSignDate")
        if last_sign_date_str:
            try:
                last_sign_date = datetime.datetime.strptime(last_sign_date_str, "%Y-%m-%d").date()
                if last_sign_date == today:
                    if current_user.playMode():
                        msg += "    - 你他妈掉钱眼子里了？今天已经签到过了，明天再来！"
                    else:
                        msg += "    - 您今天已经签到过了，请明天再来！"
                    await morningToday_function.finish(msg)
                else:
                    # 更新签到日期为今天
                    morningd_records[user_record_index]["LastSignDate"] = today.strftime("%Y-%m-%d")
            except ValueError:
                # 日期格式错误，当作新签到处理
                print(f"Warning: Invalid date format for user {user_id_str} in {MORNING_DATA_PATH}. Treating as new sign-in.")
                morningd_records[user_record_index]["LastSignDate"] = today.strftime("%Y-%m-%d")
        else:
            # 记录中没有LastSignDate，当作新签到处理
            morningd_records[user_record_index]["LastSignDate"] = today.strftime("%Y-%m-%d")
    else:
        # 用户没有签到记录，添加新记录
        morningd_records.append({
            "Id": user_id_str,
            "LastSignDate": today.strftime("%Y-%m-%d")
            # "Morningd": True 字段在此逻辑中不再必要，因为LastSignDate已经足够判断
        })

    # 保存更新后的签到记录
    with open(MORNING_DATA_PATH, "w", encoding="utf-8") as f:
        json.dump(morningd_records, f, ensure_ascii=False, indent=4)

    # --- 4. 执行签到并计算积分 ---
    earned_money = float(random.randint(70, 100)) * applied_boost_value

    current_user.addScore(earned_money)
    current_user.save()

    msg += "    - 签到成功！"
    msg += f"\n    - 您今天签到获得了 {earned_money:.2f} 积分。" # 格式化为两位小数
    msg += f"\n    - 目前您的积分为 {current_user.getScore():.2f}。" # 格式化为两位小数

    await morningToday_function.finish(msg)

    # fuck logic, how long

"""
setinfo 函数 (管理员专用)
用于设置用户的各项信息 (乌萨奇行)

@author: BL-BlueLighting
"""

setinfo_function = on_command("setinfo", priority=10, permission=SUPERUSER)

@setinfo_function.handle()
async def _ (bot: v11bot, event: GroupMessageEvent | PrivateMessageEvent, args: Message = CommandArg()):
    msg = TITLE + " 设置信息"
    _msg = args.extract_plain_text()
    try:
        at = At(event.json()) [0]
    except IndexError:
        at = ""

    user = User(at)

    if at == "":
        msg += "\n    - 使用方法： ^setinfo [@用户] [项目 (id, name, score, banned)] [值]"
        await setinfo_function.finish(msg)

    arg = args.extract_plain_text().split(" ")
    item = arg [1]
    value = arg [2]

    if item == "id":
        user.id = value
        msg += f"\n    - 用户的 {item} 已设为 {value}"
    elif item == "name":
        user.name = value
        msg += f"\n    - 用户的 {item} 已设为 {value}"
    elif item == "score":
        user.score = float(value)
        msg += f"\n    - 用户的 {item} 已设为 {value}"
    elif item == "banned":
        user.banned = value == "true"
        msg += f"\n    - 用户的 {item} 已设为 {value}"
    else:
        msg += f"\n    - 语法错误。"

    user.save()

    await setinfo_function.finish(msg)

"""
buy 函数
购买和使用物品

@author: BL-BlueLighting
"""

"""
TLoH Bot
PILLAR OF SHAME
QQ 3829537708
QQ 3562258276
QQ 287280700 (GROUP)
"""

buy_function = on_command("buy", priority=10)

@buy_function.handle()
async def _ (bot: v11bot, event: GroupMessageEvent | PrivateMessageEvent, args: Message = CommandArg()):
    msg = TITLE + " 商店"
    user = User(event.get_user_id())
    _msg = args.extract_plain_text()

    if user.banned:
        msg += "\n    - 滚"
        await buy_function.finish(msg)

    if _msg == "":
        msg += "\n    - 使用 ^buy list 来查看列表"
        await buy_function.finish(msg)

    with open(DATA_PATH / "item.json", "r", encoding="utf-8") as f:
        items = json.load(f)
    arg = args.extract_plain_text().split(" ")

    if arg [0] == "list":
        msg += """\n    - 商店状态：售卖中
    - 物品："""

        for item in items:
            msg += f"\n    - {item.get("Name", "未知")} 价格 {item.get("Cost", 0)}"

        msg += "\n    - 使用 ^buy thing [物品名称] 来购买"
    elif arg [0] == "thing":
        msg += "\n   - 购买商品"
        if len(arg) == 2:
            arg.append("1")
        elif len(arg) == 1:
            if user.playMode():
                msg += "\n    - 购买失败，原因：你他妈填名字没有就来买？"
            else:
                msg += "\n    - 购买失败，原因：请填写物品名称"
            await buy_function.finish(msg)

        msg += f"\n    - 购买物品：{arg [1]}"
        msg += f"\n    - 数量: {arg [2]}"
        msg += f"\n    - 交付中..."

        if int(arg[2]) >= 100:
            if user.playMode():
                msg += f"\n    - 交付失败，原因：购买数量过大。你他妈买这么多干啥？"
            else:
                msg += f"\n    - 交付失败，原因：购买数量过大。"
            await buy_function.finish(msg)

        # fetch
        global _cost
        _cost = 0.0
        for item in items:
            if item.get("Name") == arg [1]:
                _cost = item.get("Cost", 0.114)

        if _cost == 0.114514:
            if user.playMode():
                msg += f"\n    - 交付失败，原因：该商品不存在。你他妈买个寂寞？"
            else:
                msg += f"\n    - 交付失败，原因：该商品不存在。"
            await buy_function.finish(msg)

        # calc
        _subtScore = int(arg [2]) * _cost

        if _subtScore < 0:
            _subtScore = float(str(_subtScore).replace("-", ""))
            _cost = 0

        if user.score >= _subtScore:
            msg += f"\n    - 扣除积分：{_subtScore}"
            msg += f"\n    - 交付成功。"
            user.addScore(-_subtScore)

            for i in range(int(arg [2])):
                user.addItem(arg [1])

            user.save()
        else:
            if user.playMode():
                msg += f"\n    - 交付失败，原因：余额不足。你他妈穷成这样还想买东西？"
            else:
                msg += f"\n    - 交付失败，原因：余额不足"

        msg += f"\n    - 购买结束。请使用 ^buy use {arg [1]} {arg [2]} (若只买了单份或只想使用单份可不填) 来使用商品。"

    elif arg [0] == "use":
        if len(arg) == 1:
            if user.playMode():
                msg += "\n    - 使用失败，原因：你他妈填名字没有就来用？"
            else:
                msg += "\n    - 请填写物品"
            await buy_function.finish(msg)
        elif len(arg) == 2:
            arg.append("1")

        msg += f"\n    - 使用物品 {arg [1]}"
        msg += f"\n    - 使用数量 {arg [2]}"

        for i in range(int(arg [2])):
            msg += f"\n    - {user.useItem(arg [1])}"

    await buy_function.finish(msg)

# ai func go to ai_funcs.py

"""
UseCode 函数
兑换码，没几个人能拿得到的那种

@author: BL-BlueLighting
"""

code_function = on_command("usecode", aliases={"code"}, priority=10)

@code_function.handle()
async def _ (bot: v11bot, event: GroupMessageEvent | PrivateMessageEvent, args: Message = CommandArg()):
    msg = TITLE = " "
    user = User(event.get_user_id())
    msgr = args
    if not user.isBanned():
        if msgr.extract_plain_text().split(" ")[0] == "":
            msg += f"\nTLoH Bot 兑换码兑换"
            msg += f"\n    - 输入 *usecode [兑换码] 以兑换"
        else:
            msg += f"\nTLoH Bot 兑换码兑换"
            with open(DATA_PATH / "codes.json","r") as f:
                present_code_dict = json.load(f)
            present_codes = list(present_code_dict.keys())
            code = msgr.extract_plain_text().split(" ")[0]
            if code in present_codes:
                userid = event.get_user_id()
                user = User(userid)
                user.addScore(int(present_code_dict[code]))
                user.save()
                msg += "\n    - 兑换成功"
                msg += f"\n    - 当前用户积分: {user.getScore()}"
                msg += "\n    - 兑换码: " + code
                msg += "\n    - 兑换积分: " + present_code_dict[code]
                del present_code_dict [code]
                with open(DATA_PATH / "codes.json","w+") as f:
                    f.write(str(present_code_dict))
                await code_function.finish(msg)
            else:
                msg += "\n    - 兑换失败: 兑换码无效"
                msg += "\n    - 兑换码: " + code.replace("\nToolsBot","")
                msg += "\n    - 兑换积分: 0"
                await code_function.finish(msg)
    else:
        msg += "\nTLoH Bot 兑换码兑换"
        msg += "\n    - 您的账户已被封禁。\n"
        await code_function.finish(msg)

"""
交易函数

@author: BL-BlueLighting
"""

pay_eventer = on_command("pay", aliases={"交易", "向对方转钱"}, priority=5)

@pay_eventer.handle()
async def _(bot: v11bot, event: GroupMessageEvent | PrivateMessageEvent, args: Message = CommandArg()):
    msg = f"{TITLE} 交易\n"
    _msg = args.extract_plain_text()

    sender_user = User(str(event.get_user_id()))

    # Check if the sender is banned
    if sender_user.isBanned():
        if sender_user.playMode():
            msg += "    - 你他妈被封禁了还想交易？滚"
        else:
            msg += "    - 您的账号已被封禁，请联系管理员解封。"

        await pay_eventer.finish(msg)

    # If no arguments are provided, show usage help
    if not _msg:
        await pay_eventer.finish(msg + "    - 输入 ^pay [@对方] [金额] 以交易")

    # Use a try-except block to handle parsing and potential errors gracefully
    try:
        # Extract the mentioned user's ID
        # MessageSegment.at() is the correct way to get the at information
        receiver_id = At(event.json()) [0]

        # Split the message to get the amount
        parts = _msg.split()

        money = int(parts[0])

        # Get the receiver's user object
        receiver_user = User(receiver_id)

    except (ValueError, IndexError):
        # Catch errors if the amount is not an integer or is missing
        if sender_user.playMode():
            msg += "    - 你他妈语法都不会还想交易？滚"
        else:
            msg += "    - 语法错误或金额不是正整数"
        await pay_eventer.finish(msg)
    except Exception:
        # Generic catch for any other unexpected errors
        if sender_user.playMode():
            msg += "    - 你他妈语法都不会还想交易？滚"
        else:
            msg += "    - 发生未知错误，请检查格式"
        await pay_eventer.finish(msg)

    # Prevent self-transfer
    if sender_user.id == receiver_user.id:
        if sender_user.playMode():
            msg += "    - 你他妈自己给自己转钱？脑子有病吧？"
        else:
            msg += "    - 你不能给自己转钱"
        await pay_eventer.finish(msg)

    # Check if receiver is banned (this is a good practice)
    if receiver_user.isBanned():
        if sender_user.playMode():
            msg += "    - 你他妈想给个封禁用户转钱？滚"
        else:
            msg += "    - 交易失败: 对方账号已被封禁，无法收款"
        await pay_eventer.finish(msg)

    # Check for valid amount and sufficient balance
    if money > 0 and sender_user.getScore() >= money:
        sender_user.subtScore(float(money))
        sender_user.save()
        receiver_user.addScore(float(money))
        receiver_user.save()

        msg += "     - 交易成功\n"
        msg += f"    - {sender_user.name} 当前积分: {sender_user.getScore():.2f}\n"
        msg += f"    - {receiver_user.name} 当前积分: {receiver_user.getScore():.2f}"
    else:
        msg += "     - 交易失败\n"
        if sender_user.playMode():
            msg += "     - 失败原因: 你他妈穷成这样还想转钱？滚"
        else:
            msg += "     - 失败原因: 积分不足或交易金额小于等于零"

    await pay_eventer.finish(msg)

"""
回声功能

@author: BL-BlueLighting
"""

echo_eventer = on_command("echo", aliases={"说"}, priority=5)

@echo_eventer.handle()
async def _(bot: v11bot, event: GroupMessageEvent | PrivateMessageEvent, args: Message = CommandArg()):
    # 提取纯文本参数，并去除首尾空格
    _msg = args.extract_plain_text().strip()

    # 实例化用户，并使用 str() 确保 ID 类型正确
    user = User(str(event.get_user_id()))

    # 检查用户是否被封禁
    if user.isBanned():
        # 如果被封禁，直接返回封禁提示
        await echo_eventer.finish(f"{TITLE} ECHO\n    - 乐，没想到吧，你被封禁了连 echo 都用不了")

    # 如果没有提供任何文本，也给出提示
    if not _msg:
        await echo_eventer.finish(f"{TITLE} ECHO\n    - 用法: ^echo [内容]")

    #  检测词语
    with open(DATA_PATH / "echoFailedWords.json", "r", encoding="utf-8") as f:
        failedWords = f.read()
    failedWordsList = json.loads(failedWords)["chinese_keywords"]
    failedRegexs = json.loads(failedWords)["regex_patterns"]
    failedEngWordsList = json.loads(failedWords)["exact_matches"]

    # 汉文检测
    for word in failedWordsList:
        if word in _msg:
            user.echoWarningd()
            await echo_eventer.finish(f"{TITLE} ECHO\n    - 键政大师！滚！")

    # 正则表达式检测
    for pattern in failedRegexs:
        if re.search(pattern, _msg):
            user.echoWarningd()
            await echo_eventer.finish(f"{TITLE} ECHO\n    - 键政大师！滚！")

    # 英文检测
    for word in failedEngWordsList:
        if word in _msg:
            user.echoWarningd()
            await echo_eventer.finish(f"{TITLE} ECHO\n    - 键政大师！滚！")

    if _msg == "棍母" or _msg == "棍母" or _msg == "██":
        await echo_eventer.finish("  ")
    # 如果用户未被封禁且提供了文本，则原样返回
    await echo_eventer.finish(_msg)

"""
捡垃圾功能

@author: BL-BlueLighting
"""

wasteTaker_event = on_command("cleanwaste", aliases={"捡垃圾"}, priority=5)

@wasteTaker_event.handle()
async def _(bot: v11bot, event: GroupMessageEvent | PrivateMessageEvent, args: Message = CommandArg()):
    # 统一的随机概率列表
    # 映射关系更清晰，避免使用 index()
    # 属性： (名称, 金额)
    waste_options = [
        ("普通", 1), ("普通", 1), ("普通", 1), ("普通", 1),
        ("垃圾", 0), ("垃圾", 0), ("垃圾", 0), ("垃圾", 0),
        ("垃圾", 0), ("垃圾", 0), ("垃圾", 0), ("垃圾", 0),
        ("中级", 5), ("高级", 10), ("黄金", 100), ("钻石", 10000)
    ]

    # 从列表中随机选择一个
    waste_name, waste_money = random.choice(waste_options)

    msg = f"{TITLE} - 捡垃圾"

    user = User(str(event.get_user_id()))

    if user.isBanned():
        if user.playMode():
            msg += "\n    - 你他妈被封禁了还想捡垃圾？滚"
        else:
            msg += "\n    - 您的账号已被封禁，请联系管理员解封。"
        await wasteTaker_event.finish(msg)

    # 用户未被封禁，执行捡垃圾逻辑
    user.addScore(float(waste_money))
    user.save()

    msg += f"\n    - 你没钱了，你来捡垃圾。"
    msg += f"\n    - 垃圾属性："
    msg += f"\n          类型：{waste_name}"
    msg += f"\n          赚了：{waste_money}"
    msg += f"\n    - 你现在的积分是: {user.getScore():.2f}"

    await wasteTaker_event.finish(msg)

"""
排行榜功能

@author: BL-BlueLighting
"""

list_eventer = on_command("moneybest", aliases={"排行榜"}, priority=5)

@list_eventer.handle()
async def _(bot: v11bot, event: GroupMessageEvent | PrivateMessageEvent, args: Message = CommandArg()):
    msg = f"{TITLE} - 排行榜\n"

    # fixing of new
    # ('1145141919810', '', 0, '[]', 'false', '0', '{}') sample tuple of user
    data = Database()
    easyc = EasyCall(bot, event)
    scores = data.run_sql("SELECT * FROM users ORDER BY Score DESC");

    if not scores:
        msg += "    - 当前没有用户数据"
        await list_eventer.finish(msg)
    
    # get front 10 users
    top_users = scores[:10]
    num = 1
    for user in top_users:
        userObj = await easyc.GetUserObject(user[0])
        msg += f"    - 用户昵称: {userObj.GetNick()} | 用户ID: {user[0]} | 积分: {user[2]:.2f}\n"
        num += 1
    await list_eventer.finish(msg)

"""
ban 函数
封禁用户

@author: BL-BlueLighting
"""

ban_function = on_command("ban", priority=10, permission=SUPERUSER)

@ban_function.handle()
async def _ (bot: v11bot, event: GroupMessageEvent, args: Message = CommandArg()): # 备注:我问你,私聊哪来的at
    msg = f"{TITLE} 管理系统"
    ats = At(event.json())

    if len(ats) == 1:
        user = User(ats [0])
        user.banned = True
        user.save()
        msg += f"\n    - 已封禁用户 {user.id}。"
    elif len(ats) > 1:
        for userId in ats:
            user = User(userId)
            user.banned = True
            user.save()
            await bot.call_api("set_group_ban", group_id=event.group_id, user_id = user.id, duration=2591940)
            msg += f"\n    - 已封禁用户 {user.id}。"
        msg += f"\n    - 本次封禁 {len(ats)} 个用户。"
    else:
        msg += "\n    - 使用 ^ban [@用户] (可封禁多个)"

    await ban_function.finish(msg)

"""
Pardon 函数
解除用户封禁

@author: BL-BlueLighting
"""

pardon_function = on_command("pardon", priority=10, permission=SUPERUSER)

@pardon_function.handle()
async def _ (bot: v11bot, event: GroupMessageEvent | PrivateMessageEvent, args: Message = CommandArg()):
    msg = f"{TITLE} 管理系统"
    ats = At(event.json())

    if len(ats) == 1:
        user = User(ats [0])
        user.banned = False
        user.save()
        msg += f"\n    - 已解封用户 {user.id}。"
    elif len(ats) > 1:
        for userId in ats:
            user = User(userId)
            user.banned = False
            user.save()
            msg += f"\n    - 已解封用户 {user.id}。"
        msg += f"\n    - 本次封禁 {len(ats)} 个用户。"
    else:
        msg += "\n    - 使用 ^pardon [@用户] (可封禁多个)"

    await pardon_function.finish(msg)

"""
BanList 函数
查看封禁用户列表

@author: BL-BlueLighting
"""

banlist_function = on_command("banlist", priority=10) # 普通用户也可以看 banlist

@banlist_function.handle()
async def _ (bot: v11bot, event: GroupMessageEvent | PrivateMessageEvent, args: Message = CommandArg()):
    msg = f"{TITLE} 管理系统"

    # users
    users = os.listdir(DATA_PATH / "userdata")

    for _user in users:
        _user = _user.replace(".toolsbot_data", "")
        user = User(_user)

        if user.isBanned():
            msg += f"\n    - {user.id} 已被封禁"

    if msg == f"{TITLE} 管理系统":
        msg += "\n    - 当前没有被封禁的用户"

    await banlist_function.finish(msg)

"""
AccountStatus 函数
查看当前账号 / 其他账号是否被封禁

@author: BL-BlueLighting
"""

accountstatus_function = on_command("accountstatus", aliases={"accountStatus"}, priority=10)

@accountstatus_function.handle()
async def _ (bot: v11bot, event: GroupMessageEvent | PrivateMessageEvent, args: Message = CommandArg()):
    msg = f"{TITLE} 当前账号情况"
    at = At(event.json())

    if len(at) == 0:

        user = User(event.get_user_id())

        ban = "解禁"
        if user.isBanned():
            ban = "封禁"

        msg += f"\n    - 当前您账号的情况："
        msg += f"\n        - 封禁状态：{ban}"
    else:

        user = User(at [0])

        ban = "解禁"
        if user.isBanned():
            ban = "封禁"

        msg += f"\n    - 当前该账号的情况："
        msg += f"\n        - 封禁状态：{ban}"

    await accountstatus_function.finish(msg)

"""
红包函数
给群友发红包

@author: BL-BlueLighting
"""

redpacket_function = on_command("redpacket", aliases={"发红包"}, priority=5)

@redpacket_function.handle()
async def _ (bot: v11bot, event: GroupMessageEvent | PrivateMessageEvent, args: Message = CommandArg()):
    msg = f"{TITLE} - 发红包"
    user = User(event.get_user_id())

    if user.isBanned():
        if user.playMode():
            msg += "\n    - 你他妈被封禁了还想发红包？滚"
        else:
            msg += "\n    - 您的账号已被封禁，请联系管理员解封。"
        await redpacket_function.finish(msg)

    _msg = args.extract_plain_text().split(" ")

    if len(_msg) < 2:
        msg += "\n    - 使用 ^redpacket [金额] [数量] 来发红包"
        await redpacket_function.finish(msg)

    try:
        money = float(_msg [0])
        number = int(_msg [1])
    except ValueError:
        if user.playMode():
            msg += "\n    - 你他妈语法都不会还想发红包？滚"
        else:
            msg += "\n    - 语法错误或金额不是正整数"
        await redpacket_function.finish(msg)

    if money <= 0 or number <= 0:
        if user.playMode():
            msg += "\n    - 你他妈语法都不会还想发红包？滚"
        else:
            msg += "\n    - 语法错误或金额不是正整数"
        await redpacket_function.finish(msg)

    if user.getScore() < money:
        if user.playMode():
            msg += "\n    - 你他妈穷成这样还想发红包？滚"
        else:
            msg += "\n    - 余额不足"
        await redpacket_function.finish(msg)

    if number > 100:
        if user.playMode():
            msg += "\n    - 发红包数量过多。你他妈有钱不如做慈善。"
        else:
            msg += "\n    - 发红包数量过大。"
        await redpacket_function.finish(msg)

    # ok, start
    user.subtScore(money)
    user.save()

    perMoney = money / number

    msg += f"\n    - 成功发出 {number} 个红包，每个 {perMoney:.2f} 积分。请让群友使用 ^openredpacket 来领取。"

    # save
    redpacket = {
        "UserID": user.id,
        "Money": perMoney,
        "Number": number,
        "TakedUser": []
    }

    # open redpacket data
    redpacket_data_path = DATA_PATH / "redpackets.json"

    if os.path.exists(redpacket_data_path):
        try:
            with open(redpacket_data_path, "r", encoding="utf-8") as f:
                redpackets = json.load(f)
        except json.JSONDecodeError:
            print(f"Warning: {redpacket_data_path} is corrupted. Starting with an empty redpacket list.")
            redpackets = []
    else:
        redpackets = []

    redpackets.append(redpacket)
    with open(redpacket_data_path, "w", encoding="utf-8") as f:
        json.dump(redpackets, f, ensure_ascii=False, indent=4)

    await redpacket_function.finish(msg)

"""
openredpacket 函数
抢红包

@author: Copilot and BL-BlueLighting
"""

openredpacket_function = on_command("openredpacket", aliases={"抢红包"}, priority=5)

@openredpacket_function.handle()
async def _ (bot: v11bot, event: GroupMessageEvent | PrivateMessageEvent, args: Message = CommandArg()):
    msg = f"{TITLE} - 抢红包"
    user = User(event.get_user_id())

    if user.isBanned():
        if user.playMode():
            msg += "\n   - 你他妈被封禁了还想抢红包？滚"
        else:
            msg += "\n   - 您的账号已被封禁，请联系管理员解封。"
        await openredpacket_function.finish(msg)

    # open redpacket data
    redpacket_data_path = DATA_PATH / "redpackets.json"

    if os.path.exists(redpacket_data_path):
        try:
            with open(redpacket_data_path, "r", encoding="utf-8") as f:
                redpackets = json.load(f)
        except json.JSONDecodeError:
            print(f"Warning: {redpacket_data_path} is corrupted. Starting with an empty redpacket list.")
            redpackets = []
    else:
        redpackets = []

    if len(redpackets) == 0:
        msg += "\n   - 当前没有可抢的红包。"
        await openredpacket_function.finish(msg)

    # 随机选择一个红包
    selected_index = random.randint(0, len(redpackets) - 1)
    selected_redpacket = redpackets[selected_index]

    if user.id in selected_redpacket["TakedUser"]:
        if user.playMode():
            msg += "\n   - 你他妈已经抢过这个红包了，再抢就变成██。"
        else:
            msg += "\n   - 您已经抢过这个红包了，不能重复抢。"
        await openredpacket_function.finish(msg)

    # 给用户加钱
    user.addScore(float(selected_redpacket["Money"]))
    user.save()

    msg += f"\n   - 抢到一个 {selected_redpacket['Money']:.2f} 积分的红包！"
    msg += f"\n   - 目前您的积分为 {user.getScore():.2f}。"

    # 更新红包数据
    selected_redpacket["Number"] -= 1
    selected_redpacket["TakedUser"].append(user.id)
    if selected_redpacket["Number"] <= 0:
        # 如果红包数量为0，移除该红包
        del redpackets[selected_index]
    else:
        # 否则更新红包信息
        redpackets[selected_index] = selected_redpacket


    # 写入
    with open(DATA_PATH / "redpackets.json", "w", encoding="utf-8") as f:
        f.write(json.dumps(redpackets, ensure_ascii=False, indent=4))

    await openredpacket_function.finish(msg)

# esu 功能
fuck_eventer = on_command("fuck")

@fuck_eventer.handle()
async def _ (bot: v11bot, event: GroupMessageEvent | PrivateMessageEvent, args: Message = CommandArg()):
    # use api
    try:
        await bot.call_api("send_private_msg", user_id=event.user_id, message="You ****ed " + args.extract_plain_text())
    except ActionFailed:
        await fuck_eventer.finish("彩蛋无法触发。若该群禁止了私聊请先加 Bot 好友。")
    else:
        await fuck_eventer.finish("彩蛋触发。请查看私聊。")

"""
modifyname 函数

修改用户昵称
@author: BL-BlueLighting
"""

modifyname_function = on_command("modifyname", priority=10)

@modifyname_function.handle()
async def _ (bot: v11bot, event: GroupMessageEvent | PrivateMessageEvent, args: Message = CommandArg()):
    msg = TITLE + " Modify Name"
    user = User(event.get_user_id())
    _msg = args.extract_plain_text()

    user.name = _msg

    msg += "\n    - 名称修改完毕。你现在的新名称为：" + user.name + "。"


    user.save()
    await modifyname_function.finish(msg)

"""
bag 函数

查看目前包里都有啥
@author: BL-BlueLighting
"""

bag_function = on_command("bag", aliases=set(), priority=10)

@bag_function.handle()
async def _(bot: v11bot, event: GroupMessageEvent | PrivateMessageEvent, args: Message = CommandArg()):
    user = User(event.get_user_id())

    msg = "\nTLoH Bot 背包"
    msg += "\n    - 目前你包里有："

    items = user.boughtItems
    if not items:
        msg += "\n    - 你包里是空的。"
    else:
        # 用 Counter 统计每个物品数量
        count = Counter(items)
        for item, num in count.items():
            msg += f"\n    - {item}" + (f" x{num}" if num > 1 else "")

    await bag_function.finish(msg)

"""
browsingbottle 函数
漂流瓶

@author: BL-BlueLighting
"""

browsingbottle_function = on_command("browsingbottle", priority=10)

@browsingbottle_function.handle()
async def _ (bot: v11bot, event: GroupMessageEvent | PrivateMessageEvent, args: Message = CommandArg()):
    msg = TITLE + " 漂流瓶 BROWSING BOTTLE"
    user = User(event.get_user_id())
    _msg = args.extract_plain_text()
    _content = []
    _arg = _msg.split(" ")[0]
    if len(msg.split(" ")) != 1:
        _content = _msg.split(" ")[1:]

    bottle_data_path = DATA_PATH / "bottles.json"
    if _arg == "throw":
        if len(_content) == 0:
            msg += "\n    - 使用 ^browsingbottle throw [内容] 来扔漂流瓶"
            await browsingbottle_function.finish(msg)

        content = " ".join(_content)

        # open data


        if os.path.exists(bottle_data_path):
            try:
                with open(bottle_data_path, "r", encoding="utf-8") as f:
                    bottles = json.load(f)
            except json.JSONDecodeError:
                print(f"Warning: {bottle_data_path} is corrupted. Starting with an empty bottle list.")
                bottles = []
        else:
            bottles = []

        bottle = {
            "UserID": user.id,
            "Content": content
        }

        bottles.append(bottle)

        with open(bottle_data_path, "w", encoding="utf-8") as f:
            json.dump(bottles, f, ensure_ascii=False, indent=4)

        msg += "\n    - 你扔下了一个漂流瓶。"
        await browsingbottle_function.finish(msg)
    elif _arg == "pick":
        if os.path.exists(bottle_data_path):
            try:
                with open(bottle_data_path, "r", encoding="utf-8") as f:
                    bottles = json.load(f)
            except json.JSONDecodeError:
                print(f"Warning: {bottle_data_path} is corrupted. Starting with an empty bottle list.")
                bottles = []
        else:
            bottles = []

        if len(bottles) == 0:
            msg += "\n    - 目前没有漂流瓶。"
            await browsingbottle_function.finish(msg)

        selected_index = random.randint(0, len(bottles) - 1)
        selected_bottle = bottles[selected_index]

        msg += f"\n    - 你捡到了一个漂流瓶，内容是：\n    {selected_bottle['Content']}"

        # remove
        del bottles[selected_index]

        with open(bottle_data_path, "w", encoding="utf-8") as f:
            json.dump(bottles, f, ensure_ascii=False, indent=4)

        await browsingbottle_function.finish(msg)
    else:
        msg += "\n    - 使用 ^browsingbottle throw [内容] 来扔漂流瓶"
        msg += "\n    - 使用 ^browsingbottle pick 来捡漂流瓶"
        await browsingbottle_function.finish(msg)

"""
Voting 函数

创建投票
@author: BL-BlueLighting
"""

voting_function = on_command("voting", priority=10)

@voting_function.handle()
async def _voting_function (bot: v11bot, event: GroupMessageEvent, args: Message = CommandArg()): # 备注: 你都投票了还用什么私聊啊
    msg = "TLoH Bot VOTING MODULE."
    user = User(event.get_user_id())
    _msg = args.extract_plain_text()

    # get args
    _arg = _msg.split(" ")

    vote_path = DATA_PATH / "voting.json"

    # get vote data
    if os.path.exists(vote_path):
        with open(vote_path, "r", encoding="utf-8") as f:
            vote_data = json.load(f)
    else:
        vote_data = []

    # cases
    act = _arg[0]
    other = _arg[1:]

    if act == "create":
        # create vote, ^voting create [title] [type: kick, normal] [duration: minutes]
        if len(other) < 3:
            msg += "\n    - 使用 ^voting create [title] [type: kick, normal] [duration: minutes] 来创建投票。"
            await voting_function.finish(msg)

        title = other[0]
        vtype = other[1]
        duration = other[2]

        if vtype not in ["kick", "normal"]:
            msg += "\n    - 投票类型只能是 kick 或 normal。"
            await voting_function.finish(msg)

        # check superuser, only superuser can create kick vote
        if vtype == "kick" and event.get_user_id() not in nonebot.get_driver().config.superusers:
            msg += "\n    - 只有超级用户可以创建踢人投票。"
            await voting_function.finish(msg)

        if not duration.isdigit():
            msg += "\n    - 投票时间必须是数字，单位为分钟。"
            await voting_function.finish(msg)

        duration = int(duration)

        if duration >= 24 * 60 * 365:
            msg += "\n    - 投票时间不能超过/等于 1 年。"
            await voting_function.finish(msg)

        # make cfg
        _cfg = {
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

        vote_data.append(_cfg)

        with open(vote_path, "w", encoding="utf-8") as f:
            json.dump(vote_data, f, ensure_ascii=False, indent=4)
        # write in
        msg += f"\n    - 已创建投票 {title}，类型 {vtype}，时长 {duration} 分钟。"
        await voting_function.finish(msg)

    elif act == "list":
        # list votes
        if len(vote_data) == 0:
            msg += "\n    - 目前没有任何投票。"
            await voting_function.finish(msg)

        msg += "\n    - 目前的投票有："
        for vote in vote_data:
            msg += f"\n        - {vote['name']} (状态: {vote['status']}, 类型: {vote['type']}, 发起人: {vote['creator']})"

        await voting_function.finish(msg)

    elif act == "status":
        # status of vote, ^voting status [title]
        if len(other) < 1:
            msg += "\n    - 使用 ^voting status [title] 来查看投票状态。"
            await voting_function.finish(msg)

        title = other[0]

        # find vote
        vote = None
        for v in vote_data:
            if v["name"] == title:
                vote = v
                break

        if vote == None:
            msg += f"\n    - 未找到投票 {title}"
            await voting_function.finish(msg)

        # show status
        msg += f"\n    - 投票 {title} 的状态："
        msg += f"\n        - 状态: {vote['status']}。"
        msg += f"\n        - 类型: {vote['type']}。"
        msg += f"\n        - 发起人: {vote['creator']}。"
        msg += f"\n        - 赞成: {vote['agree']} 票。"
        msg += f"\n        - 反对: {vote['objection']} 票。"
        msg += f"\n        - 弃权: {vote['abstain']} 票。"
        msg += f"\n        - 时长: {vote['duration']} 分钟。"
        msg += f"\n        - 已投票人数: {len(vote['voters'])} 人。"

        await voting_function.finish(msg)

    elif act == "help":
        msg += """
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
        await voting_function.finish(msg)

    elif act == "vote":
        # vote, ^voting vote [title] [agree, objection, abstain]
        if len(other) < 2:
            msg += "\n    - 使用 ^voting vote [title] [agree, objection, abstain] 来投票。"
            await voting_function.finish(msg)

        title = other[0]
        choice = other[1]

        if choice not in ["agree", "objection", "abstain"]:
            msg += "\n    - 投票选项只能是 agree, objection, abstain。"
            await voting_function.finish(msg)

        # find vote
        vote = None
        for v in vote_data:
            if v["name"] == title:
                vote = v
                break

        if vote == None:
            msg += f"\n    - 未找到投票 {title}。"
            await voting_function.finish(msg)

        if vote["status"] != "进行中":
            msg += f"\n    - 投票 {title} 已结束，无法投票。"
            await voting_function.finish(msg)
        else:
            # check duration:
            if (datetime.datetime.now() - datetime.datetime.fromisoformat(vote["begintime"])).total_seconds() > vote["duration"] * 60:
                vote["status"] = "已结束"
                with open(vote_path, "w", encoding="utf-8") as f:
                    json.dump(vote_data, f, ensure_ascii=False, indent=4)
                if vote["type"] == "kick":
                    if vote["agree"] > vote["objection"]:
                        # kick the creator
                        target_user = User(vote["creator"])
                        target_user.banned = True
                        target_user.save()
                        # check admin
                        admin_list = await bot.call_api("get_group_member_info", group_id=event.group_id, user_id=bot.self_id)
                        if admin_list ["role"] == "member":
                            msg += f"\n    - 投票 {title} 已结束，结果为赞成票多于反对票，已自动封禁发起人 {vote['creator']}。"
                        else:
                            # direct call kick
                            await bot.call_api("set_group_kick", group_id=event.group_id, user_id=vote["creator"])
                    else:
                        msg += f"\n    - 投票 {title} 已结束，结果为反对票多于或等于赞成票，未封禁发起人 {vote['creator']}。"
                msg += f"\n    - 投票 {title} 已结束，无法投票。"
                await voting_function.finish(msg)

        if user.id in vote["voters"]:
            msg += f"\n    - 你已在投票 {title} 中投过票，无法重复投票。"
            await voting_function.finish(msg)

        # cast vote
        if choice == "agree":
            vote["agree"] += 1
        elif choice == "objection":
            vote["objection"] += 1
        elif choice == "abstain":
            vote["abstain"] += 1

        vote["voters"].append({user.id: choice})

        with open(vote_path, "w", encoding="utf-8") as f:
            json.dump(vote_data, f, ensure_ascii=False, indent=4)

        msg += f"\n    - 你已在投票 {title} 中投下 {choice} 一票。"
        await voting_function.finish(msg)
    else:
        msg += "    - 使用 ^voting help 来查看帮助。"
        await voting_function.finish(msg)