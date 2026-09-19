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


def _entered_word(flag: Any) -> str:
    if flag is True:
        return "EMIRA IV ENTERED"
    if flag is False:
        return "EMIRA IV not entered / did not sail"
    return "EMIRA IV entry unconfirmed"


def _latest_fix(curated: Dict[str, Any], live: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """The newest dated fix: the operator-verified log, or the live rail's
    derived fix when it is newer (the same rule the page applies)."""
    log = [p for p in (curated.get("position_log") or []) if _parse_date(p.get("date"))]
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


def build_campaign_status(curated: Dict[str, Any], *, live: Optional[Dict[str, Any]] = None,
                          now: Optional[_dt.datetime] = None) -> str:
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
    fix = _latest_fix(curated, live)
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
        entered = f" {_entered_word(c.get('emira_entered'))}." if "emira_entered" in c else ""
        lines.append(f"- {c.get('label', '')} ({_fmt(when.date())}): {state} — {detail}.{entered}")

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
    rdr = curated.get("rdr_imoca_entries") or {}
    if rdr:
        entries = rdr.get("entries") or []
        canada = [e for e in entries if e.get("canada")]
        total = rdr.get("total_registered") or len(entries)
        lines.append(
            f"ROUTE DU RHUM 2026 — IMOCA ENTRY: {total} registered on the class page "
            f"(read {rdr.get('read_date', verified)}); "
            + ("Scott Shawyer IS on the list" if canada else "Scott Shawyer is NOT on the list read")
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


def campaign_status_from_files(*, now: Optional[_dt.datetime] = None) -> str:
    """The block from the committed record + the live rail; '' on any failure."""
    try:
        curated = _load(CURATED_PATH) or {}
        live = _load(LIVE_PATH)
        return build_campaign_status(curated, live=live, now=now)
    except Exception as exc:  # noqa: BLE001 — never block an episode
        logger.warning("Offshore North campaign status unavailable (non-fatal): %s", exc)
        return ""
