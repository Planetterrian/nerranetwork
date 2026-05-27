#!/usr/bin/env python3
"""Scaffold a new Nerra Network podcast show.

Example:
  python scripts/scaffold_show.py \\
    --name "Ocean Tech Weekly" \\
    --slug ocean_tech \\
    --description "Daily ocean technology and marine science news." \\
    --audience "marine researchers, ocean tech founders, and policy readers" \\
    --source "https://www.science.org/rss/news_current.xml,Science AAAS" \\
    --keyword "ocean technology" --keyword "marine science" \\
    --cron "45 10 * * *" \\
    --brand-color "#0EA5E9"

Then:
  python scripts/validate_show.py ocean_tech
  python run_show.py ocean_tech --test
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from engine.show_scaffold import ScaffoldSpec, scaffold_show  # noqa: E402


def _parse_sources(raw: list[str]) -> list[dict[str, str]]:
    out: list[dict[str, str]] = []
    for item in raw:
        if "," in item and item.startswith("http"):
            url, label = item.split(",", 1)
            out.append({"url": url.strip(), "label": label.strip()})
        elif item.startswith("http"):
            out.append({"url": item.strip(), "label": "Feed"})
        else:
            q = item.strip().replace(" ", "+")
            out.append({
                "url": (
                    f"https://news.google.com/rss/search?q={q}&hl=en-US&gl=US&ceid=US:en"
                ),
                "label": f"Google News: {item.strip()}",
            })
    return out


def main() -> int:
    p = argparse.ArgumentParser(description="Scaffold a new Nerra Network show.")
    p.add_argument("--name", required=True, help="Display name")
    p.add_argument("--slug", required=True, help="YAML slug (snake_case)")
    p.add_argument("--description", required=True, help="One-paragraph show description")
    p.add_argument("--audience", required=True, help="Who listens?")
    p.add_argument("--prefix", default="", help="Episode file prefix (default: auto)")
    p.add_argument("--brand-color", default="#6B47FF")
    p.add_argument("--emoji", default="🎙️")
    p.add_argument("--schedule", default="Daily", help="Label for website (Daily, Weekdays, …)")
    p.add_argument("--weekly-recap", action="store_true", default=True)
    p.add_argument("--no-weekly-recap", action="store_false", dest="weekly_recap")
    p.add_argument("--min-articles-skip", type=int, default=3)
    p.add_argument("--source", action="append", default=[], dest="sources",
                   help="URL, or 'URL,Label', or plain topic for Google News RSS")
    p.add_argument("--keyword", action="append", default=[], dest="keywords")
    p.add_argument("--web-search", action="append", default=[], dest="web_search")
    p.add_argument("--image-query", action="append", default=[], dest="image_queries")
    p.add_argument("--cron", default="", help="Cron expression for run-show.yml")
    p.add_argument("--cron-filter", default=None,
                   choices=["even", "odd", "odd_weekday", "weekday"],
                   help="Day filter for CRON_MAP")
    p.add_argument("--related-show", default="omni_view")
    p.add_argument("--dry-run", action="store_true")
    args = p.parse_args()

    spec = ScaffoldSpec(
        show_name=args.name,
        slug=args.slug,
        description=args.description,
        audience=args.audience,
        episode_prefix=args.prefix,
        brand_color=args.brand_color,
        emoji=args.emoji,
        schedule_label=args.schedule,
        weekly_recap=args.weekly_recap,
        min_articles_skip=args.min_articles_skip,
        sources=_parse_sources(args.sources),
        keywords=args.keywords,
        web_search_queries=args.web_search or [
            f"{args.name} news today",
            f"{args.slug.replace('_', ' ')} latest",
        ],
        image_queries=args.image_queries,
        cron=args.cron,
        cron_day_filter=args.cron_filter,
        related_show=args.related_show,
    )

    try:
        lines = scaffold_show(ROOT, spec, dry_run=args.dry_run)
    except (ValueError, FileExistsError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    for line in lines:
        print(line)

    # Item 6: automated onboarding hint (builds on the registration patch already emitted)
    print("\n" + "=" * 60)
    print("Item 6 (onboarding automation): To turn this into a PR:")
    print(f"  git checkout -b add-show-{spec.slug}")
    print("  # (scaffold already created the files + printed the registration patch above)")
    print("  git add shows/ scripts/ digests/ templates/ .github/workflows/")
    print(f"  git commit -m 'feat(shows): scaffold new show {spec.slug} ({spec.show_name})'")
    print("  # Then push + open PR with the registration patch from the output as description body.")
    print("=" * 60)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
