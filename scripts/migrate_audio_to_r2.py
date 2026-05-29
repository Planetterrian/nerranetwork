#!/usr/bin/env python3
"""Migrate existing podcast MP3s from git to Cloudflare R2.

Usage:
    python scripts/migrate_audio_to_r2.py                # Dry run (default)
    python scripts/migrate_audio_to_r2.py --execute       # Actually upload + update RSS

Reads R2 credentials from environment variables:
    R2_ENDPOINT_URL, R2_ACCESS_KEY_ID, R2_SECRET_ACCESS_KEY

Reads the public base URL from show YAML configs (storage.public_base_url).
"""

from __future__ import annotations

import argparse
import os
import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from dotenv import load_dotenv  # noqa: E402
load_dotenv(PROJECT_ROOT / ".env")


# RSS feeds and their show slugs
RSS_FEEDS = [
    ("podcast.rss", "tesla"),
    ("omni_view_podcast.rss", "omni_view"),
    ("fascinating_frontiers_podcast.rss", "fascinating_frontiers"),
    ("planetterrian_podcast.rss", "planetterrian"),
    ("env_intel_podcast.rss", "env_intel"),
    ("models_agents_podcast.rss", "models_agents"),
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Migrate MP3s from git to R2.")
    parser.add_argument("--execute", action="store_true",
                        help="Actually upload files and update RSS (default is dry run)")
    return parser.parse_args()


def _find_mp3_path(enclosure_url: str) -> Path | None:
    """Resolve a raw.githubusercontent.com URL to a local file path."""
    # URL pattern: https://raw.githubusercontent.com/.../main/digests/file.mp3
    match = re.search(r"/main/(.+\.mp3)", enclosure_url)
    if match:
        rel_path = match.group(1)
        local = PROJECT_ROOT / rel_path
        if local.exists():
            return local
    return None


def migrate(execute: bool = False) -> None:
    from engine.config import load_config
    from engine.storage import upload_to_r2

    endpoint = os.getenv("R2_ENDPOINT_URL", "").strip()
    access_key = os.getenv("R2_ACCESS_KEY_ID", "").strip()
    secret_key = os.getenv("R2_SECRET_ACCESS_KEY", "").strip()

    if execute and not all([endpoint, access_key, secret_key]):
        print("ERROR: R2 credentials not set. Set R2_ENDPOINT_URL, "
              "R2_ACCESS_KEY_ID, R2_SECRET_ACCESS_KEY in .env")
        sys.exit(1)

    total_files = 0
    total_uploaded = 0
    total_skipped = 0
    total_missing = 0

    for rss_filename, show_slug in RSS_FEEDS:
        rss_path = PROJECT_ROOT / rss_filename
        if not rss_path.exists():
            print(f"  SKIP: {rss_filename} not found")
            continue

        config_path = PROJECT_ROOT / "shows" / f"{show_slug}.yaml"
        if not config_path.exists():
            print(f"  SKIP: config not found for {show_slug}")
            continue

        config = load_config(config_path)
        bucket = config.storage.bucket
        public_base_url = config.storage.public_base_url

        print(f"\n=== {config.name} ({rss_filename}) ===")

        tree = ET.parse(str(rss_path))
        root = tree.getroot()
        channel = root.find("channel")
        if channel is None:
            print("  ERROR: No <channel> found in RSS")
            continue

        items = channel.findall("item")
        print(f"  Episodes: {len(items)}")

        modified = False
        for item in items:
            enclosure = item.find("enclosure")
            if enclosure is None:
                continue

            url = enclosure.get("url", "")
            if not url.endswith(".mp3"):
                continue

            total_files += 1

            # Already migrated?
            if public_base_url and public_base_url in url:
                total_skipped += 1
                continue

            local_path = _find_mp3_path(url)
            if local_path is None:
                print(f"  MISSING: {url}")
                total_missing += 1
                continue

            remote_key = f"{show_slug}/{local_path.name}"
            new_url = f"{public_base_url.rstrip('/')}/{remote_key}" if public_base_url else url

            if execute:
                print(f"  UPLOAD: {local_path.name} → r2://{bucket}/{remote_key}")
                upload_to_r2(
                    local_path, remote_key,
                    bucket=bucket,
                    endpoint_url=endpoint,
                    access_key=access_key,
                    secret_key=secret_key,
                    public_base_url=public_base_url,
                )
                enclosure.set("url", new_url)
                modified = True
                total_uploaded += 1
            else:
                print(f"  WOULD UPLOAD: {local_path.name} → {remote_key}")
                total_uploaded += 1

        if execute and modified:
            tree.write(str(rss_path), encoding="unicode", xml_declaration=True)
            print(f"  RSS updated: {rss_path}")

    print(f"\n{'EXECUTED' if execute else 'DRY RUN'} Summary:")
    print(f"  Total MP3 references: {total_files}")
    print(f"  {'Uploaded' if execute else 'Would upload'}: {total_uploaded}")
    print(f"  Already migrated: {total_skipped}")
    print(f"  Missing locally: {total_missing}")


if __name__ == "__main__":
    args = parse_args()
    migrate(execute=args.execute)
