import sqlite3

from nonebot import on_command
from nonebot.adapters import Message
from nonebot.adapters.onebot.v11 import (Bot, GroupMessageEvent,
                                         PrivateMessageEvent)
from nonebot.params import CommandArg

from plugins.userInfoController import User

"""
TLoH Bot
Tools Bot 的第二版。

@author: BL-BlueLighting

undefiendControllers.sayNormaly
"""

TITLE = "TLoH Bot"

"""
saynormal 函数

说人话
@author: BL-BlueLighting
"""

saynormal_function = on_command("saynormal", aliases={""}, priority=10)

@saynormal_function.handle()
async def _ (bot: Bot, event: GroupMessageEvent | PrivateMessageEvent, args: Message = CommandArg()):
    msg = TITLE + " 能不能好好说话??"
    user = User(event.get_user_id())
    _msg = args.extract_plain_text()

    cmd = _msg.split(" ") [0]
    content = "notfillnow114514"
    try:
        content = _msg.split(" ") [1:]
    except Exception:
        pass

    if cmd == "fetch" or cmd != "add":
        fet = ""
        if content == "notfillnow114514" and cmd != "":
            fet = cmd
        else:
            fet = content

        # fetch sqlite
        db = sqlite3.connect("userinfo.db")
        cursor = db.cursor()

        # if table not exists create it
        cursor.execute("CREATE TABLE IF NOT EXISTS saynormal (keyword TEXT, content TEXT, ban tinyint(1)); ")
        cursor.execute("SELECT * FROM saynormal WHERE keyword = ?", (fet, ))

        results = cursor.fetchall()
        if len(results) == 0:
            msg += f"\n    - 关键词：{fet}\n    - 啥也木有。\n    - 如果希望创建该词条，请使用 ^saynormal add {fet} [content]。"
            await saynormal_function.finish(msg)

        msg += f"\n    - 关键词：{fet}\n    - 共有 {len(results)} 条数据。"
        for result in results:
            if result[2] == 0:
                msg += f"\n   - 内容：{result[1]}"
        msg += f"\n    - 如果希望添加数据，请使用 ^saynormal add {fet} [content]。"

        await saynormal_function.finish(msg)

    elif cmd == "add":
        if content == "notfillnow114514":
            msg += "\n    - 请输入内容。"
            await saynormal_function.finish(msg)

        # fetch sqlite
        db = sqlite3.connect("userinfo.db")
        cursor = db.cursor()

        # if table not exists create it
        cursor.execute("CREATE TABLE IF NOT EXISTS saynormal (keyword TEXT, content TEXT, ban tinyint(1)); ")
        cursor.execute("SELECT * FROM saynormal WHERE keyword = ?", (content.split(" ") [0], )) # type: ignore
        if len(cursor.fetchall()) != 0:
            cursor.execute("INSERT INTO saynormal (keyword, content, ban) VALUES (?, ?, ?)", (content.split(" ") [0], content.split(" ") [1:], 0)) # type: ignore
            msg += "\n    - 添加成功。"
            await saynormal_function.finish(msg)
        msg += "\n    - 关键词不存在。"
        await saynormal_function.finish(msg)

    else:
        msg += "\n    - 未知命令。"
        await saynormal_function.finish(msg)


