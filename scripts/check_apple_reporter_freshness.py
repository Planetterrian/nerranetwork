#!/usr/bin/env python3
"""Warn when the Apple Podcasts Reporter rollup stops advancing.

Why this needs its own check
----------------------------
``scripts/fetch_apple_reporter.py`` is deliberately built to fail
*quietly and safely*: when every request errors it leaves
``api/apple_reporter_daily.json`` untouched rather than replacing real
numbers with an empty file. That is the right call — stale-but-real
beats empty — but it means a dead token produces a nightly job that
succeeds, a dashboard that still shows plausible figures, and no signal
at all. The failure is invisible precisely because the safety worked.

The Reporter access token expires **180 days** after issue. That is the
most likely cause of a rollup that stops moving, so the warning names it
directly rather than making someone rediscover it.

Exit code is always 0 unless ``--strict``: this is an alarm, not a gate,
and it must never fail the nightly pipeline it rides along with.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
ROLLUP_PATH = REPO_ROOT / "api" / "apple_reporter.json"

# Apple's daily report lands next-day and a day can still fill in after
# first publication, so a couple of days of lag is normal. Three days
# without the window advancing is not.
DEFAULT_MAX_AGE_DAYS = 3


def _parse_iso(value: str) -> dt.datetime | None:
    if not value:
        return None
    try:
        parsed = dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=dt.timezone.utc)
    return parsed


def check(path: Path, max_age_days: float, now: dt.datetime) -> tuple[bool, str]:
    """Return ``(ok, message)``. ``ok`` is False when someone should look."""
    if not path.exists():
        # Not an alarm: the feed is opt-in and may simply not be set up.
        return True, (
            f"{path.name} not present — Apple Reporter is not configured "
            "yet, so there is nothing to be stale."
        )

    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        return False, f"{path.name} is unreadable ({exc})"

    fetched = _parse_iso(data.get("fetched_at", ""))
    if fetched is None:
        return False, f"{path.name} has no usable fetched_at timestamp"

    age_days = (now - fetched).total_seconds() / 86400
    shows = len(data.get("shows") or {})
    last_date = data.get("last_date") or "?"

    if age_days > max_age_days:
        return False, (
            f"Apple Reporter rollup has not advanced in {age_days:.1f} days "
            f"(last fetch {fetched.date()}, last report date {last_date}, "
            f"{shows} show(s)). The access token expires 180 days after "
            "issue and a dead token is the most likely cause — regenerate "
            "it in Apple Podcasts Connect and update the secret. See "
            "docs/analytics.md."
        )

    # A fresh fetch that keeps returning "no report" advances fetched_at
    # but NOT last_date. That is what a wrong APPLE_REPORTER_VENDOR looks
    # like (Apple phrases it exactly like a pre-provisioning date), and
    # every day it persists is unrecoverable history.
    try:
        last_report = dt.datetime.strptime(last_date, "%Y-%m-%d").replace(
            tzinfo=dt.timezone.utc)
    except ValueError:
        last_report = None
    if last_report is not None:
        report_lag_days = (now - last_report).total_seconds() / 86400
        # +1: Apple publishes next-day, so "yesterday missing" is normal.
        if report_lag_days > max_age_days + 1:
            return False, (
                f"Apple Reporter fetches are running (last fetch "
                f"{fetched.date()}) but the newest report date is still "
                f"{last_date} — {report_lag_days:.1f} days ago. Every "
                "request is answering 'no report'; verify "
                "APPLE_REPORTER_VENDOR (a wrong vendor number is "
                "indistinguishable from 'no data') — missed days cannot "
                "be backfilled. See docs/analytics.md."
            )

    return True, (
        f"Apple Reporter fresh: fetched {age_days:.1f} days ago, "
        f"through {last_date}, {shows} show(s)."
    )


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--max-age-days", type=float, default=DEFAULT_MAX_AGE_DAYS)
    ap.add_argument("--path", default=str(ROLLUP_PATH))
    ap.add_argument("--strict", action="store_true",
                    help="Exit non-zero when stale (default: warn only)")
    args = ap.parse_args(argv)

    ok, message = check(
        Path(args.path), args.max_age_days,
        dt.datetime.now(dt.timezone.utc),
    )
    if ok:
        print(message)
        return 0

    print(f"::warning::{message}", flush=True)
    print(message, file=sys.stderr)
    return 1 if args.strict else 0


if __name__ == "__main__":
    raise SystemExit(main())
