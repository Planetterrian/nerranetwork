#!/usr/bin/env python3
"""Backfill the Content Lake from existing markdown digest files.

Scans all show digest directories and imports historical episodes.

The content lake feeds cross-episode dedup, the Sunday weekly recaps, and the
global site search.  When a rebuild silently produces an empty (or near-empty)
lake — historically a quiet failure mode — those downstream features degrade
without anyone noticing.  This script now evaluates the rebuilt lake and
*fails loud*: it emits a GitHub ``::error::``/``::warning::`` annotation (visible
in the Actions UI) so the failure can't hide.  By default it does NOT block the
caller (the episode can still ship with degraded dedup); pass ``--strict`` to
exit non-zero so a dedicated maintenance job can hard-fail instead.
"""

import argparse
import logging
import re
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from engine.content_lake import (
    EpisodeRecord,
    extract_entities_and_topics,
    get_lake_stats,
    init_db,
    store_episode,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
)
logger = logging.getLogger(__name__)

SHOWS_DIR = Path("shows")

# A healthy lake holds at least a week of episodes (weekly recap needs ~7 days).
DEFAULT_WARN_BELOW = 7


def evaluate_backfill(total_episodes: int, warn_below: int = DEFAULT_WARN_BELOW) -> tuple[str, str]:
    """Classify a rebuilt lake. Returns ``(level, message)``.

    level is one of ``"ok"``, ``"warning"`` (suspiciously small), or
    ``"error"`` (empty — catastrophic). Pure function so it is unit-testable.
    """
    if total_episodes <= 0:
        return (
            "error",
            "Content lake is EMPTY after backfill — cross-episode dedup, weekly "
            "recaps, and global search will be broken. Check that committed "
            "digests/<slug>/*.md exist and content_lake init succeeded.",
        )
    if total_episodes < warn_below:
        return (
            "warning",
            f"Content lake has only {total_episodes} episodes after backfill "
            f"(expected >= {warn_below}). Recaps/search may be thin.",
        )
    return ("ok", f"Content lake healthy: {total_episodes} episodes.")


def _annotate(level: str, message: str) -> None:
    """Emit a GitHub Actions annotation (no-op-friendly elsewhere) + log."""
    if level == "error":
        print(f"::error::{message}", flush=True)
        logger.error(message)
    elif level == "warning":
        print(f"::warning::{message}", flush=True)
        logger.warning(message)
    else:
        logger.info(message)


def extract_episode_info(filepath: Path) -> dict | None:
    """Extract episode number and date from digest filename."""
    match = re.search(r"_Ep(\d+)_(\d{8})", filepath.stem)
    if match:
        return {
            "episode_num": int(match.group(1)),
            "date": datetime.strptime(match.group(2), "%Y%m%d").strftime("%Y-%m-%d"),
        }
    return None


def extract_hook_from_digest(text: str) -> str:
    """Extract the HOOK line from a digest."""
    # Try explicit HOOK marker
    match = re.search(r"\*\*HOOK:\*\*\s*(.+)", text)
    if match:
        return match.group(1).strip()
    # Try [HOOK: ...] pattern
    match = re.search(r"\[HOOK:\s*(.+?)\]", text)
    if match:
        return match.group(1).strip()
    # Fallback: first bold line of reasonable length
    match = re.search(r"\*\*(.{20,100})\*\*", text)
    return match.group(1).strip() if match else ""


def main(argv=None):
    parser = argparse.ArgumentParser(description="Backfill the Content Lake from committed digests.")
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Exit non-zero when the rebuilt lake is empty or below the warn threshold.",
    )
    parser.add_argument(
        "--warn-below",
        type=int,
        default=DEFAULT_WARN_BELOW,
        help=f"Warn (or fail under --strict) when fewer than N episodes land (default {DEFAULT_WARN_BELOW}).",
    )
    args = parser.parse_args(argv)

    init_db()

    total_imported = 0

    for config_path in sorted(SHOWS_DIR.glob("*.yaml")):
        try:
            from engine.config import load_config
            cfg = load_config(str(config_path))
        except Exception as e:
            logger.warning("Failed to load %s: %s", config_path, e)
            continue

        show_slug = config_path.stem
        show_name = getattr(cfg.publishing, "rss_title", show_slug)
        output_dir = Path(cfg.episode.output_dir)
        lang = "ru" if show_slug in ("finansy_prosto", "privet_russian") else "en"

        if not output_dir.exists():
            logger.info("No digest directory for %s, skipping", show_slug)
            continue

        # Find all markdown digest files
        md_files = sorted(output_dir.glob("*.md"))
        logger.info("\n%s: Found %d digest files in %s", show_slug, len(md_files), output_dir)

        for md_file in md_files:
            if "_tts" in md_file.stem:
                continue

            info = extract_episode_info(md_file)
            if not info:
                logger.debug("  Skipping %s (can't parse episode info)", md_file.name)
                continue

            digest_text = md_file.read_text(errors="replace")
            hook = extract_hook_from_digest(digest_text)
            entities_topics = extract_entities_and_topics(digest_text, show_slug)

            # Check for corresponding TTS script
            tts_file = md_file.parent / (md_file.stem + "_tts.txt")
            script_text = ""
            if tts_file.exists():
                script_text = tts_file.read_text(errors="replace")

            record = EpisodeRecord(
                show_slug=show_slug,
                episode_num=info["episode_num"],
                date=info["date"],
                title=hook or f"Episode {info['episode_num']}",
                hook=hook,
                digest_md=digest_text,
                podcast_script=script_text,
                summary=digest_text[:500],
                headlines=[],
                source_urls=[],
                entities=entities_topics["entities"],
                topics=entities_topics["topics"],
                word_count=len(digest_text.split()),
                show_name=show_name,
                language=lang,
            )

            store_episode(record)
            total_imported += 1

    stats = get_lake_stats()
    logger.info("\n%s", "=" * 60)
    logger.info("BACKFILL COMPLETE")
    logger.info("Total episodes imported: %d", total_imported)
    logger.info("Content Lake stats: %d episodes, %s words",
                stats["total_episodes"], f"{stats['total_words']:,}")
    for show, info in stats.get("per_show", {}).items():
        logger.info("  %s: %d episodes (%s to %s)",
                    show, info["count"], info["earliest"], info["latest"])

    # Fail-loud evaluation: surface an empty/thin lake so it can't hide.
    level, message = evaluate_backfill(stats.get("total_episodes", 0), args.warn_below)
    _annotate(level, message)
    if args.strict and level in ("error", "warning"):
        return 1
    if level == "error" and not args.strict:
        # Loud but non-blocking by default so an episode still ships with
        # (degraded) dedup rather than being blocked by a lake rebuild.
        logger.error("Continuing despite empty lake (use --strict to hard-fail).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
