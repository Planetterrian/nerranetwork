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
import shutil
import ssl
import sys
import urllib.parse
import urllib.request
from pathlib import Path

logging.basicConfig(level=logging.INFO, stream=sys.stdout,
                    format="%(levelname)s %(message)s")
logger = logging.getLogger("fetch_nasa_broll")

_API = "https://images-api.nasa.gov/search"
_MAX_BYTES_DEFAULT = 220 * 1024 * 1024  # skip multi-GB full-event videos


def _ssl_context() -> ssl.SSLContext:
    """TLS context that works on a stock macOS python.org install.

    Python from python.org ships its own OpenSSL and does NOT read the
    system keychain, so every HTTPS call fails with
    ``CERTIFICATE_VERIFY_FAILED`` until the user runs the bundled
    "Install Certificates.command". Preferring ``certifi``'s CA bundle
    (already present via ``requests``) makes the script work as-is;
    the stdlib default remains the fallback.
    """
    try:
        import certifi
        return ssl.create_default_context(cafile=certifi.where())
    except Exception:  # noqa: BLE001 — fall back to the stdlib default
        return ssl.create_default_context()


_SSL_CTX = _ssl_context()


def _urlopen(req, timeout: int):
    """``urlopen`` with our CA bundle, and a readable TLS error."""
    try:
        return urllib.request.urlopen(req, timeout=timeout,
                                      context=_SSL_CTX)  # noqa: S310
    except urllib.error.URLError as exc:
        if "CERTIFICATE_VERIFY_FAILED" in str(exc.reason):
            raise RuntimeError(
                "TLS certificate verification failed. On a python.org "
                "macOS build, run: pip install certifi  (or execute "
                "'/Applications/Python 3.11/Install Certificates.command')"
            ) from exc
        raise


def _get_json(url: str) -> dict:
    with _urlopen(url, timeout=60) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _search(query: str, page: int = 1) -> list:
    q = urllib.parse.urlencode({
        "q": query, "media_type": "video", "page": page,
    })
    data = _get_json(f"{_API}?{q}")
    return ((data.get("collection") or {}).get("items")) or []


# Rendition preference, best-quality-first. The download loop walks
# this and takes the first one that fits under the size cap — picking a
# single rendition and giving up when it was oversized skipped most of
# the best footage (verified 2026-08-01: 4 of 6 "Isolated Launch Views",
# incl. DART and JPSS-2, were dropped even though each manifest also
# offered a medium/small that fits comfortably). 'orig' is a multi-GB
# master and 'preview' is a thumbnail-grade stub, so both sit last.
_RENDITION_ORDER = ("~large.mp4", "~medium.mp4", "~small.mp4",
                    "~mobile.mp4", "~orig.mp4", "~preview.mp4")


def _mp4_candidates(asset_manifest_href: str) -> list:
    """Ordered mp4 renditions for an asset, best quality first."""
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
    ordered = []
    for marker in _RENDITION_ORDER:
        for h in mp4s:
            if h.lower().endswith(marker) and h not in ordered:
                ordered.append(h)
    # Any unrecognised rendition still beats returning nothing.
    ordered.extend(h for h in mp4s if h not in ordered)
    return ordered


def _content_length(url: str) -> int:
    try:
        req = urllib.request.Request(url, method="HEAD")
        with _urlopen(req, timeout=30) as resp:
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
                candidates = _mp4_candidates(item.get("href") or "")
                if not candidates:
                    continue
                # Step DOWN through renditions until one fits the cap,
                # instead of skipping the asset outright.
                mp4, size = "", 0
                for cand in candidates:
                    cand_size = _content_length(cand)
                    if not cand_size or cand_size <= args.max_bytes:
                        mp4, size = cand, cand_size
                        break
                if not mp4:
                    logger.info("skip (every rendition over %.0f MB): %s",
                                args.max_bytes / 1e6, title[:60])
                    continue
                logger.info("downloading %s [%s] (%.0f MB): %s",
                            nasa_id, mp4.rsplit("~", 1)[-1].replace(".mp4", ""),
                            (size or 0) / 1e6, title[:70])
                # Stream to disk via our CA bundle (urlretrieve takes no
                # SSL context, so it cannot be made to work on the
                # python.org macOS build).
                with _urlopen(mp4, timeout=600) as resp, \
                        dest.open("wb") as fh:
                    shutil.copyfileobj(resp, fh)
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
