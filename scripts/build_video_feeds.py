#!/usr/bin/env python3
"""Build the video-podcast RSS feeds (July 2026 pilot).

For each show with ``video_podcast.enabled``, emit a standalone
Apple-ready video feed next to the canonical audio one:

    spacex_podcast.rss          (audio, canonical — never touched)
    spacex_podcast.video.rss    (the long-form MP4 of each episode)

Apple's 2026 HLS video experience is gated to a handful of hosting
partners and it ignores ``podcast:alternateEnclosure``, so a self-hosted
show reaches the Apple video player only through a plain MP4
``<enclosure>`` — and Apple's guidance is to publish video as a separate
show rather than mixing formats in one feed. Hence a second feed.

Feeds are rebuilt **fresh from each show's summaries JSON** (idempotent,
churn-suppressed), so this is safe to run nightly. ``run_show.py`` also
rebuilds a show's feed inline right after it publishes an episode; this
script is the sweep that repairs a feed whose inline build was skipped
(e.g. the episode run timed out after the R2 upload) and the entry point
for a manual rebuild.

A show with no episode carrying a video track yet is a clean no-op — an
empty feed is never written, because Apple rejects one.

Usage
-----
    python scripts/build_video_feeds.py --all
    python scripts/build_video_feeds.py spacex
    python scripts/build_video_feeds.py --all --dry-run
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path
from typing import List

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from engine.config import load_config  # noqa: E402
from engine.video_feed import (  # noqa: E402
    build_video_feed_for_show,
    video_feed_filename,
)

logging.basicConfig(level=logging.INFO, stream=sys.stdout,
                    format="%(levelname)s %(message)s")
logger = logging.getLogger("build_video_feeds")


def discover_show_slugs() -> List[str]:
    slugs = []
    for path in sorted((PROJECT_ROOT / "shows").glob("*.yaml")):
        name = path.stem
        if name.startswith("_") or name in {"network_meta", "pronunciation_map",
                                            "translation_overrides",
                                            "scaffold_pending"}:
            continue
        slugs.append(name)
    return slugs


def main() -> int:
    ap = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("show", nargs="?", help="Show slug (omit with --all)")
    ap.add_argument("--all", action="store_true",
                    help="Build feeds for every video-podcast show")
    ap.add_argument("--dry-run", action="store_true",
                    help="Report what would be built; write nothing")
    args = ap.parse_args()

    if not args.all and not args.show:
        ap.error("pass a show slug or --all")

    slugs = discover_show_slugs() if args.all else [args.show]
    built = 0
    for slug in slugs:
        try:
            config = load_config(PROJECT_ROOT / "shows" / f"{slug}.yaml")
        except FileNotFoundError:
            logger.warning("[%s] config not found — skipping", slug)
            continue
        except Exception as exc:  # noqa: BLE001 — one show must not block the rest
            logger.error("[%s] config load failed: %s", slug, exc)
            continue

        if not config.video_podcast.enabled:
            continue

        if args.dry_run:
            out = config.video_podcast.rss_file or video_feed_filename(
                config.publishing.rss_file)
            logger.info("[%s] would build %s", slug, out)
            continue

        try:
            result = build_video_feed_for_show(config, PROJECT_ROOT)
        except Exception as exc:  # noqa: BLE001
            logger.error("[%s] video feed build failed: %s", slug, exc)
            continue
        if result:
            built += 1
            logger.info("[%s] %s -> %d episodes", slug, result[0].name, result[1])

    logger.info("built %d video feed(s)", built)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
