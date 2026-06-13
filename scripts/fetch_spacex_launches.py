#!/usr/bin/env python3
"""Fetch SpaceX launch data for the public launch dashboard.

Pulls upcoming + previous launches for SpaceX (Launch Library 2, agency
id 121) and writes a compact, dashboard-ready JSON to ``api/spacex_launches.json``.
The dashboard page (``spacex-dashboard.html``) reads this same-origin file
first, so per-visitor traffic never hits the upstream API's rate limit.

Robust by design (mirrors the SPCX price cache, landmine #22):
- A failed/empty fetch NEVER overwrites a previous-good cache.
- All upstream access is best-effort; the dashboard degrades to a
  friendly "data unavailable" state when the file is missing.

Free, no API key. CORS-enabled upstream, so the dashboard can also fall
back to calling the API directly client-side if the cache is stale.

Usage:
    python scripts/fetch_spacex_launches.py [--out api/spacex_launches.json]
"""

from __future__ import annotations

import argparse
import datetime as _dt
import json
import logging
import urllib.request
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger("fetch_spacex_launches")

_ROOT = Path(__file__).resolve().parent.parent
_API_BASE = "https://ll.thespacedevs.com/2.3.0/launches"
_SPACEX_LSP_ID = 121
_UA = {"User-Agent": "NerraNetwork/1.0 (+https://nerranetwork.com)"}
_TIMEOUT = 25


def _get(url: str) -> Optional[Dict[str, Any]]:
    try:
        req = urllib.request.Request(url, headers=_UA)
        with urllib.request.urlopen(req, timeout=_TIMEOUT) as resp:
            return json.load(resp)
    except Exception as exc:  # network/HTTP/JSON — all non-fatal
        logger.warning("Launch API fetch failed (%s): %s", url, exc)
        return None


def _slim_launch(r: Dict[str, Any]) -> Dict[str, Any]:
    """Reduce a Launch Library record to the fields the dashboard needs."""
    pad = r.get("pad") or {}
    loc = pad.get("location") or {}
    rocket = (r.get("rocket") or {}).get("configuration") or {}
    mission = r.get("mission") or {}
    status = r.get("status") or {}
    image = r.get("image")
    image_url = image.get("image_url") if isinstance(image, dict) else image
    webcasts = [
        v.get("url") for v in (r.get("vidURLs") or [])
        if isinstance(v, dict) and v.get("url")
    ]
    return {
        "id": r.get("id"),
        "name": r.get("name"),
        "net": r.get("net"),  # ISO 8601 UTC "no earlier than" time
        "window_start": r.get("window_start"),
        "window_end": r.get("window_end"),
        "status": status.get("abbrev"),
        "status_name": status.get("name"),
        "rocket": rocket.get("name"),
        "pad": pad.get("name"),
        "location": loc.get("name"),
        "mission": mission.get("name"),
        "mission_type": mission.get("type"),
        "mission_description": mission.get("description"),
        "orbit": (mission.get("orbit") or {}).get("name") if isinstance(mission.get("orbit"), dict) else None,
        "image": image_url,
        "webcast": webcasts[0] if webcasts else None,
        "info_url": (r.get("infoURLs") or [{}])[0].get("url") if r.get("infoURLs") else None,
    }


def _is_spacex(r: Dict[str, Any]) -> bool:
    return (r.get("launch_service_provider") or {}).get("id") == _SPACEX_LSP_ID


def _monthly_cadence(previous: List[Dict[str, Any]], months: int = 12) -> List[Dict[str, Any]]:
    """Count SpaceX launches per calendar month for the last *months*."""
    today = _dt.datetime.now(_dt.timezone.utc).date().replace(day=1)
    buckets: Dict[str, int] = {}
    labels: List[str] = []
    y, m = today.year, today.month
    for _ in range(months):
        key = f"{y:04d}-{m:02d}"
        buckets[key] = 0
        labels.append(key)
        m -= 1
        if m == 0:
            m = 12
            y -= 1
    labels.reverse()
    for r in previous:
        net = r.get("net")
        if not net:
            continue
        key = net[:7]  # YYYY-MM
        if key in buckets:
            buckets[key] += 1
    return [{"month": k, "count": buckets[k]} for k in labels]


def _stats(previous: List[Dict[str, Any]], now: _dt.datetime) -> Dict[str, Any]:
    def _parse(net: Optional[str]) -> Optional[_dt.datetime]:
        if not net:
            return None
        try:
            return _dt.datetime.fromisoformat(net.replace("Z", "+00:00"))
        except ValueError:
            return None

    dates = [d for d in (_parse(r.get("net")) for r in previous) if d]
    ytd = sum(1 for d in dates if d.year == now.year)
    last_30 = sum(1 for d in dates if (now - d).days <= 30)
    last_365 = sum(1 for d in dates if (now - d).days <= 365)
    starlink_ytd = sum(
        1 for r in previous
        if (_parse(r.get("net")) or now).year == now.year
        and "starlink" in (r.get("name") or "").lower()
    )
    return {
        "launches_ytd": ytd,
        "launches_last_30d": last_30,
        "launches_last_365d": last_365,
        "starlink_launches_ytd": starlink_ytd,
        "avg_days_between_last_365d": round(365 / last_365, 2) if last_365 else None,
    }


def _fetch_previous_paginated(now: _dt.datetime, max_pages: int = 4) -> tuple[List[Dict[str, Any]], Optional[int]]:
    """Walk the previous-launches feed until ~13 months of history is
    covered (SpaceX flies ~12-15/month, so a true 12-month cadence chart
    + accurate 365-day stats need well over 100 records). Capped at
    *max_pages* (100/page) to bound API calls."""
    cutoff = now - _dt.timedelta(days=400)
    collected: List[Dict[str, Any]] = []
    total: Optional[int] = None
    url = (
        f"{_API_BASE}/previous/?lsp__id={_SPACEX_LSP_ID}"
        f"&limit=100&ordering=-net&mode=detailed"
    )
    for _ in range(max_pages):
        page = _get(url)
        if not page:
            break
        if total is None:
            total = page.get("count")
        results = [r for r in page.get("results", []) if _is_spacex(r)]
        collected.extend(results)
        # Stop once we've walked past the 13-month cutoff.
        oldest = results[-1].get("net") if results else None
        if oldest:
            try:
                if _dt.datetime.fromisoformat(oldest.replace("Z", "+00:00")) < cutoff:
                    break
            except ValueError:
                pass
        url = page.get("next")
        if not url:
            break
    return collected, total


def build_payload() -> Optional[Dict[str, Any]]:
    now = _dt.datetime.now(_dt.timezone.utc)

    up = _get(
        f"{_API_BASE}/upcoming/?lsp__id={_SPACEX_LSP_ID}"
        f"&limit=6&ordering=net&mode=detailed"
    )
    prev_results, prev_total = _fetch_previous_paginated(now)
    if not up and not prev_results:
        return None

    up_results = [r for r in (up or {}).get("results", []) if _is_spacex(r)]

    # "Next" = soonest upcoming whose net is in the future. LL2 sometimes
    # leaves a just-flown launch in the upcoming feed for a beat; skip any
    # whose net is already in the past.
    next_launch = None
    for r in up_results:
        net = r.get("net")
        try:
            net_dt = _dt.datetime.fromisoformat((net or "").replace("Z", "+00:00"))
        except ValueError:
            continue
        if net_dt > now:
            next_launch = _slim_launch(r)
            break

    previous_launch = _slim_launch(prev_results[0]) if prev_results else None
    upcoming_list = [_slim_launch(r) for r in up_results][:5]

    slim_prev = [_slim_launch(r) for r in prev_results]
    return {
        "next": next_launch,
        "previous": previous_launch,
        "upcoming": upcoming_list,
        "cadence_monthly": _monthly_cadence(slim_prev),
        "stats": _stats(slim_prev, now),
        "total_launches": prev_total,
        "source": "thespacedevs_ll2",
        "updated_at": now.isoformat(),
    }


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="api/spacex_launches.json")
    args = ap.parse_args()

    out_path = _ROOT / args.out
    payload = build_payload()

    if not payload or (not payload.get("next") and not payload.get("previous")):
        # Keep last-good cache; never overwrite with an empty result.
        if out_path.exists():
            logger.warning("Launch fetch empty — keeping existing %s", out_path)
            return 0
        logger.error("Launch fetch empty and no existing cache to keep.")
        return 0  # non-fatal: dashboard shows a friendly empty state

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    nxt = payload.get("next") or {}
    logger.info(
        "Wrote %s — next: %s (%s), ytd: %s launches",
        out_path, nxt.get("name"), nxt.get("net"),
        payload.get("stats", {}).get("launches_ytd"),
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
