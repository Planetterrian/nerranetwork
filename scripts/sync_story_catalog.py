#!/usr/bin/env python3
"""Copy the content lake's aired items and story ids to the story catalog,
and write the catalog readout (Oct 21 2026).

Run after ``scripts/backfill_content_lake.py`` has rebuilt the lake. Steps:

1. ``--full`` copies every episode, item, story, claim and correction; the
   default copies the last ``--days`` days (the nightly heal for any runtime
   write a show run missed).
2. ``--prune`` deletes unaired articles older than 90 days.
3. ``--report`` writes ``api/story_catalog.json``: what the network aired and
   how its stories spread over the last seven days (from the lake, always),
   the stories three or more outlets carried that no show aired (from the
   catalog, null when it is not configured), and every recent correction with
   the OTHER episodes that told the same story.

Unconfigured (no Supabase credentials) is a clean no-op for steps 1-2; the
report is still written with the catalog-only fields null, never 0.

Usage:
    python scripts/sync_story_catalog.py --report
    python scripts/sync_story_catalog.py --full --prune --report
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import logging
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

logger = logging.getLogger("sync_story_catalog")

REPORT_PATH = ROOT / "api" / "story_catalog.json"
WINDOW_DAYS = 7
TOP_N = 15


def build_report(today: dt.date, *, db_path=None, missed=None, catalog_ok: bool = False) -> dict:
    from engine import content_lake
    from engine.corrections import load_corrections

    kwargs = {"db_path": db_path} if db_path else {}
    start = (today - dt.timedelta(days=WINDOW_DAYS - 1)).isoformat()
    items = [i for i in content_lake.query_items(start, today.isoformat(), **kwargs)
             if i.get("kind") != "essay" and i.get("story_id")]
    by_story = defaultdict(list)
    for i in items:
        by_story[i["story_id"]].append(i)

    def _story(sid, members):
        return {"story_id": sid, "title": members[0]["title"],
                "days": len({m["date"] for m in members}),
                "shows": sorted({m["show_slug"] for m in members}),
                "first": members[0]["date"], "last": members[-1]["date"],
                "items": len(members)}

    multi_show = sorted((_story(s, m) for s, m in by_story.items()
                         if len({x["show_slug"] for x in m}) > 1),
                        key=lambda s: (-len(s["shows"]), -s["days"], s["title"]))
    developing = sorted((_story(s, m) for s, m in by_story.items()
                         if len({x["date"] for x in m}) >= 3),
                        key=lambda s: (-s["days"], -len(s["shows"]), s["title"]))

    # A show's retell share: its items whose story it had already aired on an
    # earlier day of the window.
    retell = {}
    per_show = defaultdict(list)
    for i in items:
        per_show[i["show_slug"]].append(i)
    for show, its in sorted(per_show.items()):
        seen_day = {}
        retold = 0
        for i in its:
            first = seen_day.setdefault(i["story_id"], i["date"])
            if first < i["date"]:
                retold += 1
        retell[show] = {"items": len(its), "retold": retold,
                        "retold_pct": round(100 * retold / len(its), 1) if its else None}

    # Corrections and the other episodes that told the same story.
    from engine.catalog import _show_dirs
    dirs = _show_dirs()
    corr_out = []
    since_c = (today - dt.timedelta(days=30)).isoformat()
    for slug, d in sorted(dirs.items()):
        for c in load_corrections(d):
            if str(c["date"]) < since_c:
                continue
            ep_items = [i for i in content_lake.query_items("2000-01-01", today.isoformat(),
                                                             show_slug=slug, **kwargs)
                        if i["episode_num"] == int(c["episode"]) and i.get("story_id")]
            from engine.catalog import correction_items
            sids = {i["story_id"] for i in correction_items(c, ep_items)}
            others = []
            for sid in sorted(sids):
                for m in content_lake.story_timeline(sid, **kwargs):
                    if (m["show_slug"], m["episode_num"]) != (slug, int(c["episode"])):
                        others.append({"show": m["show_slug"], "episode": m["episode_num"],
                                       "date": m["date"], "title": m["title"]})
            corr_out.append({"show": slug, "episode": int(c["episode"]), "date": str(c["date"]),
                             "where": c.get("where") or "", "same_story_elsewhere": others[:10]})

    stats = content_lake.get_lake_stats(**kwargs)
    return {
        "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "window_days": WINDOW_DAYS,
        "lake": {"episodes": stats.get("total_episodes"),
                 "items_in_window": len(items), "stories_in_window": len(by_story)},
        "stories_told_by_several_shows": multi_show[:TOP_N],
        "stories_told_on_three_or_more_days": developing[:TOP_N],
        "retell_by_show": retell,
        "corrections_30d": corr_out,
        "catalog_configured": catalog_ok,
        # Null when the catalog cannot be read — never an empty list that
        # reads as "nothing was missed".
        "missed_stories": missed,
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--full", action="store_true", help="Copy the whole lake")
    ap.add_argument("--days", type=int, default=3, help="Days to copy without --full")
    ap.add_argument("--prune", action="store_true", help="Delete unaired articles past retention")
    ap.add_argument("--report", action="store_true", help=f"Write {REPORT_PATH.relative_to(ROOT)}")
    ap.add_argument("--dry-run", action="store_true", help="Count, write nothing to the catalog")
    args = ap.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    from engine import catalog

    today = dt.date.today()
    ok = catalog.configured()
    if not ok:
        print("::notice::Story catalog not configured (no Supabase credentials) — "
              "copy skipped; the report is written from the lake only.")
    try:
        since = "" if args.full else (today - dt.timedelta(days=args.days)).isoformat()
        counts = catalog.sync_from_lake(full=args.full, since=since, dry_run=args.dry_run)
        logger.info("Catalog sync%s: %s", " (dry run)" if args.dry_run else "", counts)
        if args.prune and ok and not args.dry_run:
            catalog.prune_unaired()
    except Exception as exc:  # noqa: BLE001 — loud, but the report still runs
        print(f"::warning::Story catalog sync failed: {exc}")
        ok = False

    if args.report:
        missed = None
        if ok:
            try:
                missed = catalog.missed_stories(today)[:TOP_N]
            except Exception as exc:  # noqa: BLE001
                print(f"::warning::Missed-stories read failed: {exc}")
        report = build_report(today, missed=missed, catalog_ok=ok)
        REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
        REPORT_PATH.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n",
                               encoding="utf-8")
        logger.info("Wrote %s (%d multi-show stories, %s missed)", REPORT_PATH,
                    len(report["stories_told_by_several_shows"]),
                    "n/a" if missed is None else len(missed))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
