#!/usr/bin/env python3
"""Accumulate age-matched early reach per video (Sep 12 2026).

Why this exists: on 2026-09-12 the operator read a "significant drop" off
YouTube Studio's rolling views. The channel day series said the opposite
(EN +50-60% week over week on matching weekdays) — the two numbers
disagreed because a three-day run of breakout Shorts (09-04..06) lifted
the channel, and every "current" figure is then compared against that
peak. The only honest comparison is AGE-MATCHED: views a video has at a
fixed age, compared across publish days. ``api/youtube_stats.json`` is a
rolling snapshot, so that comparison could only be made by digging old
copies out of git. This script writes the per-video views observed at
each snapshot age into ``api/youtube_early_reach.json`` nightly, so the
dashboard can show reach-at-day-3 per publish day, by channel and kind.

Contract:
* Reads the committed ``api/youtube_stats.json`` (``generated`` date G;
  per-video ``published``, ``views``, ``subscribers_gained``).
* For every video whose age ``(G - published)`` is 1..``MAX_AGE_DAYS``,
  records ``views_by_age[age]`` (first observation wins, so re-running on
  the same snapshot is a no-op).
* Prunes videos older than ``PRUNE_DAYS``.
* Never raises out of ``main`` — the nightly step is ``|| true`` and the
  file is additive.

Analytics lag: the snapshot on day G carries views through roughly G-2,
so "age 3" is about the first 24-48 h of real exposure. It is a fixed
ruler, not an absolute; compare it against itself.
"""

from __future__ import annotations

import argparse
import datetime as _dt
import json
import sys
from pathlib import Path
from typing import Any, Dict, Optional

ROOT = Path(__file__).resolve().parent.parent

MAX_AGE_DAYS = 7
PRUNE_DAYS = 60
SCHEMA_VERSION = 1


def _parse_date(s: Any) -> Optional[_dt.date]:
    try:
        return _dt.date.fromisoformat(str(s)[:10])
    except (TypeError, ValueError):
        return None


def load_reach(path: Path) -> Dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(data, dict) and isinstance(data.get("videos"), dict):
            return data
    except (OSError, ValueError):
        pass
    return {"schema_version": SCHEMA_VERSION, "updated": None, "videos": {}}


def merge_snapshot(reach: Dict[str, Any], stats: Dict[str, Any]) -> int:
    """Fold one analytics snapshot into *reach*; returns observations added."""
    gen = _parse_date(stats.get("generated"))
    if gen is None:
        return 0
    videos = reach.setdefault("videos", {})
    added = 0
    for show in (stats.get("shows") or {}).values():
        for v in show.get("videos", []) if isinstance(show, dict) else []:
            vid = v.get("video_id")
            pub = _parse_date(v.get("published"))
            if not vid or pub is None:
                continue
            age = (gen - pub).days
            if age < 1 or age > MAX_AGE_DAYS:
                continue
            rec = videos.setdefault(vid, {
                "published": pub.isoformat(),
                "channel": (v.get("channel") or "en"),
                "kind": v.get("kind") or "",
                "show": v.get("show_slug") or "",
                "window": v.get("window") or "",
                "views_by_age": {},
                "subs_by_age": {},
            })
            key = str(age)
            if key not in rec["views_by_age"]:
                rec["views_by_age"][key] = int(v.get("views") or 0)
                rec["subs_by_age"][key] = int(v.get("subscribers_gained") or 0)
                added += 1
    cutoff = (gen - _dt.timedelta(days=PRUNE_DAYS)).isoformat()
    for vid in [k for k, r in videos.items() if str(r.get("published") or "") < cutoff]:
        del videos[vid]
    last = reach.get("updated")
    if not last or str(last)[:10] <= gen.isoformat():
        reach["updated"] = gen.isoformat()
    reach["schema_version"] = SCHEMA_VERSION
    return added


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    p.add_argument("--stats", default=str(ROOT / "api" / "youtube_stats.json"))
    p.add_argument("--out", default=str(ROOT / "api" / "youtube_early_reach.json"))
    args = p.parse_args(argv)
    try:
        stats = json.loads(Path(args.stats).read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        print(f"::warning::early reach: cannot read {args.stats}: {exc}")
        return 0
    out = Path(args.out)
    reach = load_reach(out)
    added = merge_snapshot(reach, stats)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(reach, indent=1, sort_keys=True, ensure_ascii=False) + "\n",
                   encoding="utf-8")
    print(f"early reach: +{added} observations, {len(reach['videos'])} videos tracked "
          f"(snapshot {reach.get('updated')})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
