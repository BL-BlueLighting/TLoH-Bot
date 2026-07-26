import sqlite3

from nonebot import on_command
from nonebot.adapters import Message
from nonebot.adapters.onebot.v11 import (Bot, GroupMessageEvent,
                                         PrivateMessageEvent)
from nonebot.params import CommandArg

from plugins.userInfoController import User
from typing import Literal
import requests
from . import defines

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

API_LINK = "https://lab.magiconch.com/api/nbnhhsh"

"""
{
    "title": "能不能好好说话",
    "interfaces": [
        {
            "method": "post",
            "path": "/guess",
            "body": {
                "text": "String"
            },
            "response": [
                {
                    "name": "String",
                    "trans": [
                        "String"
                    ]
                },
                {
                    "name": "String",
                    "inputting": [
                        "String"
                    ]
                },
                {
                    "name": "String",
                    "trans": null
                }
            ]
        },
        {
            "method": "post",
            "path": "/translation/:name",
            "body": {
                "text": "String"
            },
            "response": null
        }
    ]
}
"""
async def _handle_request(
        api_select: Literal["guess", "submitTrans"], 
        text: str) -> dict[str, str | list[str]]:

    """请求 nbnhhsh api"""
    body = {
        "text": text
    }

    request_link = ""

    if api_select == "guess":
        request_link = API_LINK + "/guess"
    else:
        request_link = API_LINK + "/translation/" + text.split(",") [0]
        body ["text"] = text.split(",") [1]

    _response = requests.post(request_link, body) # request

    if _response.text == "": # translation api will return null, so add special if
        return {"err": "no"}

    response: dict = _response.json()
    
    return response [0]
    

saynormal_function = on_command("saynormal", aliases={"nbnhhsh", "能不能好好说话", "srh", "说人话"}, priority=10)

@saynormal_function.handle()
async def _ (bot: Bot, event: GroupMessageEvent | PrivateMessageEvent, args: Message = CommandArg()):
    msg = TITLE + " 能不能好好说话"
    user = User(event.get_user_id())
    _msg = args.extract_plain_text()

    # call nbnhhsh api
    _arg = _msg.split(" ")

    if _arg [0] == "submit":
        if len(_arg) < 2:
            await saynormal_function.finish(msg + "\n    - 请输入你要提交的 缩写 与 完整名称")
        await _handle_request("submitTrans", f"{_arg [1]},{_arg[2]}")
        await saynormal_function.finish(msg + "\n    - 您的词条提交成功！当词条审核通过后将可以被查询。")
    else:
        if _arg [0] == "":
            await saynormal_function.finish(msg + "\n    - 请使用 ^srh/^nbnhhsh/^saynormal <词条名> 来进行查询。")
 
        result = await _handle_request("guess", _arg [0])
        trans = result.get("trans", [])
        if len(trans) <= 0 or result.get("inputting") != None:
            msg += "\n    - 该缩写暂没有完整名称。\n    - 使用 ^srh submit <缩写> <完整名称> 来提交一个词条。"
        else:
            msg += f"\n    - 查询到 {len(trans)} 个词条。"
            for tran in trans:
                msg += f"\n    - {tran}"
            msg += "\n    - 使用 ^srh submit <缩写> <完整名称> 来提交一个词条。"
            await defines.send_fake_forward_msg(bot, event, msg)
            await saynormal_function.finish()