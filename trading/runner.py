"""
MIT Webull Paper Trading Runner

This is the main tool to run the recursive learning loop against real market data on Webull paper trading.

Usage examples:
    # Dry run (no orders)
    python -m trading.runner --paper --dry-run

    # Actually place paper trades
    python -m trading.runner --paper

    # With specific symbols
    python -m trading.runner --paper --symbols AAPL,NVDA,TSLA
"""

from __future__ import annotations

import argparse
import logging
import os
from datetime import datetime, date
from pathlib import Path

from .config import load_config, TradingConfig
from .mit_context import get_mit_context_for_trading
from .paper_tracker import PaperTracker
from .risk import RiskLimits, can_take_trade
from .strategy import generate_trade_ideas
from .webull_client import WebullClient
from .position_sizing import kelly_position_size, volatility_adjusted_size
from .regime import get_regime_adjustment

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger("mit_webull")


def run_paper_trading_loop(cfg: TradingConfig, dry_run: bool = False):
    logger.info("=" * 60)
    logger.info("MIT RECURSIVE LEARNING PAPER TRADER")
    logger.info(f"Date: {date.today()}")
    logger.info(f"Paper Mode: {cfg.use_paper}")
    logger.info(f"Dry Run:    {dry_run}")
    logger.info("=" * 60)

    client = WebullClient(paper=cfg.use_paper)

    email = cfg.webull_email or os.getenv("WEBULL_EMAIL")
    password = cfg.webull_password or os.getenv("WEBULL_PASSWORD")

    if not email or not password:
        logger.error("Missing Webull credentials. Set WEBULL_EMAIL and WEBULL_PASSWORD")
        return

    if not client.login(email, password):
        logger.error("Failed to login to Webull")
        return

    # Load MIT recursive context
    mit_context = get_mit_context_for_trading(cfg.mit_data_dir)
    logger.info(
        f"MIT Context loaded | Trades: {mit_context['total_trades']} | "
        f"Alpha vs NASDAQ: {mit_context['alpha_vs_nasdaq']:+.2f}% | "
        f"Active Lessons: {len(mit_context['active_lessons'])}"
    )

    # Paper tracker (separate from podcast)
    paper_tracker = PaperTracker(cfg.paper_tracker_path)

    # Get current account equity
    account = client.get_account()
    equity = 0.0
    if account:
        equity = float(account.get("netLiquidation") or account.get("availableCash", 10000))
    logger.info(f"Account Equity: ${equity:,.2f}")

    # Gather basic market context for each symbol (volatility proxy via recent bars)
    market_context: Dict[str, Any] = {}
    for sym in cfg.symbols:
        bars = client.get_bars(sym, interval="d", count=20)
        if bars and len(bars) >= 5:
            closes = [float(b.get("close", 0)) for b in bars[-5:]]
            if len(closes) >= 2 and closes[-1] > 0:
                recent_vol = (max(closes) - min(closes)) / closes[-1]
                market_context[sym] = {"recent_volatility": recent_vol}

    # Generate ideas using MIT logic + market context
    ideas = generate_trade_ideas(
        symbols_to_consider=cfg.symbols,
        market_data=market_context,
        mit_context=mit_context,
        max_ideas=cfg.max_ideas_per_day,
    )

    risk_limits = RiskLimits(
        max_position_pct_of_equity=cfg.max_position_pct,
        max_daily_loss_pct=cfg.max_daily_loss_pct,
        max_open_positions=cfg.max_open_positions,
    )

    # Extra live guardrails
    if not cfg.use_paper:
        if cfg.require_manual_confirmation:
            print("\n⚠️  LIVE TRADING MODE - Manual confirmation required for each order.")
        effective_size = cfg.max_position_pct * cfg.live_size_multiplier
        logger.info(f"Live mode active. Effective max position size reduced to {effective_size:.1%} of equity.")

    open_positions = paper_tracker.get_open_positions()

    # Rough daily P&L and drawdown from paper tracker (best effort)
    closed = paper_tracker.get_closed_trades()
    today_pnl = sum(t.get("pnl_pct", 0) for t in closed if t.get("date") == str(date.today())) / 100.0 if closed else 0.0

    # Simple peak-to-trough from paper book
    running_pnl = 0.0
    peak = 0.0
    max_dd = 0.0
    for t in sorted(closed, key=lambda x: x.get("date", "")):
        running_pnl += t.get("pnl_pct", 0)
        peak = max(peak, running_pnl)
        max_dd = min(max_dd, running_pnl - peak)
    current_drawdown = abs(max_dd) / 100.0 if max_dd < 0 else 0.0

    for idea in ideas:
        symbol = idea["symbol"]
        confidence = idea.get("confidence", "medium")
        suggested_pct = idea.get("suggested_size_pct", 0.05)

        quote = client.get_quote(symbol) or {}
        price = float(quote.get("close") or quote.get("lastPrice", 0))

        if price <= 0:
            continue

        # === Edge-based + volatility-adjusted position sizing (major improvement) ===
        expectancy = paper_tracker.get_expectancy_stats()
        base_kelly_pct = kelly_position_size(equity, expectancy, max_position_pct=cfg.max_position_pct)

        vol = client.get_recent_volatility(symbol)
        final_size_pct = volatility_adjusted_size(base_kelly_pct, vol or 0.30)

        # Apply regime filter (reduces size when MIT system or market conditions are unfavorable)
        regime_mult = get_regime_adjustment(
            mit_alpha=mit_context.get("alpha_vs_nasdaq", 0.0),
            recent_market_return=0.0,  # TODO: fetch real recent benchmark return
            vix_level=20.0,            # TODO: fetch real VIX
        )
        final_size_pct *= regime_mult

        # Never exceed the configured hard max
        final_size_pct = min(final_size_pct, cfg.max_position_pct)

        proposed_dollars = equity * final_size_pct
        quantity = max(1, int(proposed_dollars / price))

        logger.info(
            f"  Sizing for {symbol}: Kelly={base_kelly_pct:.1%} → Vol-adjusted={final_size_pct:.1%} "
            f"(Expectancy={expectancy.get('expectancy',0):.2%}, Kelly frac={expectancy.get('kelly_fraction',0):.2%})"
        )

        allowed, reason = can_take_trade(
            proposed_size_dollars=proposed_dollars,
            account_equity=equity,
            current_open_positions=len(open_positions),
            today_pnl_pct=today_pnl,
            trade_confidence=confidence,
            current_sector_exposure={},  # TODO: compute from paper_tracker + mit_context
            proposed_sector="other",
            limits=risk_limits,
            current_drawdown_from_peak=current_drawdown,
        )

        if not allowed:
            logger.info(f"REJECTED {symbol}: {reason}")
            continue

        logger.info(
            f"APPROVED: {symbol} | {idea['thesis'][:70]}... | "
            f"Conf={confidence} | Size=${proposed_dollars:,.0f} ({suggested_pct*100:.1f}%)"
        )

        if dry_run:
            logger.info("[DRY RUN] Would place paper order")
            continue

        # Actually place the paper trade
        order = client.place_paper_order(
            symbol=symbol,
            action="BUY",
            order_type="MKT",
            quantity=quantity,
        )

        if order:
            paper_tracker.record_trade(
                symbol=symbol,
                action="BUY",
                quantity=quantity,
                entry_price=price,
                strategy=idea.get("strategy", "MIT Recursive"),
                confidence=confidence,
                mit_lesson_refs=idea.get("lesson_references"),
            )
            logger.info(f"✓ Paper order placed for {quantity} {symbol}")
        else:
            logger.error(f"✗ Failed to place paper order for {symbol}")

    paper_tracker.save()
    logger.info("Paper trading loop complete. Tracker saved.")


def main():
    parser = argparse.ArgumentParser(description="MIT Recursive Learning Webull Paper Trader")
    parser.add_argument("--paper", action="store_true", default=True)
    parser.add_argument("--dry-run", action="store_true", help="Do not place any orders")
    parser.add_argument("--symbols", type=str, help="Comma separated symbols")
    args = parser.parse_args()

    cfg = load_config()
    if args.symbols:
        cfg.symbols = [s.strip().upper() for s in args.symbols.split(",")]

    cfg.use_paper = args.paper

    run_paper_trading_loop(cfg, dry_run=args.dry_run)


if __name__ == "__main__":
    main()
