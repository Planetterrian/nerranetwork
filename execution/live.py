"""Live executor (Phase 3 of the SnapTrade plan) — DORMANT until armed.

Places real micro-live orders from the trade signal, behind gates that
must ALL pass, in order, before any brokerage call happens:

1. ``LIVE_TRADING_ENABLED=1`` (the kill switch; unset = this module
   returns immediately without loading credentials),
2. SnapTrade env config present,
3. not halted (two consecutive rejected orders self-halt the layer
   until the operator clears ``live_execution_state.json``),
4. the same pure risk gates shadow mode uses (``execution/risk.py``),
5. daily-order and open-position caps,
6. a resolvable target account and a live decision-time quote —
   no quote means no order, never a blind placement.

State model (public repo — privacy by construction):
- ``live_execution_state.json`` (committed): halt flag, reject counter,
  and an order INDEX carrying only client_order_ids/symbols/status —
  the idempotency memory across CI runs. No account ids, no dollar
  amounts.
- ``live_ledger.json`` (GITIGNORED, uploaded as CI artifact): the full
  audit trail (account id, units, prices).

Sizing is INTEGER shares under ``max_position_usd`` (fractional support
is broker-dependent; a price above the cap skips the trade — correct
behavior for micro-live). Exits follow the sim's calendar via
``execution.shadow._exit_due_date`` and sell no more than the units the
account actually holds.

The LLM never touches this path: inputs are the deterministic signal
artifact and prior state, nothing else.
"""

from __future__ import annotations

import datetime
import json
import logging
import os
from pathlib import Path

from execution import shadow
from execution.risk import RiskConfig, validate_signal

logger = logging.getLogger(__name__)

STATE_SCHEMA_VERSION = 1


def notify(line: str) -> None:
    """Best-effort operator notification — every live action must be seen."""
    url = os.environ.get("NOTIFICATION_WEBHOOK_URL", "").strip()
    if not url:
        return
    try:
        import requests
        requests.post(url, json={"text": line}, timeout=10)
    except Exception as exc:  # noqa: BLE001
        logger.warning("notification failed (non-fatal): %s", exc)


def load_state(path: Path) -> dict:
    if path.exists():
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            data.setdefault("orders", [])
            data.setdefault("halted", False)
            data.setdefault("consecutive_rejects", 0)
            return data
        except (json.JSONDecodeError, OSError) as exc:
            logger.warning("Failed to load live state: %s — starting fresh", exc)
    return {
        "schema_version": STATE_SCHEMA_VERSION,
        "halted": False,
        "halt_reason": None,
        "consecutive_rejects": 0,
        "orders": [],
    }


def save_state(state: dict, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(state, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def load_ledger(path: Path) -> dict:
    if path.exists():
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            data.setdefault("orders", [])
            return data
        except (json.JSONDecodeError, OSError):
            pass
    return {"schema_version": STATE_SCHEMA_VERSION, "mode": "live", "orders": []}


save_ledger = shadow.save_ledger  # same shape/serialization


def _default_client():
    from execution import snaptrade_client
    return snaptrade_client


def resolve_account(accounts: list[dict], suggested: str, currency: str) -> dict | None:
    """Pick the connected account for a signal's routing hint.

    Institution-name substring match on the suggestion (``wealthsimple``
    / ``webull``); among matches, prefer one whose reported currency
    matches. None when nothing matches — the caller skips loudly rather
    than guessing an account for a real order.
    """
    needle = (suggested or "").lower()
    matches = [
        a for a in accounts or []
        if needle and needle in str(a.get("institution_name", "")).lower()
    ]
    if not matches:
        return None
    for acct in matches:
        bal = acct.get("balance") or {}
        total = bal.get("total") if isinstance(bal, dict) else None
        acct_ccy = (total or {}).get("currency") if isinstance(total, dict) else None
        if acct_ccy and str(acct_ccy).upper() == (currency or "").upper():
            return acct
    return matches[0]


def _is_rejected(result: dict) -> bool:
    return str(result.get("status", "")).upper() in ("REJECTED", "FAILED")


def _halt(state: dict, reason: str) -> None:
    state["halted"] = True
    state["halt_reason"] = reason
    logger.error("LIVE TRADING HALTED: %s", reason)
    notify(f"MIT LIVE HALTED: {reason} — clear live_execution_state.json "
           f"after investigating.")


def run_live_entry(
    signal: dict,
    state: dict,
    ledger: dict,
    config: RiskConfig,
    *,
    client=None,
    quote_fn=shadow.decision_quote,
    now: datetime.datetime | None = None,
) -> dict:
    """Process today's signal into at most one real BUY. Returns a decision
    dict; appends to state+ledger only when something noteworthy happened."""
    now = now or datetime.datetime.now(datetime.timezone.utc)
    today = now.date()

    # Gate 1 — kill switch, before anything else (no credential loads).
    if not config.live_trading_enabled:
        return {"decision": "disabled",
                "note": "LIVE_TRADING_ENABLED is not 1 — live layer dormant"}
    client = client or _default_client()
    if not client.is_configured():
        return {"decision": "skipped", "skip_reasons": ["SnapTrade env not configured"]}

    # Gate 2 — self-halt.
    if state.get("halted"):
        notify("MIT LIVE: still halted "
               f"({state.get('halt_reason')}) — no entry attempted.")
        return {"decision": "halted", "skip_reasons": [state.get("halt_reason")]}

    prior_ids = {o.get("client_order_id") for o in state.get("orders", [])}
    ok, reasons = validate_signal(
        signal, config, today=today, prior_order_ids=prior_ids)
    if not ok:
        return {"decision": "skipped", "skip_reasons": reasons}

    trade = signal["trade"]

    # Gate 3 — position/order caps from the committed index.
    todays = [o for o in state["orders"]
              if str(o.get("logged_at", ""))[:10] == today.isoformat()]
    if len(todays) >= config.max_daily_orders:
        return {"decision": "skipped",
                "skip_reasons": [f"daily order cap ({config.max_daily_orders}) reached"]}
    open_entries = [
        o for o in state["orders"]
        if o.get("kind") == "entry" and not o.get("exited")
        and not _is_rejected(o)
    ]
    if len(open_entries) >= config.max_open_positions:
        return {"decision": "skipped",
                "skip_reasons": [f"open-position cap ({config.max_open_positions}) reached"]}

    # Gate 4 — a real account and a real quote.
    accounts = client.list_accounts()
    account = resolve_account(
        accounts, trade.get("suggested_account"), trade.get("currency"))
    if account is None:
        notify(f"MIT LIVE: no connected account matches "
               f"'{trade.get('suggested_account')}' — entry skipped.")
        return {"decision": "skipped", "skip_reasons": ["no matching account"]}
    quote = quote_fn(trade["snaptrade_symbol"])
    if not isinstance(quote, (int, float)) or quote <= 0:
        return {"decision": "skipped",
                "skip_reasons": ["no live quote — never place blind"]}

    limit_price = round(quote * (1 + config.max_slippage_pct / 100), 2)
    units = int(config.max_position_usd // limit_price)
    if units < 1:
        return {"decision": "skipped",
                "skip_reasons": [f"price ${limit_price:.2f} exceeds the "
                                 f"${config.max_position_usd:.0f} position cap"]}

    try:
        result = client.place_limit_order(
            account_id=str(account.get("id")),
            symbol=trade["snaptrade_symbol"],
            action="BUY",
            units=units,
            limit_price=limit_price,
            client_order_id=trade["client_order_id"],
        )
    except Exception as exc:  # noqa: BLE001
        state["consecutive_rejects"] = int(state.get("consecutive_rejects", 0)) + 1
        if state["consecutive_rejects"] >= 2:
            _halt(state, f"placement raised twice in a row (last: {exc})")
        notify(f"MIT LIVE: BUY {trade['snaptrade_symbol']} FAILED to place: {exc}")
        return {"decision": "error", "skip_reasons": [str(exc)]}

    status = str(result.get("status", "UNKNOWN")).upper()
    index_entry = {
        "kind": "entry",
        "client_order_id": trade["client_order_id"],
        "symbol": trade["snaptrade_symbol"],
        "trade_type": trade.get("trade_type"),
        "pick_date": trade.get("pick_date"),
        "status": status,
        "logged_at": now.isoformat(timespec="seconds"),
    }
    state["orders"].append(index_entry)
    ledger["orders"].append({
        **index_entry,
        "mode": "live",
        "account_id": str(account.get("id")),
        "units": units,
        "limit_price": limit_price,
        "quote": round(float(quote), 4),
        "position_usd": round(units * limit_price, 2),
        "brokerage_order_id": result.get("brokerage_order_id"),
        "stop_loss": trade.get("stop_loss"),
    })

    if _is_rejected(result):
        state["consecutive_rejects"] = int(state.get("consecutive_rejects", 0)) + 1
        if state["consecutive_rejects"] >= 2:
            _halt(state, "two consecutive rejected orders")
        notify(f"MIT LIVE: BUY {units}x {trade['snaptrade_symbol']} "
               f"@ ${limit_price:.2f} was {status}.")
    else:
        state["consecutive_rejects"] = 0
        notify(f"MIT LIVE: placed BUY {units}x {trade['snaptrade_symbol']} "
               f"@ limit ${limit_price:.2f} ({status}).")
    logger.info("Live entry %s: %s x%d @ $%.2f",
                status, trade["snaptrade_symbol"], units, limit_price)
    return {"decision": "placed", "status": status, "units": units,
            "limit_price": limit_price}


def run_live_exits(
    state: dict,
    ledger: dict,
    config: RiskConfig,
    *,
    client=None,
    quote_fn=shadow.decision_quote,
    now: datetime.datetime | None = None,
) -> list[dict]:
    """Sell open live positions past their sim exit date. Idempotent."""
    now = now or datetime.datetime.now(datetime.timezone.utc)
    today = now.date()
    if not config.live_trading_enabled:
        return []
    client = client or _default_client()
    if not client.is_configured():
        return []
    if state.get("halted"):
        # Exits still run when halted? NO for placement of anything new —
        # but leaving real positions unmanaged is worse. Exits proceed.
        logger.warning("Live layer halted — exits still processed to avoid "
                       "unmanaged open positions.")

    exit_ids = {o.get("client_order_id") for o in state.get("orders", [])
                if o.get("kind") == "exit"}
    results: list[dict] = []
    accounts = None
    for entry in [o for o in state.get("orders", [])
                  if o.get("kind") == "entry" and not o.get("exited")
                  and not _is_rejected(o)]:
        exit_id = f"{entry.get('client_order_id')}-exit"
        if exit_id in exit_ids:
            entry["exited"] = True
            continue
        try:
            pick_date = datetime.date.fromisoformat(str(entry.get("pick_date"))[:10])
        except (ValueError, TypeError):
            pick_date = datetime.date.fromisoformat(str(entry.get("logged_at"))[:10])
        due = shadow._exit_due_date(pick_date, entry.get("trade_type", "weekly"))
        if today < due:
            continue

        if accounts is None:
            accounts = client.list_accounts()
        # Find the ledger record for account/units; fall back to position scan.
        full = next((o for o in ledger.get("orders", [])
                     if o.get("client_order_id") == entry.get("client_order_id")
                     and o.get("kind") == "entry"), {})
        account_id = full.get("account_id")
        if not account_id and accounts:
            account_id = str(accounts[0].get("id"))
        positions = client.account_positions(account_id) if account_id else []
        held = 0.0
        for pos in positions:
            sym = pos.get("symbol") or {}
            inner = sym.get("symbol") if isinstance(sym, dict) else None
            ticker = (inner.get("symbol") if isinstance(inner, dict)
                      else inner or (sym if isinstance(sym, str) else None))
            if ticker == entry.get("symbol"):
                try:
                    held = float(pos.get("units") or 0)
                except (TypeError, ValueError):
                    held = 0.0
                break
        units = min(int(full.get("units") or 0), int(held))
        if units < 1:
            # Entry never filled (Day limit expired) or already flat.
            entry["exited"] = True
            entry["exit_note"] = "no position to sell (entry unfilled or flat)"
            notify(f"MIT LIVE: {entry.get('symbol')} exit due but no position "
                   f"held — entry likely never filled.")
            continue

        quote = quote_fn(entry.get("symbol"))
        if not isinstance(quote, (int, float)) or quote <= 0:
            logger.warning("Live exit: no quote for %s — retry next run",
                           entry.get("symbol"))
            continue
        limit_price = round(quote * (1 - config.max_slippage_pct / 100), 2)
        try:
            result = client.place_limit_order(
                account_id=str(account_id),
                symbol=entry.get("symbol"),
                action="SELL",
                units=units,
                limit_price=limit_price,
                client_order_id=exit_id,
            )
        except Exception as exc:  # noqa: BLE001
            notify(f"MIT LIVE: SELL {entry.get('symbol')} FAILED: {exc}")
            continue
        status = str(result.get("status", "UNKNOWN")).upper()
        exit_record = {
            "kind": "exit",
            "client_order_id": exit_id,
            "symbol": entry.get("symbol"),
            "status": status,
            "logged_at": now.isoformat(timespec="seconds"),
        }
        state["orders"].append(exit_record)
        ledger["orders"].append({
            **exit_record,
            "mode": "live",
            "account_id": str(account_id),
            "units": units,
            "limit_price": limit_price,
            "quote": round(float(quote), 4),
            "entry_client_order_id": entry.get("client_order_id"),
        })
        entry["exited"] = True
        exit_ids.add(exit_id)
        notify(f"MIT LIVE: placed SELL {units}x {entry.get('symbol')} "
               f"@ limit ${limit_price:.2f} ({status}).")
        results.append(exit_record)
    return results
