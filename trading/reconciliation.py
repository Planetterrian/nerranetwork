"""
Position reconciliation between Webull and the paper tracker.

Critical for live trading. Should be run frequently.
"""

from __future__ import annotations

from typing import List, Dict
from .webull_client import WebullClient
from .paper_tracker import PaperTracker


def reconcile_positions(client: WebullClient, paper_tracker: PaperTracker) -> Dict:
    """
    Compares Webull positions with paper_tracker open positions.
    Returns a report dict.
    """
    webull_positions = {p.get("symbol"): p for p in client.get_positions()}
    tracker_positions = {p.get("symbol"): p for p in paper_tracker.get_open_positions()}

    report = {
        "only_in_webull": [],
        "only_in_tracker": [],
        "mismatched_quantity": [],
        "in_sync": [],
    }

    all_symbols = set(webull_positions.keys()) | set(tracker_positions.keys())

    for sym in all_symbols:
        wb = webull_positions.get(sym)
        tr = tracker_positions.get(sym)

        if wb and not tr:
            report["only_in_webull"].append(sym)
        elif tr and not wb:
            report["only_in_tracker"].append(sym)
        elif wb and tr:
            wb_qty = int(wb.get("position", 0))
            tr_qty = int(tr.get("quantity", 0))
            if abs(wb_qty - tr_qty) > 0:
                report["mismatched_quantity"].append({
                    "symbol": sym,
                    "webull": wb_qty,
                    "tracker": tr_qty
                })
            else:
                report["in_sync"].append(sym)

    return report
