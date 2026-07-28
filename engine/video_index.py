"""Durable per-show index of hosted episode videos.

Why this exists
---------------
:mod:`engine.video_feed` builds the video-podcast feed from each show's
``summaries_<slug>.json``, and ``engine.publisher.save_summary_to_github_pages``
truncates that file to its newest **30** records (``max_summaries``). The
pilot documented the consequence — ``VideoPodcastConfig.max_episodes`` notes
it is "capped in practice by the summaries file's own 30-record window" — but
two effects deserve their own fix rather than a caveat:

* ``max_episodes`` is not actually a knob. Raising it above 30 changes
  nothing, because the records are gone.
* An episode that ages out of summaries **leaves the feed**, and Apple
  de-lists what leaves a feed. The MP4 stays in R2 forever (the pilot
  deliberately ships no retention sweep), so a month in you are paying to
  store objects that nothing indexes and no rebuild can recover.

Neither is visible until day 31, which is exactly the kind of thing that
should be caught by structure rather than by noticing.

So the authoritative "this episode has a video at this URL with this many
bytes" record lives here, in ``digests/<slug>/video_assets.json``, which
nothing truncates. Summaries is still consulted first for title and
description text (the operator edits summaries; this file is machine-owned),
and the feed falls back to this index for anything summaries has forgotten.

Shape and discipline follow :mod:`engine.youtube_index` — including *why it
is per-show*: up to a dozen show jobs run concurrently in the daily matrix,
and a single network-wide file would have every job racing to commit the
same path. A per-show file is only ever written by that show's own
serialised job.

Schema (``schema_version`` 1)::

    {
      "schema_version": 1,
      "videos": [
        {
          "episode": 553,
          "url": "https://audio.nerranetwork.com/video/tesla/..._Ep553_20260726.mp4",
          "bytes": 168231044,
          "duration_sec": 692.3,
          "filename": "Tesla_Shorts_Time_Pod_Ep553_20260726.mp4",
          "date": "2026-07-26",
          "title": "Ep 553: ...",
          "recorded": "2026-07-26T16:04:11+00:00"
        },
        ...
      ]
    }

Every write is best-effort and swallows its own errors: a bookkeeping
failure must never break an episode publish.
"""

from __future__ import annotations

import datetime as _dt
import json
import logging
import os
from pathlib import Path
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parent.parent

_SCHEMA_VERSION = 1
_INDEX_FILENAME = "video_assets.json"
# ~13 months for a daily show. Bounds the committed JSON while comfortably
# outliving any feed window an operator would set.
_MAX_ROWS = 400


def index_path(config, project_root: Optional[Path] = None) -> Path:
    """``digests/<show output dir>/video_assets.json`` for *config*.

    *project_root* defaults to the real repo root but is threaded through by
    callers that operate on an alternate tree (tests, a staged checkout) —
    resolving it against the module constant instead would silently read the
    live repo's index while writing a sandbox feed.
    """
    return Path(project_root or PROJECT_ROOT) / config.episode.output_dir / _INDEX_FILENAME


def load_index(path: Path) -> dict:
    """Read the index, returning an empty skeleton when absent or corrupt."""
    path = Path(path)
    if not path.exists():
        return {"schema_version": _SCHEMA_VERSION, "videos": []}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(data, dict) and isinstance(data.get("videos"), list):
            return data
        logger.warning("Unrecognized video index shape in %s — starting fresh", path)
    except Exception as exc:  # noqa: BLE001 — a corrupt index must not break a publish
        logger.warning("Could not read video index %s: %s", path, exc)
    return {"schema_version": _SCHEMA_VERSION, "videos": []}


def indexed_episodes(path: Path) -> Dict[int, dict]:
    """``{episode_num: row}`` for every row carrying a usable video.

    A row with no URL, or a zero byte length, is dropped: zero length is the
    fingerprint of a half-finished upload and Apple's validator flags it.
    """
    out: Dict[int, dict] = {}
    for row in load_index(path).get("videos", []):
        try:
            ep = int(row.get("episode"))
        except (TypeError, ValueError):
            continue
        if row.get("url") and int(row.get("bytes") or 0) > 0:
            out[ep] = row
    return out


def record_video(
    *,
    config,
    episode: int,
    url: str,
    bytes: int,  # noqa: A002 — matches the field name in the schema
    duration_sec: float = 0.0,
    filename: str = "",
    date: str = "",
    title: str = "",
    image_url: str = "",
    project_root: Optional[Path] = None,
) -> bool:
    """Record one episode's hosted video. Idempotent on *episode*.

    Re-recording replaces the existing row rather than duplicating it, so a
    re-run or a ``--force`` backfill converges. Returns True on success and
    never raises.
    """
    path = index_path(config, project_root)
    try:
        data = load_index(path)
        rows: List[dict] = [r for r in data.get("videos", [])
                            if r.get("episode") != episode]
        rows.append({
            "episode": int(episode),
            "url": url,
            "bytes": int(bytes or 0),
            "duration_sec": float(duration_sec or 0.0),
            "filename": filename,
            "date": date,
            "title": title,
            # Square per-episode artwork for the feed's item-level
            # <itunes:image>. Empty on every row written before
            # engine.episode_art existed; the feed then inherits the
            # channel cover, which is the pre-existing behaviour.
            "image_url": image_url or "",
            "recorded": _dt.datetime.now(_dt.timezone.utc).isoformat(),
        })
        rows.sort(key=lambda r: r.get("episode") or 0, reverse=True)
        data["schema_version"] = _SCHEMA_VERSION
        data["videos"] = rows[:_MAX_ROWS]

        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        os.replace(tmp, path)
        logger.info("Recorded episode video for ep%s in %s", episode, path.name)
        return True
    except Exception as exc:  # noqa: BLE001 — bookkeeping never breaks a publish
        logger.warning("Could not record episode video for ep%s: %s", episode, exc)
        return False


def record_from_track(config, episode: int, track: dict, *,
                      date: str = "", title: str = "",
                      project_root: Optional[Path] = None) -> bool:
    """Convenience wrapper over the dict ``video_feed.upload_episode_video`` returns."""
    if not (track and track.get("url")):
        return False
    return record_video(
        config=config,
        episode=episode,
        url=track["url"],
        bytes=int(track.get("bytes") or 0),
        duration_sec=float(track.get("duration_sec") or 0.0),
        filename=track.get("filename") or "",
        date=date,
        title=title,
        image_url=track.get("image_url") or "",
        project_root=project_root,
    )
