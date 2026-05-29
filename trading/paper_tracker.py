"""
Paper Trading Tracker - Separate from the podcast's simulated investment_tracker.json

This allows the MIT podcast simulation to remain pure while we run real (paper) trading experiments.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, date
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class PaperTracker:
    def __init__(self, path: Path):
        self.path = path
        self.data: Dict[str, Any] = self._load()

    def _load(self) -> Dict[str, Any]:
        if self.path.exists():
            try:
                return json.loads(self.path.read_text(encoding="utf-8"))
            except Exception as e:
                logger.warning("Failed to load paper tracker, starting fresh: %s", e)
        return self._fresh()

    def _fresh(self) -> Dict[str, Any]:
        return {
            "metadata": {
                "created": datetime.now().isoformat(),
                "version": "1.0",
            },
            "summary": {
                "total_trades": 0,
                "wins": 0,
                "losses": 0,
                "breakeven": 0,
                "win_rate_pct": 0.0,
                "cumulative_pnl": 0.0,
            },
            "trades": [],
            "alpha": {"vs_nasdaq": 0.0},
        }

    def save(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(self.data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    def record_trade(
        self,
        symbol: str,
        action: str,
        quantity: int,
        entry_price: float,
        strategy: str,
        confidence: str,
        mit_lesson_refs: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """Record an executed paper trade."""
        trade = {
            "id": f"PAPER-{datetime.now().strftime('%Y%m%d-%H%M%S')}",
            "date": date.today().isoformat(),
            "symbol": symbol,
            "action": action,
            "quantity": quantity,
            "entry_price": entry_price,
            "strategy": strategy,
            "confidence": confidence,
            "status": "open",
            "mit_lesson_refs": mit_lesson_refs or [],
        }
        self.data["trades"].append(trade)
        self.save()
        return trade

    def close_trade(self, trade_id: str, exit_price: float) -> Optional[Dict]:
        """Close a paper trade and update P&L."""
        for trade in self.data["trades"]:
            if trade["id"] == trade_id and trade["status"] == "open":
                entry = trade["entry_price"]
                qty = trade["quantity"]
                pnl_pct = ((exit_price - entry) / entry) * 100 if entry else 0
                pnl_dollars = (exit_price - entry) * qty

                trade.update({
                    "status": "closed",
                    "exit_price": exit_price,
                    "pnl_pct": round(pnl_pct, 2),
                    "pnl_dollars": round(pnl_dollars, 2),
                })

                # Update summary
                summary = self.data["summary"]
                summary["total_trades"] += 1
                if pnl_dollars > 0:
                    summary["wins"] += 1
                elif pnl_dollars < 0:
                    summary["losses"] += 1
                else:
                    summary["breakeven"] += 1

                summary["cumulative_pnl"] = round(summary["cumulative_pnl"] + pnl_dollars, 2)
                total = summary["wins"] + summary["losses"] + summary["breakeven"]
                summary["win_rate_pct"] = round((summary["wins"] / total) * 100, 1) if total > 0 else 0

                self.save()
                return trade
        return None

    def get_open_positions(self) -> List[Dict]:
        return [t for t in self.data["trades"] if t.get("status") == "open"]

    def get_summary(self) -> Dict:
        return self.data.get("summary", {})

    def get_closed_trades(self) -> List[Dict]:
        return [t for t in self.data.get("trades", []) if t.get("status") == "closed"]

    def calculate_alpha_vs_nasdaq(self, nasdaq_return_pct: float) -> float:
        """Very rough alpha calculation for the paper book."""
        summary = self.get_summary()
        book_return = summary.get("cumulative_pnl", 0.0)  # This is in dollars on $1k-style sizing
        # Normalize to percentage assuming average $1000 risk per trade for rough comparison
        total_trades = summary.get("total_trades", 1)
        avg_book_return = (book_return / total_trades) if total_trades > 0 else 0
        return round(avg_book_return - nasdaq_return_pct, 2)

    def update_alpha(self, nasdaq_return_pct: float):
        alpha = self.calculate_alpha_vs_nasdaq(nasdaq_return_pct)
        self.data.setdefault("alpha", {})["vs_nasdaq"] = alpha
        self.save()
        return alpha

    def get_sector_exposure(self, symbol_sector_map: Dict[str, str]) -> Dict[str, float]:
        """
        Returns current % of book exposed to each sector based on open positions.
        symbol_sector_map: e.g. {"AAPL": "tech", "XOM": "energy"}
        """
        exposure: Dict[str, float] = {}
        total_value = 0.0

        for pos in self.get_open_positions():
            sym = pos.get("symbol")
            qty = pos.get("quantity", 0)
            entry = pos.get("entry_price", 0)
            value = qty * entry
            total_value += value

            sector = symbol_sector_map.get(sym, "other").lower()
            exposure[sector] = exposure.get(sector, 0.0) + value

        if total_value > 0:
            for s in exposure:
                exposure[s] /= total_value

        return exposure

    def get_expectancy_stats(self) -> Dict[str, float]:
        """
        Returns key statistics needed for Kelly / edge-based sizing.
        """
        closed = self.get_closed_trades()
        if not closed:
            return {
                "win_rate": 0.5,
                "avg_win_pct": 0.0,
                "avg_loss_pct": 0.0,
                "expectancy": 0.0,
                "kelly_fraction": 0.0,
            }

        wins = [t["pnl_pct"] for t in closed if t.get("pnl_pct", 0) > 0]
        losses = [t["pnl_pct"] for t in closed if t.get("pnl_pct", 0) < 0]

        win_rate = len(wins) / len(closed)
        avg_win = sum(wins) / len(wins) if wins else 0.0
        avg_loss = abs(sum(losses) / len(losses)) if losses else 0.0

        # Expectancy per trade (as decimal)
        expectancy = (win_rate * avg_win) - ((1 - win_rate) * avg_loss)

        # Fractional Kelly (half-Kelly for safety)
        if avg_loss > 0:
            kelly = (win_rate / avg_loss) - ((1 - win_rate) / avg_win) if avg_win > 0 else 0.0
            kelly_fraction = max(0.0, kelly * 0.5)  # Half-Kelly
        else:
            kelly_fraction = 0.0

        return {
            "win_rate": round(win_rate, 4),
            "avg_win_pct": round(avg_win, 2),
            "avg_loss_pct": round(avg_loss, 2),
            "expectancy": round(expectancy, 4),
            "kelly_fraction": round(min(kelly_fraction, 0.25), 4),  # Cap at 25% for safety
        }
