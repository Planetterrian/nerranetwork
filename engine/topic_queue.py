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

#: A topic whose episode the source-integrity gate has blocked this many
#: times is DEFERRED by the picker (it stays in the queue, annotated, for
#: the operator to prune or re-clear). Without this, the gate's
#: queue-preserving skip turns one pathological topic into an indefinite
#: outage: UC re-picked "the-philippine-land-reform-and" on 2026-08-24 AND
#: -25 — its authoritative sources 403 GitHub runners, so the block was
#: deterministic and the show simply stopped publishing.
GATE_BLOCK_DEFER_THRESHOLD = 2


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
    deferred = 0
    for entry in queue:
        if not isinstance(entry, dict):
            continue
        if entry.get("produced") is True:
            continue
        if int(entry.get("gate_blocks") or 0) >= GATE_BLOCK_DEFER_THRESHOLD:
            # Loop-breaker: the source-integrity gate has blocked this
            # topic repeatedly — defer it so one bad topic can never take
            # the show down indefinitely. Loud, never silent.
            deferred += 1
            logger.warning(
                "Topic %r deferred: source-integrity gate blocked it %s "
                "time(s) (last %s) — operator should re-source or prune it "
                "in %s",
                entry.get("id"), entry.get("gate_blocks"),
                entry.get("gate_blocked_last", "?"), queue_path.name,
            )
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
        "Topic queue %s: every topic has been produced%s. "
        "Append new topics to keep the show running.",
        queue_path,
        f" or gate-deferred ({deferred})" if deferred else "",
    )
    return None


def pick_deep_dive_topic(
    queue_path: Path,
    today_iso: str,
    force_id: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    """Select a deep-dive topic for this run, or ``None`` for a normal
    (news) episode.

    Unlike ``pick_next_topic`` (which always returns the first unproduced
    entry), deep dives only fire when explicitly scheduled or forced, so
    a news-driven show isn't hijacked by a stale queue. Among entries that
    are not yet ``produced``:

      1. ``force_id`` given (``--deep-dive <id>``) — the matching entry,
         regardless of its schedule. Returns ``None`` if the id is unknown
         or already produced (caller decides whether to skip or fall back).
      2. an entry whose ``date`` equals *today_iso* (a scheduled deep dive).
      3. an entry flagged ``when: next`` (fires on the very next run).

    The returned dict is a shallow copy; use ``mark_topic_produced`` to
    record completion.
    """
    data = _load_queue(queue_path)
    queue = data.get("queue", [])

    def _valid_unproduced() -> list:
        out = []
        for entry in queue:
            if not isinstance(entry, dict) or entry.get("produced") is True:
                continue
            if not all(entry.get(k) for k in ("id", "title", "brief")):
                logger.error(
                    "Deep-dive queue entry missing id/title/brief — skipping: %s",
                    entry,
                )
                continue
            out.append(entry)
        return out

    candidates = _valid_unproduced()

    if force_id:
        for entry in candidates:
            if entry.get("id") == force_id:
                return dict(entry)
        logger.warning(
            "pick_deep_dive_topic: forced id %r not found among unproduced "
            "entries in %s", force_id, queue_path,
        )
        return None

    # Scheduled-for-today wins over a generic "next" flag.
    for entry in candidates:
        if str(entry.get("date", "")) == today_iso:
            return dict(entry)
    for entry in candidates:
        if str(entry.get("when", "")).lower() == "next":
            return dict(entry)
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


def record_gate_block(queue_path: Path, topic_id: str,
                      date_str: str) -> bool:
    """Record that the source-integrity gate blocked *topic_id* today.

    Increments the entry's ``gate_blocks`` counter and stamps
    ``gate_blocked_last`` — the committed state the picker's defer
    threshold reads (the skip path publishes nothing, so this annotation
    is the ONLY thing that survives to the next day's fresh checkout;
    run-show.yml commits it on gate-block skips). Idempotent per day: a
    rerun on the same date does not double-count.

    Returns True if the file changed."""
    if not queue_path.exists():
        logger.error("record_gate_block: queue file missing: %s", queue_path)
        return False
    with queue_path.open("r", encoding="utf-8") as fh:
        data = yaml.safe_load(fh) or {}
    queue = data.get("queue", [])
    blocks = 0
    updated = False
    for entry in queue:
        if isinstance(entry, dict) and entry.get("id") == topic_id:
            if str(entry.get("gate_blocked_last") or "") == date_str:
                logger.info(
                    "record_gate_block: %r already recorded for %s",
                    topic_id, date_str)
                return False
            blocks = int(entry.get("gate_blocks") or 0) + 1
            entry["gate_blocks"] = blocks
            entry["gate_blocked_last"] = date_str
            updated = True
            break
    if not updated:
        logger.warning(
            "record_gate_block: topic_id %r not found in %s",
            topic_id, queue_path)
        return False
    with queue_path.open("w", encoding="utf-8") as fh:
        yaml.safe_dump(
            data, fh,
            allow_unicode=True,
            sort_keys=False,
            default_flow_style=False,
            width=10000,
        )
    logger.warning(
        "record_gate_block: %r now at %d gate block(s) (defer threshold %d)",
        topic_id, blocks, GATE_BLOCK_DEFER_THRESHOLD,
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
    gate_deferred = sum(
        1 for e in queue
        if isinstance(e, dict) and e.get("produced") is not True
        and int(e.get("gate_blocks") or 0) >= GATE_BLOCK_DEFER_THRESHOLD
    )
    return {
        "total": total,
        "produced": produced,
        "remaining": total - produced,
        # Deferred topics still count in ``remaining`` (they are runway an
        # operator can re-clear) but are surfaced separately so a queue
        # full of gate-deferred topics doesn't read as healthy.
        "gate_deferred": gate_deferred,
    }
