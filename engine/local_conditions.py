"""Roads and weather as hook articles for the local shows (Sep 2026).

Vancouver Daily News and Collingwood Weekly (docs/new_shows_plan_2026_09_22.md
§4.5-4.6) each carry a getting-around section. A model asked for "the roads
and the weather" with nothing in front of it writes them from memory, and the
claims gate then strips every sentence it cannot trace — so the section would
either be invented or empty. These functions turn three public, keyless data
sources into ordinary hook ARTICLES (engine/hook_articles.py): each has a real
URL and the data as its ``content_text``, so the digest cites it and
``engine.claims.build_local_texts`` verifies a quote against the copy the run
already holds, with no second fetch.

Sources (all probed 2026-09-23 from this session's egress):

* DriveBC Open511 (``api.open511.gov.bc.ca/events``) — BC road events, JSON,
  filterable by area (``drivebc.ca/1`` is the Lower Mainland District).
* Ontario 511 (``511on.ca/api/v2/get/event``) — every Ontario road event in
  one ~700 KB JSON list with coordinates; filtered here to a bounding box.
* Environment Canada's location Atom feed
  (``weather.gc.ca/rss/weather/<lat>_<lon>_e.xml``) — warnings, current
  conditions and the forecast periods. The old ``/rss/city/<code>_e.xml``
  path the plan named returns 404.

Every function is best-effort: a network error, a bad payload or an empty
result returns ``None`` and logs, because a hook failure must degrade to "no
road data today", never to a failed episode. Nothing here writes a file.
"""

from __future__ import annotations

import datetime as _dt
import html
import logging
import re
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple

logger = logging.getLogger(__name__)

USER_AGENT = "Mozilla/5.0 (compatible; NerraNetwork/1.0; +https://nerranetwork.com)"
TIMEOUT_S = 15

#: A fetcher returns parsed JSON (dict/list) or text, given a URL. Injectable
#: so tests never touch the network.
Fetch = Callable[[str], Any]

DRIVEBC_EVENTS_URL = "https://api.open511.gov.bc.ca/events"
DRIVEBC_PUBLIC_URL = "https://www.drivebc.ca/"
ONTARIO_511_URL = "https://511on.ca/api/v2/get/event?format=json&lang=en"
ONTARIO_511_PUBLIC_URL = "https://511on.ca/"

#: The most road events one article carries. The section is one or two
#: minutes of audio; a list of forty closures is not a briefing.
MAX_EVENTS = 8

#: Forecast periods kept (today, tonight, tomorrow, tomorrow night, ...).
MAX_FORECAST_PERIODS = 5


def _http_json(url: str) -> Any:
    import requests

    resp = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=TIMEOUT_S)
    resp.raise_for_status()
    return resp.json()


def _http_text(url: str) -> str:
    import requests

    resp = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=TIMEOUT_S)
    resp.raise_for_status()
    return resp.text


def _clean(text: str) -> str:
    text = html.unescape(re.sub(r"<[^>]+>", " ", str(text or "")))
    return re.sub(r"\s+", " ", text).strip()


def _now_iso() -> str:
    return _dt.datetime.now(_dt.timezone.utc).replace(microsecond=0).isoformat()


# ---------------------------------------------------------------------------
# Roads
# ---------------------------------------------------------------------------

def _drivebc_line(ev: Dict[str, Any]) -> str:
    kind = str(ev.get("event_type") or "").replace("_", " ").lower()
    sev = str(ev.get("severity") or "").lower()
    desc = _clean(ev.get("description") or "")
    # DriveBC appends a "Last update: …" sentence to every description; it is
    # noise in a briefing and the article is dated anyway.
    desc = re.sub(r"\s*(?:Last update[d]?:?|Next update(?: time)?:?)[^.]*?(?:PDT|PST|MST|MDT)\.?", " ", desc)
    desc = re.sub(r"\s*\(DBC-\d+\)", "", desc)
    desc = re.sub(r"\s*\.\s*\.", ".", desc).strip()
    road = ""
    roads = ev.get("roads") or []
    if roads and isinstance(roads[0], dict):
        name = _clean(roads[0].get("name") or "")
        frm = _clean(roads[0].get("from") or "")
        if name and name.lower() != "other roads":
            road = name
        elif frm:
            road = frm
    where = f" on {road}" if road and road.lower() not in desc.lower() else ""
    return f"- {sev} {kind}{where}: {desc}".replace("  ", " ")


def _first_point(geo: Any) -> Optional[Tuple[float, float]]:
    """(lat, lon) of a GeoJSON Point / LineString / Multi* geometry."""
    try:
        coords = (geo or {}).get("coordinates")
        while coords and isinstance(coords[0], (list, tuple)):
            coords = coords[0]
        lon, lat = float(coords[0]), float(coords[1])
        return lat, lon
    except (TypeError, ValueError, IndexError, AttributeError):
        return None


#: Metro Vancouver (Lions Bay to Langley, the border to the North Shore
#: mountains) as (south, west, north, east). DriveBC's "Lower Mainland
#: District" runs to Hope and the Fraser Canyon, which is not this show's
#: region — the first probe's top event was a washout near Hope.
METRO_VANCOUVER_BOX = (49.0, -123.35, 49.50, -122.45)

#: An incident older than this is not today's news (DriveBC keeps washouts
#: "active" with a next update months away).
INCIDENT_MAX_AGE_H = 48


def drivebc_article(
    area_id: str = "drivebc.ca/1",
    area_name: str = "Metro Vancouver",
    *,
    box: Optional[Tuple[float, float, float, float]] = METRO_VANCOUVER_BOX,
    fetch: Fetch = _http_json,
    max_events: int = MAX_EVENTS,
    now: Optional[_dt.datetime] = None,
) -> Optional[Dict[str, Any]]:
    """Active MAJOR events and fresh INCIDENTS in one DriveBC area.

    Minor planned roadwork is left out: the Lower Mainland carries ~55 minor
    construction events on an ordinary day, and a commuter needs the closures
    and the crashes, not the line-painting.
    """
    url = f"{DRIVEBC_EVENTS_URL}?format=json&status=ACTIVE&area_id={area_id}&limit=500"
    try:
        data = fetch(url)
        events = list((data or {}).get("events") or [])
    except Exception as exc:  # noqa: BLE001 — degrade to no road data
        logger.warning("DriveBC fetch failed (non-fatal): %s", exc)
        return None
    now = now or _dt.datetime.now(_dt.timezone.utc)

    def _fresh(ev: Dict[str, Any]) -> bool:
        try:
            upd = _dt.datetime.fromisoformat(str(ev.get("updated") or ""))
            return (now - upd).total_seconds() <= INCIDENT_MAX_AGE_H * 3600
        except ValueError:
            return False

    def _inside(ev: Dict[str, Any]) -> bool:
        if box is None:
            return True
        pt = _first_point(ev.get("geography"))
        if not pt:
            return False
        south, west, north, east = box
        return south <= pt[0] <= north and west <= pt[1] <= east

    regional = [e for e in events if _inside(e)]
    incidents = [e for e in regional
                 if str(e.get("event_type") or "").upper() == "INCIDENT" and _fresh(e)]
    majors = [e for e in regional
              if str(e.get("severity") or "").upper() == "MAJOR" and e not in incidents]
    incidents.sort(key=lambda e: str(e.get("updated") or ""), reverse=True)
    majors.sort(key=lambda e: str(e.get("updated") or ""), reverse=True)
    chosen = (incidents + majors)[:max_events]
    if not chosen:
        logger.info("DriveBC: no major events or fresh incidents in %s", area_name)
        return None
    lines = [_drivebc_line(e) for e in chosen]
    body = (f"DriveBC active road events in {area_name} (closures, major work and "
            f"incidents updated in the last {INCIDENT_MAX_AGE_H} hours; "
            f"{len(regional)} active events in the area):\n" + "\n".join(lines))
    return {
        "title": f"DriveBC: {len(chosen)} major road events in {area_name}",
        "url": DRIVEBC_PUBLIC_URL,
        "description": lines[0][2:][:300],
        "content_text": body,
        "source_name": "DriveBC",
        "published_date": _now_iso(),
        # A closure that began last month and is still in force is today's
        # news for a driver; the stale gate must not drop it.
        "exempt_stale": True,
    }


def _in_box(ev: Dict[str, Any], box: Tuple[float, float, float, float]) -> bool:
    try:
        lat, lon = float(ev.get("Latitude")), float(ev.get("Longitude"))
    except (TypeError, ValueError):
        return False
    south, west, north, east = box
    return south <= lat <= north and west <= lon <= east


def ontario511_article(
    box: Tuple[float, float, float, float],
    area_name: str,
    *,
    fetch: Fetch = _http_json,
    max_events: int = MAX_EVENTS,
) -> Optional[Dict[str, Any]]:
    """Ontario 511 events inside ``box`` = (south, west, north, east).

    Closures and incidents lead; ordinary lane work fills what is left.
    """
    try:
        events = list(fetch(ONTARIO_511_URL) or [])
    except Exception as exc:  # noqa: BLE001
        logger.warning("Ontario 511 fetch failed (non-fatal): %s", exc)
        return None
    local = [e for e in events if isinstance(e, dict) and _in_box(e, box)]
    if not local:
        logger.info("Ontario 511: no events in %s", area_name)
        return None

    def _rank(e: Dict[str, Any]) -> tuple:
        kind = str(e.get("EventType") or "").lower()
        return (not bool(e.get("IsFullClosure")), kind not in ("accidentsandincidents", "incident"),
                -(int(e.get("LastUpdated") or 0)))

    local.sort(key=_rank)
    seen, chosen = set(), []
    for e in local:
        # Daily and nightly entries for the same closure repeat word for word.
        key = re.sub(r"\b(daily|nightly)\b", "", _clean(e.get("Description") or "").lower())
        if key in seen:
            continue
        seen.add(key)
        chosen.append(e)
        if len(chosen) >= max_events:
            break
    lines = []
    for e in chosen:
        road = _clean(e.get("RoadwayName") or "")
        desc = _clean(e.get("Description") or "")
        lanes = _clean(e.get("LanesAffected") or "")
        lines.append(f"- {road}: {desc}" + (f" ({lanes})" if lanes and lanes not in desc else ""))
    body = (f"Ontario 511 road events around {area_name} ({len(local)} in the area):\n"
            + "\n".join(lines))
    return {
        "title": f"Ontario 511: {len(chosen)} road events around {area_name}",
        "url": ONTARIO_511_PUBLIC_URL,
        "description": lines[0][2:][:300],
        "content_text": body,
        "source_name": "Ontario 511",
        "published_date": _now_iso(),
        "exempt_stale": True,
    }


# ---------------------------------------------------------------------------
# Weather
# ---------------------------------------------------------------------------

def weather_feed_url(lat: float, lon: float) -> str:
    return f"https://weather.gc.ca/rss/weather/{lat:g}_{lon:g}_e.xml"


_ENTRY_RE = re.compile(
    r"<entry>.*?<title>(?P<title>.*?)</title>.*?<summary[^>]*>(?P<summary>.*?)</summary>.*?</entry>",
    re.S,
)


def parse_weather_feed(xml: str) -> Dict[str, Any]:
    """{warnings: [...], current: str, periods: [(title, summary), ...]}."""
    out: Dict[str, Any] = {"warnings": [], "current": "", "periods": []}
    for m in _ENTRY_RE.finditer(xml or ""):
        title = _clean(re.sub(r"<!\[CDATA\[|\]\]>", "", m.group("title")))
        summary = _clean(re.sub(r"<!\[CDATA\[|\]\]>", "", m.group("summary")))
        low = title.lower()
        if low.startswith("current conditions"):
            out["current"] = title.split(":", 1)[-1].strip()
        elif "watch" in low or "warning" in low or "statement" in low or "advisory" in low:
            if not low.startswith("no watches or warnings"):
                out["warnings"].append(f"{title}: {summary}"[:400])
        else:
            name = title.split(":", 1)[0].strip()
            summary = re.sub(r"\s*Forecast issued .*$", "", summary).strip()
            out["periods"].append((name, summary[:300]))
    return out


def weather_article(
    lat: float,
    lon: float,
    place: str,
    *,
    fetch: Callable[[str], str] = _http_text,
    max_periods: int = MAX_FORECAST_PERIODS,
) -> Optional[Dict[str, Any]]:
    url = weather_feed_url(lat, lon)
    try:
        parsed = parse_weather_feed(fetch(url))
    except Exception as exc:  # noqa: BLE001
        logger.warning("Environment Canada fetch failed for %s (non-fatal): %s", place, exc)
        return None
    periods = parsed["periods"][:max_periods]
    if not periods:
        logger.info("Environment Canada: no forecast periods for %s", place)
        return None
    lines = []
    if parsed["warnings"]:
        lines.append("Alerts in effect: " + " | ".join(parsed["warnings"]))
    else:
        lines.append("No watches or warnings in effect.")
    if parsed["current"]:
        lines.append(f"Current conditions: {parsed['current']}.")
    lines += [f"- {t}: {s}" for t, s in periods]
    return {
        "title": f"Environment Canada forecast for {place}",
        "url": url,
        "description": f"{periods[0][0]}: {periods[0][1]}"[:300],
        "content_text": f"Environment Canada forecast for {place}.\n" + "\n".join(lines),
        "source_name": "Environment Canada",
        "published_date": _now_iso(),
    }


def conditions_block(articles: Sequence[Dict[str, Any]], section: str) -> str:
    """The digest instruction that goes with the articles.

    Names the section these articles feed and the one honest fallback, so a
    data-less day produces one sentence rather than an invented forecast.
    """
    have = [a.get("source_name", "") for a in articles]
    if not articles:
        return (f"### {section.upper()} DATA (instruction — do not include in output)\n"
                f"No road or weather data reached the pipeline today. The {section} "
                "section is ONE sentence saying the data feeds were unavailable — "
                "never a forecast or a closure from memory.")
    return (f"### {section.upper()} DATA (instruction — do not include in output)\n"
            f"The {section} section is built ONLY from these articles in the list "
            f"above: {', '.join(have)}. Cite each by its URL like any article. "
            "Name the road or place, what is closed or expected, and the day; skip "
            "what is ordinary. Never add a closure, a temperature or an alert that "
            "those articles do not carry.")


def gather(builders: List[Callable[[], Optional[Dict[str, Any]]]]) -> List[Dict[str, Any]]:
    """Run each builder, keep what came back. Never raises."""
    out: List[Dict[str, Any]] = []
    for build in builders:
        try:
            art = build()
        except Exception as exc:  # noqa: BLE001
            logger.warning("local conditions builder failed (non-fatal): %s", exc)
            art = None
        if art:
            out.append(art)
    return out
