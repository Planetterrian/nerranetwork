#!/usr/bin/env python3
"""Refresh per-show performance trackers from OP3 audience data.

Closes the performance-feedback loop of the recursive memory systems
(June 10 2026 reviews): the performance trackers had no automated
writer, so the performance-signals block injected into digest/podcast
prompts ran on stale or empty text.

Covers Tesla (bespoke ``engine.tesla_memory``) plus every show
registered in ``engine.show_memory.SHOW_MEMORY_CONFIGS`` (Models &
Agents, Fascinating Frontiers, Planetterrian). Reads the per-episode
download counts the nightly maintenance job already fetches into
``api/op3_stats.json``. Clean no-op when the stats file is missing or
has no data for a show (e.g. ``OP3_API_TOKEN`` unset).

Usage:
    python scripts/update_performance_trackers.py [--stats api/op3_stats.json]
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

from engine import show_memory, tesla_memory  # noqa: E402

logging.basicConfig(level=logging.INFO, stream=sys.stdout,
                    format="%(levelname)s %(message)s")
logger = logging.getLogger("update_performance_trackers")

# slug → output dir for the bespoke Tesla module; memory shows use
# digests/<slug>/ by convention.
_TESLA_OUTPUT_DIR = "digests/tesla_shorts_time"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stats", default="api/op3_stats.json",
                        help="Path to the OP3 stats JSON (nightly output)")
    args = parser.parse_args()

    stats_path = ROOT / args.stats
    if not stats_path.exists():
        logger.info("No OP3 stats at %s — nothing to do (clean no-op)", stats_path)
        return 0

    try:
        shows = (json.loads(stats_path.read_text(encoding="utf-8"))
                 .get("shows") or {})
    except Exception as exc:
        logger.warning("Could not parse %s: %s — skipping", stats_path, exc)
        return 0

    # Tesla (bespoke module, bespoke output dir).
    tesla_stats = shows.get("tesla")
    if tesla_stats:
        tesla_memory.update_performance_from_op3(
            ROOT / _TESLA_OUTPUT_DIR, tesla_stats,
        )
    else:
        logger.info("No 'tesla' entry in OP3 stats — skipped")

    # Generalized memory shows.
    for slug, cfg in show_memory.SHOW_MEMORY_CONFIGS.items():
        show_stats = shows.get(slug)
        if not show_stats:
            logger.info("No '%s' entry in OP3 stats — skipped", slug)
            continue
        show_memory.update_performance_from_op3(
            ROOT / "digests" / slug, cfg, show_stats,
        )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
