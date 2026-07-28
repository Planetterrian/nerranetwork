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


def _sweep(token: str, args, report: str, stamp: str) -> int:
    """Try each plausible request envelope against a date known to have data.

    Apple answered with error 102, "Too few or too many parameters
    specified for the method" — which says the shape is wrong without
    saying which part. The jar is closed source and the wire format is
    undocumented, so this walks the small space of real differences
    rather than guessing one variant per round trip.

    Reading the output: a **fake** token returns 124 for a well-formed
    request and 102 for a malformed one, so the two codes separate
    "envelope wrong" from "credential wrong". With a real token, 102
    means the parameter list is wrong while anything else means the
    envelope was accepted.
    """
    # Named variants rather than a full cross product — twelve blind
    # combinations tell you less than eight deliberate ones.
    variants = [
        ("baseline (jar-style)", {}),
        ("account as JSON number", {"account_as_int": True}),
        ("no account", {"send_account": False}),
        ("mode=Normal", {"mode": "Normal"}),
        ("report version 1_0", {"report_version": "1_0"}),
        ("report version 1_1", {"report_version": "1_1"}),
        ("version 1.0", {"version": "1.0"}),
        ("bare queryInput", {"wrapped_query": False}),
        ("account int + mode Normal",
         {"account_as_int": True, "mode": "Normal"}),
        ("account int + version 1_0",
         {"account_as_int": True, "report_version": "1_0"}),
    ]

    print(f"Sweeping request envelopes for {report} on {stamp}")
    print("(the jar returns data for this date, so anything but success "
          "is our bug)\n")

    for label, overrides in variants:
        result = fetch_report_http(
            access_token=token, account=args.account, vendor=args.vendor,
            date=stamp, report_type=report, **overrides)
        if result.rows:
            print(f"  {label:<28} -> {len(result.rows)} ROWS\n")
            print(f"WORKING ENVELOPE: {label}  {overrides or '(defaults)'}")
            for row in result.rows:
                print("   ", row.as_dict())
            return 0
        if result.no_data:
            print(f"  {label:<28} -> accepted, but no data")
            continue
        text = (result.error or "?").strip()
        code = message = ""
        if "<Code>" in text:
            code = "code " + text.split("<Code>")[1].split("<")[0]
        if "<Message>" in text:
            message = text.split("<Message>")[1].split("<")[0]
        if not (code or message):
            # Not every rejection is Apple's XML — mode=Normal answers in
            # plain text. Showing the raw first non-empty line beats
            # printing an empty arrow, which reads like a crash.
            message = next((ln.strip() for ln in text.splitlines()
                            if ln.strip()), "(empty response)")
        print(f"  {label:<28} -> {code} {message[:80]}".rstrip())

    print("\nNone worked. Paste the whole output — the codes differ "
          "between variants and that narrows it further.")
    return 1


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
    ap.add_argument("--sweep", action="store_true",
                    help="Try every plausible request envelope and report "
                         "which one Apple accepts")
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

    if args.sweep:
        return _sweep(token, args, report, base.strftime("%Y%m%d"))

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
        if result.no_data:
            # Apple says "Invalid vendor number specified" here, which is
            # a lie — the vendor is fine, it just did not exist on that
            # date. Reports begin when the Podcasters Program agreement
            # goes Active, so anything earlier has no history to fetch.
            print(f"{stamp}  no report exists for this date "
                  f"(before the vendor was provisioned)")
            continue
        if not result.rows:
            print(f"{stamp}  report exists but no show had activity")
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
