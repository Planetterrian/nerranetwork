#!/usr/bin/env python3
"""Event-driven Show Review Agent dispatch for the Daily Audit workflow.

Reads api/daily-review.json (produced by review_episodes.py) and, when a
show shipped an episode with editorial-CRITICAL issues today, dispatches
`gh workflow run show-review.yml -f show=<slug>` so the review agent
investigates out of rotation — review when something breaks, not just
when the calendar says so.

Deliberately conservative:
  - Missed episodes are NOT a trigger (dispatch_audit_retries.py already
    re-runs those; a missed episode needs a retry, not a review).
  - At most ONE dispatch per audit run (the show with the most criticals;
    alphabetical tie-break) to bound agent spend.
  - A show with an open agent/review-<slug>-* PR is skipped — the existing
    PR already owns that show's problems.
  - Never fails the audit: every error path exits 0.

Lives outside the workflow YAML for the same reason as
dispatch_audit_retries.py (keeps actionlint/shellcheck quiet and testable).
"""

import json
import os
import subprocess
import sys
from pathlib import Path


def pick_review_candidate(data: dict) -> str | None:
    """The single show most deserving an out-of-rotation review, or None.

    Counts editorial criticals from episodes that actually shipped;
    auto-retry (missed) shows are excluded.
    """
    retried = set(data.get("remediation", {}).get("auto_retry_shows", []) or [])
    criticals: dict[str, int] = {}
    for episode in data.get("episodes", []) or []:
        show = episode.get("show")
        count = episode.get("critical", 0) or 0
        if show and count > 0 and show not in retried:
            criticals[show] = criticals.get(show, 0) + count
    if not criticals:
        return None
    return min(criticals.items(), key=lambda kv: (-kv[1], kv[0]))[0]


def _open_review_branches() -> list[str]:
    result = subprocess.run(
        ["gh", "pr", "list", "--state", "open", "--json", "headRefName",
         "--jq", ".[].headRefName"],
        check=True, capture_output=True, text=True,
    )
    return [line.strip() for line in result.stdout.splitlines() if line.strip()]


def main() -> None:
    review_path = Path("api/daily-review.json")
    if not review_path.exists():
        print("No structured audit output — skipping review dispatch")
        return

    try:
        data = json.loads(review_path.read_text())
    except Exception as exc:
        print(f"Failed to parse {review_path}: {exc}")
        return

    slug = pick_review_candidate(data)
    if not slug:
        print("No editorial-critical issues today — no review dispatch needed")
        return

    if not (os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")):
        print("No GH_TOKEN / GITHUB_TOKEN in environment — cannot dispatch")
        return

    try:
        branches = _open_review_branches()
    except subprocess.CalledProcessError as exc:
        print(f"Could not list open PRs ({exc.stderr.strip() or exc}) — skipping dispatch")
        return
    if any(b.startswith(f"agent/review-{slug}-") for b in branches):
        print(f"{slug}: review PR already open — skipping dispatch")
        return

    cmd = ["gh", "workflow", "run", "show-review.yml",
           "-f", f"show={slug}", "--ref", "main"]
    try:
        subprocess.run(cmd, check=True, capture_output=True, text=True)
        print(f"Dispatched out-of-rotation review for {slug} (editorial criticals today)")
    except subprocess.CalledProcessError as exc:
        print(f"Review dispatch failed for {slug}: {exc.stderr.strip() or exc}")


if __name__ == "__main__":
    main()
    sys.exit(0)
