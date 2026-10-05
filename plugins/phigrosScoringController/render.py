"""
Image rendering for the Phigros commands.

Everything is drawn with Pillow, so there is no browser or headless Chrome to
install (unlike the puppeteer/HTML approach used elsewhere).

The look follows the familiar "PHIGROS RANK QUERY" score sheet: a light grid
background, white rounded cards, and a three-column grid for the B19 where each
cell carries the song title in its own colour, the single-song RKS, the score
and accuracy, the album art and the difficulty badge.

Album art comes from ``data/illustrations/<song id>.jpg``; a cell simply omits
the artwork when the song has no thumbnail.
"""

from __future__ import annotations

import colorsys
import hashlib
import os
import random
import tempfile
import time
from pathlib import Path
from typing import Any, Optional, Sequence

from PIL import Image, ImageDraw, ImageFont

from toolsbot.services import _error

# ---------------------------------------------------------------------------
# Palette
# ---------------------------------------------------------------------------

BG = (238, 241, 245)
GRID = (226, 231, 238)
CARD = (255, 255, 255)
CARD_EDGE = (225, 230, 238)
TEXT = (26, 29, 36)
MUTED = (139, 147, 163)
FAINT = (186, 193, 205)
ACCENT = (58, 110, 220)

#: Difficulty colours, indexed by level (EZ / HD / IN / AT).
LEVEL_COLORS = ((36, 168, 92), (48, 118, 224), (222, 72, 72), (152, 84, 220))

#: Colour of the accuracy line: orange for a perfect score, green for FC, else blue.
ACC_AP = (240, 140, 20)
ACC_FC = (36, 168, 92)
ACC_PLAIN = (48, 118, 224)

LEVEL_NAMES = ("EZ", "HD", "IN", "AT")

#: Stamped on the bottom-right of the score sheet.
COPYRIGHT = "(C) Copyright 2026 TLoH-Bot Contributors and BL-BlueLighting"

#: Reaction shown next to an AP / FC on a hard chart, picked at random.
PRAISE_PHRASES = ("吓哭了", "大神啊教我", "/bx")

#: Colour of that reaction.
PRAISE_COLOR = (226, 62, 92)

#: RKS at or above which the bottom quip changes.
QUIP_RKS_THRESHOLD = 16.5

#: Bottom quip for a very high RKS.
QUIP_HIGH_RKS = ":: 多打歌...等等？rks 这么高？"

#: Bottom quip everyone else gets.
QUIP_DEFAULT = ":: 多打歌。"


def earns_praise(level: int, constant: float) -> bool:
    """Whether a clear on this chart is worth a reaction: AT 17+ and IN 16+."""
    return (level == 3 and constant >= 17.0) or (level == 2 and constant >= 16.0)

#: Cell sizes for the B19 grid.
CELL_W = 560
CELL_H = 172
CELL_GAP = 18
COLUMNS = 3
MARGIN = 44
HEADER_H = 132

ILLUSTRATION_DIR = Path(__file__).parent / "data" / "illustrations"
ILLUSTRATION_SIZE = (160, 90)
#: Vertical offset of the artwork, leaving room for the rank label above it.
ILLUSTRATION_TOP = 36

# ---------------------------------------------------------------------------
# Fonts
# ---------------------------------------------------------------------------

#: Subset faces shipped with the plugin, used when the host has no CJK font
#: installed. Covers ASCII, kana and the 3755 common simplified hanzi.
_BUNDLED_FONTS = Path(__file__).parent / "data" / "fonts"

#: The CJK faces live inside .ttc collections; index 2 is Simplified Chinese.
#: System fonts come first because they cover every character; the bundled
#: subset is the fallback so a bare server still renders properly.
_CJK = (
    ("/usr/share/fonts/noto-cjk/NotoSansCJK-Regular.ttc", 2),
    ("/usr/share/fonts/noto-cjk/NotoSansCJK-DemiLight.ttc", 2),
    ("/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc", 2),
    ("/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc", 2),
    (str(_BUNDLED_FONTS / "NotoSansSC-Regular.otf"), 0),
)
_CJK_BOLD = (
    ("/usr/share/fonts/noto-cjk/NotoSansCJK-Bold.ttc", 2),
    ("/usr/share/fonts/noto-cjk/NotoSansCJK-Medium.ttc", 2),
    ("/usr/share/fonts/truetype/noto/NotoSansCJK-Bold.ttc", 2),
    ("/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc", 2),
    (str(_BUNDLED_FONTS / "NotoSansSC-Bold.otf"), 0),
)
_MONO = (
    ("/usr/share/fonts/TTF/JetBrainsMono-ExtraBold.ttf", 0),
    ("/usr/share/fonts/noto/NotoSansMono-Light.ttf", 0),
)

_font_cache: dict[tuple[str, int], ImageFont.FreeTypeFont] = {}
_font_warned = False


def _try_load(candidates: Sequence[tuple[str, int]], size: int) -> Optional[ImageFont.FreeTypeFont]:
    for path, index in candidates:
        if not os.path.exists(path):
            continue
        try:
            return ImageFont.truetype(path, size, index=index)
        except OSError:
            continue

    return None


def _load_font(size: int, bold: bool = False, mono: bool = False) -> ImageFont.FreeTypeFont:
    """Load a font, falling back through the bundled faces then Pillow's default."""
    global _font_warned

    kind = "mono" if mono else "bold" if bold else "regular"
    key = (kind, size)
    if key in _font_cache:
        return _font_cache[key]

    font = _try_load(_MONO if mono else _CJK_BOLD if bold else _CJK, size)

    if font is None and mono:
        # The CJK faces carry digits and Latin too, which beats the bitmap default.
        font = _try_load(_CJK_BOLD if bold else _CJK, size)

    if font is None:
        if not _font_warned:
            _font_warned = True
            _error(
                "[phigros] 没有可用字体，卡片上的中文会显示成方块。"
                "请安装 fonts-noto-cjk，或把字体放到 data/fonts/ 下。"
            )
        font = ImageFont.load_default(size)

    _font_cache[key] = font
    return font


def _font_for(text: str, size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    """Mono digits for plain ASCII, the CJK face for anything else.

    The monospaced faces carry no CJK glyphs at all, so drawing non-ASCII with
    them produces rows of empty boxes.
    """
    if text and text.isascii():
        return _load_font(size, mono=True)
    return _load_font(size, bold=bold)


_measure = ImageDraw.Draw(Image.new("RGB", (1, 1)))


def _width(text: str, font: ImageFont.FreeTypeFont) -> float:
    return _measure.textlength(text, font=font)


def _fit(text: str, font: ImageFont.FreeTypeFont, max_width: float) -> str:
    """Truncate ``text`` with an ellipsis so it fits ``max_width``."""
    if _width(text, font) <= max_width:
        return text

    while text and _width(text + "…", font) > max_width:
        text = text[:-1]

    return text + "…"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def title_color(song_id: str) -> tuple[int, int, int]:
    """A stable per-song colour, so the sheet looks varied but never random."""
    digest = hashlib.md5(song_id.encode("utf-8")).digest()
    hue = digest[0] / 255.0
    red, green, blue = colorsys.hls_to_rgb(hue, 0.40, 0.78)
    return (int(red * 255), int(green * 255), int(blue * 255))


def _background(width: int, height: int) -> Image.Image:
    """Light background with the faint graph-paper grid of the score sheet."""
    image = Image.new("RGB", (width, height), BG)
    draw = ImageDraw.Draw(image)

    step = 26
    for x in range(0, width, step):
        draw.line([(x, 0), (x, height)], fill=GRID)
    for y in range(0, height, step):
        draw.line([(0, y), (width, y)], fill=GRID)

    return image


def _card(draw: ImageDraw.ImageDraw, box: Sequence[float], fill=CARD, radius: int = 14) -> None:
    """A white rounded panel with a hairline border."""
    draw.rounded_rectangle(box, radius=radius, fill=fill, outline=CARD_EDGE, width=1)


_illustrations: dict[str, Optional[Image.Image]] = {}


def _illustration(song_id: str) -> Optional[Image.Image]:
    """Album art for a song, or None when no thumbnail was shipped."""
    if song_id in _illustrations:
        return _illustrations[song_id]

    path = ILLUSTRATION_DIR / f"{song_id}.jpg"
    image: Optional[Image.Image] = None
    if path.exists():
        try:
            image = Image.open(path).convert("RGB").resize(ILLUSTRATION_SIZE, Image.LANCZOS)
        except OSError:
            image = None

    _illustrations[song_id] = image
    return image


def _paste_rounded(base: Image.Image, art: Image.Image, box: Sequence[int], radius: int = 10) -> None:
    """Paste album art with rounded corners."""
    mask = Image.new("L", art.size, 0)
    ImageDraw.Draw(mask).rounded_rectangle([0, 0, art.size[0] - 1, art.size[1] - 1], radius=radius, fill=255)
    base.paste(art, (int(box[0]), int(box[1])), mask)


#: Rendered cards older than this are deleted on the next render.
_CLEANUP_AGE = 6 * 60 * 60


def _save(image: Image.Image, prefix: str = "pgr") -> str:
    """Write the image to a temp file and return its path."""
    directory = os.path.join(tempfile.gettempdir(), "pgr-render")
    os.makedirs(directory, exist_ok=True)
    _cleanup(directory)

    path = os.path.join(directory, f"{prefix}-{random.randint(10**8, 10**9 - 1)}.png")
    image.save(path, "PNG", optimize=True)

    return path


def _cleanup(directory: str) -> None:
    """Drop old cards so the temp directory does not grow without bound."""
    cutoff = time.time() - _CLEANUP_AGE
    try:
        for name in os.listdir(directory):
            target = os.path.join(directory, name)
            try:
                if os.path.getmtime(target) < cutoff:
                    os.remove(target)
            except OSError:
                continue
    except OSError:
        pass


# ---------------------------------------------------------------------------
# B19 score sheet
# ---------------------------------------------------------------------------

def render_b19(
    nickname: str,
    region: str,
    captured_at: str,
    rks: Optional[float],
    phi: Optional[dict[str, Any]],
    best: Sequence[dict[str, Any]],
    progress: Optional[Sequence[dict[str, Any]]] = None,
) -> str:
    """The B19 score sheet: header plus a three-column grid of entries."""
    rows = max(1, -(-len(best) // COLUMNS))  # ceil
    width = MARGIN * 2 + COLUMNS * CELL_W + (COLUMNS - 1) * CELL_GAP
    grid_h = rows * CELL_H + (rows - 1) * CELL_GAP
    height = HEADER_H + MARGIN + grid_h + MARGIN + 88

    image = _background(width, height)
    draw = ImageDraw.Draw(image)

    _draw_header(draw, nickname, region, captured_at, rks, phi, width)

    for index, entry in enumerate(best):
        column = index % COLUMNS
        row = index // COLUMNS
        left = MARGIN + column * (CELL_W + CELL_GAP)
        top = HEADER_H + MARGIN + row * (CELL_H + CELL_GAP)
        _draw_cell(image, draw, left, top, index + 1, entry)

    _draw_b19_footer(draw, height, progress, width, rks)
    return _save(image, "b19")


def _draw_header(
    draw: ImageDraw.ImageDraw,
    nickname: str,
    region: str,
    captured_at: str,
    rks: Optional[float],
    phi: Optional[dict[str, Any]],
    width: int,
) -> None:
    """Name and RKS in white boxes on the left, the wordmark on the right."""
    box_h = 76
    top = 28

    name_font = _load_font(38, bold=True)
    name = _fit(nickname or "未知玩家", name_font, 620)
    name_w = int(_width(name, name_font)) + 56

    _card(draw, [MARGIN, top, MARGIN + name_w, top + box_h], radius=12)
    draw.text((MARGIN + 28, top + box_h / 2), name, font=name_font, fill=TEXT, anchor="lm")

    rks_font = _load_font(40, mono=True)
    rks_text = f"{rks:.4f}" if rks is not None else "--"
    rks_w = int(_width(rks_text, rks_font)) + 56

    rks_left = MARGIN + name_w + 14
    _card(draw, [rks_left, top, rks_left + rks_w, top + box_h], radius=12)
    draw.text((rks_left + 28, top + box_h / 2), rks_text, font=rks_font, fill=TEXT, anchor="lm")

    subtitle = f"{'国际服' if region == 'global' else '国服'} · {captured_at[:10] or '未知'}"
    draw.text((MARGIN + 6, top + box_h + 20), subtitle, font=_load_font(19), fill=MUTED, anchor="lm")

    mark_font = _load_font(30, bold=True)
    mark = "Phigros Scoring"
    # Letter-spaced wordmark, drawn glyph by glyph.
    spacing = 4
    total = sum(_width(ch, mark_font) + spacing for ch in mark)
    x = width - MARGIN - total
    for ch in mark:
        draw.text((x, top + box_h / 2), ch, font=mark_font, fill=TEXT, anchor="lm")
        x += _width(ch, mark_font) + spacing


def _draw_cell(
    image: Image.Image,
    draw: ImageDraw.ImageDraw,
    left: int,
    top: int,
    rank: int,
    entry: dict[str, Any],
) -> None:
    """One entry: title, RKS and accuracy on the left, art and badges on the right."""
    _card(draw, [left, top, left + CELL_W, top + CELL_H])

    song_id = str(entry.get("song_id") or "")
    level = int(entry.get("level") or 0)
    level_color = LEVEL_COLORS[level] if 0 <= level < 4 else MUTED
    constant = float(entry.get("difficulty") or 0)

    art = _illustration(song_id)
    text_right = left + CELL_W - 20
    if art is not None:
        art_left = left + CELL_W - ILLUSTRATION_SIZE[0] - 18
        art_top = top + ILLUSTRATION_TOP
        _paste_rounded(image, art, (art_left, art_top))
        text_right = art_left - 16

    text_left = left + 20
    text_width = text_right - text_left

    # Prefer the display name over the raw id, matching the logotype on the
    # score sheet ("Distorted Fate" rather than "DistortedFate.Sakuzyo").
    display = str(entry.get("title") or song_id)

    name_font = _load_font(21, bold=True)
    draw.text((text_left, top + 32), _fit(display, name_font, text_width),
              font=name_font, fill=title_color(song_id), anchor="lm")

    # Single-song RKS, the headline number of the cell.
    rks_font = _load_font(38, mono=True)
    draw.text((text_left - 2, top + 80), f"{float(entry.get('rks') or 0):.4f}",
              font=rks_font, fill=TEXT, anchor="lm")

    # Score and accuracy, coloured by clear status.
    score = int(entry.get("score") or 0)
    accuracy = float(entry.get("accuracy") or 0)
    if score >= 1000000:
        acc_color = ACC_AP
    elif entry.get("full_combo"):
        acc_color = ACC_FC
    else:
        acc_color = ACC_PLAIN

    acc_font = _load_font(17, mono=True)
    draw.text((text_left, top + 124), f"{accuracy:.2f}%   {score:07d}",
              font=acc_font, fill=acc_color, anchor="lm")

    # Rank top-right, difficulty and chart constant bottom-right.
    draw.text((left + CELL_W - 18, top + 22), f"#{rank:02d}",
              font=_load_font(17, mono=True), fill=FAINT, anchor="rm")

    badge_font = _load_font(18, bold=True)
    badge = f"{LEVEL_NAMES[level] if 0 <= level < 4 else '?'} {constant:.1f}"
    draw.text((left + CELL_W - 18, top + CELL_H - 22), badge,
              font=badge_font, fill=level_color, anchor="rm")

    # An AP / FC on a hard chart gets a reaction, right-aligned on the score line.
    if earns_praise(level, constant) and (score >= 1000000 or entry.get("full_combo")):
        draw.text((text_right, top + 124), random.choice(PRAISE_PHRASES),
                  font=_load_font(18, bold=True), fill=PRAISE_COLOR, anchor="rm")


def _draw_b19_footer(
    draw: ImageDraw.ImageDraw,
    height: int,
    progress: Optional[Sequence[dict[str, Any]]],
    width: int,
    rks: Optional[float],
) -> None:
    """The closing quip, a summary line and the copyright."""
    baseline = height - MARGIN + 6

    quip = (
        QUIP_HIGH_RKS
        if rks is not None and rks >= QUIP_RKS_THRESHOLD
        else QUIP_DEFAULT
    )
    draw.text((MARGIN, baseline - 32), quip, font=_load_font(18), fill=MUTED, anchor="lm")

    if progress:
        played = sum(int(row.get("played") or 0) for row in progress)
        draw.text((MARGIN, baseline), f"已游玩 {played} 首",
                  font=_load_font(18), fill=MUTED, anchor="lm")

    draw.text((width - MARGIN, baseline), COPYRIGHT,
              font=_load_font(16), fill=FAINT, anchor="rm")


# ---------------------------------------------------------------------------
# Generic list card
# ---------------------------------------------------------------------------

class _Card:
    """A light card with a header band and a stack of rows."""

    WIDTH = 940
    PADDING = 26

    def __init__(self, title: str, subtitle: str = ""):
        self.title = title
        self.subtitle = subtitle
        self.rows: list[dict[str, Any]] = []
        self.footer: list[tuple[str, str]] = []
        self.note = ""

    # -- content ----------------------------------------------------------

    def add_row(
        self,
        index: str = "",
        title: str = "",
        badge: str = "",
        badge_color: tuple[int, int, int] = ACCENT,
        left: str = "",
        right: str = "",
        accent: Optional[tuple[int, int, int]] = None,
        title_color: Optional[tuple[int, int, int]] = None,
    ) -> None:
        self.rows.append({
            "mode": "score", "index": index, "title": title, "badge": badge,
            "badge_color": badge_color, "left": left, "right": right,
            "accent": accent, "title_color": title_color or TEXT,
        })

    def add_field(self, label: str, value: str, accent: bool = False) -> None:
        """A label/value row: label on the left, value right-aligned."""
        self.rows.append({
            "mode": "field", "label": label, "value": value,
            "accent": ACCENT if accent else None, "badge": "", "left": "", "right": "",
            "index": "", "title": "", "badge_color": ACCENT, "title_color": TEXT,
        })

    def add_footer(self, label: str, value: str) -> None:
        self.footer.append((label, value))

    def set_note(self, note: str) -> None:
        self.note = note

    # -- rendering --------------------------------------------------------

    def render(self) -> Image.Image:
        row_h, gap = 54, 8
        body = len(self.rows) * (row_h + gap)
        footer = len(self.footer) * 30 + 16 if self.footer else 0
        note = 34 if self.note else 0
        height = 108 + self.PADDING + body + footer + note + self.PADDING

        image = _background(self.WIDTH, height)
        draw = ImageDraw.Draw(image)

        draw.rectangle([0, 0, self.WIDTH, 108], fill=CARD)
        draw.line([(0, 108), (self.WIDTH, 108)], fill=CARD_EDGE)

        title_font = _load_font(30, bold=True)
        draw.text((self.PADDING, 44), _fit(self.title, title_font, self.WIDTH - 2 * self.PADDING),
                  font=title_font, fill=TEXT, anchor="lm")
        if self.subtitle:
            draw.text((self.PADDING, 76), self.subtitle, font=_load_font(18), fill=MUTED, anchor="lm")

        y = 108 + self.PADDING
        for position, row in enumerate(self.rows):
            _card(draw, [self.PADDING, y, self.WIDTH - self.PADDING, y + row_h], radius=10)
            if row["accent"]:
                draw.rounded_rectangle(
                    [self.PADDING, y, self.PADDING + 5, y + row_h], radius=3, fill=row["accent"],
                )
            if row["mode"] == "field":
                self._draw_field(draw, row, y, row_h)
            else:
                self._draw_score(draw, row, y, row_h, position)
            y += row_h + gap

        y = self._draw_footer(draw, y)
        if self.note:
            draw.text((self.PADDING + 8, y + 14), self.note, font=_load_font(16), fill=MUTED, anchor="lm")

        return image

    def _draw_score(
        self, draw: ImageDraw.ImageDraw, row: dict[str, Any], top: int, height: int, position: int
    ) -> None:
        middle = top + height // 2
        x = self.PADDING + 16

        if row["index"]:
            draw.text((x + 12, middle), row["index"], font=_load_font(20, mono=True),
                      fill=row["accent"] or MUTED, anchor="mm")
        x += 60

        badge_width = 0
        if row["badge"]:
            badge_font = _load_font(15, bold=True)
            badge_width = max(_width(row["badge"], badge_font) + 22, 44)
            draw.rounded_rectangle([x, middle - 13, x + badge_width, middle + 13],
                                   radius=7, fill=row["badge_color"])
            draw.text((x + badge_width / 2, middle), row["badge"], font=badge_font,
                      fill=(255, 255, 255), anchor="mm")
            x += badge_width + 14

        right_font = _load_font(21, mono=True)
        right_width = 0.0
        if row["right"]:
            right_width = _width(row["right"], right_font)
            draw.text((self.WIDTH - self.PADDING - 18, middle), row["right"], font=right_font,
                      fill=row["accent"] or TEXT, anchor="rm")

        space = self.WIDTH - self.PADDING - 18 - right_width - 22 - x
        title_font = _load_font(20)
        draw.text((x, middle - 6 if row["left"] else middle),
                  _fit(row["title"], title_font, space), font=title_font,
                  fill=row["title_color"], anchor="lm")

        if row["left"]:
            left_font = _font_for(row["left"], 17)
            draw.text((x, middle + 13), _fit(row["left"], left_font, space),
                      font=left_font, fill=MUTED, anchor="lm")

    def _draw_field(self, draw: ImageDraw.ImageDraw, row: dict[str, Any], top: int, height: int) -> None:
        middle = top + height // 2
        label_font = _load_font(18)
        value_font = _load_font(19, bold=True)

        draw.text((self.PADDING + 22, middle), row["label"], font=label_font, fill=MUTED, anchor="lm")
        space = self.WIDTH - 2 * self.PADDING - 44 - _width(row["label"], label_font) - 22
        draw.text((self.WIDTH - self.PADDING - 22, middle),
                  _fit(row["value"], value_font, space), font=value_font, fill=TEXT, anchor="rm")

    def _draw_footer(self, draw: ImageDraw.ImageDraw, y: int) -> int:
        if not self.footer:
            return y

        y += 8
        for label, value in self.footer:
            draw.text((self.PADDING + 8, y), label, font=_load_font(17),
                      fill=MUTED, anchor="lm")
            draw.text((self.WIDTH - self.PADDING - 8, y), value,
                      font=_load_font(19, mono=True), fill=TEXT, anchor="rm")
            y += 30

        return y

    # -- helpers for callers ----------------------------------------------

    @staticmethod
    def level_color(level: int) -> tuple[int, int, int]:
        return LEVEL_COLORS[level] if 0 <= level < 4 else MUTED


# ---------------------------------------------------------------------------
# Other renderers
# ---------------------------------------------------------------------------

def render_help(title: str, groups: Sequence[tuple[str, Sequence[tuple[str, str]]]]) -> str:
    """Help card: one section per group of commands."""
    card = _Card(title=title, subtitle="TLoH Bot")
    for group, commands in groups:
        card.add_row(title=group, title_color=ACCENT)
        for command, description in commands:
            card.add_row(title=f"  {command}", left=description)
    return _save(card.render(), "help")


def render_song(
    nickname: str,
    song_id: str,
    records: Sequence[dict[str, Any]],
    difficulty: Sequence[float],
) -> str:
    """Per-difficulty card for a single song, with the album art in the header."""
    card = _Card(title=song_id, subtitle=f"{nickname} · 历史最好成绩")

    for level in range(4):
        record = next((r for r in records if int(r.get("level", -1)) == level), None)
        constant = difficulty[level] if level < len(difficulty) else 0.0
        color = LEVEL_COLORS[level]

        if record is None:
            card.add_row(title=f"定数 {constant:.1f}" if constant else "未游玩",
                         badge=LEVEL_NAMES[level], badge_color=FAINT,
                         right="--", accent=FAINT)
            continue

        detail = f"{int(record.get('score') or 0):07d}   {float(record.get('accuracy') or 0):.2f}%"
        if int(record.get("score") or 0) >= 1000000:
            detail += "   AP"
        elif record.get("full_combo"):
            detail += "   FC"

        card.add_row(
            title=f"定数 {constant:.1f}" if constant else "定数未知",
            badge=LEVEL_NAMES[level], badge_color=color, left=detail,
            right=f"{float(record.get('rks') or 0):.4f}", accent=color,
        )

    return _save(card.render(), "song")


def render_status(
    nickname: str,
    region: str,
    bound_at: str,
    token_ok: bool,
    latest: Optional[dict[str, Any]],
    player_id: str,
) -> str:
    """Account card."""
    card = _Card(
        title=nickname or "未知玩家",
        subtitle=f"{'国际服' if region == 'global' else '国服'} · {player_id}",
    )

    card.add_field("登录状态", "有效" if token_ok else "已失效，请重新 pgr bind", accent=token_ok)
    card.add_field("绑定时间", bound_at or "未知")

    if latest:
        card.add_field("最近同步", str(latest.get("captured_at", ""))[:19])
        card.add_field("游戏内 RKS", f"{float(latest.get('ranking_score') or 0):.4f}", accent=True)
        card.add_field("存档 / 游戏版本",
                       f"{latest.get('save_version')} / {latest.get('game_version')}")
        card.add_field("课题模式段位", str(latest.get("challenge_mode_rank")))
    else:
        card.add_field("尚未同步过成绩", "发送 pgr update")

    return _save(card.render(), "status")


def render_history(points: Sequence[dict[str, Any]]) -> str:
    """RKS over time."""
    card = _Card(title="RKS 变化", subtitle=f"共 {len(points)} 条记录")

    if not points:
        card.add_row(title="暂无历史记录")
        return _save(card.render(), "history")

    values = [float(p.get("rks") or 0) for p in points]
    low, high = min(values), max(values)

    for index, point in enumerate(points):
        previous = values[index - 1] if index else None
        delta, color = "", TEXT
        if previous is not None and abs(values[index] - previous) > 1e-9:
            change = values[index] - previous
            delta = f"{change:+.4f}"
            color = ACC_FC if change > 0 else LEVEL_COLORS[2]

        card.add_row(
            title=str(point.get("captured_at", ""))[:10],
            badge=f"{values[index]:.4f}", badge_color=ACCENT,
            left=f"区间 {low:.2f} ~ {high:.2f}", right=delta,
            accent=color if delta else None,
        )

    return _save(card.render(), "history")


def render_info(song_id: str, info: Sequence[str], difficulty: Sequence[float]) -> str:
    """Song metadata card, fed by data/info.tsv."""
    card = _Card(title=song_id, subtitle=str(info[0]) if info else "")

    labels = ("曲名", "曲师", "画师", "谱师 EZ", "谱师 HD", "谱师 IN", "谱师 AT")
    for index, label in enumerate(labels):
        if index >= len(info) or not str(info[index]).strip():
            continue
        card.add_field(label, str(info[index]))

    constants = " / ".join(
        f"{LEVEL_NAMES[i]} {value:.1f}" for i, value in enumerate(difficulty[:4]) if value > 0
    )
    if constants:
        card.add_field("定数", constants, accent=True)

    return _save(card.render(), "info")


def render_progress(rows: Sequence[dict[str, Any]], nickname: str) -> str:
    """Per-difficulty clear / FC / AP counts."""
    card = _Card(title=f"{nickname} 的进度", subtitle="最新快照")

    for row in rows:
        level = int(row.get("level") or 0)
        color = LEVEL_COLORS[level] if 0 <= level < 4 else MUTED
        card.add_row(
            index=LEVEL_NAMES[level] if 0 <= level < 4 else "?",
            title=f"定数区间内 FC {row.get('full_combo') or 0}   AP {row.get('all_perfect') or 0}",
            badge=LEVEL_NAMES[level] if 0 <= level < 4 else "?",
            badge_color=color, right=str(row.get("played") or 0), accent=color,
        )

    card.set_note("右侧数字为已游玩曲目数")
    return _save(card.render(), "progress")


def render_board(song_id: str, level: int, rows: Sequence[dict[str, Any]]) -> str:
    """Leaderboard for one song and difficulty."""
    color = LEVEL_COLORS[level] if 0 <= level < 4 else ACCENT
    name = LEVEL_NAMES[level] if 0 <= level < 4 else "?"
    card = _Card(title=song_id, subtitle=f"{name} 难度排行榜 · 共 {len(rows)} 人")

    for position, row in enumerate(rows, start=1):
        detail = f"{int(row.get('score') or 0):07d}   {float(row.get('accuracy') or 0):.2f}%"
        if row.get("full_combo"):
            detail += "   FC"
        card.add_row(
            index=str(position), title=row.get("nickname") or row.get("player_id", ""),
            badge=name, badge_color=color, left=detail,
            right=f"{float(row.get('rks') or 0):.4f}", accent=color,
        )

    return _save(card.render(), "board")


def render_songs(titles: Sequence[str], subtitle: str = "") -> str:
    """Plain listing, used for search results."""
    card = _Card(title="曲目列表", subtitle=subtitle)
    for index, title in enumerate(titles, start=1):
        card.add_row(index=str(index), title=title)
    if not titles:
        card.add_row(title="没有匹配的曲目")
    return _save(card.render(), "list")


def render_message(title: str, lines: Sequence[str], subtitle: str = "") -> str:
    """Generic fallback so every reply can be an image."""
    card = _Card(title=title, subtitle=subtitle)
    for line in lines:
        card.add_row(title=line)
    return _save(card.render(), "msg")
