#!/usr/bin/env python3
"""Export what the network has aired about a story or a subject (Oct 21 2026).

Reads the content lake's aired items and story ids (rebuild it first with
``scripts/backfill_content_lake.py``; no Supabase needed) and writes one
dossier: every item that told the story, oldest first, with the show,
episode, date, the item's own text, its sources and the VERIFIED claims from
that episode's ledger whose source the item cites.

What it is for (docs/story_catalog.md):

* books — themed or year-in-review volumes start from a query, not from one
  show's episode range ("the lake makes themed compilation a query",
  docs/product_opportunities_2026_08.md B6);
* members-only specials — the network's own prior coverage of a subject,
  beside (never instead of) the pages a special's research reads;
* story pages and the Beat Chronicle idea (B2) — a timeline per story;
* corrections — what else the network said about a corrected story.

Usage:
    python scripts/catalog_dossier.py --like "Starship Flight 15 catch"
    python scripts/catalog_dossier.py --story st_1a2b3c4d5e6f --json
    python scripts/catalog_dossier.py --search "wolves" --since 2026-06-01 --out wolves.md
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from engine.story_dossier import build, find_story, to_markdown  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--story", help="A story id (st_…)")
    g.add_argument("--like", help="Headline-like text; exports the best-matching story")
    g.add_argument("--search", help="Full-text query over every aired item")
    ap.add_argument("--since", default="", help="YYYY-MM-DD (search only)")
    ap.add_argument("--until", default="", help="YYYY-MM-DD (search only)")
    ap.add_argument("--show", default="", help="Limit a search to one show slug")
    ap.add_argument("--limit", type=int, default=200)
    ap.add_argument("--json", action="store_true", help="JSON instead of markdown")
    ap.add_argument("--out", default="", help="Write to this file (default: stdout)")
    args = ap.parse_args()

    from engine import content_lake

    if args.story or args.like:
        sid = args.story or find_story(args.like)
        if not sid:
            print("No story matches.", file=sys.stderr)
            return 1
        items = content_lake.story_timeline(sid)
        heading = items[0]["title"] if items else sid
    else:
        items = content_lake.search_items(args.search, limit=args.limit)
        items = [i for i in items
                 if (not args.since or i["date"] >= args.since)
                 and (not args.until or i["date"] <= args.until)
                 and (not args.show or i["show_slug"] == args.show)]
        heading = f"Nerra Network coverage: {args.search}"
    if not items:
        print("Nothing aired matches.", file=sys.stderr)
        return 1
    d = build(items, heading=heading)
    text = json.dumps(d, indent=2, ensure_ascii=False) if args.json else to_markdown(d)
    if args.out:
        Path(args.out).write_text(text, encoding="utf-8")
        print(f"Wrote {args.out} ({len(d['stories'])} stories, {len(items)} items)")
    else:
        sys.stdout.write(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
