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


# ---------------------------------------------------------------------------
# Trade signal (SnapTrade execution bridge, July 2026)
# ---------------------------------------------------------------------------

class TestTradeSignal:
    """The future execution layer consumes trade_signal_latest.json — never
    the digest prose — so LLM formatting drift can't reach an order ticket."""

    _DIGEST = (
        "### Practice Investment of the Day\n"
        "**Trade Type:** Weekly Hold\n"
        "**Today's Pick:** CNR — Canadian National Railway (TSX:CNR)\n"
        "**Market:** TSX\n"
        "**Strategy:** Dividend-growth entry\n"
        "**Confidence Level:** Medium\n"
    )

    def _run_post_generate(self, tmp_path, digest, monkeypatch):
        monkeypatch.delenv("NERRA_HOOKS_READONLY", raising=False)
        config = SimpleNamespace(episode=SimpleNamespace(output_dir=str(tmp_path)))
        with patch.object(mi, "_probe_pick", return_value=True):
            mi.post_generate(config, digest_text=digest, episode_num=96)
        return json.loads(
            (tmp_path / mi.TRADE_SIGNAL_LATEST_FILENAME).read_text())

    def test_new_trade_signal_routes_tsx_to_cad_wealthsimple(
            self, tmp_path, monkeypatch):
        signal = self._run_post_generate(tmp_path, self._DIGEST, monkeypatch)
        assert signal["schema_version"] == mi.TRADE_SIGNAL_SCHEMA_VERSION
        assert signal["action"] == "new_trade"
        t = signal["trade"]
        assert t["snaptrade_symbol"] == "CNR.TO"  # Yahoo == SnapTrade format
        assert t["currency"] == "CAD"
        assert t["suggested_account"] == "wealthsimple"
        assert t["side"] == "BUY"
        # Per-episode copy also written.
        assert (tmp_path / "trade_signal_ep096.json").exists()

    def test_us_pick_routes_to_usd_webull(self, tmp_path, monkeypatch):
        digest = self._DIGEST.replace(
            "CNR — Canadian National Railway (TSX:CNR)", "NVDA — Nvidia"
        ).replace("**Market:** TSX", "**Market:** NASDAQ")
        signal = self._run_post_generate(tmp_path, digest, monkeypatch)
        t = signal["trade"]
        assert t["snaptrade_symbol"] == "NVDA"
        assert t["currency"] == "USD"
        assert t["suggested_account"] == "webull"

    def test_client_order_id_is_deterministic(self, tmp_path, monkeypatch):
        s1 = self._run_post_generate(tmp_path, self._DIGEST, monkeypatch)
        s2 = self._run_post_generate(tmp_path, self._DIGEST, monkeypatch)
        # A retried cron produces the SAME id → idempotent placement.
        assert (s1["trade"]["client_order_id"]
                == s2["trade"]["client_order_id"])
        assert len(s1["trade"]["client_order_id"]) == 36  # uuid string

    def test_explicit_no_trade_day_is_explicit_in_signal(
            self, tmp_path, monkeypatch):
        digest = ("### Practice Investment of the Day\n"
                  "**Today's Pick:** No trade today.\n")
        signal = self._run_post_generate(tmp_path, digest, monkeypatch)
        assert signal["action"] == "no_trade"
        assert signal["reason"] == "explicit_no_trade"
        assert signal["trade"] is None

    def test_extraction_drift_is_distinguishable(self, tmp_path, monkeypatch):
        signal = self._run_post_generate(
            tmp_path, "**Today's Pick** is Nvidia at current levels.",
            monkeypatch)
        assert signal["action"] == "no_trade"
        assert signal["reason"] == "no_pick_extracted"

    def test_readonly_mode_writes_no_signal(self, tmp_path, monkeypatch):
        monkeypatch.setenv("NERRA_HOOKS_READONLY", "1")
        config = SimpleNamespace(episode=SimpleNamespace(output_dir=str(tmp_path)))
        mi.post_generate(config, digest_text=self._DIGEST, episode_num=96)
        assert not (tmp_path / mi.TRADE_SIGNAL_LATEST_FILENAME).exists()


# ---------------------------------------------------------------------------
# Multi-index benchmarking (July 2026 "beat all major indices" pass)
# ---------------------------------------------------------------------------

class TestMultiIndexBenchmark:
    def _closed(self, pnl, ndq, sp500=None, tsx=None):
        return {
            "status": "closed", "pnl_pct": pnl, "pnl_dollars": pnl * 10,
            "nasdaq_return_pct": ndq, "alpha_pct": pnl - ndq,
            "benchmark_returns": {"nasdaq": ndq, "sp500": sp500, "tsx": tsx},
        }

    def test_summary_scores_every_index(self):
        tracker = {"metadata": {"position_size": 1000}, "summary": {},
                   "trades": [self._closed(10.0, 2.0, sp500=1.0, tsx=-1.0),
                              self._closed(-2.0, 1.0, sp500=0.5, tsx=0.2)]}
        mi._recompute_summary(tracker)
        scores = tracker["summary"]["benchmark_scores"]
        assert set(scores) == {"nasdaq", "sp500", "tsx"}
        assert scores["sp500"]["trades"] == 2
        # portfolio compounded: 1.10*0.98-1 = +7.8%; tsx: 0.99*1.002-1
        assert scores["tsx"]["alpha_pct"] == pytest.approx(
            (1.10 * 0.98 - 0.99 * 1.002) * 100, abs=0.05)
        assert tracker["summary"]["indices_scored"] == 3
        # Beats nasdaq (7.8 vs 3.02), sp500 (7.8 vs 1.5), tsx (7.8 vs -0.6).
        assert tracker["summary"]["indices_beaten"] == 3

    def test_legacy_trades_fall_back_to_nasdaq_field_only(self):
        legacy = {"status": "closed", "pnl_pct": 5.0, "pnl_dollars": 50.0,
                  "nasdaq_return_pct": 2.0, "alpha_pct": 3.0}
        tracker = {"metadata": {"position_size": 1000}, "summary": {},
                   "trades": [legacy]}
        mi._recompute_summary(tracker)
        scores = tracker["summary"]["benchmark_scores"]
        assert scores["nasdaq"]["trades"] == 1
        assert "sp500" not in scores  # no data — not silently zeroed

    def test_annotate_fills_benchmark_returns_for_all_indices(self):
        trade = {"symbol": "MU", "date": "2026-07-01",
                 "trade_type": "flash", "pnl_pct": 1.0}
        with patch.object(mi, "_fetch_history_bars", return_value=_BARS):
            mi._annotate_trade_with_nasdaq(trade)
        returns = trade["benchmark_returns"]
        assert set(returns) == {"nasdaq", "sp500", "tsx"}
        # Same stub bars for every index → same matched-window return.
        assert returns["sp500"] == returns["nasdaq"] == pytest.approx(0.48, abs=0.01)

    def test_benchmark_block_reports_index_sweep(self):
        tracker = mi._fresh_tracker()
        tracker["benchmark"] = {"current_close": 25000.0, "ytd_pct": 11.0,
                                "inception_to_date_pct": 15.0,
                                "last_updated": "2026-07-04"}
        tracker["alpha"] = {"ytd_pct": -10.0, "inception_to_date_pct": -14.0,
                            "monthly": {}}
        tracker["summary"] = {
            "matched_window_alpha_pct": 11.2, "matched_window_trades": 35,
            "compounded_return_pct": 23.6,
            "compounded_nasdaq_matched_pct": 12.4,
            "indices_beaten": 2, "indices_scored": 3,
            "benchmark_scores": {
                "nasdaq": {"alpha_pct": 11.2, "trades": 35},
                "sp500": {"alpha_pct": 5.0, "trades": 35},
                "tsx": {"alpha_pct": -1.0, "trades": 35},
            },
        }
        block = mi._build_benchmark_block(tracker)
        assert "beating 2 of 3 major indices" in block
        assert "S&P 500" in block and "TSX Composite" in block


# ---------------------------------------------------------------------------
# Rule-effectiveness scoring (the loop learns whether it's learning)
# ---------------------------------------------------------------------------

class TestRuleEffectiveness:
    _RULE_A = {"id": "LL-017", "status": "active",
               "observation": "Momentum faded without volume",
               "adjustment": "Always require volume confirmation before momentum entries"}
    _RULE_B = {"id": "LL-002", "status": "active",
               "observation": "Sector concentration built up",
               "adjustment": "Cap any single sector at 30% of the trailing window"}

    def _closed(self, alpha, rules):
        return {"status": "closed", "alpha_pct": alpha,
                "rules_in_effect": rules}

    def test_post_generate_stamps_rules_in_effect(self, tmp_path, monkeypatch):
        monkeypatch.delenv("NERRA_HOOKS_READONLY", raising=False)
        lessons = {"metadata": {}, "entries": [self._RULE_A, self._RULE_B]}
        (tmp_path / mi.LESSONS_LEARNED_FILENAME).write_text(
            json.dumps(lessons), encoding="utf-8")
        config = SimpleNamespace(episode=SimpleNamespace(output_dir=str(tmp_path)))
        digest = ("**Trade Type:** Flash Trade\n"
                  "**Today's Pick:** NVDA — Nvidia\n"
                  "**Market:** NASDAQ\n"
                  "**Strategy:** Momentum play\n"
                  "**Confidence Level:** High\n")
        with patch.object(mi, "_probe_pick", return_value=True):
            mi.post_generate(config, digest_text=digest, episode_num=100)
        tracker = json.loads((tmp_path / mi.TRACKER_FILENAME).read_text())
        assert set(tracker["trades"][0]["rules_in_effect"]) == {"LL-017", "LL-002"}

    def test_scoreboard_reports_with_and_without_alpha(self):
        lessons = {"entries": [self._RULE_A]}
        tracker = {"trades": (
            [self._closed(2.0, ["LL-017"]) for _ in range(5)]
            + [self._closed(-1.0, []) for _ in range(5)]
        )}
        board = mi._build_rule_scoreboard(lessons, tracker)
        assert "[LL-017] in effect for 5 closed trades" in board
        assert "+2.00%" in board
        assert "-1.00%" in board
        assert "RETIREMENT" not in board  # positive edge — keep

    def test_ineffective_rule_flagged_for_retirement(self):
        lessons = {"entries": [self._RULE_A]}
        tracker = {"trades": (
            [self._closed(0.0, ["LL-017"]) for _ in range(8)]
            + [self._closed(1.0, []) for _ in range(4)]
        )}
        board = mi._build_rule_scoreboard(lessons, tracker)
        assert "RETIREMENT CANDIDATE" in board
        assert "keep obeying it until retired" in board  # never auto-retired

    def test_too_few_stamped_trades_yields_empty_board(self):
        lessons = {"entries": [self._RULE_A]}
        tracker = {"trades": [self._closed(2.0, ["LL-017"])]}
        assert mi._build_rule_scoreboard(lessons, tracker) == ""

    def test_selected_rules_match_block_content(self):
        lessons = {"entries": [self._RULE_A, self._RULE_B]}
        selected = {e["id"] for e in mi._selected_active_rules(lessons)}
        block = mi._build_lessons_learned_block(lessons)
        for rid in selected:
            assert rid in block


# ---------------------------------------------------------------------------
# Regime block (adaptive selectivity) + statistical discipline
# ---------------------------------------------------------------------------

class TestRegimeBlock:
    def _closed(self, alpha, pnl_dollars):
        return {"status": "closed", "alpha_pct": alpha,
                "pnl_pct": alpha, "pnl_dollars": pnl_dollars}

    def test_cold_streak_raises_the_bar(self):
        # July 18: fresh cold streaks (dated today, no drought) raise the
        # bar and now also instruct on-air transparency.
        recent = datetime.date.today().isoformat()
        tracker = {"trades": [dict(self._closed(-2.0, -20.0), date=recent)
                              for _ in range(10)]}
        block = mi._build_regime_block(tracker)
        assert "COLD STREAK" in block
        assert "3+ independent aligned factors" in block

    def test_hot_streak_holds_discipline_never_presses(self):
        tracker = {"trades": [self._closed(2.5, 25.0) for _ in range(10)]}
        block = mi._build_regime_block(tracker)
        assert "HOT STREAK" in block
        assert "do not loosen criteria" in block

    def test_neutral_regime(self):
        tracker = {"trades": [self._closed(0.2, 2.0) for _ in range(10)]}
        block = mi._build_regime_block(tracker)
        assert "NEUTRAL" in block

    def test_drawdown_alone_triggers_cold(self):
        # July 18 recalibration: only a FULL-POSITION drawdown (> $250)
        # triggers cold on its own — $164 of standing drawdown had locked
        # the show cold permanently. Deep drawdown still tightens the bar.
        recent = datetime.date.today().isoformat()
        trades = ([dict(self._closed(5.0, 150.0), date=recent)
                   for _ in range(5)]
                  + [dict(self._closed(0.1, -60.0), date=recent)
                     for _ in range(5)])
        block = mi._build_regime_block({"trades": trades})
        assert "COLD STREAK" in block  # drawdown $300 > $250

    def test_too_few_trades_yields_empty(self):
        tracker = {"trades": [self._closed(1.0, 10.0) for _ in range(3)]}
        assert mi._build_regime_block(tracker) == ""


class TestPerformancePageMultiIndex:
    def test_template_carries_matched_window_and_sweep(self):
        src = (_ROOT / "templates/mit_performance_page.html.j2").read_text(
            encoding="utf-8")
        assert "Matched-Window Alpha vs NASDAQ" in src
        assert "Buy-and-Hold Gap vs NASDAQ" in src
        assert "not capital-matched" in src
        assert "Major-Index Sweep" in src


# ---------------------------------------------------------------------------
# Stop-loss enforcement (July 2026 fidelity pass)
# ---------------------------------------------------------------------------

_BARS_WITH_LOWS = [
    (datetime.date(2026, 6, 29), 102.0, 103.0, 101.5),  # Mon
    (datetime.date(2026, 6, 30), 103.5, 104.0, 103.0),  # Tue
    (datetime.date(2026, 7, 1), 104.5, 96.0, 94.0),     # Wed — plunge
    (datetime.date(2026, 7, 2), 95.5, 97.0, 95.0),      # Thu
]


class TestStopLossExtraction:
    def test_dollar_stop_extracted(self):
        digest = ("### Practice Investment of the Day\n"
                  "**Risk Assessment:** Momentum could fade; stop-loss at "
                  "$98.50, max acceptable loss 4%.\n")
        assert mi._extract_stop_loss(digest) == {"price": 98.5}

    def test_percent_stop_extracted(self):
        digest = ("### Practice Investment of the Day\n"
                  "**Risk Assessment:** Set a stop-loss of 5% below entry.\n")
        assert mi._extract_stop_loss(digest) == {"pct": 5.0}

    def test_no_stop_returns_none_never_guesses(self):
        digest = ("### Practice Investment of the Day\n"
                  "**Risk Assessment:** Volatility is elevated.\n")
        assert mi._extract_stop_loss(digest) is None

    def test_stop_outside_practice_section_ignored(self):
        digest = ("### Investor Education\n"
                  "A stop-loss at $50 protects capital.\n"
                  "### Practice Investment of the Day\n"
                  "**Risk Assessment:** thesis intact.\n")
        assert mi._extract_stop_loss(digest) is None


class TestStopBreach:
    def test_breach_fills_at_stop_price(self):
        entry_bar, exit_bar = _BARS_WITH_LOWS[0], _BARS_WITH_LOWS[-1]
        breach = mi._stop_breach(_BARS_WITH_LOWS, entry_bar, exit_bar, 97.0)
        assert breach == (datetime.date(2026, 7, 1), 97.0)

    def test_gap_through_stop_fills_at_open(self):
        bars = [
            (datetime.date(2026, 6, 29), 102.0, 103.0, 101.5),
            (datetime.date(2026, 6, 30), 90.0, 92.0, 89.0),  # gaps below stop
        ]
        breach = mi._stop_breach(bars, bars[0], bars[-1], 97.0)
        assert breach == (datetime.date(2026, 6, 30), 90.0)  # open, not stop

    def test_entry_bar_never_claims_same_day_breach(self):
        bars = [(datetime.date(2026, 6, 29), 102.0, 103.0, 90.0)]
        assert mi._stop_breach(bars, bars[0], bars[0], 97.0) is None

    def test_no_breach_returns_none(self):
        entry_bar, exit_bar = _BARS_WITH_LOWS[0], _BARS_WITH_LOWS[1]
        assert mi._stop_breach(
            _BARS_WITH_LOWS[:2], entry_bar, exit_bar, 90.0) is None

    def test_close_trade_enforces_stop(self):
        trade = {
            "symbol": "GIS", "market": "NYSE", "trade_type": "weekly",
            "date": "2026-06-29", "stop_loss": {"pct": 4.0},
        }
        with patch.object(mi, "_fetch_bars_for_trade",
                          return_value=_BARS_WITH_LOWS), \
             patch.object(mi, "_fetch_history_bars",
                          return_value=_BARS_WITH_LOWS):
            mi._close_trade(trade, {"metadata": {"position_size": 1000},
                                    "trades": [], "summary": {}})
        assert trade["stopped_out"] is True
        # stop = 102 * 0.96 = 97.92; breached Wed (low 94), fills at stop.
        assert trade["exit_price"] == 97.92
        assert trade["exit_bar_date"] == "2026-07-01"
        # Benchmark window matches the ACTUAL shortened holding period.
        assert trade["nasdaq_exit_date"] == "2026-07-01"

    def test_close_trade_without_stop_unchanged(self):
        trade = {
            "symbol": "GIS", "market": "NYSE", "trade_type": "weekly",
            "date": "2026-06-29",
        }
        with patch.object(mi, "_fetch_bars_for_trade",
                          return_value=_BARS_WITH_LOWS), \
             patch.object(mi, "_fetch_history_bars",
                          return_value=_BARS_WITH_LOWS):
            mi._close_trade(trade, {"metadata": {"position_size": 1000},
                                    "trades": [], "summary": {}})
        assert "stopped_out" not in trade
        assert trade["exit_bar_date"] == "2026-07-02"

    def test_review_narrates_stop_out(self):
        tracker = {
            "metadata": {"position_size": 1000},
            "trades": [{
                "symbol": "GIS", "status": "closed", "trade_type": "weekly",
                "strategy": "earnings play", "entry_price": 102.0,
                "exit_price": 97.92, "pnl_pct": -4.0, "pnl_dollars": -40.0,
                "stopped_out": True, "stop_price": 97.92,
                "entry_bar_date": "2026-06-29", "exit_bar_date": "2026-07-01",
            }],
            "summary": {"cumulative_pnl": 0.0, "total_trades": 1, "wins": 0,
                        "win_rate_pct": 0.0, "current_streak": -1},
        }
        review = mi._build_trade_review(tracker, episode_num=101)
        assert "Stopped out" in review
        assert "$97.92" in review


class TestAlphaTStat:
    def _closed(self, alpha):
        return {"status": "closed", "pnl_pct": alpha, "pnl_dollars": alpha,
                "alpha_pct": alpha, "nasdaq_return_pct": 0.0}

    def test_consistent_edge_is_significant(self):
        # 10 trades, alpha ~ +1% with tiny spread → t >> 2.
        tracker = {"metadata": {"position_size": 1000}, "summary": {},
                   "trades": [self._closed(1.0 + 0.01 * i) for i in range(10)]}
        mi._recompute_summary(tracker)
        assert tracker["summary"]["alpha_t_stat"] > 2
        assert tracker["summary"]["alpha_statistically_significant"] is True

    def test_noisy_record_is_not_significant(self):
        tracker = {"metadata": {"position_size": 1000}, "summary": {},
                   "trades": [self._closed(a) for a in
                              (5.0, -4.0, 3.0, -3.5, 4.0, -4.2)]}
        mi._recompute_summary(tracker)
        assert tracker["summary"]["alpha_statistically_significant"] is False

    def test_block_tells_the_model_to_hedge_when_not_significant(self):
        tracker = mi._fresh_tracker()
        tracker["benchmark"] = {"current_close": 25000.0, "ytd_pct": 11.0,
                                "inception_to_date_pct": 15.0,
                                "last_updated": "2026-07-04"}
        tracker["summary"] = {
            "matched_window_alpha_pct": 3.0, "matched_window_trades": 12,
            "compounded_return_pct": 5.0,
            "compounded_nasdaq_matched_pct": 2.0,
            "alpha_t_stat": 0.9, "alpha_statistically_significant": False,
        }
        block = mi._build_benchmark_block(tracker)
        # July 18: the caveat moved INLINE with the alpha number (models
        # echo data lines and drop separate instructions). July 24: after
        # a second miss, it fused into the value as a data parenthetical.
        assert "(early, not yet statistically significant" in block

    def test_signal_carries_stop_loss(self, tmp_path, monkeypatch):
        monkeypatch.delenv("NERRA_HOOKS_READONLY", raising=False)
        config = SimpleNamespace(episode=SimpleNamespace(output_dir=str(tmp_path)))
        digest = ("### Practice Investment of the Day\n"
                  "**Trade Type:** Flash Trade\n"
                  "**Today's Pick:** NVDA — Nvidia\n"
                  "**Market:** NASDAQ\n"
                  "**Strategy:** Momentum play\n"
                  "**Risk Assessment:** stop-loss at $190.00.\n"
                  "**Confidence Level:** High\n")
        with patch.object(mi, "_probe_pick", return_value=True):
            mi.post_generate(config, digest_text=digest, episode_num=102)
        signal = json.loads(
            (tmp_path / mi.TRADE_SIGNAL_LATEST_FILENAME).read_text())
        assert signal["trade"]["stop_loss"] == {"price": 190.0}


# ---------------------------------------------------------------------------
# July 18 2026 scoring pass — regime deadlock, degenerate weeklies,
# sweep gating, inline hedge, no-trade taxonomy
# ---------------------------------------------------------------------------

class TestRegimeDeadlockFix:
    def _closed(self, alpha, pnl_dollars, date="2026-07-01"):
        return {"status": "closed", "alpha_pct": alpha, "pnl_pct": alpha,
                "pnl_dollars": pnl_dollars, "date": date}

    def test_median_is_outlier_robust(self):
        # The Ep81 MDA shape: nine mild positives + one -11.8 outlier.
        # Mean would be negative; median must keep the regime out of COLD.
        recent = datetime.date.today().isoformat()
        trades = ([self._closed(0.5, 5.0, recent) for _ in range(9)]
                  + [self._closed(-11.8, -118.0, recent)])
        block = mi._build_regime_block({"trades": trades})
        assert "COLD STREAK" not in block

    def test_standing_drawdown_of_one_trade_is_not_cold(self):
        # $164 below high-water (the real July state) must not trip a
        # permanent cold streak; only a full-position drawdown does.
        recent = datetime.date.today().isoformat()
        trades = ([self._closed(2.0, 100.0, recent) for _ in range(5)]
                  + [self._closed(0.2, -33.0, recent) for _ in range(5)])
        block = mi._build_regime_block({"trades": trades})
        assert "COLD STREAK" not in block

    def test_pick_drought_releases_the_brake(self):
        # Genuinely cold record + no pick in 10 days → SELECTIVE RESET
        # (the deadlock breaker), never a suppressive COLD text.
        old = (datetime.date.today() - datetime.timedelta(days=10)).isoformat()
        trades = [self._closed(-2.0, -20.0, old) for _ in range(10)]
        block = mi._build_regime_block({"trades": trades})
        assert "SELECTIVE RESET" in block
        assert "no pick in 10 days" in block
        assert "COLD STREAK" not in block

    def test_fresh_cold_streak_still_raises_bar_with_transparency(self):
        recent = datetime.date.today().isoformat()
        trades = [self._closed(-2.0, -20.0, recent) for _ in range(10)]
        block = mi._build_regime_block({"trades": trades})
        assert "COLD STREAK" in block
        assert "TELL LISTENERS PLAINLY" in block  # dead air → narrative


class TestWeeklyMinHold:
    def test_thursday_pick_not_closed_on_next_day_friday(self):
        # The Ep101 COST degenerate: picked Thursday, closed on Friday's
        # pre-market run with one bar (entry==exit bar). Now rolls.
        thursday = datetime.date(2026, 7, 9)
        friday = datetime.date(2026, 7, 10)
        tracker = {"metadata": {"position_size": 1000}, "summary": {},
                   "trades": [{"symbol": "COST", "market": "NYSE",
                               "trade_type": "weekly", "status": "open",
                               "date": thursday.isoformat()}]}
        with patch.object(mi.datetime, "date", wraps=datetime.date) as mock_date, \
             patch.object(mi, "_snapshot_trade") as snap, \
             patch.object(mi, "_close_trade") as close, \
             patch.object(mi, "_save_tracker"):
            mock_date.today.return_value = friday
            mi._evaluate_open_trade(tracker, Path("/nope"))
        close.assert_not_called()
        snap.assert_called_once()

    def test_monday_pick_still_closes_friday(self):
        monday = datetime.date(2026, 7, 6)
        friday = datetime.date(2026, 7, 10)
        tracker = {"metadata": {"position_size": 1000}, "summary": {},
                   "trades": [{"symbol": "GIS", "market": "NYSE",
                               "trade_type": "weekly", "status": "open",
                               "date": monday.isoformat()}]}
        with patch.object(mi.datetime, "date", wraps=datetime.date) as mock_date, \
             patch.object(mi, "_close_trade") as close, \
             patch.object(mi, "_save_tracker"):
            mock_date.today.return_value = friday
            mi._evaluate_open_trade(tracker, Path("/nope"))
        close.assert_called_once()

    def test_shadow_exit_calendar_matches(self):
        from execution import shadow as sh
        # Thursday weekly → NEXT Friday, not tomorrow.
        assert sh._exit_due_date(
            datetime.date(2026, 7, 9), "weekly") == datetime.date(2026, 7, 17)
        # Wednesday weekly → this Friday (2-day hold is acceptable).
        assert sh._exit_due_date(
            datetime.date(2026, 7, 8), "weekly") == datetime.date(2026, 7, 10)


class TestSweepGating:
    def _summary(self, sp_trades):
        return {
            "matched_window_alpha_pct": 6.59, "matched_window_trades": 37,
            "compounded_return_pct": 18.94,
            "compounded_nasdaq_matched_pct": 12.35,
            "alpha_t_stat": 0.31, "alpha_statistically_significant": False,
            "indices_beaten": 1, "indices_scored": 3,
            "benchmark_scores": {
                "nasdaq": {"alpha_pct": 6.59, "trades": 37},
                "sp500": {"alpha_pct": -4.24, "trades": sp_trades},
                "tsx": {"alpha_pct": -4.59, "trades": sp_trades},
            },
        }

    def _tracker(self, sp_trades):
        tracker = mi._fresh_tracker()
        tracker["benchmark"] = {"current_close": 25873.0, "ytd_pct": 11.0,
                                "inception_to_date_pct": 15.0,
                                "last_updated": "2026-07-18"}
        tracker["summary"] = self._summary(sp_trades)
        return tracker

    def test_two_trade_samples_suppress_the_sweep(self):
        # The real July 18 state: 37-trade NASDAQ vs 2-trade S&P/TSX —
        # "beating 1 of 3" was statistically meaningless prompt context.
        block = mi._build_benchmark_block(self._tracker(sp_trades=2))
        assert "MAJOR-INDEX SWEEP" not in block

    def test_qualified_samples_reenable_the_sweep(self):
        block = mi._build_benchmark_block(self._tracker(sp_trades=12))
        assert "MAJOR-INDEX SWEEP" in block
        assert "beating 1 of 3" in block

    def test_hedge_is_inline_with_the_alpha_number(self):
        # Two weeks of transcripts: alpha quoted in most episodes, hedge
        # spoken in zero — the caveat must be part of the quoted line.
        # July 24 2026 (second miss): even the em-dash instruction form
        # was dropped in 5/6 mentions; the qualifier is now a data-shaped
        # parenthetical fused to the alpha value itself.
        block = mi._build_benchmark_block(self._tracker(sp_trades=2))
        assert "+6.59% (early, not yet statistically significant" in block
        assert "never quote" not in block.lower()


class TestNoTradeReasonTaxonomy:
    def test_none_form_is_explicit(self):
        assert mi._no_trade_reason(
            "### Practice Investment of the Day\n"
            "**Trade Type:** No new trade\n**Today's Pick:** None\n"
        ) == "explicit_no_trade"

    def test_no_trade_type_form_is_explicit(self):
        assert mi._no_trade_reason(
            "### Practice Investment of the Day\n"
            "**Trade Type:** No Trade\n**Today's Pick:** None — watching BNKR\n"
        ) == "explicit_no_trade"

    def test_midweek_update_is_explicit_not_drift(self):
        assert mi._no_trade_reason(
            "### Practice Investment of the Day\n"
            "**Trade Type:** Mid-Week Update\n"
        ) == "explicit_no_trade"

    def test_recap_without_section_is_not_drift(self):
        assert mi._no_trade_reason(
            "# Weekly recap\nNo practice segment this Sunday.\n"
        ) == "no_practice_section"

    def test_genuine_drift_still_flagged(self):
        assert mi._no_trade_reason(
            "### Practice Investment of the Day\n"
            "**Today's Pick** is Nvidia at current levels.\n"
        ) == "no_pick_extracted"


# ---------------------------------------------------------------------------
# July 24 2026 review — suffixed-symbol extraction + wrong-instrument
# tripwire (Ep111 CNR.TO lost pick / Ep113 BTC-USD → equity "BTC" class)
# ---------------------------------------------------------------------------

class TestSuffixedSymbolExtraction:
    """The July 3 pass taught the DIGEST to emit exchange-native symbols
    (CNR.TO, BTC-USD) but the extractor still only accepted bare
    [A-Z]{1,5}: Ep111's spoken CNR.TO weekly pick was silently lost
    (signal reason no_pick_extracted) and Ep113's BTC-USD was truncated
    to "BTC" and validated against the wrong equity."""

    def _digest(self, pick_line, market="NYSE"):
        return (
            "### Practice Investment of the Day\n"
            f"**Trade Type:** Weekly Hold\n"
            f"**Today's Pick:** {pick_line}\n"
            f"**Market:** {market}\n"
            "**Strategy:** test strategy\n"
            "- **Confidence Level:** Medium\n"
        )

    def test_crypto_pair_symbol_survives(self):
        trade = mi._extract_trade_from_digest(
            self._digest("BTC-USD — Bitcoin", market="Crypto"), 999)
        assert trade is not None
        assert trade["symbol"] == "BTC-USD"
        assert trade["market"] == "CRYPTO"

    def test_tsx_suffixed_symbol_survives(self):
        trade = mi._extract_trade_from_digest(
            self._digest("CNR.TO — Canadian National Railway", market="TSX"), 999)
        assert trade is not None
        assert trade["symbol"] == "CNR.TO"

    def test_ep111_real_pick_line_extracts(self):
        # The exact shipped Ep111 line, prompt-echo parenthetical included.
        trade = mi._extract_trade_from_digest(self._digest(
            "CNR.TO — Canadian National Railway (only for new picks on "
            "Monday or Flash Trades)", market="TSX"), 111)
        assert trade is not None
        assert trade["symbol"] == "CNR.TO"

    def test_bare_us_symbol_unchanged(self):
        trade = mi._extract_trade_from_digest(
            self._digest("LMT — Lockheed Martin"), 999)
        assert trade is not None
        assert trade["symbol"] == "LMT"

    def test_no_trade_day_still_returns_none(self):
        trade = mi._extract_trade_from_digest(
            self._digest("None — monitoring Lockheed Martin ($LMT)"), 999)
        assert trade is None

    def test_tsx_v_market_no_longer_shadowed_by_tsx(self):
        # Latent bug: (TSX|NYSE|NASDAQ|TSX-V) matched "TSX" inside
        # "TSX-V", so TSX-V could never be extracted. Alternation order
        # now puts TSX-V first.
        trade = mi._extract_trade_from_digest(
            self._digest("ABC.V — Test Venture Co", market="TSX-V"), 999)
        assert trade is not None
        assert trade["market"] == "TSX-V"


class TestCryptoSymbolCandidates:
    def test_crypto_pair_passes_through(self):
        assert mi._yf_symbol_candidates("BTC-USD", "CRYPTO") == ["BTC-USD"]

    def test_suffixed_tsx_passes_through(self):
        assert mi._yf_symbol_candidates("CNR.TO", "TSX") == ["CNR.TO"]

    def test_bare_crypto_symbol_gets_pair_and_never_falls_back(self):
        # Bare "BTC" resolves to an unrelated equity on Yahoo — the
        # crypto market must force the -USD pair with NO bare fallback.
        assert mi._yf_symbol_candidates("BTC", "CRYPTO") == ["BTC-USD"]


class TestInstrumentScaleMismatch:
    def _btc_trade(self, **over):
        trade = {
            "episode_num": 113, "date": "2026-07-21", "symbol": "BTC",
            "status": "open", "trade_type": "weekly",
            "stop_loss": {"price": 64500.0},
            "pick_reference_price": 28.8,
            "entry_price": None, "exit_price": None,
            "pnl_pct": None, "pnl_dollars": None,
        }
        trade.update(over)
        return trade

    def test_ep113_shape_trips(self):
        assert mi._instrument_scale_mismatch(self._btc_trade()) is True

    def test_normal_stop_does_not_trip(self):
        t = self._btc_trade(stop_loss={"price": 27.0}, pick_reference_price=28.8)
        assert mi._instrument_scale_mismatch(t) is False

    def test_pct_stop_does_not_trip(self):
        assert mi._instrument_scale_mismatch(
            self._btc_trade(stop_loss={"pct": 6.0})) is False

    def test_no_reference_does_not_trip(self):
        assert mi._instrument_scale_mismatch(
            self._btc_trade(pick_reference_price=None)) is False

    def test_migration_voids_mismatched_open_trade(self):
        tracker = {"trades": [self._btc_trade()]}
        mi._void_instrument_scale_mismatch_trades(tracker)
        t = tracker["trades"][0]
        assert t["status"] == "voided"
        assert t["void_reason"] == "instrument_scale_mismatch"
        assert t["pnl_pct"] is None

    def test_migration_voids_wrongly_closed_trade(self):
        # If the wrong listing already CLOSED before the fix merged, the
        # migration still voids it — never narrated as a market outcome.
        t = self._btc_trade(status="closed", entry_price=28.9,
                            exit_price=29.4, pnl_pct=1.7, pnl_dollars=17.0)
        tracker = {"trades": [t]}
        mi._void_instrument_scale_mismatch_trades(tracker)
        assert tracker["trades"][0]["status"] == "voided"

    def test_migration_leaves_healthy_trades_alone(self):
        healthy = self._btc_trade(
            symbol="COST", stop_loss={"price": 880.0},
            pick_reference_price=934.94, status="closed",
            entry_price=934.94, exit_price=912.97, pnl_pct=-2.35)
        tracker = {"trades": [healthy]}
        mi._void_instrument_scale_mismatch_trades(tracker)
        assert tracker["trades"][0]["status"] == "closed"


class TestVoidDisclosure:
    def _tracker_with_recent_void(self):
        return {
            "trades": [{
                "episode_num": 113,
                "date": datetime.date.today().isoformat(),
                "symbol": "BTC-USD", "status": "voided",
                "void_reason": "instrument_scale_mismatch",
            }],
            "summary": {},
        }

    def test_recent_void_disclosed_once(self):
        tracker = self._tracker_with_recent_void()
        block = mi._build_trade_review(tracker, episode_num=116)
        assert "VOIDED" in block
        assert tracker["trades"][0]["void_disclosed_in_episode"] == 116
        # Second episode: already disclosed — never repeated.
        block2 = mi._build_trade_review(tracker, episode_num=117)
        assert "VOIDED" not in block2

    def test_old_void_not_resurfaced(self):
        tracker = self._tracker_with_recent_void()
        tracker["trades"][0]["date"] = "2026-06-01"
        block = mi._build_trade_review(tracker, episode_num=116)
        assert "VOIDED" not in block


class TestAlphaCaveatDataShaped:
    """Third mechanism for the twice-missed significance caveat: the
    qualifier is now a data-shaped parenthetical inside the alpha value
    itself, not an instruction sentence the model can drop."""

    def _tracker(self, significant=False):
        tracker = mi._fresh_tracker()
        tracker["benchmark"] = {"current_close": 25873.0, "ytd_pct": 11.0,
                                "inception_to_date_pct": 15.0,
                                "last_updated": "2026-07-23"}
        tracker["summary"] = {
            "matched_window_alpha_pct": 6.59,
            "matched_window_trades": 37,
            "compounded_return_pct": 18.94,
            "compounded_nasdaq_matched_pct": 12.35,
            "alpha_t_stat": 0.31,
            "alpha_statistically_significant": significant,
            "benchmark_scores": {},
        }
        return tracker

    def test_insignificant_alpha_carries_inline_parenthetical(self):
        block = mi._build_benchmark_block(self._tracker())
        assert "+6.59% (early, not yet statistically significant" in block
        # The old imperative phrasing is gone (it was dropped 5/6 times).
        assert "never quote" not in block.lower()

    def test_significant_alpha_says_so_inside_the_value(self):
        block = mi._build_benchmark_block(self._tracker(significant=True))
        assert "+6.59% (statistically significant" in block


class TestArticleCollapseAlarm:
    """run_show warns when a show's article fetch collapses vs its own
    recent median (MIT Ep115: 9 articles vs 222-337 — the digest then
    sourced every section from x.com posts). Log-only, never blocking."""

    def test_alarm_source_present(self):
        src = (_ROOT / "run_show.py").read_text(encoding="utf-8")
        assert "article_count_degraded" in src
        assert "article fetch collapsed" in src
        # Non-blocking contract: the alarm must not call _skip_episode.
        block = src.split("Source-collapse alarm")[1].split("if not articles")[0]
        assert "_skip_episode" not in block

    def test_mit_yaml_has_digest_length_lever(self):
        import yaml as _yaml
        y = _yaml.safe_load((_ROOT / "shows/modern_investing.yaml").read_text())
        assert y["llm"]["digest_expand_below_target"] is True
        assert y["llm"]["min_digest_words"] == 1500


# ---------------------------------------------------------------------------
# August 15 2026 pass — data honesty, review coverage, alarm sensitivity
# ---------------------------------------------------------------------------


class TestVerifiedWindowAlpha:
    """The spoken alpha must come only from windows we trust.

    The July 3 pass rebuilt the benchmark window to align with the pick
    date and recorded ``entry_bar_date`` on every trade it priced. It
    also declared every OLDER window untrustworthy ("old-window
    inflation") and left the backfill to an operator script that has
    never been run. ``matched_window_alpha_pct`` compounded both sets
    together, so the number the show stated on air every episode —
    +9.28% across 45 trades — was carried by the 35 trades whose windows
    the pass itself had disowned; the 10 honestly-measured trades were
    at -1.95%.
    """

    @staticmethod
    def _tracker():
        return {
            "metadata": {"position_size": 1000},
            "trades": [
                # Verified: carries entry_bar_date (only the aligned path
                # writes it).
                {"symbol": "AAA", "status": "closed", "pnl_pct": 1.0,
                 "nasdaq_return_pct": 3.0, "alpha_pct": -2.0,
                 "entry_bar_date": "2026-08-03",
                 "exit_bar_date": "2026-08-06", "pnl_dollars": 10.0},
                {"symbol": "BBB", "status": "closed", "pnl_pct": -1.0,
                 "nasdaq_return_pct": 1.0, "alpha_pct": -2.0,
                 "entry_bar_date": "2026-08-07",
                 "exit_bar_date": "2026-08-10", "pnl_dollars": -10.0},
                # Legacy: no entry_bar_date, wildly flattering window.
                {"symbol": "CCC", "status": "closed", "pnl_pct": 20.0,
                 "nasdaq_return_pct": 0.0, "alpha_pct": 20.0,
                 "pnl_dollars": 200.0},
            ],
            "summary": {},
        }

    def test_verified_subset_excludes_legacy_windows(self):
        tracker = self._tracker()
        mi._recompute_summary(tracker)
        s = tracker["summary"]
        assert s["verified_window_trades"] == 2
        assert s["unverified_window_trades"] == 1
        # Verified alpha is negative; the blended figure is dragged
        # positive by the legacy trade. They must not be the same number.
        assert s["verified_window_alpha_pct"] < 0
        assert s["matched_window_alpha_pct"] > s["verified_window_alpha_pct"]

    def test_headline_block_states_verified_figure_and_its_n(self):
        tracker = self._tracker()
        mi._recompute_summary(tracker)
        block = mi._build_portfolio_summary(tracker)
        n = tracker["summary"]["verified_window_trades"]
        # The sample size travels with the claim, in the same line.
        headline = [ln for ln in block.splitlines()
                    if "Matched-window alpha" in ln][0]
        assert f"{n} verified-window trades" in headline
        # The blended lifetime figure must never be offered as the number
        # to say out loud.
        assert "NOT for air" in block

    def test_no_verified_trades_falls_back_to_legacy_wording(self):
        tracker = {
            "metadata": {"position_size": 1000},
            "trades": [{"symbol": "CCC", "status": "closed", "pnl_pct": 5.0,
                        "nasdaq_return_pct": 1.0, "alpha_pct": 4.0,
                        "pnl_dollars": 50.0}],
            "summary": {},
        }
        mi._recompute_summary(tracker)
        assert tracker["summary"]["verified_window_trades"] == 0
        assert tracker["summary"]["verified_window_alpha_pct"] is None
        # Still produces a usable block rather than crashing or going silent.
        assert "Matched-window alpha" in mi._build_portfolio_summary(tracker)

    def test_significance_is_measured_on_the_verified_subset(self):
        tracker = self._tracker()
        mi._recompute_summary(tracker)
        s = tracker["summary"]
        assert "verified_alpha_t_stat" in s
        assert s["verified_alpha_statistically_significant"] is False


class TestReviewBacklogDrain:
    """Every closed trade is narrated exactly once — including the ones
    that closed while another trade was closing.

    The July guard fixed over-reviewing by stamping the trade it
    narrated, but only ever looked at ``closed[-1]``. Once the pick
    cadence reached roughly one a day, several trades closed between
    reviews and all but the newest were skipped permanently: 43 of 50
    closed trades had never been narrated, five of them within the
    preceding ten days, while their results still counted in the running
    totals the segment reported.
    """

    @staticmethod
    def _tracker(days_ago_list):
        today = datetime.date.today()
        return {
            "metadata": {"position_size": 1000},
            "trades": [
                {"symbol": f"S{i}", "status": "closed", "trade_type": "weekly",
                 "strategy": "test", "entry_price": 100.0, "exit_price": 101.0,
                 "pnl_pct": 1.0, "pnl_dollars": 10.0,
                 "date": (today - datetime.timedelta(days=d)).isoformat(),
                 "exit_bar_date": (today - datetime.timedelta(days=d)).isoformat()}
                for i, d in enumerate(days_ago_list)
            ],
            "summary": {"cumulative_pnl": 0.0, "total_trades": len(days_ago_list),
                        "wins": 0, "win_rate_pct": 0.0, "current_streak": 0},
        }

    def test_oldest_fresh_close_is_reviewed_first(self):
        tracker = self._tracker([5, 3, 1])
        review = mi._build_trade_review(tracker, episode_num=200)
        assert "S0" in review          # oldest fresh, not the newest
        assert tracker["trades"][0]["reviewed_in_episode"] == 200
        assert tracker["trades"][2].get("reviewed_in_episode") is None

    def test_backlog_drains_one_per_episode(self):
        tracker = self._tracker([5, 3, 1])
        seen = []
        for ep in (200, 201, 202):
            review = mi._build_trade_review(tracker, episode_num=ep)
            seen.append(next(s for s in ("S0", "S1", "S2") if s in review))
        assert seen == ["S0", "S1", "S2"]

    def test_stale_backlog_is_retired_not_narrated(self):
        # Months-old closes must never be presented as a fresh result.
        tracker = self._tracker([400, 380, 2])
        review = mi._build_trade_review(tracker, episode_num=200)
        assert "S2" in review
        assert "S0" not in review and "S1" not in review
        assert tracker["trades"][0]["review_skipped_stale"] is True
        assert tracker["trades"][1]["review_skipped_stale"] is True
        assert "review_skipped_stale" not in tracker["trades"][2]

    def test_newest_close_is_never_retired_even_when_stale(self):
        # A long pipeline outage must not silence the segment entirely.
        tracker = self._tracker([400, 380])
        review = mi._build_trade_review(tracker, episode_num=200)
        assert "S1" in review
        assert tracker["trades"][1].get("review_skipped_stale") is None

    def test_readonly_runs_do_not_retire_the_backlog(self, monkeypatch):
        monkeypatch.setenv("NERRA_HOOKS_READONLY", "1")
        tracker = self._tracker([400, 380, 2])
        mi._build_trade_review(tracker, episode_num=200)
        assert all("review_skipped_stale" not in t for t in tracker["trades"])


class TestHonestHoldLength:
    """The review states the window actually held.

    Exits are pinned to the Friday pre-market run, which prices
    Thursday's bar, so a mid-week pick resolves after one or two
    sessions. Across the ten verified-window trades the holds ran 0-6
    days (median 3) while the scripts described a five-day window.
    """

    def test_review_states_actual_hold_span(self):
        tracker = {
            "metadata": {"position_size": 1000},
            "trades": [{
                "symbol": "X.TO", "status": "closed", "trade_type": "weekly",
                "strategy": "catalyst entry", "entry_price": 53.03,
                "exit_price": 54.06, "pnl_pct": 1.94, "pnl_dollars": 19.42,
                "entry_bar_date": "2026-08-12", "exit_bar_date": "2026-08-13",
            }],
            "summary": {"cumulative_pnl": 0.0, "total_trades": 1, "wins": 1,
                        "win_rate_pct": 100.0, "current_streak": 1},
        }
        review = mi._build_trade_review(tracker, episode_num=200)
        assert "Actual hold:** 1 calendar day" in review
        assert "never call it a five-day" in review


class TestSourceDecayAlarm:
    """The collapse alarm must catch a slide, not only a cliff.

    Comparing today against the median of the last 10 episodes uses a
    baseline that decays with the problem: MIT's fetch fell from a median
    of 274 (ep90-119) to 50-64 (ep120-137) after three of its RSS sources
    began returning 403/500, and the alarm went quiet after three
    firings.
    """

    def test_long_baseline_comparison_present(self):
        src = (_ROOT / "run_show.py").read_text(encoding="utf-8")
        assert "article_count_baseline_median" in src
        assert "article fetch has DECAYED" in src
        # Still non-blocking.
        block = src.split("Source-collapse alarm")[1].split("if not articles")[0]
        assert "_skip_episode" not in block

    def test_metrics_path_sorted_by_episode_number(self):
        src = (_ROOT / "run_show.py").read_text(encoding="utf-8")
        assert "_episode_num_from_metrics_path" in src

    def test_dead_feeds_removed_from_mit(self):
        import yaml as _yaml
        y = _yaml.safe_load((_ROOT / "shows/modern_investing.yaml").read_text())
        urls = " ".join(s["url"] for s in y["sources"])
        # All three returned hard 403s to the production User-Agent.
        assert "cnbc.com" not in urls
        assert "benzinga.com" not in urls
        # Yahoo Finance was briefly among the Aug-15 replacements but is
        # on shows/_blocked_sources.yaml (blocked 2026-03-16 for editorial
        # quality) — the live probe checked reachability, the wrong axis.
        # Removed same day; the volume floor rests on the remaining
        # replacements.
        assert "finance.yahoo.com" not in urls
        assert "feeds.bloomberg.com/markets" in urls
        assert "marketwatch.com/rss" in urls

    def test_no_show_uses_a_blocked_source(self):
        """Network-wide mirror of `check_sources.py --check-blocked`.

        That check runs in the weekly source-discovery workflow, so a
        blocked source re-added to a show YAML sails through CI and only
        fails days later on the cron (exactly how Yahoo Finance shipped
        on 2026-08-15). This makes the blocklist a merge gate.
        """
        import yaml as _yaml
        blocked_file = _ROOT / "shows/_blocked_sources.yaml"
        blocked = _yaml.safe_load(blocked_file.read_text()) or {}
        patterns = [b["url"] for b in blocked.get("blocked", [])
                    if isinstance(b, dict) and b.get("url")]
        assert patterns, "blocklist parse drift — no patterns found"
        for cfg in sorted((_ROOT / "shows").glob("*.yaml")):
            if cfg.name.startswith("_"):
                continue
            y = _yaml.safe_load(cfg.read_text()) or {}
            for src in y.get("sources") or []:
                url = src.get("url", "") if isinstance(src, dict) else ""
                for pat in patterns:
                    assert pat not in url, (
                        f"{cfg.name}: source {url!r} matches blocked "
                        f"pattern {pat!r} (see shows/_blocked_sources.yaml "
                        "for the reason and date)"
                    )


class TestScriptStageModelOverride:
    """History: MIT ran a script-stage-only grok-4.6 A/B (08-15..08-18)
    until the operator-directed NETWORK 4.6 upgrade absorbed it. The pin
    is gone on purpose — MIT now inherits the network default like every
    show, and the show-level guard is that no stale per-show pin sneaks
    back in silently."""

    def test_mit_carries_no_stale_model_pins(self):
        import yaml as _yaml
        y = _yaml.safe_load((_ROOT / "shows/modern_investing.yaml").read_text())
        # Absorbed into the network default 2026-08-18 — re-adding a
        # per-show podcast_model/model pin needs a new experiments.yaml
        # entry, not a leftover.
        assert "podcast_model" not in y["llm"]
        assert "model" not in y["llm"]
        assert "fallback_model" not in y["llm"]

    def test_override_model_is_priced(self):
        from engine.tracking import GROK_PRICING
        assert "grok-4.6" in GROK_PRICING

    def test_unavailable_override_falls_back_instead_of_failing(self):
        src = (_ROOT / "engine/generator.py").read_text(encoding="utf-8")
        block = src.split("Per-stage model override")[1][:3000]
        assert "falling back" in block
        assert "config.llm.model" in block
