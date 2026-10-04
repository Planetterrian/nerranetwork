"""EMIRA IV's position from the team's public YB tracker (Oct 4 2026).

The campaign's tracker page (``https://my.yb.tl/emira4``) is a single-page
app over a public JSON API — the same two calls the page makes:

* ``GET https://app.yb.tl/APIX/Blog/GetEvents?keyword=<kw>`` — the named
  windows the team set up ("Leaving Canada", "Training", …) plus a rolling
  "Last 30 days" window;
* ``GET https://app.yb.tl/APIX/Blog/GetPositions?keyword=<kw>&event=<id>``
  — every fix in a window as ``{"at": epoch_ms, "t": lat, "g": lon}``.

The Sep 19 2026 note in CLAUDE.md said the page "exposes no JSON endpoint";
that probe read only the HTML. This module reads the API the page itself
calls, which is what let the show say "alongside in Gosport, 4 October"
instead of a month-old blog post.

What it produces is a FIX, never a story: the newest dated position, where
the boat has sat since, the last time it left the berth, and how many
times it has gone out since it arrived. A place NAME is given only when
the fix sits inside a place the operator put in the record
(``tracker.places`` in ``site/data/offshore_north_dashboard.json``);
anywhere else the fix is spoken as coordinates. The tracker is never asked
to name a place it was not told about.

Wording rule (operator, 4 Oct 2026): a fix up to ``STALE_DAYS`` old may be
spoken in the present tense WITH its date and source ("As of 4 October,
the YB tracker has EMIRA IV alongside in Gosport"); an older one is "last
seen <date>", never the present tense.

Best-effort by contract: every network call returns ``None`` on failure and
nothing here raises into a run.
"""

from __future__ import annotations

import datetime as _dt
import logging
import math
from typing import Any, Dict, Iterable, List, Optional

logger = logging.getLogger(__name__)

API_BASE = "https://app.yb.tl/APIX/Blog"
PAGE_URL = "https://my.yb.tl/{keyword}"
_HEADERS = {
    "User-Agent": "NerraNetwork/1.0 (+https://nerranetwork.com)",
    "Origin": "https://my.yb.tl",
}
_TIMEOUT = 20

#: A fix older than this is "last seen <date>", never the present tense.
STALE_DAYS = 7

#: A fix this far from the newest berth counts as the boat being OUT.
OUTING_KM = 1.5

#: A far-away run this long is the boat living elsewhere, not an outing.
RESIDENCE_HOURS = 36

#: The rolling window the team's tracker keeps (matched by name).
_ROLLING_EVENT_RE = "last 30 days"


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    r = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = p2 - p1, math.radians(lon2 - lon1)
    h = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(h))


def _get_json(method: str, params: Dict[str, Any], session=None) -> Optional[Dict[str, Any]]:
    try:
        import requests

        http = session or requests
        resp = http.get(f"{API_BASE}/{method}", params=params, headers=_HEADERS,
                        timeout=_TIMEOUT)
        if resp.status_code != 200:
            logger.warning("YB %s: HTTP %s", method, resp.status_code)
            return None
        data = resp.json()
        if isinstance(data, dict) and data.get("error"):
            logger.warning("YB %s: %s", method, data.get("error"))
            return None
        return data if isinstance(data, dict) else None
    except Exception as exc:  # noqa: BLE001
        logger.warning("YB %s failed: %s", method, exc)
        return None


def _rolling_event_id(events: Iterable[Dict[str, Any]]) -> Optional[int]:
    """The "Last 30 days" window, else the newest-ending event."""
    events = [e for e in events if isinstance(e, dict) and e.get("id")]
    for e in events:
        if _ROLLING_EVENT_RE in str(e.get("name", "")).lower():
            return int(e["id"])
    if not events:
        return None
    return int(max(events, key=lambda e: e.get("endTime") or 0)["id"])


def parse_positions(payload: Optional[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """API positions → ``[{"at": aware datetime, "lat", "lon"}]``, oldest first."""
    out: List[Dict[str, Any]] = []
    for p in (payload or {}).get("positions") or []:
        try:
            at = _dt.datetime.fromtimestamp(int(p["at"]) / 1000, _dt.timezone.utc)
            out.append({"at": at, "lat": float(p["t"]), "lon": float(p["g"])})
        except (KeyError, TypeError, ValueError):
            continue
    out.sort(key=lambda f: f["at"])
    return out


def fetch_fixes(keyword: str, *, session=None) -> Optional[List[Dict[str, Any]]]:
    """Every fix in the tracker's rolling window, or ``None`` on failure."""
    events = _get_json("GetEvents", {"keyword": keyword}, session)
    if not events:
        return None
    event_id = _rolling_event_id(events.get("events") or [])
    if event_id is None:
        return None
    fixes = parse_positions(_get_json("GetPositions",
                                      {"keyword": keyword, "event": event_id}, session))
    return fixes or None


def place_for(lat: float, lon: float, places: Iterable[Dict[str, Any]]) -> str:
    """The operator-recorded place this fix sits inside, or ``""``."""
    best, best_km = "", None
    for p in places or []:
        try:
            d = haversine_km(lat, lon, float(p["lat"]), float(p["lon"]))
        except (KeyError, TypeError, ValueError):
            continue
        if d <= float(p.get("radius_km", 2.0)) and (best_km is None or d < best_km):
            best, best_km = str(p.get("name", "")), d
    return best


def coords_text(lat: float, lon: float) -> str:
    ns = "N" if lat >= 0 else "S"
    ew = "E" if lon >= 0 else "W"
    return f"{abs(lat):.2f}°{ns}, {abs(lon):.2f}°{ew}"


def _far_runs(dist: List[float]) -> List[tuple]:
    """``(start, end)`` index ranges (end exclusive) of fixes beyond OUTING_KM."""
    runs, k = [], 0
    while k < len(dist):
        if dist[k] > OUTING_KM:
            start = k
            while k < len(dist) and dist[k] > OUTING_KM:
                k += 1
            runs.append((start, k))
        else:
            k += 1
    return runs


def summarise(fixes: List[Dict[str, Any]], *, keyword: str,
              places: Iterable[Dict[str, Any]] = ()) -> Optional[Dict[str, Any]]:
    """The newest fix, when the boat arrived at that berth, and its outings.

    Every fix is measured from the NEWEST one (the berth). A run of fixes
    beyond :data:`OUTING_KM` that lasts longer than ``RESIDENCE_HOURS`` is
    the boat living somewhere else (a delivery, another port): the first
    berth fix after the last such run is the ARRIVAL. Shorter runs after
    the arrival are OUTINGS. When the window opens with the boat already
    at the berth, the arrival is not in the window and ``arrived`` is
    ``None`` — the record carries it, the tracker cannot.
    """
    if not fixes:
        return None
    places = list(places or [])
    last = fixes[-1]
    lat0, lon0 = last["lat"], last["lon"]
    dist = [haversine_km(lat0, lon0, f["lat"], f["lon"]) for f in fixes]
    runs = _far_runs(dist)
    arrival_idx = None
    for start, end in runs:
        span = fixes[end - 1]["at"] - fixes[start]["at"]
        if span >= _dt.timedelta(hours=RESIDENCE_HOURS) and end < len(fixes):
            arrival_idx = end
    outings: List[Dict[str, Any]] = []
    for start, end in runs:
        if arrival_idx is not None and start < arrival_idx:
            continue
        if end >= len(fixes):
            continue  # cannot happen: the newest fix is the berth
        far = max(range(start, end), key=lambda n: dist[n])
        outings.append({
            "date": fixes[start]["at"].date().isoformat(),
            "left": fixes[start]["at"].isoformat(),
            "back": fixes[end]["at"].isoformat(),
            "max_km": round(dist[far], 1),
            "furthest": coords_text(fixes[far]["lat"], fixes[far]["lon"]),
        })
    return {
        "keyword": keyword,
        "source": "YB tracker",
        "url": PAGE_URL.format(keyword=keyword),
        "latest": {
            "at": last["at"].isoformat(),
            "date": last["at"].date().isoformat(),
            "lat": round(lat0, 5),
            "lon": round(lon0, 5),
            "place": place_for(lat0, lon0, places),
            "coords": coords_text(lat0, lon0),
        },
        "arrived": (fixes[arrival_idx]["at"].date().isoformat()
                    if arrival_idx is not None else None),
        "outings": outings,
        "window_start": fixes[0]["at"].date().isoformat(),
        "fixes_in_window": len(fixes),
    }


def fetch_summary(keyword: str, *, places: Iterable[Dict[str, Any]] = (),
                  session=None) -> Optional[Dict[str, Any]]:
    fixes = fetch_fixes(keyword, session=session)
    if not fixes:
        return None
    return summarise(fixes, keyword=keyword, places=places)


def _long_date(iso: str) -> str:
    d = _dt.date.fromisoformat(iso[:10])
    return f"{d.day} {d.strftime('%B %Y')}"


def position_sentence(summary: Optional[Dict[str, Any]], today: _dt.date,
                      boat: str = "EMIRA IV") -> str:
    """One sourced, dated sentence — present tense only inside STALE_DAYS."""
    if not summary or not summary.get("latest"):
        return ""
    latest = summary["latest"]
    where = (f"alongside in {latest['place']}" if latest.get("place")
             else f"at {latest.get('coords', '')}")
    when = _long_date(latest["date"])
    age = (today - _dt.date.fromisoformat(latest["date"])).days
    if age <= STALE_DAYS:
        return f"As of {when}, the team's YB tracker has {boat} {where}."
    return f"{boat} was last seen on the team's YB tracker on {when}, {where}."


def tracker_article(summary: Optional[Dict[str, Any]], today: _dt.date) -> Optional[Dict[str, Any]]:
    """The fix as a hook article, so the claims gate verifies the position
    sentence against the copy the run holds (the tracker page is a script
    app; an HTTP fetch of it returns no text)."""
    sentence = position_sentence(summary, today)
    if not sentence:
        return None
    lines = [sentence]
    if summary.get("arrived"):
        lines.append(f"The tracker shows the boat arriving at this berth on "
                     f"{_long_date(summary['arrived'])}.")
    outs = summary.get("outings") or []
    since = (f"since {_long_date(summary['arrived'])}" if summary.get("arrived")
             else f"since {_long_date(summary['window_start'])} (the tracker's 30-day window)")
    if outs:
        trips = "; ".join(f"{_long_date(o['date'])}, out to {o['max_km']:.0f} km from the berth"
                          for o in outs)
        lines.append(f"Outings {since}: {len(outs)} ({trips}).")
    else:
        lines.append(f"No outing on the tracker {since}.")
    return {
        "title": f"YB tracker: {sentence}",
        "url": summary.get("url") or PAGE_URL.format(keyword=summary.get("keyword", "")),
        "description": sentence,
        "content_text": " ".join(lines),
        "source_name": "YB tracker (Canada Ocean Racing)",
        "published_date": summary["latest"]["at"],
        "exempt_stale": True,
    }
