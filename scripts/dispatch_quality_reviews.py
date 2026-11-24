#!/usr/bin/env python3
"""Event-driven Show Review Agent dispatch for the Daily Audit workflow.

Reads api/daily-review.json (produced by review_episodes.py) and, when a
show shipped an episode with editorial-CRITICAL issues today, dispatches
`gh workflow run show-review.yml -f show=<slug>` so the review agent
investigates out of rotation — review when something breaks, not just
when the calendar says so.

Nov 24 2026 — a critical is news only against the show's own normal.
154 of 225 reviewed episodes Nov 9-23 carried an audit critical (REPETITIVE
on 135), so "any critical today" dispatched a review almost every day and
the one daily review went to noise. With the score history passed in, a
show qualifies only when its share of critical episodes over the last
``RECENT_ROWS`` exceeds its share over the ``PRIOR_ROWS`` before by
``RATE_MARGIN`` (a show with under ``MIN_PRIOR_ROWS`` of history keeps the
old rule). A page-severity MUST-HAVE miss today
(``api/show_contracts.json``, scripts/check_show_contracts.py) outranks
every critical: a missing share price is a defect the listener hears.

Deliberately conservative:
  - Missed episodes are NOT a trigger (dispatch_audit_retries.py already
    re-runs those; a missed episode needs a retry, not a review).
  - At most ONE dispatch per audit run (the show with the most criticals;
    alphabetical tie-break) to bound agent spend.
  - A show with an open agent/review-<slug>-* PR OR a pushed
    agent/review-<slug>-* branch is skipped — the existing review already
    owns that show's problems (branches without PRs happen when `gh pr
    create` is org-blocked).
  - Never fails the audit: every error path exits 0.

Lives outside the workflow YAML for the same reason as
dispatch_audit_retries.py (keeps actionlint/shellcheck quiet and testable).
"""

import json
import os
import subprocess
import sys
from pathlib import Path


RECENT_ROWS = 7
PRIOR_ROWS = 28
MIN_PRIOR_ROWS = 14
RATE_MARGIN = 0.25


def critical_rate_rise(rows: list[dict], show: str) -> float | None:
    """The show's critical-episode share over its last RECENT_ROWS audit
    rows minus the share over the PRIOR_ROWS before them; None when the
    prior window is shorter than MIN_PRIOR_ROWS."""
    mine = sorted((r for r in rows if r.get("show") == show),
                  key=lambda r: (str(r.get("date")), r.get("episode") or 0))
    recent = mine[-RECENT_ROWS:]
    prior = mine[-(RECENT_ROWS + PRIOR_ROWS):-RECENT_ROWS]
    if len(prior) < MIN_PRIOR_ROWS or not recent:
        return None

    def share(block):
        return sum(1 for r in block if (r.get("critical") or 0) > 0) / len(block)
    return share(recent) - share(prior)


def contract_page_shows(contracts: dict | None) -> dict[str, int]:
    """``{show: page-severity misses today}`` from api/show_contracts.json."""
    out: dict[str, int] = {}
    for slug, entry in ((contracts or {}).get("shows") or {}).items():
        n = sum(1 for ep in entry.get("today", []) for c in ep.get("checks", [])
                if c.get("ok") is False and c.get("severity") == "page")
        if n:
            out[slug] = n
    return out


def pick_review_candidate(data: dict, history: list[dict] | None = None,
                          contracts: dict | None = None) -> str | None:
    """The single show most deserving an out-of-rotation review, or None.

    A page-severity must-have miss today wins. Otherwise counts editorial
    criticals from episodes that actually shipped; auto-retry (missed) shows
    are excluded; with *history* (the rows of
    api/editorial_score_history.json) a show must ALSO be above its own
    critical rate by RATE_MARGIN.
    """
    retried = set(data.get("remediation", {}).get("auto_retry_shows", []) or [])
    paged = {s: n for s, n in contract_page_shows(contracts).items() if s not in retried}
    if paged:
        return min(paged.items(), key=lambda kv: (-kv[1], kv[0]))[0]
    criticals: dict[str, int] = {}
    for episode in data.get("episodes", []) or []:
        show = episode.get("show")
        count = episode.get("critical", 0) or 0
        if show and count > 0 and show not in retried:
            criticals[show] = criticals.get(show, 0) + count
    if history is not None:
        for show in list(criticals):
            rise = critical_rate_rise(history, show)
            if rise is not None and rise < RATE_MARGIN:
                del criticals[show]
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


def _remote_review_branch_exists(slug: str) -> bool:
    """A pushed agent/review-<slug>-* branch counts as a review in flight even
    with no PR: `gh pr create` is blocked in some org configs, so review runs
    land as orphan branches — the open-PR-only dedupe then re-dispatched the
    same show repeatedly (FF 4x, Jun 26 - Jul 1 2026)."""
    result = subprocess.run(
        ["git", "ls-remote", "--heads", "origin",
         f"refs/heads/agent/review-{slug}-*"],
        check=True, capture_output=True, text=True,
    )
    return bool(result.stdout.strip())


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

    history = None
    try:
        history = json.loads(Path("api/editorial_score_history.json")
                             .read_text()).get("rows")
    except Exception as exc:  # a missing history keeps the old rule
        print(f"No score history ({exc}) — dispatching on any critical")
    contracts = None
    try:
        contracts = json.loads(Path("api/show_contracts.json").read_text())
    except Exception:
        pass
    slug = pick_review_candidate(data, history, contracts)
    if not slug:
        print("No must-have miss and no show above its own critical rate "
              "— no review dispatch needed")
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

    try:
        if _remote_review_branch_exists(slug):
            print(f"{slug}: review branch agent/review-{slug}-* already pushed "
                  f"(PR creation may be org-blocked) — skipping dispatch")
            return
    except subprocess.CalledProcessError as exc:
        print(f"Could not list remote review branches "
              f"({exc.stderr.strip() or exc}) — skipping dispatch")
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
