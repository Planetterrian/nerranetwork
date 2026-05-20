#!/usr/bin/env python3
"""Generate placeholder YouTube channel branding (logo + banner) for both
Nerra Network (English) and Nerra RU.

Matches the existing brand: dark navy ``#0B0F1A`` background with a
purple→cyan gradient (``#7C5CFF`` → ``#00D4FF``) network-node mark.

Outputs (under ``assets/youtube/``):
  * ``nerra_network_logo.png``   — 800x800 channel avatar
  * ``nerra_network_banner.png`` — 2048x1152 banner, safe area centered
  * ``nerra_ru_logo.png``        — 800x800 channel avatar
  * ``nerra_ru_banner.png``      — 2048x1152 banner

Run from the repo root::

    python3 scripts/generate_youtube_brand_assets.py
"""
from __future__ import annotations

import math
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont


REPO_ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = REPO_ROOT / "assets" / "youtube"

NAVY = (11, 15, 26, 255)            # #0B0F1A — bg
NAVY_LIGHTER = (22, 28, 48, 255)    # banner gradient stop
PURPLE = (124, 92, 255, 255)        # #7C5CFF — gradient start
CYAN = (0, 212, 255, 255)           # #00D4FF — gradient end
WHITE = (240, 244, 252, 255)
WHITE_DIM = (200, 210, 230, 255)


def lerp(a, b, t):
    return tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(len(a)))


def font(size: int, *, bold: bool = True) -> ImageFont.ImageFont:
    """Best available system font; DejaVu Sans Bold is preinstalled in CI."""
    candidates = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold
        else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/Library/Fonts/Arial Bold.ttf" if bold else "/Library/Fonts/Arial.ttf",
        "/System/Library/Fonts/Helvetica.ttc",
    ]
    for path in candidates:
        if Path(path).exists():
            try:
                return ImageFont.truetype(path, size)
            except OSError:
                continue
    return ImageFont.load_default()


def draw_network_mark(draw: ImageDraw.ImageDraw, cx: int, cy: int,
                      radius: int, *, line_width: int = 8,
                      satellite_radius: int = None,
                      hub_radius: int = None) -> None:
    """Render the Nerra network-node glyph centered at (cx, cy).

    ``radius`` controls how far the satellite nodes sit from the hub.
    """
    if satellite_radius is None:
        satellite_radius = max(8, radius // 6)
    if hub_radius is None:
        hub_radius = max(12, radius // 4)

    # 4 satellites NW/NE/SW/SE — same angles as the SVG (~36° off horizontal)
    angles_deg = [-144, -36, 144, 36]  # NW, NE, SW, SE in screen coords
    points = []
    for deg in angles_deg:
        rad = math.radians(deg)
        x = cx + int(radius * math.cos(rad))
        y = cy + int(radius * math.sin(rad))
        points.append((x, y))

    # Lines from hub to each satellite, with gradient color sampled by index
    for i, (x, y) in enumerate(points):
        # Mix purple→cyan along the diagonal axis, like the SVG gradient
        t = (math.cos(math.radians(angles_deg[i])) + 1) / 2
        color = lerp(PURPLE, CYAN, t)
        # Draw as semi-transparent line by drawing twice (PIL has no alpha line)
        draw.line([(cx, cy), (x, y)], fill=color, width=line_width)

    # Satellites — top two cyan, bottom two purple, matching the SVG
    sat_colors = [CYAN, CYAN, PURPLE, PURPLE]
    for (x, y), c in zip(points, sat_colors):
        draw.ellipse(
            [x - satellite_radius, y - satellite_radius,
             x + satellite_radius, y + satellite_radius],
            fill=c,
        )

    # Hub: gradient feel via concentric — outer purple, inner cyan
    draw.ellipse(
        [cx - hub_radius, cy - hub_radius,
         cx + hub_radius, cy + hub_radius],
        fill=PURPLE,
    )
    inner = max(4, hub_radius - 6)
    draw.ellipse(
        [cx - inner, cy - inner, cx + inner, cy + inner],
        fill=CYAN,
    )


def make_logo(out_path: Path, *, size: int = 800,
              wordmark: str = "NN") -> None:
    """Square channel avatar — network mark + small wordmark below."""
    img = Image.new("RGBA", (size, size), NAVY)
    draw = ImageDraw.Draw(img)

    # Soft radial vignette toward purple in upper-left
    overlay = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    odraw = ImageDraw.Draw(overlay)
    for r in range(size, 0, -40):
        alpha = max(0, 30 - (size - r) // 30)
        odraw.ellipse([size//4 - r//2, size//4 - r//2,
                       size//4 + r//2, size//4 + r//2],
                      fill=(*PURPLE[:3], alpha))
    overlay = overlay.filter(ImageFilter.GaussianBlur(radius=size // 12))
    img = Image.alpha_composite(img, overlay)
    draw = ImageDraw.Draw(img)

    # Rounded-square border tint
    border = max(4, size // 80)
    draw.rounded_rectangle(
        [border, border, size - border, size - border],
        radius=size // 8,
        outline=(60, 70, 110, 200),
        width=border // 2 if border > 4 else 2,
    )

    # Network mark, slightly above center to leave room for wordmark
    cx, cy = size // 2, int(size * 0.45)
    draw_network_mark(
        draw, cx, cy,
        radius=int(size * 0.22),
        line_width=max(6, size // 80),
        satellite_radius=max(14, size // 28),
        hub_radius=max(20, size // 18),
    )

    # Wordmark — letter-spaced caps
    wm_font = font(int(size * 0.18))
    spaced = "  ".join(wordmark)
    bbox = draw.textbbox((0, 0), spaced, font=wm_font)
    w = bbox[2] - bbox[0]
    h = bbox[3] - bbox[1]
    draw.text(
        ((size - w) // 2 - bbox[0], int(size * 0.78) - h // 2 - bbox[1]),
        spaced, font=wm_font, fill=WHITE,
    )

    img.convert("RGB").save(out_path, "PNG", optimize=True)
    print(f"  wrote {out_path.relative_to(REPO_ROOT)} ({size}x{size})")


def make_banner(out_path: Path, *, title: str, tagline: str,
                wordmark: str = "NN",
                width: int = 2048, height: int = 1152) -> None:
    """YouTube channel banner.

    Safe area is centered 1235x338 — keep all text + the mark inside that.
    """
    img = Image.new("RGBA", (width, height), NAVY)

    # Vertical gradient background — slightly lighter at top
    grad = Image.new("RGBA", (1, height), (0, 0, 0, 0))
    for y in range(height):
        t = y / max(1, height - 1)
        grad.putpixel((0, y), lerp(NAVY_LIGHTER, NAVY, t))
    grad = grad.resize((width, height))
    img = Image.alpha_composite(img, grad)

    # Soft purple glow upper-left, soft cyan glow lower-right
    glow = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    gdraw = ImageDraw.Draw(glow)
    for r in range(width, 0, -120):
        alpha = max(0, 18 - (width - r) // 80)
        gdraw.ellipse([- width//4 - r//2, - height//4 - r//2,
                       - width//4 + r//2, - height//4 + r//2],
                      fill=(*PURPLE[:3], alpha))
        gdraw.ellipse([width + width//6 - r//2, height + height//6 - r//2,
                       width + width//6 + r//2, height + height//6 + r//2],
                      fill=(*CYAN[:3], alpha))
    glow = glow.filter(ImageFilter.GaussianBlur(radius=width // 18))
    img = Image.alpha_composite(img, glow)
    draw = ImageDraw.Draw(img)

    # Safe area is centered 1235x338. We'll lay out:
    #   [ network mark ] [ stacked: title (big) / tagline (small) ]
    safe_w, safe_h = 1235, 338
    safe_x = (width - safe_w) // 2
    safe_y = (height - safe_h) // 2

    # Mark on the left of the safe area
    mark_radius = safe_h // 3
    mark_cx = safe_x + mark_radius + 30
    mark_cy = safe_y + safe_h // 2
    draw_network_mark(
        draw, mark_cx, mark_cy,
        radius=mark_radius,
        line_width=8,
        satellite_radius=22,
        hub_radius=32,
    )

    # Text block to the right of the mark — auto-fit so it never escapes
    # the safe area. Available width = safe area right edge minus 80px gutter.
    text_x = mark_cx + mark_radius + 70
    available_w = (safe_x + safe_w) - text_x

    def fit_font(text: str, max_w: int, *, max_size: int,
                 min_size: int = 18, bold: bool = True):
        size_px = max_size
        while size_px >= min_size:
            f = font(size_px, bold=bold)
            bbox = draw.textbbox((0, 0), text, font=f)
            if (bbox[2] - bbox[0]) <= max_w:
                return f, bbox
            size_px -= 4
        f = font(min_size, bold=bold)
        return f, draw.textbbox((0, 0), text, font=f)

    title_font, title_bbox = fit_font(title, available_w, max_size=140)
    title_h = title_bbox[3] - title_bbox[1]

    # Wrap tagline if needed; keep within safe-area width
    tag_font_size = 38
    tag_font = font(tag_font_size, bold=False)
    tag_bbox = draw.textbbox((0, 0), tagline, font=tag_font)
    if (tag_bbox[2] - tag_bbox[0]) > available_w:
        # word-wrap to two lines max
        words = tagline.split()
        line1, line2 = "", ""
        for w in words:
            trial = (line1 + " " + w).strip()
            if (draw.textbbox((0, 0), trial, font=tag_font)[2]
                    - draw.textbbox((0, 0), trial, font=tag_font)[0]) <= available_w:
                line1 = trial
            else:
                line2 = (line2 + " " + w).strip()
        tagline_lines = [line1, line2] if line2 else [line1]
    else:
        tagline_lines = [tagline]

    tag_line_h = tag_bbox[3] - tag_bbox[1]
    total_tag_h = tag_line_h * len(tagline_lines) + 8 * (len(tagline_lines) - 1)
    block_h = title_h + 24 + total_tag_h
    block_y = safe_y + (safe_h - block_h) // 2

    draw.text((text_x - title_bbox[0], block_y - title_bbox[1]),
              title, font=title_font, fill=WHITE)

    cur_y = block_y + title_h + 24
    for line in tagline_lines:
        lb = draw.textbbox((0, 0), line, font=tag_font)
        draw.text((text_x - lb[0], cur_y - lb[1]),
                  line, font=tag_font, fill=WHITE_DIM)
        cur_y += tag_line_h + 8

    img.convert("RGB").save(out_path, "PNG", optimize=True)
    print(f"  wrote {out_path.relative_to(REPO_ROOT)} ({width}x{height})")


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    print("Nerra Network (EN):")
    make_logo(OUT_DIR / "nerra_network_logo.png", wordmark="NN")
    make_banner(
        OUT_DIR / "nerra_network_banner.png",
        title="NERRA NETWORK",
        tagline="Daily AI-narrated podcasts on Tesla, space, science, AI & finance.",
        wordmark="NN",
    )

    print("Nerra RU:")
    make_logo(OUT_DIR / "nerra_ru_logo.png", wordmark="NR")
    make_banner(
        OUT_DIR / "nerra_ru_banner.png",
        title="NERRA RU",
        tagline="Ежедневные AI-подкасты о финансах и языке.",
        wordmark="NR",
    )

    print(f"\nDone. Files in {OUT_DIR.relative_to(REPO_ROOT)}/")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
