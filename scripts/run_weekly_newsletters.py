#!/usr/bin/env python3
"""Generate and send weekly newsletters for all Nerra Network shows."""

import argparse
import logging
import os
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from engine.content_lake import get_lake_stats
from engine.synthesizer import synthesize_weekly_newsletter

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
)
logger = logging.getLogger(__name__)

def _discover_shows() -> list:
    """Discover show slugs from YAML configs instead of hardcoding."""
    shows_dir = Path(__file__).resolve().parent.parent / "shows"
    slugs = []
    for f in sorted(shows_dir.glob("*.yaml")):
        if f.name.startswith("_") or f.name in ("pronunciation_map.yaml", "translation_overrides.yaml"):
            continue
        if f.parent.name != "shows":
            continue
        # templates directory
        if "template" in f.name:
            continue
        slugs.append(f.stem)
    return slugs


SHOWS = _discover_shows()


def sent_marker_path(output_dir: Path, show_slug: str, week_ending: date) -> Path:
    """Per-show, per-week 'already sent' marker (see the guard in main)."""
    return output_dir / f"{show_slug}_weekly_{week_ending.isoformat()}.sent.json"


def record_sent(marker: Path, *, email_id: str, subject: str) -> None:
    """Write the sent marker after a successful Buttondown send. Best-effort:
    a write failure must never turn a sent newsletter into a job error."""
    import json
    from datetime import datetime, timezone
    try:
        marker.parent.mkdir(parents=True, exist_ok=True)
        marker.write_text(json.dumps({
            "email_id": email_id,
            "subject": subject,
            "sent_at": datetime.now(timezone.utc).isoformat(),
        }, indent=2) + "\n", encoding="utf-8")
    except OSError as exc:
        logger.warning("  could not write sent marker %s: %s", marker, exc)


def main():
    parser = argparse.ArgumentParser(description="Generate weekly newsletters")
    parser.add_argument("--show", type=str, help="Specific show slug (default: all)")
    parser.add_argument("--date", type=str, help="Week ending date YYYY-MM-DD (default: today)")
    parser.add_argument("--dry-run", action="store_true", help="Generate but don't send")
    parser.add_argument("--output-dir", type=str, default="outputs/newsletters",
                        help="Save generated newsletters to this directory")
    args = parser.parse_args()

    week_ending = date.fromisoformat(args.date) if args.date else date.today()
    shows = [args.show] if args.show else SHOWS

    # Show content lake stats
    stats = get_lake_stats()
    logger.info("Content Lake: %d episodes, %s words",
                stats["total_episodes"], f"{stats['total_words']:,}")

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    results = {}
    for show_slug in shows:
        logger.info("\n%s", "=" * 60)
        logger.info("Generating weekly newsletter for: %s", show_slug)
        logger.info("Week ending: %s", week_ending)

        prompt_file = Path(f"shows/prompts/{show_slug}_weekly.txt")

        # Same-week double-send guard (Sep 6 2026). The Sunday cron has
        # been arriving hours late (or not at all) during the GitHub cron
        # outage, so the operator dispatches the workflow by hand — and a
        # late cron firing AFTER that dispatch would send every show's
        # weekly a second time. The marker is written only after a real
        # send and lives in the tracked outputs/newsletters/ directory the
        # workflow commits, so a fresh checkout sees it. The daily guard
        # (engine.newsletter._can_send_now) is 20-hour and per-DAILY send;
        # it does not know about weeklies.
        sent_marker = sent_marker_path(output_dir, show_slug, week_ending)
        if not args.dry_run and sent_marker.exists():
            logger.info("  Weekly newsletter for %s (week ending %s) already "
                        "sent — marker %s; skipping", show_slug, week_ending,
                        sent_marker.name)
            results[show_slug] = "already sent this week"
            continue

        # One show's failure must never sink the whole weekly run: on
        # 2026-08-30 first_principles' template carried a placeholder the
        # synthesizer doesn't supply (KeyError: 'episodes_block') and
        # every show after it in the loop got no newsletter that week.
        try:
            envelope = synthesize_weekly_newsletter(
                show_slug=show_slug,
                week_ending=week_ending,
                prompt_file=prompt_file if prompt_file.exists() else None,
            )
        except Exception as exc:  # noqa: BLE001 — isolate per show, stay loud
            logger.error("  Weekly newsletter CRASHED for %s: %s",
                         show_slug, exc)
            results[show_slug] = f"failed ({type(exc).__name__})"
            continue

        if not envelope or not envelope.get("body_md"):
            logger.warning("  No newsletter generated for %s", show_slug)
            results[show_slug] = "skipped"
            continue

        newsletter_md = envelope["body_md"]

        # Save the body markdown so the operator can review it before send.
        filename = f"{show_slug}_weekly_{week_ending.isoformat()}.md"
        (output_dir / filename).write_text(newsletter_md, encoding="utf-8")
        logger.info("  Saved: %s", output_dir / filename)

        if args.dry_run:
            results[show_slug] = "generated (dry run)"
            continue

        # Send via Buttondown if configured
        try:
            from engine.config import load_config
            cfg = load_config(f"shows/{show_slug}.yaml")

            newsletter_cfg = getattr(cfg, "newsletter", None)
            if not newsletter_cfg or not getattr(newsletter_cfg, "enabled", False):
                logger.info("  Newsletter not enabled for %s, skipping send", show_slug)
                results[show_slug] = "generated (not enabled)"
                continue

            api_key_env = getattr(newsletter_cfg, "api_key_env", "")
            api_key = os.environ.get(api_key_env) if api_key_env else None
            if not api_key:
                logger.warning("  No API key found for %s (%s)", show_slug, api_key_env)
                results[show_slug] = "generated (no API key)"
                continue

            from engine.newsletter import send_newsletter
            from engine.newsletter_template import (
                build_subject_line,
                compute_issue_number,
                wrap_with_branding,
            )

            issue_number = compute_issue_number(show_slug, week_ending)
            subject = build_subject_line(
                show_slug, envelope.get("subject_hook", ""),
                send_date=week_ending,
            )
            logger.info(
                "  Issue #%d / subject=%r", issue_number, subject,
            )
            tag = getattr(newsletter_cfg, "tag", "") or ""
            tags_list = [tag] if tag else None

            requires_disclaimer = bool(
                getattr(newsletter_cfg, "requires_financial_disclaimer", False)
            )

            # Wrap the synthesized markdown with the show's branded
            # hero, optional by-the-numbers strip, optional financial
            # disclaimer callout, body, P.S. block, and footer.
            # Buttondown passes inline HTML through its markdown
            # renderer untouched.
            # Deterministic Buttondown slug so the view-in-browser link
            # can point at the issue's archive page before the send
            # (June 2026 growth pass).
            from engine.newsletter import BUTTONDOWN_USERNAME
            bd_slug = (
                f"{show_slug.replace('_', '-')}-weekly-issue-{issue_number:03d}"
            )
            archive_url = (
                f"https://buttondown.com/{BUTTONDOWN_USERNAME}"
                f"/archive/{bd_slug}/"
            )

            branded_body = wrap_with_branding(
                show_slug, newsletter_md,
                week_ending=week_ending,
                preheader=envelope.get("preheader", ""),
                by_the_numbers=envelope.get("by_the_numbers") or [],
                featured_episode=envelope.get("featured_episode"),
                p_s=envelope.get("p_s", ""),
                adjacent_shows=envelope.get("cross_network") or [],
                requires_financial_disclaimer=requires_disclaimer,
                archive_url=archive_url,
            )

            email_id = send_newsletter(
                subject=subject,
                body=branded_body,
                api_key=api_key,
                status=getattr(newsletter_cfg, "status", "draft"),
                tags=tags_list,
                slug=bd_slug,
            )
            results[show_slug] = f"sent ({email_id})" if email_id else "send failed"
            if email_id:
                record_sent(sent_marker, email_id=email_id, subject=subject)
        except Exception as e:
            logger.error("  Send failed for %s: %s", show_slug, e)
            results[show_slug] = f"error: {e}"

    # Summary
    logger.info("\n%s", "=" * 60)
    logger.info("WEEKLY NEWSLETTER SUMMARY")
    for show, status in results.items():
        logger.info("  %s: %s", show, status)
    # Per-show crashes are isolated above so every show still runs, but
    # the JOB must stay red when any show crashed — otherwise a broken
    # template fails silently forever.
    failed = [s for s, st in results.items() if st.startswith("failed")]
    if failed:
        logger.error("Weekly newsletter FAILED for: %s", ", ".join(failed))
        raise SystemExit(1)


if __name__ == "__main__":
    main()
