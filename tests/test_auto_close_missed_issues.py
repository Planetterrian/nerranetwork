"""Tests for ``review_episodes.close_resolved_missed_episode_issues``.

Operator caught (May 7 2026) the daily-review queue accumulating
"missed episode" issues that the next morning's run had already
resolved. Issue #330 today was the trigger: 6 shows flagged at 12:40
UTC, root cause fixed in PRs #331 + #333, but the issue stayed open
until manually closed.

These tests pin the auto-close logic so:

  1. The title regex matches the actual `create_github_issue` template.
  2. ``_has_per_episode_findings`` correctly distinguishes missed-only
     issues (auto-closeable) from issues with real per-episode bugs
     (NOT auto-closeable).
  3. ``_MISSED_SHOW_RE`` extracts the slug from each missed-show line.
  4. The end-to-end ``close_resolved_missed_episode_issues`` only fires
     ``gh issue close`` when every conservative gate passes.
"""

from __future__ import annotations

import datetime
import json
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from review_episodes import (
    _DAILY_TITLE_RE,
    _MISSED_SHOW_RE,
    _has_per_episode_findings,
    close_resolved_missed_episode_issues,
)


# ---------------------------------------------------------------------------
# Title pattern
# ---------------------------------------------------------------------------


class TestDailyTitleRe:

    def test_matches_critical_template(self):
        title = "Daily Review 2026-05-07: 6 critical issue(s) across 6 show(s)"
        m = _DAILY_TITLE_RE.match(title)
        assert m is not None
        assert m.group(1) == "2026-05-07"

    def test_matches_warning_template(self):
        title = "Daily Review 2026-05-06: 2 warning(s) across 1 show(s)"
        m = _DAILY_TITLE_RE.match(title)
        assert m is not None
        assert m.group(1) == "2026-05-06"

    def test_does_not_match_unrelated_titles(self):
        for title in (
            "Bug: thing broke",
            "Daily Review without trailing details",
            "Random Daily Review 2026-05-07: details",
        ):
            assert _DAILY_TITLE_RE.match(title) is None


# ---------------------------------------------------------------------------
# Missed-show extractor
# ---------------------------------------------------------------------------


class TestMissedShowRe:

    def test_extracts_slug_from_real_body_line(self):
        body = (
            "### Missed Episodes\n\n"
            "These shows were scheduled to produce an episode today but "
            "no output was found:\n\n"
            "- **Tesla Shorts Time** (`tesla`): Tesla Shorts Time was "
            "scheduled to produce an episode on 2026-05-07 (schedule: daily) "
            "but no output files were found in digests/tesla_shorts_time/...\n"
            "- **Omni View** (`omni_view`): Omni View was scheduled...\n"
        )
        slugs = _MISSED_SHOW_RE.findall(body)
        assert slugs == ["tesla", "omni_view"]

    def test_does_not_match_arbitrary_backticks(self):
        """The pattern requires the bold-name + parenthesised-backtick
        structure, not just any backtick mention. A per-episode finding
        that mentions ``digests/<slug>/`` shouldn't be confused for a
        missed-show line."""
        body = "Some episode mentioned `digests/tesla/` in passing.\n"
        assert _MISSED_SHOW_RE.findall(body) == []


# ---------------------------------------------------------------------------
# Per-episode findings detector
# ---------------------------------------------------------------------------


class TestHasPerEpisodeFindings:

    def test_empty_table_returns_false(self):
        body = (
            "### Episodes Reviewed\n\n"
            "| Show | Episode | Issues |\n"
            "|------|---------|--------|\n"
        )
        assert _has_per_episode_findings(body) is False

    def test_table_with_data_row_returns_true(self):
        body = (
            "### Episodes Reviewed\n\n"
            "| Show | Episode | Issues |\n"
            "|------|---------|--------|\n"
            "| Tesla | 466 | 1 critical |\n"
        )
        assert _has_per_episode_findings(body) is True

    def test_no_episodes_section_returns_false(self):
        body = "### Missed Episodes\n\n- **Tesla** (`tesla`): missed.\n"
        assert _has_per_episode_findings(body) is False


# ---------------------------------------------------------------------------
# End-to-end close
# ---------------------------------------------------------------------------


def _stub_run(stdout: str = "", returncode: int = 0):
    """Helper to build a ``subprocess.run`` stub that returns *stdout*."""
    def _run(*args, **kwargs):
        result = MagicMock()
        result.stdout = stdout
        result.stderr = ""
        result.returncode = returncode
        return result
    return _run


def _missed_only_issue_body(slugs: list[str]) -> str:
    """Build a body matching create_github_issue's missed-only template."""
    lines = ["### Missed Episodes\n"]
    for slug in slugs:
        lines.append(
            f"- **{slug.replace('_',' ').title()}** (`{slug}`): missed.\n"
        )
    lines.append("\n### Episodes Reviewed\n\n")
    lines.append("| Show | Episode | Issues |\n")
    lines.append("|------|---------|--------|\n")
    return "".join(lines)


class TestCloseResolvedIssues:

    def test_closes_when_all_missed_shows_have_replayed(
        self, tmp_path, monkeypatch,
    ):
        """The happy path: yesterday's issue listed Tesla as missed,
        today the digest dir has a Tesla file for that date, so the
        issue closes."""
        # Build a fake project root with a Tesla output file for 2026-05-07.
        tesla_dir = tmp_path / "digests" / "tesla_shorts_time"
        tesla_dir.mkdir(parents=True)
        (tesla_dir / "Tesla_Shorts_Time_Pod_Ep466_20260507.md").write_text("body")

        monkeypatch.setattr("review_episodes.PROJECT_ROOT", tmp_path)

        issues_payload = json.dumps([{
            "number": 330,
            "title": "Daily Review 2026-05-07: 1 critical issue(s) across 1 show(s)",
            "body": _missed_only_issue_body(["tesla"]),
            "createdAt": "2026-05-07T12:40:14Z",
        }])

        close_calls: list[list[str]] = []

        def _fake_run(cmd, **kwargs):
            close_calls.append(list(cmd))
            result = MagicMock()
            result.returncode = 0
            result.stderr = ""
            if cmd[1] == "issue" and cmd[2] == "list":
                result.stdout = issues_payload
            else:
                result.stdout = ""
            return result

        monkeypatch.setattr("review_episodes.subprocess.run", _fake_run)

        # Today is the day AFTER the issue date so the auto-close gate
        # ("strictly before today") passes.
        closed = close_resolved_missed_episode_issues(datetime.date(2026, 5, 8))
        assert closed == 1

        # gh issue close was invoked with --reason completed.
        close_cmd = next(c for c in close_calls if c[1:3] == ["issue", "close"])
        assert "330" in close_cmd
        assert "--reason" in close_cmd
        assert close_cmd[close_cmd.index("--reason") + 1] == "completed"

    def test_does_not_close_when_show_has_not_replayed(
        self, tmp_path, monkeypatch,
    ):
        """If the digest directory still doesn't have a file for the
        date in the issue title, leave the issue open."""
        # Empty digests dir — no Tesla output for 2026-05-07.
        (tmp_path / "digests" / "tesla_shorts_time").mkdir(parents=True)
        monkeypatch.setattr("review_episodes.PROJECT_ROOT", tmp_path)

        issues_payload = json.dumps([{
            "number": 330,
            "title": "Daily Review 2026-05-07: 1 critical issue(s) across 1 show(s)",
            "body": _missed_only_issue_body(["tesla"]),
            "createdAt": "2026-05-07T12:40:14Z",
        }])
        close_calls: list[list[str]] = []

        def _fake_run(cmd, **kwargs):
            close_calls.append(list(cmd))
            result = MagicMock()
            result.returncode = 0
            result.stderr = ""
            result.stdout = issues_payload if cmd[1:3] == ["issue", "list"] else ""
            return result

        monkeypatch.setattr("review_episodes.subprocess.run", _fake_run)

        closed = close_resolved_missed_episode_issues(datetime.date(2026, 5, 8))
        assert closed == 0
        # No close call was made.
        assert not any(c[1:3] == ["issue", "close"] for c in close_calls)

    def test_does_not_close_todays_issue(self, tmp_path, monkeypatch):
        """Even if all shows have replayed, today's issue stays open
        (the review run is happening NOW; closing it would be racy)."""
        tesla_dir = tmp_path / "digests" / "tesla_shorts_time"
        tesla_dir.mkdir(parents=True)
        (tesla_dir / "Tesla_Shorts_Time_Pod_Ep466_20260507.md").write_text("body")
        monkeypatch.setattr("review_episodes.PROJECT_ROOT", tmp_path)

        issues_payload = json.dumps([{
            "number": 330,
            "title": "Daily Review 2026-05-07: 1 critical issue(s) across 1 show(s)",
            "body": _missed_only_issue_body(["tesla"]),
            "createdAt": "2026-05-07T12:40:14Z",
        }])
        close_calls: list[list[str]] = []

        def _fake_run(cmd, **kwargs):
            close_calls.append(list(cmd))
            result = MagicMock()
            result.returncode = 0
            result.stderr = ""
            result.stdout = issues_payload if cmd[1:3] == ["issue", "list"] else ""
            return result

        monkeypatch.setattr("review_episodes.subprocess.run", _fake_run)

        # ``today`` matches the issue date — must NOT close.
        closed = close_resolved_missed_episode_issues(datetime.date(2026, 5, 7))
        assert closed == 0
        assert not any(c[1:3] == ["issue", "close"] for c in close_calls)

    def test_does_not_close_when_per_episode_findings_present(
        self, tmp_path, monkeypatch,
    ):
        """An issue with per-episode findings might have real bugs
        unrelated to the missed-episode replay. Leave it for human
        triage."""
        tesla_dir = tmp_path / "digests" / "tesla_shorts_time"
        tesla_dir.mkdir(parents=True)
        (tesla_dir / "Tesla_Shorts_Time_Pod_Ep466_20260507.md").write_text("body")
        monkeypatch.setattr("review_episodes.PROJECT_ROOT", tmp_path)

        body = (
            "### Missed Episodes\n\n"
            "- **Tesla Shorts Time** (`tesla`): missed.\n\n"
            "### Episodes Reviewed\n\n"
            "| Show | Episode | Issues |\n"
            "|------|---------|--------|\n"
            "| Omni View | 42 | 1 critical |\n"
        )
        issues_payload = json.dumps([{
            "number": 330,
            "title": "Daily Review 2026-05-07: 1 critical issue(s) across 1 show(s)",
            "body": body,
            "createdAt": "2026-05-07T12:40:14Z",
        }])
        close_calls: list[list[str]] = []

        def _fake_run(cmd, **kwargs):
            close_calls.append(list(cmd))
            result = MagicMock()
            result.returncode = 0
            result.stderr = ""
            result.stdout = issues_payload if cmd[1:3] == ["issue", "list"] else ""
            return result

        monkeypatch.setattr("review_episodes.subprocess.run", _fake_run)

        closed = close_resolved_missed_episode_issues(datetime.date(2026, 5, 8))
        assert closed == 0
        assert not any(c[1:3] == ["issue", "close"] for c in close_calls)

    def test_handles_missing_gh_cli_gracefully(self, monkeypatch):
        """If gh isn't installed (local dev), the helper exits 0
        without raising — the daily review must keep working."""
        def _fake_run(*args, **kwargs):
            raise FileNotFoundError("gh not found")

        monkeypatch.setattr("review_episodes.subprocess.run", _fake_run)
        closed = close_resolved_missed_episode_issues(datetime.date(2026, 5, 8))
        assert closed == 0
