"""Generate the weekly cross-network intelligence briefing.

Calls ``engine.synthesizer.synthesize_cross_show_briefing`` for the
week ending today (or the date supplied via ``--week-ending``) and
writes the resulting markdown to
``outputs/cross_network/cross_network_briefing_<YYYY-WWW>.md``.

The Sunday newsletter workflow runs this after the per-show weekly
newsletters land. The briefing is the editorial synthesis the
``_build_cross_network_data`` newsletter module currently doesn't
produce — surfaces threads no single-show coverage would catch
("AI x energy", "regulatory move ripples across 3 shows", etc.).

Usage:
    python scripts/run_cross_network_briefing.py
    python scripts/run_cross_network_briefing.py --week-ending 2026-05-04
    python scripts/run_cross_network_briefing.py --dry-run
"""

from __future__ import annotations

import argparse
import logging
import sys
from datetime import date, datetime
from pathlib import Path

# Allow running from repo root.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    stream=sys.stdout,
)
logger = logging.getLogger("cross_network_briefing")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--week-ending",
        help="ISO date (YYYY-MM-DD) for the week ending. Defaults to today.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Generate but do not write the file.",
    )
    args = parser.parse_args()

    if args.week_ending:
        try:
            week_ending = datetime.strptime(args.week_ending, "%Y-%m-%d").date()
        except ValueError:
            logger.error("Invalid --week-ending; expected YYYY-MM-DD")
            return 2
    else:
        week_ending = date.today()

    from engine.synthesizer import synthesize_cross_show_briefing
    text = synthesize_cross_show_briefing(week_ending)

    if not text:
        logger.warning(
            "Cross-network briefing returned empty (likely <10 episodes "
            "in window). Skipping write.",
        )
        return 0

    out_dir = Path(__file__).resolve().parent.parent / "outputs" / "cross_network"
    out_dir.mkdir(parents=True, exist_ok=True)
    iso_year, iso_week, _ = week_ending.isocalendar()
    out_path = out_dir / f"cross_network_briefing_{iso_year}-W{iso_week:02d}.md"

    if args.dry_run:
        logger.info(
            "DRY RUN — would write %d chars to %s", len(text), out_path,
        )
        print(text[:500] + ("..." if len(text) > 500 else ""))
        return 0

    out_path.write_text(text, encoding="utf-8")
    logger.info("Cross-network briefing written: %s (%d chars)", out_path, len(text))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
