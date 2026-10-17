"""Daytime posting for @nerranetwork (Oct 11 2026; ET grid Oct 17 2026).

The shows publish in the early morning, and on the first night their X
posts went out then too, to an audience that was asleep. A show's post now
waits in a queue (Supabase ``x_post_queue``) for a slot on a half-hour grid
between 7:00 AM and 10:00 PM New York time, one post per slot, and
``scripts/post_x_queue.py`` posts what is due. Oct 17 2026: the network is
timed to an East-coast morning (engine/release_schedule.py) — Nerra Daily
holds 7:00 ET (no show is queued into it; the edition builder queues itself
there with ``enqueue(slot=...)``) and each show takes its own preferred slot
from 7:30 ET in release order when that slot is free and not past, else the
next free slot. The scheduler Worker
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

EASTERN = ZoneInfo("America/New_York")
UTC = dt.timezone.utc
FIRST_SLOT = dt.time(7, 0)
LAST_SLOT = dt.time(22, 0)
SPACING = dt.timedelta(minutes=30)
LEAD = dt.timedelta(minutes=5)
TABLE = "x_post_queue"
REPLY_TABLE = "x_post_replies"
R2_PREFIX = "x_queue"
# The audio bucket and its public domain (shows/_defaults.yaml storage:),
# the one R2 host the network already serves media from.
R2_BUCKET = os.getenv("X_QUEUE_R2_BUCKET", "podcast-audio")
R2_PUBLIC_BASE = os.getenv("X_QUEUE_R2_PUBLIC_BASE", "https://audio.nerranetwork.com").rstrip("/")
MAX_ATTEMPTS = 3
# X's limit for a video on a post from a default (non-Premium) account
# (docs.x.com media best practices, Oct 2026): 20 minutes, 8 GB.
LONG_FORM_MAX_SECONDS = 20 * 60


# ------------------------------------------------------------------ slots --
def next_slot(taken: Iterable[dt.datetime], now: dt.datetime, *,
              reserve_edition: bool = True) -> dt.datetime:
    """The earliest free half-hour slot, 7:00 AM to 10:00 PM ET, at least
    five minutes from *now*. Returned in UTC. Nerra Daily's 7:00 ET slot is
    never handed to a show (*reserve_edition*)."""
    from engine.release_schedule import x_reserved_slots
    busy = {t.astimezone(UTC).replace(second=0, microsecond=0) for t in taken}
    earliest = now.astimezone(EASTERN) + LEAD
    day = earliest.date()
    for _ in range(30):
        reserved = set(x_reserved_slots(day)) if reserve_edition else set()
        slot = dt.datetime.combine(day, FIRST_SLOT, EASTERN)
        last = dt.datetime.combine(day, LAST_SLOT, EASTERN)
        while slot <= last:
            utc = slot.astimezone(UTC)
            if slot >= earliest and utc not in busy and utc not in reserved:
                return utc
            slot = (slot.replace(tzinfo=None) + SPACING).replace(tzinfo=EASTERN)
        day += dt.timedelta(days=1)
    return earliest.astimezone(UTC)  # a month of full slots: post now


def choose_slot(show_slug: str, taken: Iterable[dt.datetime], now: dt.datetime) -> dt.datetime:
    """The show's preferred release slot when it is free and not past
    (engine/release_schedule.py), else :func:`next_slot`. UTC."""
    taken = list(taken)
    try:
        from engine.release_schedule import x_slot
        preferred = x_slot(show_slug, now)
    except Exception as exc:  # noqa: BLE001 — the grid still works
        logger.info("X release slot unavailable for %s: %s", show_slug, exc)
        preferred = None
    if preferred is not None:
        busy = {t.astimezone(UTC).replace(second=0, microsecond=0) for t in taken}
        if preferred.astimezone(UTC) not in busy:
            return preferred.astimezone(UTC)
    return next_slot(taken, now)


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


def host_file(path, show_slug: str) -> str:
    """Put *path* on the audio bucket under ``x_queue/`` and return its
    public URL, or ``""`` when the queue is not configured or the upload
    fails. The copy is deleted once the post that carries it is up."""
    try:
        if not configured() or not Path(path).is_file():
            return ""
        return _host(Path(path), show_slug)
    except Exception as exc:  # noqa: BLE001 — a reply is a bonus
        logger.warning("Could not host %s for X: %s", Path(path).name, exc)
        return ""


# ---------------------------------------------------------------- enqueue --
def slot_for(show_slug: str, taken: Iterable[dt.datetime], now: dt.datetime,
             slot: Optional[dt.datetime] = None) -> dt.datetime:
    """*slot* when one is given, free and at least five minutes out, else
    :func:`choose_slot`. UTC.

    The explicit slot is how a caller takes a RESERVED slot the grid never
    hands out — Nerra Daily's 7:00 ET (Oct 17 2026). It is still one post
    per slot: a taken or passed slot falls back to the grid.
    """
    taken = list(taken)
    if slot is not None:
        want = slot.astimezone(UTC).replace(second=0, microsecond=0)
        busy = {t.astimezone(UTC).replace(second=0, microsecond=0) for t in taken}
        if want >= now.astimezone(UTC) + LEAD and want not in busy:
            return want
    return choose_slot(show_slug, taken, now)


def enqueue(*, show_slug: str, episode_num: int, env_prefix: str, text: str,
            media_path: str = "", media_kind: str = "", media_url: str = "",
            slot: Optional[dt.datetime] = None,
            now: Optional[dt.datetime] = None) -> Tuple[bool, str]:
    """Queue one post. ``(True, due_at_iso)`` when queued or already queued,
    ``(False, reason)`` when the caller should post now instead.

    *media_url* is a copy already hosted with :func:`host_file` (it wins over
    *media_path*); *slot* asks for a specific due time (:func:`slot_for`).
    """
    if not configured():
        return False, "queue_not_configured"
    now = now or dt.datetime.now(UTC)
    try:
        if not media_url and media_path and Path(media_path).is_file():
            media_url = _host(Path(media_path), show_slug)
        due = slot_for(show_slug, _taken(now), now, slot)
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
        local = due.astimezone(EASTERN)
        logger.info("X post for %s ep%s queued for %s ET", show_slug, episode_num,
                    local.strftime("%a %-I:%M %p"))
        return True, _iso(due)
    except Exception as exc:  # noqa: BLE001 — post now rather than lose it
        logger.warning("X queue unavailable (%s); posting now", exc)
        return False, "queue_error"


def enqueue_reply(*, show_slug: str, episode_num: int, env_prefix: str, text: str,
                  media_url: str, subtitles_url: str = "", kind: str = "long") -> Tuple[bool, str]:
    """Queue the full episode as a reply under the show's queued post.

    Never posts on its own: a reply needs its parent post, so with no queue
    (or no ``x_post_replies`` table yet) the reply is simply not made and the
    hosted copy is deleted. ``(True, "queued")`` or ``(False, reason)``.
    """
    if not media_url:
        return False, "no_media"
    if not configured():
        return False, "queue_not_configured"
    try:
        _rest("POST", REPLY_TABLE, params={"on_conflict": "show_slug,episode_num,kind"},
              prefer="return=representation,resolution=ignore-duplicates",
              json={"show_slug": show_slug, "episode_num": int(episode_num), "kind": kind,
                    "env_prefix": env_prefix, "text": text, "media_url": media_url,
                    "subtitles_url": subtitles_url or None, "status": "queued"})
        logger.info("X %s reply for %s ep%s queued under its post", kind, show_slug, episode_num)
        return True, "queued"
    except Exception as exc:  # noqa: BLE001 — the parent post is unaffected
        logger.warning("X reply queue unavailable (%s); no %s reply for %s ep%s",
                       exc, kind, show_slug, episode_num)
        for url in (media_url, subtitles_url):
            if url:
                _forget_media(url)
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


def forget_media(url: str) -> None:
    """Delete a copy :func:`host_file` put on the bucket (best-effort)."""
    _forget_media(url)


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


def _status_id(url: str) -> str:
    tail = (url or "").rstrip("/").rsplit("/", 1)[-1]
    return tail if tail.isdigit() else ""


def post_due_replies(*, limit: int = 1, now: Optional[dt.datetime] = None) -> List[dict]:
    """Post queued replies whose parent post is up, oldest first.

    A reply waits while its parent is queued or posting, is cancelled when
    the parent failed or was cancelled, and posts as a reply to the parent's
    status once it is up. One per run by default: a full episode is a large
    upload, and the queue workflow runs every half hour.
    """
    from engine.x_post import post_video_reply
    now = now or dt.datetime.now(UTC)
    _rest("PATCH", REPLY_TABLE, params={"status": "eq.posting",
                                        "updated_at": f"lt.{_iso(now - dt.timedelta(minutes=60))}"},
          json={"status": "queued"}, prefer="return=minimal")
    queued = _rest("GET", REPLY_TABLE, params={
        "select": "*", "status": "eq.queued", "order": "created_at.asc", "limit": "20"})
    results: List[dict] = []
    for row in queued:
        if len(results) >= limit:
            break
        label = f"{row['show_slug']} ep{row['episode_num']} ({row.get('kind') or 'long'})"
        parents = _rest("GET", TABLE, params={
            "select": "status,tweet_url", "show_slug": f"eq.{row['show_slug']}",
            "episode_num": f"eq.{row['episode_num']}", "limit": "1"})
        parent = parents[0] if parents else {}
        pstatus = parent.get("status")
        if pstatus in ("failed", "cancelled") or (not parents and row.get("created_at")
                                                   and _age_hours(row["created_at"], now) > 48):
            _rest("PATCH", REPLY_TABLE, params={"id": f"eq.{row['id']}"}, prefer="return=minimal",
                  json={"status": "cancelled", "error": f"parent {pstatus or 'missing'}",
                        "updated_at": _iso(now)})
            for url in (row.get("media_url"), row.get("subtitles_url")):
                if url:
                    _forget_media(url)
            results.append({"id": row["id"], "show": label, "status": "cancelled",
                            "error": f"parent {pstatus or 'missing'}"})
            continue
        parent_id = _status_id(parent.get("tweet_url") or "")
        if pstatus != "posted" or not parent_id:
            continue  # the parent is still waiting for its slot
        claimed = _rest("PATCH", REPLY_TABLE, params={"id": f"eq.{row['id']}", "status": "eq.queued"},
                        json={"status": "posting", "attempts": int(row.get("attempts") or 0) + 1,
                              "updated_at": _iso(now)})
        if not claimed:
            continue
        with tempfile.TemporaryDirectory() as tmp:
            try:
                video = _download(row["media_url"], Path(tmp))
                subs = _download(row["subtitles_url"], Path(tmp)) if row.get("subtitles_url") else ""
            except Exception as exc:  # noqa: BLE001
                video, subs = "", ""
                logger.warning("Could not fetch the %s video: %s", label, exc)
            posted, reason, url = (False, "no_media", "") if not video else post_video_reply(
                env_prefix=row.get("env_prefix") or "NERRANETWORK_X_", text=row["text"],
                video_path=video, subtitles_path=subs, in_reply_to=parent_id, label=label)
        if posted:
            _rest("PATCH", REPLY_TABLE, params={"id": f"eq.{row['id']}"}, prefer="return=minimal",
                  json={"status": "posted", "tweet_url": url, "posted_at": _iso(now),
                        "updated_at": _iso(now), "error": reason or None})
            for media in (row.get("media_url"), row.get("subtitles_url")):
                if media:
                    _forget_media(media)
            results.append({"id": row["id"], "show": label, "status": "posted", "url": url})
            continue
        attempts = int(row.get("attempts") or 0) + 1
        final = attempts >= MAX_ATTEMPTS or reason in ("no_credentials", "too_long")
        _rest("PATCH", REPLY_TABLE, params={"id": f"eq.{row['id']}"}, prefer="return=minimal",
              json={"status": "failed" if final else "queued", "error": reason,
                    "updated_at": _iso(now)})
        if final:
            for media in (row.get("media_url"), row.get("subtitles_url")):
                if media:
                    _forget_media(media)
        results.append({"id": row["id"], "show": label,
                        "status": "failed" if final else "retry", "error": reason})
    return results


def _age_hours(stamp: str, now: dt.datetime) -> float:
    try:
        t = dt.datetime.fromisoformat(str(stamp).replace("Z", "+00:00"))
    except ValueError:
        return 0.0
    return (now - t).total_seconds() / 3600.0
