"""Nerra Personal: a member's routes and trips (Nov 13 2026).

Two member-typed lists ride the spec beside cities and topics:

* **Routes** — the trips a member makes most days ("from", "to", an
  optional "via", the days they make it and how they travel). With the
  ``traffic`` add-on on, Mira's traffic research follows THOSE routes
  ("Your commute") instead of the whole city. Off = nothing changes.
* **Trips** — a place they are going and, optionally, the dates. Mira
  tells them about the place (its history, its culture, what to see, the
  practical things) once a week until she runs out of angles, looks up
  what is on there during the stay as the dates near, and each morning of
  the stay says what is on that day.

Both are personal data. They live in the member's Worker record, reach
the builder only through the bearer-protected admin spec export (never an
email beside them), go to the model that writes Mira's lines (as city and
profile already do), and are never logged: logs carry the token prefix
only. A trip that has ended is dropped by the Worker on save and ignored
here.

Sourcing follows the field-note rules every researched Personal segment
runs under: one web-search-grounded call, every item names its source
aloud, an unverifiable item is omitted and an unverifiable day is SKIP.
There is no live-traffic API (every regional one needs a key — a paid
source is the operator's call), so the commute segment reports reported
closures, works, detours and transit changes on the member's routes,
never live congestion or a travel time.
"""

from __future__ import annotations

import datetime as _dt
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

#: Mirrored in workers/gallery/src/personal.ts (drift-guarded in
#: tests/test_personal_travel_2026_11_13.py).
ROUTES_MAX = 3
ROUTE_PART_MAX = 80
#: When a route is travelled. ``weekdays`` is a commute.
ROUTE_DAYS: Tuple[str, ...] = ("weekdays", "daily", "weekends")
#: How the member travels it. ``any`` asks for both roads and transit.
ROUTE_MODES: Tuple[str, ...] = ("any", "drive", "transit", "cycle")

TRIPS_MAX = 3
TRIP_PLACE_MAX = 80
#: The furthest ahead a trip may start, and the longest stay with dates.
#: A start further out or a longer stay keeps the place and drops the
#: dates (the angles still run; the events never guess a calendar).
TRIP_MAX_DAYS_AHEAD = 730
TRIP_MAX_STAY_DAYS = 90

#: The place itself, one angle per edition, in this order. Each is told
#: once per trip — no angle is ever re-told.
TRIP_ANGLES: Tuple[str, ...] = ("history", "culture", "sights", "practical")
#: How often a trip segment may run: weekly, every other day in the last
#: three weeks before a dated trip, every day of the stay.
TRIP_GAP_DAYS = 7
TRIP_NEAR_GAP_DAYS = 2
TRIP_NEAR_DAYS = 21
TRIP_FINAL_DAYS = 3

_ISO_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_FREE_TEXT_RE = re.compile(r"[^\w \-.,'’&/()]", re.UNICODE)


def _clean(value: object, max_chars: int) -> str:
    """The same scrub as engine.personal_edition._clean_free_text (and the
    Worker's cleanList): tags out whole, markup out, whitespace collapsed,
    length capped."""
    text = re.sub(r"<[^>]*>", " ", str(value or ""))
    text = _FREE_TEXT_RE.sub("", text)
    text = " ".join(text.split())
    return text[:max_chars].strip()


@dataclass(frozen=True)
class Route:
    origin: str
    destination: str
    via: str = ""
    days: str = "weekdays"
    mode: str = "any"

    def runs_on(self, day: _dt.date) -> bool:
        weekend = day.weekday() >= 5
        if self.days == "weekdays":
            return not weekend
        if self.days == "weekends":
            return weekend
        return True

    def spoken(self) -> str:
        """The route as one prompt line."""
        line = f"{self.origin} to {self.destination}"
        if self.via:
            line += f" via {self.via}"
        how = {"drive": "by car", "transit": "by public transit",
               "cycle": "by bike"}.get(self.mode, "by road or transit")
        return f"{line}, {how}"


@dataclass(frozen=True)
class Trip:
    place: str
    start: Optional[_dt.date] = None
    end: Optional[_dt.date] = None

    @property
    def key(self) -> str:
        """Identity for the heard-history: the place and its start date,
        so a second trip to the same place starts its angles over."""
        return f"{self.place.lower()}|{self.start.isoformat() if self.start else ''}"

    def is_over(self, today: _dt.date) -> bool:
        return self.end is not None and self.end < today


def clean_routes(raw: object) -> List[Route]:
    """A member's routes as the Worker stores them: dicts with ``from`` and
    ``to`` (both required), optional ``via``, ``days`` and ``mode`` from the
    closed sets (anything else is the default), case-insensitive dedupe,
    at most ROUTES_MAX."""
    out: List[Route] = []
    if not isinstance(raw, list):
        return out
    seen = set()
    for r in raw:
        if not isinstance(r, dict):
            continue
        origin = _clean(r.get("from"), ROUTE_PART_MAX)
        dest = _clean(r.get("to"), ROUTE_PART_MAX)
        if not origin or not dest:
            continue
        via = _clean(r.get("via"), ROUTE_PART_MAX)
        days = str(r.get("days") or "")
        mode = str(r.get("mode") or "")
        route = Route(origin, dest, via,
                      days if days in ROUTE_DAYS else ROUTE_DAYS[0],
                      mode if mode in ROUTE_MODES else ROUTE_MODES[0])
        ident = (origin.lower(), dest.lower(), via.lower())
        if ident in seen:
            continue
        seen.add(ident)
        out.append(route)
        if len(out) >= ROUTES_MAX:
            break
    return out


def _date(value: object) -> Optional[_dt.date]:
    s = str(value or "").strip()
    if not _ISO_RE.match(s):
        return None
    try:
        return _dt.date.fromisoformat(s)
    except ValueError:
        return None


def clean_trips(raw: object, today: _dt.date) -> List[Trip]:
    """A member's trips: a place (required) and optional ISO dates. An end
    without a start is dropped; a start without an end is a one-day stay;
    dates too far ahead or a stay too long keep the place, drop the dates.
    A trip already over is dropped. At most TRIPS_MAX."""
    out: List[Trip] = []
    if not isinstance(raw, list):
        return out
    seen = set()
    for t in raw:
        if not isinstance(t, dict):
            continue
        place = _clean(t.get("place"), TRIP_PLACE_MAX)
        if not place:
            continue
        start, end = _date(t.get("start")), _date(t.get("end"))
        if start is None:
            end = None
        elif end is None or end < start:
            end = start
        if start is not None and (
                (start - today).days > TRIP_MAX_DAYS_AHEAD
                or (end - start).days > TRIP_MAX_STAY_DAYS):
            start = end = None
        trip = Trip(place, start, end)
        if trip.is_over(today) or trip.key in seen:
            continue
        seen.add(trip.key)
        out.append(trip)
        if len(out) >= TRIPS_MAX:
            break
    return out


# ---------------------------------------------------------------------------
# The commute
# ---------------------------------------------------------------------------

def routes_today(routes: Sequence[Route], day: _dt.date) -> List[Route]:
    return [r for r in routes if r.runs_on(day)]


def wants_commute(addons: Sequence[str], routes: Sequence[Route],
                  day: _dt.date) -> bool:
    """The commute segment runs only with the traffic add-on ON and a route
    the member travels on this day."""
    return "traffic" in addons and bool(routes_today(routes, day))


def build_commute_prompt(root: Path, routes: Sequence[Route], day: _dt.date,
                         listener_name: str, city: str = "") -> str:
    template = (root / "shows" / "prompts" / "nerra_personal_commute.txt"
                ).read_text(encoding="utf-8")
    todays = routes_today(routes, day)
    return template.format(
        date_spoken=day.strftime("%A, %B %-d, %Y"),
        listener_name=listener_name or "the listener",
        home_area=city or "(not given — infer the region from the routes)",
        route_lines="\n".join(f"- {r.spoken()}" for r in todays),
        route_count=len(todays),
        words_lo=40, words_hi=60 + 50 * len(todays),
    )


def commute_max_words(routes: Sequence[Route], day: _dt.date) -> int:
    return 80 + 60 * max(1, len(routes_today(routes, day)))


# ---------------------------------------------------------------------------
# Trips
# ---------------------------------------------------------------------------

def trip_mode(trip: Trip, today: _dt.date,
              heard: Sequence[dict]) -> Optional[str]:
    """What, if anything, today's edition tells this member about *trip*.

    *heard* is this trip's history before today: ``[{"date": iso, "mode":
    m}, ...]`` (the builder drops today's own entries, so a rebuild of the
    day hears the same segment again).
    During a dated stay it is every day (``during``). Before it: the
    events during the stay once inside TRIP_NEAR_DAYS (``events``) and
    a final look inside TRIP_FINAL_DAYS (``events_final``); otherwise the
    next angle not yet told, no sooner than the gap since the last one."""
    if trip.is_over(today):
        return None
    modes = {str(h.get("mode")) for h in heard}
    dates = [d for d in (_date(h.get("date")) for h in heard) if d]
    last = max(dates) if dates else None
    gap = TRIP_GAP_DAYS
    if trip.start is not None:
        if trip.start <= today <= (trip.end or trip.start):
            return "during"
        until = (trip.start - today).days
        if until <= TRIP_FINAL_DAYS and "events_final" not in modes:
            return "events_final"
        if until <= TRIP_NEAR_DAYS and not modes & {"events", "events_final"}:
            return "events"
        if until <= TRIP_NEAR_DAYS:
            gap = TRIP_NEAR_GAP_DAYS
    if last is not None and (today - last).days < gap:
        return None
    for angle in TRIP_ANGLES:
        if angle not in modes:
            return angle
    return None


def plan_trip(trips: Sequence[Trip], today: _dt.date,
              heard: Dict[str, List[dict]]) -> Optional[Tuple[Trip, str]]:
    """At most ONE trip segment an edition: the soonest dated trip with
    something to say, then undated trips in the member's order."""
    def order(t: Trip):
        return (t.start is None, t.start or _dt.date.max)
    for trip in sorted(trips, key=order):
        mode = trip_mode(trip, today, heard.get(trip.key, []))
        if mode:
            return trip, mode
    return None


def record_trip_heard(heard: Dict[str, List[dict]], trip: Trip, mode: str,
                      today: _dt.date, trips: Sequence[Trip]) -> Dict[str, List[dict]]:
    """The heard-history after today's segment, keeping only the member's
    current trips (a removed or finished trip leaves no trace)."""
    keep = {t.key for t in trips}
    out = {k: list(v) for k, v in (heard or {}).items() if k in keep}
    out.setdefault(trip.key, []).append({"date": today.isoformat(), "mode": mode})
    return out


def prune_trip_heard(heard: Dict[str, List[dict]],
                     trips: Sequence[Trip]) -> Dict[str, List[dict]]:
    keep = {t.key for t in trips}
    return {k: list(v) for k, v in (heard or {}).items() if k in keep}


#: Shape-only focus lines (de-seed by shape — never a quotable sentence).
_TRIP_FOCUS = {
    "history": (
        "The place's history: two or three moments or forces that made it "
        "what it is, told so the listener will recognise their traces when "
        "they are there. Specific names and dates, no survey of centuries."),
    "culture": (
        "The place's culture as a visitor meets it: food and drink worth "
        "seeking out, a custom or two that would surprise a newcomer, and a "
        "few words of the local language if it is not English."),
    "sights": (
        "What to see beyond the obvious postcard: two or three places with "
        "the specific reason each is worth the time."),
    "practical": (
        "The practical things: getting around, the season's conditions "
        "they should expect for their dates (or the time of year if no "
        "dates), and any current advisory, strike or closure a visitor "
        "should know about."),
    "events": (
        "What is on there during their stay ({stay}): festivals, concerts, "
        "exhibitions, matches, markets, holidays that close things. Only "
        "events with a confirmed date inside the stay; say each one's "
        "date."),
    "events_final": (
        "A last look before they go ({stay}): events confirmed for their "
        "dates, anything newly announced, and any strike, closure or "
        "advisory that would change their plans. Do not repeat background "
        "about the place."),
    "during": (
        "They are there now (day {day_n} of their stay, {stay}). What is "
        "on today and tomorrow: events, openings, a market, anything that "
        "closes or disrupts. Practical, current, short."),
}


def _stay_words(trip: Trip) -> str:
    if trip.start is None:
        return "no dates given"
    if trip.end is None or trip.end == trip.start:
        return trip.start.strftime("%A, %B %-d")
    return (f"{trip.start.strftime('%B %-d')} to "
            f"{trip.end.strftime('%B %-d, %Y')}")


def build_trip_prompt(root: Path, trip: Trip, mode: str, today: _dt.date,
                      listener_name: str, weather_line: str = "") -> str:
    template = (root / "shows" / "prompts" / "nerra_personal_trip.txt"
                ).read_text(encoding="utf-8")
    day_n = (today - trip.start).days + 1 if trip.start else 1
    focus = _TRIP_FOCUS[mode].format(stay=_stay_words(trip), day_n=day_n)
    if trip.start is None:
        when = "They have not given dates."
    elif mode == "during":
        when = f"They are there now: {_stay_words(trip)}."
    else:
        until = (trip.start - today).days
        when = (f"They arrive in {until} day{'s' if until != 1 else ''} "
                f"({_stay_words(trip)}).")
    weather_block = ("Measured weather there today (from Open-Meteo — read "
                     "it naturally, never alter the numbers):\n" + weather_line
                     if weather_line else "(No weather for this segment.)")
    return template.format(
        date_spoken=today.strftime("%A, %B %-d, %Y"),
        listener_name=listener_name or "the listener",
        place=trip.place, when=when, focus=focus,
        weather_block=weather_block,
        words_lo=70 if mode == "during" else 90,
        words_hi=140 if mode == "during" else 190,
    )


TRIP_MAX_WORDS = 220


def trip_chapter_title(trip: Trip) -> str:
    from engine.titles import clip_words

    return clip_words(f"Your trip to {trip.place}", 100)


COMMUTE_CHAPTER_TITLE = "Your commute"
