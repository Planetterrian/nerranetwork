#!/usr/bin/env python3
"""Generate brand assets (cover art + logo SVGs) for the Mira-hosted
interview shows: The Age of AI and its sister show Nerra Voices.

Brand: "The Dialogue" — inside a circular aperture, two waveforms meet at
the center: quantized bars in the show's machine colour (Mira) on the
left, a smooth amber wave (the human guest) on the right. The amber wave
is IDENTICAL across shows — amber is the human, and the human does not
change between shows; only Mira's colour does. Palette + usage rules:
docs/age_of_ai_brand.md.

Outputs (idempotent, deterministic) — ``--show age_of_ai`` (default):
  assets/covers/age-of-ai.jpg        3000x3000 podcast cover (then run
                                     scripts/generate_webp.py for variants)
  assets/age-of-ai-logo.svg          horizontal lockup (mark + wordmark)
  assets/age-of-ai-mark.svg          square mark only (avatar / favicon use)

``--show nerra_voices`` writes the same trio as ``assets/covers/nerra-voices.jpg``,
``assets/nerra-voices-logo.svg``, ``assets/nerra-voices-mark.svg``.

Run from repo root:  python scripts/generate_age_of_ai_brand.py [--show SLUG]
"""

from __future__ import annotations

import argparse
import math
from dataclasses import dataclass, field
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

ROOT = Path(__file__).resolve().parent.parent

# ---------------------------------------------------------------------------
# Palette (single source of truth — mirrored in docs/age_of_ai_brand.md)
# ---------------------------------------------------------------------------
# --- The Age of AI
DEEP_FIELD = (18, 13, 46)        # #120D2E  background base
MIDNIGHT = (41, 27, 92)          # #291B5C  gradient top
SIGNAL_VIOLET = (124, 58, 237)   # #7C3AED  Mira / machine (network-registered)
VIOLET_BRIGHT = (167, 112, 255)  # #A770FF  violet highlight
LAVENDER = (196, 181, 253)       # #C4B5FD  secondary text
SIGNAL_WHITE = (248, 247, 255)   # #F8F7FF  primary text

# --- Shared: the human voice. Never re-tinted per show (brand rule #2).
HUMAN_AMBER = (251, 191, 36)     # #FBBF24  the human voice

# --- Nerra Voices (sister show — same mark, Mira wears the show teal)
DEEP_WATER = (7, 30, 32)         # #071E20  background base
TIDE = (15, 59, 62)              # #0F3B3E  gradient top
SIGNAL_TEAL = (15, 118, 110)     # #0F766E  Mira / machine (network-registered)
TEAL_BRIGHT = (45, 212, 191)     # #2DD4BF  teal highlight
SEA_GLASS = (153, 246, 228)      # #99F6E4  secondary text
TIDE_WHITE = (246, 255, 253)     # #F6FFFD  primary text

FONT_BOLD = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
FONT_BOOK = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"

# The two waveforms, sampled left→right across the aperture. Deterministic,
# hand-tuned envelope (peaks mid-conversation, breathes at the edges).
BAR_HEIGHTS = [0.22, 0.40, 0.30, 0.62, 0.48, 0.85, 0.58, 1.00, 0.70, 0.44,
               0.58, 0.32]


def _hex(rgb: tuple) -> str:
    return "#%02X%02X%02X" % rgb


@dataclass(frozen=True)
class BrandSpec:
    """Everything the drawing code needs to know about one show."""
    slug: str
    stem: str                        # file stem: age-of-ai / nerra-voices
    display_name: str                # "The Age of AI"
    wordmark_lines: tuple            # cover wordmark, one entry per line
    subtitle: str                    # "WITH MIRA"
    deep_field: tuple                # background base + mark tile
    midnight: tuple                  # gradient top
    machine: tuple                   # Mira's bars (= network brand_color)
    machine_bright: tuple            # bar-gradient highlight toward center
    secondary: tuple                 # aperture ring + subtitle text
    white: tuple                     # wordmark
    human: tuple = HUMAN_AMBER       # the guest's wave — shared, never re-tinted
    cover_wordmark_scale: float = 0.088
    lockup_wordmark: str = field(default="")

    @property
    def lockup_text(self) -> str:
        return self.lockup_wordmark or " ".join(self.wordmark_lines)


AGE_OF_AI = BrandSpec(
    slug="age_of_ai",
    stem="age-of-ai",
    display_name="The Age of AI",
    wordmark_lines=("THE AGE", "OF AI"),
    subtitle="WITH MIRA",
    deep_field=DEEP_FIELD,
    midnight=MIDNIGHT,
    machine=SIGNAL_VIOLET,
    machine_bright=VIOLET_BRIGHT,
    secondary=LAVENDER,
    white=SIGNAL_WHITE,
)

NERRA_VOICES = BrandSpec(
    slug="nerra_voices",
    stem="nerra-voices",
    display_name="Nerra Voices",
    wordmark_lines=("NERRA", "VOICES"),
    subtitle="WITH MIRA",
    deep_field=DEEP_WATER,
    midnight=TIDE,
    machine=SIGNAL_TEAL,
    machine_bright=TEAL_BRIGHT,
    secondary=SEA_GLASS,
    white=TIDE_WHITE,
)

BRANDS = {spec.slug: spec for spec in (AGE_OF_AI, NERRA_VOICES)}


def _human_wave_points(cx: float, cy: float, span: float, max_h: float,
                       steps: int) -> list:
    """The guest's wave: one smooth, breathing curve — a gentle S that
    swells mid-phrase and settles, deliberately calmer than Mira's bars."""
    pts = []
    for s in range(steps + 1):
        t = s / steps
        envelope = math.sin(t * math.pi) ** 0.85          # swell + settle
        y = cy - math.sin(t * math.pi * 2.35 + 0.35) * envelope * max_h * 0.40
        pts.append((cx + t * span, y))
    return pts


def _vertical_gradient(size: int, top: tuple, bottom: tuple) -> Image.Image:
    strip = Image.new("RGB", (1, size))
    for y in range(size):
        t = y / (size - 1)
        strip.putpixel((0, y), tuple(
            round(top[c] + (bottom[c] - top[c]) * t) for c in range(3)))
    return strip.resize((size, size))


def _radial_glow(size: int, center: tuple, radius: int, color: tuple,
                 peak_alpha: int) -> Image.Image:
    glow = Image.new("L", (size, size), 0)
    d = ImageDraw.Draw(glow)
    d.ellipse([center[0] - radius, center[1] - radius,
               center[0] + radius, center[1] + radius], fill=peak_alpha)
    glow = glow.filter(ImageFilter.GaussianBlur(radius * 0.55))
    layer = Image.new("RGB", (size, size), color)
    return Image.composite(layer, Image.new("RGB", (size, size), (0, 0, 0)),
                           glow), glow


def _tracked_text(draw: ImageDraw.ImageDraw, xy: tuple, text: str,
                  font: ImageFont.FreeTypeFont, fill: tuple,
                  tracking: int, anchor_center_x: float) -> None:
    """Draw letterspaced text centered on anchor_center_x."""
    widths = [draw.textlength(ch, font=font) for ch in text]
    total = sum(widths) + tracking * (len(text) - 1)
    x = anchor_center_x - total / 2
    for ch, w in zip(text, widths):
        draw.text((x, xy[1]), ch, font=font, fill=fill)
        x += w + tracking


def _bar_color(spec: BrandSpec, t: float) -> tuple:
    return tuple(round(spec.machine[c] + (spec.machine_bright[c] - spec.machine[c]) * t)
                 for c in range(3))


def draw_mark(canvas: Image.Image, center: tuple, radius: int,
              spec: BrandSpec = AGE_OF_AI) -> None:
    """The Dialogue mark: aperture ring + quantized bars (the show's machine
    colour) meeting a smooth wave (amber) at the vertical centerline."""
    cx, cy = center
    layer = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)

    ring_w = max(6, radius // 26)
    inner_r = radius - ring_w * 4          # content stays inside the ring

    # Aperture ring — secondary tint, understated.
    d.ellipse([cx - radius, cy - radius, cx + radius, cy + radius],
              outline=spec.secondary + (200,), width=ring_w)

    # --- Left half: Mira — quantized bars with a lift toward center.
    n = len(BAR_HEIGHTS)
    span = inner_r * 2 * 0.82              # horizontal span of the whole wave
    left_span = span / 2
    bar_gap = left_span / n
    bar_w = bar_gap * 0.52
    max_h = inner_r * 1.12
    for i, h in enumerate(BAR_HEIGHTS):
        x = cx - left_span + i * bar_gap + bar_gap / 2
        color = _bar_color(spec, i / (n - 1))
        half = h * max_h / 2
        d.rounded_rectangle([x - bar_w / 2, cy - half, x + bar_w / 2, cy + half],
                            radius=bar_w / 2, fill=color + (255,))

    # --- Right half: the human — one continuous smooth wave, calmer than
    # the machine's bars, drawn as a thick round-capped line.
    pts = _human_wave_points(cx + bar_gap * 0.4, cy, left_span, max_h, 220)
    d.line(pts, fill=spec.human + (255,), width=max(4, radius // 22),
           joint="curve")
    # Terminal dot where the human wave ends (the listener).
    dot_r = max(6, radius // 20)
    d.ellipse([pts[-1][0] - dot_r, pts[-1][1] - dot_r,
               pts[-1][0] + dot_r, pts[-1][1] + dot_r],
              fill=spec.human + (255,))

    canvas.alpha_composite(layer)


def build_cover(out_path: Path, size: int = 3000,
                spec: BrandSpec = AGE_OF_AI) -> None:
    img = _vertical_gradient(size, spec.midnight, spec.deep_field).convert("RGBA")

    # Soft glow behind the mark, in the machine colour.
    glow_rgb, glow_mask = _radial_glow(
        size, (size // 2, int(size * 0.40)), int(size * 0.33),
        spec.machine, 92)
    img = Image.composite(
        Image.blend(img.convert("RGB"), glow_rgb, 0.5).convert("RGBA"),
        img, glow_mask)

    draw_mark(img, (size // 2, int(size * 0.385)), int(size * 0.223), spec)

    d = ImageDraw.Draw(img)
    cx = size / 2

    # Wordmark — two tracked-caps lines.
    f_title = ImageFont.truetype(FONT_BOLD, int(size * spec.cover_wordmark_scale))
    line_ys = (0.660, 0.762)
    for line, y in zip(spec.wordmark_lines, line_ys):
        _tracked_text(d, (0, int(size * y)), line, f_title,
                      spec.white, int(size * 0.012), cx)

    # Amber rule — the human thread carries through the lockup.
    rule_w = size * 0.056
    ry = int(size * 0.892)
    d.rounded_rectangle([cx - rule_w, ry, cx + rule_w, ry + size * 0.0045],
                        radius=size * 0.002, fill=spec.human)

    f_sub = ImageFont.truetype(FONT_BOOK, int(size * 0.030))
    _tracked_text(d, (0, int(size * 0.912)), spec.subtitle, f_sub,
                  spec.secondary, int(size * 0.010), cx)

    img.convert("RGB").save(out_path, "JPEG", quality=90, optimize=True)
    print(f"Wrote {out_path} ({size}x{size})")


# ---------------------------------------------------------------------------
# SVGs (web use — same geometry, vector)
# ---------------------------------------------------------------------------

def _mark_svg_group(cx: float, cy: float, radius: float,
                    spec: BrandSpec = AGE_OF_AI) -> str:
    ring_w = radius / 26 * 1.6
    inner_r = radius - ring_w * 4
    n = len(BAR_HEIGHTS)
    left_span = inner_r * 0.82
    bar_gap = left_span / n
    bar_w = bar_gap * 0.52
    max_h = inner_r * 1.12
    human_hex = _hex(spec.human)
    parts = [
        f'<circle cx="{cx}" cy="{cy}" r="{radius}" fill="none" '
        f'stroke="{_hex(spec.secondary)}" stroke-opacity="0.8" '
        f'stroke-width="{ring_w:.2f}"/>'
    ]
    for i, h in enumerate(BAR_HEIGHTS):
        x = cx - left_span + i * bar_gap + bar_gap / 2
        color = _bar_color(spec, i / (n - 1))
        half = h * max_h / 2
        parts.append(
            f'<rect x="{x - bar_w / 2:.2f}" y="{cy - half:.2f}" '
            f'width="{bar_w:.2f}" height="{half * 2:.2f}" rx="{bar_w / 2:.2f}" '
            f'fill="rgb{color}"/>'
        )
    wave = _human_wave_points(cx + bar_gap * 0.4, cy, left_span, max_h, 80)
    pts = [f"{x:.1f},{y:.1f}" for x, y in wave]
    stroke_w = max(1.5, radius / 22)
    parts.append(
        f'<polyline points="{" ".join(pts)}" fill="none" stroke="{human_hex}" '
        f'stroke-width="{stroke_w:.2f}" stroke-linecap="round" '
        f'stroke-linejoin="round"/>'
    )
    ex, ey = pts[-1].split(",")
    parts.append(f'<circle cx="{ex}" cy="{ey}" r="{radius / 20:.2f}" fill="{human_hex}"/>')
    return "\n  ".join(parts)


def build_mark_svg(out_path: Path, spec: BrandSpec = AGE_OF_AI) -> None:
    svg = f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 120 120" role="img" aria-label="{spec.display_name} mark">
  <rect width="120" height="120" rx="26" fill="{_hex(spec.deep_field)}"/>
  {_mark_svg_group(60, 60, 46, spec)}
</svg>
'''
    out_path.write_text(svg, encoding="utf-8")
    print(f"Wrote {out_path}")


def build_logo_svg(out_path: Path, spec: BrandSpec = AGE_OF_AI) -> None:
    # Self-contained: carries its own dark surface so the white wordmark is
    # legible anywhere (brand rule #3).
    svg = f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 560 120" role="img" aria-label="{spec.display_name} — with Mira">
  <rect width="560" height="120" rx="24" fill="{_hex(spec.deep_field)}"/>
  {_mark_svg_group(60, 60, 46, spec)}
  <text x="136" y="66" font-family="'DM Sans', system-ui, sans-serif" font-weight="700" font-size="44" letter-spacing="2" fill="{_hex(spec.white)}">{spec.lockup_text}</text>
  <rect x="138" y="80" width="64" height="4" rx="2" fill="{_hex(spec.human)}"/>
  <text x="214" y="90" font-family="'DM Sans', system-ui, sans-serif" font-weight="400" font-size="20" letter-spacing="4" fill="{_hex(spec.secondary)}">{spec.subtitle}</text>
</svg>
'''
    out_path.write_text(svg, encoding="utf-8")
    print(f"Wrote {out_path}")


def build_all(spec: BrandSpec) -> None:
    build_cover(ROOT / "assets" / "covers" / f"{spec.stem}.jpg", spec=spec)
    build_mark_svg(ROOT / "assets" / f"{spec.stem}-mark.svg", spec)
    build_logo_svg(ROOT / "assets" / f"{spec.stem}-logo.svg", spec)


def main(argv: list | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--show", choices=sorted(BRANDS), default="age_of_ai",
                        help="which show's brand to generate (default: age_of_ai)")
    args = parser.parse_args(argv)
    build_all(BRANDS[args.show])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
