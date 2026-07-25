import datetime
import json
import os
import random
import sqlite3
from typing import Optional, List

from nonebot import on_command
from nonebot.adapters import Message
from nonebot.adapters.onebot.v11 import (Bot, GroupMessageEvent,
                                         PrivateMessageEvent)
from nonebot.params import CommandArg

import plugins.userInfoController as uic
from toolsbot.configs import DATA_PATH
from toolsbot.services import _error, _info

"""
TLoH Bot
Tools Bot 的第二版。

@author: BL-BlueLighting

argGodMakerController
"""

TITLE = "TLoH Bot"
TIMEDATESTR = "%Y-%d-%m-%H-%M-%S"

cfg_path = DATA_PATH / "gmConfig.json"
pking_json_path = DATA_PATH / "gmPKing.json"
pk_info_path = DATA_PATH / "gmPKinfo.json"
pking_path = DATA_PATH / "gmPKing"


def _safe_read_json(filepath, default=None):
    """Safely read a JSON file with error handling."""
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


class GMUser:
    """ARG 修仙系统用户"""

    def __init__(self, userEntity, status: str = "凉菜起"):
        self.user = userEntity
        self.status = status
        self.rating = 0
        self.level = 1
        self.pausing = False
        self.beginPause: Optional[datetime.datetime] = None
        self.db_path = DATA_PATH / "userdata.db"
        self._init_db()
        self.load()

    def _init_db(self):
        """初始化数据库表结构"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS gods (
                        ID TEXT PRIMARY KEY,
                        Status TEXT NOT NULL,
                        Rating INTEGER DEFAULT 0,
                        Level INTEGER DEFAULT 1,
                        Pausing BOOLEAN DEFAULT FALSE,
                        BeginPause TEXT
                    )
                """)
                conn.commit()
        except sqlite3.Error as e:
            _error(f"Failed to initialize gods table: {e}")

    def load(self):
        """Load GM user data from database."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT Status, Rating, Level, Pausing, BeginPause FROM gods WHERE ID = ?",
                    (self.user.id,)
                )
                row = cursor.fetchone()

                if row is None:
                    self.initData()
                    return

                self.status = row[0]
                self.rating = row[1]
                self.level = row[2]
                self.pausing = bool(row[3])
                if row[4]:
                    try:
                        self.beginPause = datetime.datetime.strptime(row[4], "%Y-%m-%d %H:%M:%S")
                    except (ValueError, TypeError):
                        self.beginPause = datetime.datetime(2025, 1, 1, 1, 1, 1)
                else:
                    self.beginPause = datetime.datetime(2025, 1, 1, 1, 1, 1)
        except sqlite3.Error as e:
            _error(f"Failed to load GM user: {e}")
            self.initData()

    def initData(self):
        """Initialize new GM user data."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO gods (ID, Status, Rating, Level, Pausing, BeginPause)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (
                    self.user.id, self.status, self.rating,
                    self.level, False, "2025-01-01 01:01:01"
                ))
                conn.commit()
        except sqlite3.Error as e:
            _error(f"Failed to initialize GM user data: {e}")

    def save(self):
        """Save GM user data to database."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                begin_pause_str = (
                    self.beginPause.strftime("%Y-%m-%d %H:%M:%S")
                    if self.beginPause else None
                )
                cursor.execute("""
                    UPDATE gods
                    SET Status = ?, Rating = ?, Level = ?, Pausing = ?, BeginPause = ?
                    WHERE ID = ?
                """, (
                    self.status, self.rating, self.level,
                    self.pausing, begin_pause_str, self.user.id
                ))
                conn.commit()
        except sqlite3.Error as e:
            _error(f"Failed to save GM user: {e}")

    def uplevel(self) -> bool:
        """Attempt to level up. Returns True on success."""
        if random.randint(1, 10) < 5:
            self.level += 1
            self.save()
            return True
        return False

    def setStatus(self, status: str):
        self.status = status
        self.save()

    def getStatus(self) -> str:
        self.save()
        return f"{self.status} {self.level} 层"

    def getRating(self) -> int:
        self.save()
        return self.rating

    def upRating(self, rating: int):
        self.rating += rating
        self.save()

    def downRating(self, rating: int):
        self.rating -= rating
        self.save()

    def pause(self):
        self.pausing = True
        self.beginPause = datetime.datetime.now()
        self.save()

    def checkPause(self) -> bool:
        """Check if pause timer has expired. Returns True if pause ended."""
        if self.beginPause and (datetime.datetime.now() - self.beginPause).seconds > 60:
            self.pausing = False
            self.save()
            return True
        return False


STATUSES = [
    "凉菜起",
    "杨倒带",
    "梁才起",
    "T3",
    "群u",
    "212",
    "derakkuma",
    "鳝丝",
    "国人",
    "小一",
    "Hello World",
    "是你让我扁",
    "是你让我神经w",
    "何异味。",
    "T1",
    "T2",
    "T0",
    "Richard",
    "Copilot",
    "DeepSeek",
    "Gemini",
    "文档",
    "退群。",
    "cutebox",
    "小绿叶",
    "SCP-Cloud-373",
    "他妈手抄",
    "令人忍俊不禁",
    "你们在瞎搞",
    "我们在瞎搞",
    "瞎搞军团",
    "诗人v1",
    "诗人v2",
    "门口午睡",
    "iai 更新日期",
    "烦人的英语",
    "德粒沙壁",
    "一群傻逼活该被炸服",
    "这么强",
    "那么扁",
    "邮差是吾辈",
    "你真的是邮差吗",
    "www.114514@qq.com",
    "职业中",
    "失业中",
    "点不动，，，",
    "Original",
    "Plus",
    "GReeN",
    "GReeN Plus",
    "ORANGE",
    "ORANGE Plus",
    "PiNK",
    "PiNK Plus",
    "murasaki",
    "murasaki Plus",
    "MiLK",
    "MiLK Plus",
    "FiNALE",
    "DX Original",
    "DX Plus",
    "DX Splash",
    "DX Splash Plus",
    "DX UNiVERSE",
    "DX UNiVERSE Plus",
    "DX FESTiVAL",
    "DX FESTiVAL Plus",
    "DX BUDDiES",
    "DX BUDDiES Plus",
    "DX PRiSM",
    "DX PRiSM Plus",
    "DX Circle",
    "PΛNDΘRΛ BΘXXX",
    "PANDORA PARADOXXX",
    "KALEID<>SCOPE",
    "Xaleid<>scopiX",
    "Virtual to Live",
    "QZKago Requiem",
    "FFT",
    "Alea jacta est!",
    "系ぎて",
    "King of Performai",
    "WEC",
    "Abstract",
    "Undertale",
    "Underverse",
    "SP!DUSTTALE",
    "DUSTTALE",
    "雨刮器",
    "After Pandora",
    "NightTheater",
    "Deltarune Chapter"
]


# =============================================================================
# Command handler sub-functions
# =============================================================================

def _format_help_message() -> str:
    """Format the help message for lcgodmaker."""
    return (
        f"TLoH Bot - ARG 修仙系统\n"
        f"    欢迎来到 ARG 修仙系统！\n"
        f"    本命令支持的操作如下：\n"
        f"        - list: 显示操作列表\n"
        f"        - begin: 开始修仙。\n"
        f"        - info: 显示修仙信息，如段位。\n"
        f"        - pk: 和他人 pk。\n"
        f"        - best: 排行榜。\n"
        f"        - break: 结束修仙。\n"
        f"    目前 ARG 修仙系统共有 {len(STATUSES)} 个段位。"
    )


async def _handle_begin(gmUser: GMUser, finish_fn) -> None:
    """Handle the 'begin' subcommand."""
    if not gmUser.pausing:
        gmUser.pause()
        await finish_fn(
            f"TLoH Bot - ARG 修仙系统\n"
            f"        - 您当前段位：{gmUser.getStatus()};\n"
            f"        - 正在尝试晋升：{gmUser.status} {gmUser.level + 1} 层\n"
            f"        - 请等待一分钟后再来 break，或者 break 掉来继续操作。"
        )
    elif gmUser.beginPause is not None:
        delta = (datetime.datetime.now() - gmUser.beginPause).seconds
        remaining = abs(delta - 60)
        await finish_fn(
            f"TLoH Bot - ARG 修仙系统\n"
            f"        - 您正在试图晋升，请不要再次使用。\n"
            f"        - 距离 break 时间：{remaining}"
        )
    else:
        await finish_fn("TLoH Bot - ARG 修仙系统\n    - 未知状态，请联系管理员。")


async def _handle_info(gmUser: GMUser, finish_fn) -> None:
    """Handle the 'info' subcommand."""
    await finish_fn(
        f"TLoH Bot - ARG 修仙系统\n"
        f"    - 用户 ID：{gmUser.user.id}\n"
        f"    - 用户段位：{gmUser.getStatus()}\n"
        f"    - RATING：{gmUser.rating}"
    )


async def _handle_break(gmUser: GMUser, cargs: list, finish_fn) -> None:
    """Handle the 'break' subcommand."""
    if len(cargs) == 2:
        gmUser.pausing = False
        gmUser.save()
        await finish_fn("TLoH Bot - ARG 修仙系统\n    - 已强制结束修仙。")
        return

    if not gmUser.checkPause():
        await finish_fn(
            "TLoH Bot - ARG 修仙系统\n"
            "    - 请使用 ^lcgodmaker break sure 来强制结束修仙。"
        )
        return

    rmsg = "TLoH Bot - ARG 修仙系统\n"

    if gmUser.level < 5:
        gmUser.level += 1
        gmUser.rating += random.randint(1000, 9999)
        gmUser.save()
        rmsg += "    - 您的等级已晋升。\n    - 目前等级：" + gmUser.getStatus()
    else:
        gmUser.level = 1
        try:
            status_index = STATUSES.index(gmUser.status)
        except ValueError:
            status_index = 0

        if status_index == len(STATUSES) - 1:
            rmsg += "    == PERFECT CHALLENGE ==\n    - 目前没有更新的段位。请等待 PERFECT CHALLENGE 第一赛季登场。"
        else:
            gmUser.rating += random.randint(1000, 9999)
            gmUser.setStatus(STATUSES[status_index + 1])
            rmsg += "    - 您的等级已晋升。\n    - 目前等级：" + gmUser.getStatus()
        gmUser.save()

    await finish_fn(rmsg)


async def _handle_pk(bot: Bot, event, gmUser: GMUser, cargs: list, finish_fn) -> None:
    """Handle the 'pk' subcommand."""
    rmsg = "TLoH Bot - ARG 修仙 - Global PK"
    gmConfig = _safe_read_json(cfg_path)

    rmsg += "\n    - 当前赛季：" + gmConfig.get("Status", "???")
    rmsg += "\n    - 您的 Rating：" + str(gmUser.rating)
    rmsg += "\n    - G L O B A L . P . K . - 开场"

    if len(cargs) == 1:
        cargs.append("")

    pk_subcmd = cargs[1] if len(cargs) > 1 else ""

    if pk_subcmd == "with":
        rmsg = await _pk_with(bot, event, gmUser, cargs, gmConfig, rmsg, finish_fn)
    elif pk_subcmd == "status":
        rmsg = await _pk_status(gmUser, rmsg, finish_fn)
    elif pk_subcmd == "season":
        rmsg = await _pk_season(gmUser, gmConfig, rmsg)
    else:
        rmsg += (
            "\nTLoH Bot - ARG 修仙 GLOBAL.P.K.\n"
            "    - 使用 ^lcgodmaker pk with @[XXX] 来和一个人发起 PK.\n"
            "    - 使用 ^lcgodmaker pk status 来查看和另一个人发起的 PK 的相关信息。\n"
            "    - 使用 ^lcgodmaker pk season 来查看赛季信息。"
        )

    await finish_fn(rmsg)


async def _pk_with(bot: Bot, event, gmUser: GMUser, cargs: list,
                    gmConfig: dict, rmsg: str, finish_fn) -> str:
    """Handle pk with command."""
    try:
        qq = uic.At(event.json())[0]
    except IndexError:
        return rmsg + "\n    - 请 @一个用户 来发起 PK。"

    if qq == "all":
        return rmsg + "\n    - 我的妈呀，你对战全体成员？"

    if not gmConfig.get("PKEnabled", False):
        return rmsg + "\n    - P.K. 暂时未揭幕。"

    _pking = _safe_read_json(pking_json_path, [])
    pkusers = []
    for pk_entry in _pking:
        parts = pk_entry.split(":")
        if len(parts) >= 2:
            pkusers.extend(parts[:2])

    if gmUser.user.id in pkusers:
        return rmsg + "\n    - 你已经在 P.K. 中了。\n    - 使用 ^lcgodmaker pk status 来查看 P.K. 进度。"

    pkinfo = {
        "Users": [gmUser.user.id, qq],
        "StartTime": datetime.datetime.now().strftime(TIMEDATESTR),
        "Redeem": random.randint(1000, 9999)
    }

    _pki = _safe_read_json(pk_info_path, [])
    _pki.append(pkinfo)
    _safe_write_json(pk_info_path, _pki)

    _pking.append(f"{gmUser.user.id}:{qq}")
    _safe_write_json(pking_json_path, _pking)

    try:
        opponent_status = GMUser(uic.User(qq)).getStatus()
    except Exception as e:
        _error(f"Failed to get opponent status: {e}")
        opponent_status = "未知"

    rmsg += "\n    - 你与 " + qq + " 开始 P.K."
    rmsg += "\n    - 对方目前段位：" + opponent_status
    rmsg += "\n    - 您目前段位：" + gmUser.getStatus()
    rmsg += "\n    - 持续时间：60 分钟，请在结束前与对方高至少一等级来获胜！\n   - 获胜奖励：" + str(pkinfo.get("Redeem")) + " 积分。"

    return rmsg


async def _pk_status(gmUser: GMUser, rmsg: str, finish_fn) -> str:
    """Handle pk status command."""
    rmsg = "TLoH Bot - ARG 修仙 - P.K. 过程"
    _pking = _safe_read_json(pking_json_path, [])

    pkStr = ""
    otherUserQQ = ""

    for pk_entry in _pking:
        if gmUser.user.id in pk_entry:
            pkStr = pk_entry
            otherUserQQ = pk_entry.replace(f"{gmUser.user.id}", "").replace(":", "")
            break

    if not pkStr:
        return rmsg + "    - 没有参加 P.K，请参加一次 P.K 再来查看。"

    otherUser = GMUser(uic.User(otherUserQQ))
    rmsg += "\n您的段位：" + gmUser.getStatus()
    rmsg += "\n对方段位：" + otherUser.getStatus()

    # Compare rankings
    try:
        user_idx = STATUSES.index(gmUser.status)
        other_idx = STATUSES.index(otherUser.status)
    except ValueError:
        return rmsg + "\n    - 段位数据异常。"

    if user_idx == other_idx:
        rmsg += "\n您和对方的段位持平。"
        if otherUser.level == gmUser.level:
            rmsg += "\n您和对方的层持平。"
        else:
            diff = abs(otherUser.level - gmUser.level)
            if otherUser.level > gmUser.level:
                rmsg += f"\n对方比您高 {diff} 个层。"
            else:
                rmsg += f"\n您比对方高 {diff} 个层。"
    elif other_idx > user_idx:
        rmsg += f"\n对方比您高 {other_idx - user_idx} 个段位。"
    else:
        rmsg += f"\n您比对方高 {user_idx - other_idx} 个段位。"

    # Check timeout and resolve
    _pki = _safe_read_json(pk_info_path, [])
    users_in_pk = pkStr.split(":")
    pki = None
    for entry in _pki:
        if entry.get("Users") == users_in_pk:
            pki = entry
            break

    if pki:
        try:
            beginTime = datetime.datetime.strptime(pki.get("StartTime", ""), TIMEDATESTR)
            if (datetime.datetime.now() - beginTime).seconds >= 60 * 60:
                rmsg += "\n    - 比赛时间到！"
                # Determine winner
                who_best = other_idx > user_idx  # higher index wins
                winner = otherUser if who_best else gmUser
                loser = gmUser if who_best else otherUser
                redeem = random.randint(1000, 9999)
                rmsg += f"\n    - {winner.user.id} 获胜！"
                rmsg += f"\n    - 获得 {redeem} Rating & 积分!"
                winner.upRating(redeem)
                winner.user.score += redeem
                winner.user.save()
                winner.save()

                # Remove pk entry
                try:
                    idx = _pki.index(pki)
                    del _pki[idx]
                    _safe_write_json(pk_info_path, _pki)
                except (ValueError, KeyError):
                    pass
        except (ValueError, TypeError) as e:
            _error(f"Error parsing PK start time: {e}")

    return rmsg


async def _pk_season(gmUser: GMUser, gmConfig: dict, rmsg: str) -> str:
    """Handle pk season command."""
    rmsg = "TLoH Bot - ARG 修仙 GLOBAL.P.K - 赛季信息"
    rmsg += "\n    - 当前赛季：" + gmConfig.get("Status", "???")
    rmsg += "\n    - 您的 Rating：" + str(gmUser.rating)
    rmsg += "\n    - G L O B A L . P . K . - 开场"
    rmsg += "\n    - 目前正在进行的 PK："

    _pking = _safe_read_json(pking_json_path, [])

    for pk_entry in _pking:
        parts = pk_entry.split(":")
        if len(parts) >= 2:
            rmsg += f"\n        - {parts[0]} 对战 {parts[1]}"

    if not _pking:
        rmsg += "\n        - 赛季未揭幕或没有一个人开始对战。"

    return rmsg


async def _handle_best(gmUser: GMUser, finish_fn) -> None:
    """Handle the 'best' (leaderboard) subcommand."""
    rmsg = "TLoH Bot - ARG 修仙排行榜\n"
    data_path = DATA_PATH / "godmaker"

    if not os.path.exists(data_path):
        await finish_fn(rmsg + "    - 暂无数据可供排名。")

    try:
        user_files = os.listdir(data_path)
    except OSError as e:
        _error(f"Failed to list godmaker directory: {e}")
        await finish_fn(rmsg + "    - 无法读取数据。")

    user_scores = {}
    for filename in user_files:
        if filename.endswith(".gmdata"):
            user_id = filename.split(".")[0]
            try:
                gm_user = GMUser(uic.User(user_id))
                user_scores[gm_user.user.id] = gm_user.rating
            except Exception as e:
                _error(f"Error reading GM data for {user_id}: {e}")
                continue

    sorted_scores = sorted(user_scores.items(), key=lambda item: item[1], reverse=True)[:10]

    if not sorted_scores:
        await finish_fn(rmsg + "    - 暂无数据可供排名。")

    for rank, (user_name, score) in enumerate(sorted_scores, 1):
        rmsg += f"    - 第 {rank} 名：{user_name}，Rating：{score:.2f}\n"

    await finish_fn(rmsg)


# =============================================================================
# Main command handler
# =============================================================================

lcgodmaker_function = on_command("lcgodmaker", priority=10)


@lcgodmaker_function.handle()
async def handle_lcgodmaker(bot: Bot, event: GroupMessageEvent | PrivateMessageEvent,
                             args: Message = CommandArg()):
    """ARG 修仙系统主处理器"""
    user = uic.User(event.get_user_id())
    gmUser = GMUser(user)
    _msg = args.extract_plain_text()
    cargs = _msg.split(" ")
    act = cargs[0] if cargs else ""

    finish_fn = lcgodmaker_function.finish

    # Dispatch to sub-handlers
    if act in ("list", ""):
        await finish_fn(_format_help_message())
    elif act == "begin":
        await _handle_begin(gmUser, finish_fn)
    elif act == "info":
        await _handle_info(gmUser, finish_fn)
    elif act == "break":
        await _handle_break(gmUser, cargs, finish_fn)
    elif act == "pk":
        await _handle_pk(bot, event, gmUser, cargs, finish_fn)
    elif act == "best":
        await _handle_best(gmUser, finish_fn)
    else:
        await finish_fn("TLoH Bot - ARG 修仙系统\n    - 未知指令。")
