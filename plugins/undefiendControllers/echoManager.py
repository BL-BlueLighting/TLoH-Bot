import json

from nonebot import on_command
from nonebot.adapters import Message
from nonebot.adapters.onebot.v11 import (Bot, GroupMessageEvent,
                                         PrivateMessageEvent)
from nonebot.params import CommandArg
from nonebot.permission import SUPERUSER

from plugins.userInfoController import User
from toolsbot.configs import DATA_PATH

"""
TLoH Bot
Tools Bot 的第二版。

@author: BL-BlueLighting

undefiendControllers.echoManager
"""

TITLE = "TLoH Bot"

"""
echotadd 函数

添加关键词和文本，仅限 SUPERUSER.
@author: BL-BlueLighting
"""

echo_path = DATA_PATH / "echoThings.json"

echot_add_function = on_command("echotadd", aliases={"echoThingAdd"}, priority=10, permission=SUPERUSER)

@echot_add_function.handle()
async def _ (bot: Bot, event: GroupMessageEvent | PrivateMessageEvent, args: Message = CommandArg()):
    msg = TITLE + " - echoThing Managing"
    user = User(event.get_user_id())
    _msg = args.extract_plain_text()

    keyword = _msg.split(" ")[0]
    content = _msg.split(" ")[1:]

    with open(echo_path, "r", encoding="utf-8") as f:
        keywords = json.load(f)

    if keyword in keywords.keys():
        await echot_add_function.finish(msg + "\n    - 关键词：" + keyword + "\n    - 该项目已存在。")
    else:
        keywords[keyword] = " ".join(content)
        with open(echo_path, "w", encoding="utf-8") as f:
            json.dump(keywords, f)
        await echot_add_function.finish(msg + "\n    - 关键词：" + keyword + "\n    - 内容：\n        " + " ".join(content))

"""
echotdel 函数

删除关键词和文本，仅限 SUPERUSER.
@author: BL-BlueLighting
"""
echot_del_function = on_command("echotdel", aliases={"echoThingAdd"}, priority=10, permission=SUPERUSER)

@echot_del_function.handle()
async def _ (bot: Bot, event: GroupMessageEvent | PrivateMessageEvent, args: Message = CommandArg()):
    msg = TITLE + " - echoThing Managing"
    user = User(event.get_user_id())
    _msg = args.extract_plain_text()

    keyword = _msg.split(" ")[0]

    with open(echo_path, "r", encoding="utf-8") as f:
        keywords = json.load(f)

    if not keyword in keywords.keys():
        await echot_del_function.finish(msg + "\n    - 关键词：" + keyword + "\n    - 该项目不存在。")
    else:
        del keywords [keyword]
        with open(echo_path, "w", encoding="utf-8") as f:
            json.dump(keywords, f)
        await echot_del_function.finish(msg + "\n    - 关键词：" + keyword + "\n    - 内容：\n        棍母")

"""
echot 函数

输出关键词指定的文本
@author: BL-BlueLighting
"""

echot_function = on_command("echot", aliases = {"echoThing"},priority=10)

@echot_function.handle()
async def _ (bot: Bot, event: GroupMessageEvent | PrivateMessageEvent, args: Message = CommandArg()):
    msg = TITLE + " - echoThing"
    user = User(event.get_user_id())
    _msg = args.extract_plain_text()

    # read echoT.json
    with open(echo_path, "r", encoding="utf-8") as f:
        keywords = json.load(f)

    if _msg in keywords.keys():
        await echot_function.finish(msg + "\n    - 关键词：" + _msg + "\n    - 内容：\n    " + keywords[_msg])
    else:
        await echot_function.finish("未找到关键词，请检查是否拼写正确。")