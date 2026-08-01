#!/usr/bin/env python3
"""Fetch royalty-free stock VIDEO for any show, from the Pexels video API.

The network already pays for nothing here: ``PEXELS_API_KEY`` is the
same key ``engine/visual_assets.py`` uses for still images, and the
video endpoint is included. This is the one source that covers EVERY
show rather than one beat — see
[`docs/broll_sources.md`](../docs/broll_sources.md) for the full
source survey (what is public domain, what is CC BY-NC and therefore
unusable, and where the brand-specific footage has to come from).

Two things make this safe to point at a whole network:

* **Queries come from the show's own curated ``image_queries``.** Those
  phrases were written to disambiguate stock-search traps (landmine
  #14: "model 3" returned fashion models, which shipped in a Tesla
  video). Reusing them means video inherits work already done, and a
  new show gets video the moment it has image queries.
* **The same safety filter runs.** ``engine.visual_assets._photo_is_safe``
  is imported rather than reimplemented, so the skip-term list has one
  home; a term added for images protects video automatically.

**Attribution is mandatory here and differs from the site license.**
Pexels content used via the *API* requires crediting the creator and
linking Pexels — so every download records a credit line in
``_provenance.json``, which ``build_broll_pool.py`` copies into
``broll.json`` and the render appends to the YouTube description.

Usage::

    # 16:9 for the long-form slideshow, using the show's own queries:
    python scripts/fetch_stock_broll.py --show tesla --out-dir tesla_stock

    # 9:16 for Shorts — nothing else in the pipeline produces these:
    python scripts/fetch_stock_broll.py --show tesla --orientation portrait \\
        --out-dir tesla_stock_vertical

    # Ad-hoc topic, ignoring the show's queries:
    python scripts/fetch_stock_broll.py --show models_agents \\
        --query "server room racks" --query "code on a screen"

Clips arrive short (the fetcher prefers 5-30 s), so they usually go
straight to the pool without needing ``cut_broll_segments.py``::

    python scripts/build_broll_pool.py --show tesla tesla_stock/*.mp4
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import re
import shutil
import sys
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Dict, List, Optional

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from dotenv import load_dotenv  # noqa: E402

load_dotenv(PROJECT_ROOT / ".env")

from engine.config import load_config  # noqa: E402
from engine.visual_assets import _photo_is_safe  # noqa: E402

logging.basicConfig(level=logging.INFO, stream=sys.stdout,
                    format="%(levelname)s %(message)s")
logger = logging.getLogger("fetch_stock_broll")

PEXELS_VIDEO_SEARCH = "https://api.pexels.com/v1/videos/search"

# Accent-length clips. Anything shorter than MIN can't fill an 8 s slot;
# anything much longer is a mini-documentary that would need cutting.
MIN_DURATION_S = 5
MAX_DURATION_S = 40
MAX_BYTES = 120 * 1024 * 1024

# Renditions, best-usable-first. 4K is a needless download for a
# 1920x1080 render; "sd" is too soft to intercut with Grok stills.
_QUALITY_ORDER = ("hd", "sd", "uhd")


def orientation_of(width: int, height: int) -> str:
    """``landscape`` / ``portrait`` / ``square`` for a frame size."""
    if not width or not height:
        return "square"
    if width > height * 1.1:
        return "landscape"
    if height > width * 1.1:
        return "portrait"
    return "square"


def pick_video_file(video: dict, orientation: str,
                    *, max_bytes: int = MAX_BYTES) -> Optional[dict]:
    """Choose the best downloadable rendition of one Pexels video.

    Prefers a file whose own aspect matches the requested orientation —
    Pexels returns portrait-cropped renditions alongside landscape ones
    for the same clip, and taking the wrong one means the render
    letterboxes or crops the subject out.
    """
    files = [f for f in (video.get("video_files") or [])
             if isinstance(f, dict) and f.get("link")]
    if not files:
        return None
    matching = [
        f for f in files
        if orientation_of(int(f.get("width") or 0),
                          int(f.get("height") or 0)) == orientation
    ]
    pool = matching or files
    # Highest resolution within the preferred quality tiers.
    def _rank(f: dict) -> tuple:
        quality = str(f.get("quality") or "").lower()
        tier = (_QUALITY_ORDER.index(quality)
                if quality in _QUALITY_ORDER else len(_QUALITY_ORDER))
        return (tier, -(int(f.get("width") or 0)))
    return sorted(pool, key=_rank)[0]


def build_attribution(video: dict) -> str:
    """Credit line required by the Pexels API terms.

    The API terms are stricter than the site license: using the API
    obliges a creator credit and a link back to Pexels.
    """
    user = video.get("user") or {}
    name = str(user.get("name") or "Pexels contributor").strip()
    url = str(video.get("url") or "https://www.pexels.com").strip()
    return f"Video by {name} on Pexels ({url})"


def video_is_usable(video: dict, skip_terms: List[str],
                    *, min_s: int = MIN_DURATION_S,
                    max_s: int = MAX_DURATION_S) -> bool:
    """Duration + safety gate for one search result."""
    duration = int(video.get("duration") or 0)
    if duration < min_s or duration > max_s:
        return False
    # Pexels video objects carry the same human-curated slug in ``url``
    # that the image filter keys on ("alt" is absent, which the shared
    # helper tolerates).
    return _photo_is_safe(video, skip_terms)


def safe_name(video: dict, query: str) -> str:
    slug = re.sub(r"[^A-Za-z0-9]+", "_", query)[:40].strip("_")
    return f"pexels_{video.get('id', 'x')}__{slug}.mp4"


def search_videos(query: str, *, api_key: str, orientation: str,
                  per_page: int = 15) -> List[dict]:
    """One Pexels video search. Returns the raw ``videos`` list."""
    params = urllib.parse.urlencode({
        "query": query,
        "orientation": orientation,
        "per_page": max(1, min(80, per_page)),
    })
    req = urllib.request.Request(
        f"{PEXELS_VIDEO_SEARCH}?{params}",
        headers={"Authorization": api_key},
    )
    with urllib.request.urlopen(req, timeout=60) as resp:  # noqa: S310
        payload = json.loads(resp.read().decode("utf-8"))
    videos = payload.get("videos")
    return videos if isinstance(videos, list) else []


def resolve_queries(config, explicit: List[str]) -> List[str]:
    """Explicit ``--query`` values, else the show's curated queries."""
    if explicit:
        return [q for q in explicit if q.strip()]
    yt = getattr(config, "youtube", None)
    queries = list(getattr(yt, "image_queries", []) or [])
    if queries:
        return queries
    # Last resort: the show's keywords, with its disambiguating prefix
    # (the raw-keyword path is exactly what landmine #14 was about).
    prefix = str(getattr(yt, "image_query_prefix", "") or "").strip()
    return [f"{prefix} {k}".strip()
            for k in (getattr(config, "keywords", []) or [])]


def _download(url: str, dest: Path, *, max_bytes: int) -> bool:
    try:
        with urllib.request.urlopen(url, timeout=300) as resp:  # noqa: S310
            length = int(resp.headers.get("Content-Length") or 0)
            if length and length > max_bytes:
                logger.info("    skip (%.0f MB over cap)", length / 1e6)
                return False
            with dest.open("wb") as fh:
                shutil.copyfileobj(resp, fh)
        return True
    except Exception as exc:  # noqa: BLE001
        logger.warning("    download failed: %s", exc)
        dest.unlink(missing_ok=True)
        return False


def _write_provenance(out_dir: Path, rows: List[dict]) -> None:
    path = out_dir / "_provenance.json"
    existing: List[dict] = []
    if path.exists():
        try:
            loaded = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(loaded, list):
                existing = loaded
        except Exception:  # noqa: BLE001
            pass
    by_file: Dict[str, dict] = {
        r.get("file"): r for r in existing if isinstance(r, dict)
    }
    for row in rows:
        by_file[row["file"]] = row
    path.write_text(json.dumps(list(by_file.values()), indent=2),
                    encoding="utf-8")


def main() -> int:
    ap = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--show", required=True, help="Show slug (e.g. tesla)")
    ap.add_argument("--query", action="append", default=[],
                    help="override the show's image_queries (repeatable)")
    ap.add_argument("--orientation", default="landscape",
                    choices=["landscape", "portrait", "square"],
                    help="landscape for long-form, portrait for Shorts")
    ap.add_argument("--out-dir", default=None,
                    help="default: stock_broll/<slug>_<orientation>")
    ap.add_argument("--per-query", type=int, default=2,
                    help="clips to keep per query")
    ap.add_argument("--max", type=int, default=20, help="total clip cap")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    api_key = os.getenv("PEXELS_API_KEY", "").strip()
    if not api_key:
        logger.error("PEXELS_API_KEY is not set — it's the same key the "
                     "image pipeline uses; add it to .env")
        return 1
    try:
        config = load_config(f"shows/{args.show}.yaml")
    except Exception as exc:  # noqa: BLE001
        logger.error("Cannot load shows/%s.yaml: %s", args.show, exc)
        return 1

    queries = resolve_queries(config, args.query)
    if not queries:
        logger.error("%s has no image_queries and no keywords — pass "
                     "--query explicitly", args.show)
        return 1
    skip_terms = list(getattr(config.youtube, "image_safe_skip_terms", [])
                      or [])

    out_dir = Path(args.out_dir or
                   f"stock_broll/{args.show}_{args.orientation}")
    if not args.dry_run:
        out_dir.mkdir(parents=True, exist_ok=True)

    rows: List[dict] = []
    seen_ids = set()
    total = 0
    for query in queries:
        if total >= args.max:
            break
        try:
            videos = search_videos(query, api_key=api_key,
                                   orientation=args.orientation)
        except Exception as exc:  # noqa: BLE001
            logger.warning("%r: search failed (%s)", query, exc)
            continue
        kept = 0
        logger.info("%r: %d result(s)", query, len(videos))
        for video in videos:
            if kept >= args.per_query or total >= args.max:
                break
            vid = video.get("id")
            if vid in seen_ids:
                continue
            if not video_is_usable(video, skip_terms):
                continue
            chosen = pick_video_file(video, args.orientation)
            if not chosen:
                continue
            seen_ids.add(vid)
            dest = out_dir / safe_name(video, query)
            credit = build_attribution(video)
            logger.info("  %s  %sx%s  %ss  — %s", dest.name,
                        chosen.get("width"), chosen.get("height"),
                        video.get("duration"), credit)
            if args.dry_run:
                kept += 1
                total += 1
                continue
            if dest.exists():
                logger.info("    skip (exists)")
                continue
            if not _download(str(chosen["link"]), dest, max_bytes=MAX_BYTES):
                continue
            kept += 1
            total += 1
            rows.append({
                "file": dest.name,
                "source_file": f"pexels:{vid}",
                "query": query,
                "source_url": video.get("url", ""),
                "license": "Pexels License (API use requires attribution)",
                "attribution": credit,
            })

    if rows:
        _write_provenance(out_dir, rows)
    if args.dry_run:
        logger.info("dry run — %d clip(s) would be fetched", total)
        return 0
    logger.info("fetched %d clip(s) into %s — watch, delete the duds, then "
                "publish with scripts/build_broll_pool.py (attribution "
                "carries over automatically)", total, out_dir)
    return 0 if total else 1


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        logger.warning("interrupted")
        raise SystemExit(130)
