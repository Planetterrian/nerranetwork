#!/usr/bin/env python3
"""Ping all podcast directories for all Nerra Network shows.

Usage:
    python scripts/ping_directories.py              # ping every show feed
    python scripts/ping_directories.py tesla        # ping only Tesla Shorts Time
"""
import sys
import pathlib
import yaml

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
from engine.publisher import notify_directories

SHOWS_DIR = pathlib.Path("shows")
BASE_URL = "https://nerranetwork.com"


def main():
    show_filter = sys.argv[1] if len(sys.argv) > 1 else None

    for cfg_path in sorted(SHOWS_DIR.glob("*.yaml")):
        cfg = yaml.safe_load(cfg_path.read_text())
        pub = cfg.get("publishing", {})
        rss_file = pub.get("rss_file")
        rss_title = pub.get("rss_title", cfg_path.stem)

        if not rss_file:
            continue
        if show_filter and show_filter not in cfg_path.stem:
            continue

        rss_url = f"{BASE_URL}/{rss_file}"
        print(f"\n{'='*60}")
        print(f"Pinging directories for: {rss_title}")
        print(f"RSS: {rss_url}")
        print(f"{'='*60}")

        results = notify_directories(rss_url, rss_title)
        for service, ok in results.items():
            status = "OK" if ok else "FAILED"
            print(f"  {service}: {status}")


if __name__ == "__main__":
    main()
