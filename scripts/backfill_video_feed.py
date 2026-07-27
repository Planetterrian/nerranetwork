#!/usr/bin/env python3
"""Seed a video podcast feed by re-rendering past episodes.

A newly enabled show's video feed contains only episodes published since it
was switched on — the long-form MP4s of everything earlier were deleted
after their YouTube upload. Apple reviews a feed before listing the show and
routinely rejects a sparse one, so a new video show wants a back catalogue
first.

Every input to the render survives (R2 audio, committed cover art, gallery
scene stills, committed transcripts) and ``build_long_form_video`` is pure
ffmpeg, so this costs runner time and no API spend.

    python scripts/backfill_video_feed.py spacex --latest 10
    python scripts/backfill_video_feed.py all --latest 10
    python scripts/backfill_video_feed.py tesla --episode 552 --force
    python scripts/backfill_video_feed.py all --verify

Requires the R2 credentials for the upload, and ``R2_GALLERY_BUCKET`` for
the scene stills: the public gallery CDN returns 403 for original JPEGs from
CI, so without the authenticated fallback every episode would quietly render
cover-only. The script refuses to start rather than produce a pile of those.
"""

from __future__ import annotations

import argparse
import logging
import os
import sys
from pathlib import Path
from typing import List

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from engine.config import load_config  # noqa: E402
from engine.summaries_io import load_summaries  # noqa: E402
from engine.video_backfill import backfill_episode_video  # noqa: E402
from engine.video_feed import build_video_feed_for_show  # noqa: E402

logging.basicConfig(level=logging.INFO, stream=sys.stdout,
                    format="%(levelname)s %(message)s")
logger = logging.getLogger("backfill_video_feed")


def video_podcast_slugs() -> List[str]:
    """Every show with ``video_podcast.enabled``."""
    slugs: List[str] = []
    for path in sorted((PROJECT_ROOT / "shows").glob("*.yaml")):
        if path.stem.startswith("_"):
            continue
        try:
            config = load_config(path)
        except Exception:  # noqa: BLE001 — non-show YAMLs live here too
            continue
        vp = getattr(config, "video_podcast", None)
        if vp and vp.enabled:
            slugs.append(path.stem)
    return slugs


def _select_episodes(config, args) -> List[int]:
    """Episode numbers to process, newest first."""
    if args.episode:
        return sorted(args.episode, reverse=True)

    summaries_path = PROJECT_ROOT / config.publishing.summaries_json
    try:
        _wrapper, records = load_summaries(summaries_path)
    except Exception as exc:  # noqa: BLE001
        logger.warning("[%s] could not read summaries: %s", config.slug, exc)
        return []

    eps = sorted(
        (int(r["episode_num"]) for r in records
         if r.get("episode_num") and r.get("audio_url")),
        reverse=True,
    )
    if args.from_episode:
        return [e for e in eps if e >= args.from_episode]
    return eps[: args.latest]


def _preflight(allow_no_scenes: bool) -> bool:
    missing = [v for v in ("R2_ENDPOINT_URL", "R2_ACCESS_KEY_ID",
                           "R2_SECRET_ACCESS_KEY")
               if not os.getenv(v, "").strip()]
    if missing:
        logger.error("::error::Missing R2 credentials: %s — every upload would fail",
                     ", ".join(missing))
        return False
    if not allow_no_scenes and not os.getenv("R2_GALLERY_BUCKET", "").strip():
        logger.error("::error::R2_GALLERY_BUCKET unset. The public gallery CDN "
                     "returns 403 for original JPEGs, so every episode would "
                     "render cover-only instead of with its scene stills. Set "
                     "it, or pass --allow-no-scenes if that is genuinely what "
                     "you want.")
        return False
    return True


def main() -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("show", help="Show slug, or 'all' for every video-podcast show")
    ap.add_argument("--latest", type=int, default=10,
                    help="Re-render the most recent N episodes (default 10)")
    ap.add_argument("--episode", type=int, action="append",
                    help="Specific episode number (repeatable)")
    ap.add_argument("--from-episode", type=int,
                    help="Every episode >= N present in summaries")
    ap.add_argument("--force", action="store_true",
                    help="Re-render even if already recorded")
    ap.add_argument("--verify", action="store_true",
                    help="HEAD each recorded URL; re-render on non-200")
    ap.add_argument("--dry-run", action="store_true",
                    help="Resolve assets and report; render nothing")
    ap.add_argument("--no-feed", action="store_true",
                    help="Skip the trailing feed rebuild")
    ap.add_argument("--allow-no-scenes", action="store_true",
                    help="Proceed without R2_GALLERY_BUCKET (cover-only renders)")
    args = ap.parse_args()

    if not args.dry_run and not _preflight(args.allow_no_scenes):
        return 1

    slugs = video_podcast_slugs() if args.show == "all" else [args.show]

    total_ok = total_attempted = 0
    for slug in slugs:
        try:
            config = load_config(PROJECT_ROOT / "shows" / f"{slug}.yaml")
        except FileNotFoundError:
            logger.warning("[%s] config not found — skipping", slug)
            continue

        episodes = _select_episodes(config, args)
        if not episodes:
            logger.warning("[%s] no episodes selected", slug)
            continue
        logger.info("[%s] %d episode(s): %s", slug, len(episodes),
                    ", ".join(str(e) for e in episodes))

        for ep in episodes:
            total_attempted += 1
            result = backfill_episode_video(
                config, ep, force=args.force, verify=args.verify,
                dry_run=args.dry_run)
            status = result.get("status")
            if status in ("ok", "already_done", "adopted", "would_render"):
                total_ok += 1
                extra = (f" ({result['scene_count']} scenes)"
                         if "scene_count" in result else "")
                logger.info("[%s] ep%s %s%s", slug, ep, status, extra)
            else:
                logger.error("[%s] ep%s %s %s", slug, ep, status,
                             result.get("error", ""))

        if not args.no_feed and not args.dry_run:
            try:
                built = build_video_feed_for_show(config, PROJECT_ROOT)
                if built:
                    logger.info("[%s] %s -> %d episodes", slug,
                                built[0].name, built[1])
            except Exception as exc:  # noqa: BLE001
                logger.error("[%s] feed rebuild failed: %s", slug, exc)

    logger.info("=" * 64)
    logger.info("Backfill: %d/%d episode(s) succeeded", total_ok, total_attempted)
    # Only a total wipeout is a failure — individual episodes legitimately
    # skip (aged out, no scenes) and must not fail the whole matrix job.
    return 0 if (total_ok or not total_attempted) else 1


if __name__ == "__main__":
    raise SystemExit(main())
