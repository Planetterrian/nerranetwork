#!/usr/bin/env python3
"""Generate cover art for the Sep 2026 new shows (deterministic, PIL-only, $0).

One template, many shows — the Nerra Daily "dial" approach generalized
(docs/new_shows_plan_2026_09_22.md §5b). Every cover shares the network
field (#070E1A → #0D1E33), the "THE NERRA NETWORK" eyebrow, the title
typography and a horizon glow; what changes per show is the ACCENT colour
(from the registry's ``theme_color``) and one simple geometric GLYPH that
names the show's subject. Consistency is the branding: on a grid of
eighteen-plus covers the family should read as one network.

Outputs per slug (idempotent):
  assets/covers/<slug-hyphen>.jpg          3000x3000 podcast cover
  assets/covers/<slug-hyphen>.webp         full-size WebP
  assets/covers/<slug-hyphen>-800.webp     800px WebP
  assets/covers/<slug-hyphen>-400.webp     400px WebP

Run from repo root:
  python scripts/generate_show_brand.py --slug ai_chips
  python scripts/generate_show_brand.py --all
"""

from __future__ import annotations

import argparse
import math
from dataclasses import dataclass
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

ROOT = Path(__file__).resolve().parent.parent

SIZE = 3000
NIGHT = (7, 14, 26)          # #070E1A  field base
DUSK = (13, 30, 51)          # #0D1E33  gradient top
NERRA_CYAN = (0, 212, 255)   # #00D4FF  the network accent
SLATE = (148, 179, 199)      # secondary text
WHITE = (245, 250, 253)      # primary text

FONT_BOLD = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
FONT_BOOK = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"


@dataclass(frozen=True)
class CoverSpec:
    title_lines: tuple            # one or two big lines
    tagline: str                  # small caps line under the glyph
    host_line: str                # "with Patrick" / "with Mira"
    accent: tuple                 # RGB accent for glyph + host line
    glyph: str                    # die | bars | chain | rings | sectors | place | commits | dial
    glyph_arg: int = 0            # glyph-specific (e.g. highlighted sector)


def _hex(h: str) -> tuple:
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def _lift(rgb: tuple, amount: float = 0.45) -> tuple:
    """Lighten a brand colour so it reads as a glyph on the dark field.

    Registry brand colours are chosen for >=4.5:1 on WHITE, which makes
    them too dark to see on #070E1A; the cover uses a lifted tint.
    """
    return tuple(round(c + (255 - c) * amount) for c in rgb)


# Per-show specs. Accents come from the registry colours in
# docs/new_shows_plan_2026_09_22.md §5a (lifted for the dark field).
SPECS: dict[str, CoverSpec] = {
    "ai_chips": CoverSpec(("AI CHIPS", "& DATA CENTRES"), "SILICON · SYSTEMS · SITES · POWER",
                          "with Patrick", _lift(_hex("#4338CA"), 0.5), "die"),
    "mag7": CoverSpec(("MAG 7", "DAILY"), "THE SEVEN LARGEST US COMPANIES · ONE DESK",
                      "with Patrick", _hex("#F59E0B"), "bars"),
    "peptides": CoverSpec(("PEPTIDES", "WEEKLY"), "EDUCATION · EVIDENCE · NEVER DOSING",
                          "with Patrick", _lift(_hex("#9D174D"), 0.45), "chain"),
    "longevity": CoverSpec(("LONGEVITY", "WEEKLY"), "THE SCIENCE OF AGING, READ CAREFULLY",
                           "with Patrick", _lift(_hex("#3F6212"), 0.5), "rings"),
    # Phase 2b: a probability gauge — the price read as a forecast.
    "prediction_markets": CoverSpec(("PREDICTION", "MARKETS DAILY"),
                                    "THE LAW · THE VENUES · HOW IT WORKS",
                                    "with Patrick", _lift(_hex("#A21CAF"), 0.4), "gauge"),
    # Local strand (plan §5b): a horizon with one place mark. glyph_arg picks
    # the ridge — 0 the North Shore mountains over water, 1 the long, low
    # Niagara Escarpment rise of Blue Mountain behind the bay.
    "vancouver": CoverSpec(("VANCOUVER", "DAILY NEWS"), "THE MORNING BRIEF FOR METRO VANCOUVER",
                           "with Mira, AI host", _lift(_hex("#0D6E8C"), 0.4), "place", 0),
    "collingwood": CoverSpec(("COLLINGWOOD", "WEEKLY"), "THE WEEK AROUND THE SOUTH GEORGIAN BAY",
                             "with Mira, AI host", _lift(_hex("#7C2D12"), 0.45), "place", 1),
}

# Phase 3: the Omni View desks. The family colour is Omni View's blue; the
# desk accent (engine.omni_desks) lights its region on the globe.
_DESK_TITLES = {
    "omni_view_europe": (("OMNI VIEW", "EUROPE"), "ONE REGION, EVERY DAY"),
    "omni_view_asia_pacific": (("OMNI VIEW", "ASIA PACIFIC"), "ONE REGION, EVERY DAY"),
    "omni_view_africa_mideast": (("OMNI VIEW", "AFRICA & MIDDLE EAST"), "ONE REGION, EVERY DAY"),
    "omni_view_latam": (("OMNI VIEW", "CENTRAL & SOUTH AMERICA"), "ONE REGION, EVERY DAY"),
    "omni_view_north_america": (("OMNI VIEW", "NORTH AMERICA"), "ONE REGION, EVERY DAY"),
}


def _register_desk_specs() -> None:
    import sys as _sys
    _sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from engine.omni_desks import DESKS
    for d in DESKS:
        title, sub = _DESK_TITLES[d.slug]
        SPECS[d.slug] = CoverSpec(title, sub, "with Mira, AI host",
                                  _lift(_hex(d.accent), 0.35), "globe", d.glyph_arg)
    SPECS["omni_view_world"] = CoverSpec(("OMNI VIEW", "TOP WORLD NEWS"), "THE TEN THAT MATTER MOST TODAY",
                                         "with Mira, AI host", _lift(_hex("#0B6FD6"), 0.35), "globe", 5)


_register_desk_specs()


def _vertical_gradient(size: int, top: tuple, bottom: tuple) -> Image.Image:
    strip = Image.new("RGB", (1, size))
    for y in range(size):
        t = y / (size - 1)
        strip.putpixel((0, y), tuple(
            round(top[c] + (bottom[c] - top[c]) * t) for c in range(3)))
    return strip.resize((size, size))


def _tracked_text(draw, y, text, font, fill, tracking, center_x):
    widths = [draw.textlength(ch, font=font) for ch in text]
    total = sum(widths) + tracking * (len(text) - 1)
    x = center_x - total / 2
    for ch, w in zip(text, widths):
        draw.text((x, y), ch, font=font, fill=fill)
        x += w + tracking


def _fit_font(draw, text, path, start, max_width, tracking):
    size = start
    while size > 120:
        font = ImageFont.truetype(path, size)
        width = sum(draw.textlength(ch, font=font) for ch in text) + tracking * (len(text) - 1)
        if width <= max_width:
            return font
        size -= 10
    return ImageFont.truetype(path, size)


def _glow(img, box, color, blur, fill=150):
    mask = Image.new("L", (SIZE, SIZE), 0)
    ImageDraw.Draw(mask).ellipse(box, fill=fill)
    mask = mask.filter(ImageFilter.GaussianBlur(blur))
    img.paste(Image.new("RGB", (SIZE, SIZE), color), (0, 0), mask)


def _draw_glyph(img, draw, spec: CoverSpec, cx: float, cy: float) -> None:
    a = spec.accent
    if spec.glyph == "die":
        # A chip die with pins on four sides and a glowing core.
        half = 300
        draw.rounded_rectangle([cx - half, cy - half, cx + half, cy + half],
                               radius=40, outline=a + (255,), width=22)
        draw.rectangle([cx - 150, cy - 150, cx + 150, cy + 150], fill=a + (70,))
        for i in range(7):
            off = -240 + i * 80
            for x0, y0, x1, y1 in (
                (cx + off, cy - half - 110, cx + off, cy - half - 20),
                (cx + off, cy + half + 20, cx + off, cy + half + 110),
                (cx - half - 110, cy + off, cx - half - 20, cy + off),
                (cx + half + 20, cy + off, cx + half + 110, cy + off),
            ):
                draw.line([x0, y0, x1, y1], fill=a + (200,), width=18)
        _glow(img, [cx - 120, cy - 120, cx + 120, cy + 120], NERRA_CYAN, 60, 170)
    elif spec.glyph == "bars":
        # Seven rising bars — the seven companies as one tape.
        heights = (0.42, 0.58, 0.5, 0.72, 0.64, 0.86, 1.0)
        w, gap, base = 90, 40, cy + 330
        x = cx - (7 * w + 6 * gap) / 2
        for h in heights:
            draw.rounded_rectangle([x, base - 620 * h, x + w, base], radius=18,
                                   fill=a + (235,))
            x += w + gap
        draw.line([cx - 560, base + 30, cx + 560, base + 30], fill=SLATE + (180,), width=10)
    elif spec.glyph == "chain":
        # A short amino-acid chain: beads on a gently curved backbone.
        pts = []
        for i in range(9):
            t = i / 8
            pts.append((cx - 560 + 1120 * t, cy + math.sin(t * math.pi * 1.6) * 170))
        draw.line(pts, fill=a + (160,), width=16, joint="curve")
        for i, (x, y) in enumerate(pts):
            r = 74 if i % 3 == 1 else 56
            draw.ellipse([x - r, y - r, x + r, y + r], fill=a + (255,) if i % 3 == 1 else a + (170,))
    elif spec.glyph == "rings":
        # Concentric growth rings, slightly off-centre — time, read carefully.
        for i, r in enumerate(range(90, 460, 62)):
            draw.ellipse([cx - r, cy - r * 0.94, cx + r, cy + r * 0.94],
                         outline=a + (255 - i * 28,), width=16)
        _glow(img, [cx - 90, cy - 90, cx + 90, cy + 90], a, 50, 160)
    elif spec.glyph == "place":
        # A horizon with a ridge above water and a single place mark.
        w = 1100
        base = cy + 200
        if spec.glyph_arg == 1:
            # One long, low escarpment rise (Blue Mountain behind the bay).
            ridge = [(-1.0, 0.0), (-0.55, 0.08), (-0.2, 0.42), (0.35, 0.5),
                     (0.7, 0.32), (1.0, 0.18)]
        else:
            # Three peaks (the North Shore mountains over the water).
            ridge = [(-1.0, 0.12), (-0.62, 0.62), (-0.35, 0.3), (-0.05, 0.9),
                     (0.3, 0.38), (0.6, 0.7), (1.0, 0.16)]
        pts = [(cx + x * w, base - h * 520) for x, h in ridge]
        draw.polygon(pts + [(cx + w, base), (cx - w, base)], fill=a + (70,))
        draw.line(pts, fill=a + (240,), width=20, joint="curve")
        # Water: three thin horizontal strokes under the horizon.
        for i, inset in enumerate((0, 160, 320)):
            y = base + 70 + i * 70
            draw.line([cx - w + inset, y, cx + w - inset, y], fill=SLATE + (150 - i * 35,), width=12)
        draw.line([cx - w, base, cx + w, base], fill=a + (255,), width=14)
        # The place mark.
        mx, my = cx + (180 if spec.glyph_arg == 1 else -60), base - 40
        draw.ellipse([mx - 58, my - 58, mx + 58, my + 58], fill=NERRA_CYAN + (255,))
        draw.ellipse([mx - 120, my - 120, mx + 120, my + 120], outline=NERRA_CYAN + (170,), width=12)
        _glow(img, [mx - 140, my - 140, mx + 140, my + 140], NERRA_CYAN, 60, 120)
    elif spec.glyph == "gauge":
        # A half-circle probability gauge: ticks at every tenth, the arc
        # filled to the needle, the needle at a price that is neither a sure
        # thing nor a long shot.
        r, base = 470, cy + 230
        box = [cx - r, base - r, cx + r, base + r]
        draw.arc(box, start=180, end=360, fill=SLATE + (200,), width=34)
        p_needle = 0.63
        draw.arc(box, start=180, end=180 + 180 * p_needle, fill=a + (255,), width=34)
        for i in range(11):
            ang = math.radians(180 + 18 * i)
            r0, r1 = r - 70, r - (110 if i % 5 else 140)
            draw.line([cx + r0 * math.cos(ang), base + r0 * math.sin(ang),
                       cx + r1 * math.cos(ang), base + r1 * math.sin(ang)],
                      fill=a + (220,), width=12)
        ang = math.radians(180 + 180 * p_needle)
        nx, ny = cx + (r - 150) * math.cos(ang), base + (r - 150) * math.sin(ang)
        draw.line([cx, base, nx, ny], fill=NERRA_CYAN + (255,), width=22)
        draw.ellipse([cx - 46, base - 46, cx + 46, base + 46], fill=NERRA_CYAN + (255,))
        _glow(img, [cx - 110, base - 110, cx + 110, base + 110], NERRA_CYAN, 50, 140)
    elif spec.glyph == "globe":
        # Omni View desks (Phase 3): a wire globe with the desk's region lit.
        # glyph_arg: 0 Europe, 1 Asia Pacific, 2 Africa & Middle East,
        # 3 Central & South America, 4 North America, 5 the whole world.
        r = 470
        box = [cx - r, cy - r, cx + r, cy + r]
        draw.ellipse(box, fill=a + (40,), outline=a + (240,), width=18)
        for k in (0.36, 0.72):                       # meridians
            draw.ellipse([cx - r * k, cy - r, cx + r * k, cy + r], outline=a + (150,), width=10)
        draw.line([cx, cy - r, cx, cy + r], fill=a + (150,), width=10)
        for f in (-0.55, 0.0, 0.55):                 # parallels
            y = cy + r * f
            half = r * math.sqrt(max(0.0, 1 - f * f))
            draw.line([cx - half, y, cx + half, y], fill=a + (150,), width=10)
        spots = {0: [(0.05, -0.45)], 1: [(0.55, -0.15)], 2: [(0.12, 0.12)],
                 3: [(-0.42, 0.42)], 4: [(-0.45, -0.4)],
                 5: [(0.05, -0.45), (0.55, -0.15), (0.12, 0.12), (-0.42, 0.42), (-0.45, -0.4)]}
        for fx, fy in spots.get(spec.glyph_arg, spots[5]):
            mx, my = cx + fx * r, cy + fy * r
            big = spec.glyph_arg != 5
            rr = 78 if big else 44
            draw.ellipse([mx - rr, my - rr, mx + rr, my + rr], fill=NERRA_CYAN + (255,))
            if big:
                draw.ellipse([mx - 150, my - 150, mx + 150, my + 150], outline=NERRA_CYAN + (170,), width=12)
            _glow(img, [mx - 170, my - 170, mx + 170, my + 170], NERRA_CYAN, 60, 120)
    else:  # dial — the Nerra Daily family default
        r = 420
        draw.arc([cx - r, cy - r, cx + r, cy + r], start=205, end=335, fill=a + (235,), width=26)


def build_cover(spec: CoverSpec) -> Image.Image:
    img = _vertical_gradient(SIZE, DUSK, NIGHT)
    draw = ImageDraw.Draw(img, "RGBA")
    cx = SIZE / 2
    _glow(img, [cx - 1150, SIZE * 0.6 - 420, cx + 1150, SIZE * 0.6 + 420],
          tuple(round(c * 0.55) for c in spec.accent), 260, 110)
    draw = ImageDraw.Draw(img, "RGBA")

    f_kicker = ImageFont.truetype(FONT_BOLD, 96)
    _tracked_text(draw, SIZE * 0.085, "THE NERRA NETWORK", f_kicker, NERRA_CYAN, 30, cx)

    y = SIZE * 0.15
    for line in spec.title_lines:
        f = _fit_font(draw, line, FONT_BOLD, 360, SIZE * 0.86, 28)
        _tracked_text(draw, y, line, f, WHITE, 28, cx)
        y += f.size * 1.12

    _draw_glyph(img, draw, spec, cx, SIZE * 0.6)

    f_sub = _fit_font(draw, spec.tagline, FONT_BOOK, 92, SIZE * 0.88, 14)
    _tracked_text(draw, SIZE * 0.815, spec.tagline, f_sub, SLATE, 14, cx)
    f_host = ImageFont.truetype(FONT_BOOK, 96)
    _tracked_text(draw, SIZE * 0.875, spec.host_line, f_host, spec.accent, 8, cx)
    return img


def write_cover(slug: str, out_dir: Path | None = None) -> Path:
    spec = SPECS[slug]
    out_dir = out_dir or (ROOT / "assets" / "covers")
    out_dir.mkdir(parents=True, exist_ok=True)
    stem = slug.replace("_", "-")
    img = build_cover(spec)
    jpg = out_dir / f"{stem}.jpg"
    img.save(jpg, quality=92, optimize=True)
    img.save(out_dir / f"{stem}.webp", quality=86, method=6)
    for px in (800, 400):
        img.resize((px, px), Image.LANCZOS).save(
            out_dir / f"{stem}-{px}.webp", quality=84, method=6)
    return jpg


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--slug", choices=sorted(SPECS))
    g.add_argument("--all", action="store_true")
    args = ap.parse_args()
    for slug in (sorted(SPECS) if args.all else [args.slug]):
        path = write_cover(slug)
        print(f"wrote {path.relative_to(ROOT)} (+3 webp variants)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
