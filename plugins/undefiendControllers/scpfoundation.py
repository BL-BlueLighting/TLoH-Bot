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

# CROM API configuration
CROM_API_URL = "https://typesense.crom.avn.sh/collections/pages/documents/search"
CROM_API_KEY = "JuNllePLZUdprXW99B2xQb6FMhjaDza5"

BRANCH_MAP = {
    "cn": "http://scp-wiki-cn.wikidot.com",
    "en": "http://scp-wiki.wikidot.com",
}


def _build_crom_search_params(search_keyword: str, branch_url: str) -> dict:
    """Build search parameters for the CROM API."""
    return {
        "q": search_keyword,
        "query_by": "publicTitle,alternateTitle,textContent,titleEmbedding",
        "page": 1,
        "per_page": 5,
        "search_cutoff_ms": 240,
        "filter_by": f"origin:={branch_url}",
        "include_fields": "id,url,publicTitle,alternateTitle,textContent,rating,tags",
        "highlight_fields": "publicTitle,alternateTitle,textContent"
    }


def _format_search_result(index: int, doc: dict) -> str:
    """Format a single search result hit into a string."""
    title = doc.get("publicTitle") or doc.get("title") or "未知标题"
    url = doc.get("url", "")
    rating = doc.get("rating", "N/A")
    tags = doc.get("tags", [])
    content = doc.get("textContent", "").replace("\n", " ").replace("\r", "")
    if len(content) > 150:
        content = content[:150] + "..."

    return (
        f"\n[{index}] {title}"
        f"\n评分: {rating}"
        f"\n标签: {', '.join(tags[:8])}"
        f"\n链接: {url}"
        f"\n摘要: {content}\n"
    )


async def _handle_fetch_command(branch: str, name: str, entry_type: str, handler) -> None:
    """Handle the 'fetch' subcommand to search SCP entries."""
    await handler.send("稍等，正在为您调取数据库...")

    if branch not in BRANCH_MAP:
        await handler.finish("未知分部。\n支持: cn / en。")
        return

    search_keyword = name
    if entry_type == "故事":
        search_keyword += " tale"

    params = _build_crom_search_params(search_keyword, BRANCH_MAP[branch])
    headers = {"X-TYPESENSE-API-KEY": CROM_API_KEY}

    try:
        response = requests.get(CROM_API_URL, params=params, headers=headers, timeout=10)
        response.raise_for_status()
        data = response.json()
    except requests.RequestException as e:
        _error(f"CROM API request failed: {e}")
        await handler.finish("检索请求失败，请稍后再试。")
        return
    except json.JSONDecodeError as e:
        _error(f"CROM API response parse failed: {e}")
        await handler.finish("检索响应解析失败。")
        return

    hits = data.get("hits", [])
    if not hits:
        await handler.finish(_info(f"未找到与 {name} 相关的条目。"))
        return

    msg = "检索完成。\n"
    for i, hit in enumerate(hits[:3], start=1):
        doc = hit.get("document", {})
        msg += _format_search_result(i, doc)

    await handler.finish(msg)


# =============================================================================
# Main command handler
# =============================================================================

scp_function = on_command("scp", aliases={"scpf", "scpfoundation", "scip", "scipterminal"},
                           priority=10)


@scp_function.handle()
async def handle_scp(bot: Bot, event: GroupMessageEvent | PrivateMessageEvent,
                      _args: Message = CommandArg()):
    """SCP 基金会相关功能主处理器"""
    msg = TITLE + " - SCP 基金会相关功能"
    user = uic.User(event.get_user_id())
    _msg = _args.extract_plain_text()
    args = _msg.strip().split(" ")

    if not args or args[0] in ("", "help"):
        msg += "\n欢迎回到 SCiP TLoH Bot 终端。"
        msg += "\n您想做什么？"
        msg += "\n    - fetch <branch> <name> <type=故事|SCP>"
        msg += "\n    - subscribe <wikidot page>"
        msg += "\n(目前 fetch 功能仅支持 中文分部(cn) 英文分部(en) 旧日分部(od) 云分(cloud))"
        msg += "\n其他功能 TLoH Bot 终端尚未支持。\n若需其他功能，请联系技术部门。"
        await scp_function.finish(msg)

    if args[0] == "fetch":
        if len(args) < 4:
            await scp_function.finish(
                "参数不足。\n使用方法: fetch <branch> <name> <type=故事|SCP>"
            )
        await _handle_fetch_command(args[1], args[2], args[3], scp_function)
    else:
        msg += f"\n未知命令: {args[0]}\n使用 'help' 查看帮助。"

    await scp_function.finish(msg)
