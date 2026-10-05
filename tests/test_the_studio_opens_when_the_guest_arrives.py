"""Oct 5 2026 (Jon Cheney). A GitHub Actions outage left his studio locked at
the start time and the page told him he was early until he gave up. Browser
interviews are now staged ahead and the Worker opens the room when the guest
arrives; on the day nothing waits on GitHub."""
from __future__ import annotations

import datetime as dt
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "pipelines" / "voices"))
WORKER = (ROOT / "workers" / "voices" / "src" / "index.ts").read_text(encoding="utf-8")
PAGE = (ROOT / "age-of-ai-studio.html").read_text(encoding="utf-8")


def _fake(monkeypatch, scheduled_in_min, host_mode=False, runs=()):
    import fire_interviews as fi
    now = dt.datetime(2026, 10, 5, 12, 0, tzinfo=dt.timezone.utc)
    iv = {"id": "iv1", "application_id": "a1", "status": "briefed", "call_mode": "webrtc",
          "host_mode": host_mode, "show": "age_of_ai", "reminder_sent_at": "x",
          "scheduled_at": (now + dt.timedelta(minutes=scheduled_in_min)).isoformat()}
    inserted, emails = [], []

    def sel(table, q):
        if table == "interviews":
            return [iv]
        if table == "interview_runs":
            return list(runs)
        if table == "guest_applications":
            return [{"id": "a1", "name": "Jon Cheney", "phone": "+18018502182", "show": "age_of_ai"}]
        if table == "interview_briefs":
            return [{"likely_questions": []}]
        return []
    monkeypatch.setattr(fi, "_now", lambda: now)
    monkeypatch.setattr(fi, "sb_select", sel)
    monkeypatch.setattr(fi, "sb_insert", lambda t, row: inserted.append(row) or {"id": "r1"})
    monkeypatch.setattr(fi, "sb_update", lambda *a, **k: None)
    monkeypatch.setattr(fi, "compile_mira_prompt", lambda *a: "prompt")
    monkeypatch.setattr(fi, "send_guest_reminder", lambda *a, **k: emails.append(a))
    monkeypatch.setattr(fi, "notify_operator", lambda *a, **k: None)
    monkeypatch.setattr(fi, "notify_host", lambda *a, **k: None)
    monkeypatch.setenv("VOXIMPLANT_CALLER_ID", "+16047575450")
    return fi, inserted, emails


def test_a_browser_interview_is_staged_a_day_ahead(monkeypatch):
    fi, inserted, _ = _fake(monkeypatch, scheduled_in_min=20 * 60)
    assert fi.fire_due_interviews() == 0
    assert inserted and inserted[0]["status"] == "staged"


def test_a_cohosted_interview_keeps_the_old_window(monkeypatch):
    fi, inserted, _ = _fake(monkeypatch, scheduled_in_min=20 * 60, host_mode=True)
    fi.fire_due_interviews()
    assert inserted == []
    fi, inserted, _ = _fake(monkeypatch, scheduled_in_min=10, host_mode=True)
    fi.fire_due_interviews()
    assert inserted and inserted[0]["status"] == "awaiting_guest"


def test_a_staged_run_is_not_staged_twice(monkeypatch):
    fi, inserted, _ = _fake(monkeypatch, scheduled_in_min=60, runs=[{"id": "r0", "status": "staged"}])
    fi.fire_due_interviews()
    assert inserted == []


def test_the_worker_opens_the_staged_run_when_someone_arrives():
    assert 'latest.status === "staged" && openNow' in WORKER
    assert "interview_runs?id=eq.${latest.id}&status=eq.staged" in WORKER
    assert "STUDIO_OPENS_BEFORE_MS = 15 * 60 * 1000" in WORKER


def test_no_prepared_run_asks_for_one_and_tells_patrick_once():
    assert "async function rescueStudio" in WORKER
    assert "is in the studio and it has not opened" in WORKER
    assert "if (!iv.studio_alert_at)" in WORKER


def test_an_on_time_guest_is_never_told_they_are_early():
    assert "Mira is getting the studio ready for you." in PAGE
    assert "s.opening ||" in PAGE


def test_the_no_show_sweep_covers_staged_runs():
    src = (ROOT / "pipelines" / "voices" / "fire_interviews.py").read_text(encoding="utf-8")
    assert 'not in ("awaiting_guest", "staged")' in src
