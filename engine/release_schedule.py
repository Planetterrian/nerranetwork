"""Release timing for an East-coast morning (Oct 17 2026, operator-directed).

The shows now finish between about 4:00 and 6:10 AM New York time (Vancouver
at 8:15 ET, 5:15 Pacific), and Nerra Daily goes out at 7:00 AM ET. What a
show RELEASES after its audio — the YouTube hook Short, the long-form, the X
post and the newsletter — is timed here, in one place, so the network's day
reads as a schedule instead of a burst at 5 AM:

- **YouTube hook Short** at 7:00 ET + 15 min x the show's rank among the
  YouTube-enabled shows on its channel (7:00, 7:15, 7:30 ...). Vancouver is a
  local show and gets its own local morning instead: 7:00 Pacific.
- **YouTube long-form** in two waves: the first half of the ranked shows at
  12:00, 12:30 ... ET, the second half at 18:00, 18:30 ... ET.
- **X**: Nerra Daily holds 7:00 ET; the shows prefer 7:30 ET onward, every
  30 min in rank order, inside the 7:00 AM - 10:00 PM ET posting window
  (engine/x_queue.py owns the grid and the "slot taken" fallback).
- **Newsletter**: a show's episode newsletter is scheduled for 7:00 ET when
  the run finishes before then on the same ET date; Vancouver's for 6:00
  Pacific. Otherwise it sends now. Weekly newsletters are not timed here.

Contract: every function is pure (no I/O, no clock — the caller passes
*now*), works in the ET (or Pacific) WALL CLOCK through ``zoneinfo`` so the
times hold across a daylight-saving change, and returns an aware UTC
datetime, or ``None`` when the slot has already passed for that day (or is
closer than the surface's minimum lead). ``None`` means "publish now" —
every caller treats any failure the same way, so a scheduling problem can
never cost an upload or a send.
"""
from __future__ import annotations

import datetime as dt
from typing import Iterable, List, Optional
from zoneinfo import ZoneInfo

EASTERN = ZoneInfo("America/New_York")
PACIFIC = ZoneInfo("America/Los_Angeles")
UTC = dt.timezone.utc

# News and markets first: the listener deciding what to hear at 7 AM wants
# the day's world picture and the market-moving shows before the evergreen
# ones. The weeklies follow the dailies (they run one weekday each, so their
# slots are usually empty), Привет, Русский! is a lesson show, and Vancouver
# is last because it runs last (8:15 ET) and is timed to its own local
# morning anyway. A show missing from the tuple goes last.
RELEASE_ORDER = (
    "omni_view_world", "spacex", "tesla", "mag7", "modern_investing",
    "omni_view", "prediction_markets", "models_agents", "ai_chips",
    "fascinating_frontiers", "planetterrian", "models_agents_beginners",
    "unintended_consequences", "first_principles",
    "env_intel", "finansy_prosto", "dp_pod", "offshore_north", "longevity",
    "peptides", "collingwood",
    "privet_russian", "vancouver",
)

NERRA_DAILY_SLUG = "nerra_daily"

# Local shows released on their own city's morning, not New York's.
LOCAL_SHORT_SLOTS = {"vancouver": (PACIFIC, dt.time(7, 0))}
LOCAL_NEWSLETTER_SLOTS = {"vancouver": (PACIFIC, dt.time(6, 0))}

SHORT_FIRST = dt.time(7, 0)
SHORT_SPACING = dt.timedelta(minutes=15)
LONG_FIRST_WAVE = dt.time(12, 0)
LONG_SECOND_WAVE = dt.time(18, 0)
LONG_SPACING = dt.timedelta(minutes=30)
X_EDITION_SLOT = dt.time(7, 0)
X_FIRST_SHOW = dt.time(7, 30)
X_SPACING = dt.timedelta(minutes=30)
X_WINDOW_START = dt.time(7, 0)
X_WINDOW_END = dt.time(22, 0)
NEWSLETTER_SLOT = dt.time(7, 0)

# A slot closer than this is treated as passed. YouTube validates
# ``publishAt`` when the insert starts and a long-form upload takes
# minutes, so a slot two minutes out would be in the past by the time the
# video exists; Buttondown only needs a future ``publish_date``.
YOUTUBE_MIN_LEAD = dt.timedelta(minutes=15)
X_MIN_LEAD = dt.timedelta(minutes=5)
NEWSLETTER_MIN_LEAD = dt.timedelta(minutes=2)


# ------------------------------------------------------------------ helpers --
def _aware(now: dt.datetime) -> dt.datetime:
    return now if now.tzinfo is not None else now.replace(tzinfo=UTC)


def _at(day: dt.date, wall: dt.time, tz: ZoneInfo, plus: dt.timedelta = dt.timedelta()) -> dt.datetime:
    """*wall* on *day* in *tz*, plus an offset counted on the wall clock."""
    naive = dt.datetime.combine(day, wall) + plus
    return naive.replace(tzinfo=tz)


def _future(slot: dt.datetime, now: dt.datetime, lead: dt.timedelta) -> Optional[dt.datetime]:
    return slot.astimezone(UTC) if slot >= _aware(now) + lead else None


def ranked(peers: Optional[Iterable[str]] = None, *, include: str = "") -> List[str]:
    """The release order restricted to *peers* (plus *include*).

    ``None`` ranks against the whole :data:`RELEASE_ORDER`. Shows missing from
    the tuple follow it, alphabetically, so two of them never share a rank.
    """
    pool = set(RELEASE_ORDER if peers is None else peers)
    if include:
        pool.add(include)
    known = [s for s in RELEASE_ORDER if s in pool]
    return known + sorted(pool - set(RELEASE_ORDER))


def release_rank(slug: str, peers: Optional[Iterable[str]] = None) -> int:
    """0-based place of *slug* in the release order among *peers*."""
    return ranked(peers, include=slug).index(slug)


# ------------------------------------------------------------------ YouTube --
def youtube_short_time(slug: str, now: dt.datetime, *,
                       peers: Optional[Iterable[str]] = None) -> Optional[dt.datetime]:
    """When the hook Short (Short #1) goes public, or ``None`` = now.

    *peers* are the YouTube-enabled shows on the same channel; the slot is
    7:00 ET + 15 min x rank among them, on the ET date of *now*.
    """
    now = _aware(now)
    if slug in LOCAL_SHORT_SLOTS:
        tz, wall = LOCAL_SHORT_SLOTS[slug]
        return _future(_at(now.astimezone(tz).date(), wall, tz), now, YOUTUBE_MIN_LEAD)
    day = now.astimezone(EASTERN).date()
    rank = release_rank(slug, peers)
    return _future(_at(day, SHORT_FIRST, EASTERN, SHORT_SPACING * rank), now, YOUTUBE_MIN_LEAD)


def youtube_long_time(slug: str, now: dt.datetime, *,
                      peers: Optional[Iterable[str]] = None) -> Optional[dt.datetime]:
    """When the long-form goes public, or ``None`` = now.

    The first half of the ranked shows (rounded up) take 12:00, 12:30 ... ET,
    the rest 18:00, 18:30 ... ET.
    """
    now = _aware(now)
    order = ranked(peers, include=slug)
    rank = order.index(slug)
    first_half = (len(order) + 1) // 2
    if rank < first_half:
        wall, step = LONG_FIRST_WAVE, rank
    else:
        wall, step = LONG_SECOND_WAVE, rank - first_half
    day = now.astimezone(EASTERN).date()
    return _future(_at(day, wall, EASTERN, LONG_SPACING * step), now, YOUTUBE_MIN_LEAD)


# ------------------------------------------------------------------------ X --
def x_slot(slug: str, now: dt.datetime, *,
           peers: Optional[Iterable[str]] = None) -> Optional[dt.datetime]:
    """The show's preferred X slot, or ``None`` when it has passed (or falls
    outside the posting window); the queue then takes the next free slot.

    Nerra Daily holds 7:00 ET; a show's is 7:30 ET + 30 min x its rank.
    """
    now = _aware(now)
    day = now.astimezone(EASTERN).date()
    if slug == NERRA_DAILY_SLUG:
        slot = _at(day, X_EDITION_SLOT, EASTERN)
    else:
        slot = _at(day, X_FIRST_SHOW, EASTERN, X_SPACING * release_rank(slug, peers))
    if slot > _at(day, X_WINDOW_END, EASTERN):
        return None
    return _future(slot, now, X_MIN_LEAD)


def x_posting_order(slugs: Iterable[str]) -> List[str]:
    """*slugs* in the order their X posts go out: Nerra Daily (7:00 ET) first,
    then each show by its :func:`x_slot` rank (the release order).

    The rank is taken against the whole :data:`RELEASE_ORDER`, exactly as
    ``engine.x_queue.choose_slot`` asks for the slot, so this is the order of
    the preferred slots. engine.x_post phases the follow ask on it.
    """
    pool = list(dict.fromkeys(slugs))
    head = [NERRA_DAILY_SLUG] if NERRA_DAILY_SLUG in pool else []
    rest = [s for s in pool if s != NERRA_DAILY_SLUG]
    return head + sorted(rest, key=lambda s: (release_rank(s), s))


def x_reserved_slots(day: dt.date) -> List[dt.datetime]:
    """Slots no show may take on *day* (ET): Nerra Daily's 7:00."""
    return [_at(day, X_EDITION_SLOT, EASTERN).astimezone(UTC)]


# --------------------------------------------------------------- newsletter --
def newsletter_send_time(slug: str, now: dt.datetime) -> Optional[dt.datetime]:
    """When a show's episode newsletter goes out, or ``None`` = send now.

    7:00 ET when *now* is before it on the same ET date; Vancouver's is
    6:00 Pacific on its own date.
    """
    now = _aware(now)
    tz, wall = LOCAL_NEWSLETTER_SLOTS.get(slug, (EASTERN, NEWSLETTER_SLOT))
    return _future(_at(now.astimezone(tz).date(), wall, tz), now, NEWSLETTER_MIN_LEAD)


def iso_utc(t: Optional[dt.datetime]) -> str:
    """RFC 3339 / ISO 8601 UTC with a ``Z`` (``""`` for ``None``)."""
    if t is None:
        return ""
    return _aware(t).astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def describe_public_at(stamp: str, *, now: Optional[dt.datetime] = None) -> str:
    """'12:30 PM ET' for a publishAt still ahead, '' for one past or unreadable.

    Read by run_show's feed rewrite: a long-form scheduled for the afternoon is
    linked from the morning's feed item with the time it goes public.
    """
    if not stamp:
        return ""
    try:
        t = dt.datetime.strptime(stamp, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=dt.timezone.utc)
    except ValueError:
        return ""
    if t <= _aware(now or dt.datetime.now(dt.timezone.utc)):
        return ""
    local = t.astimezone(EASTERN)
    return local.strftime("%I:%M %p ET").lstrip("0")
