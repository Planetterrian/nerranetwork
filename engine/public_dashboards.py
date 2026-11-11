"""The public data dashboards' derived numbers and their freshness.

Nov 11 2026 dashboard review: the Tesla dashboard's quarterly series ended at
2025 Q1 (six quarters behind) and the SpaceX Starship tracker at IFT-9 (five
flights behind) while both pages read "Live". Nothing watched the two curated
files, so nothing noticed. This module is the ONE place that reads them for

* the Tesla dashboard's "latest quarter" scoreboard (``tesla_latest_quarter``),
* the home page's dashboard cards (``homepage_facts``), and
* Mission Control's freshness check (``curated_freshness``),

so a number on the home page and the same number on the dashboard can never
come from two readings. Pure functions over the committed JSON; no network.
"""

from __future__ import annotations

import datetime as _dt
import json
from pathlib import Path
from typing import Any, Dict, List, Optional

TESLA_METRICS = Path("site") / "data" / "tesla_metrics.json"
SPACEX_METRICS = Path("site") / "data" / "spacex_metrics.json"
SPACEX_LAUNCHES = Path("api") / "spacex_launches.json"
MIT_SUMMARY = Path("digests") / "modern_investing" / "investment_tracker.json"

# Tesla publishes each quarter's Production & Deliveries in the first days of
# the next quarter. A quarter is OVERDUE in the curated file once this many
# days have passed since it ended (a week of slack for the release + the edit).
TESLA_QUARTER_GRACE_DAYS = 10
# A finished calendar year is overdue in the annual series after January.
ANNUAL_GRACE_DAYS = 31


def _load(root: Path, rel: Path) -> Dict[str, Any]:
    try:
        data = json.loads((root / rel).read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def _quarter_key(label: Any) -> Optional[tuple]:
    """``"2026 Q3"`` -> ``(2026, 3)``; None for anything else."""
    parts = str(label or "").split()
    if len(parts) != 2 or not parts[0].isdigit() or not parts[1].upper().startswith("Q"):
        return None
    try:
        q = int(parts[1][1:])
    except ValueError:
        return None
    return (int(parts[0]), q) if 1 <= q <= 4 else None


def _quarter_end(year: int, q: int) -> _dt.date:
    if q == 4:
        return _dt.date(year, 12, 31)
    return _dt.date(year, 3 * q + 1, 1) - _dt.timedelta(days=1)


def _pct(new: Optional[float], old: Optional[float]) -> Optional[float]:
    if new is None or not old:
        return None
    return round((float(new) - float(old)) / float(old) * 100, 1)


def tesla_latest_quarter(metrics: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """The newest quarter in the curated series with its year-over-year
    changes (None where the year-ago quarter is not in the file — a missing
    comparison is never shown as 0)."""
    rows = [r for r in (metrics.get("deliveries_quarterly") or [])
            if isinstance(r, dict) and _quarter_key(r.get("quarter"))]
    if not rows:
        return None
    rows.sort(key=lambda r: _quarter_key(r["quarter"]))
    last = rows[-1]
    y, q = _quarter_key(last["quarter"])
    by_key = {_quarter_key(r["quarter"]): r for r in rows}
    ago = by_key.get((y - 1, q)) or {}
    nq = (y + 1, 1) if q == 4 else (y, q + 1)
    return {
        "quarter": last["quarter"],
        "label": f"Q{q} {y}",
        "delivered": last.get("delivered"),
        "produced": last.get("produced"),
        "energy_gwh": last.get("energy_gwh"),
        "delivered_yoy_pct": _pct(last.get("delivered"), ago.get("delivered")),
        "energy_yoy_pct": _pct(last.get("energy_gwh"), ago.get("energy_gwh")),
        "inventory_change": (last["produced"] - last["delivered"]
                             if isinstance(last.get("produced"), int) and isinstance(last.get("delivered"), int)
                             else None),
        "next_label": f"Q{nq[1]} {nq[0]}",
        # The next release lands in the first days after that quarter ends.
        "next_release_after": (_quarter_end(*nq) + _dt.timedelta(days=1)).isoformat(),
    }


def _latest_year(rows: Any, key: str = "year") -> Optional[int]:
    years = [int(str(r.get(key))) for r in (rows or [])
             if isinstance(r, dict) and str(r.get(key) or "").isdigit() and not r.get("ytd")]
    return max(years) if years else None


def curated_freshness(root: Path, today: Optional[_dt.date] = None) -> List[Dict[str, str]]:
    """Every curated public series that has fallen behind, as findings
    ``{"series", "latest", "expected"}``. Empty when all are current."""
    today = today or _dt.date.today()
    findings: List[Dict[str, str]] = []

    tesla = _load(root, TESLA_METRICS)
    lq = tesla_latest_quarter(tesla)
    if lq:
        y, q = _quarter_key(lq["quarter"])
        nq = (y + 1, 1) if q == 4 else (y, q + 1)
        due = _quarter_end(*nq) + _dt.timedelta(days=TESLA_QUARTER_GRACE_DAYS)
        if today > due:
            findings.append({"series": "Tesla quarterly deliveries (site/data/tesla_metrics.json)",
                             "latest": lq["quarter"],
                             "expected": f"{nq[0]} Q{nq[1]} (released early {_quarter_end(*nq) + _dt.timedelta(days=2):%B %Y})"})
    prev_year = today.year - 1
    year_due = _dt.date(today.year, 1, 1) + _dt.timedelta(days=ANNUAL_GRACE_DAYS)
    for key, label in (("deliveries_annual", "Tesla annual deliveries"),
                       ("energy_storage_annual_gwh", "Tesla annual energy storage"),
                       ("supercharger_connectors_annual", "Tesla Supercharger connectors")):
        latest = _latest_year(tesla.get(key))
        if latest is not None and latest < prev_year - (0 if today > year_due else 1):
            findings.append({"series": f"{label} (site/data/tesla_metrics.json)",
                             "latest": str(latest), "expected": str(prev_year if today > year_due else prev_year - 1)})

    spx = _load(root, SPACEX_METRICS)
    years = (spx.get("annual_launches") or {}).get("years") or []
    latest = _latest_year(years)
    want = prev_year if today > year_due else prev_year - 1
    if latest is not None and latest < want:
        findings.append({"series": "SpaceX launches per year (site/data/spacex_metrics.json)",
                         "latest": str(latest), "expected": str(want)})
    flights = (spx.get("starship_flights") or {}).get("flights") or []
    tracked = max((str(f.get("date") or "") for f in flights if isinstance(f, dict)), default="")
    launches = _load(root, SPACEX_LAUNCHES)
    flown = [str(launch.get("net") or "")[:10]
             for launch in [launches.get("previous") or {}] + list(launches.get("recent") or [])
             if isinstance(launch, dict) and "starship" in f"{launch.get('rocket')} {launch.get('name')}".lower()]
    newest_flown = max(flown, default="")
    if tracked and newest_flown and newest_flown > tracked:
        findings.append({"series": "Starship flight-test tracker (site/data/spacex_metrics.json)",
                         "latest": tracked, "expected": f"the flight of {newest_flown}"})
    return findings


def _fmt_int(n: Any) -> str:
    return f"{int(n):,}" if isinstance(n, (int, float)) else ""


def _signed(p: Optional[float], unit: str = "%", places: int = 1) -> str:
    if p is None:
        return ""
    sign = "+" if p >= 0 else "\u2212"
    return f"{sign}{abs(p):.{places}f}{unit}"


def homepage_facts(root: Path) -> Dict[str, List[Dict[str, str]]]:
    """Up to three headline numbers per dashboard for the home page's
    dashboards band: ``{slug: [{"value", "label"}]}``. A number the files do
    not hold is left out, never shown as 0."""
    out: Dict[str, List[Dict[str, str]]] = {}

    lq = tesla_latest_quarter(_load(root, TESLA_METRICS))
    if lq and lq.get("delivered"):
        tesla = [{"value": _fmt_int(lq["delivered"]),
                  "label": f"delivered in {lq['label']}"
                           + (f" ({_signed(lq['delivered_yoy_pct'])} y/y)" if lq.get("delivered_yoy_pct") is not None else "")}]
        if lq.get("energy_gwh") is not None:
            tesla.append({"value": f"{lq['energy_gwh']:g} GWh",
                          "label": "energy storage deployed"
                                   + (f" ({_signed(lq['energy_yoy_pct'])} y/y)" if lq.get("energy_yoy_pct") is not None else "")})
        out["tesla"] = tesla

    spacex: List[Dict[str, str]] = []
    launches = _load(root, SPACEX_LAUNCHES)
    metrics = _load(root, SPACEX_METRICS)
    # The same row the dashboard's "Launches per year" chart labels YTD.
    ytd = next((y for y in (metrics.get("annual_launches") or {}).get("years") or []
                if isinstance(y, dict) and y.get("ytd") and isinstance(y.get("launches"), int)), None)
    if ytd:
        spacex.append({"value": str(ytd["launches"]), "label": f"orbital launches in {ytd['year']} so far"})
    fleet = launches.get("fleet") or {}
    if isinstance(fleet.get("starlink_active"), int):
        spacex.append({"value": _fmt_int(fleet["starlink_active"]), "label": "active Starlink satellites"})
    flights = ((metrics.get("starship_flights") or {}).get("flights")) or []
    if flights:
        last = max((f for f in flights if isinstance(f, dict)), key=lambda f: str(f.get("date") or ""))
        if last.get("flight"):
            spacex.append({"value": str(last["flight"]).replace("IFT-", "Flight "),
                           "label": f"latest Starship test ({last.get('outcome') or 'flown'})"})
    if spacex:
        out["spacex"] = spacex

    # MIT: the ERA record only, the one number the show speaks (CLAUDE.md,
    # "MIT speaks the era record"); the blended history is never a headline.
    summary = (_load(root, MIT_SUMMARY).get("summary") or {})
    n = summary.get("era_trades")
    alpha = summary.get("era_alpha_pct")
    if isinstance(n, int) and n > 0 and isinstance(alpha, (int, float)):
        t = summary.get("era_alpha_t_stat")
        luck = isinstance(t, (int, float)) and abs(t) < 2
        mit = [{"value": f"{_signed(float(alpha), '', 2)} pts",
                "label": "average trade vs the NASDAQ" + (" (not yet distinguishable from luck)" if luck else "")},
               {"value": str(n), "label": f"closed trades since {summary.get('era_inception') or 'the rules began'}"}]
        beat = summary.get("era_beat_benchmark")
        if isinstance(beat, int):
            mit.append({"value": f"{beat} of {n}", "label": "beat the index"})
        out["modern_investing"] = mit
    return out
