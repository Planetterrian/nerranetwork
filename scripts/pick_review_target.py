#!/usr/bin/env python3
"""Pick the next target for the automated show-review agent.

Reads docs/reviews/review_state.yaml (the rotation ROSTER + seed dates)
and prints the least-recently-reviewed target slug (ties broken
alphabetically, so the choice is deterministic). Targets with an in-flight
review PR are passed via --exclude so the same show isn't reviewed twice
while the operator considers the first PR.

July 21 2026: the effective last-reviewed date is the NEWER of the state
file's seed date and the latest entry date in the target's ledger
(docs/reviews/ledger/<slug>.yaml). Review PRs previously advanced the
shared state file themselves, and any two concurrently-open review PRs
conflicted on that block every time (PRs #845/#856). The ledger entry each
PR already carries IS the rotation advance — merging the PR advances the
rotation with no shared-file write. review_state.yaml only needs editing
when a show is added to (or removed from) the rotation.

Ledger dates are read by regex, not yaml.safe_load — three committed
ledgers contain unquoted ": " inside list items and must never be
reserialized (see CLAUDE.md, review-agent section).

Exit codes: 0 = slug printed, 2 = no eligible target (all excluded).

Usage:
    python scripts/pick_review_target.py
    python scripts/pick_review_target.py --exclude tesla network
"""

import argparse
import re
import sys
from pathlib import Path

import yaml

DEFAULT_STATE = Path(__file__).resolve().parents[1] / "docs" / "reviews" / "review_state.yaml"

_LEDGER_DATE_RE = re.compile(r"^\s*-\s*date:\s*['\"]?(\d{4}-\d{2}-\d{2})['\"]?\s*$", re.M)


def _latest_ledger_date(ledger_dir: Path, slug: str) -> str:
    """Newest entry date in the slug's ledger, or "" when absent."""
    path = ledger_dir / f"{slug}.yaml"
    if not path.exists():
        return ""
    dates = _LEDGER_DATE_RE.findall(path.read_text(encoding="utf-8"))
    return max(dates) if dates else ""


def pick_target(state_path: Path, excludes: set[str],
                ledger_dir: Path | None = None) -> str | None:
    if ledger_dir is None:
        ledger_dir = state_path.parent / "ledger"
    data = yaml.safe_load(state_path.read_text(encoding="utf-8"))
    targets = data.get("targets") or {}
    candidates = {
        slug: max(str(last_reviewed), _latest_ledger_date(ledger_dir, slug))
        for slug, last_reviewed in targets.items()
        if slug not in excludes
    }
    if not candidates:
        return None
    # ISO dates sort correctly as strings; alphabetical slug tie-break.
    return min(candidates.items(), key=lambda kv: (kv[1], kv[0]))[0]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--state", type=Path, default=DEFAULT_STATE)
    parser.add_argument("--exclude", nargs="*", default=[])
    args = parser.parse_args()

    slug = pick_target(args.state, set(args.exclude))
    if slug is None:
        print("no eligible review target (all excluded)", file=sys.stderr)
        return 2
    print(slug)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
