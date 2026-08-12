"""Staggered Shorts publishing — spread one episode's Shorts through the day.

Operator directive (Aug 2026): when an episode publishes N Shorts, only
Short #1 should go public with the episode; the rest should land at the
channel's high-traffic hours later in the day instead of all competing
with each other (and with the long-form) in the same minute. This applies
to every channel (EN / RU / FR) and to manual runs too.

Mechanism: **YouTube's own scheduler** (``status.publishAt``). Later
Shorts are uploaded at run time exactly as before — same render, same
metadata, same thumbnail, same playlist — but with ``privacyStatus:
private`` + a ``publishAt`` timestamp, and YouTube flips them public at
the scheduled moment. No new infrastructure, nothing to babysit: a dead
runner can't strand a Short because the upload already happened.

Slot hours are per-channel (UTC), tuned to each audience's evening:

- ``en`` — US-centric: 17 UTC (~1pm ET / 10am PT lunch scroll),
  21 UTC (~5pm ET commute), 23 UTC (~7pm ET evening).
- ``ru`` — Moscow (UTC+3): 15 UTC (6pm MSK), 18 UTC (9pm MSK),
  20 UTC (11pm MSK).
- ``fr`` — Central Europe (UTC+2 summer): 17 UTC (7pm CEST),
  19 UTC (9pm CEST), 21 UTC (11pm CEST).

Override per show/network via ``youtube.shorts_stagger_slots_utc`` in the
YAML (mapping channel → list of UTC hours). These are heuristics, not
analytics-derived — the YouTube Analytics API exposes no hour-of-day
views dimension — so they encode audience-timezone priors and are cheap
to retune.

One real trade-off is handled here too: the channel funnel comment
("▶ Full episode: …") cannot be posted on a still-private video, so for
a scheduled Short the comment is QUEUED to a per-show sidecar
(``digests/<slug>/scheduled_comments.json``) and posted by
``scripts/post_scheduled_short_comments.py`` (wired into the multilingual
sweep + nightly maintenance, both of which already hold the channel
tokens) once the publish time has passed. Losing those comments silently
would degrade the network's strongest Shorts→long funnel placement — the
July 2026 RU pilot exists because of exactly that class of silent gap.

Everything in this module is best-effort by contract: any failure must
leave the caller publishing all Shorts immediately (the legacy behavior),
never block an upload.
"""

from __future__ import annotations

import datetime as _dt
import json
import logging
from pathlib import Path
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

# Per-channel preferred publish hours, UTC. See module docstring for the
# audience-timezone rationale. Operator-tunable via
# ``youtube.shorts_stagger_slots_utc`` without touching code.
DEFAULT_SLOT_HOURS_UTC: Dict[str, List[int]] = {
    "en": [17, 21, 23],
    "ru": [15, 18, 20],
    "fr": [17, 19, 21],
}

# A scheduled time closer than this to "now" is pointless (the Short would
# publish before the first one has had any run at the feed) and risks
# YouTube rejecting a past timestamp after a slow upload.
MIN_LEAD_MINUTES = 90

# When the slot list can't supply enough future times (e.g. a run at
# 23:30 UTC), fall back to fixed offsets so the Shorts still spread out.
FALLBACK_GAP_HOURS = 3

# A queued comment older than this is dropped (loudly) instead of posted
# onto a week-old Short nobody will scroll past again.
COMMENT_MAX_AGE_DAYS = 7
# A permanently-failing comment (403 comments-disabled) is dropped after
# this many attempts instead of re-charging quota every sweep for 7 days.
COMMENT_MAX_ATTEMPTS = 3

_SIDECAR_NAME = "scheduled_comments.json"


def resolve_slot_hours(youtube_config, channel: str) -> List[int]:
    """Slot hours for *channel*, from YAML override or the defaults.

    Invalid entries (non-int, out of 0-23) are dropped; an empty result
    falls back to the ``en`` defaults so the caller always gets a usable
    list.
    """
    raw = getattr(youtube_config, "shorts_stagger_slots_utc", None) or {}
    hours = raw.get(channel) if isinstance(raw, dict) else None
    if not hours:
        hours = DEFAULT_SLOT_HOURS_UTC.get(channel)
    if not hours:
        hours = DEFAULT_SLOT_HOURS_UTC["en"]
    out = []
    for h in hours:
        try:
            h = int(h)
        except (TypeError, ValueError):
            continue
        if 0 <= h <= 23:
            out.append(h)
    return sorted(set(out)) or list(DEFAULT_SLOT_HOURS_UTC["en"])


def stagger_publish_times(
    now: _dt.datetime,
    count: int,
    *,
    slot_hours: List[int],
    min_lead_minutes: int = MIN_LEAD_MINUTES,
    fallback_gap_hours: int = FALLBACK_GAP_HOURS,
) -> List[_dt.datetime]:
    """Return *count* future UTC publish times for the 2nd..Nth Shorts.

    Takes the next unelapsed slot hours (today's remaining, then
    tomorrow's) that are at least *min_lead_minutes* away; when the slot
    list runs dry inside that window, fills with ``now + k*gap`` so the
    Shorts always spread even on a late-night run. Result is sorted and
    strictly increasing.
    """
    if count <= 0:
        return []
    if now.tzinfo is None:
        now = now.replace(tzinfo=_dt.timezone.utc)
    lead = _dt.timedelta(minutes=min_lead_minutes)

    candidates: List[_dt.datetime] = []
    for day_offset in (0, 1):
        day = (now + _dt.timedelta(days=day_offset)).date()
        for h in sorted(slot_hours):
            t = _dt.datetime(day.year, day.month, day.day, h,
                             tzinfo=_dt.timezone.utc)
            if t >= now + lead:
                candidates.append(t)
    times = sorted(candidates)[:count]

    # Fallback fills EXTEND THE TAIL by a fixed gap. The old loop only
    # appended ``now + k*gap`` when it beat the last slot candidate — so
    # with one late-evening slot left, k had to climb past tomorrow's
    # slot before anything was appended and the "3 hours from now" fill
    # landed ~18 h out. A 0/negative gap (reachable kwarg) also made the
    # loop spin forever.
    gap = max(1, int(fallback_gap_hours or 0))
    while len(times) < count:
        tail = times[-1] if times else (now + lead)
        times.append(max(tail, now + lead) + _dt.timedelta(hours=gap))
    return times[:count]


def format_publish_at(t: _dt.datetime) -> str:
    """RFC3339 UTC string for ``status.publishAt``."""
    if t.tzinfo is not None:
        t = t.astimezone(_dt.timezone.utc).replace(tzinfo=None)
    return t.strftime("%Y-%m-%dT%H:%M:%SZ")


# ---------------------------------------------------------------------------
# Deferred funnel comments (a comment can't be posted on a private video)
# ---------------------------------------------------------------------------

def queue_comment(
    digests_dir: Path,
    *,
    video_id: str,
    channel: str,
    text: str,
    publish_at: _dt.datetime,
) -> bool:
    """Queue a funnel comment for a scheduled Short. Best-effort."""
    if not (video_id and text):
        return False
    try:
        path = Path(digests_dir) / _SIDECAR_NAME
        data = {"schema_version": 1, "pending": []}
        if path.exists():
            data = json.loads(path.read_text(encoding="utf-8"))
            data.setdefault("pending", [])
        # Idempotent per video — a rerun must not double-queue.
        data["pending"] = [
            e for e in data["pending"] if e.get("video_id") != video_id
        ]
        data["pending"].append({
            "video_id": video_id,
            "channel": channel or "en",
            "text": text,
            "publish_at": format_publish_at(publish_at),
        })
        path.write_text(
            json.dumps(data, ensure_ascii=False, indent=1) + "\n",
            encoding="utf-8",
        )
        return True
    except Exception as exc:  # noqa: BLE001 — never block a publish
        logger.warning("scheduled-comment queue failed for %s: %s",
                       video_id, exc)
        return False


def post_due_comments(
    project_root: Path,
    now: Optional[_dt.datetime] = None,
    *,
    show_dir: Optional[str] = None,
) -> Dict[str, int]:
    """Post every queued comment whose Short has gone public. Sweep entry
    point for ``scripts/post_scheduled_short_comments.py``.

    *show_dir* narrows the sweep to one ``digests/<dir>`` sidecar. The
    multilingual workflow runs this INSIDE its per-show matrix with
    max-parallel 3 — three concurrent jobs globbing every sidecar each
    saw the same pending entries and each posted them, so the network's
    strongest Shorts→long placement shipped as 2-3 identical bot
    comments on the same Short. Matrix jobs pass their own show; only
    single-job sweeps (nightly) run the full glob.

    Returns counters: posted / kept (not yet due) / dropped (too old or
    repeatedly failing). Missing credentials for a channel keep its
    entries queued for the next sweep; an entry that fails 3 attempts is
    dropped early (a 403 comments-disabled channel used to be retried
    every sweep for 7 days at real quota cost).
    """
    from engine.youtube import (
        get_channel_credentials_from_env,
        post_video_comment,
    )

    now = now or _dt.datetime.now(_dt.timezone.utc)
    if now.tzinfo is None:
        now = now.replace(tzinfo=_dt.timezone.utc)
    stats = {"posted": 0, "kept": 0, "dropped": 0}
    creds_cache: Dict[str, object] = {}

    pattern = (f"digests/{show_dir}/{_SIDECAR_NAME}"
               if show_dir else f"digests/*/{_SIDECAR_NAME}")
    for path in sorted(Path(project_root).glob(pattern)):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception as exc:  # noqa: BLE001
            logger.warning("scheduled-comments sidecar unreadable %s: %s",
                           path, exc)
            continue
        keep = []
        changed = False
        posted_here = 0
        for entry in data.get("pending", []):
            try:
                due = _dt.datetime.strptime(
                    entry.get("publish_at", ""), "%Y-%m-%dT%H:%M:%SZ"
                ).replace(tzinfo=_dt.timezone.utc)
            except ValueError:
                logger.warning("dropping malformed scheduled-comment entry "
                               "in %s: %r", path, entry)
                stats["dropped"] += 1
                changed = True
                continue
            if due > now:
                keep.append(entry)
                stats["kept"] += 1
                continue
            if now - due > _dt.timedelta(days=COMMENT_MAX_AGE_DAYS):
                logger.warning(
                    "::warning::scheduled comment for %s is > %dd overdue — "
                    "dropping (video %s)", path.parent.name,
                    COMMENT_MAX_AGE_DAYS, entry.get("video_id"))
                stats["dropped"] += 1
                changed = True
                continue
            ch = entry.get("channel", "en")
            if ch not in creds_cache:
                creds_cache[ch] = get_channel_credentials_from_env(ch)
            creds = creds_cache[ch]
            if creds is None:
                keep.append(entry)  # no token in this environment — retry later
                stats["kept"] += 1
                continue
            try:
                cid = post_video_comment(
                    credentials=creds,
                    video_id=entry["video_id"],
                    text=entry["text"],
                )
            except Exception as exc:  # noqa: BLE001
                logger.warning("deferred comment failed for %s: %s — "
                               "keeping for next sweep",
                               entry.get("video_id"), exc)
                cid = None
            if cid:
                stats["posted"] += 1
                posted_here += 1
                changed = True
            else:
                entry["attempts"] = int(entry.get("attempts", 0) or 0) + 1
                if entry["attempts"] >= COMMENT_MAX_ATTEMPTS:
                    logger.warning(
                        "scheduled comment for %s dropped after %d failed "
                        "attempts (video %s) — likely comments disabled "
                        "on the channel/video", path.parent.name,
                        entry["attempts"], entry.get("video_id"))
                    stats["dropped"] += 1
                    changed = True
                else:
                    keep.append(entry)
                    stats["kept"] += 1
                    changed = True  # persist the attempt count
        if changed or len(keep) != len(data.get("pending", [])):
            try:
                # Rolling per-show counter for the dashboard's stagger-
                # health card — pending entries vanish once posted, so
                # without this the sidecar carries no evidence the sweep
                # ever worked.
                data["posted_total"] = (
                    int(data.get("posted_total", 0) or 0) + posted_here)
                data["pending"] = keep
                path.write_text(
                    json.dumps(data, ensure_ascii=False, indent=1) + "\n",
                    encoding="utf-8",
                )
            except Exception as exc:  # noqa: BLE001
                logger.warning("scheduled-comments sidecar write failed "
                               "%s: %s", path, exc)
    return stats
