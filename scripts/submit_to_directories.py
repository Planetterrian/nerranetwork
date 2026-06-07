#!/usr/bin/env python3
"""Submit all Nerra Network podcast RSS feeds to major directories.

Automates what can be automated (Podcast Index add-by-feed-url) and
prints instructions for manual submission (Apple Podcasts, Spotify).

Usage:
    python scripts/submit_to_directories.py [--dry-run]
"""

import argparse
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger(__name__)

BASE_URL = "https://nerranetwork.com"

# All shows with their RSS files and human-readable names
SHOWS = [
    # Tesla uses the legacy flat filename "podcast.rss" — do NOT rename this,
    # subscribers' apps are anchored to the historic feed URL.
    ("tesla", "Tesla Shorts Time", "podcast.rss"),
    ("omni_view", "Omni View", "omni_view_podcast.rss"),
    ("fascinating_frontiers", "Fascinating Frontiers", "fascinating_frontiers_podcast.rss"),
    ("planetterrian", "Planetterrian Daily", "planetterrian_podcast.rss"),
    ("env_intel", "Environmental Intelligence", "env_intel_podcast.rss"),
    ("models_agents", "Models & Agents", "models_agents_podcast.rss"),
    ("models_agents_beginners", "Models & Agents for Beginners", "models_agents_beginners_podcast.rss"),
    ("finansy_prosto", "Финансы Просто", "finansy_prosto_podcast.rss"),
    ("modern_investing", "Modern Investing Techniques", "modern_investing_podcast.rss"),
    ("privet_russian", "Привет, Русский!", "privet_russian_podcast.rss"),
    ("unintended_consequences", "Unintended Consequences", "unintended_consequences_podcast.rss"),
    ("first_principles", "First Principles Daily", "first_principles_podcast.rss"),
]


def submit_to_podcast_index(rss_url: str, show_name: str, dry_run: bool = False) -> bool:
    """Submit a feed to Podcast Index via their pubnotify endpoint."""
    import requests

    if dry_run:
        logger.info("  [DRY RUN] Would submit to Podcast Index: %s", rss_url)
        return True

    try:
        resp = requests.get(
            "https://api.podcastindex.org/api/1.0/hub/pubnotify",
            params={"url": rss_url},
            timeout=15,
        )
        if resp.status_code == 200:
            logger.info("  [OK] Podcast Index notified: %s", show_name)
            return True
        else:
            logger.warning("  [WARN] Podcast Index returned %s for %s", resp.status_code, show_name)
            return False
    except Exception as e:
        logger.warning("  [FAIL] Podcast Index: %s — %s", show_name, e)
        return False


def submit_to_pubsubhubbub(rss_url: str, show_name: str, dry_run: bool = False) -> bool:
    """Submit a feed to PubSubHubbub/WebSub hub."""
    import requests

    if dry_run:
        logger.info("  [DRY RUN] Would submit to PubSubHubbub: %s", rss_url)
        return True

    try:
        resp = requests.post(
            "https://pubsubhubbub.appspot.com/",
            data={"hub.mode": "publish", "hub.url": rss_url},
            timeout=15,
        )
        if resp.status_code == 204:
            logger.info("  [OK] PubSubHubbub notified: %s", show_name)
            return True
        else:
            logger.warning("  [WARN] PubSubHubbub returned %s for %s", resp.status_code, show_name)
            return False
    except Exception as e:
        logger.warning("  [FAIL] PubSubHubbub: %s — %s", show_name, e)
        return False


def main():
    parser = argparse.ArgumentParser(description="Submit podcasts to directories")
    parser.add_argument("--dry-run", action="store_true", help="Print what would be done")
    args = parser.parse_args()

    logger.info("=" * 70)
    logger.info("Nerra Network — Podcast Directory Submission")
    logger.info("=" * 70)

    # Automated submissions
    logger.info("\n1. AUTOMATED SUBMISSIONS (Podcast Index + PubSubHubbub)")
    logger.info("-" * 50)
    for slug, name, rss_file in SHOWS:
        rss_url = f"{BASE_URL}/{rss_file}"
        logger.info("\n%s (%s)", name, rss_url)
        submit_to_podcast_index(rss_url, name, dry_run=args.dry_run)
        submit_to_pubsubhubbub(rss_url, name, dry_run=args.dry_run)

    # Manual submission instructions
    logger.info("\n\n2. MANUAL SUBMISSIONS REQUIRED")
    logger.info("-" * 50)

    logger.info("\n--- Apple Podcasts ---")
    logger.info("Submit each RSS feed at: https://podcastsconnect.apple.com/")
    logger.info("(Requires Apple ID. One-time submission per show.)\n")
    for slug, name, rss_file in SHOWS:
        logger.info("  %s: %s/%s", name, BASE_URL, rss_file)

    logger.info("\n--- Spotify for Podcasters ---")
    logger.info("Submit each RSS feed at: https://podcasters.spotify.com/")
    logger.info("(Requires Spotify account. One-time submission per show.)\n")
    for slug, name, rss_file in SHOWS:
        logger.info("  %s: %s/%s", name, BASE_URL, rss_file)

    logger.info("\n--- YouTube Music (via RSS) ---")
    logger.info("Submit at: https://podcasts.google.com/publish")
    logger.info("(Google account required. Supports RSS submission.)\n")
    for slug, name, rss_file in SHOWS:
        logger.info("  %s: %s/%s", name, BASE_URL, rss_file)

    logger.info("\n\nDone. Automated notifications sent. Manual submissions listed above.")


if __name__ == "__main__":
    main()
