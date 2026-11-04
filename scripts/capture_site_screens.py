#!/usr/bin/env python3
"""Refresh the committed nerranetwork.com screenshots in assets/site_screens/.

The screenshots are COMMITTED assets refreshed only by this script, and
since Nov 3 2026 nothing in the render pipeline reads them: the outro card
and the Shorts end-card strip render from the show registry
(``engine/promo_card.py``). They stay for whichever showcase design the
operator keeps — a capture that fails must say so, because the one that
ran on Aug 9 2026 was the only one that ever did: the monthly workflow's
Nov 1 run was green with every page failed and committed nothing, and the
Aug 9 homepage ("ad-free", "4 languages") shipped on every video for 86
days.

Usage (operator laptop or a CI job with playwright + chromium):

    pip install playwright && playwright install chromium
    python scripts/capture_site_screens.py            # all pages
    python scripts/capture_site_screens.py --only network_home

Exit status is the record: 0 only when at least one page was written;
a missing playwright or a run that captured NOTHING exits non-zero with a
``::error::`` annotation (the Oct 28 2026 class — a green step that fails
every run). A page that fails while others succeed is a ``::warning::``
naming the page; the pages that succeeded are still written. Output is
downscaled to 1280px wide before writing so the repo cost stays
~0.4 MB/page.

The consent banner is suppressed by pre-seeding the site's own
``nn_consent_v1`` localStorage key (state=rejected) before navigation —
the same key ``assets/js/consent.js`` reads — so no analytics consent is
ever recorded by a robot and no banner ever appears in a screenshot.
"""
from __future__ import annotations

import argparse
import io
import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = PROJECT_ROOT / "assets" / "site_screens"

BASE = "https://nerranetwork.com"

# name -> URL path. ``show_<slug>`` names one show's page; ``<channel>_<slug>``
# (e.g. ru_spacex) a channel lander. Add a page here + rerun to capture
# another page.
PAGES = {
    "network_home": "/",
    "show_spacex": "/spacex.html",
    "show_tesla": "/tesla.html",
    "show_fascinating_frontiers": "/fascinating-frontiers.html",
    "ru_spacex": "/ru/spacex.html",
}

VIEWPORT = {"width": 1280, "height": 1500}
TARGET_WIDTH = 1280

CONSENT_SEED = """
try {
  localStorage.setItem('nn_consent_v1', JSON.stringify({
    state: 'rejected', timestamp: Date.now()
  }));
} catch (e) {}
"""


def capture(only: str = "", out_dir: Path = OUT_DIR) -> int:
    """Capture the pages into ``out_dir``; the return value is the exit status."""
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("::error::capture_site_screens: playwright not installed — "
              "nothing captured (pip install playwright && playwright "
              "install chromium)")
        return 1
    try:
        from PIL import Image
    except ImportError:
        Image = None  # noqa: N806 — downscale becomes a no-op

    out_dir.mkdir(parents=True, exist_ok=True)
    pages = {k: v for k, v in PAGES.items() if not only or k == only}
    if not pages:
        print(f"::error::capture_site_screens: no page named {only!r}")
        return 1

    captured = 0
    failed = []
    with sync_playwright() as p:
        browser = p.chromium.launch()
        ctx = browser.new_context(viewport=VIEWPORT, device_scale_factor=2)
        ctx.add_init_script(CONSENT_SEED)
        page = ctx.new_page()
        for name, path in pages.items():
            url = BASE + path
            try:
                page.goto(url, wait_until="networkidle", timeout=45_000)
                time.sleep(2.0)
                # Belt-and-braces if the seed ever stops matching.
                page.evaluate(
                    "document.querySelectorAll('#nn-consent-banner,"
                    "[class*=consent],[id*=consent]')"
                    ".forEach(e => e.remove())"
                )
                time.sleep(0.5)
                png = page.screenshot(clip={
                    "x": 0, "y": 0,
                    "width": VIEWPORT["width"], "height": VIEWPORT["height"],
                })
            except Exception as exc:  # noqa: BLE001 — named, never silent
                print(f"::warning::capture_site_screens: {name} ({url}) "
                      f"failed: {exc}")
                failed.append(name)
                continue
            out = out_dir / f"{name}.png"
            if Image is not None:
                im = Image.open(io.BytesIO(png))
                if im.width > TARGET_WIDTH:
                    im = im.resize(
                        (TARGET_WIDTH,
                         int(round(im.height * TARGET_WIDTH / im.width))),
                        Image.LANCZOS,
                    )
                im.save(out, format="PNG", optimize=True)
            else:
                out.write_bytes(png)
            captured += 1
            print(f"capture_site_screens: wrote {out}")
        browser.close()
    print(f"capture_site_screens: {captured}/{len(pages)} pages captured"
          + (f" (failed: {', '.join(failed)})" if failed else ""))
    if captured == 0:
        print("::error::capture_site_screens: no page was captured — the "
              "committed screenshots were NOT refreshed")
        return 1
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--only", default="", help="capture a single named page")
    args = ap.parse_args()
    return capture(only=args.only)


if __name__ == "__main__":
    sys.exit(main())
