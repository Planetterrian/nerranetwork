"""Daytime posting for @nerranetwork (Oct 11 2026).

The shows publish between about 11 PM and 5 AM Pacific, and on the first
night their X posts went out then too, to an audience that was asleep. A
show's post now waits in a queue (Supabase ``x_post_queue``) for a slot on a
half-hour grid between 6:30 AM and 7:00 PM Pacific, one post per slot, and
``scripts/post_x_queue.py`` posts what is due. The scheduler Worker
dispatches that script every half hour; the workflow keeps a slower GitHub
cron as a fallback. The clip or image waits on the audio R2 bucket (served
at audio.nerranetwork.com) under ``x_queue/`` and is deleted once posted.

A queue that is not configured (no ``X_QUEUE_SUPABASE_*`` or no R2 keys)
returns ``(False, reason)`` from :func:`enqueue`, and the caller posts at
once, exactly as before.
"""
from __future__ import annotations

import datetime as dt
import logging
import mimetypes
import os
import tempfile
from pathlib import Path
from typing import Iterable, List, Optional, Tuple
from zoneinfo import ZoneInfo

logger = logging.getLogger(__name__)

PACIFIC = ZoneInfo("America/Los_Angeles")
UTC = dt.timezone.utc
FIRST_SLOT = dt.time(6, 30)
LAST_SLOT = dt.time(19, 0)
SPACING = dt.timedelta(minutes=30)
LEAD = dt.timedelta(minutes=5)
TABLE = "x_post_queue"
R2_PREFIX = "x_queue"
# The audio bucket and its public domain (shows/_defaults.yaml storage:),
# the one R2 host the network already serves media from.
R2_BUCKET = os.getenv("X_QUEUE_R2_BUCKET", "podcast-audio")
R2_PUBLIC_BASE = os.getenv("X_QUEUE_R2_PUBLIC_BASE", "https://audio.nerranetwork.com").rstrip("/")
MAX_ATTEMPTS = 3


# ------------------------------------------------------------------ slots --
def next_slot(taken: Iterable[dt.datetime], now: dt.datetime) -> dt.datetime:
    """The earliest free half-hour slot, 6:30 AM to 7:00 PM Pacific, at
    least five minutes from *now*. Returned in UTC."""
    busy = {t.astimezone(UTC).replace(second=0, microsecond=0) for t in taken}
    earliest = now.astimezone(PACIFIC) + LEAD
    day = earliest.date()
    for _ in range(30):
        slot = dt.datetime.combine(day, FIRST_SLOT, PACIFIC)
        last = dt.datetime.combine(day, LAST_SLOT, PACIFIC)
        while slot <= last:
            if slot >= earliest and slot.astimezone(UTC) not in busy:
                return slot.astimezone(UTC)
            slot = (slot.replace(tzinfo=None) + SPACING).replace(tzinfo=PACIFIC)
        day += dt.timedelta(days=1)
    return earliest.astimezone(UTC)  # a month of full slots: post now


# --------------------------------------------------------------- plumbing --
def _db() -> Tuple[str, str]:
    return (os.getenv("X_QUEUE_SUPABASE_URL", "").strip().rstrip("/"),
            os.getenv("X_QUEUE_SUPABASE_KEY", "").strip())


def _r2() -> Tuple[str, str, str]:
    return (os.getenv("R2_ENDPOINT_URL", "").strip(),
            os.getenv("R2_ACCESS_KEY_ID", "").strip(),
            os.getenv("R2_SECRET_ACCESS_KEY", "").strip())


def configured() -> bool:
    url, key = _db()
    return bool(url and key and all(_r2()))


def _rest(method: str, path: str, *, params=None, json=None, prefer: str = "return=representation"):
    import requests
    url, key = _db()
    r = requests.request(method, f"{url}/rest/v1/{path}", params=params, json=json, timeout=30,
                         headers={"apikey": key, "Authorization": f"Bearer {key}",
                                  "Content-Type": "application/json", "Prefer": prefer})
    r.raise_for_status()
    return r.json() if r.text.strip() else []


def _iso(t: dt.datetime) -> str:
    return t.astimezone(UTC).isoformat().replace("+00:00", "Z")


def _taken(now: dt.datetime) -> List[dt.datetime]:
    rows = _rest("GET", TABLE, params={
        "select": "due_at", "status": "in.(queued,posting,posted)",
        "due_at": f"gte.{_iso(now - dt.timedelta(hours=1))}"})
    out = []
    for row in rows:
        try:
            out.append(dt.datetime.fromisoformat(str(row["due_at"]).replace("Z", "+00:00")))
        except (KeyError, ValueError):
            pass
    return out


def _host(path: Path, show_slug: str) -> str:
    from engine.storage import upload_to_r2
    endpoint, access, secret = _r2()
    return upload_to_r2(
        path, f"{R2_PREFIX}/{show_slug}/{path.name}", bucket=R2_BUCKET,
        endpoint_url=endpoint, access_key=access, secret_key=secret,
        public_base_url=R2_PUBLIC_BASE,
        content_type=mimetypes.guess_type(path.name)[0] or "application/octet-stream")


# ---------------------------------------------------------------- enqueue --
def enqueue(*, show_slug: str, episode_num: int, env_prefix: str, text: str,
            media_path: str = "", media_kind: str = "",
            now: Optional[dt.datetime] = None) -> Tuple[bool, str]:
    """Queue one post. ``(True, due_at_iso)`` when queued or already queued,
    ``(False, reason)`` when the caller should post now instead."""
    if not configured():
        return False, "queue_not_configured"
    now = now or dt.datetime.now(UTC)
    try:
        media_url = ""
        if media_path and Path(media_path).is_file():
            media_url = _host(Path(media_path), show_slug)
        due = next_slot(_taken(now), now)
        rows = _rest("POST", TABLE, params={"on_conflict": "show_slug,episode_num"},
                     prefer="return=representation,resolution=ignore-duplicates",
                     json={"show_slug": show_slug, "episode_num": int(episode_num),
                           "env_prefix": env_prefix, "text": text,
                           "media_url": media_url or None,
                           "media_kind": media_kind or ("" if not media_url else "media"),
                           "due_at": _iso(due), "status": "queued"})
        if not rows:
            logger.info("X post for %s ep%s was already queued", show_slug, episode_num)
            return True, "already_queued"
        local = due.astimezone(PACIFIC)
        logger.info("X post for %s ep%s queued for %s Pacific", show_slug, episode_num,
                    local.strftime("%a %-I:%M %p"))
        return True, _iso(due)
    except Exception as exc:  # noqa: BLE001 — post now rather than lose it
        logger.warning("X queue unavailable (%s); posting now", exc)
        return False, "queue_error"


# --------------------------------------------------------------- post due --
def _download(url: str, folder: Path) -> str:
    import requests
    name = url.rsplit("/", 1)[-1].split("?", 1)[0] or "media"
    dest = folder / name
    # Cloudflare in front of audio.nerranetwork.com turns away the default
    # Python user agents (Sep 2026), so name ourselves like a browser would.
    with requests.get(url, stream=True, timeout=120,
                      headers={"User-Agent": "Mozilla/5.0 (compatible; nerra-x-queue/1.0)"}) as r:
        r.raise_for_status()
        with dest.open("wb") as fh:
            for chunk in r.iter_content(1 << 20):
                fh.write(chunk)
    return str(dest)


def _forget_media(url: str) -> None:
    """Delete the hosted copy once X has it (best-effort)."""
    try:
        if not url.startswith(R2_PUBLIC_BASE + "/"):
            return
        key = url[len(R2_PUBLIC_BASE) + 1:]
        if not key.startswith(R2_PREFIX + "/"):
            return
        endpoint, access, secret = _r2()
        if not all((endpoint, access, secret)):
            return
        import boto3
        boto3.client("s3", endpoint_url=endpoint, aws_access_key_id=access,
                     aws_secret_access_key=secret).delete_object(Bucket=R2_BUCKET, Key=key)
    except Exception as exc:  # noqa: BLE001
        logger.info("Could not delete hosted X media %s: %s", url, exc)


def post_due(*, limit: int = 2, now: Optional[dt.datetime] = None) -> List[dict]:
    """Post up to *limit* due posts, oldest first. One row per result:
    ``{"id", "show", "status", "url" | "error"}``."""
    from engine.x_post import post_media
    now = now or dt.datetime.now(UTC)
    # A run that died mid-post leaves "posting"; give it back after 30 min.
    _rest("PATCH", TABLE, params={"status": "eq.posting",
                                  "updated_at": f"lt.{_iso(now - dt.timedelta(minutes=30))}"},
          json={"status": "queued"}, prefer="return=minimal")
    due = _rest("GET", TABLE, params={
        "select": "*", "status": "eq.queued", "due_at": f"lte.{_iso(now)}",
        "order": "due_at.asc", "limit": str(limit)})
    results = []
    for row in due:
        claimed = _rest("PATCH", TABLE, params={"id": f"eq.{row['id']}", "status": "eq.queued"},
                        json={"status": "posting", "attempts": int(row.get("attempts") or 0) + 1,
                              "updated_at": _iso(now)})
        if not claimed:
            continue
        label = f"{row['show_slug']} ep{row['episode_num']}"
        with tempfile.TemporaryDirectory() as tmp:
            media = []
            if row.get("media_url"):
                try:
                    media = [_download(row["media_url"], Path(tmp))]
                except Exception as exc:  # noqa: BLE001 — text alone beats nothing
                    logger.warning("Could not fetch media for %s: %s", label, exc)
            posted, reason, url, used = post_media(
                env_prefix=row.get("env_prefix") or "NERRANETWORK_X_",
                text=row["text"], media_paths=media, label=label)
        if posted:
            _rest("PATCH", TABLE, params={"id": f"eq.{row['id']}"}, prefer="return=minimal",
                  json={"status": "posted", "tweet_url": url, "posted_at": _iso(now),
                        "updated_at": _iso(now), "error": None if used or not media else "posted without media"})
            if row.get("media_url"):
                _forget_media(row["media_url"])
            results.append({"id": row["id"], "show": label, "status": "posted", "url": url})
        else:
            attempts = int(row.get("attempts") or 0) + 1
            final = attempts >= MAX_ATTEMPTS or reason == "no_credentials"
            _rest("PATCH", TABLE, params={"id": f"eq.{row['id']}"}, prefer="return=minimal",
                  json={"status": "failed" if final else "queued", "error": reason,
                        "updated_at": _iso(now),
                        "due_at": _iso(now + SPACING) if not final else row["due_at"]})
            results.append({"id": row["id"], "show": label,
                            "status": "failed" if final else "retry", "error": reason})
    return results
