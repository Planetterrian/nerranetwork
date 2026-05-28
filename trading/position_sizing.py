"""
Edge-based position sizing using MIT-style recursive data.

This is one of the highest-leverage improvements for long-term outperformance.
"""

from __future__ import annotations

from typing import Dict


def kelly_position_size(
    account_equity: float,
    expectancy_stats: Dict[str, float],
    max_kelly_fraction: float = 0.25,
    max_position_pct: float = 0.08,
) -> float:
    """
    Returns recommended position size as % of equity using half-Kelly.
    """
    kelly = expectancy_stats.get("kelly_fraction", 0.0)
    if kelly <= 0:
        return 0.02  # Very small size if no edge

    size = min(kelly, max_kelly_fraction) * account_equity
    return min(size / account_equity, max_position_pct)


def volatility_adjusted_size(
    base_size_pct: float,
    recent_volatility: float,      # annualized, e.g. 0.35
    target_volatility: float = 0.25,
) -> float:
    """
    Reduce size on high-vol names so that risk is roughly constant.
    """
    if recent_volatility <= 0:
        return base_size_pct
    adjustment = target_volatility / recent_volatility
    return base_size_pct * min(adjustment, 1.5)  # Don't increase size too aggressively
