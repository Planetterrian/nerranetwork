#!/usr/bin/env python3
"""Generate Apple Podcasts QR codes for every show, locally.

Apple's Marketing Tools toolbox has a QR generator, but it is one show
at a time through a web form. The QR payload is just the show URL, and
every show's URL is derivable from its ``apple_show_id`` in
``shows/<slug>.yaml`` — so for a 30-show network it is faster and more
repeatable to generate them here.

The codes carry the same UTM tagging as the site's Apple links
(``utm_medium=qr``) so scans are attributable in Apple's referrer data
rather than blending into direct traffic.

Usage::

    python scripts/make_apple_qr.py                 # all shows
    python scripts/make_apple_qr.py tesla spacex    # named shows
    python scripts/make_apple_qr.py --out assets/qr # custom output dir

Requires ``qrcode``, which is deliberately NOT in requirements.txt —
this is a one-off local asset generator, not part of the daily build,
and CI has no reason to install it::

    pip install "qrcode[pil]"
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from urllib.parse import quote

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

DEFAULT_OUT = ROOT / "assets" / "qr"


def _apple_urls() -> dict:
    """Map slug -> tagged Apple Podcasts URL, reusing the site generator's
    own resolution so the QR codes can never point somewhere different
    from the links rendered on the show pages."""
    import generate_html as gh

    out = {}
    for slug, cfg in gh.NETWORK_SHOWS.items():
        url = gh._apple_links_for(slug, cfg.get("apple_podcasts_url"))[
            "apple_podcasts_url"]
        if not url:
            continue
        sep = "&" if "?" in url else "?"
        out[slug] = (
            f"{url}{sep}utm_source=nerranetwork&utm_medium=qr"
            f"&utm_campaign={quote(slug)}"
        )
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("slugs", nargs="*", help="Shows to render (default: all)")
    ap.add_argument("--out", default=str(DEFAULT_OUT),
                    help=f"Output directory (default: {DEFAULT_OUT})")
    ap.add_argument("--dry-run", action="store_true",
                    help="Print the URLs without writing PNGs")
    args = ap.parse_args()

    urls = _apple_urls()
    if args.slugs:
        missing = [s for s in args.slugs if s not in urls]
        if missing:
            print(f"No Apple show ID for: {', '.join(missing)}", file=sys.stderr)
        urls = {s: u for s, u in urls.items() if s in args.slugs}

    if not urls:
        print("Nothing to do — no shows with an Apple show ID.", file=sys.stderr)
        return 1

    if args.dry_run:
        for slug, url in sorted(urls.items()):
            print(f"{slug}: {url}")
        return 0

    try:
        import qrcode
    except ImportError:
        print('qrcode not installed. Run: pip install "qrcode[pil]"',
              file=sys.stderr)
        return 2

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    for slug, url in sorted(urls.items()):
        # High error correction so the code still scans when printed
        # small or partly obscured by cover art in a layout.
        img = qrcode.make(url, error_correction=qrcode.constants.ERROR_CORRECT_H)
        path = out_dir / f"{slug}-apple.png"
        img.save(path)
        print(f"Wrote {path}")

    print(f"\n{len(urls)} QR codes in {out_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
