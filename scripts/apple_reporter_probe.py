#!/usr/bin/env python3
"""Verify the token-only HTTP path against Apple, no Java required.

``Reporter.jar`` works but cannot run in CI: macOS ships no JRE, GitHub's
runners would need a Java toolchain, and Apple's binary can't be
redistributed into a public repo. The jar is a thin client over an HTTP
endpoint, so :func:`engine.apple_reporter.fetch_report_http` speaks that
endpoint directly with nothing but the 180-day access token.

This proves it before anything depends on it. Run it where the token is,
compare the numbers to what the jar produced for the same date, and only
then wire the nightly to it.

Usage::

    export APPLE_REPORTER_TOKEN='<the AccessToken from Reporter.properties>'
    python scripts/apple_reporter_probe.py --vendor 93825591 --account 128317151
    python scripts/apple_reporter_probe.py --date 20260727 --storefronts

The token is read from the environment, never a flag — a flag would put
a 180-day credential into shell history.
"""

from __future__ import annotations

import argparse
import datetime as dt
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

try:
    from dotenv import load_dotenv

    load_dotenv(ROOT / ".env")
except ImportError:  # pragma: no cover
    pass

from engine.apple_reporter import (  # noqa: E402
    SHOW_REPORT,
    SHOW_REPORT_WORLDWIDE,
    aggregate_by_show,
    fetch_report_http,
)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--vendor", default=os.getenv("APPLE_REPORTER_VENDOR", ""),
                    help="Vendor number from Sales.getVendors")
    ap.add_argument("--account", default=os.getenv("APPLE_REPORTER_ACCOUNT", ""),
                    help="Account number from Sales.getAccounts")
    ap.add_argument("--date", default="",
                    help="YYYYMMDD, default yesterday (reports are next-day)")
    ap.add_argument("--storefronts", action="store_true",
                    help="Per-storefront report instead of worldwide")
    ap.add_argument("--days", type=int, default=1,
                    help="Also walk back this many days, to see coverage")
    args = ap.parse_args()

    token = os.getenv("APPLE_REPORTER_TOKEN", "").strip()
    if not token:
        print("APPLE_REPORTER_TOKEN is not set.\n"
              "It is the AccessToken line in your Reporter.properties.\n"
              "  export APPLE_REPORTER_TOKEN='...'", file=sys.stderr)
        return 2
    if not args.vendor:
        print("--vendor is required (Sales.getVendors)", file=sys.stderr)
        return 2

    report = SHOW_REPORT if args.storefronts else SHOW_REPORT_WORLDWIDE
    base = (dt.datetime.strptime(args.date, "%Y%m%d").date() if args.date
            else dt.date.today() - dt.timedelta(days=1))  # noqa: DTZ011

    any_rows = False
    for offset in range(args.days):
        day = base - dt.timedelta(days=offset)
        stamp = day.strftime("%Y%m%d")
        result = fetch_report_http(
            access_token=token, account=args.account,
            vendor=args.vendor, date=stamp, report_type=report,
        )
        if not result.ok:
            print(f"{stamp}  ERROR  {result.error}")
            continue
        if not result.rows:
            print(f"{stamp}  no shows reported activity")
            continue

        any_rows = True
        merged = aggregate_by_show(result.rows)
        print(f"{stamp}  {len(merged)} show(s), "
              f"{len(result.rows)} row(s)")
        for row in sorted(merged.values(),
                          key=lambda r: r.plays or -1, reverse=True):
            # "—" rather than 0 for a metric Apple suppressed: the whole
            # point of this integration is not inventing zeros.
            def show(value):
                return "—" if value is None else value

            print(f"    {row.show_id:<12} {row.show_name[:34]:<34} "
                  f"plays={show(row.plays):>6}  "
                  f"listeners={show(row.listeners):>5}  "
                  f"engaged={show(row.engaged_listeners):>5}  "
                  f"hours={show(row.listening_hours):>6}")

    if not any_rows:
        print("\nNo data returned. If the jar works for the same date, the "
              "HTTP path needs adjusting — paste this output.")
        return 1
    print("\nHTTP path works. This can run in CI with no Java and no jar.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
