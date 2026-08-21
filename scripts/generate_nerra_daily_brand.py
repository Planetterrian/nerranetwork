#!/usr/bin/env python3
"""Generate the Nerra Daily cover art (deterministic, PIL-only, $0).

Brand: "The Day Dial" — a dark field in the network's palette with a
rising cyan arc on the horizon and a ring of tick marks, one per show in
the edition's rundown: the whole network, turned through in one day.
Mira is credited on the cover (she anchors the edition).

Outputs (idempotent):
  assets/covers/nerra-daily.jpg        3000x3000 podcast cover
  assets/covers/nerra-daily.webp       full-size WebP variant
  assets/covers/nerra-daily-800.webp   800px WebP variant
  assets/covers/nerra-daily-400.webp   400px WebP variant

Run from repo root:  python scripts/generate_nerra_daily_brand.py
"""

from __future__ import annotations

import math
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

ROOT = Path(__file__).resolve().parent.parent

SIZE = 3000
NIGHT = (7, 14, 26)          # #070E1A  field base
DUSK = (13, 30, 51)          # #0D1E33  gradient top
NERRA_CYAN = (0, 212, 255)   # #00D4FF  the network accent
CYAN_DEEP = (0, 122, 163)    # #007AA3  arc shading
SLATE = (148, 179, 199)      # secondary text
WHITE = (245, 250, 253)      # primary text

FONT_BOLD = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
FONT_BOOK = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"

#: One tick per show in the EN edition rundown (engine.daily_edition).
TICK_COUNT = 13


def _vertical_gradient(size: int, top: tuple, bottom: tuple) -> Image.Image:
    strip = Image.new("RGB", (1, size))
    for y in range(size):
        t = y / (size - 1)
        strip.putpixel((0, y), tuple(
            round(top[c] + (bottom[c] - top[c]) * t) for c in range(3)))
    return strip.resize((size, size))


def _tracked_text(draw: ImageDraw.ImageDraw, y: float, text: str,
                  font: ImageFont.FreeTypeFont, fill: tuple,
                  tracking: int, center_x: float) -> None:
    widths = [draw.textlength(ch, font=font) for ch in text]
    total = sum(widths) + tracking * (len(text) - 1)
    x = center_x - total / 2
    for ch, w in zip(text, widths):
        draw.text((x, y), ch, font=font, fill=fill)
        x += w + tracking


def build_cover() -> Image.Image:
    img = _vertical_gradient(SIZE, DUSK, NIGHT)
    draw = ImageDraw.Draw(img, "RGBA")
    cx = SIZE / 2

    # Horizon glow — the day rising behind the wordmark.
    horizon_y = SIZE * 0.615
    glow = Image.new("L", (SIZE, SIZE), 0)
    gd = ImageDraw.Draw(glow)
    gd.ellipse([cx - 1150, horizon_y - 420, cx + 1150, horizon_y + 420],
               fill=120)
    glow = glow.filter(ImageFilter.GaussianBlur(260))
    img.paste(Image.new("RGB", (SIZE, SIZE), CYAN_DEEP), (0, 0), glow)

    # The dial: a broad arc over the horizon with one tick per show.
    radius = SIZE * 0.34
    arc_box = [cx - radius, horizon_y - radius, cx + radius, horizon_y + radius]
    draw.arc(arc_box, start=205, end=335, fill=NERRA_CYAN + (235,), width=26)
    draw.arc([b + s for b, s in zip(arc_box, (-52, -52, 52, 52))],
             start=213, end=327, fill=NERRA_CYAN + (60,), width=10)
    for i in range(TICK_COUNT):
        ang = math.radians(205 + (335 - 205) * i / (TICK_COUNT - 1))
        inner, outer = radius + 66, radius + 148
        bright = 255 if i == TICK_COUNT - 1 else 150
        draw.line(
            [cx + math.cos(ang) * inner, horizon_y + math.sin(ang) * inner,
             cx + math.cos(ang) * outer, horizon_y + math.sin(ang) * outer],
            fill=NERRA_CYAN + (bright,), width=20 if i == TICK_COUNT - 1 else 14)
    # The risen point — today.
    ang = math.radians(335)
    px, py = cx + math.cos(ang) * radius, horizon_y + math.sin(ang) * radius
    dot = Image.new("L", (SIZE, SIZE), 0)
    ImageDraw.Draw(dot).ellipse([px - 90, py - 90, px + 90, py + 90], fill=200)
    dot = dot.filter(ImageFilter.GaussianBlur(46))
    img.paste(Image.new("RGB", (SIZE, SIZE), NERRA_CYAN), (0, 0), dot)
    draw.ellipse([px - 34, py - 34, px + 34, py + 34], fill=WHITE)

    # Wordmark.
    f_kicker = ImageFont.truetype(FONT_BOLD, 96)
    f_main = ImageFont.truetype(FONT_BOLD, 430)
    f_sub = ImageFont.truetype(FONT_BOOK, 104)
    f_host = ImageFont.truetype(FONT_BOOK, 88)
    _tracked_text(draw, SIZE * 0.205, "THE NERRA NETWORK", f_kicker,
                  NERRA_CYAN, 30, cx)
    _tracked_text(draw, SIZE * 0.275, "NERRA", f_main, WHITE, 44, cx)
    _tracked_text(draw, SIZE * 0.425, "DAILY", f_main, WHITE, 44, cx)
    _tracked_text(draw, SIZE * 0.755, "EVERY SHOW · ONE DAILY LISTEN", f_sub,
                  SLATE, 18, cx)
    _tracked_text(draw, SIZE * 0.812, "with Mira", f_host, NERRA_CYAN, 8, cx)
    return img


def main() -> int:
    out_dir = ROOT / "assets" / "covers"
    out_dir.mkdir(parents=True, exist_ok=True)
    img = build_cover()
    img.save(out_dir / "nerra-daily.jpg", quality=92, optimize=True)
    img.save(out_dir / "nerra-daily.webp", quality=86, method=6)
    for px in (800, 400):
        img.resize((px, px), Image.LANCZOS).save(
            out_dir / f"nerra-daily-{px}.webp", quality=84, method=6)
    print(f"wrote {out_dir}/nerra-daily.jpg (+3 webp variants)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
