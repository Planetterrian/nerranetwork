#!/usr/bin/env python3
"""Automated remediation for the Daily Audit workflow.

Reads api/daily-review.json (produced by review_episodes.py) and dispatches
`gh workflow run run-show.yml` for any shows listed under
`remediation.auto_retry_shows`.

This script exists so the complex shell + heredoc logic lives outside the
workflow YAML. This completely avoids noisy SC2086 reports from actionlint's
embedded shellcheck when processing large `run: |` blocks.
"""

import json
import os
import subprocess
import sys
from pathlib import Path


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
