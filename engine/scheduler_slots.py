"""The scheduler Worker's slot table — committed source vs. what is deployed.

The Worker (``workers/scheduler/src/index.ts``) dispatches each show's run at
its slot minute. Its SLOTS table is committed here, but what FIRES is
whatever was last ``wrangler deploy``-ed, and nothing compared the two: on
2026-09-24 the operator's redeploy came from a checkout that predated the
launch-cohort PR, so the cron string looked right (hour 6 was already
covered) while none of the nine new slots existed on the live Worker. Every
old slot fired on the minute; every new one silently did not.

:func:`worker_slots` parses the committed table (the punctuality test's
regex, moved here so the deploy check reads the same thing). The Worker's
``GET /`` returns ``{"slots": [{"at": "06:16Z", "show": ..., "filter": ...}]}``;
:func:`slots_from_status` parses that, and :func:`slot_drift` names what
differs. ``scripts/check_scheduler_deploy.py`` is the nightly instrument.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Dict, Optional, Tuple

ROOT = Path(__file__).resolve().parent.parent
WORKER_SOURCE = ROOT / "workers" / "scheduler" / "src" / "index.ts"

Slot = Tuple[int, int, Optional[str]]  # (utc hour, utc minute, day filter)

_SLOT_RE = re.compile(r'\[(\d+),\s*(\d+),\s*"(\w+)",\s*(?:"(\w+)"|null)\]')
_AT_RE = re.compile(r"^(\d{2}):(\d{2})Z?$")


def worker_slots(source: Optional[str] = None) -> Dict[str, Slot]:
    """``{show: (hour, minute, filter|None)}`` from the committed TS source."""
    text = source if source is not None else WORKER_SOURCE.read_text(encoding="utf-8")
    out: Dict[str, Slot] = {}
    for m in _SLOT_RE.finditer(text):
        hour, minute, show, day_filter = m.groups()
        out[show] = (int(hour), int(minute), day_filter)
    return out


def slots_from_status(payload: dict) -> Dict[str, Slot]:
    """The same shape from the Worker's ``GET /`` JSON. Malformed rows are
    skipped; a payload with no ``slots`` list yields ``{}``."""
    out: Dict[str, Slot] = {}
    for row in (payload or {}).get("slots") or []:
        if not isinstance(row, dict):
            continue
        m = _AT_RE.match(str(row.get("at", "")).strip())
        show = str(row.get("show", "")).strip()
        if not m or not show:
            continue
        flt = row.get("filter")
        out[show] = (int(m.group(1)), int(m.group(2)), str(flt) if flt else None)
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
