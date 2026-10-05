"""
TLoH Bot
phigrosScoringController

Phigros score lookup for QQ groups.

Everything is driven by the single ``pgr`` command; the first argument picks a
subcommand (``pgr bind``, ``pgr me``, ...). Accounts are bound by scanning a
TapTap QR code, after which the sessionToken is kept in ``userdata.db`` so
later lookups need no interaction.

Replies that carry more than a couple of lines are rendered as PNG cards (see
:mod:`.render`) and sent as images; short confirmations and errors stay as text.
Song metadata lives in ``data/info.tsv`` and is reached through :mod:`.songs`.

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

# Relative imports on purpose: this package can be pulled in while
# userInfoController is still initialising (its user.py imports this module),
# and "from plugins.phigrosScoringController import x" would then look up an
# attribute on a half-built package and fail.
from . import render
from .database import LEVEL_NAMES, PhigrosUserdataDatabase, SnapshotSaveResult, make_player_id
from .songs import SongInfo
from plugins.undefiendControllers.defines import send_image_msg
from toolsbot.services import _error

TITLE = "TLoH Bot"

#: Where login QR codes are written before being sent. Gitignored.
QRCODE_DIR = "toolsbot/loginQRCodes"

#: Song searches return at most this many matches.
SEARCH_LIMIT = 10

#: Difficulty keywords accepted by commands that take a level.
LEVEL_KEYWORDS = {"0": 0, "1": 1, "2": 2, "3": 3}
for _index, _name in enumerate(LEVEL_NAMES):
    LEVEL_KEYWORDS[_name] = _index
    LEVEL_KEYWORDS[_name.lower()] = _index

HELP_GROUPS = (
    ("账号", (
        ("pgr bind [global]", "扫码登录并绑定（global 为国际服）"),
        ("pgr unbind [all]", "解绑；all 连历史成绩一起删"),
        ("pgr status", "查看绑定状态"),
    )),
    ("成绩", (
        ("pgr update", "拉取最新云存档"),
        ("pgr me", "查看 B19 与 RKS"),
        ("pgr song <关键词>", "查询自己某首歌的成绩"),
        ("pgr progress", "各难度的通关 / FC / AP 进度"),
        ("pgr history", "RKS 变化曲线"),
    )),
    ("曲目", (
        ("pgr info <关键词>", "曲目信息与定数"),
        ("pgr search <关键词>", "搜索曲目"),
        ("pgr random", "随机抽一首"),
    )),
    ("排行", (
        ("pgr board <关键词> [难度]", "某曲某难度的排行榜"),
    )),
)

#: Shared song metadata; loaded on first use.
SONGS = SongInfo()


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
        """Send a plain text reply."""
        if isinstance(self.evt, PrivateMessageEvent):
            await self.bot.send_private_msg(user_id=int(self.evt.user_id), message=message)
        else:
            await self.bot.send_group_msg(group_id=self.evt.group_id, message=message)

    async def send_image(self, path: str) -> None:
        """Send a rendered card."""
        await send_image_msg(self.bot, self.evt, path)

    async def GenerateSendQRCode(self, qrcode_url: str) -> None:
        """Render the TapTap login URL as a QR image and send it."""
        os.makedirs(QRCODE_DIR, exist_ok=True)

        path = os.path.join(QRCODE_DIR, f"{random.randint(100000000, 999999999)}.png")
        qrcode.make(qrcode_url).save(path)

        await self.send_image(path)

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
            return f"{TITLE} - Phigros 查分\n    - 您尚未绑定账号，请先发送 pgr bind。"
        if not self.Token():
            return f"{TITLE} - Phigros 查分\n    - 登录已失效，请重新发送 pgr bind。"
        return None

    # -------------------------------------------------------------------------
    # PhigrosScoreLibrary helpers
    # -------------------------------------------------------------------------

    async def FetchSave(self) -> tuple[psl.SaveData, bytes, psl.Summary]:
        """Download and parse the bound account's cloud save.

        Returns the parsed save, the raw zip (needed for the content hash and
        for archival) and the summary.

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
                "返回的存档不属于当前绑定的账号，请重新发送 pgr bind 登录。"
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
            await self.send_msg(f"{TITLE} - Phigros 查分\n    - 登录失败：{error}")
            return None

        # Remember the LeanCloud account id so the same game account cannot be
        # bound twice; it is also what identifies the player in the API.
        player_id = self.db.BindPlayer(
            self.evt.get_user_id(), region=region.value, open_id=result.user_id
        )
        if result.user_id:
            self.db.SetOpenId(player_id, result.user_id)

        self.db.SaveSessionToken(player_id, result.session_token)

        nickname = result.nickname or await self.FetchNickname()
        if nickname:
            self.db.SetNickname(player_id, nickname)

        return result.session_token

    # -------------------------------------------------------------------------
    # Routing
    # -------------------------------------------------------------------------

    async def Dispatch(self, args: str) -> str | None:
        """Route the subcommand. Returns text to send, or None when done."""
        parts = args.split()
        sub = parts[0].lower() if parts else "help"
        rest = " ".join(parts[1:])

        routes = {
            "help": self.CmdHelp, "帮助": self.CmdHelp, "菜单": self.CmdHelp,
            "bind": self.CmdBind, "绑定": self.CmdBind, "登录": self.CmdBind,
            "unbind": self.CmdUnbind, "解绑": self.CmdUnbind,
            "status": self.CmdStatus, "状态": self.CmdStatus,
            "update": self.CmdUpdate, "更新": self.CmdUpdate, "同步": self.CmdUpdate,
            "me": self.CmdMe, "b19": self.CmdMe, "查分": self.CmdMe,
            "song": self.CmdSong, "单曲": self.CmdSong,
            "board": self.CmdBoard, "排行": self.CmdBoard, "排行榜": self.CmdBoard,
            "progress": self.CmdProgress, "进度": self.CmdProgress,
            "history": self.CmdHistory, "历史": self.CmdHistory,
            "info": self.CmdInfo, "曲目": self.CmdInfo, "曲目信息": self.CmdInfo,
            "search": self.CmdSearch, "搜索": self.CmdSearch,
            "random": self.CmdRandom, "随机": self.CmdRandom,
        }

        handler = routes.get(sub)
        if handler is None:
            return f"{TITLE} - Phigros 查分\n    - 未知指令 {sub}，发送 pgr help 查看用法。"

        return await handler(rest)

    # -------------------------------------------------------------------------
    # Account commands
    # -------------------------------------------------------------------------

    async def CmdHelp(self, rest: str) -> None:
        await self.send_image(render.render_help(f"{TITLE} - Phigros 查分", HELP_GROUPS))
        return None

    async def CmdBind(self, rest: str) -> str | None:
        """Bind the account, or report why it cannot be bound yet."""
        region = (
            psl.TapTapRegion.GLOBAL
            if rest.strip().lower() in ("global", "gb", "国际服")
            else psl.TapTapRegion.CHINA
        )

        player = self.Player()
        if player is not None:
            if self.Token():
                return f"{TITLE} - Phigros 查分\n    - 您已经绑定过了。如需更换账号，请先发送 pgr unbind。"
            if player.get("region") != region.value:
                # Re-binding under a different region would leave stale data
                # under the old region, so ask for an explicit unbind first.
                return f"{TITLE} - Phigros 查分\n    - 您之前绑定的是其它区服，请先发送 pgr unbind all。"

        await self.send_msg(f"{TITLE} - Phigros 查分\n    - 请使用 TapTap App 扫描下方二维码完成登录。")

        token = await self.Login()
        if not token:
            return None

        nickname = (self.db.GetPlayer(self.player_id) or {}).get("nickname")
        return (
            f"{TITLE} - Phigros 查分\n    - 登录成功，欢迎回来 {nickname}。"
            if nickname
            else f"{TITLE} - Phigros 查分\n    - 登录成功。"
        )

    async def CmdUnbind(self, rest: str) -> str:
        """Unbind the account. 'all' also erases every stored snapshot."""
        if self.Player() is None:
            return f"{TITLE} - Phigros 查分\n    - 您尚未绑定任何账号。"

        if rest.strip().lower() in ("all", "全部", "彻底"):
            self.db.DeletePlayer(self.player_id)
            return f"{TITLE} - Phigros 查分\n    - 已解绑并删除全部数据，包括历史成绩。"

        # Without a credential the account is unusable, but keeping the
        # snapshots means a later re-bind inherits the history.
        self.db.DeleteSessionToken(self.player_id)
        return (
            f"{TITLE} - Phigros 查分\n"
            "    - 已解绑。历史成绩仍保留，重新绑定后可继续查看；\n"
            "    - 如需彻底删除请发送 pgr unbind all。"
        )

    async def CmdStatus(self, rest: str) -> str | None:
        player = self.Player()
        if player is None:
            return f"{TITLE} - Phigros 查分\n    - 您尚未绑定账号。发送 pgr bind 开始。"

        snapshots = self.db.ListSnapshots(self.player_id, limit=1)
        await self.send_image(
            render.render_status(
                nickname=player.get("nickname") or "未知玩家",
                region=player.get("region") or "china",
                bound_at=str(player.get("created_at") or "")[:19],
                token_ok=bool(self.Token()),
                latest=snapshots[0] if snapshots else None,
                player_id=player.get("id", ""),
            )
        )
        return None

    # -------------------------------------------------------------------------
    # Score commands
    # -------------------------------------------------------------------------

    async def CmdUpdate(self, rest: str) -> str:
        """Pull the cloud save and store a new snapshot."""
        error = self.RequireBinding()
        if error:
            return error

        try:
            save, blob, summary = await self.FetchSave()
        except psl.PhigrosError as error:
            return f"{TITLE} - Phigros 查分\n    - 获取存档失败：{error}"

        result: SnapshotSaveResult = self.db.SaveSnapshot(
            self.player_id, save, blob, summary
        )

        if not result.ok:
            return f"{TITLE} - Phigros 查分\n    - 存档入库失败，请稍后重试。"

        if not result.is_new:
            return f"{TITLE} - Phigros 查分\n    - 成绩没有变化，无需同步。"

        # Show the RKS the game uploaded rather than recomputing it from the
        # records; the two can disagree (see Database.GetReportedRks).
        rks = self.db.GetReportedRks(self.player_id)
        lines = [
            f"    - 同步完成，本次写入 {result.record_count} 条成绩。",
            f"    - RKS：{rks:.4f}" if rks is not None else "    - RKS：暂无",
        ]

        if result.missing_songs:
            # The bundled chart table lags behind game updates; the songs are
            # stored but contribute nothing to RKS until the table catches up.
            lines.append(f"    - 其中 {len(result.missing_songs)} 首曲目不在定数表中，暂不计入 RKS。")

        return f"{TITLE} - Phigros 查分\n" + "\n".join(lines)

    async def CmdMe(self, rest: str) -> str | None:
        """Show the stored B19 as an image."""
        error = self.RequireBinding()
        if error:
            return error

        snapshot = self.db.GetLatestSnapshot(self.player_id)
        if snapshot is None:
            return f"{TITLE} - Phigros 查分\n    - 还没有成绩数据，请先发送 pgr update。"

        best19 = self.db.ComputeBest19(self.player_id)
        nickname = (self.Player() or {}).get("nickname") or "未知玩家"

        # The sheet shows display names, not raw ids, so resolve them here
        # rather than making the renderer depend on the metadata table.
        entries = self.db.GetBest19List(self.player_id)
        for entry in entries:
            entry["title"] = SONGS.title(entry.get("song_id", ""))

        await self.send_image(
            render.render_b19(
                nickname=nickname,
                region=self.Region(),
                captured_at=str(snapshot.get("captured_at") or ""),
                rks=self.db.GetReportedRks(self.player_id),
                phi=best19.get("phi"),
                best=entries,
                progress=self.db.GetProgress(self.player_id),
            )
        )
        return None

    async def CmdSong(self, rest: str) -> str | None:
        """Show the player's best score for one song."""
        error = self.RequireBinding()
        if error:
            return error

        keyword = rest.strip()
        if not keyword:
            return f"{TITLE} - Phigros 查分\n    - 用法：pgr song <曲名关键词>"

        song_id, matches = SONGS.resolve(keyword)
        if song_id is None:
            if not matches:
                return f"{TITLE} - Phigros 查分\n    - 没有找到包含「{keyword}」的曲目。"
            await self.send_image(render.render_songs(matches, f"匹配「{keyword}」，请输入更完整的关键词"))
            return None

        records = [
            record
            for level in range(4)
            if (record := self.db.GetSongBest(self.player_id, song_id, level)) is not None
        ]
        if not records:
            return f"{TITLE} - Phigros 查分\n    - 您还没有 {song_id} 的成绩。"

        await self.send_image(
            render.render_song(
                nickname=(self.Player() or {}).get("nickname") or "未知玩家",
                song_id=song_id,
                records=records,
                difficulty=SONGS.constants(song_id),
            )
        )
        return None

    async def CmdBoard(self, rest: str) -> str | None:
        """Show the leaderboard for one song and difficulty."""
        words = rest.split()
        if not words:
            return f"{TITLE} - Phigros 查分\n    - 用法：pgr board <曲名关键词> [难度]"

        level = 2  # IN by default
        if len(words) > 1 and words[-1] in LEVEL_KEYWORDS:
            level = LEVEL_KEYWORDS[words[-1]]
            words = words[:-1]

        keyword = " ".join(words)
        song_id, matches = SONGS.resolve(keyword)
        if song_id is None:
            if not matches:
                return f"{TITLE} - Phigros 查分\n    - 没有找到包含「{keyword}」的曲目。"
            await self.send_image(render.render_songs(matches, f"匹配「{keyword}」，请输入更完整的关键词"))
            return None

        rows = self.db.GetSongLeaderboard(song_id, level, limit=20)
        if not rows:
            return f"{TITLE} - Phigros 查分\n    - {song_id} [{LEVEL_NAMES[level]}] 还没有人打过。"

        await self.send_image(render.render_board(song_id, level, rows))
        return None

    async def CmdProgress(self, rest: str) -> str | None:
        """Show clear / FC / AP counts per difficulty."""
        error = self.RequireBinding()
        if error:
            return error

        if self.db.GetLatestSnapshot(self.player_id) is None:
            return f"{TITLE} - Phigros 查分\n    - 还没有成绩数据，请先发送 pgr update。"

        await self.send_image(
            render.render_progress(
                self.db.GetProgress(self.player_id),
                (self.Player() or {}).get("nickname") or "未知玩家",
            )
        )
        return None

    async def CmdHistory(self, rest: str) -> str | None:
        """Show how the stored RKS changed over time."""
        error = self.RequireBinding()
        if error:
            return error

        points = self.db.GetRksHistory(self.player_id, limit=30)
        if not points:
            return f"{TITLE} - Phigros 查分\n    - 还没有历史记录，请先发送 pgr update。"

        await self.send_image(render.render_history(points))
        return None

    # -------------------------------------------------------------------------
    # Song commands
    # -------------------------------------------------------------------------

    async def CmdInfo(self, rest: str) -> str | None:
        """Show metadata and chart constants for one song."""
        keyword = rest.strip()
        if not keyword:
            return f"{TITLE} - Phigros 查分\n    - 用法：pgr info <曲名关键词>"

        song_id, matches = SONGS.resolve(keyword)
        if song_id is None:
            if not matches:
                return f"{TITLE} - Phigros 查分\n    - 没有找到包含「{keyword}」的曲目。"
            await self.send_image(render.render_songs(matches, f"匹配「{keyword}」，请输入更完整的关键词"))
            return None

        await self.send_image(
            render.render_info(song_id, SONGS.fields(song_id), SONGS.constants(song_id))
        )
        return None

    async def CmdSearch(self, rest: str) -> str | None:
        """List songs matching a keyword."""
        keyword = rest.strip()
        if not keyword:
            return f"{TITLE} - Phigros 查分\n    - 用法：pgr search <曲名关键词>"

        matches = SONGS.search(keyword, limit=30)
        await self.send_image(render.render_songs(matches, f"搜索「{keyword}」，共 {len(matches)} 首"))
        return None

    async def CmdRandom(self, rest: str) -> str | None:
        """Pick a random song and show its constants."""
        song_id = SONGS.random_id()
        await self.send_image(
            render.render_info(song_id, SONGS.fields(song_id), SONGS.constants(song_id))
        )
        return None


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
