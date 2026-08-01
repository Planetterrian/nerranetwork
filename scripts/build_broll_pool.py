#!/usr/bin/env python3
"""Populate a show's evergreen b-roll pool from curated local clips.

The pool lets renders reuse video clips the network already paid for —
primarily the recovered Grok Video clips (46 Tesla Ep519 + 12 SpaceX Ep12,
16:9, silent) — instead of regenerating imagery. Consumers pull clips via
``engine.gallery_library.select_broll_clips``.

Operator workflow (end to end):

  1. Recover clips that still exist server-side (result URLs are temporary,
     so do this soon after a run)::

         GROK_API_KEY=... python scripts/recover_grok_video.py \\
             --out-dir recovered_ep519/

  2. Curate locally: watch the clips, delete the duds, keep only evergreen
     footage (generic Tesla factory shots, rockets on the pad — nothing
     dated like a specific headline overlay).

  3. Run this script to upload the keepers to R2 and index them::

         python scripts/build_broll_pool.py --show tesla \\
             recovered_ep519/ep519_clip02.mp4 recovered_ep519/ep519_clip05.mp4

Uploads go to the gallery R2 bucket (``R2_GALLERY_BUCKET``, same env vars as
``engine/gallery_uploader.py`` — ``R2_ENDPOINT_URL`` / ``R2_ACCESS_KEY_ID``
/ ``R2_SECRET_ACCESS_KEY`` / ``R2_GALLERY_PUBLIC_BASE_URL``) under a
``broll/<slug>/`` prefix, keyed by content hash so re-runs are idempotent.
Duration is probed via ffprobe (``engine.audio.get_audio_duration`` — the
format-level probe works for video files too).

The ONLY thing committed to git is the small ``digests/<dir>/broll.json``
index (entries: ``{"url", "duration_s", "label", "key"}``, merged by url,
stable order). Never ``git add`` the clips themselves — media in git is
landmine #1.

Usage::

    python scripts/build_broll_pool.py --show tesla clip1.mp4 clip2.mp4
    python scripts/build_broll_pool.py --show spacex --label "pad b-roll" clip.mp4
"""

from __future__ import annotations

import argparse
import datetime
import json
import logging
import sys
from pathlib import Path
from typing import List

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from dotenv import load_dotenv  # noqa: E402

load_dotenv(PROJECT_ROOT / ".env")

from engine.audio import get_audio_duration  # noqa: E402
from engine.config import load_config  # noqa: E402
from engine.gallery_uploader import (  # noqa: E402
    compute_image_id,
    gallery_config_from_env,
)
from engine.storage import upload_to_r2  # noqa: E402

logging.basicConfig(level=logging.INFO, stream=sys.stdout,
                    format="%(levelname)s %(message)s")
logger = logging.getLogger("build_broll_pool")

_VIDEO_CONTENT_TYPES = {
    ".mp4": "video/mp4",
    ".mov": "video/quicktime",
    ".webm": "video/webm",
    ".mkv": "video/x-matroska",
}


def attribution_for(clip: Path, explicit: str | None) -> str:
    """Resolve a clip's footage credit line.

    Precedence: the ``--attribution`` flag, then the ``attribution``
    field of a ``_provenance.json`` beside the clip (written by
    ``fetch_spacex_broll.py`` / ``fetch_nasa_broll.py``, keyed by file
    name), else empty. CC BY-sourced clips (SpaceX YouTube) NEED this to
    reach ``broll.json`` — the description credit the license requires
    is built from it.
    """
    if explicit:
        return explicit.strip()
    prov_path = clip.parent / "_provenance.json"
    if not prov_path.exists():
        return ""
    try:
        rows = json.loads(prov_path.read_text(encoding="utf-8"))
    except Exception as exc:  # noqa: BLE001
        logger.warning("%s unreadable (%s) — no attribution", prov_path, exc)
        return ""
    if not isinstance(rows, list):
        return ""
    for row in rows:
        if isinstance(row, dict) and row.get("file") == clip.name:
            return str(row.get("attribution") or "").strip()
    return ""


def _load_pool(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:  # noqa: BLE001
        logger.warning("Existing %s unreadable (%s) — starting fresh", path, exc)
        return {}
    if isinstance(data, list):  # tolerate a hand-written bare list
        return {"clips": data}
    return data if isinstance(data, dict) else {}


def main() -> int:
    ap = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--show", required=True, help="Show slug (e.g. tesla)")
    ap.add_argument("clips", nargs="+", type=Path,
                    help="Curated local clip files (.mp4/.mov/.webm)")
    ap.add_argument("--label", default=None,
                    help="Label for the uploaded clips (default: file stem)")
    ap.add_argument("--attribution", default=None,
                    help="Footage credit line for the uploaded clips "
                         "(default: looked up per clip in a sibling "
                         "_provenance.json from the fetch scripts)")
    args = ap.parse_args()

    try:
        config = load_config(f"shows/{args.show}.yaml")
    except Exception as exc:  # noqa: BLE001
        logger.error("Cannot load shows/%s.yaml: %s", args.show, exc)
        return 1
    pool_path = PROJECT_ROOT / config.episode.output_dir / "broll.json"

    gcfg = gallery_config_from_env()
    if not gcfg.is_configured:
        logger.error("Gallery R2 not configured — set R2_ENDPOINT_URL / "
                     "R2_ACCESS_KEY_ID / R2_SECRET_ACCESS_KEY "
                     "(+ optional R2_GALLERY_BUCKET / "
                     "R2_GALLERY_PUBLIC_BASE_URL).")
        return 1

    data = _load_pool(pool_path)
    clips: List[dict] = [c for c in data.get("clips", [])
                         if isinstance(c, dict) and c.get("url")]
    by_url = {c["url"]: c for c in clips}

    uploaded = 0
    for clip in args.clips:
        if not clip.exists():
            logger.error("%s: not found — skipped", clip)
            continue
        ext = clip.suffix.lower()
        content_type = _VIDEO_CONTENT_TYPES.get(ext)
        if content_type is None:
            logger.error("%s: unsupported extension %s — skipped", clip, ext)
            continue
        duration = get_audio_duration(clip)  # ffprobe format probe; video OK
        if not duration:
            logger.error("%s: ffprobe could not read a duration — skipped "
                         "(is it a valid video file?)", clip)
            continue
        # Content-hash key (same idempotency convention as gallery images):
        # re-running on the same bytes re-uploads to the same object.
        stem = compute_image_id(clip.read_bytes())
        key = f"broll/{args.show}/{stem}{ext}"
        try:
            url = upload_to_r2(
                clip, key,
                bucket=gcfg.bucket,
                endpoint_url=gcfg.endpoint_url,
                access_key=gcfg.access_key,
                secret_key=gcfg.secret_key,
                public_base_url=gcfg.public_base_url,
                content_type=content_type,
            )
        except Exception as exc:  # noqa: BLE001
            logger.error("%s: R2 upload failed (%s): %s — skipped",
                         clip, type(exc).__name__, exc)
            continue
        entry = {
            "url": url,
            "duration_s": round(float(duration), 2),
            "label": args.label or clip.stem,
            "key": key,
        }
        credit = attribution_for(clip, args.attribution)
        if credit:
            entry["attribution"] = credit
        if url in by_url:
            by_url[url].update(entry)  # refresh label/duration in place
        else:
            clips.append(entry)
            by_url[url] = entry
        uploaded += 1
        logger.info("%s → %s (%.1fs)", clip.name, url, duration)

    if not uploaded:
        logger.error("No clips uploaded — broll.json unchanged.")
        return 1

    data["show_slug"] = args.show
    data["updated"] = datetime.datetime.now(
        datetime.timezone.utc).isoformat(timespec="seconds")
    data["clips"] = clips
    pool_path.parent.mkdir(parents=True, exist_ok=True)
    pool_path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n",
                         encoding="utf-8")
    logger.info("Pool updated: %s (%d clip(s) total). Commit ONLY this JSON — "
                "never the media files.", pool_path, len(clips))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
