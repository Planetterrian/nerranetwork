"""The scheduler Worker's slot table — committed source vs. what is deployed.

The Worker (``workers/scheduler/src/index.ts``) dispatches each show's run at
its slot minute. Its SLOTS table is committed here, but what FIRES is
whatever was last ``wrangler deploy``-ed, and nothing compared the two: on
2026-09-24 the operator's redeploy came from a checkout that predated the
launch-cohort PR, so the cron string looked right (hour 6 was already
covered) while none of the nine new slots existed on the live Worker. Every
old slot fired on the minute; every new one silently did not.

:func:`worker_slots` parses the committed table (the punctuality test's
regex, moved here so the deploy check reads the same thing). Since Oct 17 2026
every row is EASTERN wall time (``SLOT_TZ`` in the Worker, ``America/New_York``
here) so Nerra Daily is out by 7:00 AM New York and the clock changes move
nothing. The Worker's ``GET /`` returns
``{"slots": [{"at": "05:45", "tz": "America/New_York", "show": ..., "filter": ...}]}``;
:func:`slots_from_status` parses that, and :func:`slot_drift` names what
differs. A Worker deployed before the Eastern schedule answers rows like
``{"at": "09:16Z"}`` (UTC); those are NOT read as Eastern slots — they are
counted by :func:`status_clocks` so the deploy check can say the live Worker
is on the old clock instead of reporting every slot as moved.
``scripts/check_scheduler_deploy.py`` is the nightly instrument.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Dict, Optional, Tuple

ROOT = Path(__file__).resolve().parent.parent
WORKER_SOURCE = ROOT / "workers" / "scheduler" / "src" / "index.ts"

#: The Worker's SLOT_TZ — every committed and live slot is on this clock.
SLOT_TZ = "America/New_York"

Slot = Tuple[int, int, Optional[str]]  # (Eastern hour, Eastern minute, day filter)

_SLOT_RE = re.compile(r'\[(\d+),\s*(\d+),\s*"(\w+)",\s*(?:"(\w+)"|null)\]')
_SLOT_TZ_RE = re.compile(r'const SLOT_TZ = "([^"]+)"')
_AT_RE = re.compile(r"^(\d{2}):(\d{2})(Z?)$")


def worker_slots(source: Optional[str] = None) -> Dict[str, Slot]:
    """``{show: (ET hour, ET minute, filter|None)}`` from the committed TS
    source (Eastern wall time — the Worker's ``SLOT_TZ``)."""
    text = source if source is not None else WORKER_SOURCE.read_text(encoding="utf-8")
    out: Dict[str, Slot] = {}
    for m in _SLOT_RE.finditer(text):
        hour, minute, show, day_filter = m.groups()
        out[show] = (int(hour), int(minute), day_filter)
    return out


def worker_slot_tz(source: Optional[str] = None) -> Optional[str]:
    """The committed Worker's ``SLOT_TZ`` (``None`` when it declares none)."""
    text = source if source is not None else WORKER_SOURCE.read_text(encoding="utf-8")
    m = _SLOT_TZ_RE.search(text)
    return m.group(1) if m else None


def _row_clock(row: dict, at_match: "re.Match[str]") -> str:
    """The clock a status row is on: its ``tz`` field, else ``UTC`` for the
    pre-Oct-17 ``"HH:MMZ"`` shape."""
    tz = str(row.get("tz") or "").strip()
    if tz:
        return tz
    return "UTC" if at_match.group(3) else ""


def _status_rows(payload: dict):
    for row in (payload or {}).get("slots") or []:
        if not isinstance(row, dict):
            continue
        m = _AT_RE.match(str(row.get("at", "")).strip())
        show = str(row.get("show", "")).strip()
        if not m or not show:
            continue
        yield row, m, show


def slots_from_status(payload: dict, tz: str = SLOT_TZ) -> Dict[str, Slot]:
    """The same shape from the Worker's ``GET /`` JSON, for rows on *tz*
    (Eastern). Malformed rows, and rows on another clock (a pre-Eastern
    deploy's ``"09:16Z"``), are skipped; a payload with no ``slots`` list
    yields ``{}``."""
    out: Dict[str, Slot] = {}
    for row, m, show in _status_rows(payload):
        if _row_clock(row, m) != tz:
            continue
        flt = row.get("filter")
        out[show] = (int(m.group(1)), int(m.group(2)), str(flt) if flt else None)
    return out


def status_clocks(payload: dict) -> Dict[str, int]:
    """``{clock: row count}`` across the status payload's well-formed rows —
    ``{"UTC": 28}`` means the live Worker predates the Eastern schedule."""
    out: Dict[str, int] = {}
    for row, m, _show in _status_rows(payload):
        clock = _row_clock(row, m) or "unlabelled"
        out[clock] = out.get(clock, 0) + 1
    return out


def slot_drift(committed: Dict[str, Slot], live: Dict[str, Slot]) -> Dict[str, dict]:
    """``{"missing_live": {...}, "extra_live": {...}, "changed": {...}}`` —
    empty dicts all round means the deployed Worker matches the source."""
    missing = {k: v for k, v in committed.items() if k not in live}
    extra = {k: v for k, v in live.items() if k not in committed}
    changed = {
        k: {"committed": committed[k], "live": live[k]}
        for k in committed if k in live and committed[k] != live[k]
    }
    return {"missing_live": missing, "extra_live": extra, "changed": changed}


def has_drift(drift: Dict[str, dict]) -> bool:
    return any(bool(v) for v in drift.values())
