"""Read-only live-account mirror (Phase 1 of the SnapTrade plan).

Builds a privacy-conscious snapshot of the operator's connected accounts:
institution, masked account number, cash + total value, and positions.
The output goes to a **gitignored** local file / CI artifact — the repo
is public, so balances must never be committed (see execution/__init__).

``build_mirror`` is a pure function over already-fetched data so it can
be unit-tested without the SDK; ``fetch_mirror`` does the network calls.
"""

from __future__ import annotations

import datetime
import logging

from execution import snaptrade_client as st

logger = logging.getLogger(__name__)

MIRROR_SCHEMA_VERSION = 1


def _mask_number(number) -> str:
    s = str(number or "")
    return f"***{s[-3:]}" if len(s) >= 3 else "***"


def _num(value, default=None):
    try:
        f = float(value)
    except (TypeError, ValueError):
        return default
    return f


def build_mirror(accounts: list[dict],
                 positions_by_account: dict[str, list[dict]],
                 balances_by_account: dict[str, list[dict]],
                 *, now_iso: str | None = None) -> dict:
    """Normalize SnapTrade account/position/balance payloads to one dict."""
    out_accounts = []
    for acct in accounts or []:
        acct_id = str(acct.get("id", ""))
        balances = balances_by_account.get(acct_id) or []
        cash_lines = [
            {
                "currency": ((b.get("currency") or {}).get("code")
                             if isinstance(b.get("currency"), dict)
                             else b.get("currency")),
                "cash": _num(b.get("cash")),
            }
            for b in balances
        ]
        positions = []
        for pos in positions_by_account.get(acct_id) or []:
            sym = pos.get("symbol") or {}
            # SnapTrade nests symbol → symbol → raw/description.
            inner = sym.get("symbol") if isinstance(sym, dict) else None
            if isinstance(inner, dict):
                ticker = inner.get("symbol") or inner.get("raw_symbol")
                description = inner.get("description")
            else:
                ticker = inner or (sym if isinstance(sym, str) else None)
                description = None
            units = _num(pos.get("units") or pos.get("fractional_units"))
            price = _num(pos.get("price"))
            positions.append({
                "symbol": ticker,
                "description": description,
                "units": units,
                "price": price,
                "value": round(units * price, 2)
                if units is not None and price is not None else None,
            })
        total = acct.get("balance") or {}
        total_value = total.get("total") if isinstance(total, dict) else None
        if isinstance(total_value, dict):
            total_amount = _num(total_value.get("amount"))
            total_currency = total_value.get("currency")
        else:
            total_amount = _num(total_value)
            total_currency = None
        out_accounts.append({
            "id": acct_id,
            "name": acct.get("name"),
            "institution": acct.get("institution_name"),
            "number_masked": _mask_number(acct.get("number")),
            "total_value": total_amount,
            "total_currency": total_currency,
            "cash": cash_lines,
            "positions": positions,
            "sync_status": (acct.get("sync_status") or {}),
        })
    return {
        "schema_version": MIRROR_SCHEMA_VERSION,
        "generated_at": now_iso
        or datetime.datetime.now(datetime.timezone.utc).isoformat(
            timespec="seconds"),
        "account_count": len(out_accounts),
        "accounts": out_accounts,
    }


def fetch_mirror() -> dict:
    """Fetch everything and build the mirror. Raises on network failure —
    the caller (script/workflow) decides how loud to be."""
    accounts = st.list_accounts()
    positions_by_account: dict[str, list[dict]] = {}
    balances_by_account: dict[str, list[dict]] = {}
    for acct in accounts:
        acct_id = str(acct.get("id", ""))
        try:
            positions_by_account[acct_id] = st.account_positions(acct_id)
        except Exception as exc:  # noqa: BLE001
            logger.warning("positions fetch failed for %s: %s", acct_id, exc)
            positions_by_account[acct_id] = []
        try:
            balances_by_account[acct_id] = st.account_balances(acct_id)
        except Exception as exc:  # noqa: BLE001
            logger.warning("balances fetch failed for %s: %s", acct_id, exc)
            balances_by_account[acct_id] = []
    return build_mirror(accounts, positions_by_account, balances_by_account)


def mirror_summary_line(mirror: dict) -> str:
    """One-line human summary (safe for notifications/logs)."""
    n_accounts = mirror.get("account_count", 0)
    n_positions = sum(
        len(a.get("positions") or []) for a in mirror.get("accounts") or [])
    institutions = sorted({
        a.get("institution") or "?" for a in mirror.get("accounts") or []})
    return (
        f"SnapTrade mirror OK: {n_accounts} account(s) "
        f"[{', '.join(institutions) or 'none'}], {n_positions} position(s)."
    )
