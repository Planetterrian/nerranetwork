#!/usr/bin/env python3
"""Generate monthly 'State of...' reports for Nerra Network shows."""

import argparse
import logging
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from engine.synthesizer import synthesize_monthly_report

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
)
logger = logging.getLogger(__name__)

SHOWS = [
    "tesla", "omni_view", "fascinating_frontiers", "planetterrian",
    "env_intel", "models_agents", "models_agents_beginners",
    "finansy_prosto", "modern_investing", "privet_russian",
    "unintended_consequences",
]


def main():
    parser = argparse.ArgumentParser(description="Generate monthly reports")
    parser.add_argument("--show", type=str, help="Specific show slug (default: all)")
    parser.add_argument("--month", type=int, default=date.today().month, help="Month number")
    parser.add_argument("--year", type=int, default=date.today().year, help="Year")
    parser.add_argument("--output-dir", type=str, default="outputs/monthly_reports")
    args = parser.parse_args()

    shows = [args.show] if args.show else SHOWS
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    for show_slug in shows:
        logger.info("Generating monthly report: %s (%d-%02d)", show_slug, args.year, args.month)

        report_md = synthesize_monthly_report(show_slug, args.month, args.year)
        if not report_md:
            logger.warning("  Skipped %s (insufficient data)", show_slug)
            continue

        filename = f"{show_slug}_monthly_{args.year}-{args.month:02d}.md"
        (output_dir / filename).write_text(report_md, encoding="utf-8")
        logger.info("  Saved: %s", output_dir / filename)


if __name__ == "__main__":
    main()
