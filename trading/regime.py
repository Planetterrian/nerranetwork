"""
Simple regime detection for the MIT trading system.

Reduces aggressiveness when conditions are unfavorable for the current MIT edge.
"""

from __future__ import annotations

from typing import Dict


def get_regime_adjustment(
    mit_alpha: float,
    recent_market_return: float = 0.0,   # last 20-60 day return of benchmark
    vix_level: float = 20.0,
) -> float:
    """
    Returns a multiplier (0.4 – 1.0) to apply to position sizes.
    """
    multiplier = 1.0

    # MIT system is underperforming → de-risk
    if mit_alpha < -3.0:
        multiplier *= 0.55
    elif mit_alpha < 0:
        multiplier *= 0.75

    # High volatility / fear regime
    if vix_level > 28:
        multiplier *= 0.65
    elif vix_level > 22:
        multiplier *= 0.85

    # Strong trending market (can be good or bad depending on MIT style)
    if abs(recent_market_return) > 0.12:  # very strong move
        multiplier *= 0.80

    return max(0.40, min(multiplier, 1.0))
