#!/usr/bin/env python3
"""Shadow-vs-sim execution report: the slippage model's raw numbers.

For every shadow ledger entry with a ``would_place`` decision, find the
matching sim trade (same ``client_order_id`` seed → episode + symbol)
in the investment tracker and compare:

- the sim's entry price (the entry bar's OPEN — the sim's "you always
  fill at the open" optimism), vs
- the shadow decision-time quote and the marketable limit that a real
  order would have carried.

The per-trade delta IS the execution-cost estimate the July-3 review
said the sim lacks. Run ad hoc; prints a table + summary stats.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

LEDGER = ROOT / "digests" / "modern_investing" / "shadow_ledger.json"
TRACKER = ROOT / "digests" / "modern_investing" / "investment_tracker.json"


def main() -> int:
    if not LEDGER.exists():
        print("No shadow ledger yet — run scripts/mit_shadow_executor.py first.")
        return 0
    ledger = json.loads(LEDGER.read_text(encoding="utf-8"))
    tracker = json.loads(TRACKER.read_text(encoding="utf-8"))
    by_episode = {}
    for t in tracker.get("trades", []):
        if t.get("episode_num") is not None:
            by_episode[(t["episode_num"], t.get("symbol"))] = t

    rows = []
    for order in ledger.get("orders", []):
        if order.get("decision") != "would_place":
            continue
        sim = by_episode.get((order.get("episode_num"), order.get("symbol")))
        sim_entry = sim.get("entry_price") if sim else None
        quote = order.get("quote")
        slippage_pct = (
            round((quote - sim_entry) / sim_entry * 100, 3)
            if isinstance(quote, (int, float))
            and isinstance(sim_entry, (int, float)) and sim_entry
            else None
        )
        rows.append((order.get("episode_num"), order.get("symbol"),
                     sim_entry, quote, order.get("limit_price"),
                     slippage_pct, (sim or {}).get("status", "—")))

    if not rows:
        print("No would_place shadow entries yet.")
        return 0

    print(f"{'Ep':>4} {'Sym':6} {'sim entry':>10} {'shadow quote':>13} "
          f"{'limit':>8} {'slip %':>8} {'sim status':>10}")
    for ep, sym, sim_entry, quote, limit, slip, status in rows:
        print(f"{ep!s:>4} {sym or '?':6} "
              f"{sim_entry if sim_entry is not None else '—':>10} "
              f"{quote if quote is not None else '—':>13} "
              f"{limit if limit is not None else '—':>8} "
              f"{slip if slip is not None else '—':>8} {status:>10}")

    slips = [r[5] for r in rows if r[5] is not None]
    if slips:
        avg = sum(slips) / len(slips)
        worst = max(slips, key=abs)
        print(f"\n{len(slips)} matched trades · avg slippage vs sim entry: "
              f"{avg:+.3f}% · worst: {worst:+.3f}%")
        print("Positive = the real fill would have been WORSE than the sim "
              "assumes. Feed this into the sim's cost model once ~20 trades "
              "accumulate.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
