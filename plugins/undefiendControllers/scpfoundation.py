import requests
from lxml import html as hi
from nonebot import on_command
from nonebot.adapters import Message
from nonebot.adapters.onebot.v11 import (Bot, GroupMessageEvent,
                                         PrivateMessageEvent)
from nonebot.params import CommandArg

import plugins.userInfoController as uic
from toolsbot.services import _error, _info

"""
TLoH Bot
Tools Bot 的第二版。

@author: BL-BlueLighting

undefiendControllers.scpfoundation MODULE.
SCP 基金会相关功能。
"""

TITLE = "TLoH Bot"

"""
SCP 函数

@author: BL-BlueLighting
"""

scp_function = on_command("scp", aliases={}, priority=10)

@scp_function.handle()
async def _ (bot: Bot, event: GroupMessageEvent | PrivateMessageEvent, _args: Message = CommandArg()):
    msg =  TITLE + " - SCP 基金会相关功能"
    user = uic.User(event.get_user_id())
    _msg = _args.extract_plain_text()
    args = _msg.strip().split(" ")

    if args [0] == "" or args [0] == "help":
        msg += "\n欢迎回到 SCiP TLoH Bot 终端。"
        msg += "\n您想做什么？"
        msg += "\n    - fetch <branch> <name> <type=故事|SCP>"
        msg += "\n    - subscribe <wikidot page>"
        msg += "\n(目前 fetch 功能仅支持 中文分部(cn) 英文分部(en) 旧日分部(od) 云分(cloud))"
        msg += "\n其他功能 TLoH Bot 终端尚未支持。\n若需其他功能，请联系技术部门。"
    
    elif args [0] == "fetch":
        await scp_function.send("稍等，正在为您调取数据库...")
        br = args [1]
        nm = args [2]
        tp = args [3]

        # 调用 api 致歉
        branch_map = {
            "cn": "http://scp-wiki-cn.wikidot.com",
            "en": "http://scp-wiki.wikidot.com",
            # "od": "http://scp-wiki-od.wikidot.com",
            # "cloud": "http://scp-wiki-cloud.wikidot.com"
            # 这俩没有接入 CROM，理论上所有接入 CROM 的 SCP 分部甚至 The Backrooms 都可以用这个 API 检索到
            # 并且因为 RU 分部使用了 Wikijump (不是 Wikidot) 导致 CROM 无法检索。
            # 其他分部比如法分、德分都可以查到，但是我懒得写
        }

        if br not in branch_map:
            await scp_function.finish(
                _error("未知分部。\n支持: cn / en。")
            )

        search_keyword = nm

        if tp == "故事":
            search_keyword += " tale"

        API_URL = (
            "https://typesense.crom.avn.sh"
            "/collections/pages/documents/search"
        )

        API_KEY = "JuNllePLZUdprXW99B2xQb6FMhjaDza5" # CROM 的开发者真的很对不起但是直接 request 文章会被 wikidot 的屎山 HTML 冲垮🙏🙏🙏

        params = {
            "q": search_keyword,
            "query_by":
                "publicTitle,"
                "alternateTitle,"
                "textContent,"
                "titleEmbedding",

            "page": 1,
            "per_page": 5,
            "search_cutoff_ms": 240,

            "filter_by":
                f"origin:={branch_map[br]}",

            "include_fields":
                "id,"
                "url,"
                "publicTitle,"
                "alternateTitle,"
                "textContent,"
                "rating,"
                "tags",

            "highlight_fields":
                "publicTitle,"
                "alternateTitle,"
                "textContent"
        }

        headers = {
            "X-TYPESENSE-API-KEY": API_KEY
        }

        try:
            r = requests.get(
                API_URL,
                params=params,
                headers=headers,
                timeout=10
            )

            r.raise_for_status()

            data = r.json()

            hits = data.get("hits", [])

            if not hits:
                await scp_function.finish(
                    _info(f"未找到与 {nm} 相关的条目。")
                )

            msg = "检索完成。\n"

            for index, hit in enumerate(hits[:3], start=1):
                doc = hit.get("document", {})

                title = (
                    doc.get("publicTitle")
                    or doc.get("title")
                    or "未知标题"
                )

                url = doc.get("url", "")

                rating = doc.get("rating", "N/A")

                tags = doc.get("tags", [])

                content = (
                    doc.get("textContent", "")
                    .replace("\n", " ")
                    .replace("\r", "")
                )

                if len(content) > 150:
                    content = content[:150] + "..."

                msg += (
                    f"\n[{index}] {title}"
                    f"\n评分: {rating}"
                    f"\n标签: {', '.join(tags[:8])}"
                    f"\n链接: {url}"
                    f"\n摘要: {content}"
                    f"\n"
                )

        except Exception as e:
            await scp_function.finish(
                _error(
                    "检索失败。\n"
                    f"{type(e).__name__}: {e}"
                )
            )
            
    await scp_function.finish(msg)
