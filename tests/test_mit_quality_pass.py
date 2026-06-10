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

    def test_close_trade_rejects_nan_prices(self):
        trade = {"symbol": "DELL", "trade_type": "flash"}
        tracker = _tracker_with_trades([])
        with patch.object(mi, "_fetch_trade_prices",
                          return_value=(426.15, NAN)):
            mi._close_trade(trade, tracker)
        assert trade["status"] == "closed"
        assert trade["exit_price"] is None
        assert trade["pnl_dollars"] == 0.0
        assert "unavailable" in trade["lesson"].lower()

    def test_sector_exposure_finite(self):
        tracker = _tracker_with_trades([
            _closed("AAA", 10.0, NAN, sector="other"),
            _closed("BBB", 2.0, 20.0, sector="other"),
        ])
        sectors = mi._compute_sector_exposure(tracker)
        assert math.isfinite(sectors["other"]["cumulative_pnl"])


class TestRecursiveLearningLoopAlive:
    def test_analyze_strategy_patterns_defined_with_favor_avoid(self):
        tracker = _tracker_with_trades(
            [_closed(f"W{i}", 5, 50, alpha=4.0, sector="tech") for i in range(3)]
            + [_closed(f"L{i}", -5, -50, alpha=-3.0, sector="energy")
               for i in range(3)]
        )
        out = mi._analyze_strategy_patterns(tracker)
        assert "FAVOR tech" in out
        assert "AVOID energy" in out

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
