"""
Risk management rules for the MIT Webull trader.

Designed to give the recursive learning loop the highest possible chance of long-term outperformance
while protecting against ruin.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Any, Optional


@dataclass
class RiskLimits:
    # Core position sizing
    max_position_pct_of_equity: float = 0.06          # Hard max 6%
    target_risk_pct_of_equity: float = 0.015          # Target 1.5% risk per trade (vol-adjusted ideal)

    # Portfolio level controls
    max_open_positions: int = 5
    max_sector_exposure_pct: float = 0.25             # Max 25% in any one sector

    # Circuit breakers
    max_daily_loss_pct: float = 0.012
    max_drawdown_from_peak_pct: float = 0.08          # Reduce size aggressively after this

    # Live vs Paper
    min_confidence_for_live: str = "high"


def calculate_position_size(
    account_equity: float,
    entry_price: float,
    stop_price: Optional[float],
    desired_risk_pct: float,
    max_position_pct: float,
    atr: Optional[float] = None,
) -> int:
    """
    Volatility-aware position sizing.
    If stop_price or atr is provided, sizes to risk ~desired_risk_pct of equity.
    Falls back to max_position_pct if no stop/atr available.
    """
    if stop_price and stop_price > 0:
        risk_per_share = abs(entry_price - stop_price)
        if risk_per_share > 0:
            risk_dollars = account_equity * desired_risk_pct
            qty = int(risk_dollars / risk_per_share)
            max_qty_by_pct = int((account_equity * max_position_pct) / entry_price)
            return max(1, min(qty, max_qty_by_pct))

    # Fallback: simple percentage of equity
    max_dollars = account_equity * max_position_pct
    return max(1, int(max_dollars / entry_price))


def can_take_trade(
    proposed_size_dollars: float,
    account_equity: float,
    current_open_positions: int,
    today_pnl_pct: float,
    trade_confidence: str,
    current_sector_exposure: Dict[str, float] | None = None,   # e.g. {"tech": 0.18, "energy": 0.09}
    proposed_sector: str = "other",
    limits: RiskLimits | None = None,
    current_drawdown_from_peak: float = 0.0,
) -> tuple[bool, str]:
    """
    Multi-layered risk gate. Returns (allowed, reason).
    """
    limits = limits or RiskLimits()

    # 1. Hard position count limit
    if current_open_positions >= limits.max_open_positions:
        return False, "Maximum number of open positions reached"

    # 2. Position size limit
    position_pct = proposed_size_dollars / account_equity
    if position_pct > limits.max_position_pct_of_equity:
        return False, f"Position would be {position_pct:.1%} of equity (limit {limits.max_position_pct_of_equity:.0%})"

    # 3. Daily loss circuit breaker
    if today_pnl_pct <= -limits.max_daily_loss_pct:
        return False, f"Daily loss limit breached ({today_pnl_pct:.2%})"

    # 4. Drawdown-based de-risking
    if current_drawdown_from_peak >= limits.max_drawdown_from_peak_pct:
        reduced_limit = limits.max_position_pct_of_equity * 0.5
        if position_pct > reduced_limit:
            return False, f"Drawdown de-risking active. Max position now {reduced_limit:.0%}"

    # 5. Sector concentration limit (best effort)
    current_sector_pct = 0.0
    if current_sector_exposure:
        current_sector_pct = current_sector_exposure.get(proposed_sector.lower(), 0.0)
    if current_sector_pct + position_pct > limits.max_sector_exposure_pct:
        return False, f"Sector {proposed_sector} would exceed {limits.max_sector_exposure_pct:.0%} exposure limit"

    # 6. Confidence gate for live trading
    if trade_confidence.lower() not in ("high", "very high") and limits.min_confidence_for_live:
        return False, f"Confidence '{trade_confidence}' is below live trading threshold"

    return True, "Trade approved by risk system"
