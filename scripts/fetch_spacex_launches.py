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


_CELESTRAK_STARLINK = (
    "https://celestrak.org/NORAD/elements/gp.php?GROUP=starlink&FORMAT=json"
)


def _starlink_active_count() -> Optional[int]:
    """Real count of active Starlink satellites on orbit, from CelesTrak's
    free catalogue (one download / 2h update). Best-effort: returns None on
    any failure so the dashboard falls back to the estimate."""
    try:
        req = urllib.request.Request(_CELESTRAK_STARLINK, headers=_UA)
        with urllib.request.urlopen(req, timeout=_TIMEOUT) as resp:
            data = json.load(resp)
        n = len(data) if isinstance(data, list) else 0
        # Sanity band — the constellation is ~6k-30k this era; reject junk.
        return n if 1000 <= n <= 60000 else None
    except Exception as exc:
        logger.info("CelesTrak Starlink count failed (non-fatal): %s", exc)
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
    # First-stage booster (serial + which flight this is for it) — detailed
    # mode only; powers the reuse "record watch" and per-launch booster line.
    booster = None
    stages = (r.get("rocket") or {}).get("launcher_stage") or []
    if stages:
        launcher = stages[0].get("launcher") or {}
        fn = stages[0].get("launcher_flight_number") or launcher.get("flights")
        if launcher.get("serial_number"):
            booster = {"serial": launcher.get("serial_number"), "flight_number": fn}
    return {
        "id": r.get("id"),
        "booster": booster,
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


def _booster_stats(prev_raw: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Fleet reuse stats from detailed launch records: the most-flown
    boosters (the reuse 'record watch'), recent landing-success rate, and
    the active-fleet size seen in the window."""
    flights: Dict[str, int] = {}
    landings_ok = landings_total = 0
    for r in prev_raw:
        for s in ((r.get("rocket") or {}).get("launcher_stage") or []):
            launcher = s.get("launcher") or {}
            serial = launcher.get("serial_number")
            fn = s.get("launcher_flight_number") or launcher.get("flights")
            if serial and fn:
                try:
                    flights[serial] = max(flights.get(serial, 0), int(fn))
                except (TypeError, ValueError):
                    pass
            landing = (s.get("landing") or {})
            if landing.get("success") is not None:
                landings_total += 1
                if landing.get("success"):
                    landings_ok += 1
    leaders = sorted(flights.items(), key=lambda x: -x[1])[:5]
    return {
        "fleet_leaders": [{"serial": s, "flights": f} for s, f in leaders],
        "most_flown": ({"serial": leaders[0][0], "flights": leaders[0][1]}
                       if leaders else None),
        "landing_success_pct": round(100 * landings_ok / landings_total, 1) if landings_total else None,
        "landings_window": landings_total,
        "active_boosters_window": len(flights),
    }


def _month_labels(months: int) -> List[str]:
    today = _dt.datetime.now(_dt.timezone.utc).date().replace(day=1)
    labels: List[str] = []
    y, m = today.year, today.month
    for _ in range(months):
        labels.append(f"{y:04d}-{m:02d}")
        m -= 1
        if m == 0:
            m = 12
            y -= 1
    labels.reverse()
    return labels


def _monthly_breakdown(previous: List[Dict[str, Any]], months: int = 12) -> List[Dict[str, Any]]:
    """Per-calendar-month metrics for the last *months*: launch count,
    estimated mass to orbit (t), estimated satellites deployed, and the
    vehicle mix. The single source the cadence chart, the mass-to-orbit
    chart, and the growing metrics time-series are all derived from."""
    labels = _month_labels(months)
    buckets: Dict[str, Dict[str, Any]] = {
        k: {"month": k, "launches": 0, "mass_t": 0.0, "satellites": 0, "vehicles": {}}
        for k in labels
    }
    for r in previous:
        net = r.get("net")
        if not net:
            continue
        b = buckets.get(net[:7])  # YYYY-MM
        if not b:
            continue
        rocket = (r.get("rocket") or "Other").strip()
        is_sl = "starlink" in (r.get("name") or "").lower()
        b["launches"] += 1
        b["mass_t"] += _launch_mass_t(rocket, is_sl)
        if is_sl:
            b["satellites"] += _SATS_PER_STARLINK_LAUNCH
        b["vehicles"][rocket] = b["vehicles"].get(rocket, 0) + 1
    out = []
    for k in labels:
        b = buckets[k]
        b["mass_t"] = round(b["mass_t"])
        out.append(b)
    return out


def _monthly_cadence(previous: List[Dict[str, Any]], months: int = 12) -> List[Dict[str, Any]]:
    """Launches per calendar month (cadence chart)."""
    return [{"month": b["month"], "count": b["launches"]}
            for b in _monthly_breakdown(previous, months)]


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


# Representative payload-to-orbit per vehicle/mission, in tonnes. Used ONLY
# for the clearly-labelled "estimated mass to orbit" headline — SpaceX
# doesn't publish per-flight mass, so these are conservative public
# averages, not measured values.
_MASS_T = {
    "falcon9_starlink": 17.0,   # v2-mini Starlink batch to LEO
    "falcon9_other": 9.0,       # mixed F9 manifest (rideshare/GTO/crew/cargo)
    "falcon_heavy": 26.0,       # representative FH payload
    "starship": 0.0,            # test flights — no payload to orbit yet
}
# Representative Starlink satellites per Falcon 9 launch (v2-mini batches
# run ~21-28; 23 is a conservative public average). Estimate only.
_SATS_PER_STARLINK_LAUNCH = 23


def _launch_mass_t(rocket: str, is_starlink: bool) -> float:
    rl = (rocket or "").lower()
    if "heavy" in rl:
        return _MASS_T["falcon_heavy"]
    if "starship" in rl:
        return _MASS_T["starship"]
    if "falcon" in rl:
        return _MASS_T["falcon9_starlink"] if is_starlink else _MASS_T["falcon9_other"]
    return _MASS_T["falcon9_other"]


# The growing, committed metrics dataset. Each run merges the freshest
# 12-month window into this persistent time-series, so months lock in and
# the history accumulates over time (the foundation for multi-year growth
# charts). Schema is intentionally extensible — the `infrastructure` block
# is reserved for operator-curated compute/GPU/datacenter milestones
# (xAI Colossus etc.) that aren't available from a launch API.
_METRICS_PATH = _ROOT / "site" / "data" / "spacex_metrics.json"


def _update_metrics_timeseries(monthly: List[Dict[str, Any]], now: _dt.datetime,
                               path: Path = _METRICS_PATH) -> int:
    try:
        existing = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    except Exception:
        existing = {}
    if not isinstance(existing, dict):
        existing = {}
    months: Dict[str, Any] = existing.get("months") or {}
    for b in monthly:
        # Refresh the last-12 window each run; older months stay locked.
        months[b["month"]] = {
            "launches": b["launches"],
            "mass_t": b["mass_t"],
            "satellites": b["satellites"],
            "vehicles": b["vehicles"],
        }
    # Cumulative satellites-deployed (estimated) across the recorded series.
    ordered = sorted(months.items())
    cum = 0
    cumulative = {}
    for k, v in ordered:
        cum += v.get("satellites", 0)
        cumulative[k] = cum
    payload = {
        "version": 1,
        "updated_at": now.isoformat(),
        "note": ("Monthly SpaceX metrics (estimated mass/satellites from public "
                 "per-vehicle averages; launch counts/vehicle mix from the launch "
                 "record). Grows over time as new months lock in."),
        "months": dict(ordered),
        "cumulative_satellites_est": cumulative,
        # Reserved for operator-curated compute/infrastructure milestones
        # (e.g. xAI Colossus GPU counts, datacenter buildouts). Preserved
        # across runs so it accrues without being overwritten by the fetch.
        "infrastructure": existing.get("infrastructure", []),
        # Curated Starship integrated flight-test record (operator-maintained;
        # outside the Falcon launch window). Preserved across runs.
        "starship_flights": existing.get("starship_flights", {}),
    }
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
        logger.info("Updated metrics time-series %s (%d months)", path, len(months))
    except Exception as exc:
        logger.warning("Could not write metrics time-series (non-fatal): %s", exc)
    # Return the latest cumulative total + the ordered cumulative series
    # (so the dashboard can chart growth-over-time from one file).
    cumulative_series = [{"month": k, "total": cumulative[k]} for k, _ in ordered]
    return cum, cumulative_series


def _starship_flights(path: Path = _METRICS_PATH) -> Dict[str, Any]:
    """Read the curated Starship flight-test record from the committed metrics
    file (operator-maintained; not derivable from the Falcon launch window)."""
    try:
        data = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
        sf = data.get("starship_flights") if isinstance(data, dict) else None
        if isinstance(sf, dict) and isinstance(sf.get("flights"), list):
            return sf
    except Exception as exc:
        logger.warning("Could not read starship_flights (non-fatal): %s", exc)
    return {"flights": []}


def _fleet_payload(previous: List[Dict[str, Any]], now: _dt.datetime) -> Dict[str, Any]:
    """Accurate fleet stats + clearly-estimated mass/satellite headlines for
    the dashboard, computed over the last 365 days of fetched launches."""
    def _parse(net):
        try:
            return _dt.datetime.fromisoformat((net or "").replace("Z", "+00:00"))
        except (ValueError, AttributeError):
            return None

    recent = [r for r in previous if (_parse(r.get("net")) and (now - _parse(r.get("net"))).days <= 365)]
    by_vehicle: Dict[str, int] = {}
    starlink = 0
    est_mass = 0.0
    est_sats = 0
    decided = 0
    successes = 0
    last_failure = None
    for r in recent:
        rocket = (r.get("rocket") or "Other").strip()
        by_vehicle[rocket] = by_vehicle.get(rocket, 0) + 1
        name = (r.get("name") or "").lower()
        is_starlink = "starlink" in name
        if is_starlink:
            starlink += 1
            est_sats += _SATS_PER_STARLINK_LAUNCH
        # mass estimate
        rl = rocket.lower()
        if "heavy" in rl:
            est_mass += _MASS_T["falcon_heavy"]
        elif "starship" in rl:
            est_mass += _MASS_T["starship"]
        elif "falcon" in rl:
            est_mass += _MASS_T["falcon9_starlink"] if is_starlink else _MASS_T["falcon9_other"]
        else:
            est_mass += _MASS_T["falcon9_other"]
        # success rate (only count launches with a decided status)
        abbr = (r.get("status") or "").lower()
        if abbr in ("success", "failure", "partial failure"):
            decided += 1
            if abbr == "success":
                successes += 1
            else:
                d = _parse(r.get("net"))
                if d and (last_failure is None or d > last_failure):
                    last_failure = d
    total_recent = len(recent)
    return {
        "window_days": 365,
        "by_vehicle": by_vehicle,
        "starlink_launches": starlink,
        "starlink_share_pct": round(100 * starlink / total_recent) if total_recent else None,
        "est_mass_to_orbit_tonnes": round(est_mass),
        "est_satellites_deployed": est_sats,
        "success_rate_pct": round(100 * successes / decided, 1) if decided else None,
        "days_since_last_failure": (now - last_failure).days if last_failure else None,
        "estimated": True,  # mass + satellite figures are estimates
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
    # Most-recent launched missions (with outcome) for the "recently flown"
    # panel. prev_results is newest-first.
    recent_list = [_slim_launch(r) for r in prev_results][:6]

    slim_prev = [_slim_launch(r) for r in prev_results]
    monthly = _monthly_breakdown(slim_prev)
    # Merge the fresh 12-month window into the growing committed dataset.
    cumulative_sats, cumulative_series = _update_metrics_timeseries(monthly, now)
    fleet = _fleet_payload(slim_prev, now)
    fleet["cumulative_satellites_est"] = cumulative_sats
    fleet["starlink_active"] = _starlink_active_count()  # real count, or None
    fleet["boosters"] = _booster_stats(prev_results)  # reuse record watch
    return {
        "next": next_launch,
        "previous": previous_launch,
        "upcoming": upcoming_list,
        "recent": recent_list,
        "cadence_monthly": [{"month": b["month"], "count": b["launches"]} for b in monthly],
        "mass_monthly": [{"month": b["month"], "tonnes": b["mass_t"]} for b in monthly],
        "sats_cumulative_monthly": cumulative_series,
        "stats": _stats(slim_prev, now),
        "fleet": fleet,
        "starship": _starship_flights(),
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

    # Keep last-good for the live Starlink count: CelesTrak rate-limits (1 dl /
    # 2h), so a transient None must not wipe a previously-fetched real number.
    if (payload.get("fleet") or {}).get("starlink_active") is None and out_path.exists():
        try:
            prev = json.loads(out_path.read_text(encoding="utf-8"))
            last = (prev.get("fleet") or {}).get("starlink_active")
            if last:
                payload["fleet"]["starlink_active"] = last
                logger.info("Kept last-good Starlink count: %s", last)
        except Exception:
            pass

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
