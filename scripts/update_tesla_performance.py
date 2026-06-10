#!/usr/bin/env python3
"""Refresh the Tesla performance tracker from OP3 audience data.

Closes the performance-feedback loop of the Tesla recursive memory
system (June 10 2026 review): ``tesla_performance_tracker.json`` had
been a hand-edited file with no automated writer, so the
``{tesla_performance_signals_block}`` injected into every digest and
podcast prompt ran on stale, static text.

Reads the per-episode download counts the nightly maintenance job
already fetches into ``api/op3_stats.json`` and rewrites the tracker's
``strong_topics_last_30d`` from the tracked-program mentions in the
most-downloaded episodes' titles. Clean no-op when the stats file is
missing or has no Tesla data (e.g. ``OP3_API_TOKEN`` unset).

Usage:
    python scripts/update_tesla_performance.py \
        [--stats api/op3_stats.json] \
        [--output-dir digests/tesla_shorts_time]
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from engine import tesla_memory  # noqa: E402

logging.basicConfig(level=logging.INFO, stream=sys.stdout,
                    format="%(levelname)s %(message)s")
logger = logging.getLogger("update_tesla_performance")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stats", default="api/op3_stats.json",
                        help="Path to the OP3 stats JSON (nightly output)")
    parser.add_argument("--output-dir", default="digests/tesla_shorts_time",
                        help="Tesla show output dir holding the trackers")
    parser.add_argument("--slug", default="tesla",
                        help="Show slug key inside the OP3 stats file")
    args = parser.parse_args()

    stats_path = ROOT / args.stats
    if not stats_path.exists():
        logger.info("No OP3 stats at %s — nothing to do (clean no-op)", stats_path)
        return 0

    try:
        stats = json.loads(stats_path.read_text(encoding="utf-8"))
    except Exception as exc:
        logger.warning("Could not parse %s: %s — skipping", stats_path, exc)
        return 0

    show_stats = (stats.get("shows") or {}).get(args.slug)
    if not show_stats:
        logger.info("No '%s' entry in OP3 stats — nothing to do", args.slug)
        return 0

    count = tesla_memory.update_performance_from_op3(
        ROOT / args.output_dir, show_stats,
    )
    logger.info("Done — %d strong topics recorded", count)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
