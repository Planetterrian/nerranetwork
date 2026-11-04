#!/usr/bin/env python3
"""Write the three YouTube channel banners from ``engine.brand``.

Nov 3 2026. The live @NerraNetwork banner still promised the free shows
carried no advertising and listed a fourth language track, weeks after the
first claim was retired on every free surface (Oct 18) and the track was
switched off (Oct 9): the banner's text was typed into
``brand-refresh-2026/build_assets.py``, which needs a Poppins TTF and
fontTools nobody re-installs, and the PNG it had produced was never
re-exported. @NerraRU's banner described a channel whose views are SpaceX,
astronomy and Tesla dubs as "finance and language". @NerraFR had no banner
of its own.

Now the two lines under the wordmark come from ``engine.brand.youtube_banner_lines``
(the tagline in the channel's language + a strap), this script writes

    brand-refresh-2026/assets/nerra-youtube-banner.svg      (@NerraNetwork)
    brand-refresh-2026/assets/nerra-youtube-banner-ru.svg   (@NerraRU)
    brand-refresh-2026/assets/nerra-youtube-banner-fr.svg   (@NerraFR)

and, when ``cairosvg`` is importable, exports each as a 2560x1440 PNG beside
the other brand PNGs (``brand-refresh-2026/assets/png/youtube-banner[-ru|-fr]-
2560x1440.png`` — the files the operator uploads in YouTube Studio) using the
site's bundled fonts (``assets/fonts``: DM Sans, and Golos Text for Cyrillic)
through a private fontconfig, so a laptop and a runner draw the same bytes.

The outlined "Nerra Network" wordmark is the one piece this script does not
own: ``build_assets.py`` outlines it from Poppins and passes it in; run on its
own, this script lifts the wordmark from the committed English SVG, so the
banners can be rebuilt anywhere Python runs. A guard
(``tests/test_youtube_brand_surfaces_2026_11_03.py``) renders the three SVGs
from the committed wordmark and asserts the committed files are byte-identical
— a banner whose text drifts from ``engine.brand`` fails CI.

    python scripts/build_youtube_banners.py              # SVGs + PNGs
    python scripts/build_youtube_banners.py --svg-only
"""
from __future__ import annotations

import argparse
import html
import os
import re
import sys
import tempfile
from pathlib import Path
from typing import Dict, List, Optional

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from engine.brand import youtube_banner_lines  # noqa: E402

ASSETS_DIR = ROOT / "brand-refresh-2026" / "assets"
PNG_DIR = ASSETS_DIR / "png"
FONTS_DIR = ROOT / "assets" / "fonts"

#: channel -> SVG basename. The English file keeps the name every deployment
#: note already points at.
SVG_NAMES: Dict[str, str] = {
    "en": "nerra-youtube-banner.svg",
    "ru": "nerra-youtube-banner-ru.svg",
    "fr": "nerra-youtube-banner-fr.svg",
}
PNG_NAMES: Dict[str, str] = {
    "en": "youtube-banner-2560x1440.png",
    "ru": "youtube-banner-ru-2560x1440.png",
    "fr": "youtube-banner-fr-2560x1440.png",
}
CHANNELS = tuple(SVG_NAMES)

#: DM Sans carries no Cyrillic; the Russian banner sets Golos Text first (the
#: font the site's Russian share cards use).
FONT_FAMILIES: Dict[str, str] = {
    "en": "'DM Sans',Arial,sans-serif",
    "ru": "'Golos Text','DM Sans',Arial,sans-serif",
    "fr": "'DM Sans',Arial,sans-serif",
}
LABELS: Dict[str, str] = {
    "en": "Nerra Network YouTube banner",
    "ru": "Nerra Network YouTube banner (Russian channel)",
    "fr": "Nerra Network YouTube banner (French channel)",
}

WIDTH, HEIGHT = 2560, 1440

# The two outlined wordmark groups sit on ONE line of the committed SVG:
# <g transform="translate(x,770.00) scale(s,-s)"><path d="…" fill="…"/></g> twice.
_WORDMARK_LINE_RE = re.compile(
    r'^[ \t]*((?:<g transform="translate\([^"]+\) scale\([^"]+\)">'
    r'<path d="[^"]+" fill="[^"]+"/></g>){2})[ \t]*$',
    re.M,
)


def wordmark_from_svg(path: Path) -> str:
    """The outlined wordmark groups of a committed banner SVG."""
    text = Path(path).read_text(encoding="utf-8")
    m = _WORDMARK_LINE_RE.search(text)
    if not m:
        raise ValueError(f"no outlined wordmark line in {path}")
    return m.group(1)


def _svg_text(value: str) -> str:
    """Escape a line for an SVG ``<text>``; runs of spaces keep their width."""
    escaped = html.escape(value, quote=False)
    return re.sub(r" {2,}", lambda m: "&#160;" * len(m.group(0)), escaped)


def banner_svg(channel: str, wordmark: str) -> str:
    """One channel's banner SVG, its two text lines from ``engine.brand``."""
    tagline, strap = youtube_banner_lines(channel)
    family = FONT_FAMILIES.get(channel, FONT_FAMILIES["en"])
    label = LABELS.get(channel, LABELS["en"])
    return f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {WIDTH} {HEIGHT}" width="{WIDTH}" height="{HEIGHT}" role="img" aria-label="{label}">
  <defs>
    <linearGradient id="bg" x1="0%" y1="0%" x2="100%" y2="100%"><stop offset="0%" stop-color="#0B0F1A"/><stop offset="55%" stop-color="#0F172A"/><stop offset="100%" stop-color="#161B2E"/></linearGradient>
    <linearGradient id="nerra" x1="0%" y1="0%" x2="100%" y2="100%">
    <stop offset="0%" stop-color="#6B47FF"/><stop offset="100%" stop-color="#00D4FF"/></linearGradient>
  <linearGradient id="nerraText" x1="0%" y1="0%" x2="100%" y2="0%">
    <stop offset="0%" stop-color="#8B6BFF"/><stop offset="100%" stop-color="#00D4FF"/></linearGradient><radialGradient id="nerraGlow" cx="50%" cy="50%" r="50%">
    <stop offset="0%" stop-color="#6B47FF" stop-opacity="0.35"/><stop offset="100%" stop-color="#6B47FF" stop-opacity="0"/></radialGradient>
    <radialGradient id="glowL" cx="50%" cy="50%" r="50%"><stop offset="0%" stop-color="#6B47FF" stop-opacity="0.22"/><stop offset="100%" stop-color="#6B47FF" stop-opacity="0"/></radialGradient>
    <radialGradient id="glowR" cx="50%" cy="50%" r="50%"><stop offset="0%" stop-color="#00D4FF" stop-opacity="0.16"/><stop offset="100%" stop-color="#00D4FF" stop-opacity="0"/></radialGradient>
  </defs>
  <rect width="{WIDTH}" height="{HEIGHT}" fill="url(#bg)"/>
  <ellipse cx="560" cy="500" rx="900" ry="700" fill="url(#glowL)"/>
  <ellipse cx="2050" cy="980" rx="900" ry="700" fill="url(#glowR)"/>
  <g opacity="0.5" stroke="url(#nerra)" stroke-width="2" fill="none">
    <line x1="300" y1="300" x2="520" y2="430" opacity="0.25"/><line x1="520" y1="430" x2="360" y2="640" opacity="0.2"/>
    <line x1="2260" y1="1120" x2="2040" y2="980" opacity="0.25"/><line x1="2040" y1="980" x2="2230" y2="820" opacity="0.2"/>
    <line x1="2180" y1="360" x2="2360" y2="300" opacity="0.2"/></g>
  <g>
    <circle cx="300" cy="300" r="7" fill="#00D4FF" opacity="0.5"/><circle cx="520" cy="430" r="9" fill="#6B47FF" opacity="0.5"/>
    <circle cx="360" cy="640" r="6" fill="#00D4FF" opacity="0.4"/><circle cx="2260" cy="1120" r="7" fill="#00D4FF" opacity="0.5"/>
    <circle cx="2040" cy="980" r="9" fill="#6B47FF" opacity="0.5"/><circle cx="2230" cy="820" r="6" fill="#00D4FF" opacity="0.4"/>
    <circle cx="2180" cy="360" r="7" fill="#6B47FF" opacity="0.45"/><circle cx="2360" cy="300" r="6" fill="#00D4FF" opacity="0.4"/></g>
  <g transform="translate(1180,470) scale(1.6)">
    <rect width="100" height="100" rx="24" fill="#0B0F1A"/><circle cx="50" cy="50" r="38" fill="url(#nerraGlow)"/>
    <circle cx="50" cy="50" r="33" fill="none" stroke="url(#nerra)" stroke-width="1" opacity="0.18"/>
    <g stroke="url(#nerra)" stroke-width="2.4" stroke-linecap="round" opacity="0.55">
      <line x1="50" y1="50" x2="50" y2="26"/><line x1="50" y1="50" x2="70.8" y2="38"/>
      <line x1="50" y1="50" x2="70.8" y2="62"/><line x1="50" y1="50" x2="50" y2="74"/>
      <line x1="50" y1="50" x2="29.2" y2="62"/><line x1="50" y1="50" x2="29.2" y2="38"/></g>
    <circle cx="50" cy="26" r="5.2" fill="#00D4FF"/><circle cx="70.8" cy="38" r="5.2" fill="#6B47FF"/>
    <circle cx="70.8" cy="62" r="5.2" fill="#00D4FF"/><circle cx="50" cy="74" r="5.2" fill="#6B47FF"/>
    <circle cx="29.2" cy="62" r="5.2" fill="#00D4FF"/><circle cx="29.2" cy="38" r="5.2" fill="#6B47FF"/>
    <circle cx="50" cy="50" r="10" fill="url(#nerra)"/><circle cx="50" cy="50" r="4.2" fill="#FFFFFF" opacity="0.95"/></g>
  {wordmark}
  <text x="1280" y="858" text-anchor="middle" font-family="{family}" font-weight="500" font-size="38" fill="#CBD5E1">{_svg_text(tagline)}</text>
  <text x="1280" y="918" text-anchor="middle" font-family="{family}" font-weight="600" font-size="24" letter-spacing="2" fill="#94A3B8">{_svg_text(strap)}</text>
</svg>'''


def banner_text_lines(svg_text: str) -> List[str]:
    """The reader-facing lines of a banner SVG, entities and NBSPs resolved."""
    return [html.unescape(t).replace("\xa0", " ")
            for t in re.findall(r"<text[^>]*>(.*?)</text>", svg_text, re.S)]


def write_banners(wordmark: Optional[str] = None,
                  out_dir: Path = ASSETS_DIR) -> List[Path]:
    """Write the three SVGs; returns their paths."""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    if wordmark is None:
        wordmark = wordmark_from_svg(ASSETS_DIR / SVG_NAMES["en"])
    written = []
    for channel in CHANNELS:
        path = out_dir / SVG_NAMES[channel]
        path.write_text(banner_svg(channel, wordmark), encoding="utf-8")
        written.append(path)
    return written


def _fontconfig_for_bundled_fonts() -> Path:
    """A fonts.conf that adds assets/fonts to the system fonts."""
    conf_dir = Path(tempfile.mkdtemp(prefix="nerra_banner_fonts_"))
    conf = conf_dir / "fonts.conf"
    conf.write_text(
        '<?xml version="1.0"?>\n<!DOCTYPE fontconfig SYSTEM "fonts.dtd">\n'
        "<fontconfig>\n"
        '  <include ignore_missing="yes">/etc/fonts/fonts.conf</include>\n'
        f"  <dir>{FONTS_DIR}</dir>\n"
        f"  <cachedir>{conf_dir / 'cache'}</cachedir>\n"
        "</fontconfig>\n",
        encoding="utf-8",
    )
    return conf


def export_pngs(svg_paths: List[Path], png_dir: Path = PNG_DIR) -> List[Path]:
    """Render each SVG to its 2560x1440 PNG with cairosvg; ``[]`` without it."""
    if "FONTCONFIG_FILE" not in os.environ:
        os.environ["FONTCONFIG_FILE"] = str(_fontconfig_for_bundled_fonts())
    try:
        import cairosvg
    except ImportError:
        print("build_youtube_banners: cairosvg not importable — SVGs written, "
              "PNGs not exported (pip install cairosvg, then rerun)")
        return []
    png_dir = Path(png_dir)
    png_dir.mkdir(parents=True, exist_ok=True)
    by_name = {v: k for k, v in SVG_NAMES.items()}
    written = []
    for svg in svg_paths:
        channel = by_name.get(Path(svg).name)
        if channel is None:
            continue
        out = png_dir / PNG_NAMES[channel]
        cairosvg.svg2png(url=str(svg), write_to=str(out),
                         output_width=WIDTH, output_height=HEIGHT)
        written.append(out)
    return written


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--svg-only", action="store_true",
                    help="write the SVGs and skip the PNG export")
    args = ap.parse_args()
    svgs = write_banners()
    for p in svgs:
        print(f"wrote {p.relative_to(ROOT)}")
    if not args.svg_only:
        for p in export_pngs(svgs):
            print(f"wrote {p.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
