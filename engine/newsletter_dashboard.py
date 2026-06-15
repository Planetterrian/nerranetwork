"""Per-show dashboard stats for the newsletter "By the numbers" block.

Reads the same live data files the public dashboards use (``api/*.json``,
``site/data/*.json``) and returns up to three ``{"value", "label"}`` tiles for
``wrap_with_branding(by_the_numbers=...)``. Strictly best-effort: any missing
file, unreadable JSON, or non-finite number is skipped, so the newsletter send
is never blocked by a stale/absent dashboard cache. Shows without a mapping
return ``[]`` (no block rendered).

Added June 2026 (operator request: surface dashboard data in the SpaceX, Tesla,
and Modern Investing newsletters).
"""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any, Dict, List, Optional

_REPO_ROOT = Path(__file__).resolve().parent.parent


def _load(root: Path, rel: str) -> Optional[Any]:
    try:
        return json.loads((root / rel).read_text(encoding="utf-8"))
    except Exception:
        return None


def _finite(v: Any) -> Optional[float]:
    """Return a finite float or None (guards the yfinance-NaN class so a bad
    cache value never reaches the email as 'nan')."""
    try:
        f = float(v)
        return f if math.isfinite(f) else None
    except (TypeError, ValueError):
        return None


def _tile(value: str, label: str) -> Dict[str, str]:
    return {"value": value, "label": label}


def _spacex_stats(root: Path) -> List[Dict[str, str]]:
    out: List[Dict[str, str]] = []
    spcx = _load(root, "api/spcx.json") or {}
    price = _finite(spcx.get("price"))
    if price and price > 0:
        out.append(_tile(f"${price:,.2f}", "SPCX price"))
    launches = _load(root, "api/spacex_launches.json") or {}
    ytd = launches.get("stats", {}).get("launches_ytd") if isinstance(launches.get("stats"), dict) else None
    if isinstance(ytd, int) and ytd > 0:
        out.append(_tile(str(ytd), "Launches this year"))
    fleet = launches.get("fleet") if isinstance(launches.get("fleet"), dict) else {}
    starlink = fleet.get("starlink_active")
    if isinstance(starlink, int) and starlink > 0:
        out.append(_tile(f"{starlink:,}", "Active Starlink sats"))
    return out[:3]


def _tesla_stats(root: Path) -> List[Dict[str, str]]:
    out: List[Dict[str, str]] = []
    dash = _load(root, "api/tesla_dashboard.json") or {}
    price = _finite(dash.get("price"))
    if price and price > 0:
        out.append(_tile(f"${price:,.2f}", "TSLA price"))
    chg = _finite(dash.get("change_pct"))
    if chg is not None:
        out.append(_tile(f"{chg:+.2f}%", "TSLA today"))
    metrics = _load(root, "site/data/tesla_metrics.json") or {}
    annual = metrics.get("deliveries_annual") if isinstance(metrics.get("deliveries_annual"), list) else []
    if annual:
        last = annual[-1]
        vehicles = _finite(last.get("vehicles"))
        if vehicles and vehicles > 0:
            out.append(_tile(f"{vehicles / 1e6:.2f}M", f"{last.get('year')} deliveries"))
    return out[:3]


def _modern_investing_stats(root: Path) -> List[Dict[str, str]]:
    out: List[Dict[str, str]] = []
    dash = _load(root, "api/dashboard.json") or {}
    perf = dash.get("mit_performance") if isinstance(dash.get("mit_performance"), dict) else {}
    summary = perf.get("summary") if isinstance(perf.get("summary"), dict) else {}
    alpha = _finite(summary.get("cumulative_alpha_vs_nasdaq"))
    if alpha is not None:
        out.append(_tile(f"{alpha:+.1f}%", "Alpha vs NASDAQ"))
    win_rate = _finite(summary.get("win_rate_pct"))
    if win_rate is not None:
        out.append(_tile(f"{win_rate:.0f}%", "Win rate"))
    trades = summary.get("total_trades")
    if isinstance(trades, int) and trades > 0:
        out.append(_tile(str(trades), "Simulated trades"))
    return out[:3]


_BUILDERS = {
    "spacex": _spacex_stats,
    "tesla": _tesla_stats,
    "modern_investing": _modern_investing_stats,
}


def build_dashboard_stats(slug: str, root: Optional[Path] = None) -> List[Dict[str, str]]:
    """Up to 3 dashboard stat tiles for *slug*'s newsletter, or [] if the show
    has no mapping or its data is unavailable. Never raises."""
    builder = _BUILDERS.get(slug)
    if builder is None:
        return []
    try:
        return builder(Path(root) if root else _REPO_ROOT)
    except Exception:
        return []
