"""Unit tests for shows/hooks/modern_investing.py.

Covers the new NASDAQ-benchmark / sector / lesson-tag helpers added in
the Chunk 1+2 implementation. yfinance is fully stubbed — no network.
"""
from __future__ import annotations

import datetime
import json
from pathlib import Path
from unittest.mock import patch

import pytest

from shows.hooks import modern_investing as m


# ---------------------------------------------------------------------------
# _classify_sector
# ---------------------------------------------------------------------------

class TestClassifySector:
    def test_known_precious_metals(self):
        assert m._classify_sector("FSM", "", "TSX") == "precious_metals"
        assert m._classify_sector("WRLG", "", "TSX") == "precious_metals"

    def test_known_financials(self):
        assert m._classify_sector("SOFI", "", "NASDAQ") == "financials"

    def test_known_tech(self):
        assert m._classify_sector("WDC", "", "NASDAQ") == "tech"

    def test_known_consumer(self):
        assert m._classify_sector("TSLA", "", "NASDAQ") == "consumer"
        assert m._classify_sector("LUCID", "", "NASDAQ") == "consumer"

    def test_keyword_fallback_energy(self):
        assert m._classify_sector("XYZ", "Oil & gas refiner margin recovery", "TSX") == "energy"

    def test_keyword_fallback_healthcare(self):
        assert m._classify_sector("XYZ", "Novel biotech therapy in Phase 3", "NASDAQ") == "healthcare"

    def test_unknown_returns_other(self):
        assert m._classify_sector("ZZZZZ", "some vague catalyst", "") == "other"

    def test_empty_symbol(self):
        assert m._classify_sector("", "Gold miner earnings beat", "") == "precious_metals"


# ---------------------------------------------------------------------------
# _extract_lesson_tags
# ---------------------------------------------------------------------------

class TestExtractLessonTags:
    def test_hyphen_normalisation(self):
        tags = m._extract_lesson_tags("The bid-ask spread widened on news.")
        assert "bid_ask_spread" in tags

    def test_underscore_normalisation(self):
        tags = m._extract_lesson_tags("Today's lesson was bid_ask_spread risk.")
        assert "bid_ask_spread" in tags

    def test_multiple_tags(self):
        tags = m._extract_lesson_tags(
            "Momentum entry after catalyst confirmation beat sector rotation plays."
        )
        assert set(tags) >= {"momentum_entry", "catalyst_confirmation", "sector_rotation"}

    def test_empty_returns_empty(self):
        assert m._extract_lesson_tags("") == []

    def test_dedups(self):
        # Same tag mentioned twice — should appear once
        tags = m._extract_lesson_tags("bid-ask spread again, bid ask spread twice")
        assert tags.count("bid_ask_spread") == 1

    def test_no_false_positives(self):
        tags = m._extract_lesson_tags("Purely unrelated commentary about the weather.")
        assert tags == []


# ---------------------------------------------------------------------------
# _load_tracker / _ensure_schema
# ---------------------------------------------------------------------------

class TestTrackerSchema:
    def test_fresh_tracker_has_all_new_keys(self):
        t = m._fresh_tracker()
        assert "benchmark" in t
        assert "alpha" in t
        assert "sectors" in t
        assert "monthly_snapshots" in t
        assert t["metadata"]["benchmark_symbol"] == "^IXIC"
        assert t["metadata"]["nasdaq_inception_close"] is None

    def test_ensure_schema_upgrades_old_tracker(self):
        old = {
            "metadata": {"created": "2026-01-02"},
            "summary": {},
            "trades": [{"symbol": "LGD", "pnl_pct": 1.2}],
        }
        m._ensure_schema(old)
        assert old["metadata"]["benchmark_symbol"] == "^IXIC"
        assert old["metadata"]["inception_date"] == "2026-01-02"
        assert "benchmark" in old
        assert "alpha" in old
        assert old["trades"][0]["symbol"] == "LGD"  # preserved

    def test_load_tracker_upgrades_in_place(self, tmp_path: Path):
        p = tmp_path / "investment_tracker.json"
        p.write_text(json.dumps({
            "metadata": {"created": "2026-03-20"},
            "summary": {"total_trades": 3},
            "trades": [],
        }))
        tracker = m._load_tracker(p)
        assert tracker["metadata"]["benchmark_symbol"] == "^IXIC"
        assert tracker["alpha"]["monthly"] == {}

    def test_load_tracker_missing_file_returns_fresh(self, tmp_path: Path):
        tracker = m._load_tracker(tmp_path / "nope.json")
        assert "benchmark" in tracker
        assert tracker["trades"] == []


# ---------------------------------------------------------------------------
# Portfolio-return helpers
# ---------------------------------------------------------------------------

class TestPortfolioReturn:
    def test_no_trades_returns_zero(self):
        assert m._portfolio_return_pct(m._fresh_tracker()) == 0.0

    def test_single_trade_equals_pct(self):
        tracker = m._fresh_tracker()
        tracker["trades"].append({
            "status": "closed",
            "date": "2026-04-01",
            "pnl_pct": 5.0,
            "pnl_dollars": 50.0,
        })
        # 50 / 1000 = 5%
        assert m._portfolio_return_pct(tracker) == 5.0

    def test_multiple_trades_averaged_over_capital(self):
        tracker = m._fresh_tracker()
        tracker["trades"].extend([
            {"status": "closed", "date": "2026-01-10", "pnl_pct": 10.0, "pnl_dollars": 100.0},
            {"status": "closed", "date": "2026-02-10", "pnl_pct": -4.0, "pnl_dollars": -40.0},
        ])
        # (100 - 40) / (2 * 1000) = 3%
        assert m._portfolio_return_pct(tracker) == 3.0

    def test_ytd_filters_by_year(self):
        tracker = m._fresh_tracker()
        tracker["trades"].extend([
            {"status": "closed", "date": "2025-12-01", "pnl_pct": 10.0, "pnl_dollars": 100.0},
            {"status": "closed", "date": f"{datetime.date.today().year}-02-10",
             "pnl_pct": 2.0, "pnl_dollars": 20.0},
        ])
        # Only the current-year trade counts: 20 / 1000 = 2%
        assert m._portfolio_return_ytd_pct(tracker) == 2.0


# ---------------------------------------------------------------------------
# _compute_benchmark_state
# ---------------------------------------------------------------------------

class TestComputeBenchmarkState:
    def _stub_closes(self, inception=15000.0, ytd=16000.0, current=18000.0):
        """Return a function that maps date -> close based on the seed dates."""
        def _stub(for_date=None):
            today = datetime.date.today()
            if for_date is None:
                return current
            # Jan 2 of current year -> ytd; anything in 2025 -> inception
            if for_date.year < today.year:
                return inception
            if for_date.month == 1 and for_date.day <= 5:
                return ytd
            return current
        return _stub

    def test_alpha_math_trailing_nasdaq(self):
        tracker = m._fresh_tracker()
        tracker["metadata"]["inception_date"] = "2025-06-01"
        # Portfolio: 1 trade, +2% YTD and ITD
        tracker["trades"].append({
            "status": "closed",
            "date": f"{datetime.date.today().year}-03-15",
            "pnl_pct": 2.0,
            "pnl_dollars": 20.0,
        })
        stub = self._stub_closes(inception=15000.0, ytd=16000.0, current=18000.0)
        with patch.object(m, "_fetch_nasdaq_close", side_effect=stub):
            m._compute_benchmark_state(tracker)
        # NASDAQ ITD: (18000-15000)/15000 = 20.0% ; YTD: (18000-16000)/16000 = 12.5%
        assert tracker["benchmark"]["inception_to_date_pct"] == 20.0
        assert tracker["benchmark"]["ytd_pct"] == 12.5
        # Portfolio 2% ITD and 2% YTD — alpha is negative
        assert tracker["alpha"]["inception_to_date_pct"] == pytest.approx(2.0 - 20.0, abs=0.01)
        assert tracker["alpha"]["ytd_pct"] == pytest.approx(2.0 - 12.5, abs=0.01)

    def test_alpha_math_beating_nasdaq(self):
        tracker = m._fresh_tracker()
        tracker["metadata"]["inception_date"] = "2025-06-01"
        tracker["trades"].append({
            "status": "closed",
            "date": f"{datetime.date.today().year}-03-15",
            "pnl_pct": 25.0,
            "pnl_dollars": 250.0,
        })
        stub = self._stub_closes(inception=15000.0, ytd=16000.0, current=18000.0)
        with patch.object(m, "_fetch_nasdaq_close", side_effect=stub):
            m._compute_benchmark_state(tracker)
        # Portfolio 25% vs NASDAQ ITD 20% -> +5 alpha
        assert tracker["alpha"]["inception_to_date_pct"] == pytest.approx(5.0, abs=0.01)

    def test_ytd_rollover_refreshes_baseline(self):
        tracker = m._fresh_tracker()
        # Pretend we were last anchored in an earlier year
        tracker["metadata"]["nasdaq_ytd_year"] = datetime.date.today().year - 1
        tracker["metadata"]["nasdaq_ytd_start_close"] = 9999.0

        stub = self._stub_closes(inception=15000.0, ytd=16000.0, current=18000.0)
        with patch.object(m, "_fetch_nasdaq_close", side_effect=stub):
            m._compute_benchmark_state(tracker)
        # Rollover should have refreshed the YTD baseline to this year's Jan 2 close.
        assert tracker["metadata"]["nasdaq_ytd_year"] == datetime.date.today().year
        assert tracker["metadata"]["nasdaq_ytd_start_close"] == 16000.0

    def test_handles_missing_yfinance_gracefully(self):
        tracker = m._fresh_tracker()
        with patch.object(m, "_fetch_nasdaq_close", return_value=None):
            m._compute_benchmark_state(tracker)
        # No crash; no phantom numbers.
        assert tracker["benchmark"]["current_close"] is None


# ---------------------------------------------------------------------------
# _annotate_trade_with_nasdaq
# ---------------------------------------------------------------------------

class TestAnnotateTradeWithNasdaq:
    def test_weekly_alpha_math(self):
        trade = {
            "symbol": "WDC",
            "date": "2026-03-23",
            "trade_type": "weekly",
            "pnl_pct": 4.44,
        }
        # Stub so entry = 15000, exit = 15300 -> NASDAQ +2.0
        def _stub(for_date=None):
            if for_date and for_date.weekday() == 4:  # Friday exit
                return 15300.0
            return 15000.0
        with patch.object(m, "_fetch_nasdaq_close", side_effect=_stub):
            m._annotate_trade_with_nasdaq(trade)
        assert trade["nasdaq_entry"] == 15000.0
        assert trade["nasdaq_exit"] == 15300.0
        assert trade["nasdaq_return_pct"] == 2.0
        # 4.44 - 2.0 = 2.44 alpha
        assert trade["alpha_pct"] == pytest.approx(2.44, abs=0.01)

    def test_null_pnl_yields_null_alpha(self):
        trade = {"symbol": "X", "date": "2026-03-23", "trade_type": "weekly", "pnl_pct": None}
        with patch.object(m, "_fetch_nasdaq_close", return_value=15000.0):
            m._annotate_trade_with_nasdaq(trade)
        assert trade["alpha_pct"] is None

    def test_missing_data_leaves_fields_none(self):
        trade = {"symbol": "X", "date": "2026-03-23", "trade_type": "weekly", "pnl_pct": 3.0}
        with patch.object(m, "_fetch_nasdaq_close", return_value=None):
            m._annotate_trade_with_nasdaq(trade)
        assert trade["nasdaq_entry"] is None
        assert trade["alpha_pct"] is None


# ---------------------------------------------------------------------------
# _build_benchmark_block
# ---------------------------------------------------------------------------

class TestBuildBenchmarkBlock:
    def test_includes_all_four_numbers(self):
        tracker = m._fresh_tracker()
        tracker["benchmark"] = {
            "current_close": 17500.0,
            "ytd_pct": 10.0,
            "inception_to_date_pct": 22.0,
            "last_updated": "2026-04-16",
        }
        tracker["alpha"] = {"ytd_pct": -3.5, "inception_to_date_pct": -1.0, "monthly": {}}
        block = m._build_benchmark_block(tracker)
        assert "NASDAQ" in block
        assert "17,500" in block
        assert "+10.00%" in block
        assert "-3.50%" in block

    def test_missing_close_yields_fallback_message(self):
        tracker = m._fresh_tracker()
        tracker["benchmark"]["current_close"] = None
        block = m._build_benchmark_block(tracker)
        assert "unavailable" in block.lower()


# ---------------------------------------------------------------------------
# Taught-lessons + stale-tag detection
# ---------------------------------------------------------------------------

class TestTaughtLessons:
    def test_empty_file_returns_fresh_struct(self, tmp_path: Path):
        data = m._load_taught_lessons(tmp_path / "nope.json")
        assert data["lessons"] == {}
        assert data["cooldown_days_default"] == 21

    def test_record_bumps_count_and_date(self, tmp_path: Path):
        data = m._load_taught_lessons(tmp_path / "nope.json")
        m._record_taught_lessons(data, ["bid_ask_spread"], episode_num=22)
        m._record_taught_lessons(data, ["bid_ask_spread"], episode_num=23)
        entry = data["lessons"]["bid_ask_spread"]
        assert entry["count"] == 2
        assert entry["last_episode"] == 23

    def test_save_roundtrip(self, tmp_path: Path):
        path = tmp_path / "taught.json"
        data = m._load_taught_lessons(path)
        m._record_taught_lessons(data, ["momentum_entry"], episode_num=1)
        m._save_taught_lessons(data, path)
        assert path.exists()
        reloaded = m._load_taught_lessons(path)
        assert reloaded["lessons"]["momentum_entry"]["count"] == 1

    def test_stale_tags_inside_cooldown(self, tmp_path: Path):
        data = m._load_taught_lessons(tmp_path / "nope.json")
        m._record_taught_lessons(data, ["bid_ask_spread"], episode_num=22)
        stale = m._stale_lesson_tags(data)
        tags = [t for t, _ in stale]
        assert "bid_ask_spread" in tags

    def test_stale_tags_drops_expired(self):
        # Hand-craft an entry whose last_date is well outside the cooldown.
        # June 2026: cooldowns ESCALATE with teach-count (count=6 →
        # 45 * (1 + 6//3) = 135d window), so the expiry horizon here is
        # 140 days, not the flat 45 the original fixture assumed.
        old_date = (datetime.date.today() - datetime.timedelta(days=140)).isoformat()
        data = {
            "metadata": {"last_updated": "2026-01-01"},
            "cooldown_days_default": 21,
            "lessons": {"bid_ask_spread": {
                "count": 6, "last_episode": 1, "last_date": old_date, "cooldown_days": 45,
            }},
        }
        assert m._stale_lesson_tags(data) == []

    def test_overtaught_lesson_blocked_inside_escalated_window(self):
        # The same count=6 entry at 100 days IS still blocked — the flat
        # window let bid_ask_spread reteach 13 times in 71 episodes.
        old_date = (datetime.date.today() - datetime.timedelta(days=100)).isoformat()
        data = {
            "metadata": {"last_updated": "2026-01-01"},
            "cooldown_days_default": 21,
            "lessons": {"bid_ask_spread": {
                "count": 6, "last_episode": 1, "last_date": old_date, "cooldown_days": 45,
            }},
        }
        assert [t for t, _ in m._stale_lesson_tags(data)] == ["bid_ask_spread"]

    def test_build_block_mentions_stale_tags(self, tmp_path: Path):
        data = m._load_taught_lessons(tmp_path / "nope.json")
        m._record_taught_lessons(data, ["bid_ask_spread"], episode_num=22)
        block = m._build_taught_lessons_block(data)
        assert "bid_ask_spread" in block
        assert "Do NOT" in block or "do not" in block.lower()

    def test_build_block_empty_when_no_cooldown(self, tmp_path: Path):
        data = m._load_taught_lessons(tmp_path / "nope.json")
        block = m._build_taught_lessons_block(data)
        assert "full latitude" in block


# ---------------------------------------------------------------------------
# Lessons-learned ledger
# ---------------------------------------------------------------------------

class TestLessonsLearned:
    def test_append_assigns_sequential_id(self, tmp_path: Path):
        data = m._load_lessons_learned(tmp_path / "nope.json")
        e1 = m._append_lesson_learned(data, observation="obs1", adjustment="do x", episode_num=1)
        e2 = m._append_lesson_learned(data, observation="obs2", adjustment="do y", episode_num=2)
        assert e1["id"] == "LL-001"
        assert e2["id"] == "LL-002"
        assert len(data["entries"]) == 2

    def test_build_block_lists_active_only(self, tmp_path: Path):
        data = m._load_lessons_learned(tmp_path / "nope.json")
        m._append_lesson_learned(data, observation="obs1", adjustment="adj1", episode_num=1)
        retired = m._append_lesson_learned(data, observation="obs2", adjustment="adj2", episode_num=2)
        retired["status"] = "retired"
        block = m._build_lessons_learned_block(data)
        assert "adj1" in block
        assert "adj2" not in block

    def test_extract_rule_block_with_valid_rule(self):
        digest = (
            "Earlier content.\n"
            "**Lesson Learned:** The trade was trimmed on the upside miss. "
            "Rule: Take profits at target even when momentum looks intact.\n"
            "**Lesson Tags:** risk_management\n"
        )
        result = m._extract_lesson_learned_from_digest(digest)
        assert result is not None
        obs, adj = result
        assert "trimmed on the upside" in obs
        assert adj.startswith("Take profits at target")

    def test_extract_returns_none_without_rule(self):
        digest = "**Lesson Learned:** Lost money. Don't do that.\n"
        assert m._extract_lesson_learned_from_digest(digest) is None

    def test_extract_returns_none_on_empty(self):
        assert m._extract_lesson_learned_from_digest("") is None


# ---------------------------------------------------------------------------
# Sector warning + narrative callback
# ---------------------------------------------------------------------------

class TestSectorWarning:
    def test_concentration_threshold_fires(self):
        tracker = m._fresh_tracker()
        for i in range(4):
            tracker["trades"].append({
                "status": "closed", "date": f"2026-04-{10 + i:02d}",
                "symbol": "FSM", "sector": "precious_metals", "pnl_dollars": 0,
            })
        for i in range(2):
            tracker["trades"].append({
                "status": "closed", "date": f"2026-04-{14 + i:02d}",
                "symbol": "WDC", "sector": "tech", "pnl_dollars": 0,
            })
        tracker["sectors"] = m._compute_sector_exposure(tracker)
        block = m._build_sector_warning_block(tracker)
        assert "precious_metals" in block
        assert "MUST AVOID" in block

    def test_balanced_portfolio_no_warning(self):
        tracker = m._fresh_tracker()
        for i, sector in enumerate(["tech", "financials", "energy", "consumer"]):
            tracker["trades"].append({
                "status": "closed", "date": f"2026-04-{10 + i:02d}",
                "symbol": "X", "sector": sector, "pnl_dollars": 0,
            })
        tracker["sectors"] = m._compute_sector_exposure(tracker)
        block = m._build_sector_warning_block(tracker)
        assert "MUST AVOID" not in block

    def test_empty_portfolio_says_so(self):
        block = m._build_sector_warning_block(m._fresh_tracker())
        assert "No sector concentration" in block


class TestSegmentRotation:
    def _write_library(self, tmp_path: Path, ids: list[str]) -> Path:
        """Write a tiny segment library with the given ids."""
        p = tmp_path / "segments.json"
        p.write_text(json.dumps({
            "show": "MIT",
            "segments": [
                {"id": sid, "title": f"Title for {sid}", "prompt_template": f"Teach {sid}."}
                for sid in ids
            ],
        }), encoding="utf-8")
        return p

    def test_picks_first_unused(self, tmp_path: Path):
        library = self._write_library(tmp_path, ["a", "b", "c"])
        tracker = m._fresh_tracker()
        sid, hint = m._pick_deep_dive_segment(tracker, library)
        assert sid == "a"
        assert "Title for a" in hint[0]

    def test_skips_recent(self, tmp_path: Path):
        library = self._write_library(tmp_path, ["a", "b", "c"])
        tracker = m._fresh_tracker()
        tracker["used_segment_ids"] = ["a", "b"]
        sid, _ = m._pick_deep_dive_segment(tracker, library)
        assert sid == "c"

    def test_all_recent_falls_back_to_oldest(self, tmp_path: Path):
        library = self._write_library(tmp_path, ["a", "b"])
        tracker = m._fresh_tracker()
        # Oldest-first list: "b" was used first (index 0), "a" most recent.
        tracker["used_segment_ids"] = ["b", "a"]
        sid, _ = m._pick_deep_dive_segment(tracker, library)
        assert sid == "b"  # least-recently-used = oldest in the list

    def test_missing_library_returns_none(self):
        tracker = m._fresh_tracker()
        sid, hint = m._pick_deep_dive_segment(tracker, Path("/nope/library.json"))
        assert sid is None
        assert hint is None

    def test_record_caps_at_60(self):
        tracker = {"used_segment_ids": [f"s{i}" for i in range(60)]}
        m._record_segment_used(tracker, "new")
        assert len(tracker["used_segment_ids"]) == 60
        assert tracker["used_segment_ids"][-1] == "new"
        assert "s0" not in tracker["used_segment_ids"]

    def test_hint_block_fallback_when_no_hint(self):
        assert "No evergreen" in m._build_deep_dive_hint_block(None)
        assert "No evergreen" in m._build_deep_dive_hint_block(("", ""))


class TestNarrativeCallback:
    def test_picks_trade_in_window(self):
        tracker = m._fresh_tracker()
        three_weeks_ago = (datetime.date.today() - datetime.timedelta(days=21)).isoformat()
        tracker["trades"].append({
            "status": "closed", "date": three_weeks_ago,
            "symbol": "WDC", "sector": "tech", "strategy": "cloud-driven growth",
            "pnl_pct": 4.44, "episode_num": 7,
        })
        callback = m._build_narrative_callback(tracker)
        assert "WDC" in callback
        assert "21 days ago" in callback

    def test_no_candidates_yields_skip_message(self):
        tracker = m._fresh_tracker()
        tracker["trades"].append({
            "status": "closed", "date": datetime.date.today().isoformat(),
            "symbol": "X", "sector": "tech", "pnl_pct": 1.0, "episode_num": 1,
        })
        callback = m._build_narrative_callback(tracker)
        assert "skip" in callback.lower()
