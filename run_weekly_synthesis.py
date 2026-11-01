#!/usr/bin/env python3
"""Weekly synthesis — generate newsletters, reports, and cross-show briefings.

Runs once per week (Sunday) to produce derivative content from the Content Lake:
  - Per-show weekly newsletters (for shows with newsletter.enabled)
  - Network-wide cross-show briefing
  - Monthly report (on first Sunday of the month)

Usage:
    python run_weekly_synthesis.py                  # All shows
    python run_weekly_synthesis.py --show tesla     # Single show
    python run_weekly_synthesis.py --cross-show     # Cross-show briefing only
    python run_weekly_synthesis.py --dry-run        # Preview without sending
"""

from __future__ import annotations

import argparse
import datetime
import logging
import sys
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT_ROOT))
load_dotenv(PROJECT_ROOT / ".env")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger("weekly_synthesis")


def _discover_shows() -> list[str]:
    shows_dir = PROJECT_ROOT / "shows"
    return [
        p.stem for p in sorted(shows_dir.glob("*.yaml"))
        if not p.stem.startswith("_")
    ]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run weekly content synthesis.")
    parser.add_argument("--show", help="Run synthesis for a single show")
    parser.add_argument("--cross-show", action="store_true", help="Generate cross-show briefing only")
    parser.add_argument("--monthly", action="store_true", help="Force monthly report generation")
    parser.add_argument("--dry-run", action="store_true", help="Preview without sending newsletters")
    return parser.parse_args()


def run_show_weekly(show_slug: str, *, dry_run: bool = False) -> None:
    """Generate and optionally send a weekly newsletter for one show."""
    from engine.config import load_config
    from engine.synthesizer import synthesize_weekly_newsletter

    config_path = PROJECT_ROOT / "shows" / f"{show_slug}.yaml"
    if not config_path.exists():
        logger.warning("Config not found for %s — skipping", show_slug)
        return

    config = load_config(config_path)
    today = datetime.date.today()
    start_date = today - datetime.timedelta(days=7)

    logger.info("Generating weekly newsletter for %s (%s to %s)", config.name, start_date, today)

    newsletter_md = synthesize_weekly_newsletter(show_slug, start_date, today, config_path=config_path)
    if not newsletter_md:
        logger.info("No episodes found for %s this week — skipping", config.name)
        return

    # Save to file
    output_dir = PROJECT_ROOT / config.episode.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)
    weekly_path = output_dir / f"weekly_{today:%Y%m%d}.md"
    weekly_path.write_text(newsletter_md, encoding="utf-8")
    logger.info("Weekly newsletter saved: %s (%d chars)", weekly_path.name, len(newsletter_md))

    # Send via Buttondown if newsletter is enabled and not dry-run
    # Nov 1 2026: an English show's week is in the Sunday Nerra Daily email;
    # only a ``delivery: own`` show (the Russian shows) sends a weekly here.
    own = (getattr(config.newsletter, "delivery", "own") or "own").strip() == "own"
    if config.newsletter.enabled and own and not dry_run:
        from engine.newsletter import send_show_newsletter
        email_id = send_show_newsletter(
            newsletter_md, config,
            episode_num=0,  # Weekly digest, not a specific episode
            date_str=f"Week of {start_date:%B %d} - {today:%B %d, %Y}",
        )
        if email_id:
            logger.info("Weekly newsletter sent: %s", email_id)
    elif dry_run:
        logger.info("[DRY RUN] Would send newsletter for %s", config.name)


def run_cross_show_briefing(*, dry_run: bool = False) -> None:
    """Generate a cross-show network briefing."""
    from engine.synthesizer import synthesize_cross_show_briefing

    today = datetime.date.today()
    start_date = today - datetime.timedelta(days=7)

    logger.info("Generating cross-show briefing (%s to %s)", start_date, today)

    briefing_md = synthesize_cross_show_briefing(start_date, today)
    if not briefing_md:
        logger.info("Insufficient episodes for cross-show briefing — skipping")
        return

    output_path = PROJECT_ROOT / "digests" / f"network_weekly_{today:%Y%m%d}.md"
    output_path.write_text(briefing_md, encoding="utf-8")
    logger.info("Cross-show briefing saved: %s (%d chars)", output_path.name, len(briefing_md))


def run_monthly_report(show_slug: str) -> None:
    """Generate a monthly report for a show."""
    from engine.synthesizer import synthesize_monthly_report

    today = datetime.date.today()
    # Previous month
    first_of_month = today.replace(day=1)
    last_month_end = first_of_month - datetime.timedelta(days=1)
    last_month_start = last_month_end.replace(day=1)

    logger.info("Generating monthly report for %s (%s to %s)", show_slug, last_month_start, last_month_end)

    report_md = synthesize_monthly_report(show_slug, last_month_start, last_month_end)
    if not report_md:
        logger.info("Insufficient episodes for monthly report — skipping")
        return

    output_dir = PROJECT_ROOT / "digests" / show_slug
    output_dir.mkdir(parents=True, exist_ok=True)
    report_path = output_dir / f"monthly_{last_month_start:%Y%m}.md"
    report_path.write_text(report_md, encoding="utf-8")
    logger.info("Monthly report saved: %s", report_path.name)


def main():
    args = parse_args()
    today = datetime.date.today()

    if args.cross_show:
        run_cross_show_briefing(dry_run=args.dry_run)
        return

    shows = [args.show] if args.show else _discover_shows()

    for slug in shows:
        try:
            run_show_weekly(slug, dry_run=args.dry_run)
        except Exception as exc:
            logger.error("Weekly synthesis failed for %s: %s", slug, exc)

        # Monthly report on first Sunday of the month (or forced)
        if args.monthly or today.day <= 7:
            try:
                run_monthly_report(slug)
            except Exception as exc:
                logger.error("Monthly report failed for %s: %s", slug, exc)

    # Cross-show briefing
    try:
        run_cross_show_briefing(dry_run=args.dry_run)
    except Exception as exc:
        logger.error("Cross-show briefing failed: %s", exc)


if __name__ == "__main__":
    main()
