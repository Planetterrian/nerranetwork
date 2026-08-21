"""Drift guard: the daily audit's retry dispatcher must never act on a
stale report.

2026-08-21: review_episodes.py died before writing a fresh
api/daily-review.json (grok-4.6 reviewer timeouts), and
dispatch_audit_retries.py replayed the 2026-08-19 remediation list on
BOTH following days — four full duplicate episode pipelines per day,
YouTube/R2 uploads included, six recovery PRs. A retry decision is only
valid for the day it was computed.
"""

from __future__ import annotations

import datetime
import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def _load_module():
    spec = importlib.util.spec_from_file_location(
        "dispatch_audit_retries", ROOT / "scripts" / "dispatch_audit_retries.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_stale_report_dispatches_nothing(tmp_path, monkeypatch, capsys):
    mod = _load_module()
    review = tmp_path / "api" / "daily-review.json"
    review.parent.mkdir(parents=True)
    review.write_text(json.dumps({
        "date": "2026-08-19",
        "remediation": {"auto_retry_shows": ["fascinating_frontiers"]},
    }))
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("GH_TOKEN", "test-token")

    calls = []
    monkeypatch.setattr(mod.subprocess, "run",
                        lambda *a, **k: calls.append(a) or None)
    mod.main()
    out = capsys.readouterr().out
    assert calls == [], "stale report must never dispatch retries"
    assert "stale" in out


def test_fresh_report_still_dispatches(tmp_path, monkeypatch):
    mod = _load_module()
    today = datetime.datetime.now(datetime.timezone.utc).date().isoformat()
    review = tmp_path / "api" / "daily-review.json"
    review.parent.mkdir(parents=True)
    review.write_text(json.dumps({
        "date": today,
        "remediation": {"auto_retry_shows": ["fascinating_frontiers"]},
    }))
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("GH_TOKEN", "test-token")

    calls = []

    class _Result:
        stdout = ""
        stderr = ""

    def _fake_run(cmd, **kwargs):
        calls.append(list(cmd))
        return _Result()

    monkeypatch.setattr(mod.subprocess, "run", _fake_run)
    mod.main()
    dispatched = [c for c in calls if c[:3] == ["gh", "workflow", "run"]]
    assert len(dispatched) == 1, "fresh report must still dispatch"


def test_committed_stale_list_is_neutralized():
    """The stale 2026-08-19 list that caused the replay must stay cleared
    until a fresh audit rewrites the file."""
    data = json.loads((ROOT / "api" / "daily-review.json").read_text())
    if data.get("date") == "2026-08-19":
        assert data.get("remediation", {}).get("auto_retry_shows") == []
