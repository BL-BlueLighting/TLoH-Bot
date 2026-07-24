import nonebot
nonebot.require("nonebot_plugin_apscheduler")
from nonebot_plugin_apscheduler import scheduler
import toml
from nonebot import on_command
from nonebot.adapters import Message
from nonebot.adapters.onebot.v11 import (Bot, GroupMessageEvent,
                                         PrivateMessageEvent)
from nonebot.exception import ActionFailed
from nonebot.params import CommandArg
from nonebot.permission import SUPERUSER

from toolsbot.configs import DATA_PATH
from toolsbot.services import _error, _info, _warn

"""
TLoH Bot
Tools Bot 的第二版。

@author: BL-BlueLighting

undefiendControllers.autosign
自动签到
"""

_info("自动签到插件加载成功。")
@scheduler.scheduled_job("cron", hour=0, minute=0, second=0, id="autosign")
async def _():
    try:
        with open(DATA_PATH.joinpath("config.toml"), "r", encoding="utf-8") as f:
            config = toml.load(f)
        if config["EnableAutoSign"]:
            bot = nonebot.get_bot()
            group_list = await bot.get_group_list()
            for group in group_list:
                try:
                    await bot.call_api("set_group_sign", group_id = group ['group_id'])
                except ActionFailed as e:
                    _warn(f"Failed to send stop message to group {group['group_id']}. This is why:\n{e}")
            await bot.send_private_msg(user_id = eval(open("./.env.prod", "r").readlines() [4].replace("SUPERUSERS=", ""))[0], message = f"TLoH Bot - 自动签到\n已完成自动签到。签到 {len(group_list)} 个群组。")
            # 解析：
            # .env.prod 的第四行为 SUPERUSERS 配置，去除 SUPERUSERS= 这个 prefix（.replace(, "=")) 之后可以直接得到超级用户列表，默认超级用户列表的第一个人为超级管理员，使用 eval 限制运行上下文的同时获得管理员列表，最后取第一个元素作为超级管理员的 QQ 号发送消息。
            _info("自动签到已完成。")
            return
    except ActionFailed as e:
        _error(f"自动签到失败: {e}")
    except Exception as e:
        _error(f"自动签到发生错误: {e}")