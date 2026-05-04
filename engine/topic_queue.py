"""Topic-queue picker for narrative-mode shows.

Narrative shows (e.g. ``Unintended Consequences``) don't run on RSS
news fetches — their input is a curated topic queue. This module
provides:

  - ``pick_next_topic(queue_path)`` — find the first ``produced: false``
    entry, return it as a dict (or ``None`` if the queue is empty /
    fully produced).

  - ``mark_topic_produced(queue_path, topic_id, episode_num, date_str)``
    — update the matching entry's ``produced`` / ``episode_number``
    / ``produced_date`` fields and rewrite the YAML in place.

The queue file is YAML with a top-level ``queue:`` list. Each entry
must have ``id`` (unique slug), ``title``, ``brief``, ``category``,
``produced``, ``episode_number``, ``produced_date``. Order matters
— the first ``produced: false`` entry wins.

Concurrency note: the runner is single-threaded per show and shows
don't share queue files, so file-level locking isn't required for
the current cron model. If parallel runs ever ship, swap in a
``fcntl.flock`` wrapper here.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Dict, Optional

import yaml

logger = logging.getLogger(__name__)


def _load_queue(queue_path: Path) -> Dict[str, Any]:
    """Load a queue YAML. Empty dict on missing file (callers handle)."""
    if not queue_path.exists():
        logger.warning("Topic queue file not found: %s", queue_path)
        return {}
    with queue_path.open("r", encoding="utf-8") as fh:
        data = yaml.safe_load(fh) or {}
    if not isinstance(data, dict) or "queue" not in data:
        logger.error(
            "Topic queue %s missing required top-level ``queue:`` list",
            queue_path,
        )
        return {}
    return data


def pick_next_topic(queue_path: Path) -> Optional[Dict[str, Any]]:
    """Return the first ``produced: false`` topic in the queue, or
    ``None`` if every topic has been produced (or the file is empty).

    The returned dict is a shallow copy — mutating it does NOT update
    the file. Use ``mark_topic_produced`` to record completion.
    """
    data = _load_queue(queue_path)
    queue = data.get("queue", [])
    for entry in queue:
        if not isinstance(entry, dict):
            continue
        if entry.get("produced") is True:
            continue
        # Defensive — make sure required fields are present.
        for required in ("id", "title", "brief"):
            if not entry.get(required):
                logger.error(
                    "Topic queue entry missing %r — skipping: %s",
                    required, entry,
                )
                break
        else:
            return dict(entry)  # shallow copy
    logger.warning(
        "Topic queue %s: every topic has been produced. "
        "Append new topics to keep the show running.",
        queue_path,
    )
    return None


def mark_topic_produced(
    queue_path: Path,
    topic_id: str,
    episode_num: int,
    produced_date: str,
) -> bool:
    """Mark *topic_id* as produced in *queue_path*.

    Returns ``True`` if the file was updated, ``False`` if the entry
    wasn't found (logs a warning either way).
    """
    if not queue_path.exists():
        logger.error(
            "mark_topic_produced: queue file missing: %s", queue_path,
        )
        return False

    with queue_path.open("r", encoding="utf-8") as fh:
        data = yaml.safe_load(fh) or {}
    queue = data.get("queue", [])

    updated = False
    for entry in queue:
        if not isinstance(entry, dict):
            continue
        if entry.get("id") == topic_id:
            entry["produced"] = True
            entry["episode_number"] = episode_num
            entry["produced_date"] = produced_date
            updated = True
            break

    if not updated:
        logger.warning(
            "mark_topic_produced: topic_id %r not found in %s",
            topic_id, queue_path,
        )
        return False

    # Re-write the file. ``allow_unicode=True`` so Cyrillic / emoji
    # in titles or briefs don't get \u-escaped. ``sort_keys=False``
    # so we preserve the queue order.
    with queue_path.open("w", encoding="utf-8") as fh:
        yaml.safe_dump(
            data, fh,
            allow_unicode=True,
            sort_keys=False,
            default_flow_style=False,
            width=10000,  # Don't line-wrap briefs
        )
    logger.info(
        "Topic queue updated: %s marked as produced in episode %d on %s",
        topic_id, episode_num, produced_date,
    )
    return True


def queue_health(queue_path: Path) -> Dict[str, int]:
    """Return ``{"total", "produced", "remaining"}`` for monitoring.

    Used by the dashboard / health-check workflow to alert when the
    queue is running low.
    """
    data = _load_queue(queue_path)
    queue = data.get("queue", [])
    total = len(queue)
    produced = sum(1 for e in queue if isinstance(e, dict) and e.get("produced") is True)
    return {"total": total, "produced": produced, "remaining": total - produced}
