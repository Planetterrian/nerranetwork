"""Drift guards for the June 2026 Modern Investing quality pass.

Pins the fixes from the flagship-style review of MIT:

* the recursive-learning loop is ALIVE: ``_analyze_strategy_patterns``
  existed only as a call site (NameError swallowed by pre_fetch's
  try/except), so every episode shipped "Learning context temporarily
  unavailable" and the operating-principles + confidence-calibration
  blocks died with it;
* NaN immunity: two trades closed with NaN exit prices (yfinance
  returns NaN floats that pass ``is None`` checks) poisoned
  ``cumulative_pnl`` into NaN — "Running Total: $nan" on air;
* the summary now carries ``cumulative_alpha_vs_nasdaq`` (the show's
  headline metric, previously read from a key that never existed) and
  the portfolio-summary prompt block states it;
* escalating lesson cooldowns (bid-ask-spread was retaught 13 times in
  71 episodes — each repeat was legal under a flat 21-day window);
* trade-extraction distinguishes deliberate no-trade days from silent
  formatting-drift losses;
* MIT opts into ``podcast_expand_below_target`` and gets a hook-led X
  teaser linking the episode blog + live performance page.
"""

from __future__ import annotations

import datetime
import math
import re
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from shows.hooks import modern_investing as mi  # noqa: E402

NAN = float("nan")


def _tracker_with_trades(trades):
    return {
        "metadata": {"position_size": 1000},
        "trades": trades,
        "summary": {},
    }


def _closed(symbol, pnl_pct, pnl_dollars, alpha=None, sector="tech"):
    return {
        "symbol": symbol, "status": "closed", "sector": sector,
        "pnl_pct": pnl_pct, "pnl_dollars": pnl_dollars, "alpha_pct": alpha,
    }


class TestNaNImmunity:
    def test_finite_helper(self):
        assert mi._finite(5.0) == 5.0
        assert mi._finite(None) == 0.0
        assert mi._finite(NAN) == 0.0
        assert mi._finite(float("inf")) == 0.0

    def test_recompute_summary_survives_nan_trades(self):
        tracker = _tracker_with_trades([
            _closed("AAA", 10.0, 100.0, alpha=5.0),
            _closed("BBB", NAN, NAN, alpha=NAN),   # the DELL/HIMS shape
            _closed("CCC", -5.0, -50.0, alpha=-2.0),
        ])
        mi._recompute_summary(tracker)
        s = tracker["summary"]
        assert math.isfinite(s["cumulative_pnl"])
        assert s["cumulative_pnl"] == 50.0
        assert math.isfinite(s["average_return_pct"])
        assert s["cumulative_alpha_vs_nasdaq"] == 3.0
        assert s["trades_with_alpha"] == 2

    def test_close_trade_voids_on_nan_prices(self):
        # July 2026: a data-fetch failure now VOIDS the trade instead of
        # recording a $0.00 breakeven close (which was counted in the
        # record and later narrated as a real market outcome). NaN bars
        # are dropped by _bars_from_history, so a symbol whose only data
        # is NaN yields no bars at all → void.
        trade = {"symbol": "DELL", "trade_type": "flash"}
        tracker = _tracker_with_trades([])
        with patch.object(mi, "_fetch_bars_for_trade", return_value=None):
            mi._close_trade(trade, tracker)
        assert trade["status"] == "voided"
        assert trade["void_reason"] == "market_data_unavailable"
        assert trade["exit_price"] is None
        assert trade["pnl_pct"] is None
        assert trade["pnl_dollars"] is None
        assert "voided" in trade["lesson"].lower()

    def test_bars_from_history_drops_nan_bars(self):
        # yfinance NaN bars (the DELL/HIMS shape) must never become an
        # entry or exit price.
        class _FakeIdx:
            def __init__(self, d):
                self._d = d
            def date(self):
                return self._d

        class _FakeHist:
            empty = False
            def iterrows(self):
                yield _FakeIdx(datetime.date(2026, 5, 29)), {"Open": 426.15, "Close": NAN}
                yield _FakeIdx(datetime.date(2026, 6, 1)), {"Open": 430.0, "Close": 432.5}

        bars = mi._bars_from_history(_FakeHist())
        # July 2026 stop-enforcement pass: bars carry a best-effort 4th
        # element (intraday low; None when the column is absent).
        assert bars == [(datetime.date(2026, 6, 1), 430.0, 432.5, None)]

    def test_sector_exposure_finite(self):
        tracker = _tracker_with_trades([
            _closed("AAA", 10.0, NAN, sector="other"),
            _closed("BBB", 2.0, 20.0, sector="other"),
        ])
        sectors = mi._compute_sector_exposure(tracker)
        assert math.isfinite(sectors["other"]["cumulative_pnl"])


def _voided(symbol, sector="tech"):
    return {
        "symbol": symbol, "status": "voided",
        "void_reason": "market_data_unavailable",
        "entry_price": None, "exit_price": None,
        "pnl_pct": None, "pnl_dollars": None, "alpha_pct": None,
    }


class TestVoidedTradesExcluded:
    """July 2026 review: four trades (Ep74 XLF / Ep75 KO / Ep77 ROKU /
    Ep79 ION) closed with null prices as $0.00 breakevens — counted in the
    spoken record and later narrated as real market outcomes. Voided trades
    must be excluded from every aggregation."""

    def test_recompute_summary_ignores_voided(self):
        tracker = _tracker_with_trades([
            _closed("AAA", 10.0, 100.0, alpha=5.0),
            _voided("XLF"),
            _closed("CCC", -4.0, -40.0, alpha=-2.0),
            _voided("KO"),
        ])
        mi._recompute_summary(tracker)
        s = tracker["summary"]
        # Only the two real closed trades count — not the voided pair.
        assert s["total_trades"] == 2
        assert s["breakeven"] == 0
        assert s["cumulative_pnl"] == 60.0

    def test_sector_exposure_ignores_voided(self):
        tracker = _tracker_with_trades([
            _closed("AAA", 5.0, 50.0, sector="tech"),
            _voided("XLF", sector="financials"),
        ])
        sectors = mi._compute_sector_exposure(tracker)
        assert "financials" not in sectors
        assert sectors["tech"]["trade_count"] == 1

    def test_trade_review_never_narrates_voided(self):
        # The most recent trade is voided → it must not become the review.
        tracker = _tracker_with_trades([
            _closed("AAA", 8.0, 80.0, alpha=4.0),
            _voided("ROKU"),
        ])
        # AAA is the only real closed trade; it becomes the review, not ROKU.
        review = mi._build_trade_review(tracker, episode_num=90)
        assert "ROKU" not in review
        assert "AAA" in review

    def test_committed_tracker_invariants(self):
        # Rewritten July 3 2026: the original pinned total_trades == 37 and
        # went red the moment new trades closed after the migration — a
        # drift guard that drifts. These invariants hold for ANY healthy
        # tracker state.
        import json
        d = json.loads(
            (_ROOT / "digests/modern_investing/investment_tracker.json").read_text())
        voided = [t for t in d["trades"] if t.get("status") == "voided"]
        closed = [t for t in d["trades"] if t.get("status") == "closed"]
        voided_ids = {(t["episode_num"], t["symbol"]) for t in voided}
        # The six known data-failure trades stay voided (4 null-price from
        # the July 2 migration + DELL/HIMS NaN-exit from the July 3 one).
        assert {(74, "XLF"), (75, "KO"), (77, "ROKU"), (79, "ION"),
                (57, "DELL"), (63, "HIMS")} <= voided_ids
        # No closed trade may carry a non-finite result — that's a voided
        # trade wearing a closed costume (the exact shape that put
        # "breakeven" data failures on air).
        for t in closed:
            assert isinstance(t["pnl_pct"], (int, float)) and math.isfinite(t["pnl_pct"]), \
                f"closed trade {t.get('symbol')} has non-finite pnl"
        for t in voided:
            assert t["pnl_pct"] is None and t["pnl_dollars"] is None
        # The summary is derived, not hand-edited: recomputing from the
        # trades must reproduce it.
        recomputed = {"trades": d["trades"], "metadata": d["metadata"], "summary": {}}
        mi._recompute_summary(recomputed)
        for key in ("total_trades", "wins", "losses", "breakeven",
                    "win_rate_pct", "cumulative_pnl",
                    "cumulative_alpha_vs_nasdaq"):
            assert d["summary"][key] == recomputed["summary"][key], key
        # Breakeven now means an ACTUAL 0.00% close, not a data failure.
        assert d["summary"]["breakeven"] == sum(
            1 for t in closed if t["pnl_pct"] == 0)


class TestDoubleReviewPrevented:
    """The MU flash trade was re-narrated as 'yesterday's' on Ep089/091/093
    because the review always picked the latest closed trade. Each result is
    now reviewed exactly once via ``reviewed_in_episode``."""

    def test_stamps_on_first_review(self):
        tracker = _tracker_with_trades([_closed("MU", 3.0, 30.0, alpha=1.0)])
        review = mi._build_trade_review(tracker, episode_num=89)
        assert "MU" in review
        assert tracker["trades"][-1]["reviewed_in_episode"] == 89

    def test_no_re_review_next_episode(self):
        trade = _closed("MU", 3.0, 30.0, alpha=1.0)
        trade["reviewed_in_episode"] = 89
        tracker = _tracker_with_trades([trade])
        review = mi._build_trade_review(tracker, episode_num=91)
        assert "MU" not in review
        assert "pending" in review.lower()

    def test_same_episode_rerun_still_reviews(self):
        # Regenerating the SAME episode must still produce the review.
        trade = _closed("MU", 3.0, 30.0, alpha=1.0)
        trade["reviewed_in_episode"] = 91
        tracker = _tracker_with_trades([trade])
        review = mi._build_trade_review(tracker, episode_num=91)
        assert "MU" in review

    def test_open_hold_update_when_latest_already_reviewed(self):
        reviewed = _closed("MU", 3.0, 30.0, alpha=1.0)
        reviewed["reviewed_in_episode"] = 89
        hold = {
            "symbol": "NVDA", "status": "open",
            "strategy": "momentum", "entry_price": 100.0,
            "current_price": 105.0,
        }
        tracker = _tracker_with_trades([reviewed, hold])
        review = mi._build_trade_review(tracker, episode_num=91)
        assert "NVDA" in review
        assert "Holding until Friday" in review


class TestRecursiveLearningLoopAlive:
    def test_analyze_strategy_patterns_defined_with_favor_avoid(self):
        # July 2026 statistical-discipline pass: FAVOR/AVOID requires
        # n >= 5 per sector (was 3 — coin-flip samples steered picks).
        tracker = _tracker_with_trades(
            [_closed(f"W{i}", 5, 50, alpha=4.0, sector="tech") for i in range(5)]
            + [_closed(f"L{i}", -5, -50, alpha=-3.0, sector="energy")
               for i in range(5)]
        )
        out = mi._analyze_strategy_patterns(tracker)
        assert "FAVOR tech" in out
        assert "AVOID energy" in out

    def test_small_samples_get_no_favor_avoid_verdict(self):
        tracker = _tracker_with_trades(
            [_closed(f"W{i}", 5, 50, alpha=4.0, sector="tech") for i in range(3)]
            + [_closed(f"L{i}", -5, -50, alpha=-3.0, sector="energy")
               for i in range(3)]
        )
        out = mi._analyze_strategy_patterns(tracker)
        assert "FAVOR" not in out and "AVOID" not in out
        block = mi._build_strategy_performance(tracker)
        assert "insufficient sample" in block
        assert "FAVOR these sectors" not in block

    def test_learning_context_runs_on_live_tracker(self):
        # The historical failure mode: NameError swallowed by pre_fetch.
        ctx = mi.get_mit_recursive_learning_context()
        assert "temporarily unavailable" not in ctx
        assert "RECURSIVE LEARNING CONTEXT" in ctx or "EARLY STAGE" in ctx

    def test_learning_context_reports_real_win_rate(self):
        ctx = mi.get_mit_recursive_learning_context()
        m = re.search(r"Win rate (\d+)%", ctx)
        assert m, f"win rate missing from context: {ctx[:200]}"
        # The old code read a nonexistent 'win_rate' key → always 0%.
        assert int(m.group(1)) > 0

    def test_portfolio_summary_states_alpha_headline(self):
        tracker = _tracker_with_trades([
            _closed("AAA", 10.0, 100.0, alpha=5.0),
            _closed("BBB", 1.0, 10.0, alpha=1.0),
        ])
        mi._recompute_summary(tracker)
        block = mi._build_portfolio_summary(tracker)
        assert "Cumulative alpha vs NASDAQ: +6.0%" in block
        assert "$nan" not in block.lower()


class TestEscalatingLessonCooldown:
    def _data(self, count, days_ago, cooldown=21):
        last = (datetime.date.today() - datetime.timedelta(days=days_ago))
        return {
            "cooldown_days_default": 21,
            "lessons": {
                "bid_ask_spread": {
                    "count": count,
                    "last_date": last.isoformat(),
                    "cooldown_days": cooldown,
                },
            },
        }

    def test_flat_cooldown_for_rarely_taught(self):
        # count=1 → multiplier 1 → 21d window; 25 days ago = teachable.
        assert mi._stale_lesson_tags(self._data(count=1, days_ago=25)) == []

    def test_overtaught_lesson_stays_blocked(self):
        # count=13 → 21 * (1 + 13//3) = 105d window; 29 days ago (the
        # exact gap that let Ep65 reteach it) is now still blocked.
        stale = mi._stale_lesson_tags(self._data(count=13, days_ago=29))
        assert [t for t, _ in stale] == ["bid_ask_spread"]

    def test_escalation_capped(self):
        # Even count=100 caps at 180 days.
        stale = mi._stale_lesson_tags(self._data(count=100, days_ago=181))
        assert stale == []


class TestTradeExtractionDiagnostics:
    def test_explicit_no_trade_is_quiet(self, caplog):
        import logging
        with caplog.at_level(logging.WARNING, logger=mi.logger.name):
            out = mi._extract_trade_from_digest(
                "### Practice Investment\n**Today's Pick:** No trade today.",
                71,
            )
        assert out is None
        assert not [r for r in caplog.records if r.levelno >= logging.WARNING]

    def test_formatting_drift_warns(self, caplog):
        import logging
        with caplog.at_level(logging.WARNING, logger=mi.logger.name):
            out = mi._extract_trade_from_digest(
                "**Today's Pick** is Nvidia at current levels.", 71,
            )
        assert out is None
        assert any("formatting drift" in r.getMessage()
                   for r in caplog.records)


class TestConfigAndTeaser:
    def test_mit_opts_into_expand_below_target(self):
        from engine.config import load_config

        cfg = load_config("shows/modern_investing.yaml")
        assert cfg.llm.podcast_expand_below_target is True

    def test_teaser_has_hook_blog_and_performance_links(self):
        import run_show

        cfg = SimpleNamespace(
            slug="modern_investing", name="Modern Investing Techniques",
            publishing=SimpleNamespace(x_teaser_template=""),
        )
        teaser = run_show._build_teaser(
            cfg, 71, "June 09, 2026",
            {"hook": "Canadian housing exposure needs a rethink after "
                     "insolvencies hit a 2009 high."},
        )
        assert "Canadian housing exposure" in teaser
        assert "blog/modern_investing/ep071.html" in teaser
        assert "modern-investing-performance.html" in teaser
        # X budget: every URL counts as 23 chars.
        assert len(re.sub(r"https?://\S+", "x" * 23, teaser)) <= 280

    def test_deep_dive_queue_has_pending_entries(self):
        import yaml

        d = yaml.safe_load(
            (_ROOT / "shows/deep_dives/modern_investing.yaml").read_text(
                encoding="utf-8"))
        pending = [e for e in d["queue"] if not e.get("produced")]
        assert len(pending) >= 5, (
            "the evergreen deep-dive bench must stay stocked (June 2026: "
            "queue was empty — both entries produced, nothing scheduled)"
        )
        # None of the new entries may auto-fire — operator schedules them.
        for e in pending:
            assert "when" not in e and "date" not in e
