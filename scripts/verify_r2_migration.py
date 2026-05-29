#!/usr/bin/env python3
"""Verify that all podcast RSS enclosure URLs return valid audio.

Usage:
    python scripts/verify_r2_migration.py

Checks each <enclosure> URL in all podcast RSS feeds:
- HTTP HEAD request (follows redirects)
- Expects 200 status and audio/mpeg content type
- Reports broken links
"""

from __future__ import annotations

import sys
import xml.etree.ElementTree as ET
from pathlib import Path

import requests

PROJECT_ROOT = Path(__file__).resolve().parent.parent

RSS_FEEDS = [
    "podcast.rss",
    "omni_view_podcast.rss",
    "fascinating_frontiers_podcast.rss",
    "planetterrian_podcast.rss",
    "env_intel_podcast.rss",
    "models_agents_podcast.rss",
    "models_agents_beginners_podcast.rss",
    "finansy_prosto_podcast.rss",
    "privet_russian_podcast.rss",
    "modern_investing_podcast.rss",
    "unintended_consequences_podcast.rss",
    "network.rss",
]


def verify() -> int:
    total = 0
    ok = 0
    broken = 0
    errors: list[str] = []

    for rss_filename in RSS_FEEDS:
        rss_path = PROJECT_ROOT / rss_filename
        if not rss_path.exists():
            print(f"  SKIP: {rss_filename} not found")
            continue

        print(f"\n=== {rss_filename} ===")
        tree = ET.parse(str(rss_path))
        items = tree.getroot().findall(".//item")

        for item in items:
            enclosure = item.find("enclosure")
            if enclosure is None:
                continue

            url = enclosure.get("url", "")
            if not url:
                continue

            total += 1
            title_el = item.find("title")
            title = (title_el.text if title_el is not None else "?")[:60]

            try:
                resp = requests.head(url, timeout=15, allow_redirects=True)
                content_type = resp.headers.get("Content-Type", "")

                if resp.status_code == 200 and "audio" in content_type:
                    ok += 1
                else:
                    broken += 1
                    msg = f"  BROKEN: {title} → {resp.status_code} ({content_type}) {url}"
                    print(msg)
                    errors.append(msg)
            except Exception as exc:
                broken += 1
                msg = f"  ERROR: {title} → {exc} {url}"
                print(msg)
                errors.append(msg)

    print("\n=== Summary ===")
    print(f"  Total enclosures: {total}")
    print(f"  OK: {ok}")
    print(f"  Broken: {broken}")

    if errors:
        print("\nBroken links:")
        for e in errors:
            print(e)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(verify())
