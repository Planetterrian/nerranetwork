"""
Performance + Lesson Attribution Reporter for the MIT Webull Paper Trading System.

This is one of the most important tools for validating whether the recursive learning loop
is actually producing an edge before moving to real money.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, Any, List
from collections import defaultdict


def load_paper_tracker(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {"summary": {}, "trades": []}
    return json.loads(path.read_text(encoding="utf-8"))


def generate_report(paper_tracker_path: Path) -> str:
    data = load_paper_tracker(paper_tracker_path)
    summary = data.get("summary", {})
    trades = data.get("trades", [])
    alpha = data.get("alpha", {}).get("vs_nasdaq", 0.0)

    total = summary.get("total_trades", 0)
    if total == 0:
        return "No closed paper trades recorded yet. Run the system for a while first."

    win_rate = summary.get("win_rate_pct", 0)
    pnl = summary.get("cumulative_pnl", 0.0)

    # Rough book return (assumes ~$1000 average risk per trade, like the podcast)
    book_return_pct = (pnl / (total * 1000)) * 100 if total > 0 else 0

    # Lesson attribution
    lesson_usage = defaultdict(int)
    for t in trades:
        for ref in t.get("mit_lesson_refs", []):
            lesson_usage[ref] += 1

    top_lessons = sorted(lesson_usage.items(), key=lambda x: x[1], reverse=True)[:6]

    lines = [
        "=== MIT Webull Paper Trading - Performance & Attribution Report ===",
        "",
        f"Total Closed Trades: {total}",
        f"Win Rate:            {win_rate:.1f}%",
        f"Book P&L:            ${pnl:,.2f}",
        f"Approx Book Return:  {book_return_pct:+.2f}% (rough)",
        f"Alpha vs NASDAQ:     {alpha:+.2f}%",
        "",
        "Most Used MIT Lessons in Paper Trades:",
    ]

    for lid, count in top_lessons:
        lines.append(f"  - {lid}: referenced in {count} trades")

    lines.append("")
    lines.append("Assessment:")

    if alpha > 4 and win_rate > 56 and total >= 30:
        lines.append("  STRONG: The system is showing meaningful edge. Consider small live sizing after more data.")
    elif alpha > 1 and win_rate > 52:
        lines.append("  PROMISING: Continue paper trading and collect more samples. Do not go live yet.")
    else:
        lines.append("  WEAK / INCONCLUSIVE: Focus on process discipline and lesson adherence. Edge not yet proven.")

    lines.append("")
    lines.append("Next Step Recommendation:")
    lines.append("  - Keep running daily in paper until you have 50+ closed trades with stable positive alpha.")
    lines.append("  - Review the last 10 trades manually against the original MIT lessons.")

    return "\n".join(lines)


if __name__ == "__main__":
    print(generate_report(Path("trading/paper_tracker.json")))
