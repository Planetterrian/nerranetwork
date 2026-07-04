"""Shadow-mode executor (Phase 2 of the SnapTrade plan).

Runs the FULL order pipeline — signal → risk gates → decision-time quote
→ marketable-limit price + sizing — and then, instead of placing an
order, appends the would-be order to a committed shadow ledger. This IS
the paper-trading layer (SnapTrade's sandbox cannot place orders), and
its accumulating decision-time quotes are the raw material for the
sim-vs-reality slippage model.

The ledger contains only hypothetical orders on public symbols — the
same information class as the published sim tracker — so unlike the
account mirror it is safe to commit.

No SnapTrade credentials are needed in shadow mode; quotes come from
yfinance. Deliberately NO order-placement call exists here (pinned by
tests/test_snaptrade_execution.py — Phase-1/2 read-only contract).
"""

from __future__ import annotations

import datetime
import json
import logging
from pathlib import Path

from execution.risk import RiskConfig, validate_signal

logger = logging.getLogger(__name__)

LEDGER_SCHEMA_VERSION = 1


def load_ledger(path: Path) -> dict:
    if path.exists():
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            data.setdefault("orders", [])
            return data
        except (json.JSONDecodeError, OSError) as exc:
            logger.warning("Failed to load shadow ledger: %s — starting fresh", exc)
    return {"schema_version": LEDGER_SCHEMA_VERSION, "mode": "shadow", "orders": []}


def save_ledger(ledger: dict, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(ledger, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def decision_quote(yf_symbol: str) -> float | None:
    """Best-effort quote at decision time (latest 1-minute bar close)."""
    try:
        import yfinance as yf
        hist = yf.Ticker(yf_symbol).history(period="1d", interval="1m")
        if hist is not None and not hist.empty:
            price = float(hist["Close"].iloc[-1])
            if price > 0:
                return round(price, 4)
    except Exception as exc:  # noqa: BLE001
        logger.warning("decision quote failed for %s: %s", yf_symbol, exc)
    return None


def run_shadow(
    signal: dict,
    ledger: dict,
    config: RiskConfig,
    *,
    quote_fn=decision_quote,
    now: datetime.datetime | None = None,
) -> dict:
    """Process one signal; append exactly one ledger entry; return it.

    Idempotent: a signal whose ``client_order_id`` already appears in the
    ledger is skipped with a ``duplicate`` decision (a re-run workflow
    cannot double-log, mirroring the live layer's idempotent placement).
    """
    now = now or datetime.datetime.now(datetime.timezone.utc)
    today = now.date()
    prior_ids = {
        o.get("client_order_id") for o in ledger.get("orders", [])
        if o.get("client_order_id")
    }

    trade = signal.get("trade") or {}
    entry: dict = {
        "logged_at": now.isoformat(timespec="seconds"),
        "mode": "shadow",
        "episode_num": signal.get("episode_num"),
        "client_order_id": trade.get("client_order_id"),
        "symbol": trade.get("symbol"),
        "snaptrade_symbol": trade.get("snaptrade_symbol"),
        "suggested_account": trade.get("suggested_account"),
        "currency": trade.get("currency"),
        "trade_type": trade.get("trade_type"),
        "pick_reference_price": trade.get("pick_reference_price"),
    }

    order_id = trade.get("client_order_id")
    if order_id and order_id in prior_ids:
        entry["decision"] = "duplicate"
        entry["skip_reasons"] = ["client_order_id already in ledger"]
        logger.info("Shadow: duplicate signal %s — not re-logged", order_id)
        return entry  # deliberately NOT appended

    ok, reasons = validate_signal(
        signal, config, today=today, prior_order_ids=prior_ids)
    if not ok:
        entry["decision"] = "skipped"
        entry["skip_reasons"] = reasons
        logger.info("Shadow: signal skipped — %s", "; ".join(reasons))
        ledger["orders"].append(entry)
        return entry

    quote = quote_fn(trade["snaptrade_symbol"])
    quote_source = "decision_time_quote"
    if quote is None:
        quote = trade.get("pick_reference_price")
        quote_source = "pick_reference_fallback"
    if not isinstance(quote, (int, float)) or quote <= 0:
        entry["decision"] = "skipped"
        entry["skip_reasons"] = ["no usable quote at decision time"]
        ledger["orders"].append(entry)
        return entry

    limit_price = round(quote * (1 + config.max_slippage_pct / 100), 2)
    units = round(config.max_position_usd / limit_price, 4)

    entry.update({
        "decision": "would_place",
        "order_type": "Limit",
        "time_in_force": "Day",
        "quote": round(float(quote), 4),
        "quote_source": quote_source,
        "limit_price": limit_price,
        "units": units,
        "position_usd": config.max_position_usd,
        "pick_date": trade.get("pick_date"),
    })
    logger.info(
        "Shadow: WOULD PLACE BUY %s x%s @ limit $%.2f (quote $%.4f, %s)",
        entry["snaptrade_symbol"], units, limit_price, quote, quote_source,
    )
    ledger["orders"].append(entry)
    return entry


# ---------------------------------------------------------------------------
# Shadow exits (Phase 2.5) — the round trip that makes shadow P&L real
# ---------------------------------------------------------------------------

def _exit_due_date(pick_date: datetime.date, trade_type: str) -> datetime.date:
    """The first executor run day on/after the sim's exit.

    Mirrors the sim's calendar: flash trades close the next trading day
    (executor runs weekdays, so the next weekday); weekly holds close on
    the Friday run (this week's Friday for Mon-Thu picks, NEXT Friday
    for Fri/Sat/Sun picks — a Friday pick isn't open yet on its own
    Friday run, matching ``_evaluate_open_trade``).
    """
    wd = pick_date.weekday()
    if trade_type == "flash":
        days = 3 if wd == 4 else (2 if wd == 5 else 1)  # Fri→Mon, Sat→Mon
        return pick_date + datetime.timedelta(days=days)
    if wd == 4:
        return pick_date + datetime.timedelta(days=7)
    if wd == 5:
        return pick_date + datetime.timedelta(days=6)
    if wd == 6:
        return pick_date + datetime.timedelta(days=5)
    return pick_date + datetime.timedelta(days=4 - wd)


def run_shadow_exits(
    ledger: dict,
    config: RiskConfig,
    *,
    quote_fn=decision_quote,
    now: datetime.datetime | None = None,
) -> list[dict]:
    """Log would-be SELLs for every open shadow position past its due date.

    Each ``would_place`` entry gets exactly one paired ``would_sell``
    (idempotent via the ``exit_client_order_id`` = ``<entry id>-exit``),
    carrying the decision-time quote and the round-trip shadow return —
    quote-to-quote, so it's directly comparable against the sim's
    open-to-close return for the same trade.
    """
    now = now or datetime.datetime.now(datetime.timezone.utc)
    today = now.date()
    orders = ledger.get("orders", [])
    existing_exit_ids = {
        o.get("exit_client_order_id") for o in orders
        if o.get("exit_client_order_id")
    }

    exits: list[dict] = []
    for entry in list(orders):
        if entry.get("decision") != "would_place":
            continue
        exit_id = f"{entry.get('client_order_id')}-exit"
        if exit_id in existing_exit_ids:
            continue
        pick_date = None
        if isinstance(entry.get("pick_date"), str):
            try:
                pick_date = datetime.date.fromisoformat(entry["pick_date"])
            except ValueError:
                pick_date = None
        if pick_date is None and isinstance(entry.get("logged_at"), str):
            pick_date = datetime.date.fromisoformat(entry["logged_at"][:10])
        if pick_date is None:
            continue
        due = _exit_due_date(pick_date, entry.get("trade_type", "weekly"))
        if today < due:
            continue

        quote = quote_fn(entry.get("snaptrade_symbol"))
        quote_source = "decision_time_quote"
        if not isinstance(quote, (int, float)) or quote <= 0:
            # No quote today — leave the position open; a later run
            # retries (mirrors the sim's leave-open-when-no-bar rule).
            logger.warning(
                "Shadow exit: no quote for %s — will retry next run",
                entry.get("snaptrade_symbol"))
            continue

        entry_quote = entry.get("quote")
        shadow_return = (
            round((quote - entry_quote) / entry_quote * 100, 3)
            if isinstance(entry_quote, (int, float)) and entry_quote
            else None
        )
        exit_entry = {
            "logged_at": now.isoformat(timespec="seconds"),
            "mode": "shadow",
            "decision": "would_sell",
            "episode_num": entry.get("episode_num"),
            "client_order_id": entry.get("client_order_id"),
            "exit_client_order_id": exit_id,
            "symbol": entry.get("symbol"),
            "snaptrade_symbol": entry.get("snaptrade_symbol"),
            "trade_type": entry.get("trade_type"),
            "order_type": "Limit",
            "time_in_force": "Day",
            "quote": round(float(quote), 4),
            "quote_source": quote_source,
            "limit_price": round(quote * (1 - config.max_slippage_pct / 100), 2),
            "units": entry.get("units"),
            "shadow_return_pct": shadow_return,
        }
        logger.info(
            "Shadow: WOULD SELL %s x%s @ ~$%.4f (round trip %s%%)",
            exit_entry["snaptrade_symbol"], exit_entry["units"], quote,
            shadow_return,
        )
        orders.append(exit_entry)
        existing_exit_ids.add(exit_id)
        exits.append(exit_entry)
    return exits
