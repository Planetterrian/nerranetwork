"""
Statistical validation gates before allowing live trading.

These are conservative thresholds designed to protect the user.
"""

from __future__ import annotations

from typing import Dict


def can_go_live(paper_summary: Dict, min_trades: int = 50) -> tuple[bool, str]:
    """
    Returns (allowed, reason).
    """
    total = paper_summary.get("total_trades", 0)
    win_rate = paper_summary.get("win_rate_pct", 0)
    alpha = paper_summary.get("alpha_vs_nasdaq", 0.0)  # This should come from paper_tracker

    if total < min_trades:
        return False, f"Need at least {min_trades} closed trades (currently {total})"

    if alpha <= 0:
        return False, f"No positive alpha vs NASDAQ yet (current: {alpha:+.2f}%)"

    if win_rate < 52:
        return False, f"Win rate too low for live trading ({win_rate:.1f}%)"

    # Very rough rule of thumb
    if alpha < 2.0:
        return False, f"Alpha too small to justify live risk ({alpha:+.2f}%)"

    return True, "Paper system meets minimum validation criteria for small live allocation."
