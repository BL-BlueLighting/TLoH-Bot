import json
import random
from pathlib import Path

import requests
from nonebot import get_driver, on_command
from nonebot.adapters.onebot.v11 import (Bot, GroupMessageEvent,
                                         PrivateMessageEvent, Message)
from nonebot.adapters.onebot.v11.message import MessageSegment
from nonebot.matcher import Matcher
from nonebot.params import CommandArg, EventMessage
from nonebot.permission import SUPERUSER

"""
TLoH Bot

快速函数列表
"""

async def send_fake_forward_msg(bot: Bot, event: GroupMessageEvent | PrivateMessageEvent, msg_content: str):
    """调用 Onebot V11 Api 发送假的群聊转发消息"""
    try:
        # 构建合并转发的消息节点列表
        msg_nodes = []
        
        msg_nodes.append(
            MessageSegment.node_custom(
                user_id=int(bot.self_id),
                nickname="TLoH Bot",
                content=Message(msg_content)
            )
        )
        
        # 发送合并转发消息
        await bot.send_group_forward_msg(
            group_id=event.group_id,
            messages=msg_nodes
        ) if isinstance(event, GroupMessageEvent) else await bot.send_private_forward_msg(
            user_id=event.user_id,
            messages=msg_nodes
        )

        return 0
        
    except Exception as e:
        # 如果合并转发失败，降级为普通消息
        return -1