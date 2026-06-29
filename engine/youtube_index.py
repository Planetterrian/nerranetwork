"""Per-show index of published YouTube videos → episode metadata.

The recursive YouTube-feedback loop (``scripts/fetch_youtube_analytics.py``
→ ``scripts/update_youtube_performance.py``) needs to map a bare YouTube
``video_id`` back to *which show, episode, and topic* produced it, so the
analytics it reads (views / retention) can be attributed to content
choices. The Analytics API returns metrics keyed by ``video_id`` only — it
knows nothing about Nerra's shows.

This module maintains ``digests/<slug>/youtube_videos.json`` (one file per
show) as that mapping. Each successful upload appends one record to its own
show's file; the analytics fetcher reads every show's file. It is small (one
row per upload), text-only, and committed with the episode — no media, so it
does not touch landmine #1.

**Per-show, not network-wide, on purpose:** up to a dozen show jobs run
concurrently in the daily matrix. A single shared index would have every job
racing to commit/push the same file — exactly the cross-show push-contention
class fixed in June 2026 (landmine #23 / the blog.rss/network.rss exclusion).
A per-show file is only ever written by that show's own (serialised) job.

Schema (``schema_version`` 1)::

    {
      "schema_version": 1,
      "videos": [
        {
          "video_id": "abc123",
          "show_slug": "tesla",
          "episode": 526,
          "kind": "long" | "short",
          "title": "<the published YouTube title>",
          "hook": "<episode hook / spoken lead>",
          "published": "2026-06-29",
          "watch_url": "https://www.youtube.com/watch?v=abc123",
          "channel": "en" | "ru"
        },
        ...
      ]
    }

Idempotent: re-recording the same ``video_id`` updates the existing row
rather than duplicating it (a re-run of the same episode keeps one entry).
All writes are best-effort — a failure here must never break a publish, so
callers wrap the call defensively (the recorder also swallows its own IO
errors and logs).
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

_SCHEMA_VERSION = 1
# Per-show index lives in the show's own output dir.
_INDEX_FILENAME = "youtube_videos.json"


def index_path_for(show_slug: str) -> Path:
    """``digests/<slug>/youtube_videos.json`` for *show_slug*."""
    return Path("digests") / (show_slug or "_unknown") / _INDEX_FILENAME


# Keep each show's index from growing without bound — newest-first cap. A
# show ships ≤3 videos/day, so 1000 rows ≈ ~10 months of history, plenty for
# a 30-90 day performance window while staying a small text file.
_MAX_ROWS = 1000


def _load(path: Path) -> dict:
    if not path.exists():
        return {"schema_version": _SCHEMA_VERSION, "videos": []}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict) or not isinstance(data.get("videos"), list):
            raise ValueError("malformed index")
        return data
    except Exception as exc:  # corrupt file shouldn't lose new data
        logger.warning("youtube_videos.json unreadable (%s) — starting fresh", exc)
        return {"schema_version": _SCHEMA_VERSION, "videos": []}


def record_video(
    *,
    video_id: str,
    show_slug: str,
    episode: int,
    kind: str,
    title: str = "",
    hook: str = "",
    published: str = "",
    watch_url: str = "",
    channel: str = "en",
    index_path: Optional[Path] = None,
) -> bool:
    """Append (or update) one published-video record. Best-effort.

    Returns True when the index was written, False on any no-op/error
    (missing ``video_id``, IO failure). Never raises — callers publish
    regardless of the feedback bookkeeping.
    """
    if not video_id:
        return False
    path = Path(index_path) if index_path else index_path_for(show_slug)
    try:
        data = _load(path)
        videos = data["videos"]
        row = {
            "video_id": video_id,
            "show_slug": show_slug,
            "episode": int(episode) if episode is not None else None,
            "kind": kind,
            "title": (title or "")[:300],
            "hook": (hook or "")[:300],
            "published": published,
            "watch_url": watch_url,
            "channel": channel,
        }
        # Idempotent upsert keyed on video_id.
        for i, existing in enumerate(videos):
            if existing.get("video_id") == video_id:
                videos[i] = row
                break
        else:
            videos.append(row)
        # Newest-first cap (keep the tail = most recent appends).
        if len(videos) > _MAX_ROWS:
            data["videos"] = videos[-_MAX_ROWS:]
        data["schema_version"] = _SCHEMA_VERSION
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        return True
    except Exception as exc:
        logger.warning("Could not record video %s in index: %s", video_id, exc)
        return False
