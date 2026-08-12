#!/usr/bin/env python3
"""Publish language-dubbed videos (engine.lang_dub) for opted-in shows.

The generalized sibling of ``publish_ru_dubs.py`` (which keeps serving
@NerraRU on the bespoke ``engine.ru_dub``). Runs AFTER
``scripts/generate_translations.py`` in the decoupled multilingual workflow:
for each show whose ``youtube.dub_languages`` includes ``--lang``, builds a
video from the episode's already-generated language audio track (reusing the
gallery scene images) and uploads it to that language's channel.

Idempotent: skips episodes whose dub is already recorded in the per-show
``youtube_videos.<lang>.json`` index unless ``--force``. A ``no_scenes_yet``
deferral is recorded as a status-only row and does NOT count as done — the
next sweep retries it. Clean no-op when the channel token
(``YOUTUBE_REFRESH_TOKEN_<CH>``) is unset — the pipeline ships dormant until
the operator creates the channel and adds the secret.

Usage::

    python scripts/publish_lang_dubs.py all --lang fr --latest 2
    python scripts/publish_lang_dubs.py tesla --lang fr --episode 543
    python scripts/publish_lang_dubs.py all --lang fr --dry-run
"""

from __future__ import annotations

import argparse
import datetime as _dt
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

from engine import lang_dub  # noqa: E402
from engine.config import discover_show_slugs, load_config  # noqa: E402
from engine.summaries_io import load_summaries  # noqa: E402

logging.basicConfig(level=logging.INFO, stream=sys.stdout,
                    format="%(levelname)s %(message)s")
logger = logging.getLogger("publish_lang_dubs")


def _dub_shows(lang: str) -> List[str]:
    out = []
    for slug in discover_show_slugs():
        try:
            cfg = load_config(f"shows/{slug}.yaml")
        except Exception:  # noqa: BLE001
            continue
        if lang in lang_dub.dub_languages_for(cfg):
            out.append(slug)
    return out


def _read_index(config, lang: str) -> dict:
    idx = lang_dub.index_path(config, lang)
    try:
        return json.loads(idx.read_text(encoding="utf-8")) if idx.exists() else {}
    except Exception:  # noqa: BLE001
        return {}


def _write_index(config, lang: str, data: dict) -> None:
    idx = lang_dub.index_path(config, lang)
    try:
        idx.parent.mkdir(parents=True, exist_ok=True)
        idx.write_text(json.dumps(data, ensure_ascii=False, indent=2),
                       encoding="utf-8")
    except OSError as exc:
        logger.warning("Could not write %s: %s", idx, exc)


def _already_done(config, lang: str, episode_num: int) -> bool:
    # Same semantics as publish_ru_dubs: any uploaded video (long or short,
    # row with a video_id) marks the episode done; status-only rows
    # (deferrals / failures) do not.
    data = _read_index(config, lang)
    return any(v.get("episode") == episode_num
               and v.get("kind") in ("long", "short")
               and v.get("video_id")
               for v in data.get("videos", []))


def _record_status_row(config, lang: str, episode_num: int, *,
                       kind: str, status: str, **extra) -> None:
    data = _read_index(config, lang)
    videos = data.setdefault("videos", [])
    videos[:] = [v for v in videos
                 if not (v.get("episode") == episode_num
                         and v.get("kind") == kind
                         and v.get("status") == status)]
    # ``channel`` rides on every row in a per-language index — consumers
    # (analytics glob, retitle channel scoping, its drift guard) treat a
    # channel-less record as a foreign body.
    row = {"episode": episode_num, "kind": kind, "status": status,
           "channel": lang,
           "recorded": _dt.datetime.now(_dt.timezone.utc).isoformat()}
    row.update({k: v for k, v in extra.items() if v is not None})
    videos.append(row)
    _write_index(config, lang, data)


def _clear_status_row(config, lang: str, episode_num: int, *,
                      kind: str, status: str) -> None:
    data = _read_index(config, lang)
    videos = data.get("videos", [])
    kept = [v for v in videos
            if not (v.get("episode") == episode_num
                    and v.get("kind") == kind
                    and v.get("status") == status)]
    if len(kept) != len(videos):
        data["videos"] = kept
        _write_index(config, lang, data)


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
    ap = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("show",
                    help='Show slug, or "all" for every opted-in show')
    ap.add_argument("--lang", required=True,
                    help="Registry language code (e.g. fr)")
    ap.add_argument("--latest", type=int, default=2,
                    help="Most recent N episodes")
    ap.add_argument("--episode", type=int, default=None,
                    help="One specific episode")
    ap.add_argument("--force", action="store_true",
                    help="Re-publish even if recorded")
    ap.add_argument("--no-short", action="store_true", help="Long-form only")
    ap.add_argument("--dry-run", action="store_true",
                    help="Resolve only; no render/upload")
    args = ap.parse_args()

    lang = args.lang.strip().lower()
    if lang not in lang_dub.DUB_LANGUAGES:
        logger.error("Unknown dub language %r (registry: %s)",
                     lang, sorted(lang_dub.DUB_LANGUAGES))
        return 1

    slugs = _dub_shows(lang) if args.show == "all" else [args.show]
    if not slugs:
        logger.info("No shows opted into %s dubs — nothing to do "
                    "(clean no-op).", lang)
        return 0

    total = 0
    for slug in slugs:
        try:
            config = load_config(f"shows/{slug}.yaml")
        except Exception as exc:  # noqa: BLE001
            logger.warning("%s: cannot load config (%s) — skip", slug, exc)
            continue
        if lang not in lang_dub.dub_languages_for(config):
            logger.info("%s: %s dub not enabled — skip", slug, lang)
            continue
        for ep in _select_episodes(config, args.latest, args.episode):
            if (not args.force and not args.dry_run
                    and _already_done(config, lang, ep)):
                logger.info("%s Ep%s: %s dub already recorded — skip",
                            slug, ep, lang)
                continue
            res = lang_dub.publish_lang_dub(
                config, ep, lang,
                build_short=not args.no_short, dry_run=args.dry_run)
            logger.info("%s Ep%s [%s]: %s", slug, ep, lang,
                        res.get("status"))
            if res.get("status") == "no_scenes_yet" and not args.dry_run:
                _record_status_row(config, lang, ep, kind="long",
                                   status="deferred",
                                   reason="no_scenes_yet")
            elif res.get("status") == "done":
                _clear_status_row(config, lang, ep, kind="long",
                                  status="deferred")
            if res.get("short_error") and not args.dry_run:
                _record_status_row(config, lang, ep, kind="short",
                                   status="failed",
                                   error=str(res["short_error"])[:300])
            elif res.get("short_url"):
                _clear_status_row(config, lang, ep, kind="short",
                                  status="failed")
            if res.get("status") in ("done", "dryrun"):
                total += 1
    logger.info("%s dubs processed: %d", lang, total)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
