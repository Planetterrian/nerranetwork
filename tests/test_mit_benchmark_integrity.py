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
import itertools
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


def _frozen_datetime(today: datetime.date):
    """A stand-in for the ``datetime`` MODULE with a fixed ``date.today()``.

    Patched onto the hook module's own ``datetime`` attribute, so the real
    module — which pandas, numpy and yfinance initialise against — is never
    touched. ``date`` is a genuine subclass, not a mock, so every
    ``isinstance``/arithmetic path behaves normally.
    """

    class _Date(datetime.date):
        @classmethod
        def today(cls) -> datetime.date:
            return today

    return SimpleNamespace(
        date=_Date,
        datetime=datetime.datetime,
        timedelta=datetime.timedelta,
        timezone=datetime.timezone,
        time=datetime.time,
    )


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

# Fixtures that represent THE CURRENT RECORD must sit inside the rulebook
# era (shows/_trading_policy.yaml), because the on-air scoreboard reports
# the era and nothing else. A dateless trade is deliberately treated as
# out-of-era by the hook — a legacy row with a missing date must never
# drift into the record the show is judged on.
_ERA_DATE = "2026-08-20"


_BARS = [
    (datetime.date(2026, 6, 26), 100.0, 101.0),  # Fri
    (datetime.date(2026, 6, 29), 102.0, 103.0),  # Mon
    (datetime.date(2026, 6, 30), 103.5, 104.0),  # Tue
    (datetime.date(2026, 7, 1), 104.5, 105.0),   # Wed
    (datetime.date(2026, 7, 2), 105.5, 106.0),   # Thu
]


# Six sessions, so a Monday pick has a full 5-session horizon plus one
# spare bar the exit must NOT drift onto (2026-08-18 policy).
_BARS_WEEK = _BARS + [
    (datetime.date(2026, 7, 3), 106.5, 107.0),   # Fri
    (datetime.date(2026, 7, 6), 107.5, 108.0),   # Mon — beyond the horizon
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
        entry, _ = mi._pick_weekly_bars(_BARS_WEEK, datetime.date(2026, 7, 1))
        assert entry[0] == datetime.date(2026, 7, 1)

    def test_exit_is_the_horizon_session_not_the_latest_bar(self):
        # 2026-08-18 policy: a weekly hold is exactly 5 sessions. Monday
        # 06-29 -> sessions Mon,Tue,Wed,Thu,Fri, so the exit is Friday
        # 07-03 even though a later bar (Mon 07-06) exists. Previously the
        # exit was window[-1], which made the holding period depend on
        # when the evaluating run happened to look.
        entry, exit_ = mi._pick_weekly_bars(
            _BARS_WEEK, datetime.date(2026, 6, 29))
        assert entry[0] == datetime.date(2026, 6, 29)
        assert exit_[0] == datetime.date(2026, 7, 3)

    def test_every_weekday_pick_gets_the_same_holding_period(self):
        # The whole point: alpha must be attributable to the pick, not to
        # which weekday it landed on.
        bars = _BARS_WEEK + [
            (datetime.date(2026, 7, 7), 108.5, 109.0),
            (datetime.date(2026, 7, 8), 109.5, 110.0),
            (datetime.date(2026, 7, 9), 110.5, 111.0),
        ]
        spans = []
        for pick in (datetime.date(2026, 6, 29), datetime.date(2026, 6, 30),
                     datetime.date(2026, 7, 1)):
            entry, exit_ = mi._pick_weekly_bars(bars, pick)
            spans.append(sum(1 for b in bars
                             if entry[0] <= b[0] <= exit_[0]))
        assert spans == [5, 5, 5]

    def test_holds_open_until_the_horizon_has_printed(self):
        # Four sessions available, five required — entry known, no exit.
        entry, exit_ = mi._pick_weekly_bars(_BARS, datetime.date(2026, 6, 29))
        assert entry[0] == datetime.date(2026, 6, 29)
        assert exit_ is None

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
        bars = _BARS_WEEK + [
            (datetime.date(2026, 7, 7), 108.5, 109.0),
            (datetime.date(2026, 7, 8), 109.5, 110.0),
        ]
        with patch.object(mi, "_fetch_bars_for_trade", return_value=bars), \
             patch.object(mi, "_fetch_history_bars", return_value=bars):
            mi._close_trade(trade, _tracker())
        assert trade["entry_bar_date"] == "2026-07-01"  # not Monday 06-29
        assert trade["entry_price"] == 104.5

    def test_price_discontinuity_flagged_not_voided(self, caplog):
        import logging
        trade = {
            "symbol": "CNR", "market": "TSX", "trade_type": "weekly",
            "date": "2026-06-29", "pick_reference_price": 300.0,
        }
        with patch.object(mi, "_fetch_bars_for_trade",
                          return_value=_BARS_WEEK), \
             patch.object(mi, "_fetch_history_bars",
                          return_value=_BARS_WEEK), \
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
                "nasdaq_return_pct": ndq, "alpha_pct": pnl - ndq,
                "date": _ERA_DATE, "entry_bar_date": _ERA_DATE}

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
        return {"status": "closed", "confidence": conf, "alpha_pct": alpha,
                "date": _ERA_DATE, "entry_bar_date": _ERA_DATE}

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
            "date": _ERA_DATE, "entry_bar_date": _ERA_DATE,
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

    def test_legacy_trades_are_excluded_from_every_index_leg(self):
        """SUPERSEDED 2026-08-18 (was: legacy trades fall back to the
        NASDAQ field).

        The fallback let the NASDAQ leg count trades no other leg could
        see: ``nasdaq_return_pct`` exists on 45 trades, ``benchmark_returns``
        on 10, so the sweep put a 45-trade NASDAQ score beside 10-trade
        S&P/TSX scores and announced "beating 1 of 3". The July-18 n>=5
        gate passed it because it checks each sample's SIZE, not that the
        legs share the same trades — and the number it produced (+9.28%)
        then contradicted the verified headline (-1.95%) in the same
        paragraph. Every leg now reads the same verified windows.
        """
        legacy = {"status": "closed", "pnl_pct": 5.0, "pnl_dollars": 50.0,
                  "nasdaq_return_pct": 2.0, "alpha_pct": 3.0}
        tracker = {"metadata": {"position_size": 1000}, "summary": {},
                   "trades": [legacy]}
        mi._recompute_summary(tracker)
        scores = tracker["summary"]["benchmark_scores"]
        # No index leg is scored from a trade with no benchmark_returns.
        assert scores == {}
        # The legacy figure is still available for the blended pair, which
        # the performance page and the recompute script continue to use.
        assert tracker["summary"]["matched_window_trades"] == 1

    def test_index_legs_always_share_the_same_trade_count(self):
        """The sweep is a like-for-like comparison or it is nothing."""
        tracker = {"metadata": {"position_size": 1000}, "summary": {},
                   "trades": [
                       self._closed(10.0, 2.0, sp500=1.0, tsx=-1.0),
                       self._closed(-2.0, 1.0, sp500=0.5, tsx=0.2),
                       # Legacy trade: must not inflate the NASDAQ leg.
                       {"status": "closed", "pnl_pct": 30.0,
                        "pnl_dollars": 300.0, "nasdaq_return_pct": 0.0,
                        "alpha_pct": 30.0},
                   ]}
        mi._recompute_summary(tracker)
        scores = tracker["summary"]["benchmark_scores"]
        assert len({s["trades"] for s in scores.values()}) == 1
        assert scores["nasdaq"]["trades"] == 2

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

    _seq = itertools.count()

    def _closed(self, alpha, rules):
        # Era-dated (2026-08-19): the scoreboard scores the current record
        # only. Its control group used to be the pre-era trades, so it was
        # comparing new trades against old ones and calling the difference
        # rule effectiveness.
        era = mi.era_inception() or datetime.date(2026, 8, 18)
        d = (era + datetime.timedelta(days=next(self._seq) % 60)).isoformat()
        return {"status": "closed", "alpha_pct": alpha, "pnl_pct": alpha,
                "nasdaq_return_pct": 0.0, "date": d, "entry_bar_date": d,
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
        # The CONTROL group needs a real sample too (2026-08-19): retiring
        # a rule because it lost to four trades is the same coin-flip
        # reasoning the July-18 pass removed from the index sweep. Both
        # arms must clear _MIN_SAMPLE_TRADES.
        lessons = {"entries": [self._RULE_A]}
        tracker = {"trades": (
            [self._closed(0.0, ["LL-017"]) for _ in range(8)]
            + [self._closed(1.0, []) for _ in range(5)]
        )}
        board = mi._build_rule_scoreboard(lessons, tracker)
        assert "RETIREMENT CANDIDATE" in board
        assert "keep obeying it until retired" in board  # never auto-retired

    def test_too_few_stamped_trades_says_so_rather_than_going_silent(self):
        """CHANGED 2026-08-19: was `== ""`.

        An empty block is indistinguishable from a block that had nothing
        to report, and silence is how five bogus RETIREMENT CANDIDATE
        verdicts rode unnoticed. Thin evidence now says it is thin.
        """
        lessons = {"entries": [self._RULE_A]}
        tracker = {"trades": [self._closed(2.0, ["LL-017"])]}
        board = mi._build_rule_scoreboard(lessons, tracker)
        assert "RETIREMENT CANDIDATE" not in board
        assert "not measurable yet" in board or "UNMEASURED" in board

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
    # Five sessions is a full weekly horizon (2026-08-18 policy), so the
    # no-stop control below exits Friday rather than drifting to whatever
    # bar arrived last.
    (datetime.date(2026, 7, 3), 97.5, 98.0, 96.5),      # Fri
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
        assert trade["exit_bar_date"] == "2026-07-03"  # 5th session

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
                "alpha_pct": alpha, "nasdaq_return_pct": 0.0,
                "date": _ERA_DATE, "entry_bar_date": _ERA_DATE}

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
        # NOTE: patch the hook's module-local ``datetime`` NAME, never the
        # real datetime module. ``patch.object(mi.datetime, "date", ...)``
        # replaced datetime.date GLOBALLY with a MagicMock, and any pandas
        # import landing inside that window died in its C-extension setup
        # ("datetime.date is not a type object"), leaving pandas
        # half-initialised in sys.modules for the rest of the session —
        # every later "import yfinance" then failed with "numpy._core.
        # multiarray failed to import". That took out all 38 tests in
        # test_tesla_hook.py whenever this file ran first, locally AND in
        # CI (PR #1027). A real date subclass keeps isinstance/type checks
        # honest where a mock could not.
        # One printed session — Thursday's own bar — which is what the
        # Friday pre-market run can actually see. Every sibling test
        # patches the fetch; this one did not, and it passed only because
        # the old global datetime patch ALSO broke the pandas import
        # inside _fetch_bars_for_trade, so the fetch raised and no bars
        # came back. With the datetime patch corrected the fetch worked,
        # pulled 14 REAL COST bars off the network, and the horizon was
        # complete — so the trade closed and this test failed (CI, #1027).
        # It was passing for the wrong reason and hitting the live market.
        thursday_bar = [(thursday, 100.0, 101.0, 99.0)]
        with patch.object(mi, "datetime", _frozen_datetime(friday)), \
             patch.object(mi, "_fetch_bars_for_trade", return_value=thursday_bar), \
             patch.object(mi, "_snapshot_trade") as snap, \
             patch.object(mi, "_close_trade") as close, \
             patch.object(mi, "_save_tracker"):
            mi._evaluate_open_trade(tracker, Path("/nope"))
        close.assert_not_called()
        snap.assert_called_once()

    def test_closes_once_the_horizon_has_printed(self):
        """SUPERSEDED 2026-08-18 (was: a Monday pick closes on Friday).

        The exit is no longer a weekday. It is five printed sessions, so
        the same pick gets the same holding period whichever day it was
        made — which is what makes per-trade alpha attributable to the
        pick instead of to the calendar.
        """
        monday = datetime.date(2026, 7, 6)
        bars = [
            (datetime.date(2026, 7, 6), 100.0, 101.0, 99.0),
            (datetime.date(2026, 7, 7), 101.0, 102.0, 100.0),
            (datetime.date(2026, 7, 8), 102.0, 103.0, 101.0),
            (datetime.date(2026, 7, 9), 103.0, 104.0, 102.0),
            (datetime.date(2026, 7, 10), 104.0, 105.0, 103.0),
        ]
        tracker = {"metadata": {"position_size": 1000}, "summary": {},
                   "trades": [{"symbol": "GIS", "market": "NYSE",
                               "trade_type": "weekly", "status": "open",
                               "date": monday.isoformat()}]}
        with patch.object(mi, "_fetch_bars_for_trade", return_value=bars), \
             patch.object(mi, "_close_trade") as close, \
             patch.object(mi, "_save_tracker"):
            mi._evaluate_open_trade(tracker, Path("/nope"))
        close.assert_called_once()

    def test_stays_open_while_the_horizon_is_incomplete(self):
        bars = [
            (datetime.date(2026, 7, 6), 100.0, 101.0, 99.0),
            (datetime.date(2026, 7, 7), 101.0, 102.0, 100.0),
        ]
        tracker = {"metadata": {"position_size": 1000}, "summary": {},
                   "trades": [{"symbol": "GIS", "market": "NYSE",
                               "trade_type": "weekly", "status": "open",
                               "date": "2026-07-06"}]}
        with patch.object(mi, "_fetch_bars_for_trade", return_value=bars), \
             patch.object(mi, "_close_trade") as close, \
             patch.object(mi, "_snapshot_trade"), \
             patch.object(mi, "_save_tracker"):
            mi._evaluate_open_trade(tracker, Path("/nope"))
        close.assert_not_called()

    def test_a_fetch_failure_never_closes_a_trade(self):
        # "No bars" must read as not-due, never as due-now: otherwise one
        # bad network day closes every open position at whatever price
        # came back.
        tracker = {"metadata": {"position_size": 1000}, "summary": {},
                   "trades": [{"symbol": "GIS", "market": "NYSE",
                               "trade_type": "weekly", "status": "open",
                               "date": "2026-07-06"}]}
        with patch.object(mi, "_fetch_bars_for_trade", return_value=None), \
             patch.object(mi, "_close_trade") as close, \
             patch.object(mi, "_snapshot_trade"), \
             patch.object(mi, "_save_tracker"):
            mi._evaluate_open_trade(tracker, Path("/nope"))
        close.assert_not_called()

    def test_shadow_exit_calendar_matches(self):
        """SUPERSEDED 2026-08-18: the shadow layer follows the session
        horizon, not the Friday calendar — otherwise it stops being a
        check on the sim and becomes a second opinion about weekdays."""
        from execution import shadow as sh
        for pick in (datetime.date(2026, 7, 6), datetime.date(2026, 7, 8),
                     datetime.date(2026, 7, 9), datetime.date(2026, 7, 10)):
            due = sh._exit_due_date(pick, "weekly")
            sessions = sum(
                1 for i in range((due - pick).days + 1)
                if (pick + datetime.timedelta(days=i)).weekday() <= 4
            )
            assert sessions == 5, f"{pick} -> {due} spanned {sessions}"


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
                 "date": _ERA_DATE, "entry_bar_date": _ERA_DATE,
                 "exit_bar_date": "2026-08-27", "pnl_dollars": 10.0},
                {"symbol": "BBB", "status": "closed", "pnl_pct": -1.0,
                 "nasdaq_return_pct": 1.0, "alpha_pct": -2.0,
                 "date": _ERA_DATE, "entry_bar_date": _ERA_DATE,
                 "exit_bar_date": "2026-08-27", "pnl_dollars": -10.0},
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
        n = tracker["summary"]["era_trades"]
        # The sample size travels with the claim, in the same line.
        headline = [ln for ln in block.splitlines()
                    if "Matched-window alpha" in ln][0]
        assert f"{n} rules-based trades" in headline
        # The blended lifetime figure must never be offered as the number
        # to say out loud, and the block must say the record is era-scoped.
        assert "NOT blended into it" in block
        blended = tracker["summary"]["matched_window_alpha_pct"]
        assert f"{blended:+.1f}%" not in block

    def test_no_verified_trades_falls_back_to_legacy_wording(self, monkeypatch):
        # With no era configured the ordering is verified -> blended. An
        # ACTIVE era short-circuits both, which is tested separately.
        monkeypatch.setattr(mi, "load_policy", lambda: {
            "era": {}, "exit": {"horizon_sessions": {"weekly": 5, "flash": 1}}})
        monkeypatch.setattr(mi, "era_inception", lambda: None)
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


class TestSingleAlphaSource:
    """Both prompt blocks must quote the SAME alpha from the SAME subset.

    The August 15 pass switched ``_build_portfolio_summary`` to the
    verified-window figure and left ``_build_benchmark_block`` — the
    "state every episode" scoreboard — on the blended one. Both reach the
    same prompt, so the model was handed two different alphas under two
    labels and fused them: Ep138 aired "+9.28% across forty-five
    VERIFIED-window trades", the inflated number wearing the honest
    label. Ep139 quoted the blend outright. Only Ep140 was right.
    """

    @staticmethod
    def _tracker():
        return {
            "metadata": {"position_size": 1000},
            "benchmark": {"current_close": 26000.0, "ytd_pct": 15.0,
                          "inception_to_date_pct": 19.0},
            "alpha": {"ytd_pct": -14.0, "inception_to_date_pct": -18.0},
            "trades": [
                {"symbol": "AAA", "status": "closed", "pnl_pct": 1.0,
                 "nasdaq_return_pct": 3.0, "alpha_pct": -2.0,
                 "pnl_dollars": 10.0, "date": _ERA_DATE,
                 "entry_bar_date": _ERA_DATE, "exit_bar_date": "2026-08-27",
                 "benchmark_returns": {"nasdaq": 3.0, "sp500": 2.0, "tsx": 1.0}},
                {"symbol": "BBB", "status": "closed", "pnl_pct": -1.0,
                 "nasdaq_return_pct": 1.0, "alpha_pct": -2.0,
                 "pnl_dollars": -10.0, "date": _ERA_DATE,
                 "entry_bar_date": _ERA_DATE, "exit_bar_date": "2026-08-27",
                 "benchmark_returns": {"nasdaq": 1.0, "sp500": 1.0, "tsx": 1.0}},
                # Legacy window — flattering, and must reach neither block.
                {"symbol": "CCC", "status": "closed", "pnl_pct": 40.0,
                 "nasdaq_return_pct": 0.0, "alpha_pct": 40.0,
                 "pnl_dollars": 400.0},
            ],
            "summary": {},
        }

    def test_both_blocks_quote_the_verified_figure(self):
        tracker = self._tracker()
        mi._recompute_summary(tracker)
        verified = tracker["summary"]["verified_window_alpha_pct"]
        blended = tracker["summary"]["matched_window_alpha_pct"]
        assert verified != blended  # fixture is only meaningful if they differ

        bench = mi._build_benchmark_block(tracker)
        port = mi._build_portfolio_summary(tracker)
        for block in (bench, port):
            assert f"{verified:+.2f}%" in block or f"{verified:+.1f}%" in block
            assert f"{blended:+.2f}%" not in block
            assert f"{blended:+.1f}%" not in block

    def test_trade_count_spoken_is_the_verified_count(self):
        tracker = self._tracker()
        mi._recompute_summary(tracker)
        n = tracker["summary"]["era_trades"]
        assert n == 2
        bench = mi._build_benchmark_block(tracker)
        # The count travels with the number, and it is never the blend's.
        assert f"across {n} rules-based trades" in bench
        assert "across 3 " not in bench

    def test_significance_follows_the_verified_subset(self):
        tracker = self._tracker()
        mi._recompute_summary(tracker)
        bench = mi._build_benchmark_block(tracker)
        t = tracker["summary"]["era_alpha_t_stat"]
        if t is not None:
            assert f"t={t:+.2f}" in bench

    def test_falls_back_to_blended_and_labels_it_when_no_verified_windows(
            self, monkeypatch):
        monkeypatch.setattr(mi, "load_policy", lambda: {
            "era": {}, "exit": {"horizon_sessions": {"weekly": 5, "flash": 1}}})
        monkeypatch.setattr(mi, "era_inception", lambda: None)
        tracker = self._tracker()
        for t in tracker["trades"]:
            t.pop("entry_bar_date", None)
            t.pop("benchmark_returns", None)
        mi._recompute_summary(tracker)
        assert tracker["summary"]["verified_window_trades"] == 0
        bench = mi._build_benchmark_block(tracker)
        # Still speaks a scoreboard, but never calls the blend "verified".
        assert "benchmarked trades" in bench
        assert "verified-window trades" not in bench


class TestRecomputeMatcherCannotBackdate:
    """The realignment script must not re-create the bug it repairs.

    ``recompute_mit_benchmarks`` fetches bars from ten days BEFORE the
    pick (to tolerate date skew) and used to return the first bar whose
    price fell inside the +/-2% tolerance while scanning that window
    forward. For any stock in a tight range an earlier bar qualifies, so
    the entry matched pre-pick and the script reproduced exactly the
    hindsight backdating it exists to remove. A 2026-08-18 dry run
    against live market data flagged 25 trades as "backdated" — including
    all ten whose entry bars were already correct (Ep135 X.TO 2026-08-12
    -> 2026-08-04). Running --apply would have corrupted the record.
    """

    @staticmethod
    def _rc():
        import importlib
        return importlib.import_module("scripts.recompute_mit_benchmarks")

    def test_entry_never_matches_a_bar_before_the_pick(self):
        rc = self._rc()
        pick = datetime.date(2026, 8, 12)
        bars = [
            # Pre-pick bars inside the price tolerance — must be ignored.
            (datetime.date(2026, 8, 4), 53.00, 53.10, 52.9),
            (datetime.date(2026, 8, 11), 53.02, 53.20, 52.8),
            # The true entry bar, on the pick date.
            (datetime.date(2026, 8, 12), 53.03, 53.71, 52.7),
        ]
        bar = rc._match_bar(bars, 53.03, field=1, not_before=pick)
        assert bar[0] == pick

    def test_exit_never_precedes_entry(self):
        rc = self._rc()
        entry_date = datetime.date(2026, 8, 12)
        bars = [
            (datetime.date(2026, 8, 5), 54.05, 54.06, 53.0),
            (datetime.date(2026, 8, 12), 53.03, 53.71, 52.7),
            (datetime.date(2026, 8, 13), 53.80, 54.06, 53.5),
        ]
        bar = rc._match_bar(bars, 54.06, field=2, not_before=entry_date)
        assert bar[0] == datetime.date(2026, 8, 13)

    def test_closest_price_wins_not_the_first_seen(self):
        rc = self._rc()
        d = datetime.date(2026, 8, 12)
        bars = [
            (d, 53.90, 54.00, 53.0),                                  # 1.6% off
            (datetime.date(2026, 8, 13), 53.05, 54.00, 53.0),         # 0.04% off
        ]
        bar = rc._match_bar(bars, 53.03, field=1, not_before=d)
        assert bar[0] == datetime.date(2026, 8, 13)

    def test_no_qualifying_bar_returns_none(self):
        rc = self._rc()
        d = datetime.date(2026, 8, 12)
        bars = [(datetime.date(2026, 8, 4), 53.03, 53.10, 52.9)]
        assert rc._match_bar(bars, 53.03, field=1, not_before=d) is None


class TestTradingPolicy:
    """The rulebook is the rules — code and file must not drift."""

    def test_policy_file_is_loadable_and_complete(self):
        pol = mi.load_policy()
        assert pol["exit"]["horizon_sessions"]["weekly"] >= 2
        assert pol["exit"]["horizon_sessions"]["flash"] == 1
        assert pol["era"]["inception_date"]
        assert pol["entry"]["rule"] == "first_session_on_or_after_pick"

    def test_unreadable_policy_falls_back_without_changing_the_rules(
            self, monkeypatch):
        monkeypatch.setattr(mi, "_POLICY_CACHE", None)
        monkeypatch.setattr(mi, "POLICY_PATH", Path("/nonexistent/policy.yaml"))
        pol = mi.load_policy()
        assert pol["exit"]["horizon_sessions"]["weekly"] == 5
        monkeypatch.setattr(mi, "_POLICY_CACHE", None)

    def test_horizon_matches_the_file(self):
        import yaml as _yaml
        pol = _yaml.safe_load(
            (_ROOT / "shows/_trading_policy.yaml").read_text(encoding="utf-8"))
        assert mi.horizon_sessions("weekly") == \
            pol["exit"]["horizon_sessions"]["weekly"]

    def test_sim_and_shadow_agree_on_the_holding_period(self):
        """If these drift, the shadow ledger stops being a check on the
        sim and becomes a second opinion about the calendar."""
        from execution import shadow as sh
        horizon = mi.horizon_sessions("weekly")
        for pick in (datetime.date(2026, 8, 17), datetime.date(2026, 8, 18),
                     datetime.date(2026, 8, 19), datetime.date(2026, 8, 20),
                     datetime.date(2026, 8, 21)):
            due = sh._exit_due_date(pick, "weekly")
            sessions = sum(
                1 for i in range((due - pick).days + 1)
                if (pick + datetime.timedelta(days=i)).weekday() <= 4)
            assert sessions == horizon


class TestEraScopedRecord:
    """The on-air record is the rulebook era and nothing else."""

    @staticmethod
    def _tracker(in_era_trades=0):
        era = mi.era_inception() or datetime.date(2026, 8, 18)
        trades = [
            # Pre-era: real, published, and never part of the on-air record.
            {"symbol": "OLD", "status": "closed", "pnl_pct": 30.0,
             "pnl_dollars": 300.0, "nasdaq_return_pct": 1.0,
             "alpha_pct": 29.0, "date": "2026-07-01",
             "entry_bar_date": "2026-07-01", "exit_bar_date": "2026-07-08",
             "benchmark_returns": {"nasdaq": 1.0, "sp500": 1.0, "tsx": 1.0}},
        ]
        for i in range(in_era_trades):
            d = (era + datetime.timedelta(days=i)).isoformat()
            trades.append({
                "symbol": f"NEW{i}", "status": "closed", "pnl_pct": -1.0,
                "pnl_dollars": -10.0, "nasdaq_return_pct": 1.0,
                "alpha_pct": -2.0, "date": d, "entry_bar_date": d,
                "exit_bar_date": d,
                "benchmark_returns": {"nasdaq": 1.0, "sp500": 1.0, "tsx": 1.0},
            })
        return {"metadata": {"position_size": 1000}, "summary": {},
                "benchmark": {"current_close": 26000.0, "ytd_pct": 15.0,
                              "inception_to_date_pct": 19.0},
                "alpha": {"ytd_pct": -14.0, "inception_to_date_pct": -18.0},
                "trades": trades}

    def test_pre_era_trades_are_excluded_from_the_record(self):
        tracker = self._tracker(in_era_trades=2)
        mi._recompute_summary(tracker)
        s = tracker["summary"]
        assert s["era_trades"] == 2          # not 3
        assert s["era_alpha_pct"] < 0        # the +29% legacy trade is out

    def test_empty_era_reports_no_alpha_instead_of_reaching_back(self):
        tracker = self._tracker(in_era_trades=0)
        mi._recompute_summary(tracker)
        bench = mi._build_benchmark_block(tracker)
        port = mi._build_portfolio_summary(tracker)
        assert "NO closed trades yet" in bench
        assert "no alpha to report" in port
        # The flattering legacy number must appear in neither block.
        for block in (bench, port):
            assert "+29.0" not in block and "+29.00" not in block

    def test_lifetime_totals_are_labelled_history_while_the_era_is_empty(self):
        tracker = self._tracker(in_era_trades=0)
        mi._recompute_summary(tracker)
        assert "HISTORY ONLY" in mi._build_portfolio_summary(tracker)

    def test_both_blocks_agree_once_the_era_has_trades(self):
        tracker = self._tracker(in_era_trades=3)
        mi._recompute_summary(tracker)
        n = tracker["summary"]["era_trades"]
        bench = mi._build_benchmark_block(tracker)
        port = mi._build_portfolio_summary(tracker)
        assert f"{n} rules-based trades" in bench
        assert f"{n} rules-based trades" in port

    def test_small_era_sample_is_called_a_scoreboard_not_evidence(self):
        tracker = self._tracker(in_era_trades=2)
        mi._recompute_summary(tracker)
        assert "not evidence" in mi._build_benchmark_block(tracker)


class TestReproducibleDecisions:
    """Entry, exit and the invalidation condition are recorded on the
    trade, so a listener can recompute every number the show reports."""

    def test_pick_records_the_policy_and_horizon(self):
        digest = (
            "### Practice Investment of the Day\n"
            "**Trade Type:** Weekly Hold\n"
            "**Today's Pick:** ABC — Alpha Beta Corp\n"
            "**Market:** NASDAQ\n"
            "**Confidence Level:** High\n"
            "**Invalidation:** Guidance below $4.10 on the Nov 2 call kills it.\n"
        )
        trade = mi._extract_trade_from_digest(digest, 141)
        assert trade["policy_version"] == mi.load_policy()["version"]
        assert trade["horizon_sessions"] == mi.horizon_sessions("weekly")
        assert "4.10" in trade["invalidation"]
        assert trade["confidence"] == "High"

    def test_confidence_accepts_both_label_forms(self):
        for label in ("**Confidence Level:** Low", "**Confidence:** Low"):
            digest = ("### Practice Investment of the Day\n"
                      "**Today's Pick:** ABC — Alpha Beta\n" + label + "\n")
            assert mi._extract_trade_from_digest(digest, 1)["confidence"] == "Low"

    def test_calibration_states_the_rubric_and_is_era_scoped(self):
        tracker = {"trades": [
            {"status": "closed", "confidence": "Medium", "alpha_pct": 5.0,
             "date": "2026-07-01"},   # pre-era — must not be graded
        ]}
        block = mi.get_mit_confidence_calibration(tracker)
        assert "RUBRIC" in block
        assert "0 graded pick(s) in this era" in block


class TestOptionsPositions:
    """The show teaches options in ~4 of 5 episodes and had never traded
    one: 0 of 61 positions used a derivative while "covered call" alone
    had been taught 33 times.

    The constraint that shapes the design: an option premium cannot be
    reconstructed after the fact from free data. So the premium is a real
    quote recorded at pick time and the payoff at expiry is arithmetic
    with no free parameters. A premium is NEVER estimated — if the chain
    cannot be quoted the pick degrades to equity.
    """

    def test_covered_call_payoff_matches_hand_calculation(self):
        pos = {"structure": "covered_call", "contracts": 1, "strike": 43.0,
               "premium": 0.58, "capital_usd": 4120.0, "underlying_entry": 41.20}
        # Assigned: shares capped at the strike, premium kept.
        r = mi.option_payoff(pos, 46.00)
        assert r["pnl_dollars"] == pytest.approx(43 * 100 + 0.58 * 100 - 4120)
        assert r["assigned"] is True
        # Unassigned below the strike: share move plus the premium.
        r2 = mi.option_payoff(pos, 39.00)
        assert r2["pnl_dollars"] == pytest.approx(39 * 100 + 0.58 * 100 - 4120)
        assert r2["assigned"] is False
        # Upside is capped — that is the trade-off the show must explain.
        assert (mi.option_payoff(pos, 99.0)["pnl_dollars"]
                == pytest.approx(r["pnl_dollars"]))

    def test_cash_secured_put_payoff_matches_hand_calculation(self):
        pos = {"structure": "cash_secured_put", "contracts": 1, "strike": 38.0,
               "premium": 0.75, "capital_usd": 3800.0, "underlying_entry": 41.20}
        assert mi.option_payoff(pos, 41.0)["pnl_dollars"] == pytest.approx(75.0)
        assert mi.option_payoff(pos, 36.0)["pnl_dollars"] == pytest.approx(
            0.75 * 100 - (38 - 36) * 100)
        # Gain is capped at the premium however far the underlying rises.
        assert mi.option_payoff(pos, 200.0)["pnl_dollars"] == pytest.approx(75.0)

    def test_returns_are_on_capital_actually_committed(self):
        pos = {"structure": "covered_call", "contracts": 1, "strike": 43.0,
               "premium": 0.58, "capital_usd": 4120.0, "underlying_entry": 41.20}
        r = mi.option_payoff(pos, 46.00)
        assert r["pnl_pct"] == pytest.approx(r["pnl_dollars"] / 4120 * 100, abs=1e-3)

    def test_strike_selection_is_deterministic_and_skips_itm(self):
        calls = [
            {"strike": 40, "bid": 1.9, "ask": 2.1},    # in the money — skip
            {"strike": 43, "bid": 0.55, "ask": 0.61},  # closest to 4% OTM
            {"strike": 44, "bid": 0.30, "ask": 0.36},
        ]
        assert mi._select_contract(calls, 41.20, "covered_call") == (43.0, 0.58)

    def test_contract_without_a_real_quote_is_never_filled(self):
        calls = [{"strike": 43, "bid": 0, "ask": 0, "lastPrice": 0}]
        assert mi._select_contract(calls, 41.20, "covered_call") is None

    def test_expiry_selection_follows_the_policy_window(self):
        pick = datetime.date(2026, 8, 19)
        # 2 days out is inside no window; 30 days is; 58 is too far.
        chosen = mi._select_expiry(
            ["2026-08-21", "2026-09-18", "2026-10-16"], pick)
        assert chosen == "2026-09-18"
        assert mi._select_expiry(["2026-08-21"], pick) is None

    def test_settlement_uses_the_last_bar_on_or_before_expiry(self):
        trade = {"symbol": "MFC.TO", "date": "2026-08-19",
                 "structure": "covered_call",
                 "option": {"structure": "covered_call", "expiry": "2026-09-18",
                            "strike": 43.0, "premium": 0.58, "contracts": 1,
                            "underlying_entry": 41.20, "capital_usd": 4120.0}}
        bars = [(datetime.date(2026, 8, 19), 41.0, 41.20, 40.8),
                (datetime.date(2026, 9, 18), 45.6, 46.00, 45.2),
                (datetime.date(2026, 9, 21), 46.5, 47.00, 46.0)]  # after expiry
        with patch.object(mi, "_annotate_trade_with_nasdaq"):
            assert mi._settle_option_trade(trade, trade["option"], bars, {}) is True
        assert trade["exit_bar_date"] == "2026-09-18"   # not the later bar
        assert trade["pnl_dollars"] == pytest.approx(238.0)

    def test_no_expiry_bar_yet_leaves_the_trade_open(self):
        trade = {"symbol": "X", "date": "2026-08-19",
                 "option": {"structure": "covered_call", "expiry": "2026-09-18",
                            "strike": 43.0, "premium": 0.58, "contracts": 1,
                            "underlying_entry": 41.2, "capital_usd": 4120.0}}
        bars = [(datetime.date(2026, 8, 19), 41.0, 41.2, 40.8)]
        assert mi._settle_option_trade(trade, trade["option"], bars, {}) is False
        assert trade.get("status") != "closed"

    def test_structure_is_parsed_from_the_digest(self):
        for text, expected in (
            ("**Structure:** Covered Call", "covered_call"),
            ("**Structure:** Cash-Secured Put", "cash_secured_put"),
            ("**Structure:** Shares", "long_equity"),
            ("", "long_equity"),                     # absent => equity
        ):
            digest = ("### Practice Investment of the Day\n"
                      "**Today's Pick:** ABC — Alpha Beta\n" + text + "\n")
            assert mi._extract_trade_from_digest(digest, 1)["structure"] == expected

    def test_policy_declares_only_the_structures_the_code_settles(self):
        allowed = set(mi.load_policy()["options"]["structures"])
        assert allowed <= set(mi.OPTION_STRUCTURES)
        for structure in allowed:
            mi.option_payoff(
                {"structure": structure, "contracts": 1, "strike": 10.0,
                 "premium": 0.5, "capital_usd": 1000.0}, 11.0)


class TestRuleScoreboardHonesty:
    """The scoreboard reported five identical RETIREMENT CANDIDATE verdicts
    (same 10 trades, same -0.17% vs +0.43%) because all five rules were
    stamped on exactly the same trades — one undivided sample presented as
    five findings, with the pre-era trades as its control group."""

    @staticmethod
    def _closed(alpha, rules, i):
        era = mi.era_inception() or datetime.date(2026, 8, 18)
        d = (era + datetime.timedelta(days=i)).isoformat()
        return {"status": "closed", "alpha_pct": alpha, "pnl_pct": alpha,
                "nasdaq_return_pct": 0.0, "date": d, "entry_bar_date": d,
                "rules_in_effect": rules}

    _RULES = {"entries": [{"id": "LL-A", "status": "active",
                           "adjustment": "Require volume confirmation"},
                          {"id": "LL-B", "status": "active",
                           "adjustment": "Cap sector concentration"},
                          {"id": "LL-C", "status": "active",
                           "adjustment": "Wait for a catalyst"}]}

    def test_identical_rule_sets_produce_no_verdict(self):
        tracker = {"trades": [self._closed(1.0, ["LL-A", "LL-B"], i)
                              for i in range(12)]}
        out = mi._build_rule_scoreboard(self._RULES, tracker)
        assert "not measurable yet" in out
        assert "RETIREMENT CANDIDATE" not in out

    def test_collinear_rules_are_flagged_as_one_piece_of_evidence(self):
        tracker = {"trades": [self._closed(2.0, ["LL-A", "LL-B"], i)
                              for i in range(8)]
                   + [self._closed(-1.0, ["LL-C"], i + 8) for i in range(8)]}
        out = mi._build_rule_scoreboard(self._RULES, tracker)
        assert "indistinguishable from" in out

    def test_pre_era_trades_are_not_the_control_group(self):
        legacy = {"status": "closed", "alpha_pct": 30.0, "pnl_pct": 30.0,
                  "nasdaq_return_pct": 0.0, "date": "2026-06-01"}
        tracker = {"trades": [legacy] + [self._closed(1.0, ["LL-A"], i)
                                         for i in range(6)]}
        out = mi._build_rule_scoreboard(self._RULES, tracker)
        assert "+30" not in out   # the legacy trade never enters the comparison

    def test_no_closed_trades_says_so_instead_of_going_silent(self):
        out = mi._build_rule_scoreboard(self._RULES, {"trades": []})
        assert "no closed trades" in out.lower()


class TestTradingVsPipelineRules:
    """Six of thirteen active 'recursive improvement rules' were production
    hygiene — re-teach cooldowns, 'every episode must state the NASDAQ
    level', and three variants of 'verify price data from multiple
    providers', which are the sim's own historical data-fetch bugs written
    up as investing wisdom and fed back into the pick prompt."""

    def test_pipeline_rules_are_excluded_from_the_pick_prompt(self):
        data = {"entries": [
            {"id": "P1", "status": "active",
             "adjustment": "Verify price data from multiple providers before entering"},
            {"id": "P2", "status": "active",
             "adjustment": "Every episode must state the NASDAQ Composite level"},
            {"id": "P3", "status": "active",
             "adjustment": "Never re-teach bid_ask_spread within its cooldown window"},
            {"id": "T1", "status": "active",
             "adjustment": "Cap any single sector at 30% of the trailing window"},
        ]}
        ids = [e["id"] for e in mi._selected_active_rules(data)]
        assert ids == ["T1"]

    def test_explicit_kind_overrides_the_heuristic(self):
        assert mi._is_trading_rule(
            {"kind": "trading", "adjustment": "verify price data"}) is True
        assert mi._is_trading_rule(
            {"kind": "pipeline", "adjustment": "cap sector exposure"}) is False

    def test_same_constraint_different_scope_is_one_rule(self):
        data = {"entries": [
            {"id": "LL-017", "status": "active", "adjustment":
             "Always require volume confirmation above the 20-day average "
             "before entering momentum trades on earnings beats"},
            {"id": "LL-067", "status": "active", "adjustment":
             "Require volume above the 20-day average before entering any "
             "catalyst-driven name already in a sector rotation"},
        ]}
        assert len(mi._selected_active_rules(data)) == 1


class TestPublicLedger:
    """'You can reproduce our numbers' has to be a link, not a claim."""

    @staticmethod
    def _mod():
        import importlib
        return importlib.import_module("scripts.build_mit_ledger")

    def test_ledger_carries_the_full_decision_record(self):
        mod = self._mod()
        tracker = {
            "summary": {"era_inception": "2026-08-18", "era_name": "Era 2"},
            "trades": [{
                "episode_num": 141, "date": "2026-08-19", "symbol": "ABC",
                "status": "open", "confidence": "High",
                "invalidation": "Guidance below $4.10 kills it",
                "horizon_sessions": 5, "policy_version": 2,
                "rules_in_effect": ["LL-A", "LL-B"],
                "stop_loss": {"pct": 6.0},
                "option": {"structure": "covered_call", "strike": 43.0,
                           "premium": 0.58, "expiry": "2026-09-18"},
            }],
        }
        payload = mod.build(tracker)
        row = payload["trades"][0]
        for key in ("invalidation", "horizon_sessions", "policy_version",
                    "rules_in_effect", "stop_pct", "option_strike",
                    "option_premium", "in_current_era"):
            assert key in row, key
        assert row["in_current_era"] is True

    def test_voided_and_pre_era_trades_are_published_not_hidden(self):
        mod = self._mod()
        tracker = {"summary": {"era_inception": "2026-08-18"}, "trades": [
            {"episode_num": 50, "date": "2026-05-01", "symbol": "CNR",
             "status": "voided", "void_reason": "instrument_scale_mismatch"},
        ]}
        payload = mod.build(tracker)
        assert payload["counts"]["voided"] == 1
        assert payload["trades"][0]["void_reason"] == "instrument_scale_mismatch"
        assert payload["trades"][0]["in_current_era"] is False

    def test_era_rationale_is_published_with_the_ledger(self):
        mod = self._mod()
        payload = mod.build({"summary": {"era_inception": "2026-08-18"},
                             "trades": []})
        assert "excluded from the on-air record, not deleted" in \
            payload["era"]["why"]

    def test_nightly_publishes_and_commits_the_ledger(self):
        wf = (_ROOT / ".github/workflows/nightly-maintenance.yml").read_text(
            encoding="utf-8")
        assert "scripts/build_mit_ledger.py" in wf
        assert "api/mit_trade_ledger.json" in wf.split("add-paths")[1]


class TestRuleRotation:
    """The scoreboard can only attribute an effect to a rule if some picks
    were made WITH it and some WITHOUT.

    Across the first 15 stamped trades only two rule sets were ever used
    — differing by a single rule, and arising because the lesson ledger
    happened to change rather than by design. The honest scoreboard was
    therefore permanently silent. Rotation supplies the variation.
    """

    # Genuinely distinct constraints — near-identical wording would be
    # collapsed by the near-duplicate filter before rotation ever runs,
    # which is correct behaviour but makes for a useless fixture.
    _ADJUSTMENTS = [
        "Require volume above the 20-day average",
        "Cap any single sector at 30% of the trailing window",
        "Wait for a confirmed earnings beat",
        "Avoid names inside an active short squeeze",
        "Size down when the VIX is above 25",
        "Skip picks with earnings inside the holding window",
    ]

    @classmethod
    def _ledger(cls, n=6):
        return {"entries": [
            {"id": f"LL-{i + 1:03d}", "status": "active",
             "adjustment": cls._ADJUSTMENTS[i]}
            for i in range(min(n, len(cls._ADJUSTMENTS)))
        ]}

    def test_rule_set_varies_between_episodes(self):
        data = self._ledger()
        sets = {tuple(e["id"] for e in mi._selected_active_rules(
            data, episode_num=ep)) for ep in range(100, 112)}
        assert len(sets) > 1, "rotation produced a constant rule set"

    def test_every_rule_gets_both_arms_over_a_cycle(self):
        from collections import Counter
        data = self._ledger()
        seen = Counter()
        episodes = list(range(100, 130))
        for ep in episodes:
            for e in mi._selected_active_rules(data, episode_num=ep):
                seen[e["id"]] += 1
        # Each rule appears sometimes and is absent sometimes — without
        # both arms no rule can ever be scored.
        for rid, count in seen.items():
            assert 0 < count < len(episodes), f"{rid} never varies"

    def test_rotation_is_deterministic(self):
        data = self._ledger()
        a = [e["id"] for e in mi._selected_active_rules(data, episode_num=207)]
        b = [e["id"] for e in mi._selected_active_rules(data, episode_num=207)]
        assert a == b  # reproducible from the trade record

    def test_proven_rules_are_never_rotated_out(self):
        data = self._ledger()
        era = mi.era_inception() or datetime.date(2026, 8, 18)

        def closed(alpha, rules, i):
            d = (era + datetime.timedelta(days=i)).isoformat()
            return {"status": "closed", "alpha_pct": alpha, "pnl_pct": alpha,
                    "nasdaq_return_pct": 0.0, "date": d, "entry_bar_date": d,
                    "rules_in_effect": rules}

        # LL-001 clearly outperforms; it must stop rotating.
        tracker = {"trades": [closed(5.0, ["LL-001"], i) for i in range(6)]
                   + [closed(-2.0, ["LL-002"], i + 6) for i in range(6)]}
        assert "LL-001" in mi._proven_rule_ids(tracker, data)
        for ep in range(100, 112):
            ids = [e["id"] for e in mi._selected_active_rules(
                data, episode_num=ep, tracker=tracker)]
            assert "LL-001" in ids

    def test_hand_pinned_rules_are_never_rotated_out(self):
        data = self._ledger()
        data["entries"][3]["always_on"] = True
        pinned = data["entries"][3]["id"]
        for ep in range(100, 112):
            ids = [e["id"] for e in mi._selected_active_rules(
                data, episode_num=ep)]
            assert pinned in ids

    def test_small_pool_is_not_rotated_away(self):
        # With fewer rules than slots there is nothing to rotate and every
        # rule must still be shown.
        data = self._ledger(n=2)
        ids = [e["id"] for e in mi._selected_active_rules(data, episode_num=5)]
        assert len(ids) == 2


class TestStrategyFamilies:
    """61 trades produced 61 unique free-text strategy strings, so the show
    could report which SECTORS worked but never which APPROACHES did."""

    def test_families_are_derived_from_free_text(self):
        cases = [
            ("Momentum play on earnings beat", "earnings_surprise"),
            ("Mean-reversion entry on 80% recovery from lows", "mean_reversion"),
            ("M&A spread capture on announced acquisition", "merger_arb"),
            ("Dividend-compounding entry on a midstream pipeline", "dividend_income"),
            ("Technical breakout attempt from one-month range", "technical_breakout"),
            ("Valuation screen on memory-chip names", "valuation"),
        ]
        for text, expected in cases:
            assert mi.strategy_family({"strategy": text}) == expected, text

    def test_explicit_family_wins_over_derivation(self):
        trade = {"strategy": "Momentum play on earnings beat",
                 "strategy_family": "macro_rotation"}
        assert mi.strategy_family(trade) == "macro_rotation"

    def test_unknown_explicit_family_falls_back_to_derivation(self):
        trade = {"strategy": "Dividend-growth entry",
                 "strategy_family": "not_a_real_family"}
        assert mi.strategy_family(trade) == "dividend_income"

    def test_unmatched_strategy_is_other_not_forced(self):
        assert mi.strategy_family({"strategy": "Something entirely novel"}) == "other"

    def test_record_prefers_verified_windows_and_labels_its_scope(self):
        era = mi.era_inception() or datetime.date(2026, 8, 18)
        trades = []
        for i in range(8):
            d = (era + datetime.timedelta(days=i)).isoformat()
            trades.append({"status": "closed", "alpha_pct": 1.0 + i,
                           "strategy": "Momentum play on earnings beat",
                           "date": d, "entry_bar_date": d})
        block = mi._build_strategy_family_performance({"trades": trades})
        assert "verified-window trades" in block
        assert "earnings_surprise" in block

    def test_legacy_only_record_is_labelled_indicative(self):
        trades = [{"status": "closed", "alpha_pct": 5.0,
                   "strategy": "Momentum play on earnings beat"}
                  for _ in range(4)]
        block = mi._build_strategy_family_performance({"trades": trades})
        assert "indicative only" in block
        assert "do NOT quote" in block

    def test_thin_buckets_are_flagged_not_hidden(self):
        trades = [{"status": "closed", "alpha_pct": 2.0,
                   "strategy": "Momentum play on earnings beat"}
                  for _ in range(3)]
        block = mi._build_strategy_family_performance({"trades": trades})
        assert "too few to lean on" in block

    def test_digest_prompt_requires_a_family(self):
        prompt = (_ROOT / "shows/prompts/modern_investing_digest.txt").read_text(
            encoding="utf-8")
        assert "**Strategy Family:**" in prompt
        assert "{strategy_family_performance}" in prompt
        for name, _ in mi.STRATEGY_FAMILIES:
            assert name in prompt, name


class TestReviewCatchUp:
    """The daily audit runs on a fixed cron; shows finish at wildly
    different times (MIT has landed 09:32-19:41 UTC). Anything finishing
    after the audit was logged 'critical: Missed episode' and auto-closed
    the next day by confirming the FILE EXISTS — its content was never
    reviewed. On 2026-08-19 that was four shows at once.
    """

    @staticmethod
    def _mod():
        import importlib
        return importlib.import_module("review_episodes")

    def test_catch_up_helpers_exist_and_are_bounded(self):
        mod = self._mod()
        assert mod.CATCH_UP_DAYS >= 1
        assert mod.CATCH_UP_MAX_PER_RUN >= 1
        assert callable(mod.find_catch_up_episodes)

    def test_coverage_key_and_day_parsing(self):
        mod = self._mod()
        day = datetime.date(2026, 8, 19)
        assert mod._coverage_key("modern_investing", day) == \
            "modern_investing|2026-08-19"
        ep = SimpleNamespace(show_slug="x", date="2026-08-19")
        assert mod._episode_day(ep, datetime.date(2000, 1, 1)) == day
        compact = SimpleNamespace(show_slug="x", date="20260819")
        assert mod._episode_day(compact, datetime.date(2000, 1, 1)) == day

    def test_unparseable_date_falls_back_instead_of_raising(self):
        mod = self._mod()
        fallback = datetime.date(2026, 1, 2)
        ep = SimpleNamespace(show_slug="x", date="not-a-date")
        assert mod._episode_day(ep, fallback) == fallback

    def test_coverage_prunes_old_entries(self, tmp_path, monkeypatch):
        mod = self._mod()
        monkeypatch.setattr(mod, "REVIEW_COVERAGE_PATH",
                            tmp_path / "review_coverage.json")
        today = datetime.date(2026, 8, 20)
        state = {"reviewed": {
            "a|2026-08-19": True,          # recent — kept
            "b|2026-01-01": True,          # ancient — pruned
        }}
        mod._save_coverage(state, today)
        reloaded = mod._load_coverage()["reviewed"]
        assert "a|2026-08-19" in reloaded
        assert "b|2026-01-01" not in reloaded

    def test_audit_workflow_persists_coverage(self):
        wf = (_ROOT / ".github/workflows/daily-audit.yml").read_text(
            encoding="utf-8")
        # Without persistence the catch-up pass re-reviews the same
        # episodes every run and never drains.
        assert "api/review_coverage.json" in wf


class TestMethodologyDisclosure:
    """The old cumulative-alpha figure vanished from air when the
    era-scoped record started.

    A number that quietly disappears is indistinguishable, from the
    listener's seat, from a number being buried — and here the truth is
    the opposite (it could not be reproduced, so it was not ours to
    claim). The correction is a one-off segment, not a standing
    changelog: it must retire itself, it must never re-air on the same
    episode twice, and it must stay out of pipeline internals.
    """

    @staticmethod
    def _tracker():
        return {"metadata": {}, "trades": []}

    def test_airs_then_retires(self, monkeypatch):
        monkeypatch.setattr(mi, "_hooks_readonly", lambda: False)
        tracker = self._tracker()
        aired = [
            bool(mi._build_methodology_disclosure(tracker, episode_num=ep))
            for ep in range(200, 210)
        ]
        assert aired[:mi.METHODOLOGY_DISCLOSURE_EPISODES] == (
            [True] * mi.METHODOLOGY_DISCLOSURE_EPISODES)
        assert not any(aired[mi.METHODOLOGY_DISCLOSURE_EPISODES:]), (
            "the correction became a permanent segment")

    def test_same_episode_never_consumes_two_airings(self, monkeypatch):
        # get_prompt_context can run more than once per episode; without
        # this guard a single episode would burn the whole allowance.
        monkeypatch.setattr(mi, "_hooks_readonly", lambda: False)
        tracker = self._tracker()
        first = mi._build_methodology_disclosure(tracker, episode_num=200)
        second = mi._build_methodology_disclosure(tracker, episode_num=200)
        assert first and not second
        assert tracker["metadata"]["methodology_disclosure_episodes"] == [200]

    def test_readonly_runs_do_not_stamp(self, monkeypatch):
        monkeypatch.setattr(mi, "_hooks_readonly", lambda: True)
        tracker = self._tracker()
        assert mi._build_methodology_disclosure(tracker, episode_num=200)
        assert not tracker["metadata"].get(
            "methodology_disclosure_episodes"), (
            "a rehearsal run consumed a real airing")

    def test_covers_the_four_audit_questions(self, monkeypatch):
        # The transferable lesson is the reason this segment is worth
        # airing at all: how to audit any track record you are shown.
        monkeypatch.setattr(mi, "_hooks_readonly", lambda: False)
        text = mi._build_methodology_disclosure(self._tracker(), 200).lower()
        for probe in ("exit rule", "losers", "published", "reproduce"):
            assert probe in text, f"missing audit question: {probe}"

    def test_stays_out_of_pipeline_internals(self, monkeypatch):
        # A listener cares what the numbers mean, not how the repo is
        # wired. Naming internal machinery on air is noise at best.
        monkeypatch.setattr(mi, "_hooks_readonly", lambda: False)
        block = mi._build_methodology_disclosure(self._tracker(), 200)
        # Everything from the closing directive on is guidance to the
        # model, never spoken — the ban applies to the content above it.
        marker = "Do NOT discuss"
        assert marker in block, "the internals ban went missing"
        text = block.split(marker)[0].lower()
        # "scoreboard" is deliberately absent from this list — it is the
        # show's own on-air word for the benchmark block, not internals.
        for leak in ("rotation", "prompt", "pipeline", "codebase",
                     "repository", "workflow"):
            assert leak not in text, f"internal detail leaked on air: {leak}"

    def test_prompt_and_runner_are_wired(self):
        prompt = (_ROOT / "shows/prompts/modern_investing_digest.txt").read_text(
            encoding="utf-8")
        assert "{methodology_disclosure}" in prompt
        runner = (_ROOT / "run_show.py").read_text(encoding="utf-8")
        # Defaulted in the runner so a hook failure degrades to an
        # episode without the correction rather than a KeyError.
        assert 'setdefault("methodology_disclosure", "")' in runner

    def test_published_sources_are_reachable_from_the_site(self):
        # The segment tells listeners the rulebook and the trade-by-trade
        # ledger are published "for anyone to check". Before this pass the
        # ledger was built nightly into api/ and linked from nowhere, so
        # the claim was true only for someone who knew the repo layout.
        tpl = (_ROOT / "templates/mit_performance_page.html.j2").read_text(
            encoding="utf-8")
        for target in ("docs/mit_trading_method.md",
                       "api/mit_trade_ledger.json",
                       "api/mit_trade_ledger.csv"):
            assert target in tpl, f"performance page does not link {target}"
            assert (_ROOT / target).exists(), f"linked file missing: {target}"
