#!/usr/bin/env python3
"""Are the members' private Nerra Personal feeds getting today's edition?

Nov 6 2026: every run of the private batch repo's "Nerra Personal daily
feeds" workflow from Nov 2 to Nov 6 failed in its first second with a 401
from ``/api/admin/personal-specs`` (the batch repo's PERSONAL_ADMIN_TOKEN no
longer matched the Worker's after a rotation). No member's feed gained an
episode for five days and nothing noticed: the batch repo's failure webhook
was never configured, and every check in this repo reads the PUBLIC feeds.

This check reads two counts-only sources and pages (exit 1) when a paying
member's feed has no edition for today:

1. The gallery Worker's ``GET /api/admin/personal-feed-health`` — for every
   active member, the newest edition date in their private episodes.json,
   summarised as counts. Needs PERSONAL_DEMAND_TOKEN (or the admin token).
2. The batch repo's recent workflow runs (conclusions and timestamps only,
   never a log) — so the page says WHY, e.g. "8 runs in a row failed".
   Needs PERSONAL_BATCH_DISPATCH_TOKEN (Actions: Read on the batch repo);
   optional.

Writes ``api/personal_feed_health.json``: counts and timestamps only — no
name, city, email or feed token ever reaches it (the file is public). A
source that could not be read is ``null``, never 0.

Exit codes: 0 healthy / unverifiable (with a ::warning::), 1 a member's
feed is behind (::error::).
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parent.parent
API_BASE = os.environ.get("NERRA_API_BASE", "https://api.nerranetwork.com").rstrip("/")
BATCH_REPO = "Planetterrian/nerra-personal-batch"
BATCH_WORKFLOW = "personal-feeds.yml"
EASTERN = ZoneInfo("America/New_York")
# Today's edition is dispatched when Nerra Daily publishes (by 7:00 ET) and
# the batch repo's sweeps follow; before this hour a feed that only lacks
# TODAY is still on time, so the page waits for a whole missed day.
ON_TIME_HOUR_EASTERN = 10

FEED_KEYS = ("today", "members", "built_today", "behind", "never_built",
             "newest_edition", "oldest_latest_edition", "max_days_behind")


def _token(*names: str) -> str:
    for name in names:
        value = (os.environ.get(name) or "").strip()
        if value:
            return value
    return ""


def fetch_feed_health(session) -> Dict[str, Any]:
    """The Worker's counts, or ``{"error": ...}`` — never a guessed zero."""
    token = _token("PERSONAL_DEMAND_TOKEN", "PERSONAL_ADMIN_TOKEN")
    if not token:
        return {"error": "no PERSONAL_DEMAND_TOKEN or PERSONAL_ADMIN_TOKEN"}
    try:
        resp = session.get(f"{API_BASE}/api/admin/personal-feed-health",
                           headers={"Authorization": f"Bearer {token}"},
                           timeout=60)
    except Exception as exc:  # noqa: BLE001 — any transport failure
        return {"error": f"unreachable: {type(exc).__name__}"}
    if resp.status_code == 404:
        return {"error": "the gallery Worker has no /api/admin/personal-feed-health "
                         "yet (deploy workers/gallery)"}
    if resp.status_code == 401:
        return {"error": "401: this repo's token does not match the Worker's"}
    if resp.status_code != 200:
        return {"error": f"HTTP {resp.status_code}"}
    try:
        body = resp.json()
    except ValueError:
        return {"error": "unreadable JSON"}
    return {k: body.get(k) for k in FEED_KEYS}


def summarise_runs(runs: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Newest-first workflow runs -> the streak that explains a stale feed."""
    completed = [r for r in runs if r.get("status") == "completed"]
    streak = 0
    for run in completed:
        if run.get("conclusion") == "success":
            break
        streak += 1
    last_ok = next((r for r in completed if r.get("conclusion") == "success"), None)
    newest = completed[0] if completed else None
    return {
        "latest_conclusion": newest.get("conclusion") if newest else None,
        "latest_run_at": newest.get("created_at") if newest else None,
        "latest_run_url": newest.get("html_url") if newest else None,
        "failures_in_a_row": streak,
        # None when no success is in the window: unknown, not "never".
        "last_success_at": last_ok.get("created_at") if last_ok else None,
        "runs_read": len(completed),
    }


def fetch_batch_runs(session) -> Dict[str, Any]:
    token = _token("PERSONAL_BATCH_DISPATCH_TOKEN")
    if not token:
        return {"error": "no PERSONAL_BATCH_DISPATCH_TOKEN"}
    url = (f"https://api.github.com/repos/{BATCH_REPO}/actions/workflows/"
           f"{BATCH_WORKFLOW}/runs?per_page=20")
    try:
        resp = session.get(url, timeout=30, headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        })
    except Exception as exc:  # noqa: BLE001
        return {"error": f"unreachable: {type(exc).__name__}"}
    if resp.status_code != 200:
        return {"error": f"HTTP {resp.status_code}"}
    try:
        runs = resp.json().get("workflow_runs") or []
    except ValueError:
        return {"error": "unreadable JSON"}
    return summarise_runs(runs)


def verdict(feeds: Dict[str, Any], now_eastern: dt.datetime) -> Optional[str]:
    """A sentence when a member's feed is behind, else None. Unreadable
    counts are never a verdict (the caller warns instead)."""
    if feeds.get("error") or not feeds.get("members"):
        return None
    behind = int(feeds.get("behind") or 0)
    never = int(feeds.get("never_built") or 0)
    lag = feeds.get("max_days_behind")
    if not behind and not never:
        return None
    if now_eastern.hour < ON_TIME_HOUR_EASTERN and not never and (lag or 0) < 2:
        return None  # only today is missing, and today's build is not due yet
    parts = []
    if behind:
        parts.append(f"{behind} of {feeds['members']} member feeds have no edition "
                     f"for {feeds.get('today')} (the oldest stopped at "
                     f"{feeds.get('oldest_latest_edition')}, {lag} day(s) behind)")
    if never:
        parts.append(f"{never} member feed(s) have never been built")
    return "; ".join(parts)


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--out", default=str(ROOT / "api" / "personal_feed_health.json"))
    args = parser.parse_args(argv)

    import requests

    session = requests.Session()
    now = dt.datetime.now(dt.timezone.utc)
    feeds = fetch_feed_health(session)
    batch = fetch_batch_runs(session)
    problem = verdict(feeds, now.astimezone(EASTERN))

    record = {
        "generated_at": now.isoformat(timespec="seconds"),
        "feeds": None if feeds.get("error") else feeds,
        "feeds_error": feeds.get("error"),
        "batch": None if batch.get("error") else batch,
        "batch_error": batch.get("error"),
        "stale": None if feeds.get("error") else bool(problem),
    }
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")

    if feeds.get("error"):
        print(f"::warning::Nerra Personal feeds UNVERIFIED — {feeds['error']}")
    else:
        print(f"Nerra Personal feeds ({feeds.get('today')}): "
              f"{feeds.get('built_today')}/{feeds.get('members')} built today, "
              f"{feeds.get('behind')} behind, {feeds.get('never_built')} never built")
    if not batch.get("error"):
        print(f"Batch workflow: latest {batch['latest_conclusion']} at "
              f"{batch['latest_run_at']}; {batch['failures_in_a_row']} failure(s) "
              f"in a row; last success {batch['last_success_at'] or 'not in the last 20 runs'}")
    elif batch.get("error") != "no PERSONAL_BATCH_DISPATCH_TOKEN":
        print(f"::warning::batch workflow runs unreadable — {batch['error']}")

    if not problem:
        # A failing batch with fresh feeds (e.g. one member's on-demand
        # rebuild failed) is worth a line, not a page.
        if not batch.get("error") and batch.get("failures_in_a_row"):
            print(f"::warning::the Nerra Personal batch workflow's last "
                  f"{batch['failures_in_a_row']} run(s) failed: {batch['latest_run_url']}")
        return 0

    why = ""
    if not batch.get("error") and batch.get("failures_in_a_row"):
        why = (f" The batch workflow has failed {batch['failures_in_a_row']} run(s) in a "
               f"row ({batch['latest_run_url']}). A 401 on /api/admin/personal-specs "
               f"means the batch repo's PERSONAL_ADMIN_TOKEN no longer matches the "
               f"gallery Worker's: set both to the same value.")
    print(f"::error::NERRA PERSONAL FEEDS STALE: {problem}.{why}")
    return 1


if __name__ == "__main__":
    sys.exit(main())
