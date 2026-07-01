#!/usr/bin/env python3
"""Publish Russian-dubbed videos to @NerraRU for the opted-in English shows.

Runs AFTER ``scripts/generate_translations.py`` in the decoupled multilingual
workflow: for each show with ``youtube.ru_dub_enabled`` it builds a video from
the episode's already-generated Russian audio track (reusing the gallery scene
images) and uploads it to the @NerraRU channel. See ``engine.ru_dub`` /
``docs/ru_youtube_dubs.md``.

Idempotent: skips episodes whose RU video is already recorded in the per-show
``youtube_videos.ru.json`` index unless ``--force``. A ``no_scenes_yet``
deferral (fresh episode whose gallery scenes haven't reached the committed
manifest yet) is recorded as a status-only row and does NOT count as done —
the next sweep retries it with the real scenes.

Usage::

    python scripts/publish_ru_dubs.py all --latest 2
    python scripts/publish_ru_dubs.py tesla --episode 526
    python scripts/publish_ru_dubs.py all --dry-run
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path
from typing import List, Optional

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from dotenv import load_dotenv  # noqa: E402

load_dotenv(PROJECT_ROOT / ".env")

from engine import ru_dub  # noqa: E402
from engine.config import discover_show_slugs, load_config  # noqa: E402
from engine.summaries_io import load_summaries  # noqa: E402

logging.basicConfig(level=logging.INFO, stream=sys.stdout,
                    format="%(levelname)s %(message)s")
logger = logging.getLogger("publish_ru_dubs")


def _ru_dub_shows() -> List[str]:
    out = []
    for slug in discover_show_slugs():
        try:
            cfg = load_config(f"shows/{slug}.yaml")
        except Exception:  # noqa: BLE001
            continue
        yt = getattr(cfg, "youtube", None)
        if yt and getattr(yt, "ru_dub_enabled", False):
            out.append(slug)
    return out


def _index_path(config) -> Path:
    return PROJECT_ROOT / config.episode.output_dir / "youtube_videos.ru.json"


def _already_done(config, episode_num: int) -> bool:
    # Keyed on the LONG upload only: engine.ru_dub.publish_ru_dub has no
    # short-only path (it always renders + uploads the long first), so
    # retrying an episode whose Short failed would re-upload a duplicate
    # public long-form video. A failed Short is therefore NOT retried; it is
    # recorded durably in the index by _record_short_failure so the gap is
    # visible (re-publish with --force after fixing the cause).
    #
    # The row must carry a video_id: status-only rows (a short-failure row
    # or a no_scenes_yet deferral row) mean nothing was uploaded, so the
    # episode is NOT done and the next sweep retries it — that's the whole
    # point of the deferral (the gallery-manifest rebuild lags the newest
    # episode; retrying later picks up the real scenes).
    idx = _index_path(config)
    if not idx.exists():
        return False
    try:
        data = json.loads(idx.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return False
    return any(v.get("episode") == episode_num and v.get("kind") == "long"
               and v.get("video_id")
               for v in data.get("videos", []))


def _record_short_failure(config, episode_num: int, error: str) -> None:
    """Durably note a failed Short in the per-show RU index.

    The row has no ``video_id`` (nothing was uploaded), so every consumer
    that walks the index — the analytics fetch, the long-done check above —
    skips it; it exists purely so the operator can see which episodes shipped
    long-form-only instead of the failure living only in a runner log."""
    import datetime as _dt
    idx = _index_path(config)
    try:
        data = json.loads(idx.read_text(encoding="utf-8")) if idx.exists() else {}
    except Exception:  # noqa: BLE001
        data = {}
    videos = data.setdefault("videos", [])
    # Replace any previous failure row for this episode (keep one, latest).
    videos[:] = [v for v in videos
                 if not (v.get("episode") == episode_num
                         and v.get("kind") == "short"
                         and v.get("status") == "failed")]
    videos.append({
        "episode": episode_num,
        "kind": "short",
        "status": "failed",
        "error": (error or "")[:300],
        "recorded": _dt.datetime.now(_dt.timezone.utc).isoformat(),
    })
    try:
        idx.parent.mkdir(parents=True, exist_ok=True)
        idx.write_text(json.dumps(data, ensure_ascii=False, indent=2),
                       encoding="utf-8")
    except OSError as exc:
        logger.warning("Could not record short failure in %s: %s", idx, exc)


def _record_scenes_deferral(config, episode_num: int) -> None:
    """Durably note a ``no_scenes_yet`` deferral in the per-show RU index.

    Same conventions as ``_record_short_failure``: no ``video_id`` (nothing
    was uploaded — so ``_already_done`` treats the episode as NOT done and
    the next sweep retries once the gallery-manifest rebuild catches up),
    one row per episode (latest wins), and the row exists so the operator
    can see WHY an episode's RU dub hasn't shipped yet instead of the
    deferral living only in a runner log."""
    import datetime as _dt
    idx = _index_path(config)
    try:
        data = json.loads(idx.read_text(encoding="utf-8")) if idx.exists() else {}
    except Exception:  # noqa: BLE001
        data = {}
    videos = data.setdefault("videos", [])
    videos[:] = [v for v in videos
                 if not (v.get("episode") == episode_num
                         and v.get("kind") == "long"
                         and v.get("status") == "deferred")]
    videos.append({
        "episode": episode_num,
        "kind": "long",
        "status": "deferred",
        "reason": "no_scenes_yet",
        "recorded": _dt.datetime.now(_dt.timezone.utc).isoformat(),
    })
    try:
        idx.parent.mkdir(parents=True, exist_ok=True)
        idx.write_text(json.dumps(data, ensure_ascii=False, indent=2),
                       encoding="utf-8")
    except OSError as exc:
        logger.warning("Could not record scenes deferral in %s: %s", idx, exc)


def _clear_scenes_deferral(config, episode_num: int) -> None:
    """Drop a stale deferral row once the episode's long-form ships."""
    idx = _index_path(config)
    if not idx.exists():
        return
    try:
        data = json.loads(idx.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return
    videos = data.get("videos", [])
    kept = [v for v in videos
            if not (v.get("episode") == episode_num
                    and v.get("kind") == "long"
                    and v.get("status") == "deferred")]
    if len(kept) != len(videos):
        data["videos"] = kept
        try:
            idx.write_text(json.dumps(data, ensure_ascii=False, indent=2),
                           encoding="utf-8")
        except OSError as exc:
            logger.warning("Could not clear scenes deferral in %s: %s", idx, exc)


def _clear_short_failure(config, episode_num: int) -> None:
    """Drop a stale failure row once a --force re-publish ships the Short."""
    idx = _index_path(config)
    if not idx.exists():
        return
    try:
        data = json.loads(idx.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return
    videos = data.get("videos", [])
    kept = [v for v in videos
            if not (v.get("episode") == episode_num
                    and v.get("kind") == "short"
                    and v.get("status") == "failed")]
    if len(kept) != len(videos):
        data["videos"] = kept
        try:
            idx.write_text(json.dumps(data, ensure_ascii=False, indent=2),
                           encoding="utf-8")
        except OSError as exc:
            logger.warning("Could not clear short failure in %s: %s", idx, exc)


def _select_episodes(config, latest: int, episode: Optional[int]) -> List[int]:
    summaries_path = PROJECT_ROOT / config.publishing.summaries_json
    try:
        _w, records = load_summaries(summaries_path)
    except Exception:  # noqa: BLE001
        return []
    nums = sorted((r["episode_num"] for r in records
                   if isinstance(r.get("episode_num"), int)), reverse=True)
    if episode is not None:
        return [episode] if episode in nums else []
    return nums[:latest]


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("show", help='Show slug, or "all" for every ru_dub-enabled show')
    ap.add_argument("--latest", type=int, default=2, help="Most recent N episodes")
    ap.add_argument("--episode", type=int, default=None, help="One specific episode")
    ap.add_argument("--force", action="store_true", help="Re-publish even if recorded")
    ap.add_argument("--no-short", action="store_true", help="Long-form only")
    ap.add_argument("--dry-run", action="store_true", help="Resolve only; no render/upload")
    args = ap.parse_args()

    slugs = _ru_dub_shows() if args.show == "all" else [args.show]
    if not slugs:
        logger.info("No ru_dub-enabled shows — nothing to do (clean no-op).")
        return 0

    total = 0
    for slug in slugs:
        try:
            config = load_config(f"shows/{slug}.yaml")
        except Exception as exc:  # noqa: BLE001
            logger.warning("%s: cannot load config (%s) — skip", slug, exc)
            continue
        yt = getattr(config, "youtube", None)
        if not (yt and getattr(yt, "ru_dub_enabled", False)):
            logger.info("%s: ru_dub not enabled — skip", slug)
            continue
        for ep in _select_episodes(config, args.latest, args.episode):
            if not args.force and not args.dry_run and _already_done(config, ep):
                logger.info("%s Ep%s: RU dub already recorded — skip", slug, ep)
                continue
            res = ru_dub.publish_ru_dub(
                config, ep, build_short=not args.no_short, dry_run=args.dry_run)
            logger.info("%s Ep%s: %s", slug, ep, res.get("status"))
            if res.get("status") == "no_scenes_yet" and not args.dry_run:
                # Fresh episode whose gallery scenes aren't in the manifest
                # yet — record the deferral (visible + NOT done) so the next
                # sweep retries with the real scenes instead of the first
                # scene-less cover upload becoming final.
                logger.info("%s Ep%s: scenes not in gallery manifest yet — "
                            "deferred for the next sweep", slug, ep)
                _record_scenes_deferral(config, ep)
            elif res.get("status") == "done":
                _clear_scenes_deferral(config, ep)
            if res.get("short_error") and not args.dry_run:
                logger.warning("%s Ep%s: Short failed (long uploaded): %s",
                               slug, ep, res["short_error"])
                _record_short_failure(config, ep, str(res["short_error"]))
            elif res.get("short_url"):
                _clear_short_failure(config, ep)
            if res.get("status") in ("done", "dryrun"):
                total += 1
    logger.info("RU dubs processed: %d", total)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
