"""Tests for the Modern Investing Techniques hook module.

Covers:
- Trade extraction from digest text
- Tracker I/O (load, save, recompute)
- Trade evaluation with mocked yfinance data
- Trade review and portfolio summary text builders
"""

import datetime
import json
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from shows.hooks.modern_investing import (
    _build_portfolio_summary,
    _build_trade_review,
    _extract_trade_from_digest,
    _format_streak,
    _load_tracker,
    _recompute_summary,
    _save_tracker,
)


# ---------------------------------------------------------------------------
# Sample digest text for extraction tests
# ---------------------------------------------------------------------------

SAMPLE_DIGEST = """# Modern Investing Techniques
**Date:** Monday, March 17, 2026
💰 **Modern Investing Techniques** — AI-Powered Daily Market Intelligence

**HOOK:** Apple beats earnings expectations, signalling AI infrastructure spending surge.

**Market Pulse:** The S&P 500 opened at 5,892, up 0.3% from Friday's close.

━━━━━━━━━━━━━━━━━━━━
### Strategy Spotlight
Momentum investing after earnings beats explained in detail.
Source: https://example.com/article

━━━━━━━━━━━━━━━━━━━━
### Practice Investment of the Day
**Disclaimer:** This is a SIMULATED trade for educational purposes only.

**Trade Type:** Weekly Hold
**Today's Pick:** AAPL — Apple Inc.
**Market:** NASDAQ
**Strategy:** Momentum play on earnings beat with AI spending catalyst
**Hold Period:** Monday-Friday
**AI Analysis:**
- **Catalyst:** Q1 earnings beat by 12%, driven by AI services revenue
- **Technical Setup:** RSI at 42 (neutral), price above 50-day MA at $198, volume 20% above average
- **Risk Assessment:** Support at $195, stop-loss at $193 (2.5% downside)
- **Target:** +3% to +5% weekly move
- **Confidence Level:** High — earnings beat + technical setup + sector momentum aligned

**Why This Teaches:** This demonstrates momentum investing after an earnings surprise.
Source: https://example.com/aapl

━━━━━━━━━━━━━━━━━━━━
### Tools & Techniques
**TradingView Screener:**
Screen for earnings beats with momentum confirmation.
Source: https://example.com/tools

━━━━━━━━━━━━━━━━━━━━
### Quick Hits
**NVIDIA acquires startup** — AI chip demand continues to surge.
Source: https://example.com/nvda
"""

SAMPLE_FLASH_DIGEST = """# Modern Investing Techniques
**Date:** Wednesday, March 19, 2026

━━━━━━━━━━━━━━━━━━━━
### Practice Investment of the Day
**Disclaimer:** This is a SIMULATED trade for educational purposes only.

**Trade Type:** Flash Trade
**Today's Pick:** NVDA — NVIDIA Corporation
**Market:** NASDAQ
**Strategy:** Catalyst-driven intraday play on surprise acquisition announcement
**Hold Period:** Same-day
**AI Analysis:**
- **Catalyst:** Surprise $2B acquisition of AI chip startup announced pre-market
- **Technical Setup:** Gap up 3% pre-market, RSI at 55
- **Risk Assessment:** Stop-loss at gap fill level, 1.5% downside
- **Target:** +1.5% to +3% same-day move
- **Confidence Level:** Medium — strong catalyst but gap plays carry reversal risk

**Why This Teaches:** Flash trades demonstrate catalyst-driven execution.
Source: https://example.com/nvda
"""


# ---------------------------------------------------------------------------
# Trade extraction
# ---------------------------------------------------------------------------

class TestExtractTradeFromDigest:
    def test_extracts_ticker_symbol(self):
        trade = _extract_trade_from_digest(SAMPLE_DIGEST, episode_num=5)
        assert trade is not None
        assert trade["symbol"] == "AAPL"

    def test_extracts_market(self):
        trade = _extract_trade_from_digest(SAMPLE_DIGEST, episode_num=5)
        assert trade["market"] == "NASDAQ"

    def test_extracts_strategy(self):
        trade = _extract_trade_from_digest(SAMPLE_DIGEST, episode_num=5)
        assert "Momentum" in trade["strategy"] or "momentum" in trade["strategy"].lower()

    def test_extracts_confidence(self):
        trade = _extract_trade_from_digest(SAMPLE_DIGEST, episode_num=5)
        assert trade["confidence"] == "High"

    def test_extracts_target(self):
        trade = _extract_trade_from_digest(SAMPLE_DIGEST, episode_num=5)
        assert "3%" in trade["target_range"] or "+3" in trade["target_range"]

    def test_trade_is_open(self):
        trade = _extract_trade_from_digest(SAMPLE_DIGEST, episode_num=5)
        assert trade["status"] == "open"
        assert trade["entry_price"] is None
        assert trade["exit_price"] is None

    def test_sets_episode_num(self):
        trade = _extract_trade_from_digest(SAMPLE_DIGEST, episode_num=42)
        assert trade["episode_num"] == 42

    def test_sets_date(self):
        trade = _extract_trade_from_digest(SAMPLE_DIGEST, episode_num=1)
        assert trade["date"] == datetime.date.today().isoformat()

    def test_returns_none_for_empty_digest(self):
        assert _extract_trade_from_digest("", episode_num=1) is None

    def test_returns_none_for_no_pick(self):
        assert _extract_trade_from_digest("Just some random text", episode_num=1) is None

    def test_extracts_trade_type_weekly(self):
        trade = _extract_trade_from_digest(SAMPLE_DIGEST, episode_num=5)
        assert trade["trade_type"] == "weekly"

    def test_extracts_trade_type_flash(self):
        trade = _extract_trade_from_digest(SAMPLE_FLASH_DIGEST, episode_num=8)
        assert trade is not None
        assert trade["trade_type"] == "flash"
        assert trade["symbol"] == "NVDA"

    def test_midweek_update_returns_none(self):
        midweek = SAMPLE_DIGEST.replace("**Trade Type:** Weekly Hold", "**Trade Type:** Mid-Week Update")
        trade = _extract_trade_from_digest(midweek, episode_num=6)
        assert trade is None

    def test_extracts_tsx_market(self):
        tsx_digest = SAMPLE_DIGEST.replace("NASDAQ", "TSX").replace("AAPL", "RY")
        trade = _extract_trade_from_digest(tsx_digest, episode_num=1)
        assert trade is not None
        assert trade["market"] == "TSX"


# ---------------------------------------------------------------------------
# Tracker I/O
# ---------------------------------------------------------------------------

class TestTrackerIO:
    def test_load_fresh_tracker(self, tmp_path):
        tracker = _load_tracker(tmp_path / "nonexistent.json")
        assert tracker["metadata"]["show"] == "Modern Investing Techniques"
        assert tracker["summary"]["total_trades"] == 0
        assert tracker["trades"] == []

    def test_load_existing_tracker(self, tmp_path):
        path = tmp_path / "tracker.json"
        data = {
            "metadata": {"show": "test", "position_size": 1000},
            "summary": {"total_trades": 5, "wins": 3},
            "trades": [{"symbol": "AAPL", "status": "closed"}],
        }
        path.write_text(json.dumps(data))
        tracker = _load_tracker(path)
        assert tracker["summary"]["total_trades"] == 5
        assert len(tracker["trades"]) == 1

    def test_load_corrupt_json_returns_fresh(self, tmp_path):
        path = tmp_path / "tracker.json"
        path.write_text("{bad json")
        tracker = _load_tracker(path)
        assert tracker["trades"] == []

    def test_save_and_reload(self, tmp_path):
        path = tmp_path / "tracker.json"
        tracker = _load_tracker(path)
        tracker["trades"].append({"symbol": "MSFT", "status": "open"})
        _save_tracker(tracker, path)

        reloaded = json.loads(path.read_text())
        assert len(reloaded["trades"]) == 1
        assert reloaded["trades"][0]["symbol"] == "MSFT"


# ---------------------------------------------------------------------------
# Summary recomputation
# ---------------------------------------------------------------------------

class TestRecomputeSummary:
    def test_empty_trades(self):
        tracker = {"trades": [], "summary": {}}
        _recompute_summary(tracker)
        # No closed trades, summary stays empty
        assert tracker["summary"] == {}

    def test_single_win(self):
        tracker = {
            "trades": [
                {"status": "closed", "pnl_pct": 2.5, "pnl_dollars": 25.0},
            ],
            "summary": {},
        }
        _recompute_summary(tracker)
        assert tracker["summary"]["total_trades"] == 1
        assert tracker["summary"]["wins"] == 1
        assert tracker["summary"]["losses"] == 0
        assert tracker["summary"]["win_rate_pct"] == 100.0
        assert tracker["summary"]["cumulative_pnl"] == 25.0

    def test_mixed_results(self):
        tracker = {
            "trades": [
                {"status": "closed", "pnl_pct": 2.0, "pnl_dollars": 20.0},
                {"status": "closed", "pnl_pct": -1.5, "pnl_dollars": -15.0},
                {"status": "closed", "pnl_pct": 3.0, "pnl_dollars": 30.0},
                {"status": "open", "pnl_pct": None, "pnl_dollars": None},  # Ignored
            ],
            "summary": {},
        }
        _recompute_summary(tracker)
        assert tracker["summary"]["total_trades"] == 3
        assert tracker["summary"]["wins"] == 2
        assert tracker["summary"]["losses"] == 1
        assert tracker["summary"]["cumulative_pnl"] == 35.0
        assert tracker["summary"]["best_trade_pct"] == 3.0
        assert tracker["summary"]["worst_trade_pct"] == -1.5

    def test_streak_calculation(self):
        tracker = {
            "trades": [
                {"status": "closed", "pnl_pct": 1.0, "pnl_dollars": 10},
                {"status": "closed", "pnl_pct": 2.0, "pnl_dollars": 20},
                {"status": "closed", "pnl_pct": -0.5, "pnl_dollars": -5},
            ],
            "summary": {},
        }
        _recompute_summary(tracker)
        assert tracker["summary"]["longest_win_streak"] == 2
        assert tracker["summary"]["current_streak"] == -1


# ---------------------------------------------------------------------------
# Text builders
# ---------------------------------------------------------------------------

class TestBuildTradeReview:
    def test_episode_1_returns_empty(self):
        tracker = {"trades": [], "summary": {}}
        assert _build_trade_review(tracker, episode_num=1) == ""

    def test_no_closed_trades_returns_empty(self):
        tracker = {
            "trades": [{"status": "open", "symbol": "AAPL"}],
            "summary": {"cumulative_pnl": 0, "wins": 0, "total_trades": 0, "win_rate_pct": 0},
        }
        assert _build_trade_review(tracker, episode_num=5) == ""

    def test_with_closed_weekly_hold(self):
        tracker = {
            "trades": [
                {
                    "status": "closed",
                    "symbol": "AAPL",
                    "strategy": "Momentum play",
                    "trade_type": "weekly",
                    "entry_price": 200.0,
                    "exit_price": 204.0,
                    "pnl_pct": 2.0,
                    "pnl_dollars": 20.0,
                },
            ],
            "summary": {
                "cumulative_pnl": 20.0,
                "wins": 1,
                "total_trades": 1,
                "win_rate_pct": 100.0,
                "current_streak": 1,
            },
        }
        review = _build_trade_review(tracker, episode_num=2)
        assert "AAPL" in review
        assert "Weekly Hold" in review
        assert "gained" in review
        assert "2.00%" in review
        assert "$200.00" in review
        # Oct 24 2026: the lifetime win rate left this block — it is the
        # record's number and belongs to Portfolio Performance alone.
        assert "Win Rate" not in review and "Running Total" not in review

    def test_with_closed_flash_trade(self):
        tracker = {
            "trades": [
                {
                    "status": "closed",
                    "symbol": "NVDA",
                    "strategy": "Catalyst play",
                    "trade_type": "flash",
                    "entry_price": 150.0,
                    "exit_price": 153.0,
                    "pnl_pct": 2.0,
                    "pnl_dollars": 20.0,
                },
            ],
            "summary": {
                "cumulative_pnl": 20.0,
                "wins": 1,
                "total_trades": 1,
                "win_rate_pct": 100.0,
                "current_streak": 1,
            },
        }
        review = _build_trade_review(tracker, episode_num=5)
        assert "Flash Trade" in review
        assert "NVDA" in review


class TestBuildPortfolioSummary:
    def test_no_trades(self):
        tracker = {"summary": {"total_trades": 0}}
        result = _build_portfolio_summary(tracker)
        assert "first episode" in result.lower() or "no simulated" in result.lower()

    def test_with_trades(self):
        tracker = {
            "summary": {
                "total_trades": 10,
                "wins": 6,
                "losses": 3,
                "breakeven": 1,
                "win_rate_pct": 60.0,
                "cumulative_pnl": 125.50,
                "average_return_pct": 1.26,
                "best_trade_pct": 4.5,
                "worst_trade_pct": -2.1,
                "current_streak": 2,
            },
        }
        result = _build_portfolio_summary(tracker)
        assert "60%" in result
        assert "$+125.50" in result
        assert "6W" in result


class TestFormatStreak:
    def test_positive(self):
        assert _format_streak(3) == "3 wins"

    def test_single_win(self):
        assert _format_streak(1) == "1 win"

    def test_negative(self):
        assert _format_streak(-2) == "2 losses"

    def test_single_loss(self):
        assert _format_streak(-1) == "1 loss"

    def test_zero(self):
        assert _format_streak(0) == "even"
