import datetime
import json
import os
import random
import re
import base64
from collections import Counter
from typing import Any, Dict

import nonebot
import requests
import toml
import difflib
import sqlite3 as sql
from nonebot import on_command, on_message
from nonebot.adapters import Message
from nonebot.adapters.onebot.v11 import (Bot, GroupMessageEvent,
                                         PrivateMessageEvent)
from nonebot.adapters.onebot.v11.message import MessageSegment
from nonebot.exception import ActionFailed
from nonebot.params import CommandArg
from nonebot.permission import SUPERUSER

from toolsbot.configs import DATA_PATH
from toolsbot.services import _error, _info
from plugins.userInfoController import User, At

"""
TLoH Bot
Tools Bot 的第二版。

@author: BL-BlueLighting

undefiendControllers.wordle MODULE.
Wordle 词汇
"""

CREATE_TABLE_SQL = """CREATE TABLE IF NOT EXISTS Wordle (
    ID TEXT PRIMARY KEY,
    CreateUser TEXT,
    CreateTime TEXT,
    Word TEXT,
    Tips TEXT,
    Vote INTEGER DEFAULT 0
)"""

INSERT_TABLE_SQL = """INSERT INTO Wordle (ID, CreateUser, CreateTime, Word, Tips) VALUES (?, ?, ?, ?, ?)"""

VOTE_DELETE_DEADLINE = -5

def compare_words(target, guess) -> tuple[int, float, int, int]:
    """
    比较词语

    (
        0 / -1: 比较成功 / 长度不相同，校验失败
        NN.N%: 相似度
        N: 相同字符数量
        N: 不同字符数量
    """


    if len(target) != len(guess):
        return (-1, 0, 0, 0)

    similarity = difflib.SequenceMatcher(None, target, guess).ratio()
    similarity_percent = similarity * 100

    same_count = 0
    diff_count = 0
    
    for t_char, g_char in zip(target, guess):
        if t_char == g_char:
            same_count += 1
        else:
            diff_count += 1

    return (0, similarity_percent, same_count, diff_count)


wordle_eventer = on_command("wordle", aliases={"customwordle"})

@wordle_eventer.handle()
async def wordle_handler(bot: Bot, event: GroupMessageEvent | PrivateMessageEvent, args: Message = CommandArg()):
    """
    Wordle 词汇
    """
    msg = "TLoH Bot Wordle\n"

    # get userdb
    conn = sql.connect(os.path.join(DATA_PATH, "./userdata.db"))
    c = conn.cursor()

    # create table if it not exists
    """
    Table:

    Wordle
    ID: String, Random generating, use random number to base64 then generate.
    CreateUser: String, Platform ID
    CreateTime: Datetime, Word create time.
    Word: String, Wordle word.
    Tips: String, Tips.
    Vote: Integer, Wordle word vote, good or bad. When vote under -5, word will be deleted.
    """

    # check if user has been banned
    if User(event.get_user_id()).isBanned():
        await wordle_eventer.finish("TLoH Bot Wordle\n    - 你已被封禁，无法使用此功能。")

    c.execute(CREATE_TABLE_SQL)
    conn.commit()

    _get = args.extract_plain_text().split(" ")

    if len(_get) > 0:
        main_cmd = _get [0]
    else:
        main_cmd = "help"
    
    if len(_get) > 1:
        params = _get [1:]
    else:
        params = []

    if main_cmd == "help":
        msg += "    - 使用方法：\n"
        msg += "        - wordle add [word] [tips]: 添加一个 Wordle 词汇。\n"
        msg += "        - wordle play [word_id]: 玩一个 Wordle 词汇。\n"
        msg += "        - wordle del [word_id]: (SUPERUSER ONLY) 删除一个 Wordle 词汇。\n"
        await wordle_eventer.finish(msg)
    
    elif main_cmd == "add":
        if len(params) < 2:
            msg += "    - 参数不足。\n    - 使用 wordle help 查看使用方法。"
            await wordle_eventer.finish(msg)
        
        word = params [0]
        tips = " ".join(params [1:])

        # generate id
        _id_number = str(random.randint(100000, 999999)) + str(random.randint(1, 9))
        _id = base64.b64encode(_id_number.encode()).decode()

        # insert into database
        c.execute(INSERT_TABLE_SQL, (_id, event.get_user_id(), datetime.datetime.now(), word, tips))
        conn.commit()

        await wordle_eventer.finish(f"TLoH Bot Wordle\n    - 您的 Wordle 词汇已被添加。\n    - ID: {_id}。")
    
    elif main_cmd == "play":
        if len(params) < 1:
            msg += "    - 参数不足。\n    - 使用 wordle help 查看使用方法。"
            await wordle_eventer.finish(msg)

        _id = params [0]

        # check if word exists
        _c = c.execute("SELECT * FROM Wordle WHERE ID = ?", (_id,))  
        data = _c.fetchone()

        if data is None:
            msg += "    - 该 Wordle 词汇不存在。"
            await wordle_eventer.finish(msg)
        
        # check word vote
        if data [5] < VOTE_DELETE_DEADLINE:
            msg += f"    - 该 Wordle 词汇因低于最低票数 ({VOTE_DELETE_DEADLINE}) 已被删除。"
            await wordle_eventer.finish(msg)

        msg += f"    - Wordle 词汇 ID: {data [0]}\n"
        msg += f"    - Wordle 词汇提示: {data [4]}\n"

        create_user_id = data [1]
        create_user_data = await bot.get_stranger_info(user_id=create_user_id)
        user_nick = create_user_data["nick"]

        msg += f"    - Wordle 词汇创建者: {user_nick}\n"
        msg += f"    - 评分：{data [5]}\n"
        msg += f"    - 使用 ^wordle guess {data [0]} [word] 来猜词。"

        await wordle_eventer.finish(msg)
    
    elif main_cmd == "del":
        if not SUPERUSER(bot, event):
            await wordle_eventer.finish("TLoH Bot Wordle\n    - 您没有权限使用此功能。")

        if len(params) < 1: 
            msg += "    - 参数不足。\n    - 使用 wordle help 查看使用方法。"
            await wordle_eventer.finish(msg)

        _id = params [0]

        # check if word exists
        _c = c.execute("SELECT * FROM Wordle WHERE ID = ?", (_id,))

        data = _c.fetchone()

        if data is None:
            msg += "    - 该 Wordle 词汇不存在。"
            await wordle_eventer.finish(msg)

        # delete word
        c.execute("DELETE FROM Wordle WHERE ID = ?", (_id,))
        conn.commit()

        await wordle_eventer.finish("TLoH Bot Wordle\n    - 您已删除该 Wordle 词汇。")

    elif main_cmd == "guess":
        if len(params) < 2:
            msg += "    - 参数不足。\n    - 使用 wordle help 查看使用方法。"
            await wordle_eventer.finish(msg)

        _id = params [0]
        word = params [1]

        # check if word exists
        _c = c.execute("SELECT * FROM Wordle WHERE ID = ?", (_id,))
        data = _c.fetchone()

        if data is None:
            msg += "    - 该 Wordle 词汇不存在。"
            await wordle_eventer.finish(msg)

        # 比较两词相似度
        cw = compare_words(data [3], word)

        # check if word is correct
        if cw [2] == len(data [3]):
            msg += "    - 您猜对了！"
            msg += "\n    - 词汇：" + data [3]
            msg += "\n    - 为该词语评分："
            msg += "\n    - 使用 ^wordle vote [word_id] [vote(up/down/1/-1)] 来评分。"
            await wordle_eventer.finish(msg)

        # uncorrect
        msg += "    - 还不对。\n"
        msg += "    - 相似度：" + str(cw [1]) + "%\n"
        msg += "    - 相同字母个数：" + str(cw [2])
        msg += "\n    - 不同字母个数：" + str(cw [0])
        msg += "\n    - 提示：" + data [4]

        await wordle_eventer.finish(msg)
    
    #vote
    elif main_cmd == "vote":
        if len(params) < 2:
            msg += "    - 参数不足。\n    - 使用 wordle help 查看使用方法。"
            await wordle_eventer.finish(msg)

        _id = params [0]
        vote = params [1]

        # check if word exists
        _c = c.execute("SELECT * FROM Wordle WHERE ID = ?", (_id,))
        data = _c.fetchone()

        if data is None:
            msg += "    - 该 Wordle 词汇不存在。"
            await wordle_eventer.finish(msg)
        
        # check vote param
        voteparam = ["up", "down", "1", "-1"]

        if vote not in voteparam:
            msg += "    - 投票参数错误。\n    - 使用 wordle help 查看使用方法。"
            await wordle_eventer.finish(msg)
        
        # vote
        if vote == "up" or vote == "1":
            c.execute("UPDATE Wordle SET Vote = Vote + 1 WHERE ID = ?", (_id,))
        elif vote == "down" or vote == "-1":
            c.execute("UPDATE Wordle SET Vote = Vote - 1 WHERE ID = ?", (_id,))

        conn.commit()

        await wordle_eventer.finish("TLoH Bot Wordle\n    - 您已投票。")
    else:
        await wordle_eventer.finish("TLoH Bot Wordle\n    - 命令不存在。\n    - 使用 wordle help 查看使用方法。")