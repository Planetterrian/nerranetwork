"""Nerra Personal's private feeds are watched (Nov 6 2026).

Every run of the private batch workflow failed on a 401 from Nov 2 to Nov 6
2026 (a rotated PERSONAL_ADMIN_TOKEN reached the Worker but not the batch
repo). No member's feed gained an episode for five days and every check in
this repo stayed green, because each one reads the PUBLIC feeds only.
"""

from __future__ import annotations

import datetime as dt
import importlib.util
import json
import re
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

ROOT = Path(__file__).resolve().parent.parent
EASTERN = ZoneInfo("America/New_York")


def _load(name: str, rel: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / rel)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


check = _load("check_personal_feeds", "scripts/check_personal_feeds.py")


class FakeResp:
    def __init__(self, status, body=None):
        self.status_code = status
        self._body = body

    def json(self):
        if self._body is None:
            raise ValueError("no json")
        return self._body


class FakeSession:
    def __init__(self, routes):
        self.routes = routes
        self.calls = []

    def get(self, url, headers=None, timeout=None):
        self.calls.append((url, headers))
        for frag, resp in self.routes.items():
            if frag in url:
                return resp
        raise ConnectionError("no route")


HEALTHY = {"ok": True, "today": "2026-11-06", "members": 2, "built_today": 2,
           "behind": 0, "never_built": 0, "newest_edition": "2026-11-06",
           "oldest_latest_edition": "2026-11-06", "max_days_behind": 0}
STALE = {**HEALTHY, "built_today": 0, "behind": 2,
         "newest_edition": "2026-11-01", "oldest_latest_edition": "2026-11-01",
         "max_days_behind": 5}


def _eastern(hour):
    return dt.datetime(2026, 11, 6, hour, 0, tzinfo=EASTERN)


class TestVerdict:
    def test_the_nov_2_outage_pages(self):
        msg = check.verdict(STALE, _eastern(11))
        assert msg and "2 of 2" in msg and "2026-11-01" in msg and "5 day" in msg

    def test_healthy_feeds_do_not_page(self):
        assert check.verdict(HEALTHY, _eastern(11)) is None

    def test_only_today_missing_waits_for_the_build_window(self):
        only_today = {**HEALTHY, "built_today": 1, "behind": 1,
                      "oldest_latest_edition": "2026-11-05", "max_days_behind": 1}
        assert check.verdict(only_today, _eastern(6)) is None
        assert check.verdict(only_today, _eastern(11))

    def test_a_whole_missed_day_pages_even_early(self):
        assert check.verdict(STALE, _eastern(6))

    def test_unreadable_counts_and_no_members_never_page(self):
        assert check.verdict({"error": "HTTP 500"}, _eastern(11)) is None
        assert check.verdict({**HEALTHY, "members": 0}, _eastern(11)) is None


class TestFetch:
    def test_a_401_is_named_not_counted(self, monkeypatch):
        monkeypatch.setenv("PERSONAL_DEMAND_TOKEN", "tok\n")
        s = FakeSession({"personal-feed-health": FakeResp(401)})
        out = check.fetch_feed_health(s)
        assert "401" in out["error"]
        # the trailing newline a pasted secret carries never reaches the bearer
        assert s.calls[0][1]["Authorization"] == "Bearer tok"

    def test_no_token_is_unverified_never_zero(self, monkeypatch):
        monkeypatch.delenv("PERSONAL_DEMAND_TOKEN", raising=False)
        monkeypatch.delenv("PERSONAL_ADMIN_TOKEN", raising=False)
        assert "error" in check.fetch_feed_health(FakeSession({}))

    def test_undeployed_route_says_deploy(self, monkeypatch):
        monkeypatch.setenv("PERSONAL_DEMAND_TOKEN", "tok")
        out = check.fetch_feed_health(FakeSession({"personal-feed-health": FakeResp(404)}))
        assert "deploy" in out["error"]


class TestBatchRuns:
    def test_streak_and_last_success(self):
        runs = [
            {"status": "in_progress", "conclusion": None, "created_at": "x"},
            {"status": "completed", "conclusion": "failure", "created_at": "2026-11-06T11:47:39Z", "html_url": "u"},
            {"status": "completed", "conclusion": "failure", "created_at": "2026-11-05T22:15:00Z"},
            {"status": "completed", "conclusion": "success", "created_at": "2026-11-01T20:48:21Z"},
        ]
        out = check.summarise_runs(runs)
        assert out["failures_in_a_row"] == 2
        assert out["last_success_at"] == "2026-11-01T20:48:21Z"
        assert out["latest_conclusion"] == "failure"

    def test_no_success_in_window_is_unknown_not_never(self):
        out = check.summarise_runs([{"status": "completed", "conclusion": "failure"}])
        assert out["last_success_at"] is None


class TestMain:
    def _run(self, monkeypatch, tmp_path, routes, hour=11):
        monkeypatch.setenv("PERSONAL_DEMAND_TOKEN", "tok")
        monkeypatch.setenv("PERSONAL_BATCH_DISPATCH_TOKEN", "pat")
        import requests
        monkeypatch.setattr(requests, "Session", lambda: FakeSession(routes))

        class Clock(dt.datetime):
            @classmethod
            def now(cls, tz=None):
                return dt.datetime(2026, 11, 6, hour + 5, 0, tzinfo=dt.timezone.utc)
        monkeypatch.setattr(check.dt, "datetime", Clock)
        out = tmp_path / "health.json"
        code = check.main(["--out", str(out)])
        return code, json.loads(out.read_text())

    def test_stale_feeds_fail_the_step_and_record_public_counts_only(
            self, monkeypatch, tmp_path, capsys):
        runs = {"workflow_runs": [
            {"status": "completed", "conclusion": "failure",
             "created_at": "2026-11-06T11:47:39Z", "html_url": "https://github.com/run/1"}]}
        code, rec = self._run(monkeypatch, tmp_path, {
            "personal-feed-health": FakeResp(200, STALE),
            "actions/workflows": FakeResp(200, runs)})
        assert code == 1
        assert rec["stale"] is True and rec["feeds"]["behind"] == 2
        assert rec["batch"]["failures_in_a_row"] == 1
        err = capsys.readouterr().out
        assert "::error::" in err and "PERSONAL_ADMIN_TOKEN" in err

    def test_unreachable_worker_is_a_warning_and_null(self, monkeypatch, tmp_path, capsys):
        code, rec = self._run(monkeypatch, tmp_path, {})
        assert code == 0
        assert rec["feeds"] is None and rec["stale"] is None
        assert "UNVERIFIED" in capsys.readouterr().out


class TestWiring:
    def test_the_daily_audit_runs_the_check_and_commits_its_record(self):
        wf = (ROOT / ".github/workflows/daily-audit.yml").read_text()
        assert "scripts/check_personal_feeds.py" in wf
        step = wf.split("Nerra Personal private feeds have today's edition")[1].split("- name:")[0]
        assert "if: always()" in step
        assert "PERSONAL_DEMAND_TOKEN" in step
        # never the full admin token: the public repo holds only the counts token
        assert "secrets.PERSONAL_ADMIN_TOKEN" not in step
        commit = wf.split("Persist Audit Artifacts")[1]
        assert "api/personal_feed_health.json" in commit

    def test_the_worker_routes_the_endpoint(self):
        idx = (ROOT / "workers/gallery/src/index.ts").read_text()
        assert '"GET /api/admin/personal-feed-health"' in idx

    def test_the_builder_names_a_401_and_strips_the_token(self):
        src = (ROOT / "scripts/build_personal_feeds.py").read_text()
        body = src.split("def load_specs")[1].split("\ndef ")[0]
        assert 'os.environ.get("PERSONAL_ADMIN_TOKEN", "").strip()' in body
        assert "resp.status_code == 401" in body
        assert body.index("resp.status_code == 401") < body.index("raise_for_status")

    def test_the_record_carries_no_member_identity(self):
        src = (ROOT / "scripts/check_personal_feeds.py").read_text()
        for key in check.FEED_KEYS:
            assert not re.search(r"token|email|name|city", key)
