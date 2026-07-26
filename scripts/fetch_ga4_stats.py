#!/usr/bin/env python3
"""Fetch GA4 website analytics into ``api/ga4_stats.json``.

Closes the last first-party loop in the audience picture: the site has
carried GA4 (property 533581233, tag G-6PWJCVQQ7B — see
``generate_html.py``) since launch, but nothing ever read the data back
into the repo. This script pulls a compact 28-day summary via the
official GA4 Data API so ``scripts/generate_dashboard.py`` (and any
human or AI reading ``api/``) can see site traffic next to podcast
downloads, YouTube subs, and newsletter counts.

Auth: a Google Cloud service account with the *Viewer* role granted on
the GA4 property (GA Admin → Property access management → add the
service-account email). The full JSON key lives in the
``GA4_SERVICE_ACCOUNT_JSON`` secret. No new dependencies — uses the
``google-auth`` stack already required by the YouTube pipeline, talking
REST to ``analyticsdata.googleapis.com``.

Clean no-op when ``GA4_SERVICE_ACCOUNT_JSON`` is unset: logs one line,
exits 0, leaves any previously committed output untouched — same
convention as every other optional integration in this repo.

Usage::

    python scripts/fetch_ga4_stats.py                # write api/ga4_stats.json
    python scripts/fetch_ga4_stats.py --dry-run      # print, write nothing
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import logging
import os
from pathlib import Path
from typing import Any, Dict, List

REPO_ROOT = Path(__file__).resolve().parent.parent

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger("fetch_ga4_stats")

DEFAULT_PROPERTY_ID = "533581233"  # Nerra Network GA4 (see generate_html.py)
API = "https://analyticsdata.googleapis.com/v1beta"
SCOPES = ["https://www.googleapis.com/auth/analytics.readonly"]


def _session():
    from google.oauth2 import service_account
    from google.auth.transport.requests import AuthorizedSession

    raw = os.getenv("GA4_SERVICE_ACCOUNT_JSON", "").strip()
    if not raw:
        return None
    info = json.loads(raw)
    creds = service_account.Credentials.from_service_account_info(
        info, scopes=SCOPES)
    return AuthorizedSession(creds)


def _run_report(session, prop: str, body: Dict[str, Any]) -> Dict[str, Any]:
    resp = session.post(f"{API}/properties/{prop}:runReport",
                        json=body, timeout=60)
    resp.raise_for_status()
    return resp.json()


def _rows(report: Dict[str, Any]) -> List[Dict[str, Any]]:
    dims = [d["name"] for d in report.get("dimensionHeaders", [])]
    mets = [m["name"] for m in report.get("metricHeaders", [])]
    out = []
    for row in report.get("rows", []):
        rec: Dict[str, Any] = {}
        for name, v in zip(dims, row.get("dimensionValues", [])):
            rec[name] = v.get("value")
        for name, v in zip(mets, row.get("metricValues", [])):
            val = v.get("value")
            try:
                rec[name] = float(val) if "." in str(val) else int(val)
            except (TypeError, ValueError):
                rec[name] = val
        out.append(rec)
    return out


def fetch(prop: str, days: int) -> Dict[str, Any]:
    session = _session()
    if session is None:
        raise RuntimeError("unconfigured")

    date_range = [{"startDate": f"{days}daysAgo", "endDate": "today"}]
    core_metrics = [{"name": "activeUsers"}, {"name": "sessions"},
                    {"name": "screenPageViews"},
                    {"name": "averageSessionDuration"}]

    day_series = _rows(_run_report(session, prop, {
        "dateRanges": date_range,
        "dimensions": [{"name": "date"}],
        "metrics": core_metrics,
        "orderBys": [{"dimension": {"dimensionName": "date"}}],
    }))
    top_pages = _rows(_run_report(session, prop, {
        "dateRanges": date_range,
        "dimensions": [{"name": "pagePath"}],
        "metrics": [{"name": "screenPageViews"}, {"name": "activeUsers"}],
        "orderBys": [{"metric": {"metricName": "screenPageViews"},
                      "desc": True}],
        "limit": 15,
    }))
    channels = _rows(_run_report(session, prop, {
        "dateRanges": date_range,
        "dimensions": [{"name": "sessionDefaultChannelGroup"}],
        "metrics": [{"name": "sessions"}, {"name": "activeUsers"}],
        "orderBys": [{"metric": {"metricName": "sessions"}, "desc": True}],
    }))
    countries = _rows(_run_report(session, prop, {
        "dateRanges": date_range,
        "dimensions": [{"name": "country"}],
        "metrics": [{"name": "activeUsers"}],
        "orderBys": [{"metric": {"metricName": "activeUsers"}, "desc": True}],
        "limit": 10,
    }))

    totals = {
        "active_users": sum(int(r.get("activeUsers", 0)) for r in day_series),
        "sessions": sum(int(r.get("sessions", 0)) for r in day_series),
        "page_views": sum(int(r.get("screenPageViews", 0))
                          for r in day_series),
    }
    return {
        "fetched_at": dt.datetime.now(dt.timezone.utc).isoformat(
            timespec="seconds"),
        "property_id": prop,
        "days": days,
        "totals": totals,
        "day_series": day_series,
        "top_pages": top_pages,
        "channels": channels,
        "countries": countries,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", default=str(REPO_ROOT / "api"
                                             / "ga4_stats.json"))
    parser.add_argument("--days", type=int, default=28)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    if not os.getenv("GA4_SERVICE_ACCOUNT_JSON", "").strip():
        logger.info("GA4_SERVICE_ACCOUNT_JSON unset — skipping GA4 fetch "
                    "(clean no-op)")
        return 0

    prop = os.getenv("GA4_PROPERTY_ID", DEFAULT_PROPERTY_ID).strip()
    try:
        data = fetch(prop, args.days)
    except Exception as exc:  # noqa: BLE001 — nightly must not go red
        logger.error("GA4 fetch failed (leaving previous output "
                     "untouched): %s", exc)
        return 0

    if args.dry_run:
        print(json.dumps(data, indent=2)[:4000])
        return 0
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    logger.info("wrote %s (%d-day window, %d sessions)",
                out, args.days, data["totals"]["sessions"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
