"""Share cards — the 1200x630 image a link shows when it is pasted anywhere.

Until Oct 2026 every share preview on the site was one of two things: the
network's ``og-preview.png`` (which still carried the no-advertising promise
the Oct 11 sponsor policy retired, and listed a ZH track three shows had
dropped) or a show's 3000x3000 podcast cover, which X, LinkedIn, Facebook,
Slack and iMessage all crop to a 1.91:1 strip through the middle of the
artwork. An episode shared from the blog looked exactly like every other
episode of that show.

This module owns three things:

* the renderers — :func:`render_network_card`, :func:`render_show_card`,
  :func:`render_page_card` and :func:`render_episode_card` — all drawn with
  PIL from the site's own fonts (DM Sans, Source Serif 4; bundled under
  ``assets/fonts`` so a runner renders what a laptop renders);
* the committed cards' paths (``assets/share/``), built by
  ``scripts/build_share_cards.py``;
* :func:`resolve_og_image`, the ONE decision about which card a page carries.
  ``base.html.j2`` calls it through a Jinja global, so a page that passes a
  square cover gets its show's card, a page that passes nothing gets its own
  page card or the network card, and anything else (an episode card, a
  landscape scene) passes through untouched. A new page is covered without a
  code change.

Episode cards are never committed — one per episode would be thousands of
JPEGs in git (landmine #1). run_show renders one per episode, uploads it to
R2 under ``share/<slug>/`` and records the URL in
``digests/<dir>/share_cards.json``; the blog post reads that record.

Text is never clipped mid-word: every block shrinks to fit, then wraps, and a
hook that still does not fit at the floor size ends on a whole word with an
ellipsis (a share card is a preview, not the title of record).
"""
from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass
from datetime import date as _date
from functools import lru_cache
from pathlib import Path
from typing import Iterable, Optional, Sequence
from urllib.parse import urlparse

from PIL import Image, ImageDraw, ImageFilter, ImageFont

logger = logging.getLogger(__name__)

ROOT = Path(__file__).resolve().parent.parent
FONTS_DIR = ROOT / "assets" / "fonts"
SHARE_DIR = ROOT / "assets" / "share"
MARK_PATH = SHARE_DIR / "_src" / "nerra-mark.png"

SITE = "https://nerranetwork.com"
WIDTH, HEIGHT = 1200, 630
JPEG_QUALITY = 84

# Palette — the site's tokens (styles/main.css).
BG = (11, 15, 26)
BG_ALT = (17, 22, 39)
PURPLE = (107, 71, 255)
CYAN = (0, 212, 255)
WHITE = (255, 255, 255)
TEXT_SECONDARY = (203, 213, 225)
TEXT_MUTED = (148, 163, 184)

NETWORK_NAME = "Nerra Network"
# The words are engine.brand's (Oct 18 2026); a card never types its own.
from engine.brand import (  # noqa: E402,F401
    NETWORK_PROMISE_SHORT, NETWORK_TAGLINE, NETWORK_TAGLINE_RU, network_promise,
)
NETWORK_DOMAIN = "nerranetwork.com"

# The record run_show writes beside a show's digests.
EPISODE_RECORD_NAME = "share_cards.json"
EPISODE_R2_PREFIX = "share"

_SANS_BOLD = FONTS_DIR / "DMSans-Bold.ttf"
_SANS_MEDIUM = FONTS_DIR / "DMSans-Medium.ttf"
_SERIF_BOLD = FONTS_DIR / "SourceSerif4-Bold.ttf"
_SERIF_SEMIBOLD = FONTS_DIR / "SourceSerif4-SemiBold.ttf"
# DM Sans has no Cyrillic. A string it cannot draw falls back to Golos Text
# (OFL, bundled — a system font would make a runner's card differ from a
# laptop's, and a differing card is rewritten into git every night), then to
# DejaVu for a script neither covers.
_FALLBACK_BOLD = FONTS_DIR / "GolosText-Bold.ttf"
_FALLBACK_REGULAR = FONTS_DIR / "GolosText-Medium.ttf"
_LAST_RESORT = Path("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf")

_RU_MONTHS = ("января", "февраля", "марта", "апреля", "мая", "июня", "июля",
              "августа", "сентября", "октября", "ноября", "декабря")


# ---------------------------------------------------------------------------
# Fonts and text fitting
# ---------------------------------------------------------------------------

@lru_cache(maxsize=256)
def _font(path: str, size: int) -> ImageFont.FreeTypeFont:
    try:
        return ImageFont.truetype(path, size)
    except OSError:
        logger.warning("share card font missing: %s", path)
        return ImageFont.load_default(size)


@lru_cache(maxsize=64)
def _notdef(path: str) -> bytes:
    return bytes(_font(path, 40).getmask("\U000F0000"))


def _covers(path: Path, text: str) -> bool:
    """True when every visible character of ``text`` has a glyph in ``path``."""
    if not path.is_file():
        return False
    nd = _notdef(str(path))
    font = _font(str(path), 40)
    return all(bytes(font.getmask(ch)) != nd for ch in set(text) if not ch.isspace())


def _pick(path: Path, text: str, fallback: Path) -> Path:
    for candidate in (path, fallback, _LAST_RESORT):
        if _covers(candidate, text):
            return candidate
    return path


def _text_width(font: ImageFont.FreeTypeFont, text: str) -> float:
    return font.getlength(text)


def _wrap(text: str, font: ImageFont.FreeTypeFont, max_width: int) -> list[str]:
    words = text.split()
    lines: list[str] = []
    line = ""
    for word in words:
        trial = f"{line} {word}".strip()
        if _text_width(font, trial) <= max_width or not line:
            line = trial
        else:
            lines.append(line)
            line = word
    if line:
        lines.append(line)
    return lines


def _shorten(text: str, font, max_width: int, max_lines: int) -> list[str]:
    """Wrap ``text``, shortening it word-safe through ``engine.titles``
    (the one owner of title limits) until it fits ``max_lines``."""
    from engine.titles import clip_words
    lines = _wrap(text, font, max_width)
    limit = len(text)
    while len(lines) > max_lines and limit > 8:
        limit = int(limit * 0.92)
        lines = _wrap(clip_words(text, limit), font, max_width)
    return lines[:max_lines]


@dataclass
class _Block:
    lines: list[str]
    font: ImageFont.FreeTypeFont
    line_height: int

    @property
    def height(self) -> int:
        return self.line_height * len(self.lines)


def _fit(text: str, path: Path, *, max_width: int, max_lines: int,
         start: int, floor: int, step: int = 2, leading: float = 1.14,
         max_height: Optional[int] = None, fallback: Path = _FALLBACK_BOLD) -> _Block:
    """Largest size from ``start`` down to ``floor`` at which ``text`` fits."""
    text = " ".join((text or "").split())
    path = _pick(path, text, fallback)
    size = start
    while True:
        font = _font(str(path), size)
        lines = _wrap(text, font, max_width)
        lh = int(round(size * leading))
        fits = len(lines) <= max_lines and (max_height is None or lh * len(lines) <= max_height)
        if fits or size <= floor:
            if not fits:
                cap = max_lines
                if max_height is not None:
                    cap = max(1, min(cap, max_height // max(1, lh)))
                lines = _shorten(text, font, max_width, cap)
            return _Block(lines=lines, font=font, line_height=lh)
        size -= step


def _draw_block(draw: ImageDraw.ImageDraw, block: _Block, x: int, y: int,
                fill, *, shadow: bool = False) -> int:
    for i, line in enumerate(block.lines):
        ly = y + i * block.line_height
        if shadow:
            draw.text((x + 2, ly + 2), line, font=block.font, fill=(0, 0, 0, 150))
        draw.text((x, ly), line, font=block.font, fill=fill)
    return y + block.height


def _tracked(draw, xy, text: str, font, fill, tracking: float = 0.12) -> float:
    """Letter-spaced small caps line (kickers). Returns the end x."""
    x, y = xy
    spacing = font.size * tracking
    for ch in text:
        draw.text((x, y), ch, font=font, fill=fill)
        x += font.getlength(ch) + spacing
    return x


# ---------------------------------------------------------------------------
# Colour
# ---------------------------------------------------------------------------

def _hex(color: str, default=PURPLE) -> tuple[int, int, int]:
    c = (color or "").strip().lstrip("#")
    if len(c) == 3:
        c = "".join(ch * 2 for ch in c)
    if not re.fullmatch(r"[0-9a-fA-F]{6}", c):
        return default
    return tuple(int(c[i:i + 2], 16) for i in (0, 2, 4))  # type: ignore[return-value]


def _luminance(rgb) -> float:
    def ch(v):
        v = v / 255
        return v / 12.92 if v <= 0.03928 else ((v + 0.055) / 1.055) ** 2.4
    r, g, b = rgb[:3]
    return 0.2126 * ch(r) + 0.7152 * ch(g) + 0.0722 * ch(b)


def contrast(a, b) -> float:
    la, lb = sorted((_luminance(a), _luminance(b)), reverse=True)
    return (la + 0.05) / (lb + 0.05)


def readable_on_dark(rgb, background=BG, minimum: float = 4.5) -> tuple[int, int, int]:
    """Blend a brand colour toward white until it reads as text on ``background``.

    Same rule as the site's ``--show-color-text``: a brand colour is a fill;
    as text on the dark surfaces it is lifted, never used raw.
    """
    r, g, b = rgb[:3]
    for t in range(0, 101, 5):
        mix = tuple(int(round(c + (255 - c) * t / 100)) for c in (r, g, b))
        if contrast(mix, background) >= minimum:
            return mix  # type: ignore[return-value]
    return WHITE


def _mix(a, b, t: float):
    return tuple(int(round(x + (y - x) * t)) for x, y in zip(a, b))


# ---------------------------------------------------------------------------
# Image helpers
# ---------------------------------------------------------------------------

def _canvas(color=BG) -> Image.Image:
    return Image.new("RGBA", (WIDTH, HEIGHT), color + (255,))


def _glow(img: Image.Image, center, radius: int, rgb, alpha: int) -> None:
    layer = Image.new("RGBA", img.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    cx, cy = center
    d.ellipse((cx - radius, cy - radius, cx + radius, cy + radius), fill=rgb + (alpha,))
    layer = layer.filter(ImageFilter.GaussianBlur(radius * 0.45))
    img.alpha_composite(layer)


def _cover_fill(src: Image.Image, size) -> Image.Image:
    """Scale and centre-crop ``src`` to exactly ``size``."""
    w, h = size
    sw, sh = src.size
    scale = max(w / sw, h / sh)
    resized = src.resize((max(w, int(round(sw * scale))), max(h, int(round(sh * scale)))),
                         Image.LANCZOS)
    left = (resized.width - w) // 2
    top = (resized.height - h) // 2
    return resized.crop((left, top, left + w, top + h))


def _inset(img: Image.Image, frac: float = 0.025) -> Image.Image:
    """Trim a cover's outer edge: several covers bake rounded black corners in."""
    dx, dy = int(img.width * frac), int(img.height * frac)
    return img.crop((dx, dy, img.width - dx, img.height - dy))


def _rounded(img: Image.Image, radius: int) -> Image.Image:
    img = img.convert("RGBA")
    mask = Image.new("L", img.size, 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, img.width - 1, img.height - 1),
                                           radius=radius, fill=255)
    img.putalpha(mask)
    return img


def _paste_tile(canvas: Image.Image, tile: Image.Image, xy, radius: int,
                *, shadow: bool = True, border: Optional[tuple] = None) -> None:
    x, y = xy
    if shadow:
        sh = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
        ImageDraw.Draw(sh).rounded_rectangle(
            (x + 6, y + 14, x + tile.width + 6, y + tile.height + 14),
            radius=radius, fill=(0, 0, 0, 140))
        canvas.alpha_composite(sh.filter(ImageFilter.GaussianBlur(18)))
    canvas.alpha_composite(_rounded(tile, radius), (x, y))
    if border:
        ImageDraw.Draw(canvas).rounded_rectangle(
            (x, y, x + tile.width - 1, y + tile.height - 1), radius=radius,
            outline=border, width=2)


def _open(path) -> Optional[Image.Image]:
    try:
        p = Path(path)
        if not p.is_absolute():
            p = ROOT / p
        if not p.is_file():
            return None
        with Image.open(p) as im:
            return im.convert("RGB")
    except Exception as exc:  # noqa: BLE001 - a bad image never blocks a card
        logger.warning("share card could not open %s: %s", path, exc)
        return None


@lru_cache(maxsize=8)
def _mark(size: int) -> Optional[Image.Image]:
    if not MARK_PATH.is_file():
        return None
    with Image.open(MARK_PATH) as im:
        return im.convert("RGBA").resize((size, size), Image.LANCZOS)


def _gradient_bar(img: Image.Image, y0: int, y1: int, left_rgb, right_rgb) -> None:
    d = ImageDraw.Draw(img)
    for x in range(WIDTH):
        d.line([(x, y0), (x, y1)], fill=_mix(left_rgb, right_rgb, x / (WIDTH - 1)) + (255,))


def _blurred_backdrop(cover: Image.Image, tint, darkness: float = 0.72) -> Image.Image:
    """A full-bleed, heavily blurred, darkened copy of a cover."""
    base = _cover_fill(cover, (WIDTH // 4, HEIGHT // 4)).filter(ImageFilter.GaussianBlur(6))
    base = base.resize((WIDTH, HEIGHT), Image.LANCZOS).filter(ImageFilter.GaussianBlur(24))
    base = base.convert("RGBA")
    shade = Image.new("RGBA", base.size, _mix(BG, tint, 0.12) + (int(255 * darkness),))
    base.alpha_composite(shade)
    return base


def _footer(img: Image.Image, *, right_text: str = NETWORK_DOMAIN,
            accent=CYAN, y: int = 552, tagline: str = NETWORK_TAGLINE) -> None:
    """Mark + network name, the tagline when it fits, the domain at the right."""
    d = ImageDraw.Draw(img)
    d.line([(56, y - 18), (WIDTH - 56, y - 18)], fill=(255, 255, 255, 38), width=1)
    mark = _mark(46)
    x = 56
    if mark is not None:
        img.alpha_composite(mark, (x, y - 4))
        x += 46 + 14
    name_font = _font(str(_SANS_BOLD), 26)
    d.text((x, y + 4), NETWORK_NAME, font=name_font, fill=WHITE)
    name_end = x + _text_width(name_font, NETWORK_NAME)
    rt = _fit(right_text, _SANS_MEDIUM, max_width=460, max_lines=1, start=24, floor=18,
              fallback=_FALLBACK_REGULAR)
    tw = _text_width(rt.font, rt.lines[0]) if rt.lines else 0
    right_x = WIDTH - 56 - tw
    d.text((right_x, y + 6), rt.lines[0] if rt.lines else "", font=rt.font, fill=accent)
    if tagline:
        # Oct 18 2026: the tagline signs every card, sized down until it fits
        # between the name and the address; a card it cannot fit carries none.
        tpath = _pick(_SANS_MEDIUM, tagline, _FALLBACK_REGULAR)
        for size in (21, 19, 17):
            tfont = _font(str(tpath), size)
            text = f"·  {tagline}"
            if name_end + 16 + _text_width(tfont, text) + 28 <= right_x:
                d.text((name_end + 16, y + 9 + (21 - size) // 2), text, font=tfont,
                       fill=TEXT_SECONDARY)
                break


def _finish(img: Image.Image) -> Image.Image:
    return img.convert("RGB")


def save_jpeg(img: Image.Image, path: Path) -> bool:
    """Write ``img`` as an optimised JPEG; True when the bytes changed.

    Rewriting a committed card with identical pixels would add a blob to git
    history on every build, so an unchanged card is left alone.
    """
    from io import BytesIO
    buf = BytesIO()
    img.convert("RGB").save(buf, "JPEG", quality=JPEG_QUALITY, optimize=True,
                            progressive=True, subsampling="4:2:0")
    data = buf.getvalue()
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.is_file() and path.read_bytes() == data:
        return False
    path.write_bytes(data)
    return True


# ---------------------------------------------------------------------------
# Renderers
# ---------------------------------------------------------------------------

def _covers_grid(img: Image.Image, covers: Sequence[Image.Image], *, x0: int, y0: int,
                 cols: int, size: int, gap: int, radius: int = 18) -> None:
    for i, cover in enumerate(covers):
        r, c = divmod(i, cols)
        tile = _cover_fill(_inset(cover), (size, size))
        _paste_tile(img, tile, (x0 + c * (size + gap), y0 + r * (size + gap)), radius,
                    border=(255, 255, 255, 30))


def render_network_card(*, show_count: int, covers: Sequence[Image.Image] = (),
                        flagship_covers: Sequence[Image.Image] = (),
                        promise: str = "") -> Image.Image:
    """The homepage and default card: the tagline as the headline, the
    promise under it, and the shows beside them — the two flagships
    (``engine.brand.FLAGSHIP_SHOW_SLUGS``) as large tiles over a row of the
    network's breadth, or a 3x3 grid when no flagship art is given."""
    img = _canvas()
    _glow(img, (180, 120), 360, PURPLE, 110)
    _glow(img, (1060, 560), 380, CYAN, 70)
    _gradient_bar(img, 0, 7, PURPLE, CYAN)
    d = ImageDraw.Draw(img)

    flagship_layout = len(flagship_covers) >= 2 and len(covers) >= 6
    has_grid = flagship_layout or len(covers) >= 9
    text_w = 590 if has_grid else 1000
    x, y = 64, 60
    mark = _mark(64)
    if mark is not None:
        img.alpha_composite(mark, (x, y))
        name_x = x + 64 + 18
    else:
        name_x = x
    d.text((name_x, y + 12), NETWORK_NAME, font=_font(str(_SANS_BOLD), 34), fill=WHITE)
    y += 64 + 34
    tag = _fit(NETWORK_TAGLINE, _SERIF_BOLD, max_width=text_w, max_lines=2, start=62,
               floor=44, leading=1.12)
    y = _draw_block(d, tag, x, y, WHITE) + 22
    body = promise or network_promise(show_count)
    prom = _fit(body, _SANS_MEDIUM, max_width=text_w, max_lines=5, start=24, floor=19,
                leading=1.38, fallback=_FALLBACK_REGULAR, max_height=520 - y - 8)
    _draw_block(d, prom, x, y, TEXT_SECONDARY)

    if flagship_layout:
        # Two large flagship tiles, then two rows of three smaller ones.
        small, gap = 124, 14
        x0 = WIDTH - 64 - (3 * small + 2 * gap)
        big = (3 * small + 2 * gap - gap) // 2
        _covers_grid(img, list(flagship_covers)[:2], x0=x0, y0=40, cols=2, size=big,
                     gap=gap, radius=22)
        _covers_grid(img, list(covers)[:6], x0=x0, y0=40 + big + gap, cols=3,
                     size=small, gap=gap, radius=16)
    elif has_grid:
        _covers_grid(img, list(covers)[:9], x0=716, y0=52, cols=3, size=136, gap=16)
    _footer(img, right_text=NETWORK_DOMAIN, tagline="")
    return _finish(img)


def render_show_card(*, name: str, tagline: str, schedule: str, cover: Optional[Image.Image],
                     brand_color: str = "", kicker: str = "", domain_path: str = "",
                     lang: str = "en") -> Image.Image:
    """One show: its artwork whole (never cropped to a strip), name, promise, cadence."""
    tint = _hex(brand_color)
    accent = readable_on_dark(tint)
    img = _blurred_backdrop(cover, tint) if cover is not None else _canvas()
    _glow(img, (300, 300), 320, tint, 90)
    _gradient_bar(img, 0, 7, tint, _mix(tint, CYAN, 0.5))
    d = ImageDraw.Draw(img)

    tile = 404
    tx, ty = 64, 62
    if cover is not None:
        _paste_tile(img, _cover_fill(_inset(cover), (tile, tile)), (tx, ty), 30,
                    border=(255, 255, 255, 40))
    x = tx + tile + 52 if cover is not None else 64
    text_w = WIDTH - x - 60

    kick = (kicker or "Podcast").upper()
    kfont = _font(str(_pick(_SANS_BOLD, kick, _FALLBACK_BOLD)), 21)
    title = _fit(name, _SERIF_BOLD, max_width=text_w, max_lines=2, start=66, floor=40)
    tag = (_fit(tagline, _SANS_MEDIUM, max_width=text_w, max_lines=3, start=30, floor=22,
                leading=1.28, fallback=_FALLBACK_REGULAR, max_height=170)
           if tagline else None)
    chip = 44 if schedule else 0
    total = 44 + title.height + 18 + ((tag.height + 24) if tag else 0) + chip
    # Centre the column on the artwork, never above the top margin.
    y = max(70, ty + tile // 2 - total // 2)
    _tracked(d, (x, y), kick, kfont, accent)
    y += 44
    y = _draw_block(d, title, x, y, WHITE, shadow=True) + 18
    if tag:
        y = _draw_block(d, tag, x, y, TEXT_SECONDARY) + 24
    if schedule:
        sfont = _font(str(_pick(_SANS_BOLD, schedule, _FALLBACK_BOLD)), 22)
        label = schedule if _text_width(sfont, schedule) <= text_w - 36 else schedule.split(",")[0]
        pw = int(_text_width(sfont, label)) + 36
        d.rounded_rectangle((x, y, x + pw, y + 44), radius=22, fill=tint + (235,))
        d.text((x + 18, y + 9), label, font=sfont,
               fill=WHITE if contrast(WHITE, tint) >= 3 else BG)
    _footer(img, right_text=f"{NETWORK_DOMAIN}/{domain_path}" if domain_path else NETWORK_DOMAIN,
            accent=accent, tagline=NETWORK_TAGLINE_RU if lang == "ru" else NETWORK_TAGLINE)
    return _finish(img)


def render_page_card(*, kicker: str, title: str, subtitle: str = "",
                     covers: Sequence[Image.Image] = (), accent_color: str = "",
                     domain_path: str = "") -> Image.Image:
    """A site page (topic hub, Mira, Personal, explore…): title, one line, its shows."""
    tint = _hex(accent_color, PURPLE)
    accent = readable_on_dark(tint)
    img = _canvas()
    _glow(img, (200, 160), 360, tint, 100)
    _glow(img, (1080, 600), 360, CYAN, 55)
    _gradient_bar(img, 0, 7, tint, CYAN)
    d = ImageDraw.Draw(img)

    covers = list(covers)[:4]
    grid = None
    if covers:
        n = len(covers)
        size = 196 if n >= 3 else 210
        cols = 2 if n >= 2 else 1
        rows = (n + cols - 1) // cols
        gw = cols * size + (cols - 1) * 18
        gh = rows * size + (rows - 1) * 18
        grid = (WIDTH - 72 - gw, max(36, (520 - gh) // 2 + 14), cols, size)
        text_w = grid[0] - 64 - 44
    else:
        # No artwork: the mark, large and faint, holds the right side.
        mark = _mark(240)
        if mark is not None:
            faint = mark.copy()
            faint.putalpha(faint.getchannel("A").point(lambda a: int(a * 0.32)))
            img.alpha_composite(faint, (WIDTH - 72 - 240, 150))
        text_w = 760

    kick = kicker.upper()
    kfont = _font(str(_pick(_SANS_BOLD, kick, _FALLBACK_BOLD)), 22)
    t = _fit(title, _SERIF_BOLD, max_width=text_w, max_lines=3, start=70, floor=40,
             max_height=250)
    s_block = (_fit(subtitle, _SANS_MEDIUM, max_width=text_w, max_lines=3, start=30,
                    floor=22, leading=1.3, fallback=_FALLBACK_REGULAR, max_height=140)
               if subtitle else None)
    total = 50 + t.height + ((20 + s_block.height) if s_block else 0)
    y = max(56, (510 - total) // 2 + 8)
    _tracked(d, (64, y), kick, kfont, accent)
    y += 50
    y = _draw_block(d, t, 64, y, WHITE) + 20
    if s_block:
        _draw_block(d, s_block, 64, y, TEXT_SECONDARY)
    if grid:
        _covers_grid(img, covers, x0=grid[0], y0=grid[1], cols=grid[2], size=grid[3],
                     gap=18, radius=22)
    # A card whose headline IS the tagline does not sign with it again.
    _footer(img, right_text=f"{NETWORK_DOMAIN}/{domain_path}" if domain_path else NETWORK_DOMAIN,
            accent=accent, tagline="" if title == NETWORK_TAGLINE else NETWORK_TAGLINE)
    return _finish(img)


def episode_meta_line(episode_num, date_str: str, lang: str = "en") -> str:
    """'Episode 612 · October 18, 2026' (Russian shows: 'Выпуск 612 · 18 октября 2026')."""
    parts = []
    if episode_num:
        parts.append(f"Выпуск {episode_num}" if lang == "ru" else f"Episode {episode_num}")
    try:
        d = _date.fromisoformat(str(date_str)[:10])
        parts.append(f"{d.day} {_RU_MONTHS[d.month - 1]} {d.year}" if lang == "ru"
                     else f"{d.strftime('%B')} {d.day}, {d.year}")
    except (TypeError, ValueError):
        pass
    return " · ".join(parts)


def render_episode_card(*, show_name: str, hook: str, episode_num=None, date_str: str = "",
                        cover: Optional[Image.Image] = None, scene: Optional[Image.Image] = None,
                        brand_color: str = "", lang: str = "en") -> Image.Image:
    """One episode: its own scene (or its show's art), the hook, the show, the date."""
    tint = _hex(brand_color)
    accent = readable_on_dark(tint)
    if scene is not None:
        img = _cover_fill(scene, (WIDTH, HEIGHT)).convert("RGBA")
        # Left-to-right scrim: text column dark enough for 4.5:1 over any scene.
        scrim = Image.new("RGBA", img.size, (0, 0, 0, 0))
        sd = ImageDraw.Draw(scrim)
        for x in range(WIDTH):
            t = min(1.0, x / 900)
            a = int(236 - (236 - 70) * (t ** 1.6))
            sd.line([(x, 0), (x, HEIGHT)], fill=BG + (a,))
        img.alpha_composite(scrim)
        bottom = Image.new("RGBA", img.size, (0, 0, 0, 0))
        bd = ImageDraw.Draw(bottom)
        for yy in range(470, HEIGHT):
            bd.line([(0, yy), (WIDTH, yy)], fill=BG + (int(235 * (yy - 470) / 160),))
        img.alpha_composite(bottom)
        text_w = 780
    elif cover is not None:
        img = _blurred_backdrop(cover, tint, darkness=0.78)
        _glow(img, (240, 200), 320, tint, 80)
        text_w = 1072
    else:
        img = _canvas()
        _glow(img, (240, 200), 360, tint, 110)
        _glow(img, (1080, 600), 360, CYAN, 50)
        text_w = 1072
    _gradient_bar(img, 0, 7, tint, _mix(tint, CYAN, 0.5))
    d = ImageDraw.Draw(img)

    x, y = 64, 52
    if cover is not None:
        _paste_tile(img, _cover_fill(_inset(cover), (84, 84)), (x, y), 16, shadow=False,
                    border=(255, 255, 255, 60))
        tx = x + 84 + 20
    else:
        tx = x
    name = _fit(show_name, _SANS_BOLD, max_width=text_w - (tx - x), max_lines=1, start=28,
                floor=20)
    d.text((tx, y + 8), name.lines[0] if name.lines else "", font=name.font, fill=WHITE)
    meta = episode_meta_line(episode_num, date_str, lang)
    if meta:
        mfont = _font(str(_pick(_SANS_MEDIUM, meta, _FALLBACK_REGULAR)), 22)
        d.text((tx, y + 48), meta, font=mfont, fill=accent)

    hook_block = _fit(hook, _SERIF_BOLD, max_width=text_w, max_lines=4, start=60, floor=36,
                      leading=1.16, max_height=322)
    hy = 170 + max(0, (322 - hook_block.height) // 2)
    d.rectangle((x - 2, hy + 8, x + 3, hy + hook_block.height - 10), fill=tint + (255,))
    _draw_block(d, hook_block, x + 26, hy, WHITE, shadow=scene is not None)
    _footer(img, right_text="Слушать на nerranetwork.com" if lang == "ru"
            else f"Listen at {NETWORK_DOMAIN}", accent=accent,
            tagline=NETWORK_TAGLINE_RU if lang == "ru" else NETWORK_TAGLINE)
    return _finish(img)


# ---------------------------------------------------------------------------
# Paths, records and the og:image decision
# ---------------------------------------------------------------------------

def network_card_path() -> Path:
    return SHARE_DIR / "network.jpg"


def show_card_path(slug: str) -> Path:
    return SHARE_DIR / "shows" / f"{slug}.jpg"


def page_card_path(key: str) -> Path:
    return SHARE_DIR / "pages" / f"{key}.jpg"


MANIFEST_PATH = SHARE_DIR / "manifest.json"


@lru_cache(maxsize=1)
def _manifest_alts() -> dict:
    """Card path -> alt text, written by scripts/build_share_cards.py."""
    try:
        data = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
        return data.get("alt") or {}
    except (OSError, ValueError):
        return {}


def card_alt(path: Path, default: str = "") -> str:
    try:
        rel = path.relative_to(ROOT).as_posix()
    except ValueError:
        rel = str(path)
    return _manifest_alts().get(rel) or default


def _url(path: Path) -> str:
    return f"{SITE}/{path.relative_to(ROOT).as_posix()}"


def page_key_for_path(path: str) -> str:
    """'topics/space.html' -> 'topics-space'; 'mira.html' -> 'mira';
    'blog/index.html' and 'blog/' -> 'blog'; the homepage -> ''."""
    p = (path or "").strip("/")
    p = re.sub(r"(^|/)index\.html$", "", p).strip("/")
    if p.endswith(".html"):
        p = p[:-5]
    return re.sub(r"[^a-z0-9]+", "-", p.lower()).strip("-")


def _cover_index(shows: dict) -> dict[str, str]:
    """Cover file stem -> show slug (covers ship as .jpg plus -400/-800 .webp)."""
    out: dict[str, str] = {}
    for slug, cfg in shows.items():
        img = (cfg or {}).get("podcast_image") or ""
        if img:
            out[Path(img).stem.lower()] = slug
    return out


def _cover_slug(url: str, shows: dict) -> str:
    if "covers/" not in (url or ""):
        return ""
    stem = Path(urlparse(url).path).stem.lower()
    stem = re.sub(r"-(400|800)$", "", stem)
    return _cover_index(shows).get(stem, "")


def resolve_og_image(og_image: str = "", canonical_url: str = "", *,
                     shows: Optional[dict] = None, alt: str = "") -> dict:
    """Which card a page carries: ``{"url", "width", "height", "alt"}``.

    * a share card or any non-cover image passes through (dimensions unknown
      unless it is one of ours);
    * a square show cover becomes that show's card when the card exists;
    * nothing becomes the page's own card, else the network card.
    """
    shows = shows or {}
    og_image = (og_image or "").strip()

    def card(path: Path, default_alt: str) -> dict:
        return {"url": _url(path), "width": WIDTH, "height": HEIGHT,
                "alt": alt or card_alt(path, default_alt)}

    if og_image and "covers/" not in og_image and not og_image.endswith("og-preview.png"):
        is_card = "/share/" in og_image
        return {"url": og_image, "width": WIDTH if is_card else None,
                "height": HEIGHT if is_card else None, "alt": alt}
    slug = _cover_slug(og_image, shows)
    if slug and show_card_path(slug).is_file():
        name = (shows.get(slug) or {}).get("name", "")
        return card(show_card_path(slug), f"{name} on {NETWORK_NAME}" if name else NETWORK_NAME)
    if not og_image or og_image.endswith("og-preview.png"):
        path = urlparse(canonical_url).path if canonical_url else ""
        key = page_key_for_path(path)
        if key and page_card_path(key).is_file():
            return card(page_card_path(key), f"{NETWORK_NAME}: {key.replace('-', ' ')}")
        if network_card_path().is_file():
            return card(network_card_path(), f"{NETWORK_NAME} — {NETWORK_TAGLINE}")
    return {"url": og_image or f"{SITE}/assets/og-preview.png", "width": None,
            "height": None, "alt": alt}


def episode_record_path(digest_dir: Path) -> Path:
    return Path(digest_dir) / EPISODE_RECORD_NAME


def load_episode_cards(digest_dir: Path) -> dict:
    path = episode_record_path(digest_dir)
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def episode_card_url(digest_dir: Path, episode_num) -> str:
    """The recorded card URL for an episode, or ''."""
    try:
        key = str(int(episode_num))
    except (TypeError, ValueError):
        return ""
    entry = load_episode_cards(digest_dir).get(key) or {}
    return entry.get("url", "") if isinstance(entry, dict) else ""


def record_episode_card(digest_dir: Path, episode_num, url: str, *, date_str: str = "",
                        source: str = "") -> None:
    """Add or replace one episode's entry (sorted keys: a stable diff)."""
    data = load_episode_cards(digest_dir)
    data[str(int(episode_num))] = {"url": url, "date": date_str, "source": source}
    ordered = dict(sorted(data.items(), key=lambda kv: int(kv[0]) if kv[0].isdigit() else 0))
    path = episode_record_path(digest_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(ordered, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")


def episode_r2_key(slug: str, episode_num, source: str) -> str:
    """``share/<slug>/ep612-scene.jpg``: a new source never reuses a cached URL."""
    return f"{EPISODE_R2_PREFIX}/{slug}/ep{int(episode_num):03d}-{source}.jpg"


def cover_images(paths: Iterable[str]) -> list[Image.Image]:
    out = []
    for p in paths:
        im = _open(p)
        if im is not None:
            out.append(im)
    return out


# ---------------------------------------------------------------------------
# Episode cards (run_show + the backfill)
# ---------------------------------------------------------------------------

def _clean_hook(hook: str) -> str:
    from engine.titles import SHARE_CARD_HOOK_MAX, clip_words
    try:
        from engine.utils import strip_speech_tags
        hook = strip_speech_tags(hook or "")
    except Exception:  # noqa: BLE001
        hook = hook or ""
    hook = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", hook)       # [label](url) -> label
    hook = re.sub(r"[*_`#>]+", "", hook)
    hook = re.sub(r"^\s*(HOOK|Hook)\s*:\s*", "", hook)
    return clip_words(" ".join(hook.split()), SHARE_CARD_HOOK_MAX)


def _registry_entry(slug: str) -> dict:
    try:
        from generate_html import NETWORK_SHOWS
        return dict(NETWORK_SHOWS.get(slug) or {})
    except Exception:  # noqa: BLE001 - a card is never worth a failed import
        return {}


def episode_card_for(config, *, episode_num, hook: str, date_str: str = "",
                     scene=None, scene_path=None, out_dir: Optional[Path] = None,
                     upload: bool = True) -> str:
    """Render, upload and record one episode's share card. Never raises.

    Returns the public URL (``upload=True``), the local path (``upload=False``)
    or ``""`` — a members-only show, no hook, no R2 credentials, any failure.
    The record is only written for an uploaded card, so a page never points
    at a URL that was not put.
    """
    slug = getattr(config, "slug", "") or ""
    try:
        from engine.access import access_mode
        if access_mode(config) == "members_only":
            return ""  # a members episode has no public page to preview
        text = _clean_hook(hook)
        if not (slug and text and episode_num):
            return ""
        meta = _registry_entry(slug)
        cover = _open(meta.get("podcast_image") or "") if meta.get("podcast_image") else None
        if scene is None and scene_path:
            scene = _open(scene_path)
        try:
            from engine.show_lang import page_lang
            lang = page_lang(slug)
        except Exception:  # noqa: BLE001
            lang = "en"
        img = render_episode_card(
            show_name=meta.get("name") or getattr(config, "name", slug),
            hook=text, episode_num=int(episode_num), date_str=str(date_str or ""),
            cover=cover, scene=scene, brand_color=meta.get("brand_color") or "", lang=lang)
        out = Path(out_dir or (ROOT / "outputs" / "share_cards"))
        source = "scene" if scene is not None else "art"
        local = out / f"{slug}-ep{int(episode_num):03d}-{source}.jpg"
        save_jpeg(img, local)
        if not upload:
            return str(local)

        storage = getattr(config, "storage", None)
        if not storage or getattr(storage, "provider", "") != "r2":
            return ""
        import os
        endpoint = os.getenv(storage.endpoint_env, "")
        access_key = os.getenv(storage.access_key_env, "")
        secret_key = os.getenv(storage.secret_key_env, "")
        if not (endpoint and access_key and secret_key):
            logger.info("[%s] share card: R2 credentials unset, not uploaded", slug)
            return ""
        from engine.storage import upload_to_r2
        url = upload_to_r2(local, episode_r2_key(slug, episode_num, source),
                           bucket=storage.bucket, endpoint_url=endpoint,
                           access_key=access_key, secret_key=secret_key,
                           public_base_url=storage.public_base_url,
                           content_type="image/jpeg")
        if not url:
            return ""
        digest_dir = ROOT / config.episode.output_dir
        record_episode_card(digest_dir, episode_num, url, date_str=str(date_str or ""),
                            source=source)
        logger.info("[%s] share card ep%s (%s) -> %s", slug, episode_num, source, url)
        return url
    except Exception as exc:  # noqa: BLE001 - a share card never blocks a publish
        logger.warning("[%s] share card for ep%s failed (non-fatal): %s", slug, episode_num, exc)
        return ""
