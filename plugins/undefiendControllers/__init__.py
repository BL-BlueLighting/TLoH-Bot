from . import botmanaging as btm
from . import echoManager as ecm
from . import scpfoundation as scp
from . import whathehell as wht
from . import ai_funcs as aif
from . import killers as kle
from . import wordle as wdl
from . import autosign as asi
from nonebot.adapters.onebot.v11 import *

# UNDEFIEND CONTROLLERS PLUGIN INITALIZATION FILE
# 这个 __init__.py 并不是主代码文件，而是副代码文件。
# undefiend 是故意取得名字，没打错。

# 不好归类的东西放 undefiendControllers __init__.py 里头

zanwo = btm.on_command("zanwo", aliases={"赞我", "likeme", "like"}, priority=10)

@zanwo.handle()
async def _ (bot: Bot, event: GroupMessageEvent | PrivateMessageEvent):
    uid = event.get_user_id()
    try:
        await bot.call_api("send_like", user_id=uid, times=10)
    except:
        await zanwo.finish("TLoH Bot\n    - 点赞失败。。。我是不是已经给你点过了喵？")
    else:
        await zanwo.finish("TLoH Bot\n    - 给你点赞啦。记得查收并回赞哦！")