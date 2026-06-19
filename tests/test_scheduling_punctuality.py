"""Drift guards for the June 2026 scheduling-punctuality pass.

GitHub delivers `schedule` events 1-6 h late (Tesla's 11:00 cron observed
starting 13:54). The fix is three-layered: off-peak cron minutes
(:07/:37), an exact-time Cloudflare Worker dispatcher
(workers/scheduler), and a same-day duplicate guard in the gate so the
two drivers never double-publish. These tests pin all three AND that the
Worker's SLOTS table stays in sync with the workflow's CRON_MAP.
"""

from __future__ import annotations

import re
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
_WF = (_ROOT / ".github" / "workflows" / "run-show.yml").read_text(encoding="utf-8")
_TS = (_ROOT / "workers" / "scheduler" / "src" / "index.ts").read_text(encoding="utf-8")


def _cron_map() -> dict:
    """Parse CRON_MAP entries: "M H ..." -> (show, day_filter|None)."""
    entries = {}
    for m in re.finditer(
        r'"(\d+) (\d+) [^"]*":\s*\("(\w+)",\s*(?:"(\w+)"|None)\)', _WF,
    ):
        minute, hour, show, day_filter = m.groups()
        entries[show] = (int(hour), int(minute), day_filter)
    return entries


def _worker_slots() -> dict:
    entries = {}
    for m in re.finditer(
        r'\[(\d+),\s*(\d+),\s*"(\w+)",\s*(?:"(\w+)"|null)\]', _TS,
    ):
        hour, minute, show, day_filter = m.groups()
        entries[show] = (int(hour), int(minute), day_filter)
    return entries


def test_cron_minutes_off_peak():
    """Crons are staggered to avoid bunching on the same minute. The
    original :07/:37 design avoided top-of-hour contention but capped at
    2 slots/hour (13 shows, 12 hours min). For 10 daily shows in 3 hours,
    :01/:16/:31/:46 spacing is used instead (same anti-bunch principle,
    tighter packing). GitHub fallback crons are no longer on the
    historically-off-peak :07/:37 marks, but the Cloudflare Worker (primary,
    minute-accurate dispatch) is unaffected and the duplicate guard still
    prevents double-publishing."""
    crons = re.findall(r"- cron: '(\d+) ", _WF)
    assert crons, "no crons parsed"
    assert set(crons) <= {"1", "7", "16", "31", "37", "46"}, f"unexpected cron minutes: {crons}"


def test_worker_slots_match_cron_map():
    cron_map = _cron_map()
    slots = _worker_slots()
    assert len(cron_map) == 13, f"CRON_MAP parse drift: {sorted(cron_map)}"
    assert slots == cron_map, (
        "workers/scheduler SLOTS desynced from run-show.yml CRON_MAP:\n"
        f"  worker-only/changed: { {k: v for k, v in slots.items() if cron_map.get(k) != v} }\n"
        f"  cron-map-only/changed: { {k: v for k, v in cron_map.items() if slots.get(k) != v} }"
    )


def test_worker_trigger_covers_all_slots():
    toml = (_ROOT / "workers" / "scheduler" / "wrangler.toml").read_text(encoding="utf-8")
    assert '"1,7,16,31,37,46 6-12 * * *"' in toml


def test_gate_has_duplicate_guard():
    assert "Duplicate guard" in _WF
    assert "Auto-generated: {slug} {today_str}" in _WF
    # The guard must be best-effort: API failure → run the show anyway.
    assert "proceeding without it" in _WF


def test_run_job_has_post_concurrency_duplicate_recheck():
    """The gate's guard runs at queue time and can be stale by the time
    the per-show concurrency lock releases (FF double-published June 12
    2026). The run job must re-check after the lock + fresh checkout."""
    assert "Post-concurrency duplicate re-check" in _WF
    assert "Duplicate re-check" in _WF
