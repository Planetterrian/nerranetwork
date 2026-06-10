#!/usr/bin/env python3
"""Preflight check for YouTube Data API quota before a run.

Landmine #20: the @NerraNetwork channel has a 10,000 unit/day quota and each
``videos.insert`` costs 1,600 units.  Enabling YouTube on a third daily show
tips the network over quota, after which uploads fail *silently* and the
operator finds out hours later.

This script sums the estimated daily quota for every show with
``youtube.enabled: true`` and emits a loud GitHub annotation when the projected
total exceeds the daily budget.  By default it only warns (never blocks an
episode); pass ``--strict`` to exit non-zero so a guard job can hard-fail.

Run it as a cheap preflight step in CI, or locally:

    python scripts/youtube_quota_preflight.py
    python scripts/youtube_quota_preflight.py --strict
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from engine.youtube_quota import (  # noqa: E402
    DEFAULT_DAILY_QUOTA,
    estimate_network_daily_units,
    format_quota_warning,
)

SHOWS_DIR = Path(__file__).resolve().parent.parent / "shows"


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="YouTube quota preflight.")
    parser.add_argument("--strict", action="store_true", help="Exit non-zero when over quota.")
    parser.add_argument("--daily-quota", type=int, default=DEFAULT_DAILY_QUOTA)
    parser.add_argument("--shows-dir", type=Path, default=SHOWS_DIR)
    args = parser.parse_args(argv)

    summary = estimate_network_daily_units(args.shows_dir, daily_quota=args.daily_quota)

    slugs = ", ".join(summary["enabled_slugs"]) or "(none)"
    print(
        f"YouTube-enabled shows: {slugs} | projected {summary['total_units']} "
        f"units/day across all channels",
        flush=True,
    )
    # Quota is per channel (@NerraNetwork = en, @NerraRU = ru) — print
    # one line per channel so the headroom that matters is visible.
    for ch, entry in sorted((summary.get("per_channel") or {}).items()):
        ch_slugs = ", ".join(entry["enabled_slugs"]) or "(none)"
        print(
            f"  channel '{ch}': {entry['total_units']} units/day "
            f"({ch_slugs}) vs quota {entry['daily_quota']} "
            f"(headroom {entry['headroom_units']})",
            flush=True,
        )

    if summary["over_quota"]:
        warning = format_quota_warning(summary) or "YouTube quota exceeded."
        print(f"::error::{warning}", flush=True)
        return 1 if args.strict else 0

    # Soft heads-up when headroom drops under one more episode's worth.
    if 0 <= summary["headroom_units"] < 1600:
        print(
            f"::warning::YouTube quota headroom is only {summary['headroom_units']} "
            "units — enabling another show would exceed the daily budget.",
            flush=True,
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
