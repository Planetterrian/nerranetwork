"""Drift guards for the July 3 2026 Modern Investing benchmark-integrity pass.

The operator wants to connect this show to a live account and beat the
NASDAQ on a regular basis — which makes the simulated track record's
integrity the product. This pass fixed the measurement layer:

* **Flash-trade alpha was fake**: ``_annotate_trade_with_nasdaq`` compared
  the same NASDAQ close to itself for same-day trades, so every flash
  trade shipped ``nasdaq_return_pct: 0.0`` and "alpha" was just the raw
  return. The benchmark now uses the index OPEN→CLOSE over the trade's
  own bar window.
* **Weekly holds were backdated**: a hold picked mid-week was credited
  from MONDAY's open — hindsight gain the pick could never have captured
  (Ep35 AMD picked Wednesday, +13.36% from Monday's open). Entry bars now
  start at the pick date.
* **Wrong-instrument pricing**: TSX picks were priced via the bare US
  symbol (Ep50 "CNR — Canadian National Railway (TSX:CNR)" was priced as
  Core Natural Resources NYSE, booking +8.66% on the wrong company). TSX
  picks now resolve ``.TO``/``.V`` first, and a pick-time probe records
  the resolved symbol + a reference price.
* **NaN closes narrated as breakeven**: DELL Ep57 / HIMS Ep63 stayed
  ``closed`` with ``pnl: NaN`` after the July 2 phantom-trade migration —
  2 of the 3 spoken "breakeven" trades were data failures. A self-healing
  migration voids any closed trade with a non-finite result.
* **``--test`` runs mutated the live tracker**: post_generate runs before
  run_show's test-mode exit, so a test invocation appended a REAL trade.
  Hooks honor ``NERRA_HOOKS_READONLY=1``.
* **Lessons ledger echo chamber**: 65 "active" rules, ~35 near-copies of
  one volume-confirmation rule — the LLM paraphrased the rules it was
  shown and the extractor appended each paraphrase as new. Dedup on
  append; diverse selection in the prompt block.
"""

from __future__ import annotations

import datetime
import json
import math
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from shows.hooks import modern_investing as mi  # noqa: E402


# ---------------------------------------------------------------------------
# Symbol resolution (Ep50 CNR wrong-company class)
# ---------------------------------------------------------------------------

class TestSymbolResolution:
    def test_tsx_prefers_toronto_listing(self):
        assert mi._yf_symbol_candidates("CNR", "TSX") == ["CNR.TO", "CNR"]

    def test_tsx_v_prefers_venture_listing(self):
        assert mi._yf_symbol_candidates("WRLG", "TSX-V") == [
            "WRLG.V", "WRLG.TO", "WRLG"]

    def test_us_markets_use_bare_symbol(self):
        assert mi._yf_symbol_candidates("NVDA", "NASDAQ") == ["NVDA"]
        assert mi._yf_symbol_candidates("UNH", "NYSE") == ["UNH"]

    def test_unknown_market_uses_bare_symbol(self):
        assert mi._yf_symbol_candidates("BTC", "UNKNOWN") == ["BTC"]

    def test_resolved_symbol_wins_for_existing_trade(self):
        trade = {"symbol": "CNR", "market": "TSX", "resolved_symbol": "CNR.TO"}
        assert mi._trade_symbol_candidates(trade) == ["CNR.TO"]

    def test_probe_stamps_resolution_and_reference(self):
        trade = {"symbol": "CNR", "market": "TSX"}
        bars = [(datetime.date(2026, 7, 2), 130.0, 131.5)]
        with patch.object(mi, "_fetch_history_bars", return_value=bars):
            assert mi._probe_pick(trade) is True
        assert trade["resolved_symbol"] == "CNR.TO"
        assert trade["pick_reference_price"] == 131.5

    def test_probe_warns_loudly_on_bogus_ticker(self, caplog):
        import logging
        trade = {"symbol": "ION", "market": "UNKNOWN"}
        with patch.object(mi, "_fetch_history_bars", return_value=None):
            with caplog.at_level(logging.WARNING, logger=mi.logger.name):
                assert mi._probe_pick(trade) is False
        assert any("PICK VALIDATION FAILED" in r.getMessage()
                   for r in caplog.records)


# ---------------------------------------------------------------------------
# Bar selection (entry-date integrity)
# ---------------------------------------------------------------------------

_BARS = [
    (datetime.date(2026, 6, 26), 100.0, 101.0),  # Fri
    (datetime.date(2026, 6, 29), 102.0, 103.0),  # Mon
    (datetime.date(2026, 6, 30), 103.5, 104.0),  # Tue
    (datetime.date(2026, 7, 1), 104.5, 105.0),   # Wed
    (datetime.date(2026, 7, 2), 105.5, 106.0),   # Thu
]


class TestFlashBarSelection:
    def test_uses_pick_date_bar_not_latest(self):
        # A delayed cron used to price "the most recent day" — with a Thu
        # bar present, a Wed pick must still price Wednesday.
        bar = mi._pick_flash_bar(_BARS, datetime.date(2026, 7, 1))
        assert bar == (datetime.date(2026, 7, 1), 104.5, 105.0)

    def test_never_uses_a_bar_before_the_pick(self):
        # Weekend pick: the first bar AFTER the pick, never Friday's.
        bar = mi._pick_flash_bar(_BARS, datetime.date(2026, 6, 27))
        assert bar[0] == datetime.date(2026, 6, 29)

    def test_returns_none_when_no_bar_yet(self):
        assert mi._pick_flash_bar(_BARS, datetime.date(2026, 7, 3)) is None


class TestWeeklyBarSelection:
    def test_midweek_pick_not_backdated_to_monday(self):
        # The Ep35 AMD shape: picked Wednesday, previously credited from
        # Monday's open (hindsight gain).
        entry, exit_ = mi._pick_weekly_bars(_BARS, datetime.date(2026, 7, 1))
        assert entry[0] == datetime.date(2026, 7, 1)
        assert exit_[0] == datetime.date(2026, 7, 2)

    def test_monday_pick_spans_week(self):
        entry, exit_ = mi._pick_weekly_bars(_BARS, datetime.date(2026, 6, 29))
        assert entry[0] == datetime.date(2026, 6, 29)
        assert exit_[0] == datetime.date(2026, 7, 2)

    def test_no_bars_after_pick_returns_none(self):
        entry, exit_ = mi._pick_weekly_bars(_BARS, datetime.date(2026, 7, 6))
        assert entry is None and exit_ is None


# ---------------------------------------------------------------------------
# Matched NASDAQ window (flash alpha was always raw return)
# ---------------------------------------------------------------------------

class TestMatchedNasdaqWindow:
    def test_flash_same_bar_open_to_close(self):
        window = mi._matched_nasdaq_window(
            _BARS, datetime.date(2026, 7, 1), datetime.date(2026, 7, 1))
        entry_open, exit_close, d1, d2 = window
        assert (entry_open, exit_close) == (104.5, 105.0)
        assert d1 == d2 == datetime.date(2026, 7, 1)

    def test_entry_snaps_forward_exit_snaps_backward(self):
        # Weekend entry date → Monday bar; holiday exit date → last prior bar.
        window = mi._matched_nasdaq_window(
            _BARS, datetime.date(2026, 6, 27), datetime.date(2026, 7, 4))
        _, _, d1, d2 = window
        assert d1 == datetime.date(2026, 6, 29)
        assert d2 == datetime.date(2026, 7, 2)

    def test_inverted_window_returns_none(self):
        assert mi._matched_nasdaq_window(
            _BARS, datetime.date(2026, 7, 3), datetime.date(2026, 6, 27)) is None


# ---------------------------------------------------------------------------
# _close_trade integration (bar dates, discontinuity tripwire, stale void)
# ---------------------------------------------------------------------------

def _tracker():
    return {"metadata": {"position_size": 1000}, "trades": [], "summary": {}}


class TestCloseTradeIntegration:
    def test_flash_close_records_bar_dates_and_real_benchmark(self):
        trade = {
            "symbol": "MU", "market": "NASDAQ", "trade_type": "flash",
            "date": "2026-07-01",
        }
        with patch.object(mi, "_fetch_bars_for_trade", return_value=_BARS), \
             patch.object(mi, "_fetch_history_bars", return_value=_BARS):
            mi._close_trade(trade, _tracker())
        assert trade["status"] == "closed"
        assert trade["entry_bar_date"] == "2026-07-01"
        assert trade["exit_bar_date"] == "2026-07-01"
        assert trade["entry_price"] == 104.5
        assert trade["exit_price"] == 105.0
        # The benchmark window is the same bar — NOT close-vs-same-close 0.0.
        assert trade["nasdaq_return_pct"] != 0.0
        assert trade["nasdaq_entry"] == 104.5

    def test_weekly_close_entry_starts_at_pick_date(self):
        trade = {
            "symbol": "GIS", "market": "NYSE", "trade_type": "weekly",
            "date": "2026-07-01",
        }
        with patch.object(mi, "_fetch_bars_for_trade", return_value=_BARS), \
             patch.object(mi, "_fetch_history_bars", return_value=_BARS):
            mi._close_trade(trade, _tracker())
        assert trade["entry_bar_date"] == "2026-07-01"  # not Monday 06-29
        assert trade["entry_price"] == 104.5

    def test_price_discontinuity_flagged_not_voided(self, caplog):
        import logging
        trade = {
            "symbol": "CNR", "market": "TSX", "trade_type": "weekly",
            "date": "2026-06-29", "pick_reference_price": 300.0,
        }
        with patch.object(mi, "_fetch_bars_for_trade", return_value=_BARS), \
             patch.object(mi, "_fetch_history_bars", return_value=_BARS), \
             caplog.at_level(logging.WARNING, logger=mi.logger.name):
            mi._close_trade(trade, _tracker())
        assert trade["status"] == "closed"
        assert trade.get("price_discontinuity") is True
        assert any("PRICE DISCONTINUITY" in r.getMessage()
                   for r in caplog.records)

    def test_no_bar_yet_leaves_trade_open(self):
        trade = {
            "symbol": "UNH", "market": "NYSE", "trade_type": "weekly",
            "date": datetime.date.today().isoformat(),
        }
        stale_bars = [(datetime.date.today() - datetime.timedelta(days=3),
                       100.0, 101.0)]
        with patch.object(mi, "_fetch_bars_for_trade", return_value=stale_bars):
            mi._close_trade(trade, _tracker())
        assert "status" not in trade or trade.get("status") != "voided"
        assert trade.get("entry_price") is None

    def test_stale_pick_with_no_data_voids(self):
        trade = {
            "symbol": "GONE", "market": "NASDAQ", "trade_type": "flash",
            "date": (datetime.date.today()
                     - datetime.timedelta(days=15)).isoformat(),
        }
        old_bars = [(datetime.date.today() - datetime.timedelta(days=20),
                     100.0, 101.0)]
        with patch.object(mi, "_fetch_bars_for_trade", return_value=old_bars):
            mi._close_trade(trade, _tracker())
        assert trade["status"] == "voided"
        assert trade["void_reason"] == "no_trading_data_after_pick"


# ---------------------------------------------------------------------------
# Self-healing NaN-closed migration
# ---------------------------------------------------------------------------

class TestNonfiniteClosedMigration:
    def test_nan_closed_trade_becomes_voided_on_load(self, tmp_path):
        p = tmp_path / "investment_tracker.json"
        p.write_text(json.dumps({
            "metadata": {"position_size": 1000},
            "summary": {},
            "trades": [
                {"symbol": "DELL", "status": "closed", "episode_num": 57,
                 "pnl_pct": float("nan"), "pnl_dollars": float("nan"),
                 "entry_price": 426.15, "exit_price": float("nan")},
                {"symbol": "MSFT", "status": "closed", "episode_num": 91,
                 "pnl_pct": 3.44, "pnl_dollars": 34.4,
                 "entry_price": 377.5, "exit_price": 390.49},
            ],
        }, allow_nan=True))
        tracker = mi._load_tracker(p)
        dell = tracker["trades"][0]
        assert dell["status"] == "voided"
        assert dell["pnl_pct"] is None
        assert tracker["summary"]["total_trades"] == 1
        assert tracker["summary"]["breakeven"] == 0

    def test_healthy_closed_trades_untouched(self):
        tracker = {
            "trades": [{"symbol": "A", "status": "closed", "pnl_pct": 1.0,
                        "exit_price": 10.0}],
        }
        mi._void_nonfinite_closed_trades(tracker)
        assert tracker["trades"][0]["status"] == "closed"


# ---------------------------------------------------------------------------
# Read-only hooks (--test runs must not mutate the track record)
# ---------------------------------------------------------------------------

class TestReadonlyHooks:
    def test_post_generate_is_a_noop_in_readonly_mode(self, tmp_path, monkeypatch):
        monkeypatch.setenv("NERRA_HOOKS_READONLY", "1")
        config = SimpleNamespace(episode=SimpleNamespace(output_dir=str(tmp_path)))
        digest = (
            "### Practice Investment of the Day\n"
            "**Trade Type:** Flash Trade\n"
            "**Today's Pick:** NVDA — Nvidia\n"
            "**Market:** NASDAQ\n"
            "**Strategy:** Momentum play on earnings beat\n"
            "**Confidence Level:** High\n"
        )
        mi.post_generate(config, digest_text=digest, episode_num=99)
        assert not (tmp_path / mi.TRACKER_FILENAME).exists()
        assert not (tmp_path / mi.TAUGHT_LESSONS_FILENAME).exists()

    def test_post_generate_records_in_normal_mode(self, tmp_path, monkeypatch):
        monkeypatch.delenv("NERRA_HOOKS_READONLY", raising=False)
        config = SimpleNamespace(episode=SimpleNamespace(output_dir=str(tmp_path)))
        digest = (
            "### Practice Investment of the Day\n"
            "**Trade Type:** Flash Trade\n"
            "**Today's Pick:** NVDA — Nvidia\n"
            "**Market:** NASDAQ\n"
            "**Strategy:** Momentum play on earnings beat\n"
            "**Confidence Level:** High\n"
        )
        with patch.object(mi, "_probe_pick", return_value=True):
            mi.post_generate(config, digest_text=digest, episode_num=99)
        tracker = json.loads((tmp_path / mi.TRACKER_FILENAME).read_text())
        assert tracker["trades"][0]["symbol"] == "NVDA"

    def test_run_show_sets_readonly_for_test_runs(self):
        # The wiring lives in run_show.run(); pin the source so the guard
        # can't be silently dropped.
        src = (_ROOT / "run_show.py").read_text(encoding="utf-8")
        assert 'NERRA_HOOKS_READONLY' in src
        assert 'args.test or getattr(args, "rehearse", False)' in src


# ---------------------------------------------------------------------------
# Lessons-learned dedup (echo-chamber fix)
# ---------------------------------------------------------------------------

class TestLessonDedup:
    _RULE = ("Always require volume confirmation above the 20-day average "
             "before entering momentum trades on earnings beats")

    def test_near_duplicate_reinforces_instead_of_appending(self, tmp_path):
        data = mi._load_lessons_learned(tmp_path / "nope.json")
        first = mi._append_lesson_learned(
            data, observation="Momentum faded without volume support",
            adjustment=self._RULE, episode_num=40)
        dup = mi._append_lesson_learned(
            data,
            observation="The launch catalyst faded once volatility rose",
            adjustment=("Require volume confirmation above the 20-day "
                        "average before entering momentum trades"),
            episode_num=41)
        assert dup is first
        assert len(data["entries"]) == 1
        assert first["reinforced_count"] == 1
        assert first["last_reinforced_episode"] == 41

    def test_distinct_rule_still_appends(self, tmp_path):
        data = mi._load_lessons_learned(tmp_path / "nope.json")
        mi._append_lesson_learned(
            data, observation="Momentum faded without volume support",
            adjustment=self._RULE, episode_num=40)
        second = mi._append_lesson_learned(
            data,
            observation="The gold miner gapped down on the headline",
            adjustment="Never carry a miner through a pending sanctions resolution",
            episode_num=41)
        assert len(data["entries"]) == 2
        assert second["id"] == "LL-002"

    def test_block_selects_distinct_rules(self, tmp_path):
        data = mi._load_lessons_learned(tmp_path / "nope.json")
        # Simulate the pre-dedup backlog: 4 near-identical actives + 2 distinct.
        for i in range(4):
            data["entries"].append({
                "id": f"LL-{i + 1:03d}", "status": "active",
                "observation": f"Observation variant {i}",
                "adjustment": self._RULE,
            })
        data["entries"].append({
            "id": "LL-005", "status": "active",
            "observation": "The miner gapped down",
            "adjustment": "Never carry a miner through a pending sanctions resolution",
        })
        data["entries"].append({
            "id": "LL-006", "status": "active",
            "observation": "Sector concentration built up",
            "adjustment": "Cap any single sector at 30% of the trailing window",
        })
        block = mi._build_lessons_learned_block(data)
        assert block.count("volume confirmation") == 1
        assert "sanctions resolution" in block
        assert "Cap any single sector" in block

    def test_committed_ledger_has_no_active_duplicates(self):
        data = json.loads(
            (_ROOT / "digests/modern_investing/lessons_learned.json")
            .read_text(encoding="utf-8"))
        active = [e for e in data["entries"] if e.get("status") == "active"]
        for i, a in enumerate(active):
            for b in active[i + 1:]:
                sim = mi._lesson_similarity(a["adjustment"], b["adjustment"])
                assert sim < mi._LESSON_SIMILARITY_THRESHOLD, (
                    f"{a['id']} and {b['id']} are near-duplicates "
                    f"(similarity {sim:.2f}) — the echo chamber is back")


# ---------------------------------------------------------------------------
# Scoreboard + calibration + snapshot
# ---------------------------------------------------------------------------

class TestMatchedWindowScore:
    def _closed(self, pnl, ndq):
        return {"status": "closed", "pnl_pct": pnl, "pnl_dollars": pnl * 10,
                "nasdaq_return_pct": ndq, "alpha_pct": pnl - ndq}

    def test_summary_carries_compounded_matched_metrics(self):
        tracker = {"metadata": {"position_size": 1000}, "summary": {},
                   "trades": [self._closed(10.0, 2.0), self._closed(-5.0, 1.0)]}
        mi._recompute_summary(tracker)
        s = tracker["summary"]
        assert s["matched_window_trades"] == 2
        assert s["compounded_return_pct"] == pytest.approx(4.5, abs=0.01)
        assert s["compounded_nasdaq_matched_pct"] == pytest.approx(3.02, abs=0.01)
        assert s["matched_window_alpha_pct"] == pytest.approx(1.48, abs=0.01)

    def test_benchmark_block_labels_both_measures(self):
        tracker = mi._fresh_tracker()
        tracker["benchmark"] = {"current_close": 25000.0, "ytd_pct": 11.0,
                                "inception_to_date_pct": 15.0,
                                "last_updated": "2026-07-03"}
        tracker["alpha"] = {"ytd_pct": -10.0, "inception_to_date_pct": -14.0,
                            "monthly": {}}
        tracker["summary"] = {"matched_window_alpha_pct": 11.2,
                              "matched_window_trades": 35,
                              "compounded_return_pct": 23.6,
                              "compounded_nasdaq_matched_pct": 12.4}
        block = mi._build_benchmark_block(tracker)
        assert "MATCHED-WINDOW SCORE" in block
        assert "BUY-AND-HOLD GAP" in block
        assert "NOT capital-matched" in block

    def test_portfolio_summary_leads_with_matched_window_alpha(self):
        tracker = {"metadata": {"position_size": 1000}, "summary": {},
                   "trades": [self._closed(10.0, 2.0), self._closed(1.0, 0.5)]}
        mi._recompute_summary(tracker)
        block = mi._build_portfolio_summary(tracker)
        assert "Matched-window alpha vs NASDAQ" in block
        assert "matched-window" in block


class TestConfidenceCalibrationAllBuckets:
    def _closed(self, conf, alpha):
        return {"status": "closed", "confidence": conf, "alpha_pct": alpha}

    def test_all_medium_distribution_gets_called_out(self):
        tracker = {"trades": [self._closed("Medium", a)
                              for a in (1.0, -1.0, 2.0, -0.5, 0.3)]}
        out = mi.get_mit_confidence_calibration(tracker)
        assert "Medium: " in out
        assert "uninformative" in out

    def test_mixed_buckets_reported_without_callout(self):
        trades = ([self._closed("High", 2.0)] * 3
                  + [self._closed("Medium", 0.5)] * 3
                  + [self._closed("Low", -1.0)] * 2)
        out = mi.get_mit_confidence_calibration({"trades": trades})
        assert "High: 3/3" in out
        assert "Low: 0/2" in out
        assert "uninformative" not in out


class TestMonthlySnapshotAlphaKey:
    def test_snapshot_reads_existing_alpha_key(self):
        tracker = {
            "summary": {"total_trades": 5, "win_rate_pct": 60.0,
                        "cumulative_pnl": 100.0},
            "alpha": {"ytd_pct": -10.46, "inception_to_date_pct": -14.74,
                      "monthly": {}},
            "monthly_snapshots": [],
        }
        mi._maybe_record_monthly_snapshot(tracker, datetime.date(2026, 7, 3))
        snap = tracker["monthly_snapshots"][-1]
        # The old code read alpha["ytd_vs_nasdaq"] — a key that never
        # existed — and recorded 0.0 in every snapshot.
        assert snap["alpha_vs_nasdaq"] == -10.46


# ---------------------------------------------------------------------------
# Honest close labels
# ---------------------------------------------------------------------------

class TestHonestCloseLabels:
    def test_review_uses_actual_bar_days(self):
        # A weekly hold closed pre-market Friday exits on THURSDAY's bar —
        # the review must say "Thursday close", not the hardcoded "Friday
        # close" that shipped for months.
        tracker = {
            "metadata": {"position_size": 1000},
            "trades": [{
                "symbol": "UNH", "status": "closed", "trade_type": "weekly",
                "strategy": "mean reversion", "entry_price": 426.53,
                "exit_price": 425.36, "pnl_pct": -0.27, "pnl_dollars": -2.7,
                "entry_bar_date": "2026-06-29", "exit_bar_date": "2026-07-02",
            }],
            "summary": {"cumulative_pnl": 0.0, "total_trades": 1, "wins": 0,
                        "win_rate_pct": 0.0, "current_streak": -1},
        }
        review = mi._build_trade_review(tracker, episode_num=97)
        assert "Monday open" in review
        assert "Thursday close" in review
        assert "Friday close" not in review
