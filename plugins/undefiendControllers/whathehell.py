import datetime

from nonebot import *
from nonebot.adapters.onebot.v11 import *
from nonebot.params import CommandArg

from toolsbot.services import _info

"""
TLoH Bot
Tools Bot 的第二版。

@author: BL-BlueLighting

undefiendControllers.whathehell MODULE.
What the hell 什么魔鬼
"""

TITLE = "TLoH Bot"

hell_funny = on_command("hellfunny", priority=5, block=True)

zale = on_message(priority=100)
@zale.handle()
async def _(bot: Bot, event: PrivateMessageEvent | GroupMessageEvent, args: Message = CommandArg()):
    _info(f"收到消息: {event.get_plaintext()}")
    if "咋了" in event.get_plaintext():
        await zale.finish("咋了")
    zale.skip()


@hell_funny.handle()
async def handle_hell_funny(bot: Bot, event: GroupMessageEvent | PrivateMessageEvent):
    # get today date
    today = datetime.datetime.now()
    _info(f"当前日期: {today.month}-{today.day}")  # 添加日期日志

    # if date = 9.11
    if today.month == 9 and today.day == 11:
        await hell_funny.finish("✈️    ⏸")

    # if date = 5.20
    if today.month == 5 and today.day == 20:
        await hell_funny.finish("祝有情人终成眷属，祝眷侣早日丧侣")

    # if date = 6.1
    if today.month == 6 and today.day == 1:
        await hell_funny.finish("祝小孩子们考0蛋")

    # if date = 9.1
    if today.month == 9 and today.day == 1:
        await hell_funny.finish("开学快乐")

    # if date = 11.29 / 11.30
    if (today.month == 11 and today.day == 29) or (today.month == 11 and today.day == 30):
        await hell_funny.finish("今天是地狱笑话模块被加入 ToolsBot 的日子，蝼蚁们，颤抖吧！！\n嘎啊哈哈哈哈")

    # if date = 12.24
    if today.month == 12 and today.day == 24:
        await hell_funny.finish("Bot 主生日快乐。")

    # if date = 12.31
    if today.month == 12 and today.day == 31:
        await hell_funny.finish("新年快乐！\n🎉🎉🎉🎉🎉🎉🎉🎉🎉🎉🎉🎉🎉🎉🎉🎉🎉🎉🎉🎉🎉🎉🎉")

    # if date = 2.8
    if today.month == 2 and today.day == 8:
        await hell_funny.finish("RE: ToolsBot -> TLoH Bot")

vme50 = on_command("vme50", aliases={"v50", "vivo50", "v我50", "VIVO50", "V我50", "V50", "微我五十", "微我50", "微我五十", "微我50元", "微我五十元"}, priority=5, block=True)
@vme50.handle()
async def _(bot: Bot, event: PrivateMessageEvent | GroupMessageEvent, args: Message = CommandArg()):
    _info(f"收到消息: {event.get_plaintext()}")
    pt = event.get_plaintext()
    if "v" in pt.lower() and "50" in pt.lower():
        # 获取今天是星期几
        today = datetime.datetime.now().weekday() + 1
        if today != 4:
            msg = "今天不是星期四，不能发动技能喵"
            # generate reply message
            _msg = Message(MessageSegment.reply(event.message_id)) + Message(MessageSegment.at(event.user_id)) + MessageSegment.text(msg)
            await vme50.finish(_msg)
        else:
            msg = "今天虽然是星期四但 bot 没钱喵"
            # generate reply message
            _msg = Message(MessageSegment.reply(event.message_id)) + Message(MessageSegment.at(event.user_id)) + MessageSegment.text(msg)
            await vme50.finish(_msg)

vme50plus = on_message(priority=5)
@vme50plus.handle()
async def _(bot: Bot, event: PrivateMessageEvent | GroupMessageEvent, args: Message = CommandArg()):
    _info(f"收到消息: {event.get_plaintext()}")
    pt = event.get_plaintext()
    if "v" in pt.lower() and "50" in pt.lower():
        # 获取今天是星期几
        today = datetime.datetime.now().weekday() + 1
        if today != 4:
            msg = "今天不是星期四，不能发动技能喵"
            # generate reply message
            _msg = Message(MessageSegment.reply(event.message_id)) + Message(MessageSegment.at(event.user_id)) + MessageSegment.text(msg)
            await vme50.finish(_msg)
        else:
            msg = "今天虽然是星期四但 bot 没钱喵"
            # generate reply message
            _msg = Message(MessageSegment.reply(event.message_id)) + Message(MessageSegment.at(event.user_id)) + MessageSegment.text(msg)
            await vme50.finish(_msg)