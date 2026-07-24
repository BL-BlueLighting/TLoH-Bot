import json

import nonebot
from nonebot import on_command
from nonebot.adapters import Message
from nonebot.adapters.onebot.v11 import MessageEvent
from nonebot.exception import ActionFailed
from nonebot.params import CommandArg
from nonebot.permission import SUPERUSER

from toolsbot.services import _warn

"""
TLoH Bot
Tools Bot 的第二版。

@author: BL-BlueLighting

undefiendControllers.botmanaging MODULE.
"""

stop_command = on_command("botstop", priority=5, permission=SUPERUSER)

@stop_command.handle()
async def stop_bot(event: MessageEvent):
    # 发送 msg 到 bot 加入的所有群聊
    msg = """TLoH Bot - 停机公告
    由于维护原因，TLoH Bot 将停止运行，直到 TLoH Bot 重新启动。
    """

    # get all group ids
    bot = nonebot.get_bot()
    group_list = await bot.get_group_list()

    for group in group_list:
        try:
            await bot.send_group_msg(group_id=group["group_id"], message=msg)
        except ActionFailed as e:
            _warn(f"Failed to send stop message to group {group['group_id']}. This is why:\n{e}")

        # use native api

start_command = on_command("botstart", priority=5, permission=SUPERUSER)

@start_command.handle()
async def start_bot(event: MessageEvent):
    # 发送 msg 到 bot 加入的所有群聊
    msg = """TLoH Bot - 启动公告
    TLoH Bot 已重新启动。
    """

    # get all group ids
    bot = nonebot.get_bot()
    group_list = await bot.get_group_list()

    for group in group_list:
        try:
            await bot.send_group_msg(group_id=group["group_id"], message=msg)
        except ActionFailed as e:
            _warn(f"Failed to send stop message to group {group['group_id']}. This is why:\n{e}")

        # use native api

update_command = on_command("botupdate", priority=5, permission=SUPERUSER)

@update_command.handle()
async def update_bot(event: MessageEvent, arg: Message = CommandArg()):
    msg = "TLoH Bot - Updated - Version "
    # get version from userinput
    content = arg.extract_plain_text()

    version = content.split(" ") [0]
    update_contents = content.split(" ") [1:]

    msg += version

    # get all group ids
    bot = nonebot.get_bot()
    group_list = await bot.get_group_list()

    # generate msg
    for _update_content in update_contents:
        msg += f"\n    - {_update_content}"

    for group in group_list:
        try:
            await bot.send_group_msg(group_id=group["group_id"], message=msg)
        except ActionFailed as e:
            _warn(f"Failed to send stop message to group {group['group_id']}. This is why:\n{e}")

broadcast_command = on_command("broadcast", priority=5, permission=SUPERUSER)

@broadcast_command.handle()
async def broadcast_bot(event: MessageEvent, arg: Message = CommandArg()):
    # get all group ids
    bot = nonebot.get_bot()
    group_list = await bot.get_group_list()

    # get msg
    content = arg.extract_plain_text()
    msg = f"TLoH Bot - Broadcast\n    - {content}"

    for group in group_list:
        try:
            await bot.send_group_msg(group_id=group["group_id"], message=msg)
        except ActionFailed as e:
            _warn(f"Failed to send stop message to group {group['group_id']}. This is why:\n{e}")

send_to_command = on_command("sendto", priority=5, permission=SUPERUSER)

@send_to_command.handle()
async def send_to_bot(event: MessageEvent, arg: Message = CommandArg()):
    bot = nonebot.get_bot()
    # get group id from plain text
    _plt = arg.extract_plain_text()
    group_id = _plt.split(" ")[0]
    __msg = _plt.split(" ")[1:]

    # generate msg
    msg = f"TLoH Bot - Send To {group_id} - From SUPERUSER\n"
    for _msg in __msg:
        msg += f"    - {_msg}\n"

    try:
        await bot.send_group_msg(group_id=group_id, message=msg)
    except ActionFailed as e:
        _warn(f"Failed to send stop message to group {group_id}. This is why:\n{e}")

signnow_handler = on_command("signnow", permission=SUPERUSER)

@signnow_handler.handle()
async def _ ( event: MessageEvent, args: Message = CommandArg()):
    msg = "TLoH Bot - SIGN"
    msg += "    - Bot sign process running..."
    bot = nonebot.get_bot()
    group_list = await bot.get_group_list()

    for group in group_list:
        try:
            msg += f"    - {group['group_id']} bot signed."
            await bot.call_api("set_group_sign", group_id = group ['group_id'])
        except ActionFailed as e:
            _warn(f"Failed to send stop message to group {group['group_id']}. This is why:\n{e}")

send_emoji_like = on_command("sendelike", permission=SUPERUSER)

@send_emoji_like.handle()
async def _(event: MessageEvent, args: Message = CommandArg()):
    emoji_name = args.extract_plain_text()
    global _emoji_id
    with open("./data/emojiIds.json", "r") as f:
        _ids = json.load(f)
        try:
            _emoji_id = int(_ids [emoji_name])
        except:
            _emoji_id = 424
    if not event.reply:
        await send_emoji_like.finish("请回复消息.")

    await nonebot.get_bot().call_api("set_msg_emoji_like", message_id = event.reply.message_id, emoji_id = _emoji_id)
    await send_emoji_like.finish()

