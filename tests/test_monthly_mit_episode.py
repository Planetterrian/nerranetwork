"""Tests for scripts/run_monthly_mit_episode.py.

Covers the last-trading-day calendar logic and the pure-function MIT
section builders. The full ``run()`` pipeline (LLM/TTS/R2/RSS) is
exercised in dry-run mode only — the network-dependent steps are
skipped there.
"""
from __future__ import annotations

import datetime as _dt
import json
import sys
from pathlib import Path

import pytest

# Make ``scripts/`` importable for the tests.
_REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_REPO_ROOT / "scripts"))

import run_monthly_mit_episode as monthly  # type: ignore


# ---------------------------------------------------------------------------
# TTS call-signature guard (regression for the speak(output_path=...) crash)
# ---------------------------------------------------------------------------

class TestTtsCallSignature:
    """The monthly episode used to call the legacy ElevenLabs ``speak()`` with
    stale kwargs (``output_path=``, ``model=``) and no ``api_key``, crashing the
    monthly-report workflow. Guard that it calls the canonical ``synthesize()``
    dispatcher with only real parameters."""

    _SCRIPT = _REPO_ROOT / "scripts" / "run_monthly_mit_episode.py"

    def test_uses_synthesize_not_legacy_speak(self):
        src = self._SCRIPT.read_text(encoding="utf-8")
        assert "from engine.tts import synthesize" in src
        assert "output_path=voice_mp3" not in src  # the old buggy kwarg

    def test_synthesize_call_kwargs_are_all_valid(self):
        import ast
        import inspect
        from engine.tts import synthesize

        valid = set(inspect.signature(synthesize).parameters)
        tree = ast.parse(self._SCRIPT.read_text(encoding="utf-8"))
        calls = [
            n for n in ast.walk(tree)
            if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
            and n.func.id == "synthesize"
        ]
        assert calls, "expected a synthesize() call in the monthly episode script"
        for call in calls:
            for kw in call.keywords:
                if kw.arg is None:  # **kwargs spread — skip
                    continue
                assert kw.arg in valid, (
                    f"synthesize() has no parameter {kw.arg!r} — stale TTS call"
                )


# ---------------------------------------------------------------------------
# is_last_trading_day_of_month
# ---------------------------------------------------------------------------

class TestLastTradingDay:
    def test_last_weekday_of_month_true(self):
        # April 2026: last weekday is Thursday the 30th (no holiday).
        assert monthly.is_last_trading_day_of_month(_dt.date(2026, 4, 30)) is True

    def test_earlier_weekday_in_month_false(self):
        assert monthly.is_last_trading_day_of_month(_dt.date(2026, 4, 15)) is False

    def test_weekend_false(self):
        # Saturday 31 Jan 2026.
        assert monthly.is_last_trading_day_of_month(_dt.date(2026, 1, 31)) is False

    def test_month_ends_on_weekend_rolls_back_to_friday(self):
        # May 2026 ends on Sunday May 31. Memorial Day (Mon May 25) is a
        # holiday. Last trading day should be Friday May 29.
        assert monthly.is_last_trading_day_of_month(_dt.date(2026, 5, 29)) is True
        assert monthly.is_last_trading_day_of_month(_dt.date(2026, 5, 30)) is False
        assert monthly.is_last_trading_day_of_month(_dt.date(2026, 5, 31)) is False

    def test_thanksgiving_week_rolls_past_thursday(self):
        # November 2026 ends on Monday Nov 30. Thanksgiving = Thu Nov 26.
        # Last trading day = Mon Nov 30 (no holiday; weekday).
        assert monthly.is_last_trading_day_of_month(_dt.date(2026, 11, 30)) is True

    def test_december_ends_on_christmas_rolls_back(self):
        # December 2026 ends on Thursday Dec 31.  Christmas Day (Fri Dec 25)
        # is a holiday; Dec 31 is a trading Thursday — that's the last.
        assert monthly.is_last_trading_day_of_month(_dt.date(2026, 12, 31)) is True
        # Dec 25 itself is NOT a trading day.
        assert monthly.is_last_trading_day_of_month(_dt.date(2026, 12, 25)) is False


# ---------------------------------------------------------------------------
# _previous_month_window
# ---------------------------------------------------------------------------

class TestPreviousMonthWindow:
    def test_mid_month_returns_previous(self):
        assert monthly._previous_month_window(_dt.date(2026, 4, 17)) == (3, 2026)

    def test_january_rolls_to_december_of_previous_year(self):
        assert monthly._previous_month_window(_dt.date(2026, 1, 5)) == (12, 2025)


# ---------------------------------------------------------------------------
# build_monthly_snapshot
# ---------------------------------------------------------------------------

class TestBuildMonthlySnapshot:
    def test_filters_by_month(self):
        tracker = {
            "trades": [
                {"status": "closed", "date": "2026-03-15", "pnl_pct": 2.0,
                 "pnl_dollars": 20.0, "nasdaq_return_pct": 1.0, "alpha_pct": 1.0},
                {"status": "closed", "date": "2026-04-05", "pnl_pct": 5.0,
                 "pnl_dollars": 50.0, "nasdaq_return_pct": 2.0, "alpha_pct": 3.0},
                {"status": "closed", "date": "2026-04-12", "pnl_pct": -1.0,
                 "pnl_dollars": -10.0, "nasdaq_return_pct": 0.0, "alpha_pct": -1.0},
            ]
        }
        snap = monthly.build_monthly_snapshot(tracker, month=4, year=2026)
        assert snap["month"] == "2026-04"
        assert snap["trades"] == 2
        assert snap["portfolio_pct"] == 2.0
        assert snap["nasdaq_pct"] == 1.0
        assert snap["alpha_pct"] == 1.0
        assert snap["portfolio_pnl"] == 40.0
        assert snap["win_rate"] == 50.0

    def test_empty_month_returns_zeros(self):
        snap = monthly.build_monthly_snapshot({"trades": []}, month=4, year=2026)
        assert snap["trades"] == 0
        assert snap["win_rate"] == 0.0
        assert snap["portfolio_pct"] == 0.0


# ---------------------------------------------------------------------------
# build_sector_heatmap
# ---------------------------------------------------------------------------

class TestBuildSectorHeatmap:
    def test_groups_and_sorts_by_trade_count(self):
        trades = [
            {"sector": "tech", "pnl_pct": 5.0, "pnl_dollars": 50.0},
            {"sector": "tech", "pnl_pct": 3.0, "pnl_dollars": 30.0},
            {"sector": "precious_metals", "pnl_pct": -2.0, "pnl_dollars": -20.0},
        ]
        rows = monthly.build_sector_heatmap(trades)
        # tech has 2 trades so it comes first
        assert rows[0][0] == "tech"
        assert rows[0][1] == 2
        assert rows[0][2] == 4.0  # mean
        assert rows[0][3] == 80.0  # sum

    def test_missing_sector_bucketed_as_other(self):
        rows = monthly.build_sector_heatmap([{"pnl_pct": 1.0, "pnl_dollars": 10.0}])
        assert rows[0][0] == "other"


# ---------------------------------------------------------------------------
# build_mit_sections — markdown assembly
# ---------------------------------------------------------------------------

class TestBuildMitSections:
    def test_markdown_contains_required_headers(self):
        tracker = {"trades": [
            {"status": "closed", "date": "2026-04-10", "sector": "tech",
             "pnl_pct": 4.0, "pnl_dollars": 40.0,
             "nasdaq_return_pct": 2.0, "alpha_pct": 2.0, "episode_num": 1},
        ]}
        lessons = {"entries": [
            {"id": "LL-100", "date": "2026-04-15", "status": "active",
             "observation": "Lost on spread.", "adjustment": "Use limit orders."},
        ]}
        md = monthly.build_mit_sections(tracker, lessons, month=4, year=2026)
        assert "## Monthly NASDAQ Showdown" in md
        assert "## Sector Heatmap" in md
        assert "## Rules Adopted This Month" in md
        assert "## Rules Retired This Month" in md
        assert "## Areas of Improvement for Next Month" in md
        # The rule adopted this month must be listed
        assert "LL-100" in md
        # Sector heatmap row present
        assert "tech" in md

    def test_adopted_vs_carry_forward_rules_differ_from_retired(self):
        tracker = {"trades": []}
        lessons = {"entries": [
            {"id": "LL-1", "date": "2026-04-10", "status": "active",
             "observation": "A", "adjustment": "adj1"},
            {"id": "LL-2", "date": "2026-03-10", "status": "active",
             "observation": "B", "adjustment": "adj2"},  # not adopted this month
            {"id": "LL-3", "date": "2026-04-22", "status": "retired",
             "observation": "C", "adjustment": "adj3"},
        ]}
        md = monthly.build_mit_sections(tracker, lessons, month=4, year=2026)
        # Only LL-1 was adopted THIS month (April)
        adopted_block = md.split("## Rules Adopted This Month")[1].split("## Rules Retired")[0]
        assert "LL-1" in adopted_block
        assert "LL-2" not in adopted_block
        # LL-3 was retired this month
        retired_block = md.split("## Rules Retired This Month")[1].split("## Areas of Improvement")[0]
        assert "LL-3" in retired_block


# ---------------------------------------------------------------------------
# _next_monthly_episode_num
# ---------------------------------------------------------------------------

class TestNextEpisodeNum:
    def test_uses_max_plus_one(self, tmp_path: Path):
        rss_file = tmp_path / "nonexistent.rss"
        tracker = {"trades": [{"episode_num": 21}, {"episode_num": 22}]}
        ledger = {"entries": []}
        assert monthly._next_monthly_episode_num(tracker, ledger, rss_file) == 23

    def test_respects_ledger(self, tmp_path: Path):
        tracker = {"trades": []}
        ledger = {"entries": [{"episode_num": 50}]}
        rss_file = tmp_path / "nope.rss"
        assert monthly._next_monthly_episode_num(tracker, ledger, rss_file) == 51

    def test_parses_rss(self, tmp_path: Path):
        rss_file = tmp_path / "feed.rss"
        rss_file.write_text(
            "<rss><channel>"
            "<item><itunes:episode>30</itunes:episode></item>"
            "<item><itunes:episode>25</itunes:episode></item>"
            "</channel></rss>",
            encoding="utf-8",
        )
        tracker = {"trades": [{"episode_num": 10}]}
        ledger = {"entries": []}
        assert monthly._next_monthly_episode_num(tracker, ledger, rss_file) == 31


# ---------------------------------------------------------------------------
# run() in dry-run mode — end-to-end content generation only
# ---------------------------------------------------------------------------

class TestRunDryRun:
    def test_dry_run_writes_markdown_and_snapshot(self, tmp_path: Path, monkeypatch):
        # Seed a temporary repo with the shape run() expects.
        shows = tmp_path / "shows"
        prompts = shows / "prompts"
        mit = tmp_path / "digests" / "modern_investing"
        shows.mkdir()
        prompts.mkdir()
        mit.mkdir(parents=True)

        # Minimal MIT YAML + _defaults.yaml.
        (shows / "_defaults.yaml").write_text(
            "llm:\n  provider: xai\n  model: grok-4.20-non-reasoning\n"
            "  digest_temperature: 0.5\n  podcast_temperature: 0.7\n"
            "tts:\n  provider: elevenlabs\n  voice_id: V1\n"
            "  stability: 0.5\n  similarity_boost: 0.75\n  style: 0.0\n",
            encoding="utf-8",
        )
        (shows / "modern_investing.yaml").write_text(
            "name: Modern Investing Techniques\nslug: modern_investing\n"
            "publishing:\n  host_name: Patrick\n  rss_file: mi.rss\n"
            "  rss_title: MIT\n  rss_link: https://example.com\n"
            "episode:\n  output_dir: digests/modern_investing\n",
            encoding="utf-8",
        )

        # Minimal tracker + lessons.
        (mit / "investment_tracker.json").write_text(json.dumps({
            "metadata": {},
            "summary": {},
            "trades": [{
                "episode_num": 1, "date": "2026-03-10", "status": "closed",
                "sector": "tech", "pnl_pct": 3.0, "pnl_dollars": 30.0,
                "nasdaq_return_pct": 1.0, "alpha_pct": 2.0,
            }],
        }), encoding="utf-8")
        (mit / "lessons_learned.json").write_text(json.dumps({
            "entries": [],
        }), encoding="utf-8")

        # Redirect PROJECT_ROOT so run() looks at the temp tree.
        monkeypatch.setattr(monthly, "PROJECT_ROOT", tmp_path)
        # synthesize_monthly_report would try to hit content_lake; stub it.
        monkeypatch.setattr(monthly, "synthesize_monthly_report",
                            lambda slug, m, y: f"# Base report for {slug} {y}-{m:02d}\n")

        rc = monthly.run(month=3, year=2026, dry_run=True)
        assert rc == 0
        out_md = mit / "Modern_Investing_Monthly_2026-03.md"
        assert out_md.exists()
        body = out_md.read_text(encoding="utf-8")
        assert "## Monthly NASDAQ Showdown" in body
        # Snapshot appended to the tracker.
        tracker = json.loads((mit / "investment_tracker.json").read_text(encoding="utf-8"))
        assert any(s.get("month") == "2026-03" for s in tracker.get("monthly_snapshots", []))
