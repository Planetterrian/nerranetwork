"""
Production-minded wrapper around the unofficial webull library.

Focus: Paper trading first, clean error handling, position management.
"""

from __future__ import annotations

import logging
import time
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

try:
    from webull import webull
except ImportError:
    webull = None


class WebullClient:
    def __init__(self, paper: bool = True):
        if webull is None:
            raise ImportError("Install with: pip install webull")

        self.paper = paper
        self.wb = webull()
        self._logged_in = False

    def login(self, email: str, password: str, device_name: str = "mit_trader") -> bool:
        """Login. Handles basic MFA flow if needed."""
        try:
            resp = self.wb.login(email, password, device_name=device_name)
            if resp and resp.get("success"):
                self._logged_in = True
                logger.info(f"Successfully logged into Webull ({'PAPER' if self.paper else 'LIVE'})")
                return True

            # Some flows return a challenge
            if resp and "verification" in str(resp).lower():
                logger.info("MFA challenge received. Check your email/app for code.")
                # In a real tool you would prompt here or accept code as parameter
            return False
        except Exception as e:
            logger.exception("Login failed: %s", e)
            return False

    def login_paper(self, email: str, password: str) -> bool:
        """Explicit paper login if the library supports it differently."""
        try:
            # The library sometimes uses a different endpoint for paper
            resp = self.wb.get_paper_account()  # Will fail if not logged in
            if resp:
                self._logged_in = True
                return True
            return self.login(email, password)
        except Exception:
            return self.login(email, password)

    def is_logged_in(self) -> bool:
        return self._logged_in

    def get_account(self) -> Optional[Dict[str, Any]]:
        if not self._logged_in:
            return None
        try:
            return self.wb.get_paper_account() if self.paper else self.wb.get_account()
        except Exception as e:
            logger.warning("get_account failed: %s", e)
            return None

    def get_positions(self) -> List[Dict]:
        if not self._logged_in:
            return []
        try:
            return self.wb.get_paper_positions() if self.paper else self.wb.get_positions() or []
        except Exception as e:
            logger.warning("get_positions failed: %s", e)
            return []

    def get_quote(self, symbol: str) -> Optional[Dict]:
        if not self._logged_in:
            return None
        try:
            return self.wb.get_quote(symbol)
        except Exception as e:
            logger.debug("Quote failed for %s: %s", symbol, e)
            return None

    def get_bars(self, symbol: str, interval: str = "d", count: int = 100):
        if not self._logged_in:
            return []
        try:
            return self.wb.get_bars(symbol, interval=interval, count=count) or []
        except Exception as e:
            logger.debug("get_bars failed for %s: %s", symbol, e)
            return []

    def get_recent_volatility(self, symbol: str, lookback: int = 20) -> Optional[float]:
        """Returns approximate 20-day realized volatility as decimal (e.g. 0.28 = 28%)."""
        bars = self.get_bars(symbol, interval="d", count=lookback + 5)
        if len(bars) < lookback:
            return None
        try:
            closes = [float(b["close"]) for b in bars[-lookback:]]
            returns = [(closes[i] - closes[i-1]) / closes[i-1] for i in range(1, len(closes))]
            import math
            std = math.sqrt(sum(r*r for r in returns) / len(returns))
            return round(std * math.sqrt(252), 4)  # annualized
        except Exception:
            return None

    def place_paper_order(
        self,
        symbol: str,
        action: str,          # BUY / SELL
        order_type: str = "MKT",
        quantity: int = 0,
        price: Optional[float] = None,
    ) -> Optional[Dict]:
        """Safe paper order placement."""
        if not self.paper:
            logger.error("Attempted paper order while in live mode!")
            return None

        if not self._logged_in:
            raise RuntimeError("Not logged in")

        try:
            return self.wb.place_order_paper(
                stock=symbol,
                action=action.upper(),
                orderType=order_type,
                quant=quantity,
                price=price,
            )
        except Exception as e:
            logger.exception("Paper order failed: %s", e)
            return None

    def close_all_paper_positions(self) -> List[str]:
        """Emergency function - use with caution."""
        if not self.paper:
            logger.error("close_all_paper_positions called in live mode!")
            return []

        closed = []
        for pos in self.get_positions():
            symbol = pos.get("symbol")
            qty = abs(int(pos.get("position", 0)))
            if qty > 0:
                side = "SELL" if int(pos.get("position", 0)) > 0 else "BUY"
                resp = self.place_paper_order(symbol, side, "MKT", qty)
                if resp:
                    closed.append(symbol)
        return closed
