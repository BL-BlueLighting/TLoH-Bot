import json
import os
import random

from nonebot import on_command
from nonebot.adapters import Message
from nonebot.adapters.onebot.v11 import Bot, MessageEvent
from nonebot.params import CommandArg

from toolsbot.configs import DATA_PATH

# 假设 TITLE 变量已在其他地方定义，这里为了完整性添加
TITLE = "TLoH Bot"

"""
弱智吧问题精选功能

@author: BL-BlueLighting
"""

QUESTION_FILE_PATH = DATA_PATH / "ruozhiba_question.json"

question_eventer = on_command("question", aliases={"弱智吧"}, priority=5, block=True)

@question_eventer.handle()
async def _(bot: Bot, event: MessageEvent, args: Message = CommandArg()):
    msg = f"{TITLE} 弱智吧问题精选\n"

    if not os.path.exists(QUESTION_FILE_PATH):
        await question_eventer.finish(f"{msg}    - 错误：问题文件不存在。")
        return

    try:
        with open(QUESTION_FILE_PATH, "r", encoding="utf-8") as f:
            questions_dict = json.load(f)
    except json.JSONDecodeError:
        await question_eventer.finish(f"{msg}    - 错误：问题文件格式不正确，请检查文件。")
        return

    questions_list = list(questions_dict.values())
    if not questions_list:
        await question_eventer.finish(f"{msg}    - 错误：问题文件中没有问题。")
        return

    random_question = random.choice(questions_list)

    # 4. 优化消息格式
    msg += f"    - 您抽到的问题为：{random_question}"

    await question_eventer.finish(msg)