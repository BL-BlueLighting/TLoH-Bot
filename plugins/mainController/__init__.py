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
Tools Bot 的第二版。

@author: BL-BlueLighting

mainController
"""

TITLE = "TLoH Bot"

"""
兜底函数
"""
# 获取配置里的 COMMAND_START，默认是 {'/', '!', '／', '！'}
command_starts = get_driver().config.command_start

def is_unmatched_command(msg: Message) -> bool:
    text = msg.extract_plain_text().strip()
    # 消息以 COMMAND_START 开头，并且不为空（避免只有 `/`）
    return bool(text) and any(text.startswith(s) for s in command_starts)

#fallback = on_message(priority=1000000, block=True)

#@fallback.handle()
async def _(msg: Message = EventMessage(), matcher: Matcher = Matcher()):
    if is_unmatched_command(msg):
        await matcher.finish("未知指令，请检查输入是否正确。")

"""
Help 函数
用于基本的介绍

@author: BL-BlueLighting
"""

COMMANDS_LIST = [
    ["help", "列出所有命令。"],
    ["info", "参数:[(可选)@用户] 显示用户信息。"],
    ["morning", "签到。"],
    ["buy", "TLoH Bot 商店"],
    ["base[16/32/58/64/85]", "参数:[(必须)encode/decode] Base家族编解码。"],
    ["lc64[(可选)_2]", "参数:[(必须)encode/decode] Liangcai 64 编码/解码。"],
    ["usecode", "参数:[(必须)兑换码] 兑换兑换码。"],
    ["pay", "参数:[(必须)@用户 钱款] 支付给@用户。"],
    ["echo", "参数:[(必须)内容] 输出文本。"],
    ["cleanwaste", "捡垃圾。"],
    ["moneybest", "金钱排行榜。"],
    ["ping/pong", "打乒乓球"],
    ["aes", "参数:[(必须)encrypt/decrypt] 加密解密 AES。"],
    ["accountStatus", "查看账号信息。"],
    ["check", "Bot 你没死吧。"],
    ["banlist", "封 神 榜"],
    ["[(可选)open]redpacket", "包红包/抢红包。"],
    ["mcstatus", "查看 MC 服务器状态。"],
    ["modifyname", "修改你的 TLoH Bot 账户用户名。"],
    ["bag", "查看背包。"],
    ["browsingbottle", "漂流瓶。"],
    ["voting", "投票。"],
    ["tryescape/tec/tryEscape", "逃离阈限空间系列。"],
    ["clearai", "清空 AI 上下文。"],
    ["ai", "参数:[(必须)内容] 问问 AI。"],
    ["lcgodmaker", "ARG 修仙系统。"],
    ["devilrounds", "恶魔轮盘赌。"],
    ["scp/scip/scpf/scpfoundation/scipterminal", "SCP 基金会相关功能。"],
    ["hellfunny", "地狱笑话功能。"],
    ["wordle", "Wordle 功能。"],
    ["saynormal", "能不能好好说话？"],
    ["hitokoto", "每日一言。"],
    ["zanwo", "给你个人资料点赞。"],
    ["vme50", "vivo 50."],
    ["超级用户权限分界线", "============="],
    ["ban", "参数:[@用户] 封禁用户。"],
    ["pardon", "参数:[@用户] 解禁用户。"],
    ["mute", "参数:[@用户(可多个)] minute=[时间] 禁言用户[时间]分钟。"],
    ["unmute", "参数:[@用户(可多个)] 解除用户禁言。"],
    ["undo", "参数:[引用一条消息] 撤回消息。"],
    ["essence", "参数:[引用一条消息] 精华一条消息。"],
    ["sql", "参数:[SQL] 对用户数据库执行 SQL。"],
    ["testadmin", "检查Bot是否是管理员笑传之测测呗"],
    ["botstop/botstart/botupdate/sendelike", "这些功能不常用，自行查看代码注释。"],
    ["broadcast", "参数:[(必须)广播内容] 广播消息。"],
    ["signnow", "在所有群签到。"],
    ["echot/echot_add/echot_del", "这些功能自己看，执行 ^echot 来查看相关介绍。"],
    ["私聊可用分界线","============="],
    ["aitalkstart", "开始 AI 聊天。"],
    ["aiprompt", "设置 AI 提示词。"],
    ["aitalkstop", "停止 AI 聊天。"],
]
# ============ 帮助命令 ============
help_cmd = on_command("help", priority=5, block=True)

@help_cmd.handle()
async def handle_help(bot: Bot, event: PrivateMessageEvent | GroupMessageEvent):
    """发送帮助菜单（合并转发消息）"""
    
    # 构建帮助文本
    help_lines = [
        "TLoH Bot - Help Menu",
        "=" * 30,
    ]
    
    # 添加命令列表
    if COMMANDS_LIST:
        for cmd, desc in COMMANDS_LIST:
            if not desc == "=============":
                help_lines.append(f"^{cmd} - {desc}")
            else:
                help_lines.append(f"\n{cmd} {desc}\n")
    else:
        help_lines.append("暂无可用命令")
    
    help_lines.append("=" * 30)
    help_lines.append("发送 ^help 查看此菜单")
    
    help_text = "\n".join(help_lines)
    
    # 发送合并转发消息
    try:
        # 构建合并转发的消息节点列表
        msg_nodes = []
        
        msg_nodes.append(
            MessageSegment.node_custom(
                user_id=int(bot.self_id),
                nickname="TLoH Bot",
                content=Message(help_text)
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
        
    except Exception as e:
        # 如果合并转发失败，降级为普通消息
        await help_cmd.finish(f"帮助菜单生成失败，请重试\n错误: {e}")

"""
check 函数
检测 bot 是否存活

@author: BL-BlueLighting
"""

check_function = on_command("check", priority=10)

@check_function.handle()
async def _ (bot: Bot, event: GroupMessageEvent | PrivateMessageEvent, args: Message = CommandArg()):
    await check_function.finish("TLoH Bot 还活着呢，没死。")

"""
^ping & ^pong 函数
和 bot 打乒乓球

@author: BL-BlueLighting
"""
ping_function = on_command("ping", priority=10)
pong_function = on_command("pong", priority=10)

@ping_function.handle()
async def _ (bot: Bot, event: GroupMessageEvent | PrivateMessageEvent):
    # 随机
    if random.randint(1, 10) > 5:
        await check_function.finish("没接住")
    else:
        await check_function.finish("pong")

@pong_function.handle()
async def _ (bot: Bot, event: GroupMessageEvent | PrivateMessageEvent):
    if random.randint(1, 10) > 5:
        await check_function.finish("没接住")
    else:
        await check_function.finish("ping")


"""
^essence 函数
设置精华消息

@author: BL-BlueLighting
"""
set_essence = on_command("essence", priority=5, permission=SUPERUSER)

@set_essence.handle()
async def _(bot: Bot, event: GroupMessageEvent, args: Message = CommandArg()):
    if event.reply:
        msg_id = event.reply.message_id
    else:
        await set_essence.finish("TLoH Bot Essence Set\n    - 请回复一条消息来设为精华")

    try:
        await bot.call_api("set_essence_msg", message_id=msg_id)
    except Exception as e:
        await set_essence.finish(f"TLoH Bot Essence Set\n    - 设置精华失败：{e}")
    else:
        await set_essence.finish("TLoH Bot Essence Set\n    - 已成功将该消息设为精华 ✨")


"""
hitokoto 函数

名言金句函數
@author: BL-BlueLighting
"""

goodsaying_function = on_command("hitokoto", priority=10)

@goodsaying_function.handle()
async def _ (bot: Bot, event: GroupMessageEvent | PrivateMessageEvent, args: Message = CommandArg()):
    msg = TITLE + " 名言金句"
    _msg = args.extract_plain_text()
    url = "https://hitokoto.152710.xyz"

    # request
    message = requests.get(url)

    # get json
    _jsonmessage = json.loads(message.content)

    # apppend
    hitokoto = _jsonmessage.get("hitokoto", "世上本沒有路，但是人走多了，便成了路。")
    _from = _jsonmessage.get("from", "《棍母》")
    creator = _jsonmessage.get("creator", "魯迅: 周樹人")

    # format
    msg += f"""
    {hitokoto}
                —— {_from} --- {creator}"""

    # finish
    await goodsaying_function.finish(msg)