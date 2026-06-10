#!/usr/bin/env python3
"""Pick the next target for the automated show-review agent.

Reads docs/reviews/review_state.yaml and prints the least-recently-reviewed
target slug (ties broken alphabetically, so the choice is deterministic).
Targets with an in-flight review PR are passed via --exclude so the same
show isn't reviewed twice while the operator considers the first PR.

Exit codes: 0 = slug printed, 2 = no eligible target (all excluded).

Usage:
    python scripts/pick_review_target.py
    python scripts/pick_review_target.py --exclude tesla network
"""

import argparse
import sys
from pathlib import Path

import yaml

DEFAULT_STATE = Path(__file__).resolve().parents[1] / "docs" / "reviews" / "review_state.yaml"


def pick_target(state_path: Path, excludes: set[str]) -> str | None:
    data = yaml.safe_load(state_path.read_text(encoding="utf-8"))
    targets = data.get("targets") or {}
    candidates = {
        slug: str(last_reviewed)
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
