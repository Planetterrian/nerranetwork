#!/usr/bin/env python3
"""Fetch Tesla dashboard data for the public Tesla data page.

Pulls live TSLA market data + a 1-year price history from yfinance (the
same library the Tesla pipeline + Modern Investing already rely on) and
writes a compact, dashboard-ready JSON to ``api/tesla_dashboard.json``.
The page (``tesla-dashboard.html``) reads this same-origin file first.

Robust by design (mirrors the SPCX/launch caches, landmine #22):
- price passes a sanity band + a deviation guard vs the last cached close;
- a failed/empty fetch NEVER overwrites a previous-good cache.

The curated quarterly/annual operating metrics (deliveries, energy
storage) live in a separate committed, operator-extendable dataset
(``site/data/tesla_metrics.json``) that this script leaves untouched.

Usage:
    python scripts/fetch_tesla_dashboard.py [--out api/tesla_dashboard.json]
"""

from __future__ import annotations

import argparse
import datetime as _dt
import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger("fetch_tesla_dashboard")

_ROOT = Path(__file__).resolve().parent.parent
# Sanity band for TSLA (split-adjusted); deviation guard vs last cache.
_PRICE_MIN, _PRICE_MAX = 50.0, 2000.0
_MAX_DEVIATION = 0.30


def _load_cache(path: Path) -> Dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _market() -> Optional[Dict[str, Any]]:
    """Live market snapshot + 1y weekly closes via yfinance."""
    try:
        import yfinance as yf
    except Exception as exc:
        logger.warning("yfinance unavailable: %s", exc)
        return None
    try:
        t = yf.Ticker("TSLA")
        fi = t.fast_info
        price = float(getattr(fi, "last_price", 0.0) or 0.0)
        prev = float(getattr(fi, "previous_close", 0.0) or 0.0)
        if not price:
            # fall back to the last daily close from history
            h = t.history(period="5d")
            closes = [float(c) for c in h["Close"].tolist() if c == c]
            price = closes[-1] if closes else 0.0
            prev = closes[-2] if len(closes) >= 2 else prev
        if not (_PRICE_MIN <= price <= _PRICE_MAX):
            logger.warning("TSLA price %s outside sanity band", price)
            return None
        # 1-year weekly price history for the chart
        hist = t.history(period="1y", interval="1wk")
        series: List[Dict[str, Any]] = []
        for idx, row in zip(hist.index, hist["Close"].tolist()):
            if row != row:  # NaN
                continue
            series.append({"date": idx.strftime("%Y-%m-%d"), "close": round(float(row), 2)})
        return {
            "price": round(price, 2),
            "prev_close": round(prev, 2) if prev else None,
            "market_cap": float(getattr(fi, "market_cap", 0.0) or 0.0) or None,
            "year_high": _f(getattr(fi, "year_high", None)),
            "year_low": _f(getattr(fi, "year_low", None)),
            "day_volume": _i(getattr(fi, "last_volume", None)),
            "avg_volume_10d": _i(getattr(fi, "ten_day_average_volume", None)),
            "price_history": series,
        }
    except Exception as exc:
        logger.warning("yfinance fetch failed: %s", exc)
        return None


def _f(v) -> Optional[float]:
    try:
        return round(float(v), 2) if v else None
    except (TypeError, ValueError):
        return None


def _i(v) -> Optional[int]:
    try:
        return int(v) if v else None
    except (TypeError, ValueError):
        return None


def build_payload(out_path: Path) -> Optional[Dict[str, Any]]:
    now = _dt.datetime.now(_dt.timezone.utc)
    m = _market()
    if not m:
        return None
    # deviation guard vs last cached price
    cached = _load_cache(out_path)
    last = cached.get("price")
    if last and abs(m["price"] - last) / last > _MAX_DEVIATION:
        logger.warning("TSLA %.2f deviates >%.0f%% from cached %.2f — rejected",
                       m["price"], _MAX_DEVIATION * 100, last)
        return None
    change_pct = None
    if m.get("prev_close"):
        change_pct = round((m["price"] - m["prev_close"]) / m["prev_close"] * 100, 2)
    m.update({
        "symbol": "TSLA",
        "change_pct": change_pct,
        "source": "yfinance",
        "updated_at": now.isoformat(),
    })
    return m


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="api/tesla_dashboard.json")
    args = ap.parse_args()
    out_path = _ROOT / args.out
    payload = build_payload(out_path)
    if not payload:
        if out_path.exists():
            logger.warning("Tesla fetch empty — keeping existing %s", out_path)
            return 0
        logger.error("Tesla fetch empty and no existing cache.")
        return 0
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    logger.info("Wrote %s — TSLA $%.2f (%s%%), %d weekly closes",
                out_path, payload["price"],
                payload.get("change_pct"), len(payload.get("price_history", [])))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
