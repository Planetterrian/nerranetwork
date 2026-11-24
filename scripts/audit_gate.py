#!/usr/bin/env python3
"""Once-a-day gate for the Daily Audit workflow (Nov 24 2026).

The audit has two clocks now: the scheduler Worker dispatches it at 11:15
Eastern, and GitHub's own cron stays as the fallback. GitHub delivered that
cron four to ten hours late on every day from Nov 14 to Nov 24, so without a
gate each day would be audited twice — a second round of reviewer calls, a
second issue, and a second retry decision made in the evening for episodes
the morning's audit had already sent back.

The rule: an untargeted run is skipped when the report on ``main`` already
carries today's date on the network's (Eastern) calendar. A run aimed at a
date or a show, or dispatched with ``force``, always runs. Any failure to
read the report means RUN — an audit done twice costs a few reviewer calls;
an audit not done is the failure this workflow exists to prevent.
"""
from __future__ import annotations

import datetime
import json
import os
import subprocess
import sys
from zoneinfo import ZoneInfo

#: review_episodes.NETWORK_TZ — the day the audit dates its report by.
NETWORK_TZ = ZoneInfo("America/New_York")
REPORT_PATH = "api/daily-review.json"


def decide(*, input_date: str, input_show: str, force: bool,
           report_date: str | None, now: datetime.datetime) -> tuple[bool, str]:
    """``(run, reason)``. Pure: the tests drive it with a fixed clock."""
    if force:
        return True, "force was set"
    if input_date.strip() or input_show.strip():
        return True, "the run names a date or a show"
    if report_date is None:
        return True, "the report on main could not be read"
    today = now.astimezone(NETWORK_TZ).date().isoformat()
    if report_date == today:
        return False, (f"{REPORT_PATH} on main is already dated {today} — "
                       "today's audit has run")
    return True, f"the report on main is dated {report_date or 'unknown'}, not {today}"


def read_report_date(repo: str) -> str | None:
    """The ``date`` of the report on the live tip of main, or ``None``.

    Read through the API, never a checkout: a run that waited on the
    workflow's concurrency lock holds the commit it was triggered on, which
    predates the report the run ahead of it just committed."""
    try:
        out = subprocess.run(
            ["gh", "api", f"repos/{repo}/contents/{REPORT_PATH}?ref=main",
             "-H", "Accept: application/vnd.github.raw"],
            check=True, capture_output=True, text=True, timeout=60,
        ).stdout
        return str(json.loads(out).get("date") or "")
    except Exception as exc:  # noqa: BLE001 — fail open, see the module note
        print(f"could not read {REPORT_PATH} from main: {exc}")
        return None


def main() -> int:
    force = (os.environ.get("INPUT_FORCE") or "").strip().lower() == "true"
    input_date = os.environ.get("INPUT_DATE") or ""
    input_show = os.environ.get("INPUT_SHOW") or ""
    report_date = None
    if not force and not (input_date.strip() or input_show.strip()):
        report_date = read_report_date(os.environ.get("GITHUB_REPOSITORY", ""))
    run, reason = decide(
        input_date=input_date, input_show=input_show, force=force,
        report_date=report_date,
        now=datetime.datetime.now(datetime.timezone.utc))
    print(f"audit gate: {'run' if run else 'skip'} — {reason}")
    if not run:
        print(f"::notice::Daily Audit skipped: {reason}. Dispatch with "
              "force=true to audit again.")
    out = os.environ.get("GITHUB_OUTPUT")
    if out:
        with open(out, "a", encoding="utf-8") as fh:
            fh.write(f"run={'true' if run else 'false'}\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
