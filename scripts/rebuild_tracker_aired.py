#!/usr/bin/env python3
"""Re-record each show's content tracker as what AIRED (one-time repair).

Until Oct 21 2026 every tracker day held the whole prompt list (up to 60
articles) as "covered": its URLs blocked the show's prompts for 45 days and
its titles fed the ALREADY-COVERED notes and the hook gate, though 63-75% of
them never aired. ``ContentTracker.record_episode`` now records what aired;
this script rewrites the days already on disk the same way, from each day's
committed digest:

* ``headlines`` / ``urls`` become the digest's aired stories
  (``engine.aired_items``) plus its section-pattern headlines;
* the old URLs the digest does not cite move to ``listed_urls``;
* a day with no committed digest aired nothing, so all its URLs are listed;
* ``sections``, quote authors, deep-dive topics and slow-news fields are kept.

``run_show`` applies the same migration (``ContentTracker.migrate_to_aired``)
the first time it loads an unmigrated tracker, so this script is a dry-run
instrument and a manual repair; it never needs to run before a show.

Dry run by default; ``--apply`` writes. Idempotent.

Usage:
    python scripts/rebuild_tracker_aired.py
    python scripts/rebuild_tracker_aired.py --show tesla --apply
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

logger = logging.getLogger("rebuild_tracker_aired")

def rebuild_show(slug: str, show_dir: Path, section_patterns: dict, *, apply: bool,
                 force: bool = False) -> dict:
    from engine.content_tracker import ContentTracker

    tracker = ContentTracker(slug, show_dir)
    if not tracker.tracker_file.is_file():
        return {}
    tracker.data = json.loads(tracker.tracker_file.read_text(encoding="utf-8"))
    if force:
        tracker.data.pop("aired_schema", None)
    eps = tracker.data.get("episodes", [])
    before_u = sum(len(e.get("urls", [])) for e in eps)
    before_h = sum(len(e.get("headlines", [])) for e in eps)
    changed = tracker.migrate_to_aired(section_patterns)
    after_u = sum(len(e.get("urls", [])) for e in eps)
    after_h = sum(len(e.get("headlines", [])) for e in eps)
    if apply and changed:
        tracker.tracker_file.write_text(
            json.dumps(tracker.data, indent=2, ensure_ascii=False), encoding="utf-8")
    return {"days": len(eps), "urls_before": before_u, "urls_after": after_u,
            "headlines_before": before_h, "headlines_after": after_h, "migrated": changed}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--show", help="One show slug (default: every show)")
    ap.add_argument("--apply", action="store_true", help="Write the trackers")
    ap.add_argument("--force", action="store_true",
                    help="Rebuild a tracker that is already marked aired-only")
    args = ap.parse_args()
    logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(message)s")

    from engine.config import load_config
    from engine.content_tracker import SHOW_SECTION_PATTERNS

    for yml in sorted((ROOT / "shows").glob("*.yaml")):
        if yml.name.startswith("_"):
            continue
        if args.show and yml.stem != args.show:
            continue
        try:
            config = load_config(yml)
        except Exception as exc:  # noqa: BLE001 — not a show config
            logger.debug("skip %s: %s", yml.name, exc)
            continue
        show_dir = ROOT / config.episode.output_dir
        patterns = (config.content_tracking.section_patterns
                    or SHOW_SECTION_PATTERNS.get(config.slug, {}))
        report = rebuild_show(config.slug, show_dir, patterns, apply=args.apply, force=args.force)
        if report:
            print(f"{config.slug:28} days={report['days']:3} "
                  f"urls {report['urls_before']:5} -> {report['urls_after']:5}  "
                  f"headlines {report['headlines_before']:5} -> {report['headlines_after']:5}")
    if not args.apply:
        print("Dry run. Re-run with --apply to write.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
