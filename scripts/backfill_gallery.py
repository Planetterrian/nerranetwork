#!/usr/bin/env python3
"""Backfill the gallery R2 bucket with persisted scene images.

Phase 1 of the gallery feature ships forward-only ingestion via
``engine.gallery_uploader``. Historical episodes generated their
slideshow scenes inside ephemeral CI work directories
(``digests/<show>/youtube_tmp/scenes_ep<NNN>/``); those paths are in
the project's ``.gitignore`` and were reclaimed when each CI container
ended. As a result, **the on-repo state of the YouTube-enabled shows
(Tesla Shorts Time and Models & Agents for Beginners) carries no
historical scene imagery to backfill from.**

This script does the best the on-repo state allows:

* Scans the two YouTube-enabled shows for any persisted
  ``scenes_ep<NNN>/`` directory (in case a future workflow keeps them).
* Accepts an optional ``--from-dir <path>`` flag pointing at an
  externally-staged archive of CI work directories (e.g. a tar dump
  the operator pulled from an old runner) and walks it the same way.
* For every scene found, reconstructs metadata from
  ``summaries_*.json`` in the show's digests directory (episode number
  from the ``scenes_ep<NNN>`` directory name → ``episode_title`` and
  ``episode_date`` from the matching summary row).
* Uploads each scene via ``engine.gallery_uploader.upload_image``
  using the same R2 settings the live pipeline reads.

Run::

    python scripts/backfill_gallery.py            # dry-run, repo scan only
    python scripts/backfill_gallery.py --execute  # actually upload
    python scripts/backfill_gallery.py --from-dir /tmp/old_ci_artifacts --execute

Without ``--execute`` the script prints the planned uploads and exits
without touching R2. Honour this default — once a sidecar is in R2 it
becomes part of the gallery manifest.
"""

from __future__ import annotations

import argparse
import json
import logging
import re
import sys
from pathlib import Path
from typing import Dict, Iterable, List, Optional

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from engine.gallery_uploader import (  # noqa: E402
    ImageMetadata,
    gallery_config_from_env,
    upload_image,
)

logger = logging.getLogger("backfill_gallery")


# Two shows currently have ``youtube.enabled: true`` (CLAUDE.md
# landmine #20). Add more here when YouTube uploads are re-enabled.
BACKFILL_SHOWS = [
    {
        "slug": "tesla",
        "name": "Tesla Shorts Time",
        "digests_dir": "digests/tesla_shorts_time",
        "summaries_file": "digests/tesla_shorts_time/summaries_tesla.json",
    },
    {
        "slug": "models_agents_beginners",
        "name": "Models & Agents for Beginners",
        "digests_dir": "digests/models_agents_beginners",
        "summaries_file": (
            "digests/models_agents_beginners/"
            "summaries_models_agents_beginners.json"
        ),
    },
]


_SCENE_DIR_RE = re.compile(r"^scenes_ep(?P<num>\d{3})(?P<suffix>_short)?$")
_SCENE_FILE_RE = re.compile(r"^grok_(?P<idx>\d+)\.(?P<ext>jpe?g|png|webp)$", re.I)


def _load_summaries(summaries_path: Path) -> Dict[int, Dict]:
    """Return ``{episode_num: summary_row}`` keyed by episode number."""
    if not summaries_path.exists():
        logger.warning("Summaries file missing: %s", summaries_path)
        return {}
    try:
        data = json.loads(summaries_path.read_text(encoding="utf-8"))
    except Exception as exc:  # noqa: BLE001
        logger.error("Failed to parse %s: %s", summaries_path, exc)
        return {}
    rows = data.get("summaries", []) if isinstance(data, dict) else []
    out: Dict[int, Dict] = {}
    for row in rows:
        if not isinstance(row, dict):
            continue
        n = row.get("episode_num")
        if isinstance(n, int):
            out[n] = row
    return out


def _iter_scene_dirs(root: Path) -> Iterable[Path]:
    """Yield every ``scenes_ep<NNN>[/]_short`` directory under root."""
    if not root.exists():
        return
    for path in root.rglob("scenes_ep*"):
        if path.is_dir() and _SCENE_DIR_RE.match(path.name):
            yield path


def _scenes_in(dir_path: Path) -> List[Path]:
    return sorted(
        p for p in dir_path.iterdir()
        if p.is_file() and _SCENE_FILE_RE.match(p.name)
    )


def _intended_use_for(scene_dir_name: str) -> str:
    return "social" if scene_dir_name.endswith("_short") else "segment_card"


def _build_metadata(
    *,
    show: Dict,
    episode_num: int,
    summary_row: Optional[Dict],
    scene_dir_name: str,
) -> ImageMetadata:
    title = ""
    episode_date = ""
    if summary_row:
        title = str(summary_row.get("episode_title") or "")
        episode_date = str(summary_row.get("date") or "")
    if not title:
        title = f"Ep {episode_num}"
    if not episode_date:
        # Best-effort: leave blank so the manifest builder can flag it.
        episode_date = "unknown"

    intended_use = _intended_use_for(scene_dir_name)
    return ImageMetadata(
        image_id="",
        show_slug=show["slug"],
        show_name=show["name"],
        episode_id=f"ep{episode_num:03d}",
        episode_title=title,
        episode_date=episode_date,
        prompt="",  # Unrecoverable for historical episodes — prompts
                    # were never persisted alongside the images.
        model="grok-imagine-image",  # Was the only image source.
        intended_use=intended_use,
        tags=[show["slug"], intended_use, "grok-imagine", "backfill"],
    )


def _process_show(
    show: Dict,
    *,
    scan_roots: List[Path],
    execute: bool,
) -> Dict[str, int]:
    """Scan a show's roots, upload (or print) what we find. Returns counters."""
    summaries = _load_summaries(PROJECT_ROOT / show["summaries_file"])

    planned = 0
    uploaded = 0
    failed = 0
    seen_dirs: List[Path] = []

    for root in scan_roots:
        for scene_dir in _iter_scene_dirs(root):
            seen_dirs.append(scene_dir)
            match = _SCENE_DIR_RE.match(scene_dir.name)
            if not match:
                continue
            episode_num = int(match.group("num"))
            for scene_file in _scenes_in(scene_dir):
                planned += 1
                if not execute:
                    logger.info(
                        "[dry-run] would upload %s (ep%d, %s)",
                        scene_file, episode_num, scene_dir.name,
                    )
                    continue
                try:
                    image_bytes = scene_file.read_bytes()
                except Exception as exc:  # noqa: BLE001
                    logger.error("Read failed for %s: %s", scene_file, exc)
                    failed += 1
                    continue
                metadata = _build_metadata(
                    show=show,
                    episode_num=episode_num,
                    summary_row=summaries.get(episode_num),
                    scene_dir_name=scene_dir.name,
                )
                result = upload_image(image_bytes, metadata)
                if result is None:
                    failed += 1
                    logger.warning(
                        "Upload returned None for %s — see prior log lines",
                        scene_file,
                    )
                else:
                    uploaded += 1
                    logger.info(
                        "Uploaded %s → %s", scene_file.name, result.original_url,
                    )

    if not seen_dirs:
        logger.info(
            "No scenes_ep<NNN>/ directories found for %s. Historical "
            "scenes were never persisted on this repo (see .gitignore). "
            "Pass --from-dir to point at an external archive of CI work "
            "directories if you have one staged.",
            show["slug"],
        )

    return {"planned": planned, "uploaded": uploaded, "failed": failed}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--from-dir", type=Path, default=None,
        help="Optional path to an external archive of CI work "
             "directories to scan in addition to the repo.",
    )
    parser.add_argument(
        "--execute", action="store_true",
        help="Actually upload to R2 instead of dry-running.",
    )
    parser.add_argument(
        "--shows", nargs="*", default=None,
        help="Limit to a subset of slugs (defaults to all YouTube shows).",
    )
    parser.add_argument(
        "-v", "--verbose", action="store_true",
    )
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )

    if args.execute:
        gconfig = gallery_config_from_env()
        if not gconfig.is_configured:
            logger.error(
                "Gallery R2 not configured — set R2_GALLERY_BUCKET, "
                "R2_ENDPOINT_URL, R2_ACCESS_KEY_ID, R2_SECRET_ACCESS_KEY "
                "before re-running with --execute.",
            )
            return 2

    shows = BACKFILL_SHOWS
    if args.shows:
        wanted = set(args.shows)
        shows = [s for s in BACKFILL_SHOWS if s["slug"] in wanted]
        if not shows:
            logger.error("No matching shows for: %s", args.shows)
            return 2

    totals = {"planned": 0, "uploaded": 0, "failed": 0}
    for show in shows:
        scan_roots = [PROJECT_ROOT / show["digests_dir"]]
        if args.from_dir is not None:
            scan_roots.append(args.from_dir.resolve())
        logger.info(
            "--- %s (%s) ---", show["name"], show["slug"],
        )
        counters = _process_show(
            show, scan_roots=scan_roots, execute=args.execute,
        )
        for key, val in counters.items():
            totals[key] += val
        logger.info("Show counters: %s", counters)

    logger.info("Total: %s", totals)
    if not args.execute:
        logger.info("Dry-run only. Re-run with --execute to upload.")
    return 0 if totals["failed"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
