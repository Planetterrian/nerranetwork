#!/usr/bin/env python3
"""Accumulate Apple's official listening reports into a durable history.

This is the token-authenticated replacement for the cookie scrape in
``fetch_apple_stats.py``. It talks to the same endpoint Reporter.jar
does, needs no Java, and authenticates with a 180-day access token
instead of two browser cookies that expire in roughly a day.

Why it accumulates rather than just fetching
--------------------------------------------
Apple has no history before the day your reporting vendor was
provisioned — which happens when the Apple Podcasters Program agreement
goes Active. Verified: 2026-07-27 downloads, and every earlier date
answers "Invalid vendor number specified", which is Apple's phrasing for
"no report exists". There is no backfill to come back for. So every
day's numbers have to be captured when they are available and kept.

The store is therefore append-merge, never a replacement: a run that
fetches nothing leaves prior days untouched.

Output
------
``api/apple_reporter_daily.json``
    ``{"days": {"YYYY-MM-DD": {"<show_id>": {...metrics}}}}`` — the
    durable history, the thing that must never lose a day.

``api/apple_reporter.json``
    Rollup for the dashboard: per-show totals across the retained
    window, plus ``fetched_at``, the date range covered, and which
    shows Apple reported at all.

Absence versus zero
-------------------
A show with no listening on a day has **no row** in Apple's report, and
a metric Apple suppresses for being too small is **blank**. Both stay
absent here — never 0. A dashboard reading "0 plays" when the truth is
"not measured" is the failure this whole integration exists to avoid.

Usage::

    export APPLE_REPORTER_TOKEN=...      # AccessToken from Reporter.properties
    export APPLE_REPORTER_VENDOR=93825591
    export APPLE_REPORTER_ACCOUNT=128317151
    python scripts/fetch_apple_reporter.py
    python scripts/fetch_apple_reporter.py --days 7 --dry-run
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import logging
import os
import sys
from pathlib import Path
from typing import Dict

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

try:
    from dotenv import load_dotenv

    load_dotenv(REPO_ROOT / ".env")
except ImportError:  # pragma: no cover
    pass

from engine.apple_reporter import (  # noqa: E402
    SHOW_REPORT_WORLDWIDE,
    aggregate_by_show,
    fetch_report_http,
)

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger("apple_reporter")

DAILY_PATH = REPO_ROOT / "api" / "apple_reporter_daily.json"
ROLLUP_PATH = REPO_ROOT / "api" / "apple_reporter.json"

# Apple's daily report lands next-day, but a day can still fill in after
# first publication, so re-fetching a short trailing window keeps the
# store honest without pretending older history is retrievable.
DEFAULT_DAYS = 4

_METRICS = ("plays", "listeners", "engaged_listeners", "listening_hours")


def load_daily() -> dict:
    if not DAILY_PATH.exists():
        return {"days": {}}
    try:
        data = json.loads(DAILY_PATH.read_text(encoding="utf-8"))
        if isinstance(data, dict) and isinstance(data.get("days"), dict):
            return data
    except Exception as exc:  # noqa: BLE001 — a corrupt store must not erase history
        logger.warning("Could not read %s (%s) — refusing to overwrite it",
                       DAILY_PATH.name, exc)
        raise SystemExit(1)
    return {"days": {}}


def show_slugs_by_id() -> Dict[str, str]:
    """Map Apple show ID -> repo slug, from the show YAMLs.

    Reuses the same ``apple_show_id`` the cookie fetcher discovers, so
    the two sources agree on which show is which.
    """
    import yaml

    out: Dict[str, str] = {}
    for path in sorted((REPO_ROOT / "shows").glob("*.yaml")):
        if path.stem.startswith("_"):
            continue
        try:
            data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        except Exception:  # noqa: BLE001
            continue
        podcast = data.get("podcast") or {}
        sid = str(data.get("apple_show_id") or podcast.get("apple_show_id") or "")
        if sid.strip():
            out[sid.strip()] = path.stem
        extra = data.get("apple_show_ids") or podcast.get("apple_show_ids") or {}
        for label, value in (extra or {}).items():
            if str(value).strip():
                out[str(value).strip()] = f"{path.stem}:{label}"
    return out


def build_rollup(days: dict, slugs: Dict[str, str]) -> dict:
    """Per-show totals across every retained day.

    Summing preserves absence: a metric no day reported stays missing
    rather than becoming 0.
    """
    totals: Dict[str, dict] = {}
    for date in sorted(days):
        for show_id, row in (days[date] or {}).items():
            entry = totals.setdefault(show_id, {
                "show_id": show_id,
                "slug": slugs.get(show_id, ""),
                "show_name": row.get("show_name", ""),
                "days_reported": 0,
            })
            entry["days_reported"] += 1
            entry["show_name"] = entry["show_name"] or row.get("show_name", "")
            for key in _METRICS:
                value = row.get(key)
                if value is None:
                    continue
                entry[key] = round(entry.get(key, 0) + value, 4)

    dates = sorted(days)
    return {
        "source": "apple_reporter",
        "fetched_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "first_date": dates[0] if dates else "",
        "last_date": dates[-1] if dates else "",
        "days_retained": len(dates),
        # Named explicitly so a consumer can tell "Apple reported nothing
        # for this show" apart from "we did not ask about it".
        "shows_reported": sorted(totals),
        "shows": totals,
    }


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--days", type=int, default=DEFAULT_DAYS,
                    help=f"Trailing days to (re)fetch, default {DEFAULT_DAYS}")
    ap.add_argument("--dry-run", action="store_true",
                    help="Fetch and report, write nothing")
    args = ap.parse_args(argv)

    token = os.getenv("APPLE_REPORTER_TOKEN", "").strip()
    vendor = os.getenv("APPLE_REPORTER_VENDOR", "").strip()
    account = os.getenv("APPLE_REPORTER_ACCOUNT", "").strip()
    if not (token and vendor):
        logger.info("APPLE_REPORTER_TOKEN / APPLE_REPORTER_VENDOR unset — "
                    "skipping (clean no-op)")
        return 0

    store = load_daily()
    days = store.setdefault("days", {})
    before = len(days)

    today = dt.date.today()  # noqa: DTZ011 — Apple reports on calendar dates
    fetched = errors = absent = 0

    for offset in range(1, max(1, args.days) + 1):
        day = today - dt.timedelta(days=offset)
        stamp = day.strftime("%Y%m%d")
        result = fetch_report_http(
            access_token=token, account=account, vendor=vendor,
            date=stamp, report_type=SHOW_REPORT_WORLDWIDE)

        if result.error:
            errors += 1
            logger.warning("%s: %s", stamp, result.error.splitlines()[0])
            continue
        if result.no_data:
            absent += 1
            logger.info("%s: no report (before the vendor existed, or not "
                        "yet published)", stamp)
            continue

        merged = aggregate_by_show(result.rows)
        # Absent rows are simply not written. Never fabricate a zero for
        # a show Apple did not mention.
        days[day.isoformat()] = {
            show_id: row.as_dict() for show_id, row in merged.items()
        }
        fetched += 1
        logger.info("%s: %d show(s) reported", stamp, len(merged))

    slugs = show_slugs_by_id()
    rollup = build_rollup(days, slugs)

    logger.info("%d day(s) fetched, %d without a report, %d error(s); "
                "store holds %d day(s) (was %d)",
                fetched, absent, errors, len(days), before)

    if args.dry_run:
        print(json.dumps(rollup, indent=2)[:2000])
        return 0

    if errors and not fetched:
        # Every request failed — almost certainly a dead token. Leaving
        # the store untouched keeps yesterday's real numbers on the
        # dashboard instead of replacing them with an empty file.
        logger.error("no day fetched successfully — leaving %s unchanged. "
                     "Regenerate the access token if this persists "
                     "(they expire after 180 days).", DAILY_PATH.name)
        return 0

    DAILY_PATH.parent.mkdir(parents=True, exist_ok=True)
    DAILY_PATH.write_text(json.dumps(store, indent=2, sort_keys=True) + "\n",
                          encoding="utf-8")
    ROLLUP_PATH.write_text(json.dumps(rollup, indent=2) + "\n",
                           encoding="utf-8")
    logger.info("wrote %s and %s", DAILY_PATH.name, ROLLUP_PATH.name)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
