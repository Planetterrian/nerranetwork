#!/usr/bin/env python3
"""Read YouTube Analytics back into the network — the recursive-feedback loop.

The pipeline uploads long-form + Shorts every day and records each in
``api/youtube_videos.json`` (``engine.youtube_index``) but never read the
*performance* back. This closes that loop, mirroring ``fetch_op3_stats.py``
for the audio side:

* ``api/youtube_stats.json`` — per-show + per-video views, watch-time, and
  **average view percentage** (the retention signal — the strongest
  content-quality lever YouTube exposes via the public API). The operator
  dashboard reads it; ``scripts/update_youtube_performance.py`` turns it
  into the per-show "what's working" guidance injected into prompts.

The video→episode map is read from every show's own
``digests/<slug>/youtube_videos.json`` (per-show to avoid the concurrent
push-contention a shared index would cause — see ``engine.youtube_index``).

Clean no-op when YouTube credentials are unset OR the stored token lacks
the ``yt-analytics.readonly`` scope (logs one line, exits 0, leaves any
previously committed output untouched) — same convention as every optional
integration here.

**Operator one-time setup:** the analytics scope was added to
``engine.youtube.YOUTUBE_SCOPES`` in June 2026, so the refresh token must be
re-authorised once (re-run ``scripts/youtube_oauth_bootstrap.py`` and
re-consent) before this returns data. Uploads keep working on the old token;
only this read no-ops until then. See ``docs/youtube_feedback_loop.md``.

YouTube Analytics API v2 (https://developers.google.com/youtube/analytics):
``reports.query`` with ``ids=channel==MINE``, ``dimensions=video``,
``filters=video==<id1>,<id2>,...`` (≤500 ids/query), metrics
``views,estimatedMinutesWatched,averageViewDuration,averageViewPercentage``.
Impressions / click-through are Studio-only and intentionally omitted.

Usage::

    python scripts/fetch_youtube_analytics.py                  # write the file
    python scripts/fetch_youtube_analytics.py --dry-run        # print, no write
    python scripts/fetch_youtube_analytics.py --days 30        # window (default 90)
    python scripts/fetch_youtube_analytics.py --index api/youtube_videos.json
"""

from __future__ import annotations

import argparse
import datetime as _dt
import json
import logging
import sys
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Optional

_SCRIPT_DIR = Path(__file__).resolve().parent
_ROOT = _SCRIPT_DIR.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

logging.basicConfig(level=logging.INFO, stream=sys.stdout,
                    format="%(levelname)s %(message)s")
logger = logging.getLogger("fetch_youtube_analytics")

_METRICS = [
    "views",
    "estimatedMinutesWatched",
    "averageViewDuration",
    "averageViewPercentage",
]
# Analytics API allows up to 500 ids in a single video== filter.
_BATCH = 200


def _load_index(digests_dir: Path) -> List[dict]:
    """Collect rows from every ``digests/<slug>/youtube_videos.json``."""
    files = sorted(digests_dir.glob("*/youtube_videos.json"))
    if not files:
        logger.info("No per-show video indexes under %s — nothing to fetch "
                    "(clean no-op)", digests_dir)
        return []
    rows: List[dict] = []
    for f in files:
        # The output dir name is the canonical key (slug != dir for some
        # shows, e.g. tesla → digests/tesla_shorts_time); the updater writes
        # the perf file back into this same dir.
        dir_name = f.parent.name
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
            for v in data.get("videos", []):
                if v.get("video_id"):
                    v = dict(v)
                    v["_dir"] = dir_name
                    rows.append(v)
        except Exception as exc:
            logger.warning("Could not parse %s: %s — skipping", f, exc)
    return rows


def _analytics_service(credentials):
    """Build the youtubeAnalytics v2 client; None if libs/creds unusable."""
    try:
        from googleapiclient.discovery import build
    except Exception as exc:  # pragma: no cover - import guard
        logger.info("googleapiclient unavailable (%s) — skipping", exc)
        return None
    try:
        return build("youtubeAnalytics", "v2", credentials=credentials,
                     cache_discovery=False)
    except Exception as exc:
        logger.warning("Could not build analytics service: %s", exc)
        return None


def _query_batch(service, video_ids: List[str], start: str, end: str) -> Dict[str, dict]:
    """Return {video_id: {metric: value}} for a batch of ids. {} on error."""
    try:
        resp = service.reports().query(
            ids="channel==MINE",
            startDate=start,
            endDate=end,
            metrics=",".join(_METRICS),
            dimensions="video",
            filters="video==" + ",".join(video_ids),
            maxResults=len(video_ids),
        ).execute()
    except Exception as exc:
        msg = str(exc)
        if "insufficient" in msg.lower() or "scope" in msg.lower() or "403" in msg:
            logger.warning(
                "Analytics query rejected (likely missing yt-analytics.readonly "
                "scope — re-auth needed): %s", msg[:200],
            )
        else:
            logger.warning("Analytics query failed: %s", msg[:200])
        return {}
    out: Dict[str, dict] = {}
    headers = [h["name"] for h in resp.get("columnHeaders", [])]
    for row in resp.get("rows", []) or []:
        record = dict(zip(headers, row))
        vid = record.pop("video", None)
        if vid:
            out[vid] = record
    return out


def fetch(digests_dir: Path, days: int) -> Optional[dict]:
    """Build the stats payload, or None if there is nothing to do."""
    videos = _load_index(digests_dir)
    if not videos:
        return None

    try:
        from engine.youtube import get_channel_credentials_from_env
    except Exception as exc:
        logger.info("engine.youtube unavailable (%s) — skipping", exc)
        return None

    today = _dt.date.today()
    start = (today - _dt.timedelta(days=days)).isoformat()
    end = today.isoformat()

    # Group video ids by channel (each channel needs its own token).
    by_channel: Dict[str, List[dict]] = defaultdict(list)
    for v in videos:
        by_channel[(v.get("channel") or "en").lower()].append(v)

    metrics_by_video: Dict[str, dict] = {}
    any_data = False
    for channel, rows in by_channel.items():
        creds = get_channel_credentials_from_env(channel)
        if creds is None:
            logger.info("No credentials for channel=%s — skipped", channel)
            continue
        service = _analytics_service(creds)
        if service is None:
            continue
        ids = [r["video_id"] for r in rows]
        for i in range(0, len(ids), _BATCH):
            batch = ids[i:i + _BATCH]
            got = _query_batch(service, batch, start, end)
            if got:
                any_data = True
            metrics_by_video.update(got)

    if not any_data:
        logger.info("No analytics returned (no scope / no data yet) — no-op")
        return None

    # Assemble per-show structure for the updater + dashboard. Keyed by the
    # show's output-dir name (where the updater writes the perf file back).
    shows: Dict[str, dict] = defaultdict(lambda: {"videos": []})
    for v in videos:
        m = metrics_by_video.get(v["video_id"])
        if not m:
            continue
        shows[v["_dir"]]["videos"].append({
            "video_id": v["video_id"],
            "show_slug": v.get("show_slug", ""),
            "episode": v.get("episode"),
            "kind": v.get("kind"),
            "title": v.get("title", ""),
            "hook": v.get("hook", ""),
            "published": v.get("published", ""),
            "views": int(float(m.get("views", 0) or 0)),
            "estimated_minutes_watched": float(m.get("estimatedMinutesWatched", 0) or 0),
            "average_view_duration_s": float(m.get("averageViewDuration", 0) or 0),
            "average_view_percentage": float(m.get("averageViewPercentage", 0) or 0),
        })

    return {
        "schema_version": 1,
        "generated": _dt.datetime.now(_dt.timezone.utc).isoformat(),
        "window_days": days,
        "shows": shows,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--digests", default="digests",
                        help="Directory holding per-show output dirs")
    parser.add_argument("--out", default="api/youtube_stats.json")
    parser.add_argument("--days", type=int, default=90)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    payload = fetch(_ROOT / args.digests, args.days)
    if payload is None:
        return 0

    n_videos = sum(len(s["videos"]) for s in payload["shows"].values())
    logger.info("Fetched analytics for %d videos across %d shows",
                n_videos, len(payload["shows"]))
    if args.dry_run:
        print(json.dumps(payload, indent=2, ensure_ascii=False)[:4000])
        return 0

    out_path = _ROOT / args.out
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    logger.info("Wrote %s", out_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
