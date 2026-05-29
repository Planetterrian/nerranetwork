"""
Very basic historical backtester for the MIT strategy.

This lets you replay the current MIT logic against past market data
to get a sense of how it would have performed.
"""

from __future__ import annotations

from typing import List, Dict
from datetime import date, timedelta

from .mit_context import get_mit_context_for_trading
from .strategy import generate_trade_ideas


def simple_backtest(symbols: List[str], lookback_days: int = 60) -> Dict:
    """
    Extremely simplified backtest.
    In reality you would feed real historical prices and simulate entries/exits.
    """
    mit_context = get_mit_context_for_trading()

    # Simulate "today" as now, generate ideas as if we were running live
    ideas = generate_trade_ideas(symbols, market_data={}, mit_context=mit_context, max_ideas=3)

    return {
        "as_of": str(date.today()),
        "mit_context_used": {
            "total_trades": mit_context.get("total_trades"),
            "alpha_vs_nasdaq": mit_context.get("alpha_vs_nasdaq"),
            "active_lessons": len(mit_context.get("active_lessons", [])),
        },
        "ideas_generated": ideas,
        "note": "This is a forward-looking simulation using current MIT state. Real backtesting requires historical price data."
    }


if __name__ == "__main__":
    result = simple_backtest(["AAPL", "TSLA", "NVDA", "AMD"])
    import pprint
    pprint.pprint(result)
