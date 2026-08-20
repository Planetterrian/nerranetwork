#!/usr/bin/env python3
"""Publish Modern Investing's complete trade ledger as an audit artifact.

The show's claim is that a listener can reproduce its numbers. Until now
that was only true in principle: the performance page showed five recent
trades, and everything needed to actually check the record — entry and
exit bar dates, the stop, the horizon, the option contract, the rules in
effect, the stated invalidation — lived in a file nobody outside the repo
reads.

This emits every trade with its full decision record, in JSON and CSV, so
"check our homework" is a link rather than an invitation.

Deliberately includes the trades that fail: voided picks with the reason,
and the eight pre-era trades whose recorded prices reconcile to no market
bar. A ledger that quietly drops its embarrassments is marketing.

    python scripts/build_mit_ledger.py --out api/mit_trade_ledger.json
"""

from __future__ import annotations

import argparse
import csv
import datetime
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

TRACKER = ROOT / "digests" / "modern_investing" / "investment_tracker.json"

# Fields a reader needs to reproduce a trade, in the order they matter.
FIELDS = [
    "episode_num", "date", "symbol", "resolved_symbol", "market", "sector",
    "structure", "trade_type", "status", "confidence", "strategy",
    "invalidation", "horizon_sessions", "policy_version",
    "entry_bar_date", "entry_price", "exit_bar_date", "exit_price",
    "pnl_pct", "pnl_dollars", "stopped_out",
    "nasdaq_return_pct", "alpha_pct",
    "void_reason", "rules_in_effect", "reviewed_in_episode",
]

OPTION_FIELDS = [
    "structure", "expiry", "strike", "premium", "contracts",
    "underlying_entry", "capital_usd", "premium_received_usd",
    "quoted_at", "quote_source",
]


def _flatten(trade: dict, era_start) -> dict:
    row = {}
    for key in FIELDS:
        val = trade.get(key)
        if isinstance(val, list):
            val = "|".join(str(v) for v in val)
        elif isinstance(val, dict):
            val = json.dumps(val, sort_keys=True)
        row[key] = val
    opt = trade.get("option") or {}
    for key in OPTION_FIELDS:
        row[f"option_{key}"] = opt.get(key)
    stop = trade.get("stop_loss") or {}
    row["stop_pct"] = stop.get("pct")
    row["stop_price"] = stop.get("price")
    row["in_current_era"] = bool(
        era_start and str(trade.get("date") or "") >= str(era_start))
    return row


def build(tracker: dict) -> dict:
    summary = tracker.get("summary", {}) or {}
    era_start = summary.get("era_inception")
    rows = [_flatten(t, era_start) for t in tracker.get("trades", [])]
    counts = {
        "total": len(rows),
        "closed": sum(1 for r in rows if r["status"] == "closed"),
        "open": sum(1 for r in rows if r["status"] == "open"),
        "voided": sum(1 for r in rows if r["status"] == "voided"),
        "in_current_era": sum(1 for r in rows if r["in_current_era"]),
        "options": sum(1 for r in rows
                       if r.get("structure") not in (None, "", "long_equity")),
    }
    return {
        "generated": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "show": "Modern Investing Techniques",
        "disclaimer": (
            "Simulated trades for education. No real money. Not financial "
            "advice."
        ),
        "methodology": "https://nerranetwork.com/modern-investing-performance.html",
        "rules_file": "shows/_trading_policy.yaml",
        "era": {
            "name": summary.get("era_name"),
            "inception": era_start,
            "why": (
                "Trades before this date were exited on whichever session "
                "the evaluating run happened to price, so their holding "
                "periods varied 0-6 sessions from the same rule. They are "
                "published as history and are excluded from the on-air "
                "record, not deleted."
            ),
        },
        "counts": counts,
        "columns": list(rows[0].keys()) if rows else [],
        "trades": rows,
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", default="api/mit_trade_ledger.json")
    ap.add_argument("--csv", default="api/mit_trade_ledger.csv")
    args = ap.parse_args()

    if not TRACKER.exists():
        print(f"::warning::MIT tracker not found at {TRACKER} — ledger skipped")
        return 0
    tracker = json.loads(TRACKER.read_text(encoding="utf-8"))
    payload = build(tracker)

    out = ROOT / args.out
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, indent=2, default=str) + "\n",
                   encoding="utf-8")

    if payload["trades"]:
        csv_path = ROOT / args.csv
        with csv_path.open("w", newline="", encoding="utf-8") as fh:
            writer = csv.DictWriter(fh, fieldnames=payload["columns"])
            writer.writeheader()
            writer.writerows(payload["trades"])

    c = payload["counts"]
    print(f"MIT ledger: {c['total']} trades "
          f"({c['closed']} closed, {c['open']} open, {c['voided']} voided; "
          f"{c['in_current_era']} in the current era, {c['options']} options) "
          f"-> {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
