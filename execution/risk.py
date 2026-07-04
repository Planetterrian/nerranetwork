"""Hard, deterministic risk gates for the MIT execution layer.

Every order path — shadow (Phase 2) and, later, live (Phase 3) — runs
through ``validate_signal`` before anything else happens. The gates are
plain code with env-tunable caps: no LLM output is ever interpreted
here, and every rejection is an explicit, logged reason. Fail closed:
any doubt means no order.
"""

from __future__ import annotations

import dataclasses
import datetime
import os


def _env_float(name: str, default: float) -> float:
    try:
        return float(os.environ.get(name, "") or default)
    except ValueError:
        return default


def _env_int(name: str, default: int) -> int:
    try:
        return int(os.environ.get(name, "") or default)
    except ValueError:
        return default


@dataclasses.dataclass(frozen=True)
class RiskConfig:
    """Caps for one executor run. Defaults are the Phase-3 micro-live
    values from docs/mit_snaptrade_live_trading_plan.md §4."""

    live_trading_enabled: bool = False   # global kill switch (unset = off)
    max_position_usd: float = 250.0
    max_slippage_pct: float = 0.5        # marketable-limit collar vs quote
    min_price_usd: float = 2.0           # no penny/OTC-grade picks
    max_signal_age_days: int = 1         # stale signal = no trade
    max_open_positions: int = 1
    max_daily_orders: int = 2

    @classmethod
    def from_env(cls) -> "RiskConfig":
        return cls(
            live_trading_enabled=(
                os.environ.get("LIVE_TRADING_ENABLED", "").strip() == "1"),
            max_position_usd=_env_float("MIT_MAX_POSITION_USD", 250.0),
            max_slippage_pct=_env_float("MIT_MAX_SLIPPAGE_PCT", 0.5),
            min_price_usd=_env_float("MIT_MIN_PRICE_USD", 2.0),
            max_signal_age_days=_env_int("MIT_MAX_SIGNAL_AGE_DAYS", 1),
            max_open_positions=_env_int("MIT_MAX_OPEN_POSITIONS", 1),
            max_daily_orders=_env_int("MIT_MAX_DAILY_ORDERS", 2),
        )


def validate_signal(
    signal: dict,
    config: RiskConfig,
    *,
    today: datetime.date,
    prior_order_ids: frozenset[str] | set[str] = frozenset(),
) -> tuple[bool, list[str]]:
    """Return ``(ok, reasons)``. Empty reasons ⇢ the order may proceed.

    Pure function — no I/O, no clock reads — so every gate is unit-
    testable and an executor run is reproducible from its inputs.
    """
    reasons: list[str] = []

    if not isinstance(signal, dict) or signal.get("schema_version") != 1:
        return False, ["unrecognized signal schema"]

    if signal.get("action") != "new_trade":
        reasons.append(
            f"signal action is '{signal.get('action')}' "
            f"(reason: {signal.get('reason')}) — nothing to trade")
        return False, reasons

    generated = signal.get("generated_at")
    try:
        generated_date = datetime.date.fromisoformat(str(generated)[:10])
        age = (today - generated_date).days
        if age > config.max_signal_age_days:
            reasons.append(
                f"signal is stale ({age}d old, max "
                f"{config.max_signal_age_days}d)")
        elif age < 0:
            reasons.append(f"signal is from the future ({generated})")
    except ValueError:
        reasons.append(f"unparseable generated_at: {generated!r}")

    trade = signal.get("trade") or {}
    if not trade.get("snaptrade_symbol"):
        reasons.append("no snaptrade_symbol on the trade")
    if trade.get("side") != "BUY":
        reasons.append(f"unsupported side {trade.get('side')!r}")
    if not trade.get("pick_validated"):
        reasons.append(
            "pick was not validated at record time (no reference price) — "
            "possible bogus ticker")
    ref = trade.get("pick_reference_price")
    if isinstance(ref, (int, float)):
        if ref < config.min_price_usd:
            reasons.append(
                f"reference price ${ref:.2f} below the "
                f"${config.min_price_usd:.2f} floor")
    elif trade.get("pick_validated"):
        reasons.append("pick_validated set but no reference price")

    order_id = trade.get("client_order_id")
    if not order_id:
        reasons.append("missing client_order_id")
    elif order_id in prior_order_ids:
        reasons.append(f"duplicate client_order_id {order_id} (already processed)")

    return (not reasons), reasons
