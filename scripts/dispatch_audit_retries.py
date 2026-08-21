#!/usr/bin/env python3
"""Automated remediation for the Daily Audit workflow.

Reads api/daily-review.json (produced by review_episodes.py) and dispatches
`gh workflow run run-show.yml` for any shows listed under
`remediation.auto_retry_shows`.

This script exists so the complex shell + heredoc logic lives outside the
workflow YAML. This completely avoids noisy SC2086 reports from actionlint's
embedded shellcheck when processing large `run: |` blocks.
"""

import datetime
import json
import os
import subprocess
import sys
from pathlib import Path


def _post_webhook(text: str) -> None:
    """Best-effort operator alert (post_run_summary.py contract): clean no-op
    when NOTIFICATION_WEBHOOK_URL is unset, warns loudly but never raises."""
    webhook = (os.environ.get("NOTIFICATION_WEBHOOK_URL") or "").strip()
    if not webhook:
        return
    try:
        import requests
        resp = requests.post(webhook, json={"text": text}, timeout=15)
        if resp.status_code >= 300:
            print(f"::warning::Audit webhook returned {resp.status_code} (non-blocking)")
    except Exception as exc:  # noqa: BLE001
        print(f"::warning::Audit webhook failed: {exc} (non-blocking)")


def _same_day_recovery_branch(show: str,
                              now: datetime.datetime | None = None) -> str | None:
    """Return a recovery/<show>-* branch pushed TODAY (UTC), if any.

    A stranded episode (push to main failed → recovery branch) already ran its
    full pipeline, INCLUDING the YouTube/R2 uploads — re-dispatching the show
    duplicates public videos (happened Jun 25 2026: models_agents + tesla).
    Branch names end in the recovery script's unix timestamp
    (recovery/<show>-<run_id>-<epoch>), so "same day" is decidable offline.
    """
    now = now or datetime.datetime.now(datetime.timezone.utc)
    try:
        result = subprocess.run(
            ["git", "ls-remote", "--heads", "origin",
             f"refs/heads/recovery/{show}-*"],
            check=True, capture_output=True, text=True,
        )
    except subprocess.CalledProcessError:
        return None  # best-effort guard; the dispatch itself stays possible
    for line in result.stdout.splitlines():
        ref = line.split("\t")[-1].strip()
        branch = ref.removeprefix("refs/heads/")
        epoch = branch.rsplit("-", 1)[-1]
        if not epoch.isdigit():
            continue
        pushed = datetime.datetime.fromtimestamp(int(epoch), tz=datetime.timezone.utc)
        if pushed.date() == now.date():
            return branch
    return None


def main() -> None:
    review_path = Path("api/daily-review.json")

    if not review_path.exists():
        print("No structured audit output — skipping auto-remediation")
        return

    try:
        data = json.loads(review_path.read_text())
    except Exception as exc:
        print(f"Failed to parse {review_path}: {exc}")
        sys.exit(0)

    # Stale-report guard (2026-08-21): when review_episodes.py dies before
    # writing a fresh report (that day: grok-4.6 reviewer timeouts blew the
    # job budget), this file still holds an EARLIER day's remediation list —
    # and replaying it dispatches full duplicate episode pipelines, YouTube
    # and R2 uploads included. The 2026-08-19 list was replayed on BOTH the
    # 20th and 21st (4 duplicate episodes/day, 6 recovery PRs). A retry
    # decision is only ever valid for the day it was computed.
    today = datetime.datetime.now(datetime.timezone.utc).date().isoformat()
    review_date = str(data.get("date") or "")
    if review_date != today:
        msg = (f"api/daily-review.json is dated {review_date or 'unknown'}, "
               f"not {today} — refusing to dispatch retries from a stale "
               "report (today's audit did not ship one)")
        print(f"::warning::{msg}")
        _post_webhook(f"⚠️ Daily audit: {msg}")
        return

    shows = data.get("remediation", {}).get("auto_retry_shows", []) or []
    if not shows:
        print("No auto-retries needed")
        return

    print(f"Auto-dispatching recovery for: {' '.join(shows)}")

    gh_token = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")
    if not gh_token:
        print("No GH_TOKEN / GITHUB_TOKEN found in environment — cannot dispatch")
        sys.exit(0)

    failed = []
    for show in shows:
        stranded = _same_day_recovery_branch(show)
        if stranded:
            msg = (f"{show}: today's episode is STRANDED on branch {stranded} "
                   f"(pipeline succeeded and already uploaded to YouTube/R2) — "
                   f"it needs a merge, NOT a re-run. Skipping dispatch to avoid "
                   f"duplicate public uploads.")
            print(f"::warning::{msg}")
            _post_webhook(f"⚠️ Daily audit: {msg}")
            continue
        cmd = [
            "gh", "workflow", "run", "run-show.yml",
            "-f", f"show={show}",
            "--ref", "main",
        ]
        try:
            subprocess.run(cmd, check=True, capture_output=True, text=True)
            print(f"Dispatched recovery run for {show}")
        except subprocess.CalledProcessError as exc:
            print(f"Dispatch failed for {show}: {exc.stderr.strip() or exc}")
            failed.append(show)

    if failed:
        # Non-fatal: we still want the rest of the audit to complete.
        print(f"Some dispatches failed: {', '.join(failed)}")


if __name__ == "__main__":
    main()
