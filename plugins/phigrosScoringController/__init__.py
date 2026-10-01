"""
TLoH Bot
phigrosScoringController

Phigros score lookup for QQ groups.

Everything is driven by the single ``pgr`` command; the first argument picks a
subcommand (``pgr bind``, ``pgr update``, ...). Accounts are bound by scanning a
TapTap QR code, after which the sessionToken is kept in ``userdata.db`` so later
lookups need no interaction.

Data lives in the ``pgr_*`` tables managed by :mod:`.database`; this module only
deals with chat I/O, the PhigrosScoreLibrary calls and user-facing wording.

@author: BL-BlueLighting
"""

import asyncio
import os
import random

import qrcode
from nonebot import on_command
from nonebot.adapters import Message
from nonebot.adapters.onebot.v11 import Bot as v11bot
from nonebot.adapters.onebot.v11 import GroupMessageEvent, PrivateMessageEvent
from nonebot.internal.matcher import Matcher
from nonebot.params import CommandArg

import PhigrosScoreLibrary as psl
from plugins.phigrosScoringController.database import (
    LEVEL_NAMES,
    PhigrosUserdataDatabase,
    SnapshotSaveResult,
    make_player_id,
)
from plugins.undefiendControllers.defines import send_fake_forward_msg, send_image_msg
from toolsbot.services import _error

TITLE = "TLoH Bot"

#: Where login QR codes are written before being sent. Gitignored.
QRCODE_DIR = "toolsbot/loginQRCodes"

#: Song searches return at most this many matches.
SEARCH_LIMIT = 10

#: Replies longer than this many lines are sent as a merged forward message
#: instead of dumping a wall of text into the group.
FORWARD_LINE_THRESHOLD = 6

HELP_TEXT = """TLoH Bot - Phigros 查分
    - ^pgr bind [global] - 扫码登录并绑定账号（global 为国际服）
    - ^pgr unbind - 解绑，保留历史成绩
    - ^pgr unbind all - 解绑并删除全部数据
    - ^pgr status - 查看绑定状态
    - ^pgr update - 拉取最新存档
    - ^pgr me - 查看 B19 与 RKS
    - ^pgr song <关键词> - 查询自己某首歌的成绩
    - ^pgr board <关键词> - 查询某首歌的排行榜
    - ^pgr history - 查看 RKS 变化
"""


class PhigrosCommand:
    """Handles one invocation of the ``pgr`` command."""

    def __init__(
        self,
        bot: v11bot,
        event: GroupMessageEvent | PrivateMessageEvent,
        command: type[Matcher],
    ):
        self.cmd = command
        self.bot = bot
        self.evt = event
        self.db = PhigrosUserdataDatabase()

    # -------------------------------------------------------------------------
    # Chat I/O
    # -------------------------------------------------------------------------

    async def send_msg(self, message: str) -> None:
        """Reply in the same context the command came from.

        Anything longer than a few lines is delivered as a merged forward, so
        a B19 listing does not flood the group with a wall of text.
        """
        if message.count("\n") + 1 > FORWARD_LINE_THRESHOLD:
            # send_fake_forward_msg returns -1 and sends nothing when the
            # forward API is unavailable, so fall through to a plain message
            # rather than dropping the reply.
            if await send_fake_forward_msg(self.bot, self.evt, message) == 0:
                return

        if isinstance(self.evt, PrivateMessageEvent):
            await self.bot.send_private_msg(user_id=int(self.evt.user_id), message=message)
        else:
            await self.bot.send_group_msg(group_id=self.evt.group_id, message=message)

    async def GenerateSendQRCode(self, qrcode_url: str) -> None:
        """Render the TapTap login URL as a QR image and send it."""
        os.makedirs(QRCODE_DIR, exist_ok=True)

        name = f"{random.randint(100000000, 999999999)}.png"
        path = os.path.join(QRCODE_DIR, name)
        qrcode.make(qrcode_url).save(path)

        await send_image_msg(self.bot, self.evt, path)

    # -------------------------------------------------------------------------
    # Account helpers
    # -------------------------------------------------------------------------

    @property
    def player_id(self) -> str:
        """Player id derived from the sender's QQ number."""
        return make_player_id(self.evt.get_user_id())

    def Player(self) -> dict | None:
        """Player row, or None when the sender has never bound."""
        return self.db.GetPlayerByPlatformId(self.evt.get_user_id())

    def Token(self) -> str | None:
        """Stored sessionToken of the sender, or None."""
        return self.db.GetSessionToken(self.player_id)

    def Region(self) -> str:
        """Region of the sender's binding; defaults to China."""
        player = self.Player()
        return (player or {}).get("region") or "china"

    def LeanCloudApp(self) -> psl.LeanCloudApp:
        """LeanCloud app matching the sender's region."""
        return psl.LeanCloudApp.for_region(psl.TapTapRegion.parse(self.Region()))

    def RequireBinding(self) -> str | None:
        """Return an error message when the sender is not usable, else None."""
        if self.Player() is None:
            return "TLoH Bot - Phigros 查分\n    - 您尚未绑定账号，请先发送 pgr bind。"
        if not self.Token():
            return "TLoH Bot - Phigros 查分\n    - 您的登录已失效，请重新发送 pgr bind。"
        return None

    # -------------------------------------------------------------------------
    # PhigrosScoreLibrary helpers
    # -------------------------------------------------------------------------

    async def FetchSave(self) -> tuple[psl.SaveData, bytes, psl.Summary]:
        """Download and parse the bound account's cloud save.

        Returns the parsed save, the raw zip (needed for the content hash and
        for archival) and the summary. Uses LeanCloudClient directly rather
        than the facade because the facade does not expose the raw bytes.

        Raises ``psl.PhigrosApiError`` when the stored token is no longer valid.
        """
        token = self.Token()
        api = psl.LeanCloudClient(app=self.LeanCloudApp())

        # `classes/_GameSave` is world-readable on LeanCloud: an expired or
        # bogus session still returns the first row of the table, i.e. some
        # stranger's save. `users/me` does enforce authentication, so it is
        # used to prove the token is still alive before trusting anything.
        await asyncio.to_thread(api.get_nickname, token)

        record = await asyncio.to_thread(api.get_save_record, token)

        # Belt and braces: when the LeanCloud account id is known, make sure
        # the save really belongs to it.
        expected = (self.Player() or {}).get("open_id")
        if expected and record.user_id and record.user_id != expected:
            raise psl.PhigrosApiError(
                "TLoH Bot - Phigros 查分\n    - 您的 Token 过期，请 ^pgr unbind 后 ^pgr bind 再登录。"
            )

        blob = await asyncio.to_thread(api.download_save, record.url)

        save = await asyncio.to_thread(psl.parse_save, blob)
        summary = await asyncio.to_thread(psl.parse_summary, record.summary)

        # The binary payload carries no cloud metadata, so attach it here.
        summary.object_id = record.object_id
        summary.user_id = record.user_id
        summary.file_id = record.file_id
        summary.url = record.url
        summary.updated_at = record.updated_at

        return save, blob, summary

    async def FetchNickname(self) -> str | None:
        """In-game name of the bound account, or None if it cannot be read."""
        try:
            api = psl.LeanCloudClient(app=self.LeanCloudApp())
            return await asyncio.to_thread(api.get_nickname, self.Token())
        except psl.PhigrosError as error:
            _error(f"[phigros] nickname lookup failed: {error}")
            return None

    async def Login(self) -> str | None:
        """Run the QR login flow and return a sessionToken, or None on failure."""
        region = psl.TapTapRegion.parse(self.Region())
        login = psl.AsyncPhigrosLogin(psl.PhigrosLogin(region))

        async def on_qr(qr):
            await self.GenerateSendQRCode(qr.url)

        try:
            result = await login.login(on_qr)
        except psl.PhigrosLoginError as error:
            await self.send_msg(f"TLoH Bot - Phigros 查分\n    - 登录失败：{error}")
            return None

        # Remember the LeanCloud account id so the same game account cannot be
        # bound twice; it is also what identifies the player in the API.
        player_id = self.db.BindPlayer(self.evt.get_user_id(), region=region.value)

        # The insert is swallowed by run_sql when it fails, so confirm the row
        # really exists before writing anything that references it.
        if self.db.GetPlayer(player_id) is None:
            _error(f"[phigros] failed to bind {player_id}")
            await self.send_msg("TLoH Bot - Phigros 查分\n    - 账号绑定失败，请稍后重试。")
            return None

        if result.user_id:
            self.db.SetOpenId(player_id, result.user_id)

        self.db.SaveSessionToken(player_id, result.session_token)

        nickname = result.nickname or await self.FetchNickname()
        if nickname:
            self.db.SetNickname(player_id, nickname)

        return result.session_token

    # -------------------------------------------------------------------------
    # Subcommands
    # -------------------------------------------------------------------------

    async def Dispatch(self, args: str) -> str | None:
        """Route the subcommand. Returns the reply text, or None if already sent."""
        parts = args.split()
        sub = parts[0].lower() if parts else "help"
        rest = parts[1:]

        routes = {
            "help": self.CmdHelp, "帮助": self.CmdHelp,
            "bind": self.CmdBind, "绑定": self.CmdBind, "登录": self.CmdBind,
            "unbind": self.CmdUnbind, "解绑": self.CmdUnbind,
            "status": self.CmdStatus, "状态": self.CmdStatus,
            "update": self.CmdUpdate, "更新": self.CmdUpdate, "同步": self.CmdUpdate,
            "me": self.CmdMe, "查分": self.CmdMe, "b19": self.CmdMe,
            "song": self.CmdSong, "单曲": self.CmdSong,
            "board": self.CmdBoard, "排行": self.CmdBoard,
            "history": self.CmdHistory, "历史": self.CmdHistory,
        }

        handler = routes.get(sub)
        if handler is None:
            return f"TLoH Bot - Phigros 查分\n    - 未知指令 {sub}。\n{HELP_TEXT}"

        return await handler(" ".join(rest))

    async def CmdHelp(self, rest: str) -> str:
        return HELP_TEXT

    async def CmdBind(self, rest: str) -> str | None:
        """Bind the account, or replace the binding when one already exists."""
        region = psl.TapTapRegion.GLOBAL if rest.strip() in ("global", "gb", "国际服") else psl.TapTapRegion.CHINA

        player = self.Player()
        if player is not None:
            if self.Token():
                return "TLoH Bot - Phigros 查分\n    - 您已经绑定过了。如需更换账号，请先发送 pgr unbind。"
            if player.get("region") != region.value:
                # Re-binding under a different region would keep stale data
                # under the old region, so ask for an explicit unbind first.
                return "TLoH Bot - Phigros 查分\n    - 您之前绑定的是其它区服，请先发送 pgr unbind all 后再绑定。"

        await self.send_msg("请使用 TapTap App 扫描下方的二维码完成登录。")

        token = await self.Login()
        if not token:
            return None

        nickname = (self.db.GetPlayer(self.player_id) or {}).get("nickname")
        return f"登录成功，欢迎回来 {nickname}。" if nickname else "登录成功。"

    async def CmdUnbind(self, rest: str) -> str:
        """Unbind the account. 'all' also erases every stored snapshot."""
        player = self.Player()
        if player is None:
            return "TLoH Bot - Phigros 查分\n    - 您尚未绑定任何账号。"

        if rest.strip().lower() in ("all", "全部", "彻底"):
            self.db.DeletePlayer(self.player_id)
            return "TLoH Bot - Phigros 查分\n    - 已解绑并删除全部数据，包括历史成绩。"

        # Without a credential the account is unusable, but keeping the
        # snapshots means a later re-bind inherits the history.
        self.db.DeleteSessionToken(self.player_id)
        return "TLoH Bot - Phigros 查分\n    - 已解绑。历史成绩仍保留，重新绑定后可以继续查看；如需彻底删除请发送 ^pgr unbind all。"

    async def CmdStatus(self, rest: str) -> str:
        player = self.Player()
        if player is None:
            return "TLoH Bot - Phigros 查分\n    - 您尚未绑定账号。发送 ^pgr bind 开始。"

        snapshots = self.db.ListSnapshots(self.player_id, limit=1)
        lines = [
            f"    - 账号：{player.get('nickname') or '未知'}",
            f"    - 区服：{'国际服' if player.get('region') == 'global' else '国服'}",
            f"    - 登录状态：{'有效' if self.Token() else '已失效，请重新 ^pgr bind'}",
            f"    - 绑定时间：{player.get('created_at')}",
        ]

        if snapshots:
            latest = snapshots[0]
            lines.append(f"    - 最近同步：{latest.get('captured_at')}")
            lines.append(f"    - RKS：{latest.get('ranking_score'):.4f}")
        else:
            lines.append("    - 尚未同步过成绩，发送 ^pgr update 拉取。")

        return "TLoH Bot - Phigros 查分\n" + "\n".join(lines)

    async def CmdUpdate(self, rest: str) -> str | None:
        """Pull the cloud save and store a new snapshot."""
        error = self.RequireBinding()
        if error:
            return error

        try:
            save, blob, summary = await self.FetchSave()
        except psl.PhigrosError as error:
            return f"TLoH Bot - Phigros 查分\n    - 获取存档失败：{error}"

        result: SnapshotSaveResult = self.db.SaveSnapshot(
            self.player_id, save, blob, summary
        )

        if not result.ok:
            return "TLoH Bot - Phigros 查分\n    - 存档入库失败，请稍后重试。"

        if not result.is_new:
            return "TLoH Bot - Phigros 查分\n    - 成绩没有变化，无需同步。"

        best19 = self.db.ComputeBest19(self.player_id)
        lines = [
            f"    - 同步完成，本次写入 {result.record_count} 条成绩。",
            f"    - RKS：{best19['rks']:.4f}",
        ]

        if result.missing_songs:
            # The bundled chart table lags behind game updates; the songs are
            # stored but contribute nothing to RKS until the table catches up.
            lines.append(f"    - 其中 {len(result.missing_songs)} 首曲目不在定数表中，暂不计入 RKS。")

        return "TLoH Bot - Phigros 查分\n" + "\n".join(lines)

    async def CmdMe(self, rest: str) -> str:
        """Show the stored B19."""
        error = self.RequireBinding()
        if error:
            return error

        if self.db.GetLatestSnapshot(self.player_id) is None:
            return "TLoH Bot - Phigros 查分\n    - 还没有成绩数据，请先发送 ^pgr update。"

        best19 = self.db.ComputeBest19(self.player_id)
        progress = self.db.GetProgress(self.player_id)

        lines = [f"    - RKS：{best19['rks']:.4f}"]

        if best19["phi"]:
            phi = best19["phi"]
            lines.append(
                f"    - φ：{phi['song_id']} [{phi['level_name']}] 定数 {phi['difficulty']}"
            )
        else:
            lines.append("    - φ：暂无满分成绩")

        lines.append("")
        lines.append("    - B19：")
        for index, entry in enumerate(self.db.GetBest19List(self.player_id), start=1):
            rks = entry["rks"] if entry["rks"] is not None else 0.0
            lines.append(
                f"    - {index:>2}. {entry['song_id']} [{entry['level_name']}] "
                f"    - {rks:.4f}  {entry['accuracy']:.2f}%"
            )

        if progress:
            lines.append("")
            lines.append("    - 进度：")
            for row in progress:
                lines.append(
                    f"    - {row['level_name']} 已游玩 {row['played']}  "
                    f"    - FC {row['full_combo']}  AP {row['all_perfect']}"
                )

        return "TLoH Bot - Phigros 查分\n" + "\n".join(lines)

    async def CmdSong(self, rest: str) -> str:
        """Show the player's best score for songs matching a keyword."""
        error = self.RequireBinding()
        if error:
            return error

        keyword = rest.strip()
        if not keyword:
            return "TLoH Bot - Phigros 查分\n    - 用法：pgr song <曲名关键词>"

        matches = self.db.FindSongs(keyword, limit=SEARCH_LIMIT)
        if not matches:
            return f"TLoH Bot - Phigros 查分\n    - 没有找到包含「{keyword}」的曲目。"

        if len(matches) > 1 and keyword not in matches:
            lines = [f"    - 匹配到 {len(matches)} 首曲目，请输入更完整的关键词："]
            lines.extend(f"  {song_id}" for song_id in matches)
            return "\n".join(lines)

        lines = []
        for song_id in matches[:1]:
            lines.append(song_id)
            for level, level_name in enumerate(LEVEL_NAMES):
                record = self.db.GetSongBest(self.player_id, song_id, level)
                if record is None:
                    continue

                rks = record["rks"] if record["rks"] is not None else 0.0
                marks = "AP" if record["score"] == 1000000 else ("FC" if record["full_combo"] else "")
                lines.append(
                    f"    -   {level_name}  定数 {record['difficulty']}  "
                    f"    - {record['score']}  {record['accuracy']:.2f}%  {rks:.4f} {marks}"
                )

        return "TLoH Bot - Phigros 查分\n" + "\n".join(lines)

    async def CmdBoard(self, rest: str) -> str:
        """Show the leaderboard for songs matching a keyword."""
        keyword = rest.strip()
        if not keyword:
            return "TLoH Bot - Phigros 查分\n    - 用法：^pgr board <曲名关键词> [难度]"

        level = 2
        words = keyword.split()
        if len(words) > 1 and words[-1].upper() in LEVEL_NAMES:
            level = LEVEL_NAMES.index(words[-1].upper())
            keyword = " ".join(words[:-1])

        matches = self.db.FindSongs(keyword, limit=1)
        if not matches:
            return f"TLoH Bot - Phigros 查分\n    - 没有找到包含「{keyword}」的曲目。"

        song_id = matches[0]
        rows = self.db.GetSongLeaderboard(song_id, level, limit=20)
        if not rows:
            return f"TLoH Bot - Phigros 查分\n    - {song_id} [{LEVEL_NAMES[level]}] 还没有人打过。"

        lines = [f"    - {song_id} [{LEVEL_NAMES[level]}] 排行榜"]
        for index, row in enumerate(rows, start=1):
            name = row["nickname"] or row["player_id"]
            rks = row["rks"] if row["rks"] is not None else 0.0
            marks = "AP" if row["score"] == 1000000 else ("FC" if row["full_combo"] else "")
            lines.append(
                f"    - {index:>2}. {name}  {row['score']}  {row['accuracy']:.2f}%  {rks:.4f} {marks}"
            )

        return "TLoH Bot - Phigros 查分\n" + "\n".join(lines)

    async def CmdHistory(self, rest: str) -> str:
        """Show how the stored RKS changed over time."""
        error = self.RequireBinding()
        if error:
            return error

        history = self.db.GetRksHistory(self.player_id, limit=30)
        if not history:
            return "TLoH Bot - Phigros 查分\n    - 还没有历史记录，请先发送 ^pgr update。"

        lines = ["    - RKS 变化："]
        previous = None
        for point in history:
            delta = ""
            if previous is not None:
                change = point["rks"] - previous
                delta = f"   -   ({change:+.4f})" if abs(change) > 1e-9 else ""
            lines.append(f"    -   {point['captured_at'][:10]}  {point['rks']:.4f}{delta}")
            previous = point["rks"]

        return "TLoH Bot - Phigros 查分\n" + "\n".join(lines)


pgr_cmd = on_command("pgr", priority=10)


@pgr_cmd.handle()
async def _(
    bot: v11bot,
    event: GroupMessageEvent | PrivateMessageEvent,
    args: Message = CommandArg(),
):
    command = PhigrosCommand(bot, event, pgr_cmd)
    reply = await command.Dispatch(args.extract_plain_text().strip())

    if reply:
        await command.send_msg(reply)

    await pgr_cmd.finish()
