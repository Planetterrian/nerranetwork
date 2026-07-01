#!/usr/bin/env python3
"""Turn YouTube analytics into per-show 'what's working' guidance.

Second half of the recursive YouTube-feedback loop: reads the analytics
``scripts/fetch_youtube_analytics.py`` wrote to ``api/youtube_stats.json``
and distils, per show, the angles/keywords that earned the best *retention*
(average view percentage — the strongest content-quality signal YouTube
exposes) into ``digests/<slug>/youtube_performance.json``.

The title generator (``engine.youtube_titles._performance_hint``) reads that
file and steers future titles toward what's landing. The signal is
TITLE-ONLY (visual metadata, no audio) so it sits outside the landmine #17
A/B-listen gate — the recursive improvement is safe to run automatically.

Clean no-op when ``api/youtube_stats.json`` is missing or empty (the loop is
dormant until the operator re-auths the analytics scope and data accrues).

Usage::

    python scripts/update_youtube_performance.py [--stats api/youtube_stats.json]
"""

from __future__ import annotations

import argparse
import datetime as _dt
import json
import logging
import re
import sys
from collections import Counter
from pathlib import Path
from typing import Dict, List

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

logging.basicConfig(level=logging.INFO, stream=sys.stdout,
                    format="%(levelname)s %(message)s")
logger = logging.getLogger("update_youtube_performance")

# Need a few videos before retention numbers mean anything.
_MIN_VIDEOS = 4
# Content words to ignore when mining recurring keywords from titles.
_STOP = frozenset({
    "the", "a", "an", "and", "or", "but", "of", "to", "in", "on", "for",
    "with", "at", "by", "from", "as", "is", "are", "was", "this", "that",
    "how", "why", "what", "new", "now", "you", "your", "ep", "episode",
    "daily", "show", "could", "will", "can", "vs", "its",
})


def _keywords(text: str) -> List[str]:
    toks = re.findall(r"[A-Za-z0-9][A-Za-z0-9'-]{2,}", (text or ""))
    return [t for t in toks if t.lower() not in _STOP]


def _build_hint(videos: List[dict]) -> str:
    """Compose a short natural-language steer from the best performers.

    EN-channel rows only (rows without a ``channel`` predate the field and
    are all EN): the title hint feeds the ENGLISH title generator, and mixing
    in @NerraRU dub retention skews the median and can quote Russian titles
    as exemplars in English prompts."""
    rated = [v for v in videos
             if v.get("average_view_percentage")
             and (v.get("channel") or "en").lower() == "en"]
    if len(rated) < _MIN_VIDEOS:
        return ""
    rated.sort(key=lambda v: v.get("average_view_percentage", 0), reverse=True)
    top = rated[: max(3, len(rated) // 4)]  # top quartile (min 3)
    median_pct = sorted(v["average_view_percentage"] for v in rated)[len(rated) // 2]

    # Recurring keywords across the high-retention titles + hooks.
    counter: Counter = Counter()
    for v in top:
        for kw in _keywords(v.get("title", "")) + _keywords(v.get("hook", "")):
            counter[kw.lower()] += 1
    common = [w for w, c in counter.most_common(8) if c >= 2]

    parts: List[str] = []
    if common:
        parts.append(
            "Topics/keywords that retained best recently: "
            + ", ".join(common[:8]) + "."
        )
    # Show the operator/LLM 2-3 concrete high-retention titles as exemplars.
    examples = [v["title"] for v in top[:3] if v.get("title")]
    if examples:
        parts.append("Highest-retention titles so far: "
                     + " | ".join(f'"{t}"' for t in examples) + ".")
    parts.append(
        f"Median retention is {median_pct:.0f}% — beat it: keep the promise "
        "concrete and front-load the strongest entity."
    )
    return " ".join(parts)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stats", default="api/youtube_stats.json")
    args = parser.parse_args()

    stats_path = ROOT / args.stats
    if not stats_path.exists():
        logger.info("No YouTube stats at %s — nothing to do (clean no-op)",
                    stats_path)
        return 0
    try:
        shows: Dict[str, dict] = (
            json.loads(stats_path.read_text(encoding="utf-8")).get("shows") or {}
        )
    except Exception as exc:
        logger.warning("Could not parse %s: %s — skipping", stats_path, exc)
        return 0

    written = 0
    # Keys are the show output-dir names (e.g. "tesla_shorts_time"), so the
    # perf file lands next to that show's index file.
    for dir_name, payload in shows.items():
        videos = payload.get("videos") or []
        hint = _build_hint(videos)
        if not hint:
            logger.info("%s: too few rated videos (%d) — skipped",
                        dir_name, len(videos))
            continue
        out_dir = ROOT / "digests" / dir_name
        if not out_dir.exists():
            logger.info("%s: no output dir — skipped", dir_name)
            continue
        out = {
            "schema_version": 1,
            "generated": _dt.datetime.now(_dt.timezone.utc).isoformat(),
            "video_count": len(videos),
            "title_hint": hint,
        }
        (out_dir / "youtube_performance.json").write_text(
            json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        written += 1
        logger.info("%s: wrote youtube_performance.json", dir_name)

    logger.info("Updated YouTube performance for %d show(s)", written)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
