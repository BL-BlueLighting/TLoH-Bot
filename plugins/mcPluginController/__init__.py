
import json
import re
from typing import Optional, Tuple

from mcstatus import JavaServer
from nonebot import on_command
from nonebot.adapters.onebot.v11 import Bot, Message, MessageEvent
from nonebot.params import CommandArg

from toolsbot.configs import DATA_PATH
from toolsbot.services import _error

server_path = DATA_PATH / "mcServers.json"


def _safe_read_json(filepath, default=None):
    """Safely read a JSON file."""
    if default is None:
        default = {}
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, FileNotFoundError, OSError) as e:
        _error(f"Failed to read {filepath}: {e}")
        return default


def _safe_write_json(filepath, data):
    """Safely write JSON data to a file."""
    try:
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=4)
    except OSError as e:
        _error(f"Failed to write {filepath}: {e}")


def strip_minecraft_colors(text: str) -> str:
    """去除 Minecraft 颜色代码 (§ + hex digit)"""
    return re.sub(r"§[0-9A-FK-ORa-fk-or]", "", text)


def _parse_host_port(target: str) -> Tuple[str, int]:
    """Parse host:port string, defaulting port to 25565."""
    if ":" in target:
        host, port_str = target.split(":", 1)
        try:
            port = int(port_str)
        except ValueError:
            port = 25565
        return host, port
    return target, 25565


def _format_server_status(host: str, port: int, status) -> str:
    """Format a Minecraft server status into a display message."""
    motd = strip_minecraft_colors(status.description)
    online = status.players.online
    maxp = status.players.max
    latency = round(status.latency, 1)

    return (
        f"TLoH Bot Minecraft Plugin\n"
        f"    - 🌍 服务器：{host}:{port}\n"
        f"    - 📋 MOTD：\n    {motd}\n"
        f"    - 👥 在线人数：{online}/{maxp}\n"
        f"    - 📡 延迟：{latency} ms"
    )


async def _handle_query(target: str, handler) -> None:
    """Handle the 'query' subcommand to ping a Minecraft server."""
    target_clean = target.replace("query ", "", 1)
    host, port = _parse_host_port(target_clean)

    try:
        server = JavaServer(host, port)
        status = server.status()
        msg = _format_server_status(host, port, status)
    except Exception as e:
        _error(f"MC server query failed for {host}:{port}: {e}")
        msg = f"TLoH Bot Minecraft Plugin\n    - 查询失败：{type(e).__name__} - {e}"

    await handler.finish(msg)


async def _handle_look(target: str, handler) -> None:
    """Handle the 'look' subcommand to look up a saved server."""
    servers = _safe_read_json(server_path, [])
    lookup_name = target.replace("look ", "", 1)
    server_info = {}

    for srv in servers:
        if srv.get("Name") == lookup_name:
            server_info = srv
            break

    if not server_info:
        await handler.finish(
            f"TLoH Bot Minecraft Plugin\n"
            f"    - 🌍 服务器：{lookup_name} (Undefined)\n"
            f"    - 未找到该服务器的任何信息。"
        )
        return

    host, port = server_info.get("Address", ["", 0])
    if host == "" and port == 0:
        await handler.finish(
            f"TLoH Bot Minecraft Plugin\n"
            f"    - 🌍 服务器：{lookup_name} ({host}, {port})\n"
            f"    - 很抱歉，配置错误导致该服务器无法被查询。"
        )
        return

    try:
        server = JavaServer(host, port)
        status = server.status()
        msg = _format_server_status(lookup_name, port, status)
        # Override host display to show the lookup name
        msg = msg.replace(f"{host}:{port}", f"{lookup_name} ({host}:{port})", 1)
    except Exception as e:
        _error(f"MC server look failed for {lookup_name}: {e}")
        msg = f"TLoH Bot Minecraft Plugin\n    - 查询失败：{type(e).__name__} - {e}"

    await handler.finish(msg)


async def _handle_add(target: str, handler) -> None:
    """Handle the 'add' subcommand to add a new server."""
    try:
        name_part, address_part = target.split("ipaddress=")
        name = name_part.replace("add ", "", 1).strip()
    except ValueError:
        await handler.finish(
            "TLoH Bot Minecraft Plugin\n"
            "    - 参数错误。使用方法：^mcstatus add [名称] ipaddress=[IP]:[端口]"
        )
        return

    addr_parts = address_part.split(":")
    ip = addr_parts[0]
    try:
        port = int(addr_parts[1]) if len(addr_parts) > 1 else 25565
    except ValueError:
        await handler.finish(
            "TLoH Bot Minecraft Plugin\n    - 无法添加，原因：请输入正确的服务器端口"
        )
        return

    # Test connection
    try:
        server = JavaServer(ip, port)
        server.status()
    except Exception as e:
        _error(f"MC server add test failed for {ip}:{port}: {e}")
        await handler.finish(
            "TLoH Bot Minecraft Plugin\n"
            "    - 无法添加，原因：服务器无法联通或端口不正确/封禁 Bot IP"
        )
        return

    # Save configuration
    servers = _safe_read_json(server_path, [])
    servers.append({"Name": name, "Address": [ip, port]})
    _safe_write_json(server_path, servers)

    await handler.finish(
        f"TLoH Bot Minecraft Plugin\n"
        f"    - 添加成功！使用 ^mcstatus look {name} 来查看该服务器。"
    )


# =============================================================================
# Main command handler
# =============================================================================

mc_status = on_command("mcstatus", aliases={"mc服务器"}, priority=5)


@mc_status.handle()
async def handle_mcstatus(bot: Bot, event: MessageEvent, args: Message = CommandArg()):
    """Minecraft 服务器状态查询主处理器"""
    target = args.extract_plain_text().strip()
    if not target:
        await mc_status.finish(
            "TLoH Bot Minecraft Plugin\n"
            "    - 用法：^mcstatus query <地址>[:端口]\n"
            "    - 用法：^mcstatus look [服务器名]\n"
            "    - 用法：^mcstatus add [名称] ipaddress=[IP]:[端口，不填默认 25565]"
        )
        return

    _args = target.split(" ")
    subcmd = _args[0] if _args else ""

    sub_handlers = {
        "query": lambda: _handle_query(target, mc_status),
        "look": lambda: _handle_look(target, mc_status),
        "add": lambda: _handle_add(target, mc_status),
    }

    if subcmd in sub_handlers:
        await sub_handlers[subcmd]()
    else:
        await mc_status.finish(
            "TLoH Bot Minecraft Plugin\n"
            f"    - 未知指令: {subcmd}\n"
            "    - 用法：^mcstatus query/look/add ..."
        )
