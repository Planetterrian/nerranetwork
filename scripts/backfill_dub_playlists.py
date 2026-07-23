#!/usr/bin/env python3
"""Backfill language-channel playlists with already-published dub videos.

The dub pipelines only add a video to its show playlist *at publish time*
(``engine/ru_dub.py`` / ``engine/lang_dub.py``). Every video published
before the playlist existed — the entire RU catalog prior to July 2026,
when ``ru_podcast_playlist_id`` was finally wired — is therefore not in
any playlist. This script closes that gap, idempotently:

  1. For every show YAML, collect (language, playlist_id, index_path):
       * ``ru`` → ``youtube.ru_podcast_playlist_id`` +
         ``<output_dir>/youtube_videos.ru.json``
       * every entry of ``youtube.dub_playlist_ids`` (``fr`` → PL...) +
         ``<output_dir>/youtube_videos.<lang>.json``
  2. List the playlist's current members (1 quota unit / 50 videos).
  3. Insert only the missing videos, oldest first so playlist order
     roughly matches publish order (50 quota units per insert).

Quota math: ``playlistItems.insert`` costs 50 units and the default
per-project quota is 10,000/day, shared with the publish pipeline. The
``--max-inserts`` cap (default 120 ≈ 6,000 units) keeps a backfill run
from starving same-day uploads. The script is safe to re-run daily —
each run picks up where the last stopped — and prints how many videos
remain so the operator knows whether another run is needed.

Clean no-op when a channel's ``YOUTUBE_REFRESH_TOKEN_<CH>`` is unset,
same convention as every optional integration in this repo.

Usage::

    python scripts/backfill_dub_playlists.py                 # all languages
    python scripts/backfill_dub_playlists.py --lang ru       # one language
    python scripts/backfill_dub_playlists.py --dry-run       # report only
    python scripts/backfill_dub_playlists.py --max-inserts 60
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path
from typing import Dict, List, Set, Tuple

import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from engine.youtube import (  # noqa: E402
    add_video_to_playlist,
    get_channel_credentials_from_env,
)

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger("backfill_dub_playlists")


def collect_targets(lang_filter: str | None) -> List[Tuple[str, str, str, Path]]:
    """Return (show_slug, lang, playlist_id, index_path) for every wired dub."""
    targets: List[Tuple[str, str, str, Path]] = []
    for show_path in sorted((REPO_ROOT / "shows").glob("*.yaml")):
        if show_path.name.startswith("_"):
            continue
        try:
            data = yaml.safe_load(show_path.read_text(encoding="utf-8")) or {}
        except yaml.YAMLError:
            continue  # non-show helper files (queues, overrides, ...)
        if not isinstance(data, dict):
            continue
        yt = data.get("youtube") or {}
        episode = data.get("episode") or {}
        output_dir = episode.get("output_dir")
        if not (isinstance(yt, dict) and output_dir):
            continue

        wired: Dict[str, str] = {}
        ru_pl = (yt.get("ru_podcast_playlist_id") or "")
        if isinstance(ru_pl, str) and ru_pl.strip():
            wired["ru"] = ru_pl.strip()
        for lang, pl in (yt.get("dub_playlist_ids") or {}).items():
            if isinstance(pl, str) and pl.strip():
                wired[str(lang).lower()] = pl.strip()

        for lang, playlist_id in sorted(wired.items()):
            if lang_filter and lang != lang_filter:
                continue
            index_path = REPO_ROOT / output_dir / f"youtube_videos.{lang}.json"
            targets.append((show_path.stem, lang, playlist_id, index_path))
    return targets


def load_index_video_ids(index_path: Path) -> List[str]:
    """Video IDs from a ``youtube_videos.<lang>.json`` index, oldest first."""
    if not index_path.exists():
        return []
    try:
        data = json.loads(index_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        logger.warning("unreadable index %s: %s", index_path, exc)
        return []
    videos = data.get("videos") or []
    rows = [v for v in videos if isinstance(v, dict) and v.get("video_id")]
    # Indexes are newest-first; insert oldest-first for sane playlist order.
    rows.sort(key=lambda v: (str(v.get("published") or ""), v.get("episode") or 0))
    return [v["video_id"] for v in rows]


def fetch_playlist_video_ids(credentials, playlist_id: str) -> Set[str] | None:
    """All video IDs currently in the playlist (None on API error)."""
    from googleapiclient.discovery import build
    from googleapiclient.errors import HttpError

    youtube = build("youtube", "v3", credentials=credentials,
                    cache_discovery=False)
    found: Set[str] = set()
    page_token = None
    try:
        while True:
            resp = youtube.playlistItems().list(
                part="snippet", playlistId=playlist_id, maxResults=50,
                pageToken=page_token,
            ).execute()
            for item in resp.get("items", []):
                vid = (item.get("snippet", {}).get("resourceId", {})
                       .get("videoId"))
                if vid:
                    found.add(vid)
            page_token = resp.get("nextPageToken")
            if not page_token:
                return found
    except HttpError as exc:
        status = getattr(getattr(exc, "resp", None), "status", "?")
        logger.error("playlistItems.list failed for %s (HTTP %s): %s",
                     playlist_id, status, exc)
        return None


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--lang", help="only this language (e.g. ru, fr)")
    parser.add_argument("--max-inserts", type=int, default=120,
                        help="insert cap across the whole run "
                             "(50 quota units each; default 120)")
    parser.add_argument("--dry-run", action="store_true",
                        help="report what would be inserted, insert nothing")
    args = parser.parse_args()

    lang_filter = args.lang.strip().lower() if args.lang else None
    targets = collect_targets(lang_filter)
    if not targets:
        logger.info("no wired dub playlists found%s — nothing to do",
                    f" for lang={lang_filter}" if lang_filter else "")
        return 0

    creds_by_lang: Dict[str, object] = {}
    inserts_left = max(0, args.max_inserts)
    total_inserted = total_remaining = 0

    for show, lang, playlist_id, index_path in targets:
        if lang not in creds_by_lang:
            creds_by_lang[lang] = get_channel_credentials_from_env(lang)
        creds = creds_by_lang[lang]
        if creds is None:
            logger.info("%s/%s: no credentials for channel %r — skipped",
                        show, lang, lang)
            continue

        index_ids = load_index_video_ids(index_path)
        if not index_ids:
            logger.info("%s/%s: empty or missing index %s — skipped",
                        show, lang, index_path.name)
            continue

        existing = fetch_playlist_video_ids(creds, playlist_id)
        if existing is None:
            continue  # listing failed; don't blind-insert duplicates

        missing = [v for v in index_ids if v not in existing]
        if not missing:
            logger.info("%s/%s: complete (%d videos, nothing missing)",
                        show, lang, len(index_ids))
            continue

        logger.info("%s/%s: %d in index, %d in playlist, %d missing",
                    show, lang, len(index_ids), len(existing), len(missing))
        if args.dry_run:
            total_remaining += len(missing)
            continue

        attempted = 0
        for vid in missing:
            if inserts_left <= 0:
                break
            # Count the attempt against the cap either way — failures
            # still spend quota, and a systematic failure must not loop.
            attempted += 1
            inserts_left -= 1
            if add_video_to_playlist(credentials=creds, video_id=vid,
                                     playlist_id=playlist_id):
                total_inserted += 1
        total_remaining += len(missing) - attempted

    logger.info("done: %d inserted, %d remaining (re-run tomorrow if > 0)",
                total_inserted, total_remaining)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
