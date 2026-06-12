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
    """Top-of-hour and half-hour marks are the most contended schedule
    slots; every show cron must sit at :07/:37."""
    crons = re.findall(r"- cron: '(\d+) ", _WF)
    assert crons, "no crons parsed"
    assert set(crons) <= {"7", "37"}, f"on-peak cron minutes present: {crons}"


def test_worker_slots_match_cron_map():
    cron_map = _cron_map()
    slots = _worker_slots()
    assert len(cron_map) == 12, f"CRON_MAP parse drift: {sorted(cron_map)}"
    assert slots == cron_map, (
        "workers/scheduler SLOTS desynced from run-show.yml CRON_MAP:\n"
        f"  worker-only/changed: { {k: v for k, v in slots.items() if cron_map.get(k) != v} }\n"
        f"  cron-map-only/changed: { {k: v for k, v in cron_map.items() if slots.get(k) != v} }"
    )


def test_worker_trigger_covers_all_slots():
    toml = (_ROOT / "workers" / "scheduler" / "wrangler.toml").read_text(encoding="utf-8")
    assert '"7,37 6-11 * * *"' in toml


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
