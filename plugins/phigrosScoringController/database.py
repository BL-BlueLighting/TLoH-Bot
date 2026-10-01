"""
Phigros score persistence layer.

Stores player bindings, save snapshots and per-song records in the SQLite file
shared with userInfoController. All table names carry a ``pgr_`` prefix so they
cannot collide with tables such as ``users`` that live in the same database.

Design notes
------------
* Every id is TEXT. A player id is ``"{platform}:{platform_id}"`` (``qq:123456``);
  a snapshot id is derived from content, ``"{player_id}:{sha256[:16]}"``, so
  re-inserting the same save collides on the primary key.
* Both the raw zip and the parsed records are stored: the zip keeps the original
  data replayable, the records make B19 answerable with plain SQL.
* Chart constants are stored per snapshot. The difficulty table changes between
  game versions, so without it historical RKS would silently drift.
* Single-song RKS is a STORED generated column of ``difficulty * ((acc-55)/45)^2``,
  so it can never disagree with its own inputs and can be indexed for B19.

Constraints imposed by ``userInfoController.Database.run_sql``
-------------------------------------------------------------
It opens a fresh sqlite3 connection per call and commits each statement
separately, which means:

* ``PRAGMA foreign_keys`` is connection-scoped and therefore never in effect, so
  foreign keys are declarative only and ``ON DELETE CASCADE`` never fires.
  Deletion is handled explicitly by :meth:`PhigrosUserdataDatabase.DeletePlayer`.
* A snapshot and its records are written by separate calls and are not one
  transaction. Every write is therefore idempotent (``INSERT OR IGNORE`` /
  ``INSERT OR REPLACE``) so a retry repairs a partial write.
* Errors are swallowed and returned as ``[]``, indistinguishable from an empty
  result, so writes are verified by reading back.

Usage::

    db = PhigrosUserdataDatabase()
    player_id = db.BindPlayer("123456789")
    db.SaveSessionToken(player_id, token)

    result = db.SaveSnapshot(player_id, save, blob, summary)
    print(db.ComputeBest19(player_id)["rks"])
"""

from __future__ import annotations

import datetime
import hashlib
import json
from dataclasses import dataclass, field
from typing import Any, Iterable, Optional, Sequence

import PhigrosScoreLibrary as psl

from plugins.userInfoController import Database
from toolsbot.services import _error, _info

#: Valid values for the ``region`` column.
REGIONS = ("china", "global")

#: Difficulty index -> display name.
LEVEL_NAMES = ("EZ", "HD", "IN", "AT")

#: Rows per INSERT when writing song records. SQLite allows 32766 bound
#: parameters by default and each row uses 7, so 3000 rows (~21k) leaves room.
_RECORD_BATCH = 3000

#: Columns added after the first release, as (table, column, definition).
#: ``CREATE TABLE IF NOT EXISTS`` leaves existing tables untouched, so a
#: database created by an older version has to be altered explicitly. Each
#: entry is checked at startup and added when missing.
_MIGRATIONS: tuple[tuple[str, str, str], ...] = (
    ("pgr_players", "nickname", "TEXT"),
)


def utcnow() -> str:
    """Current UTC time as an ISO-8601 string (sorts correctly as text)."""
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def make_player_id(platform_id: str, platform: str = "qq") -> str:
    """Build a player id from a platform user id."""
    return f"{platform}:{platform_id}"


def make_snapshot_id(player_id: str, save_sha256: str) -> str:
    """Build a snapshot id from the player and the save content hash."""
    return f"{player_id}:{save_sha256[:16]}"


# =============================================================================
# Schema
# =============================================================================
#
# Statements are executed one by one: run_sql wraps cursor.execute, which
# accepts a single statement per call.

_TABLE_STATEMENTS: tuple[str, ...] = (
    # ---- players ----
    """
    CREATE TABLE IF NOT EXISTS pgr_players (
        id          TEXT NOT NULL PRIMARY KEY,
        platform    TEXT NOT NULL,
        platform_id TEXT NOT NULL,
        region      TEXT NOT NULL DEFAULT 'china'
                    CHECK (region IN ('china', 'global')),
        open_id     TEXT,
        nickname    TEXT,
        created_at  TEXT NOT NULL,
        updated_at  TEXT NOT NULL,
        UNIQUE (platform, platform_id)
    ) STRICT
    """,
    """
    CREATE UNIQUE INDEX IF NOT EXISTS idx_pgr_players_open_id
        ON pgr_players (region, open_id) WHERE open_id IS NOT NULL
    """,
    # ---- credentials, kept apart so exporting players does not leak tokens ----
    """
    CREATE TABLE IF NOT EXISTS pgr_credentials (
        player_id     TEXT NOT NULL PRIMARY KEY,
        session_token TEXT NOT NULL,
        obtained_at   TEXT NOT NULL,
        expires_at    TEXT
    ) STRICT
    """,
    # ---- save snapshots ----
    """
    CREATE TABLE IF NOT EXISTS pgr_snapshots (
        id                  TEXT NOT NULL PRIMARY KEY,
        player_id           TEXT NOT NULL,

        save_sha256         TEXT NOT NULL,
        save_size           INTEGER NOT NULL,
        save_blob           BLOB NOT NULL,

        save_version        INTEGER NOT NULL,
        game_version        INTEGER NOT NULL,
        challenge_mode_rank INTEGER NOT NULL,
        ranking_score       REAL NOT NULL,
        avatar              TEXT NOT NULL,
        progress            TEXT NOT NULL,

        game_key            TEXT,
        game_progress       TEXT,
        user_data           TEXT,
        settings            TEXT,

        captured_at         TEXT NOT NULL,
        created_at          TEXT NOT NULL,

        UNIQUE (player_id, save_sha256)
    ) STRICT
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_pgr_snapshots_player
        ON pgr_snapshots (player_id, captured_at DESC)
    """,
    # ---- song records ----
    """
    CREATE TABLE IF NOT EXISTS pgr_song_records (
        snapshot_id TEXT    NOT NULL,
        song_id     TEXT    NOT NULL,
        level       INTEGER NOT NULL CHECK (level BETWEEN 0 AND 3),
        score       INTEGER NOT NULL CHECK (score    BETWEEN 0 AND 1000000),
        accuracy    REAL    NOT NULL CHECK (accuracy BETWEEN 0 AND 100),
        full_combo  INTEGER NOT NULL CHECK (full_combo IN (0, 1)),

        difficulty  REAL,

        rks REAL GENERATED ALWAYS AS (
            CASE
                WHEN accuracy < 55.0 THEN 0.0
                ELSE difficulty * ((accuracy - 55.0) / 45.0) * ((accuracy - 55.0) / 45.0)
            END
        ) STORED,

        PRIMARY KEY (snapshot_id, song_id, level)
    ) STRICT, WITHOUT ROWID
    """,
    # difficulty is nullable on purpose: a song missing from the chart table is
    # stored as NULL, which makes rks NULL (sorted last) instead of a fake 0.
    """
    CREATE INDEX IF NOT EXISTS idx_pgr_records_b19
        ON pgr_song_records (snapshot_id, rks DESC)
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_pgr_records_song
        ON pgr_song_records (song_id, level, rks DESC)
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_pgr_records_phi
        ON pgr_song_records (snapshot_id, difficulty DESC) WHERE score = 1000000
    """,
    # ---- views ----
    """
    CREATE VIEW IF NOT EXISTS v_pgr_latest_snapshot AS
    SELECT * FROM (
        SELECT s.*,
               ROW_NUMBER() OVER (
                   PARTITION BY player_id
                   ORDER BY captured_at DESC, created_at DESC, id DESC
               ) AS rn
        FROM pgr_snapshots s
    ) WHERE rn = 1
    """,
    """
    CREATE VIEW IF NOT EXISTS v_pgr_player_song_best AS
    SELECT player_id, snapshot_id, song_id, level, score, accuracy, full_combo, difficulty, rks
    FROM (
        SELECT s.player_id, r.snapshot_id, r.song_id, r.level, r.score, r.accuracy,
               r.full_combo, r.difficulty, r.rks,
               ROW_NUMBER() OVER (
                   PARTITION BY s.player_id, r.song_id, r.level
                   ORDER BY r.rks DESC, s.captured_at DESC
               ) AS rn
        FROM pgr_song_records r
        JOIN pgr_snapshots s ON s.id = r.snapshot_id
    ) WHERE rn = 1
    """,
)

# Columns are listed explicitly because run_sql returns cursor.fetchall(), i.e.
# bare tuples with no names, which are zipped back into dicts here.
_PLAYER_COLUMNS = (
    "id", "platform", "platform_id", "region", "open_id", "nickname", "created_at", "updated_at",
)

_SNAPSHOT_COLUMNS = (
    "id", "player_id", "save_sha256", "save_size",
    "save_version", "game_version", "challenge_mode_rank",
    "ranking_score", "avatar", "progress",
    "captured_at", "created_at",
)

_RECORD_COLUMNS = ("song_id", "level", "score", "accuracy", "full_combo", "difficulty", "rks")


def _to_dicts(rows: Iterable[Sequence[Any]], columns: Sequence[str]) -> list[dict[str, Any]]:
    """Zip fetchall() tuples into dicts using the given column names."""
    return [dict(zip(columns, row)) for row in rows]


@dataclass(slots=True)
class SnapshotSaveResult:
    """Outcome of :meth:`PhigrosUserdataDatabase.SaveSnapshot`."""

    snapshot_id: str
    is_new: bool
    """False means this exact save was already stored and nothing was written."""

    record_count: int
    """Number of song rows written."""

    missing_songs: list[str] = field(default_factory=list)
    """Songs absent from the difficulty table; their difficulty/rks stay NULL."""

    @property
    def ok(self) -> bool:
        return self.snapshot_id != ""


class PhigrosUserdataDatabase(Database):
    """Read/write entry point for Phigros data.

    Inherits from ``userInfoController.Database`` and reuses the same
    ``userdata.db`` file and its ``run_sql``.
    """

    def __init__(self) -> None:
        super().__init__()
        self._table_ready = False

    # -------------------------------------------------------------------------
    # Schema setup
    # -------------------------------------------------------------------------

    def CreateTableIfNotExists(self) -> None:
        """Create tables, indexes and views. Safe to call repeatedly."""
        if self._table_ready:
            return

        # WAL keeps readers from blocking the writer, which suits a long-running
        # bot process. It is persisted in the database file, so once is enough.
        self.run_sql("PRAGMA journal_mode = WAL")

        for statement in _TABLE_STATEMENTS:
            self.run_sql(statement)

        self._Migrate()

        # run_sql swallows errors, so read back to confirm the tables exist.
        rows = self.run_sql(
            "SELECT COUNT(*) FROM sqlite_master WHERE type = 'table' AND name LIKE 'pgr_%'"
        )
        count = rows[0][0] if rows else 0
        if count < 4:
            _error(f"[phigros] schema setup failed: found {count} pgr_ tables, expected 4")
            return

        self._table_ready = True
        _info(f"[phigros] schema ready ({count} tables)")

    def _Migrate(self) -> None:
        """Add columns introduced after a database was first created.

        ``CREATE TABLE IF NOT EXISTS`` silently does nothing when the table is
        already there, so a database from an older version keeps its old
        column set and every statement mentioning a new column fails.
        """
        for table, column, definition in _MIGRATIONS:
            # PRAGMA table_info returns (cid, name, type, notnull, dflt, pk).
            rows = self.run_sql(f"PRAGMA table_info({table})")
            if not rows:
                continue  # Table not created yet; CREATE TABLE already has it.

            existing = {row[1] for row in rows}
            if column in existing:
                continue

            self.run_sql(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")
            _info(f"[phigros] migrated: added {table}.{column}")

    def _ensure_tables(self) -> None:
        """Create the schema on first use so callers cannot forget to."""
        if not self._table_ready:
            self.CreateTableIfNotExists()

    # -------------------------------------------------------------------------
    # Players
    # -------------------------------------------------------------------------

    def BindPlayer(
        self,
        platform_id: str,
        platform: str = "qq",
        region: str = "china",
        open_id: Optional[str] = None,
        nickname: Optional[str] = None,
    ) -> str:
        """Bind a player and return the player id.

        Binding is idempotent: re-binding never overwrites an existing row, so
        it is safe to call on every command.
        """
        self._ensure_tables()

        player_id = make_player_id(platform_id, platform)
        now = utcnow()

        self.run_sql(
            """
            INSERT OR IGNORE INTO pgr_players
                (id, platform, platform_id, region, open_id, nickname, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (player_id, platform, platform_id, region, open_id, nickname, now, now),
        )

        return player_id

    def GetPlayer(self, player_id: str) -> Optional[dict[str, Any]]:
        """Return the player row, or None if it does not exist."""
        self._ensure_tables()

        rows = self.run_sql(
            f"SELECT {', '.join(_PLAYER_COLUMNS)} FROM pgr_players WHERE id = ?",
            (player_id,),
        )
        players = _to_dicts(rows, _PLAYER_COLUMNS)
        return players[0] if players else None

    def GetPlayerByPlatformId(
        self, platform_id: str, platform: str = "qq"
    ) -> Optional[dict[str, Any]]:
        """Return the player row for a platform user id (e.g. a QQ number)."""
        return self.GetPlayer(make_player_id(platform_id, platform))

    def SetOpenId(self, player_id: str, open_id: str) -> None:
        """Record the LeanCloud user id, which identifies the game account."""
        self._ensure_tables()

        self.run_sql(
            "UPDATE pgr_players SET open_id = ?, updated_at = ? WHERE id = ?",
            (open_id, utcnow(), player_id),
        )

    def SetNickname(self, player_id: str, nickname: str) -> None:
        """Cache the in-game nickname so listing players needs no API call."""
        self._ensure_tables()

        self.run_sql(
            "UPDATE pgr_players SET nickname = ?, updated_at = ? WHERE id = ?",
            (nickname, utcnow(), player_id),
        )

    def ListPlayers(self, region: Optional[str] = None) -> list[dict[str, Any]]:
        """List bound players, optionally filtered by region."""
        self._ensure_tables()

        if region is None:
            rows = self.run_sql(
                f"SELECT {', '.join(_PLAYER_COLUMNS)} FROM pgr_players ORDER BY created_at"
            )
        else:
            rows = self.run_sql(
                f"SELECT {', '.join(_PLAYER_COLUMNS)} FROM pgr_players "
                "WHERE region = ? ORDER BY created_at",
                (region,),
            )

        return _to_dicts(rows, _PLAYER_COLUMNS)

    def DeletePlayer(self, player_id: str) -> None:
        """Delete a player and everything owned by them.

        run_sql opens a new connection per call, so ``PRAGMA foreign_keys``
        never takes effect and ``ON DELETE CASCADE`` does not fire. The
        cascade is therefore done by hand, children first.
        """
        self._ensure_tables()

        self.run_sql(
            "DELETE FROM pgr_song_records WHERE snapshot_id IN "
            "(SELECT id FROM pgr_snapshots WHERE player_id = ?)",
            (player_id,),
        )
        self.run_sql("DELETE FROM pgr_snapshots WHERE player_id = ?", (player_id,))
        self.run_sql("DELETE FROM pgr_credentials WHERE player_id = ?", (player_id,))
        self.run_sql("DELETE FROM pgr_players WHERE id = ?", (player_id,))

    # -------------------------------------------------------------------------
    # Credentials
    # -------------------------------------------------------------------------

    def SaveSessionToken(
        self, player_id: str, session_token: str, expires_at: Optional[str] = None
    ) -> None:
        """Store or replace the sessionToken for a player."""
        self._ensure_tables()

        self.run_sql(
            """
            INSERT INTO pgr_credentials (player_id, session_token, obtained_at, expires_at)
            VALUES (?, ?, ?, ?)
            ON CONFLICT (player_id) DO UPDATE SET
                session_token = excluded.session_token,
                obtained_at   = excluded.obtained_at,
                expires_at    = excluded.expires_at
            """,
            (player_id, session_token, utcnow(), expires_at),
        )

    def GetSessionToken(self, player_id: str) -> Optional[str]:
        """Return the stored sessionToken, or None when the player is unbound."""
        self._ensure_tables()

        rows = self.run_sql(
            "SELECT session_token FROM pgr_credentials WHERE player_id = ?", (player_id,)
        )
        return rows[0][0] if rows else None

    def DeleteSessionToken(self, player_id: str) -> None:
        """Remove the credential, leaving historical snapshots in place."""
        self._ensure_tables()
        self.run_sql("DELETE FROM pgr_credentials WHERE player_id = ?", (player_id,))

    # -------------------------------------------------------------------------
    # Snapshots
    # -------------------------------------------------------------------------

    def SaveSnapshot(
        self,
        player_id: str,
        save: "psl.SaveData",
        blob: bytes,
        summary: "Optional[psl.Summary]" = None,
        difficulties: "Optional[psl.DifficultyTable]" = None,
        captured_at: Optional[str] = None,
    ) -> SnapshotSaveResult:
        """Store one save, together with the records parsed out of it.

        :param save: parsed save (``psl.SaveData``).
        :param blob: the raw zip, kept for the content hash and for replay.
        :param summary: LeanCloud summary; without it RKS and progress are
            estimated from the records, which is less accurate than the value
            the game itself reports.
        :param difficulties: chart constant table, defaults to the bundled one.
        :param captured_at: when the save was made; defaults to the summary's
            update time, or to now.

        Submitting the same save twice is a no-op and returns ``is_new=False``.
        """
        self._ensure_tables()

        if difficulties is None:
            difficulties = psl.DifficultyTable.bundled()

        sha = hashlib.sha256(blob).hexdigest()
        snapshot_id = make_snapshot_id(player_id, sha)

        # Already stored: nothing to do. Also refuse to write for unknown
        # players so no orphan rows can appear.
        if self.GetSnapshot(snapshot_id) is not None:
            return SnapshotSaveResult(snapshot_id, is_new=False, record_count=0)

        if self.GetPlayer(player_id) is None:
            _error(f"[phigros] unknown player {player_id}, snapshot skipped")
            return SnapshotSaveResult("", is_new=False, record_count=0)

        calculator = psl.RksCalculator(difficulties)

        if summary is not None:
            save_version = summary.save_version
            game_version = summary.game_version
            challenge_rank = summary.challenge_mode_rank
            ranking_score = summary.ranking_score
            avatar = summary.avatar
            progress = list(summary.progress)
        else:
            save_version = 1
            game_version = 0
            challenge_rank = save.game_progress.challenge_mode_rank
            avatar = save.user.avatar
            ranking_score, progress = self._EstimateFromRecords(save, calculator)

        now = utcnow()

        # captured_at is when the save itself was made; created_at is when we
        # stored it. They differ when backfilling history, so both are kept.
        if captured_at is None:
            if summary is not None and summary.updated_at is not None:
                captured_at = summary.updated_at.isoformat()
            else:
                captured_at = now

        self.run_sql(
            """
            INSERT OR IGNORE INTO pgr_snapshots (
                id, player_id, save_sha256, save_size, save_blob,
                save_version, game_version, challenge_mode_rank,
                ranking_score, avatar, progress,
                game_key, game_progress, user_data, settings,
                captured_at, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                snapshot_id, player_id, sha, len(blob), blob,
                save_version, game_version, challenge_rank,
                ranking_score, avatar, json.dumps(progress),
                json.dumps(save.game_key.to_dict(), ensure_ascii=False),
                json.dumps(save.game_progress.to_dict(), ensure_ascii=False),
                json.dumps(save.user.to_dict(), ensure_ascii=False),
                json.dumps(save.settings.to_dict(), ensure_ascii=False),
                captured_at,
                now,
            ),
        )

        # Writes always return [] and swallow errors, so confirm by reading back.
        if self.GetSnapshot(snapshot_id) is None:
            _error(f"[phigros] snapshot {snapshot_id} failed to save")
            return SnapshotSaveResult("", is_new=False, record_count=0)

        missing, written = self._WriteRecords(snapshot_id, save, difficulties)

        if missing:
            _error(
                f"[phigros] snapshot {snapshot_id}: {len(missing)} songs missing from "
                f"the difficulty table ({', '.join(missing[:10])})"
            )

        return SnapshotSaveResult(
            snapshot_id, is_new=True, record_count=written, missing_songs=missing
        )

    @staticmethod
    def _EstimateFromRecords(
        save: "psl.SaveData", calculator: "psl.RksCalculator"
    ) -> tuple[float, list[int]]:
        """Derive RKS and progress from the records when there is no summary.

        RKS needs chart constants, and the table may not know a brand new song
        yet. In that case progress is still counted (it needs no constants) and
        RKS is recorded as 0: dropping the whole snapshot over one unknown song
        would be worse. Re-saving with a summary replaces it with the real value.
        """
        try:
            return (
                calculator.compute_best19(save.game_record).rks,
                calculator.compute_progress(save.game_record),
            )
        except psl.PhigrosDataError as error:
            _error(f"[phigros] {error}; recording RKS as 0 and counting progress directly")
            return 0.0, PhigrosUserdataDatabase._CountProgress(save)

    @staticmethod
    def _CountProgress(save: "psl.SaveData") -> list[int]:
        """Count played / FC / AP per difficulty (12 values).

        Matches ``psl.RksCalculator.compute_progress`` but needs no difficulty
        table, so it still works while the table lags behind a game update.
        """
        progress = [0] * (len(LEVEL_NAMES) * 3)

        for levels in save.game_record.values():
            for level, record in levels.played():
                if record.accuracy == 0:
                    continue

                offset = 3 * int(level)
                progress[offset] += 1
                if record.is_all_perfect:
                    progress[offset + 1] += 1
                    progress[offset + 2] += 1
                elif record.full_combo:
                    progress[offset + 1] += 1

        return progress

    def _WriteRecords(
        self,
        snapshot_id: str,
        save: "psl.SaveData",
        difficulties: "psl.DifficultyTable",
    ) -> tuple[list[str], int]:
        """Write song rows, returning (songs missing from the table, rows written)."""
        # Unplayed difficulties get no row at all, so "played count" is COUNT(*).
        # Rows are flushed in batches to stay under the bound-parameter limit.
        batch: list[tuple[Any, ...]] = []
        missing: list[str] = []
        written = 0

        for song_id, levels in save.game_record.items():
            chart = difficulties.get(song_id)
            if chart is None:
                if not levels.is_empty:
                    missing.append(song_id)
                chart = [0.0] * 4

            for level, record in levels.played():
                # A constant of 0 means the chart table has no entry for this
                # difficulty, so store NULL rather than a fake value.
                difficulty = chart[level] if chart[level] > 0 else None

                batch.append((
                    snapshot_id, song_id, int(level),
                    record.score, record.accuracy, int(record.full_combo),
                    difficulty,
                ))

                if len(batch) >= _RECORD_BATCH:
                    written += self._FlushRecords(batch)
                    batch.clear()

        if batch:
            written += self._FlushRecords(batch)

        return missing, written

    def _FlushRecords(self, batch: list[tuple[Any, ...]]) -> int:
        """Insert one batch of song rows and return how many rows it held."""
        placeholders = ", ".join(["(?, ?, ?, ?, ?, ?, ?)"] * len(batch))
        flat = [value for row in batch for value in row]

        self.run_sql(
            "INSERT OR REPLACE INTO pgr_song_records "
            "(snapshot_id, song_id, level, score, accuracy, full_combo, difficulty) "
            f"VALUES {placeholders}",
            tuple(flat),
        )

        return len(batch)

    def GetSnapshot(self, snapshot_id: str) -> Optional[dict[str, Any]]:
        """Return snapshot metadata (without the blob)."""
        self._ensure_tables()

        rows = self.run_sql(
            f"SELECT {', '.join(_SNAPSHOT_COLUMNS)} FROM pgr_snapshots WHERE id = ?",
            (snapshot_id,),
        )
        snapshots = _to_dicts(rows, _SNAPSHOT_COLUMNS)
        return snapshots[0] if snapshots else None

    def GetSnapshotBlob(self, snapshot_id: str) -> Optional[bytes]:
        """Return the original save zip."""
        self._ensure_tables()

        rows = self.run_sql("SELECT save_blob FROM pgr_snapshots WHERE id = ?", (snapshot_id,))
        return rows[0][0] if rows else None

    def GetLatestSnapshot(self, player_id: str) -> Optional[dict[str, Any]]:
        """Return the player's most recent snapshot metadata."""
        self._ensure_tables()

        rows = self.run_sql(
            f"SELECT {', '.join(_SNAPSHOT_COLUMNS)} FROM v_pgr_latest_snapshot WHERE player_id = ?",
            (player_id,),
        )
        snapshots = _to_dicts(rows, _SNAPSHOT_COLUMNS)
        return snapshots[0] if snapshots else None

    def ListSnapshots(self, player_id: str, limit: int = 30) -> list[dict[str, Any]]:
        """List a player's snapshots, newest first (without blobs)."""
        self._ensure_tables()

        rows = self.run_sql(
            f"SELECT {', '.join(_SNAPSHOT_COLUMNS)} FROM pgr_snapshots "
            "WHERE player_id = ? ORDER BY captured_at DESC, created_at DESC LIMIT ?",
            (player_id, int(limit)),
        )
        return _to_dicts(rows, _SNAPSHOT_COLUMNS)

    # -------------------------------------------------------------------------
    # Records and statistics
    # -------------------------------------------------------------------------

    def GetSongRecords(self, snapshot_id: str) -> list[dict[str, Any]]:
        """Return every song row of one snapshot."""
        self._ensure_tables()

        rows = self.run_sql(
            f"SELECT {', '.join(_RECORD_COLUMNS)} FROM pgr_song_records WHERE snapshot_id = ?",
            (snapshot_id,),
        )
        return _to_dicts(rows, _RECORD_COLUMNS)

    def GetLatestRecords(self, player_id: str) -> list[dict[str, Any]]:
        """Return every song row of the player's latest snapshot."""
        self._ensure_tables()

        rows = self.run_sql(
            f"SELECT {', '.join(_RECORD_COLUMNS)} FROM pgr_song_records "
            "WHERE snapshot_id = (SELECT id FROM v_pgr_latest_snapshot WHERE player_id = ?)",
            (player_id,),
        )
        return _to_dicts(rows, _RECORD_COLUMNS)

    def ComputeBest19(self, player_id: str) -> dict[str, Any]:
        """Compute B19 with SQL, matching ``psl.RksCalculator.compute_best19``.

        Returns ``{"rks", "best_count", "phi"}`` where ``phi`` may be None.
        Everything is computed inside the database; no records are fetched.
        """
        self._ensure_tables()

        rows = self.run_sql(
            """
            WITH latest AS (
                SELECT id FROM v_pgr_latest_snapshot WHERE player_id = ?
            ),
            best AS (
                SELECT song_id, level, score, accuracy, difficulty, rks
                FROM pgr_song_records
                WHERE snapshot_id = (SELECT id FROM latest) AND accuracy >= 55
                ORDER BY rks DESC
                LIMIT 19
            ),
            phi AS (
                SELECT song_id, level, score, accuracy, difficulty, rks
                FROM pgr_song_records
                WHERE snapshot_id = (SELECT id FROM latest) AND score = 1000000
                ORDER BY difficulty DESC
                LIMIT 1
            )
            SELECT
                (COALESCE((SELECT SUM(rks) FROM best), 0.0)
                 + COALESCE((SELECT rks FROM phi), 0.0)) / 20.0 AS rks,
                (SELECT COUNT(*)     FROM best) AS best_count,
                (SELECT song_id      FROM phi)  AS phi_song_id,
                (SELECT level        FROM phi)  AS phi_level,
                (SELECT score        FROM phi)  AS phi_score,
                (SELECT accuracy     FROM phi)  AS phi_accuracy,
                (SELECT difficulty   FROM phi)  AS phi_difficulty,
                (SELECT rks          FROM phi)  AS phi_rks
            """,
            (player_id,),
        )

        if not rows:
            return {"rks": 0.0, "best_count": 0, "phi": None}

        rks, best_count, song_id, level, score, accuracy, difficulty, phi_rks = rows[0]

        phi = None
        if song_id is not None:
            phi = {
                "song_id": song_id,
                "level": level,
                "level_name": LEVEL_NAMES[level] if level is not None else None,
                "score": score,
                "accuracy": accuracy,
                "difficulty": difficulty,
                "rks": phi_rks,
            }

        # Fewer than 19 entries still divide by 20, as the game does.
        return {"rks": rks or 0.0, "best_count": best_count, "phi": phi}

    def GetBest19List(self, player_id: str, limit: int = 19) -> list[dict[str, Any]]:
        """Return the B19 entries themselves, for display."""
        self._ensure_tables()

        rows = self.run_sql(
            f"SELECT {', '.join(_RECORD_COLUMNS)} FROM pgr_song_records "
            "WHERE snapshot_id = (SELECT id FROM v_pgr_latest_snapshot WHERE player_id = ?) "
            "AND accuracy >= 55 ORDER BY rks DESC LIMIT ?",
            (player_id, int(limit)),
        )
        records = _to_dicts(rows, _RECORD_COLUMNS)

        for record in records:
            level = record.get("level")
            record["level_name"] = (
                LEVEL_NAMES[level] if isinstance(level, int) and 0 <= level < 4 else None
            )

        return records

    def GetProgress(self, player_id: str) -> list[dict[str, Any]]:
        """Count played / FC / AP per difficulty for the latest snapshot."""
        self._ensure_tables()

        rows = self.run_sql(
            """
            SELECT level,
                   COUNT(*)             AS played,
                   SUM(full_combo)      AS full_combo,
                   SUM(score = 1000000) AS all_perfect
            FROM pgr_song_records
            WHERE snapshot_id = (SELECT id FROM v_pgr_latest_snapshot WHERE player_id = ?)
            GROUP BY level ORDER BY level
            """,
            (player_id,),
        )

        result = []
        for level, played, full_combo, all_perfect in rows:
            result.append({
                "level": level,
                "level_name": (
                    LEVEL_NAMES[level] if isinstance(level, int) and 0 <= level < 4 else None
                ),
                "played": played,
                "full_combo": full_combo or 0,
                "all_perfect": all_perfect or 0,
            })

        return result

    def GetSongBest(self, player_id: str, song_id: str, level: int) -> Optional[dict[str, Any]]:
        """Best historical score for one song and difficulty, across snapshots."""
        self._ensure_tables()

        rows = self.run_sql(
            f"SELECT {', '.join(_RECORD_COLUMNS)} FROM v_pgr_player_song_best "
            "WHERE player_id = ? AND song_id = ? AND level = ?",
            (player_id, song_id, int(level)),
        )
        records = _to_dicts(rows, _RECORD_COLUMNS)
        return records[0] if records else None

    def FindSongs(self, keyword: str, limit: int = 10) -> list[str]:
        """Song ids the player has played that contain ``keyword``.

        Song ids look like ``Artist.Title``, so a plain LIKE is enough.
        """
        self._ensure_tables()

        rows = self.run_sql(
            "SELECT DISTINCT song_id FROM pgr_song_records "
            "WHERE song_id LIKE ? ORDER BY song_id LIMIT ?",
            (f"%{keyword}%", int(limit)),
        )
        return [row[0] for row in rows]

    def GetSongLeaderboard(self, song_id: str, level: int, limit: int = 20) -> list[dict[str, Any]]:
        """Players with the best score on one song and difficulty."""
        self._ensure_tables()

        rows = self.run_sql(
            """
            SELECT b.player_id, b.score, b.accuracy, b.full_combo, b.rks,
                   p.nickname, p.open_id
            FROM v_pgr_player_song_best b
            JOIN pgr_players p ON p.id = b.player_id
            WHERE b.song_id = ? AND b.level = ?
            ORDER BY b.rks DESC
            LIMIT ?
            """,
            (song_id, int(level), int(limit)),
        )

        return [
            {
                "player_id": row[0],
                "score": row[1],
                "accuracy": row[2],
                "full_combo": bool(row[3]),
                "rks": row[4],
                "nickname": row[5],
                "open_id": row[6],
            }
            for row in rows
        ]

    def GetRksHistory(self, player_id: str, limit: int = 50) -> list[dict[str, Any]]:
        """RKS over time, oldest first, for a progress curve.

        Uses the ``ranking_score`` stored with each snapshot: the value the game
        reported when a summary was available, otherwise an estimate computed
        with the chart table of that moment.
        """
        self._ensure_tables()

        rows = self.run_sql(
            "SELECT captured_at, ranking_score FROM pgr_snapshots "
            "WHERE player_id = ? ORDER BY captured_at DESC LIMIT ?",
            (player_id, int(limit)),
        )

        return [{"captured_at": row[0], "rks": row[1]} for row in reversed(rows)]
