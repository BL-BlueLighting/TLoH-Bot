import configparser

from nonebot import on_command
from nonebot.adapters import Message
from nonebot.adapters.onebot.v11 import (Bot, GroupMessageEvent,
                                         PrivateMessageEvent)
from nonebot.params import CommandArg

import plugins.userInfoController as dc  # old name = dauCtl
from toolsbot.configs import USER_PATH
from toolsbot.services import _info

from . import runner

template_path = USER_PATH / "finaleScope" / "template.finaleScope_data"

User = dc.User


# logging settings

"""
TLoH Bot
Tools Bot 的第二版。

@author: BL-BlueLighting

finaleScopeController

Finale Scope 的相关功能控制器。
"""

TITLE = "TLoH Bot"

"""
scopes 函数

查询目前的 Finale Scope 信息。
@author: BL-BlueLighting
"""

query_function = on_command("finaleScope", priority=10)

@query_function.handle()
async def _ (bot: Bot, event: GroupMessageEvent | PrivateMessageEvent, args: Message = CommandArg()):
    msg = TITLE + " FiNALE SCOPE 信息查询。\n"
    user = User(event.get_user_id())
    _msg = args.extract_plain_text()

    user_file_path = USER_PATH / "finaleScope" / f"{user.id}.finalescope_data"

    # query data

    scope = runner.run("doors.finalescope_data")

    if scope == None:
        msg += "    - FiNALE SCOPE 没有 Doors 的数据文件。\n    - 请询问 Bot 主，向 2733392694 索取文件。"
        await query_function.finish(msg)

    msg += "    - 目前 FiNALE SCOPE 有 " + str(len(scope.doors)) + " 个门。\n"

    # get unlocked doors
    try:
        with open(user_file_path, "r", encoding="utf-8") as f:
            f.read() # this is a ini
    except FileNotFoundError:
        # create new file from template
        with open(template_path, "r", encoding="utf-8") as f:
            template = f.read()
        with open(user_file_path, "w", encoding="utf-8") as f:
            f.write(template)
            _info("Create new finaleScope data file for user " + user.id)

    config = configparser.ConfigParser()
    config.read(user_file_path,
                encoding="utf-8")

    if config.get("Scope", "DoorsUnlock") != "":
        unlockedDoors = config.get("Scope", "DoorsUnlock").split(", ")
    else:
        unlockedDoors = []

    if len(unlockedDoors) == 0:
        msg += "    - 你目前还没有解锁任何门。\n"
    else:
        if unlockedDoors [0] == '""' and len(unlockedDoors) == 1:
            unlockedDoors = []
            msg += "    - 你目前还没有解锁任何门。\n"
        else:
            if unlockedDoors [0].startswith('"') and unlockedDoors [0].endswith('"'):
                del unlockedDoors[0]
            msg += "    - 你目前解锁了 " + str(len(unlockedDoors)) + " 个门，分别是：\n"
            for doorName in unlockedDoors:
                msg += "        - " + doorName + "\n"

    await query_function.finish(msg) # 不给看其他的

"""
unlockNext 函数


@author: BL-BlueLighting
"""

unlock_next_function = on_command("finaleScopeNext", priority=10)

@unlock_next_function.handle()
async def _ (bot: Bot, event: GroupMessageEvent | PrivateMessageEvent, args: Message = CommandArg()):
    msg = TITLE + " FiNALE SCOPE UNLOCK NEXT\n"
    user = User(event.get_user_id())
    _msg = args.extract_plain_text()

    user_file_path = USER_PATH / "finaleScope" / f"{user.id}.finalescope_data"

    # query data
    scope = runner.run("doors.finalescope_data")
    if scope == None:
        msg += "    - FiNALE SCOPE 没有 Doors 的数据文件。\n    - 请询问 Bot 主，向 2733392694 索取文件。"
        await unlock_next_function.finish(msg)

    # get unlocked doors
    try:
        with open(user_file_path, "r", encoding="utf-8") as f:
            f.read() # this is a ini
    except FileNotFoundError:
        # create new file from template
        with open(template_path, "r", encoding="utf-8") as f:
            template = f.read()
        with open(user_file_path, "w", encoding="utf-8") as f:
            f.write(template)
            _info("Create new finaleScope data file for user " + user.id)

    config = configparser.ConfigParser()
    config.read(user_file_path,
                encoding="utf-8")

    if config.get("Scope", "DoorsUnlock") != "":
        unlockedDoors = config.get("Scope", "DoorsUnlock").split(", ")
    else:
        unlockedDoors = []

    # check next door
    nextDoor = None
    for door in scope.doors:
        if not door.name in unlockedDoors:
            nextDoor = door
            break

    if nextDoor == None:
        msg += "    - 目前还没有更多的门出现。请等待后面新门加入。\n"
        await unlock_next_function.finish(msg)

    if nextDoor.condition(user):
        # unlock
        if config.get("Scope", "DoorsUnlock") == "":
            config.set("Scope", "DoorsUnlock", nextDoor.name)
        else:
            config.set("Scope", "DoorsUnlock", config.get("Scope", "DoorsUnlock") + ", " + nextDoor.name)

        with open(user_file_path, "w", encoding="utf-8") as configfile:
            config.write(configfile)

        msg += "    - 你解锁了 " + nextDoor.name + " 门。\n"
        msg += "    - 你获得了 " + str(nextDoor.reward) + " 点数。\n"

        user.addScore(nextDoor.reward)
        user.save()
        await unlock_next_function.finish(msg)
    else:
        msg += "    - 下一个门你还未满足打开条件。\n"
        msg += "    - 请自己探索或询问 Bot 主条件。\n"

        await unlock_next_function.finish(msg)
