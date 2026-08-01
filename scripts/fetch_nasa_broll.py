#!/usr/bin/env python3
"""Fetch public-domain NASA footage as b-roll candidates for curation.

Why NASA and not SpaceX's own media (August 2026, operator request to use
"real SpaceX videos" in SpaceX Daily renders):

* **NASA-produced footage is public domain** (17 U.S.C. §105) — launches,
  Crew Dragon arrivals/departures, ISS operations, mission coverage. Safe
  in monetized YouTube videos; NASA asks only that its logo not imply
  endorsement.
* **SpaceX's Flickr photos are CC BY-NC 2.0** — the NC (non-commercial)
  term is a problem for monetized channels. Operator judgment call, not a
  default.
* **SpaceX's own video is usable ONLY per-video**: parts of the YouTube
  back-catalog are marked "Creative Commons Attribution (reuse allowed)"
  (CC BY — monetized reuse OK with credit), but it's a per-video flag,
  never channel-wide, and 2024+ streams live on X with no license grant.
  ``fetch_spacex_broll.py`` handles that path with a hard CC gate +
  attribution plumbing; anything not CC-marked stays off limits without
  written permission from SpaceX media relations.

This script only DOWNLOADS candidates into a local directory. The
operator then curates (watch, delete duds, keep evergreen shots — pads,
launches, stage separations; nothing dated) and publishes the keepers
with the existing pool builder::

    python scripts/fetch_nasa_broll.py --query "Falcon 9 launch" \
        --out-dir nasa_broll/ --max 12
    # ...watch + curate...
    python scripts/build_broll_pool.py --show spacex \
        --label "NASA launch b-roll" nasa_broll/keeper1.mp4 ...

The NASA Image and Video Library API (images-api.nasa.gov) needs no key.
Videos come as asset manifests; we pick the largest mp4 under the size
cap (b-roll only needs a few seconds of each — the renderer trims).
"""

from __future__ import annotations

import argparse
import json
import logging
import re
import sys
import urllib.parse
import urllib.request
from pathlib import Path

logging.basicConfig(level=logging.INFO, stream=sys.stdout,
                    format="%(levelname)s %(message)s")
logger = logging.getLogger("fetch_nasa_broll")

_API = "https://images-api.nasa.gov/search"
_MAX_BYTES_DEFAULT = 220 * 1024 * 1024  # skip multi-GB full-event videos


def _get_json(url: str) -> dict:
    with urllib.request.urlopen(url, timeout=60) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _search(query: str, page: int = 1) -> list:
    q = urllib.parse.urlencode({
        "q": query, "media_type": "video", "page": page,
    })
    data = _get_json(f"{_API}?{q}")
    return ((data.get("collection") or {}).get("items")) or []


def _best_mp4(asset_manifest_href: str, max_bytes: int) -> str:
    """Pick the preferred mp4 rendition from an asset manifest.

    Manifests list renditions like ``...~orig.mp4`` / ``~large.mp4`` /
    ``~medium.mp4`` / ``~small.mp4``. Prefer large -> medium -> orig ->
    small: 'orig' can be a multi-GB master, and b-roll only needs
    1080p-ish quality.
    """
    data = _get_json(asset_manifest_href)
    # The item's href points at a collection.json that is a BARE LIST of
    # asset URLs (verified live 2026-08-01); some endpoints wrap it in
    # the search-style {"collection": {"items": [{"href": ...}]}}
    # envelope instead. Handle both.
    if isinstance(data, list):
        hrefs = [str(h) for h in data]
    else:
        hrefs = [i.get("href") or "" for i in
                 ((data.get("collection") or {}).get("items")) or []]
    mp4s = [h for h in hrefs if h.lower().endswith(".mp4")]
    for marker in ("~large.mp4", "~medium.mp4", "~orig.mp4", "~small.mp4"):
        for h in mp4s:
            if h.lower().endswith(marker):
                return h
    return mp4s[0] if mp4s else ""


def _content_length(url: str) -> int:
    try:
        req = urllib.request.Request(url, method="HEAD")
        with urllib.request.urlopen(req, timeout=30) as resp:
            return int(resp.headers.get("Content-Length") or 0)
    except Exception:  # noqa: BLE001
        return 0


def _safe_name(nasa_id: str, title: str) -> str:
    slug = re.sub(r"[^A-Za-z0-9]+", "_", (title or nasa_id))[:60].strip("_")
    return f"{nasa_id}__{slug}.mp4"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--query", required=True,
                        help='e.g. "Falcon 9 launch", "Crew Dragon docking"')
    parser.add_argument("--out-dir", default="nasa_broll")
    parser.add_argument("--max", type=int, default=10,
                        help="max videos to download")
    parser.add_argument("--max-bytes", type=int, default=_MAX_BYTES_DEFAULT)
    parser.add_argument("--pages", type=int, default=2,
                        help="search pages to scan (100 results/page)")
    args = parser.parse_args()

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    downloaded = 0
    manifest_rows = []
    for page in range(1, args.pages + 1):
        if downloaded >= args.max:
            break
        try:
            items = _search(args.query, page=page)
        except Exception as exc:  # noqa: BLE001
            logger.warning("search page %d failed: %s", page, exc)
            break
        for item in items:
            if downloaded >= args.max:
                break
            data0 = (item.get("data") or [{}])[0]
            nasa_id = data0.get("nasa_id") or ""
            title = data0.get("title") or ""
            center = data0.get("center") or ""
            if not nasa_id:
                continue
            dest = out_dir / _safe_name(nasa_id, title)
            if dest.exists():
                logger.info("skip (exists): %s", dest.name)
                continue
            try:
                mp4 = _best_mp4(item.get("href") or "", args.max_bytes)
                if not mp4:
                    continue
                size = _content_length(mp4)
                if size and size > args.max_bytes:
                    logger.info("skip (too large, %.0f MB): %s",
                                size / 1e6, title[:60])
                    continue
                logger.info("downloading %s (%.0f MB): %s",
                            nasa_id, (size or 0) / 1e6, title[:70])
                urllib.request.urlretrieve(mp4, dest)  # noqa: S310
                downloaded += 1
                manifest_rows.append({
                    "nasa_id": nasa_id, "title": title, "center": center,
                    "source_url": mp4, "file": dest.name,
                    "license": "public domain (NASA, 17 U.S.C. 105)",
                    # Attribution isn't legally required for public-domain
                    # NASA footage, but NASA asks for a courtesy credit —
                    # build_broll_pool.py copies this into broll.json and
                    # the render appends it to the YouTube description.
                    "attribution": "NASA (public domain)",
                })
            except Exception as exc:  # noqa: BLE001
                logger.warning("failed %s: %s", nasa_id, exc)
                dest.unlink(missing_ok=True)

    # Provenance sidecar so the curated keepers keep their attribution
    # trail (which clip came from which NASA asset).
    if manifest_rows:
        (out_dir / "_provenance.json").write_text(
            json.dumps(manifest_rows, indent=2), encoding="utf-8")
    logger.info("downloaded %d video(s) to %s — now WATCH and curate, "
                "then publish keepers with scripts/build_broll_pool.py",
                downloaded, out_dir)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
