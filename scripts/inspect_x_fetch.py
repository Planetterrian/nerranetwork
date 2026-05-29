#!/usr/bin/env python3
"""Inspect X fetch results for a show — diagnostic tool.

Usage:
    python scripts/inspect_x_fetch.py tesla
    python scripts/inspect_x_fetch.py tesla --verbose

Shows which posts come back from each X account, what was dropped
(no URL, keyword filter), and the final relevance scores.
"""

import argparse
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from engine.config import load_config


def main():
    parser = argparse.ArgumentParser(description="Inspect X fetch for a show")
    parser.add_argument("show_slug", help="Show slug (e.g. tesla, omni_view)")
    parser.add_argument("--verbose", "-v", action="store_true", help="Show DEBUG logs")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(levelname)s %(message)s",
    )

    cfg = load_config(f"shows/{args.show_slug}.yaml")
    x_accounts = getattr(cfg, "x_accounts", []) or []

    if not x_accounts:
        print(f"No x_accounts configured for show '{args.show_slug}'.")
        return

    print(f"\n{'='*60}")
    print(f"X Fetch Inspection: {args.show_slug}")
    print(f"Accounts: {len(x_accounts)}")
    keywords = getattr(cfg, "keywords", []) or []
    print(f"Keywords: {len(keywords)} ({', '.join(keywords[:8])}{'...' if len(keywords) > 8 else ''})")
    print(f"{'='*60}\n")

    from engine.fetcher import fetch_x_posts

    posts = fetch_x_posts(x_accounts, keywords=keywords)

    if not posts:
        print("\n  ** No posts returned. Check logs above for errors. **\n")
        return

    by_author = {}
    for p in posts:
        author = p.get("author", "unknown")
        by_author.setdefault(author, []).append(p)

    print(f"\nTotal posts: {len(posts)}")
    print("By account:")
    for author, author_posts in sorted(by_author.items()):
        print(f"  {author}: {len(author_posts)} posts")

    print(f"\n{'─'*60}")
    for i, p in enumerate(posts, 1):
        score = p.get("relevance_score", 0.0)
        url = p.get("url", "???")
        title = p.get("title", "")[:100]
        desc = (p.get("description", "") or "")[:100]
        author = p.get("author", "?")
        source = p.get("source_name", "?")

        has_status = "/status/" in url
        url_flag = "" if has_status else " ⚠️ NO STATUS URL"

        print(f"\n  [{i}] {author} (score={score}){url_flag}")
        print(f"      Title:  {title}")
        print(f"      Text:   {desc}")
        print(f"      URL:    {url}")
        print(f"      Source: {source}")

    print(f"\n{'='*60}")
    print("Done.\n")


if __name__ == "__main__":
    main()
