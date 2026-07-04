#!/usr/bin/env python3
"""One-shot historical benchmark realignment for Modern Investing Techniques.

July 3 2026 review: every FLASH trade in the tracker carries
``nasdaq_return_pct: 0.0`` (the old annotator compared the same NASDAQ
close to itself) and weekly holds compared a Monday-open stock entry to
the PREVIOUS Friday's index close — so the recorded per-trade alpha is
not trustworthy. This script rebuilds each closed trade's benchmark
fields over the trade's ACTUAL bar window and reports — without changing
— the trades whose recorded prices can't be reconciled with market data
(the wrong-instrument class, e.g. Ep50 CNR).

The stock-side P&L (entry/exit/pnl) is deliberately NOT rewritten: those
numbers were published on air and remain the show's spoken record. Only
the benchmark comparison (nasdaq_* / alpha_pct) is recomputed, plus
``entry_bar_date``/``exit_bar_date`` stamps recovered by matching the
recorded prices to real bars.

Usage (needs market-data network access — run locally or in CI):

    python scripts/recompute_mit_benchmarks.py            # dry-run report
    python scripts/recompute_mit_benchmarks.py --apply    # write tracker

Flags every trade where:
- no bar matches the recorded entry/exit prices (±2%) → possible
  wrong-instrument pricing; consider voiding it manually;
- the matched entry bar predates the pick date → the old Monday
  backdating (hindsight gain); the report quantifies the phantom edge.
"""

from __future__ import annotations

import argparse
import datetime
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from shows.hooks import modern_investing as mi  # noqa: E402

TRACKER = ROOT / "digests" / "modern_investing" / "investment_tracker.json"
PRICE_TOLERANCE = 0.02  # ±2% match window for recorded price → bar


def _fetch_range_bars(symbol: str, start: datetime.date, end: datetime.date):
    """Date-ranged daily bars as [(date, open, close)] or None."""
    try:
        import yfinance as yf
        hist = yf.Ticker(symbol).history(
            start=start.isoformat(), end=end.isoformat(),
            interval="1d", auto_adjust=False,
        )
        return mi._bars_from_history(hist)
    except Exception as exc:  # noqa: BLE001
        print(f"    fetch failed for {symbol}: {exc}")
        return None


def _close_to(a: float, b: float) -> bool:
    return b > 0 and abs(a - b) / b <= PRICE_TOLERANCE


def _match_bar(bars, price: float, *, field: int):
    """Bar whose open (field=1) or close (field=2) matches *price*."""
    for bar in bars:
        if _close_to(price, bar[field]):
            return bar
    return None


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true",
                        help="write the realigned tracker (default: dry-run)")
    args = parser.parse_args()

    tracker = mi._load_tracker(TRACKER)
    closed = [t for t in tracker["trades"] if t.get("status") == "closed"]
    print(f"{len(closed)} closed trades to realign\n")

    unmatched, backdated, realigned = [], [], 0

    for trade in closed:
        sym = trade.get("symbol", "?")
        ep = trade.get("episode_num", "?")
        pick_date = mi._trade_pick_date(trade)
        entry_price = trade.get("entry_price")
        exit_price = trade.get("exit_price")
        if pick_date is None or entry_price is None or exit_price is None:
            unmatched.append((ep, sym, "missing pick date or prices"))
            continue

        window_start = pick_date - datetime.timedelta(days=10)
        window_end = pick_date + datetime.timedelta(days=16)

        bars = None
        for cand in mi._trade_symbol_candidates(trade):
            bars = _fetch_range_bars(cand, window_start, window_end)
            if bars:
                trade["resolved_symbol"] = cand
                break
        if not bars:
            unmatched.append((ep, sym, "no market data"))
            continue

        entry_bar = _match_bar(bars, entry_price, field=1)
        exit_bar = _match_bar(bars, exit_price, field=2)
        if entry_bar is None or exit_bar is None:
            unmatched.append((
                ep, sym,
                f"recorded prices ${entry_price}/${exit_price} match no bar "
                f"(±{PRICE_TOLERANCE:.0%}) — possible WRONG-INSTRUMENT "
                f"pricing; consider voiding",
            ))
            continue

        trade["entry_bar_date"] = entry_bar[0].isoformat()
        trade["exit_bar_date"] = exit_bar[0].isoformat()
        if entry_bar[0] < pick_date:
            backdated.append((
                ep, sym,
                f"entry bar {entry_bar[0]} predates pick {pick_date} — "
                f"hindsight-backdated entry (old Monday-anchor bug)",
            ))

        ndq_bars = _fetch_range_bars(
            mi.NASDAQ_SYMBOL, window_start, window_end)
        window = mi._matched_nasdaq_window(
            ndq_bars, entry_bar[0], exit_bar[0]) if ndq_bars else None
        old_alpha = trade.get("alpha_pct")
        if window:
            entry_open, exit_close, d1, d2 = window
            trade["nasdaq_entry"] = round(entry_open, 2)
            trade["nasdaq_exit"] = round(exit_close, 2)
            trade["nasdaq_entry_date"] = d1.isoformat()
            trade["nasdaq_exit_date"] = d2.isoformat()
            ndq_ret = ((exit_close - entry_open) / entry_open) * 100
            trade["nasdaq_return_pct"] = round(ndq_ret, 2)
            pnl = trade.get("pnl_pct")
            trade["alpha_pct"] = (
                round(pnl - ndq_ret, 2) if isinstance(pnl, (int, float)) else None
            )
            # Multi-index sweep over the identical window (July 2026).
            returns = {"nasdaq": trade["nasdaq_return_pct"]}
            for key, idx_symbol in mi.BENCHMARK_INDICES.items():
                if key == "nasdaq":
                    continue
                idx_bars = _fetch_range_bars(
                    idx_symbol, window_start, window_end)
                idx_window = mi._matched_nasdaq_window(
                    idx_bars, entry_bar[0], exit_bar[0]) if idx_bars else None
                if idx_window:
                    io, ic, _, _ = idx_window
                    returns[key] = round(((ic - io) / io) * 100, 2)
                else:
                    returns[key] = None
            trade["benchmark_returns"] = returns
            realigned += 1
            print(f"  Ep{ep:>3} {sym:6} window {d1}→{d2}  "
                  f"ndq {trade['nasdaq_return_pct']:+.2f}%  "
                  f"alpha {old_alpha} → {trade['alpha_pct']}")
        else:
            unmatched.append((ep, sym, "no NASDAQ window"))

    mi._recompute_summary(tracker)
    s = tracker["summary"]
    print(f"\nRealigned {realigned}/{len(closed)} trades")
    print(f"Matched-window score: portfolio "
          f"{s.get('compounded_return_pct'):+.2f}% vs NASDAQ "
          f"{s.get('compounded_nasdaq_matched_pct'):+.2f}% → alpha "
          f"{s.get('matched_window_alpha_pct'):+.2f}% across "
          f"{s.get('matched_window_trades')} trades")
    print(f"Per-trade alpha sum: {s.get('cumulative_alpha_vs_nasdaq'):+.2f}%")
    for key, score in (s.get("benchmark_scores") or {}).items():
        print(f"  vs {mi.BENCHMARK_LABELS.get(key, key)}: "
              f"alpha {score['alpha_pct']:+.2f}% over {score['trades']} trades")
    print(f"Beating {s.get('indices_beaten', 0)} of "
          f"{s.get('indices_scored', 0)} major indices (matched windows)")

    if backdated:
        print("\nBACKDATED ENTRIES (hindsight gain in the published record):")
        for ep, sym, why in backdated:
            print(f"  Ep{ep:>3} {sym:6} {why}")
    if unmatched:
        print("\nUNRECONCILED TRADES (operator review — possibly wrong "
              "instrument):")
        for ep, sym, why in unmatched:
            print(f"  Ep{ep:>3} {sym:6} {why}")

    if args.apply:
        mi._save_tracker(tracker, TRACKER)
        print(f"\nWrote {TRACKER}")
    else:
        print("\nDRY RUN — re-run with --apply to write the tracker.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
