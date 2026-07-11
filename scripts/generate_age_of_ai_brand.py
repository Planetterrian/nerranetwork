#!/usr/bin/env python3
"""Generate The Age of AI brand assets (cover art + logo SVGs).

Brand: "The Dialogue" — inside a circular aperture, two waveforms meet at
the center: quantized violet bars (Mira, the machine) on the left, a smooth
amber wave (the human guest) on the right. Palette + usage rules:
docs/age_of_ai_brand.md.

Outputs (idempotent, deterministic):
  assets/covers/age-of-ai.jpg        3000x3000 podcast cover (then run
                                     scripts/generate_webp.py for variants)
  assets/age-of-ai-logo.svg          horizontal lockup (mark + wordmark)
  assets/age-of-ai-mark.svg          square mark only (avatar / favicon use)

Run from repo root:  python scripts/generate_age_of_ai_brand.py
"""

from __future__ import annotations

import math
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

ROOT = Path(__file__).resolve().parent.parent

# ---------------------------------------------------------------------------
# Palette (single source of truth — mirrored in docs/age_of_ai_brand.md)
# ---------------------------------------------------------------------------
DEEP_FIELD = (18, 13, 46)        # #120D2E  background base
MIDNIGHT = (41, 27, 92)          # #291B5C  gradient top
SIGNAL_VIOLET = (124, 58, 237)   # #7C3AED  Mira / machine (network-registered)
VIOLET_BRIGHT = (167, 112, 255)  # #A770FF  violet highlight
HUMAN_AMBER = (251, 191, 36)     # #FBBF24  the human voice
LAVENDER = (196, 181, 253)       # #C4B5FD  secondary text
SIGNAL_WHITE = (248, 247, 255)   # #F8F7FF  primary text

FONT_BOLD = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
FONT_BOOK = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"

# The two waveforms, sampled left→right across the aperture. Deterministic,
# hand-tuned envelope (peaks mid-conversation, breathes at the edges).
BAR_HEIGHTS = [0.22, 0.40, 0.30, 0.62, 0.48, 0.85, 0.58, 1.00, 0.70, 0.44,
               0.58, 0.32]


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


def draw_mark(canvas: Image.Image, center: tuple, radius: int) -> None:
    """The Dialogue mark: aperture ring + quantized bars (violet) meeting a
    smooth wave (amber) at the vertical centerline."""
    cx, cy = center
    layer = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)

    ring_w = max(6, radius // 26)
    inner_r = radius - ring_w * 4          # content stays inside the ring

    # Aperture ring — lavender, understated.
    d.ellipse([cx - radius, cy - radius, cx + radius, cy + radius],
              outline=LAVENDER + (200,), width=ring_w)

    # --- Left half: Mira — quantized bars with a violet lift toward center.
    n = len(BAR_HEIGHTS)
    span = inner_r * 2 * 0.82              # horizontal span of the whole wave
    left_span = span / 2
    bar_gap = left_span / n
    bar_w = bar_gap * 0.52
    max_h = inner_r * 1.12
    for i, h in enumerate(BAR_HEIGHTS):
        x = cx - left_span + i * bar_gap + bar_gap / 2
        t = i / (n - 1)
        color = tuple(round(SIGNAL_VIOLET[c] + (VIOLET_BRIGHT[c] - SIGNAL_VIOLET[c]) * t)
                      for c in range(3))
        half = h * max_h / 2
        d.rounded_rectangle([x - bar_w / 2, cy - half, x + bar_w / 2, cy + half],
                            radius=bar_w / 2, fill=color + (255,))

    # --- Right half: the human — one continuous smooth wave, calmer than
    # the machine's bars, drawn as a thick round-capped line.
    pts = _human_wave_points(cx + bar_gap * 0.4, cy, left_span, max_h, 220)
    d.line(pts, fill=HUMAN_AMBER + (255,), width=max(4, radius // 22),
           joint="curve")
    # Terminal dot where the human wave ends (the listener).
    dot_r = max(6, radius // 20)
    d.ellipse([pts[-1][0] - dot_r, pts[-1][1] - dot_r,
               pts[-1][0] + dot_r, pts[-1][1] + dot_r],
              fill=HUMAN_AMBER + (255,))

    canvas.alpha_composite(layer)


def build_cover(out_path: Path, size: int = 3000) -> None:
    img = _vertical_gradient(size, MIDNIGHT, DEEP_FIELD).convert("RGBA")

    # Soft violet glow behind the mark.
    glow_rgb, glow_mask = _radial_glow(
        size, (size // 2, int(size * 0.40)), int(size * 0.33),
        SIGNAL_VIOLET, 92)
    img = Image.composite(
        Image.blend(img.convert("RGB"), glow_rgb, 0.5).convert("RGBA"),
        img, glow_mask)

    draw_mark(img, (size // 2, int(size * 0.385)), int(size * 0.223))

    d = ImageDraw.Draw(img)
    cx = size / 2

    # Wordmark
    f_title = ImageFont.truetype(FONT_BOLD, int(size * 0.088))
    _tracked_text(d, (0, int(size * 0.660)), "THE AGE", f_title,
                  SIGNAL_WHITE, int(size * 0.012), cx)
    _tracked_text(d, (0, int(size * 0.762)), "OF AI", f_title,
                  SIGNAL_WHITE, int(size * 0.012), cx)

    # Amber rule — the human thread carries through the lockup.
    rule_w = size * 0.056
    ry = int(size * 0.892)
    d.rounded_rectangle([cx - rule_w, ry, cx + rule_w, ry + size * 0.0045],
                        radius=size * 0.002, fill=HUMAN_AMBER)

    f_sub = ImageFont.truetype(FONT_BOOK, int(size * 0.030))
    _tracked_text(d, (0, int(size * 0.912)), "WITH MIRA", f_sub,
                  LAVENDER, int(size * 0.010), cx)

    img.convert("RGB").save(out_path, "JPEG", quality=90, optimize=True)
    print(f"Wrote {out_path} ({size}x{size})")


# ---------------------------------------------------------------------------
# SVGs (web use — same geometry, vector)
# ---------------------------------------------------------------------------

def _mark_svg_group(cx: float, cy: float, radius: float) -> str:
    ring_w = radius / 26 * 1.6
    inner_r = radius - ring_w * 4
    n = len(BAR_HEIGHTS)
    left_span = inner_r * 0.82
    bar_gap = left_span / n
    bar_w = bar_gap * 0.52
    max_h = inner_r * 1.12
    parts = [
        f'<circle cx="{cx}" cy="{cy}" r="{radius}" fill="none" '
        f'stroke="#C4B5FD" stroke-opacity="0.8" stroke-width="{ring_w:.2f}"/>'
    ]
    for i, h in enumerate(BAR_HEIGHTS):
        x = cx - left_span + i * bar_gap + bar_gap / 2
        t = i / (n - 1)
        color = tuple(round(SIGNAL_VIOLET[c] + (VIOLET_BRIGHT[c] - SIGNAL_VIOLET[c]) * t)
                      for c in range(3))
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
        f'<polyline points="{" ".join(pts)}" fill="none" stroke="#FBBF24" '
        f'stroke-width="{stroke_w:.2f}" stroke-linecap="round" '
        f'stroke-linejoin="round"/>'
    )
    ex, ey = pts[-1].split(",")
    parts.append(f'<circle cx="{ex}" cy="{ey}" r="{radius / 20:.2f}" fill="#FBBF24"/>')
    return "\n  ".join(parts)


def build_mark_svg(out_path: Path) -> None:
    svg = f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 120 120" role="img" aria-label="The Age of AI mark">
  <rect width="120" height="120" rx="26" fill="#120D2E"/>
  {_mark_svg_group(60, 60, 46)}
</svg>
'''
    out_path.write_text(svg, encoding="utf-8")
    print(f"Wrote {out_path}")


def build_logo_svg(out_path: Path) -> None:
    # Self-contained: carries its own Deep Field surface so the white
    # wordmark is legible anywhere (brand rule #3).
    svg = f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 560 120" role="img" aria-label="The Age of AI — with Mira">
  <rect width="560" height="120" rx="24" fill="#120D2E"/>
  {_mark_svg_group(60, 60, 46)}
  <text x="136" y="66" font-family="'DM Sans', system-ui, sans-serif" font-weight="700" font-size="44" letter-spacing="2" fill="#F8F7FF">THE AGE OF AI</text>
  <rect x="138" y="80" width="64" height="4" rx="2" fill="#FBBF24"/>
  <text x="214" y="90" font-family="'DM Sans', system-ui, sans-serif" font-weight="400" font-size="20" letter-spacing="4" fill="#C4B5FD">WITH MIRA</text>
</svg>
'''
    out_path.write_text(svg, encoding="utf-8")
    print(f"Wrote {out_path}")


def main() -> int:
    build_cover(ROOT / "assets" / "covers" / "age-of-ai.jpg")
    build_mark_svg(ROOT / "assets" / "age-of-ai-mark.svg")
    build_logo_svg(ROOT / "assets" / "age-of-ai-logo.svg")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
