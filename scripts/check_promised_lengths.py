#!/usr/bin/env python3
"""Warn when a public string promises an episode length the show does not
deliver (Nov 3 2026).

Reads every show's ``rss_description`` (show YAML), ``description_long`` /
``about_text`` and typed ``episode_length`` (the registry) and compares each
stated length with the median audio of the show's last 14 committed
episodes (``engine.cadence``). A stated length more than 25% from that
median prints a ``::warning::`` annotation. It NEVER fails: a check that
reads today's committed data must tolerate today, and the fix is the
operator's (a per-show yes to ``engine.cadence.COMPUTED_LENGTH_SHOWS``, or
new copy).

Usage: python scripts/check_promised_lengths.py
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def main() -> int:
    try:
        from engine.cadence import LENGTH_DRIFT_TOLERANCE, length_drift_report
        report = length_drift_report(ROOT)
    except Exception as exc:  # noqa: BLE001 — a warning check never fails the job
        print(f"::warning::Promised-length check could not run: {exc}")
        return 0
    if not report:
        print("Promised episode lengths: every stated length is within "
              f"{int(100 * LENGTH_DRIFT_TOLERANCE)}% of what the show delivers.")
        return 0
    for row in report:
        fix = ("add the show to engine.cadence.COMPUTED_LENGTH_SHOWS on the "
               "operator's yes" if row["field"] == "episode_length"
               else "the copy is the operator's to change")
        print(
            f"::warning::{row['show']} {row['field']} promises \"{row['phrase']}\" "
            f"but its last 14 episodes ran a median {row['median_min']} min "
            f"({row['off_pct']}% off) — {fix}."
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
