import datetime
import json
import os
import random
import re
import base64
from collections import Counter
from typing import Any, Dict, Optional, Tuple

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

INSERT_TABLE_SQL = """INSERT INTO Wordle (ID, CreateUser, CreateTime, Word, Tips)
VALUES (?, ?, ?, ?, ?)"""

VOTE_DELETE_DEADLINE = -5


def compare_words(target: str, guess: str) -> Tuple[int, float, int, int]:
    """Compare two words and return similarity metrics.

    Returns:
        Tuple of (status, similarity_percent, same_count, diff_count)
        status: 0 for success, -1 for length mismatch
    """
    if len(target) != len(guess):
        return (-1, 0.0, 0, 0)

    similarity = difflib.SequenceMatcher(None, target, guess).ratio()
    similarity_percent = similarity * 100

    same_count = sum(1 for t, g in zip(target, guess) if t == g)
    diff_count = len(target) - same_count

    return (0, similarity_percent, same_count, diff_count)


def _get_db_connection():
    """Get a database connection with error handling."""
    try:
        db_path = os.path.join(DATA_PATH, "userdata.db")
        conn = sql.connect(db_path)
        return conn
    except sql.Error as e:
        _error(f"Failed to connect to database: {e}")
        raise


# =============================================================================
# Sub-handlers for wordle commands
# =============================================================================

async def _wordle_help(handler) -> None:
    """Show wordle help."""
    msg = "TLoH Bot Wordle\n"
    msg += "    - 使用方法：\n"
    msg += "        - wordle add [word] [tips]: 添加一个 Wordle 词汇。\n"
    msg += "        - wordle play [word_id]: 玩一个 Wordle 词汇。\n"
    msg += "        - wordle del [word_id]: (SUPERUSER ONLY) 删除一个 Wordle 词汇。\n"
    await handler.finish(msg)


async def _wordle_add(params: list, event, conn, handler) -> None:
    """Add a new wordle word."""
    if len(params) < 2:
        await handler.finish("TLoH Bot Wordle\n    - 参数不足。\n    - 使用 wordle help 查看使用方法。")

    word = params[0]
    tips = " ".join(params[1:])

    _id_number = str(random.randint(100000, 999999)) + str(random.randint(1, 9))
    _id = base64.b64encode(_id_number.encode()).decode()

    try:
        c = conn.cursor()
        c.execute(INSERT_TABLE_SQL, (_id, event.get_user_id(), datetime.datetime.now(), word, tips))
        conn.commit()
    except sql.Error as e:
        _error(f"Failed to insert wordle: {e}")
        await handler.finish("TLoH Bot Wordle\n    - 添加失败，数据库错误。")

    await handler.finish(f"TLoH Bot Wordle\n    - 您的 Wordle 词汇已被添加。\n    - ID: {_id}。")


async def _wordle_play(params: list, bot: Bot, conn, handler) -> None:
    """Play a wordle game."""
    if len(params) < 1:
        await handler.finish("TLoH Bot Wordle\n    - 参数不足。\n    - 使用 wordle help 查看使用方法。")

    _id = params[0]

    try:
        c = conn.cursor()
        data = c.execute("SELECT * FROM Wordle WHERE ID = ?", (_id,)).fetchone()
    except sql.Error as e:
        _error(f"Failed to query wordle: {e}")
        await handler.finish("TLoH Bot Wordle\n    - 查询失败，数据库错误。")

    if data is None:
        await handler.finish("TLoH Bot Wordle\n    - 该 Wordle 词汇不存在。")

    if data[5] < VOTE_DELETE_DEADLINE:
        await handler.finish(
            f"TLoH Bot Wordle\n    - 该 Wordle 词汇因低于最低票数 ({VOTE_DELETE_DEADLINE}) 已被删除。"
        )

    msg = f"TLoH Bot Wordle\n"
    msg += f"    - Wordle 词汇 ID: {data[0]}\n"
    msg += f"    - Wordle 词汇提示: {data[4]}\n"

    try:
        create_user_data = await bot.get_stranger_info(user_id=data[1])
        user_nick = create_user_data.get("nick", "未知")
    except Exception as e:
        _error(f"Failed to get user info for wordle: {e}")
        user_nick = "未知"

    msg += f"    - Wordle 词汇创建者: {user_nick}\n"
    msg += f"    - 评分：{data[5]}\n"
    msg += f"    - 使用 ^wordle guess {data[0]} [word] 来猜词。"

    await handler.finish(msg)


async def _wordle_del(params: list, bot: Bot, event, conn, handler) -> None:
    """Delete a wordle word (superuser only)."""
    if not SUPERUSER(bot, event):
        await handler.finish("TLoH Bot Wordle\n    - 您没有权限使用此功能。")

    if len(params) < 1:
        await handler.finish("TLoH Bot Wordle\n    - 参数不足。\n    - 使用 wordle help 查看使用方法。")

    _id = params[0]

    try:
        c = conn.cursor()
        data = c.execute("SELECT * FROM Wordle WHERE ID = ?", (_id,)).fetchone()
    except sql.Error as e:
        _error(f"Failed to query wordle for deletion: {e}")
        await handler.finish("TLoH Bot Wordle\n    - 查询失败，数据库错误。")

    if data is None:
        await handler.finish("TLoH Bot Wordle\n    - 该 Wordle 词汇不存在。")

    try:
        c.execute("DELETE FROM Wordle WHERE ID = ?", (_id,))
        conn.commit()
    except sql.Error as e:
        _error(f"Failed to delete wordle: {e}")
        await handler.finish("TLoH Bot Wordle\n    - 删除失败，数据库错误。")

    await handler.finish("TLoH Bot Wordle\n    - 您已删除该 Wordle 词汇。")


async def _wordle_guess(params: list, conn, handler) -> None:
    """Guess a wordle word."""
    if len(params) < 2:
        await handler.finish("TLoH Bot Wordle\n    - 参数不足。\n    - 使用 wordle help 查看使用方法。")

    _id = params[0]
    word = params[1]

    try:
        c = conn.cursor()
        data = c.execute("SELECT * FROM Wordle WHERE ID = ?", (_id,)).fetchone()
    except sql.Error as e:
        _error(f"Failed to query wordle for guess: {e}")
        await handler.finish("TLoH Bot Wordle\n    - 查询失败，数据库错误。")

    if data is None:
        await handler.finish("TLoH Bot Wordle\n    - 该 Wordle 词汇不存在。")

    status, sim_percent, same_count, diff_count = compare_words(data[3], word)

    if same_count == len(data[3]):
        msg = "TLoH Bot Wordle\n"
        msg += "    - 您猜对了！"
        msg += "\n    - 词汇：" + data[3]
        msg += "\n    - 为该词语评分："
        msg += "\n    - 使用 ^wordle vote [word_id] [vote(up/down/1/-1)] 来评分。"
        await handler.finish(msg)

    msg = "TLoH Bot Wordle\n"
    msg += "    - 还不对。\n"
    msg += f"    - 相似度：{sim_percent:.1f}%\n"
    msg += f"    - 相同字母个数：{same_count}\n"
    msg += f"    - 不同字母个数：{diff_count}\n"
    msg += f"    - 提示：{data[4]}"

    await handler.finish(msg)


async def _wordle_vote(params: list, conn, handler) -> None:
    """Vote on a wordle word."""
    if len(params) < 2:
        await handler.finish("TLoH Bot Wordle\n    - 参数不足。\n    - 使用 wordle help 查看使用方法。")

    _id = params[0]
    vote = params[1]

    try:
        c = conn.cursor()
        data = c.execute("SELECT * FROM Wordle WHERE ID = ?", (_id,)).fetchone()
    except sql.Error as e:
        _error(f"Failed to query wordle for voting: {e}")
        await handler.finish("TLoH Bot Wordle\n    - 查询失败，数据库错误。")

    if data is None:
        await handler.finish("TLoH Bot Wordle\n    - 该 Wordle 词汇不存在。")

    valid_votes = ["up", "down", "1", "-1"]
    if vote not in valid_votes:
        await handler.finish("TLoH Bot Wordle\n    - 投票参数错误。\n    - 使用 wordle help 查看使用方法。")

    try:
        if vote in ("up", "1"):
            c.execute("UPDATE Wordle SET Vote = Vote + 1 WHERE ID = ?", (_id,))
        elif vote in ("down", "-1"):
            c.execute("UPDATE Wordle SET Vote = Vote - 1 WHERE ID = ?", (_id,))
        conn.commit()
    except sql.Error as e:
        _error(f"Failed to update wordle vote: {e}")
        await handler.finish("TLoH Bot Wordle\n    - 投票失败，数据库错误。")

    await handler.finish("TLoH Bot Wordle\n    - 您已投票。")


# =============================================================================
# Main wordle command handler
# =============================================================================

wordle_eventer = on_command("wordle", aliases={"customwordle"})


@wordle_eventer.handle()
async def wordle_handler(bot: Bot, event: GroupMessageEvent | PrivateMessageEvent,
                          args: Message = CommandArg()):
    """Wordle 词汇游戏主处理器"""
    if User(event.get_user_id()).isBanned():
        await wordle_eventer.finish("TLoH Bot Wordle\n    - 你已被封禁，无法使用此功能。")

    try:
        conn = _get_db_connection()
        c = conn.cursor()
        c.execute(CREATE_TABLE_SQL)
        conn.commit()
    except sql.Error as e:
        _error(f"Failed to initialize wordle database: {e}")
        await wordle_eventer.finish("TLoH Bot Wordle\n    - 数据库初始化失败。")

    _get = args.extract_plain_text().split(" ")
    main_cmd = _get[0] if _get else "help"
    params = _get[1:] if len(_get) > 1 else []

    # Dispatch to sub-handlers
    sub_handlers = {
        "help": lambda: _wordle_help(wordle_eventer),
        "add": lambda: _wordle_add(params, event, conn, wordle_eventer),
        "play": lambda: _wordle_play(params, bot, conn, wordle_eventer),
        "del": lambda: _wordle_del(params, bot, event, conn, wordle_eventer),
        "guess": lambda: _wordle_guess(params, conn, wordle_eventer),
        "vote": lambda: _wordle_vote(params, conn, wordle_eventer),
    }

    if main_cmd in sub_handlers:
        await sub_handlers[main_cmd]()
    else:
        await wordle_eventer.finish(
            "TLoH Bot Wordle\n    - 命令不存在。\n    - 使用 wordle help 查看使用方法。"
        )
