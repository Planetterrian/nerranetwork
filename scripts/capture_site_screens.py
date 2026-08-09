#!/usr/bin/env python3
"""Refresh the committed nerranetwork.com screenshots in assets/site_screens/.

The outro/end-card showcase (``engine/promo_card.py``) composites real
screenshots of the public site into the closing seconds of every long-form
video and Short. Those screenshots are COMMITTED assets — the render
pipeline never hits the network for them — so this script is the one
place they get refreshed when the site's look changes.

Usage (operator laptop or a CI job with playwright + chromium):

    pip install playwright && playwright install chromium
    python scripts/capture_site_screens.py            # all pages
    python scripts/capture_site_screens.py --only network_home

Best-effort by design: a missing playwright install exits 0 with a clear
message (so an accidental CI wiring never fails a pipeline); individual
page failures are logged and skipped. Output is downscaled to 1280px wide
before writing so the repo cost stays ~0.4 MB/page.

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

# name -> URL path. ``show_<slug>`` names are what
# engine.promo_card.site_screenshot_for() resolves; ``<channel>_<slug>``
# (e.g. ru_spacex) wins for that channel's dubs. Add a page here + rerun
# to give another show its own page card (anything absent falls back to
# the network_home shot, so this list only needs the shows that earn it).
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


def capture(only: str = "") -> int:
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("capture_site_screens: playwright not installed — skipping "
              "(pip install playwright && playwright install chromium)")
        return 0
    try:
        from PIL import Image
    except ImportError:
        Image = None  # noqa: N806 — downscale becomes a no-op

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    pages = {k: v for k, v in PAGES.items() if not only or k == only}
    if not pages:
        print(f"capture_site_screens: no page named {only!r}")
        return 1

    captured = 0
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
            except Exception as exc:  # noqa: BLE001 — per-page best-effort
                print(f"capture_site_screens: {name} failed: {exc}")
                continue
            out = OUT_DIR / f"{name}.png"
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
    print(f"capture_site_screens: {captured}/{len(pages)} pages captured")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--only", default="", help="capture a single named page")
    args = ap.parse_args()
    return capture(only=args.only)


if __name__ == "__main__":
    sys.exit(main())
