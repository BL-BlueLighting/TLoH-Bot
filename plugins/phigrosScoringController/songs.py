"""
Song metadata lookup.

``data/info.tsv`` ships with the plugin and holds one row per song::

    songId  <TAB>  曲名  <TAB>  曲师  <TAB>  画师  <TAB>  谱师EZ  <TAB>  HD  <TAB>  IN  [<TAB>  AT]

Chart constants come from PhigrosScoreLibrary's bundled difficulty table, which
is the same data the score calculations use, so the two can never disagree.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional, Sequence

import PhigrosScoreLibrary as psl

#: Field names for the columns of a data row, in order.
INFO_FIELDS = ("曲名", "曲师", "画师", "谱师EZ", "谱师HD", "谱师IN", "谱师AT")

DEFAULT_LIMIT = 10


class SongInfo:
    """Lazily-loaded song metadata plus chart constants."""

    def __init__(self, path: Optional[Path] = None) -> None:
        self.path = path or Path(__file__).parent / "data" / "info.tsv"
        self._info: Optional[dict[str, list[str]]] = None
        self._difficulty: Optional["psl.DifficultyTable"] = None

    # -- loading ----------------------------------------------------------

    @property
    def info(self) -> dict[str, list[str]]:
        if self._info is None:
            self._info = self._load()
        return self._info

    @property
    def difficulty(self) -> "psl.DifficultyTable":
        if self._difficulty is None:
            self._difficulty = psl.DifficultyTable.bundled()
        return self._difficulty

    def _load(self) -> dict[str, list[str]]:
        table: dict[str, list[str]] = {}
        if not self.path.exists():
            return table

        for line in self.path.read_text(encoding="utf-8").splitlines():
            parts = line.rstrip("\n").split("\t")
            if len(parts) >= 2:
                table[parts[0]] = parts[1:]

        return table

    def reload(self) -> None:
        """Drop the cache, e.g. after replacing the data files."""
        self._info = None
        self._difficulty = None

    # -- lookup -----------------------------------------------------------

    def exists(self, song_id: str) -> bool:
        return song_id in self.difficulty

    def fields(self, song_id: str) -> list[str]:
        """Metadata columns for a song, padded so indexes are always valid."""
        row = list(self.info.get(song_id, []))
        return (row + [""] * len(INFO_FIELDS))[: len(INFO_FIELDS)]

    def constants(self, song_id: str) -> list[float]:
        """Chart constants as [EZ, HD, IN, AT]; unknown songs give zeros."""
        levels = self.difficulty.get(song_id)
        return list(levels) if levels else [0.0, 0.0, 0.0, 0.0]

    def title(self, song_id: str) -> str:
        """Display title, falling back to the raw id."""
        name = self.fields(song_id)[0]
        return name or song_id

    @property
    def song_ids(self) -> Sequence[str]:
        return list(self.difficulty.songs.keys())

    def search(self, keyword: str, limit: int = DEFAULT_LIMIT) -> list[str]:
        """Songs whose id, title, composer or charter matches ``keyword``.

        An exact id match short-circuits the search so a full song id always
        resolves, even when it is also a substring of other ids.
        """
        keyword = keyword.strip()
        if not keyword:
            return []

        if self.exists(keyword):
            return [keyword]

        needle = keyword.lower()
        exact: list[str] = []
        partial: list[str] = []

        for song_id in self.song_ids:
            title = self.title(song_id)
            haystack = " ".join((song_id, title, *self.fields(song_id))).lower()

            if song_id.lower().endswith(needle) or title.lower() == needle:
                exact.append(song_id)
            elif needle in haystack:
                partial.append(song_id)

        return (exact + partial)[:limit]

    def resolve(self, keyword: str) -> tuple[Optional[str], list[str]]:
        """Return (song_id, candidates).

        ``song_id`` is set only when the keyword points at exactly one song;
        otherwise the caller shows ``candidates`` and asks for a better keyword.
        """
        matches = self.search(keyword, limit=DEFAULT_LIMIT)
        if len(matches) == 1:
            return matches[0], matches

        return None, matches

    def random_id(self) -> str:
        import random

        return random.choice(self.song_ids)
