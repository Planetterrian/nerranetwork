"""Offshore North — the computed CAMPAIGN STATUS block (Sep 19 2026).

One record feeds two surfaces. ``site/data/offshore_north_dashboard.json``
is the show's verified campaign record (dated, sourced, operator-maintained)
and the public dashboard bakes it in; this module renders the SAME record
into a dated block for the digest and podcast prompts, so the show and the
page can never disagree about where the boat was last reported, which
races have started, are running or have finished, and what the results on
record are.

Why it exists: the two errors the operator scored on Ep005 (14 Sep 2026)
were both DATE errors — a 1 September race start aired on the 14th as if
live, and the boat was reported as still in Canada because the newest
dated fix fell outside a 7-day window. The prompt's RACE STATE CHECK rule
asks the model to work that out from the articles; this block does the
arithmetic from the record and hands it over, by today's date.

Contract: pure function of the record + a clock, never raises into the
pipeline (the hook wraps it; an empty string degrades to the pre-Sep-19
prompt), never invents a date — every line carries the date it came from.
"""

from __future__ import annotations

import datetime as _dt
import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

_ROOT = Path(__file__).resolve().parent.parent
CURATED_PATH = _ROOT / "site" / "data" / "offshore_north_dashboard.json"
LIVE_PATH = _ROOT / "api" / "offshore_north_dashboard.json"

#: Vendée Globe 2028 start — the show's fixed clock (also in the record's
#: ``countdowns`` as ``vg_start``; this is the fallback if that entry goes).
VENDEE_GLOBE_START = _dt.date(2028, 11, 12)

MAX_RESULT_ROWS = 3


def _parse_date(value: Any) -> Optional[_dt.date]:
    if not value:
        return None
    text = str(value).strip()
    try:
        return _dt.date.fromisoformat(text[:10])
    except ValueError:
        return None


def _parse_when(value: Any) -> Optional[_dt.datetime]:
    if not value:
        return None
    try:
        dt = _dt.datetime.fromisoformat(str(value).strip())
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=_dt.timezone.utc)
    return dt


def _days_word(n: int) -> str:
    return f"{n} day" if abs(n) == 1 else f"{n} days"


def _fmt(d: _dt.date) -> str:
    return d.strftime("%-d %B %Y") if hasattr(d, "strftime") else str(d)


def race_state(when: Optional[_dt.datetime], end: Optional[_dt.datetime],
               now: _dt.datetime) -> str:
    """NOT STARTED / RUNNING / FINISHED for an event window, by the clock.

    ``end`` is the last day the event is still "on" (a finish window for a
    race, the last day of a regatta). Without an ``end`` a passed start is
    FINISHED the day after it.
    """
    if when is None:
        return "DATE UNKNOWN"
    if now < when:
        return "NOT STARTED"
    if end is not None:
        return "RUNNING" if now <= end else "FINISHED"
    return "RUNNING" if (now - when) < _dt.timedelta(days=1) else "FINISHED"


def _host(url: str) -> str:
    try:
        from urllib.parse import urlparse

        return (urlparse(url).netloc or "").replace("www.", "")
    except Exception:  # noqa: BLE001
        return ""


def _entered_word(flag: Any, text: str = "") -> str:
    if text:
        return text
    if flag is True:
        return "EMIRA IV ENTERED"
    if flag is False:
        return "EMIRA IV not entered / did not sail"
    return "EMIRA IV entry unconfirmed"


def _latest_fix(curated: Dict[str, Any], live: Optional[Dict[str, Any]],
                today: Optional[_dt.date] = None) -> Optional[Dict[str, Any]]:
    """The newest dated fix: the operator-verified log, or the live rail's
    derived fix when it is newer (the same rule the page applies). A fix
    dated after ``today`` is not yet a fix — the block is computed for a
    clock, and a record can be newer than the clock it is read at."""
    log = [p for p in (curated.get("position_log") or []) if _parse_date(p.get("date"))
           and (today is None or _parse_date(p.get("date")) <= today)]
    best = max(log, key=lambda p: p["date"]) if log else None
    live_pos = (live or {}).get("position") if isinstance(live, dict) else None
    if isinstance(live_pos, dict) and _parse_date(live_pos.get("date")):
        if best is None or live_pos["date"] > best.get("date", ""):
            best = {
                "date": live_pos["date"],
                "text": live_pos.get("text") or live_pos.get("title") or "",
                "url": live_pos.get("url", ""),
                "source": live_pos.get("channel", "the team's channels"),
            }
    return best


def _tracker_lines(tracker: Dict[str, Any], today: _dt.date) -> List[str]:
    """The YB tracker fix, worded by the operator's rule (Oct 4 2026)."""
    from engine.yb_tracker import STALE_DAYS, position_sentence

    latest = tracker.get("latest") or {}
    fd = _parse_date(latest.get("date"))
    if fd is None:
        return []
    age = (today - fd).days
    sentence = position_sentence(tracker, today)
    tense = ("present tense is allowed, WITH this date and the source" if age <= STALE_DAYS
             else f"it is more than {STALE_DAYS} days old, so say \"last seen {_fmt(fd)}\" — "
                  "never the present tense")
    lines = [
        f"LAST KNOWN POSITION — YB TRACKER, newest fix {latest.get('date')} "
        f"({_days_word(age)} ago): {sentence} Source: {tracker.get('url', '')}. "
        f"Every position sentence carries its date and its source; {tense}. "
        f"This outranks any blog post about where the boat was going."
    ]
    outs = tracker.get("outings") or []
    since = (f"since it arrived on {tracker['arrived']}" if tracker.get("arrived")
             else f"in the tracker's window from {tracker.get('window_start', '')}")
    if outs:
        trips = "; ".join(f"{o['date']} (out to {o['max_km']:.0f} km)" for o in outs)
        lines.append(
            f"OUTINGS ON THE TRACKER {since}: {len(outs)} — {trips}. That is ALL the sailing "
            f"the tracker shows: never describe the boat or the skipper as training regularly, "
            f"or as \"training solo in Europe\", beyond these dated outings."
        )
    else:
        lines.append(f"OUTINGS ON THE TRACKER {since}: none. The boat has not left the berth on "
                     f"the tracker; never describe it as training or sailing this week.")
    return lines


def build_campaign_status(curated: Dict[str, Any], *, live: Optional[Dict[str, Any]] = None,
                          now: Optional[_dt.datetime] = None,
                          tracker: Optional[Dict[str, Any]] = None) -> str:
    """Render the CAMPAIGN STATUS block from the record. Empty record → ''."""
    if not curated:
        return ""
    now = now or _dt.datetime.now(_dt.timezone.utc)
    if now.tzinfo is None:
        now = now.replace(tzinfo=_dt.timezone.utc)
    today = now.date()
    lines: List[str] = []
    verified = curated.get("last_verified", "unknown")
    lines.append(
        f"Computed {today.isoformat()} from the show's verified campaign record "
        f"(last verified {verified}). Every line carries the date it comes from; "
        f"this week's brief may carry something NEWER, and a newer dated source wins."
    )

    # --- Last known position -------------------------------------------
    if tracker is None and isinstance(live, dict):
        tracker = live.get("tracker") if isinstance(live.get("tracker"), dict) else None
    tracker_lines = _tracker_lines(tracker, today) if tracker else []
    lines.extend(tracker_lines)
    fix = None if tracker_lines else _latest_fix(curated, live, today)
    if fix:
        fd = _parse_date(fix.get("date"))
        age = (today - fd).days if fd else None
        age_txt = f" ({_days_word(age)} ago)" if age is not None else ""
        src = fix.get("source") or _host(fix.get("url", "")) or "team channel"
        text = (fix.get("text") or "").strip()
        lines.append(
            f"LAST KNOWN POSITION / MOVEMENT: {fix.get('date')}{age_txt} — "
            f"{text} — {src}, {fix.get('url', '')}. "
            f"Report THIS with its date unless the brief carries a newer dated fix from the team's "
            f"channels. Never \"unconfirmed\", never \"no update\"; a fix that is {age_txt.strip(' ()') or 'old'} "
            f"is still a fix."
        )
    note = curated.get("position_note") or {}
    if isinstance(note, dict) and note.get("text"):
        lines.append(f"NOTE (as of {note.get('as_of', verified)}): {note['text']} {note.get('url', '')}".rstrip())

    # --- Race state check ----------------------------------------------
    lines.append("RACE STATE CHECK — by today's date, from the official dates on record. "
                 "A race marked FINISHED has a result (below); a headline about its START is old news. "
                 "A race marked NOT STARTED has no result, whatever a preview implies.")
    next_ms: Optional[Dict[str, Any]] = None
    on_record = {r.get("key") for r in (curated.get("results") or []) if r.get("key")}
    for c in curated.get("countdowns") or []:
        when, end = _parse_when(c.get("when")), _parse_when(c.get("end"))
        state = race_state(when, end, now)
        if when is None:
            continue
        if state == "NOT STARTED":
            togo = (when.date() - today).days
            detail = f"{_days_word(togo)} to go"
            if next_ms is None:
                next_ms = {"label": c.get("label", ""), "days": togo, "date": when.date()}
        elif state == "RUNNING":
            detail = f"started {_days_word((today - when.date()).days)} ago"
            if end:
                detail += f", window closes {end.date().isoformat()}"
        else:
            ref = end.date() if end else when.date()
            detail = f"ended {_days_word((today - ref).days)} ago"
        entered = (f" {_entered_word(c.get('emira_entered'), c.get('emira_entry_text', ''))}."
                   if "emira_entered" in c else "")
        pending = ""
        if state == "FINISHED" and c.get("results_key") and c["results_key"] not in on_record:
            pending = (" RESULT NOT YET ON RECORD — do not state a winner or a placing unless a this-week"
                       " source reports it, attributed.")
        lines.append(f"- {c.get('label', '')} ({_fmt(when.date())}): {state} — {detail}.{entered}{pending}")

    # --- Results on record -----------------------------------------------
    results = curated.get("results") or []
    if results:
        lines.append("RESULTS ON RECORD (these races are over; cite them as results, never as news of a start):")
        for r in results:
            podium = r.get("podium") or []
            rows = "; ".join(
                f"{p.get('pos')}. {p.get('boat', '')} — {p.get('skipper', '')}"
                + (f" ({p.get('note')})" if p.get("note") else "")
                for p in podium[:MAX_RESULT_ROWS]
            )
            lines.append(f"- {r.get('event', '')} [{r.get('dates', '')}]: {rows}. Source: {r.get('url', '')}")

    # --- Route du Rhum entry ---------------------------------------------
    entry = curated.get("rhum_entry") or {}
    if isinstance(entry, dict) and entry.get("text"):
        # Oct 4 2026 (operator): the entry status is its own dated record.
        # "Aiming to start" until the skipper is on the OFFICIAL list.
        lines.append(f"ROUTE DU RHUM ENTRY STATUS (as of {entry.get('as_of', verified)}): "
                     f"{entry['text']}")
    rdr = curated.get("rdr_imoca_entries") or {}
    if rdr:
        entries = rdr.get("entries") or []
        official = [e for e in entries if e.get("canada") and e.get("official", True)]
        total = rdr.get("total_registered") or len(entries)
        lines.append(
            f"ROUTE DU RHUM 2026 — IMOCA ENTRY: {total} registered on the class page "
            f"(read {rdr.get('read_date', verified)}); "
            + ("Scott Shawyer IS on the list" if official
               else "Scott Shawyer is NOT on the official entry list")
            + f". Source: {rdr.get('source_url', '')}"
        )

    # --- Countdown ---------------------------------------------------------
    vg = VENDEE_GLOBE_START
    for c in curated.get("countdowns") or []:
        if c.get("id") == "vg_start" and _parse_when(c.get("when")):
            vg = _parse_when(c["when"]).date()
    lines.append(
        f"COUNTDOWN: {_days_word((vg - today).days)} to the Vendée Globe start ({_fmt(vg)})."
        + (f" Next milestone on record: {next_ms['label']} in {_days_word(next_ms['days'])} "
           f"({_fmt(next_ms['date'])})." if next_ms else "")
    )
    return "\n".join(lines)


def _load(path: Path) -> Optional[Dict[str, Any]]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:  # noqa: BLE001
        logger.debug("campaign status: could not read %s: %s", path, exc)
        return None


def campaign_status_from_files(*, now: Optional[_dt.datetime] = None,
                               tracker: Optional[Dict[str, Any]] = None) -> str:
    """The block from the committed record + the live rail; '' on any failure.

    ``tracker`` is a fresh YB summary fetched by the caller at episode
    time; without it the live rail's last tracker read is used.
    """
    try:
        curated = _load(CURATED_PATH) or {}
        live = _load(LIVE_PATH)
        return build_campaign_status(curated, live=live, now=now, tracker=tracker)
    except Exception as exc:  # noqa: BLE001 — never block an episode
        logger.warning("Offshore North campaign status unavailable (non-fatal): %s", exc)
        return ""
