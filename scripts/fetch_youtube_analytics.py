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

Nov 3 2026: the Data API's uploads playlist is read back too
(``channels.<ch>.unindexed_recent`` — the videos the per-show indexes do not
know, with YouTube Podcasts' RSS-ingested copies attributed as ``rss_copy``),
and a retention curve is fetched for every long of the last 14 days, stamped
``curve_fetched_at``.

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
import re
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
    # July 18 2026 — the growth metric the operator actually wants to
    # move. Valid with dimensions=video in Analytics v2 (impressions/CTR
    # remain Studio-only and are still intentionally omitted).
    "subscribersGained",
    "subscribersLost",
]
# Analytics API allows up to 500 ids in a single video== filter.
_BATCH = 200

# Daily channel-level snapshot history (subscribers, total views) —
# appended once per run, deduped on (date, channel), capped so the file
# never grows unbounded.
_CHANNEL_HISTORY_PATH = "api/youtube_channel_history.json"
_CHANNEL_HISTORY_MAX_ROWS = 800

# Nov 3 2026 — the channel the repo can see. The per-show indexes carried
# 2,434 EN rows against a channel ``video_count`` of 4,822: half the
# channel was YouTube Podcasts' RSS-ingested copies ("Ep N: <hook>" at the
# render's exact duration, the square cover as the still), competing with
# the rendered long-form for the same subscribers and taking 37% of the
# first-day long views on ten visible pairs. The uploads playlist is read
# back over this many days and diffed against the indexes; a copy whose
# episode number and hook prefix match an index row is attributed to its
# show as kind ``rss_copy`` and joins the metrics batch, so its views and
# subscribers are read. Every consumer that reads the indexed kinds
# (``INDEXED_KINDS``) ignores it — the copies are counted by the dashboard's
# ``youtube_rss_copies_14d_<ch>`` and nowhere else.
UPLOADS_SINCE_DAYS = 35
INDEXED_KINDS = ("long", "short")
RSS_COPY_KIND = "rss_copy"
# The feed title shape (engine.titles.episode_title): "Ep 653: <hook>" on the
# English shows, "Выпуск 41: <hook>" on the Russian ones.
_RSS_COPY_TITLE_RE = re.compile(r"^(?:Ep|Выпуск)\s?(\d+):\s*(.*)$", re.IGNORECASE)
_HOOK_PREFIX_MIN_CHARS = 8
# The policy file read for the nightly ``::warning::`` (a show that renders
# its own long-form and still has RSS copies beside it).
_POLICY_PATH = "api/youtube_policy.json"

# Nov 3 2026 — a retention curve for EVERY long. The fetch read curves for
# the top FIVE longs per channel by views, so the file carried 37 curves
# and the spoken-open A/B ended at n = 1 per arm. Now every long published
# in the last ``RETENTION_CURVE_DAYS`` is queried (newest first, at most
# ``RETENTION_CURVE_MAX`` a night across the channels — one Analytics
# query each, on the Analytics API's own quota), plus the channel's top
# ``RETENTION_CURVE_SHORTS_TOP`` Shorts by views for the hook-Short readouts
# (a Short's 5% point is ~1.6 s; never pooled with the longs). A curve is
# stamped ``curve_fetched_at`` so a carried-forward one is never read as
# fresh, and a failed curve never joins ``_FAILED_QUERIES`` (it is
# informational, like the traffic-source day series).
RETENTION_CURVE_DAYS = 14
RETENTION_CURVE_MAX = 150
RETENTION_CURVE_SHORTS_TOP = 20


def _load_index(digests_dir: Path) -> List[dict]:
    """Collect rows from every per-show video index — the EN channel
    (``youtube_videos.json``) AND every dubbed channel
    (``youtube_videos.<lang>.json``). Each row carries its own ``channel``
    field, so the fetch groups them onto the right channel token; without
    the dub files the analytics loop was EN-only.

    The language files are matched by PATTERN rather than listed. When
    @NerraFR went live (2026-07-23) it published 39 videos that this
    fetch never saw, because only ``.ru.json`` had been added alongside
    the base index. Everything downstream inherited the blind spot: the
    adaptive policy computed ``video_count_14d = 0`` for all four FR
    shows and froze them at their seed tier — a channel that could never
    earn a promotion no matter how well it performed — and the title
    hints, subscriber attribution and gallery-retention join were all
    equally blind. A glob costs nothing and cannot be forgotten again.
    """
    files = sorted(digests_dir.glob("*/youtube_videos.json"))
    files += sorted(digests_dir.glob("*/youtube_videos.*.json"))
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


# Sep 17 2026: the Analytics API answered HTTP 500 to most of the 09-16
# nightly's queries (13 video batches + the day series on all three
# channels, over ~25 s). Each failure was swallowed as an empty result,
# so a snapshot with a third of the videos and NO day series overwrote a
# healthy file and every downstream instrument (policy, scorecard,
# early-reach card, register metrics) read zeros for a day. Two guards:
# a short retry on 5xx here, and a refuse-to-overwrite check in main()
# (`snapshot_regression`). A transient server error is retried; a 403 /
# scope problem is not (it never fixes itself in five seconds).
_RETRY_SLEEPS_S = (2.0, 5.0)
_FAILED_QUERIES: List[str] = []


def _is_server_error(exc: Exception) -> bool:
    status = getattr(getattr(exc, "resp", None), "status", None)
    try:
        if status is not None and int(status) >= 500:
            return True
    except (TypeError, ValueError):
        pass
    low = str(exc).lower()
    return any(t in low for t in ("http 500", "httperror 500", "returned \"an internal error",
                                  "http 502", "httperror 502", "http 503", "httperror 503",
                                  "backend error", "internal error has occurred"))


def _execute_with_retry(build_request, what: str):
    """Run ``build_request().execute()``; retry a 5xx twice with short sleeps.

    Raises the last exception so callers keep their own classification.
    """
    import time as _time
    attempt = 0
    while True:
        try:
            return build_request().execute()
        except Exception as exc:  # noqa: BLE001
            if attempt < len(_RETRY_SLEEPS_S) and _is_server_error(exc):
                logger.warning("%s: server error (attempt %d) — retrying in %.0fs: %s",
                               what, attempt + 1, _RETRY_SLEEPS_S[attempt], str(exc)[:120])
                _time.sleep(_RETRY_SLEEPS_S[attempt])
                attempt += 1
                continue
            raise


def _query_batch(service, video_ids: List[str], start: str, end: str) -> Dict[str, dict]:
    """Return {video_id: {metric: value}} for a batch of ids. {} on error."""
    try:
        resp = _execute_with_retry(lambda: service.reports().query(
            ids="channel==MINE",
            startDate=start,
            endDate=end,
            metrics=",".join(_METRICS),
            dimensions="video",
            filters="video==" + ",".join(video_ids),
            maxResults=len(video_ids),
        ), "video batch")
    except Exception as exc:
        _FAILED_QUERIES.append(f"video batch ({len(video_ids)} ids)")
        msg = str(exc)
        low = msg.lower()
        # Distinguish the two common 403s so the operator doesn't re-auth
        # when the real fix is enabling the Analytics API in GCP (July 2026
        # nightly log: "YouTube Analytics API has not been used in project
        # … or it is disabled" was mis-labelled as a scope problem).
        if "has not been used" in low or "is disabled" in low or "accessnotconfigured" in low:
            logger.warning(
                "Analytics query rejected — enable YouTube Analytics API v2 "
                "in the Google Cloud project (APIs & Services → Library → "
                "YouTube Analytics API), then wait a few minutes: %s",
                msg[:220],
            )
        elif "insufficient" in low or "scope" in low or "access_denied" in low:
            logger.warning(
                "Analytics query rejected — refresh token lacks "
                "yt-analytics.readonly; revoke the app at "
                "myaccount.google.com/permissions and re-run "
                "scripts/youtube_oauth_bootstrap.py: %s",
                msg[:220],
            )
        elif "403" in msg:
            logger.warning(
                "Analytics query rejected (HTTP 403 — check API enablement "
                "and OAuth scopes): %s", msg[:220],
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


# Demographics window. 28 days to match what YouTube Studio's own
# Audience tab shows, so a number here can be checked against the app.
_DEMO_DAYS = 28
# The video filter accepts a bounded id list; keep well under the API's
# limit so a big channel doesn't 400 the whole report.
_DEMO_FILTER_MAX = 200


def _viewer_percentages(service, start: str, end: str,
                        video_ids: Optional[List[str]] = None) -> List[dict]:
    """Age x gender split as ``viewerPercentage`` rows.

    Percentages cover SIGNED-IN viewers only and sum to 100 across the
    whole matrix — YouTube reports no absolute counts here. Passing
    *video_ids* restricts the report to those videos, which is how the
    Shorts-vs-long-form split is produced (the API has no "Shorts"
    dimension; our own index knows which is which).

    Returns [] on any failure — demographics are a reporting nicety and
    must never take down the nightly analytics fetch.
    """
    params = dict(
        ids="channel==MINE", startDate=start, endDate=end,
        metrics="viewerPercentage", dimensions="ageGroup,gender",
    )
    if video_ids:
        params["filters"] = "video==" + ",".join(video_ids[:_DEMO_FILTER_MAX])
    try:
        resp = service.reports().query(**params).execute()
    except Exception as exc:  # noqa: BLE001
        logger.info("demographics query skipped (%s): %s",
                    "filtered" if video_ids else "channel", str(exc)[:160])
        return []
    headers = [h["name"] for h in resp.get("columnHeaders", [])]
    out = []
    for row in resp.get("rows", []) or []:
        rec = dict(zip(headers, row))
        try:
            pct = float(rec.get("viewerPercentage") or 0.0)
        except (TypeError, ValueError):
            continue
        out.append({
            # "age25-34" -> "25-34"; leave anything unexpected alone.
            "age": str(rec.get("ageGroup", "")).replace("age", ""),
            "gender": str(rec.get("gender", "")),
            "pct": round(pct, 3),
        })
    return out


def _geography(service, start: str, end: str, limit: int = 25) -> List[dict]:
    """Top viewing countries by views. [] on any failure."""
    try:
        resp = service.reports().query(
            ids="channel==MINE", startDate=start, endDate=end,
            metrics="views,estimatedMinutesWatched", dimensions="country",
            sort="-views", maxResults=limit,
        ).execute()
    except Exception as exc:  # noqa: BLE001
        logger.info("geography query skipped: %s", str(exc)[:160])
        return []
    headers = [h["name"] for h in resp.get("columnHeaders", [])]
    rows = []
    for row in resp.get("rows", []) or []:
        rec = dict(zip(headers, row))
        rows.append({
            "country": rec.get("country", ""),
            "views": int(float(rec.get("views") or 0)),
            "minutes": round(float(rec.get("estimatedMinutesWatched") or 0), 1),
        })
    total = sum(r["views"] for r in rows) or 0
    for r in rows:
        # Share of the REPORTED countries, and honestly labelled as such:
        # the API returns a top-N, so this is not a share of all views.
        r["pct_of_listed"] = round(100.0 * r["views"] / total, 2) if total else None
    return rows


def _traffic_sources(service, start: str, end: str) -> List[dict]:
    """Views by traffic source type (Shorts feed / browse / SEARCH /
    suggested / external). [] on any failure.

    Aug 2026: the policy treated a search-driven view and a Shorts-feed
    view as identical evidence; this is the free split that says whether
    titles/tags are doing anything at all.
    """
    try:
        resp = service.reports().query(
            ids="channel==MINE", startDate=start, endDate=end,
            metrics="views,estimatedMinutesWatched",
            dimensions="insightTrafficSourceType",
            sort="-views", maxResults=25,
        ).execute()
    except Exception as exc:  # noqa: BLE001
        logger.info("traffic-source query skipped: %s", str(exc)[:160])
        return []
    headers = [h["name"] for h in resp.get("columnHeaders", [])]
    rows = []
    for row in resp.get("rows", []) or []:
        rec = dict(zip(headers, row))
        rows.append({
            "source": rec.get("insightTrafficSourceType", ""),
            "views": int(float(rec.get("views") or 0)),
            "minutes": round(float(
                rec.get("estimatedMinutesWatched") or 0), 1),
        })
    return rows


def _search_terms(service, start: str, end: str, limit: int = 20) -> List[dict]:
    """The literal YouTube search queries that reached this channel.

    The single best free input for tags and the title prompt. [] on any
    failure (the detail dimension needs YT_SEARCH traffic to exist).
    """
    try:
        resp = service.reports().query(
            ids="channel==MINE", startDate=start, endDate=end,
            metrics="views", dimensions="insightTrafficSourceDetail",
            filters="insightTrafficSourceType==YT_SEARCH",
            sort="-views", maxResults=limit,
        ).execute()
    except Exception as exc:  # noqa: BLE001
        logger.info("search-terms query skipped: %s", str(exc)[:160])
        return []
    headers = [h["name"] for h in resp.get("columnHeaders", [])]
    rows = []
    for row in resp.get("rows", []) or []:
        rec = dict(zip(headers, row))
        term = str(rec.get("insightTrafficSourceDetail", "")).strip()
        if term:
            rows.append({"term": term,
                         "views": int(float(rec.get("views") or 0))})
    return rows


def _retention_curve(service, video_id: str, start: str, end: str) -> List[dict]:
    """The audience-retention curve for ONE video — where viewers leave.

    averageViewPercentage is one scalar; the curve says WHERE the drop
    happens, which is what the scene scheduler and the hook-first
    directive actually need measured. [] on any failure.
    """
    try:
        resp = service.reports().query(
            ids="channel==MINE", startDate=start, endDate=end,
            metrics="audienceWatchRatio",
            dimensions="elapsedVideoTimeRatio",
            filters=f"video=={video_id}",
        ).execute()
    except Exception as exc:  # noqa: BLE001
        logger.info("retention-curve query skipped (%s): %s",
                    video_id, str(exc)[:120])
        return []
    headers = [h["name"] for h in resp.get("columnHeaders", [])]
    curve = []
    for row in resp.get("rows", []) or []:
        rec = dict(zip(headers, row))
        try:
            curve.append({
                "t": round(float(rec.get("elapsedVideoTimeRatio")), 3),
                "ratio": round(float(rec.get("audienceWatchRatio")), 4),
            })
        except (TypeError, ValueError):
            continue
    return curve


def _summarise_demographics(rows: List[dict]) -> dict:
    """Marginals worth putting on a dashboard card."""
    if not rows:
        return {}
    by_gender: Dict[str, float] = defaultdict(float)
    by_age: Dict[str, float] = defaultdict(float)
    for r in rows:
        by_gender[r["gender"]] += r["pct"]
        by_age[r["age"]] += r["pct"]
    older = sum(p for a, p in by_age.items()
                if a in ("55-64", "65-"))
    under_25 = sum(p for a, p in by_age.items()
                   if a in ("13-17", "18-24"))
    return {
        "by_gender": {k: round(v, 2) for k, v in sorted(by_gender.items())},
        "by_age": {k: round(v, 2) for k, v in sorted(by_age.items())},
        "pct_55_plus": round(older, 2),
        "pct_under_25": round(under_25, 2),
    }


def _channel_snapshot(credentials) -> Optional[dict]:
    """Channel-level statistics via the Data API (subs, total views).

    July 18 2026: subscribers were previously tracked NOWHERE — growth
    was judged purely on per-video views/retention. Best-effort: None on
    any failure.
    """
    try:
        from googleapiclient.discovery import build
        service = build("youtube", "v3", credentials=credentials,
                        cache_discovery=False)
        resp = service.channels().list(part="statistics", mine=True).execute()
        items = resp.get("items") or []
        if not items:
            return None
        stats = items[0].get("statistics") or {}
        return {
            "subscribers": int(stats.get("subscriberCount", 0) or 0),
            "total_views": int(stats.get("viewCount", 0) or 0),
            "video_count": int(stats.get("videoCount", 0) or 0),
        }
    except Exception as exc:  # noqa: BLE001 — optional read, never fatal
        logger.warning("Channel snapshot failed: %s", str(exc)[:200])
        return None


def _data_service(credentials):
    """Build the YouTube Data API v3 client; None if libs/creds unusable."""
    try:
        from googleapiclient.discovery import build
        return build("youtube", "v3", credentials=credentials,
                     cache_discovery=False)
    except Exception as exc:  # noqa: BLE001 — optional read, never fatal
        logger.warning("Could not build Data API service: %s", str(exc)[:200])
        return None


def _channel_uploads(credentials, *, since_days: int = UPLOADS_SINCE_DAYS,
                     service=None, today: Optional[_dt.date] = None,
                     ) -> Optional[List[dict]]:
    """Every video on the channel's uploads playlist published in the last
    *since_days* days: ``[{video_id, title, published}]``, newest first.

    ``channels().list(part="contentDetails", mine=True)`` names the uploads
    playlist; ``playlistItems().list`` pages it (1 quota unit a page, ~10
    pages a channel) until an item is older than the window. **None on any
    failure** — the caller then writes NO ``unindexed_recent`` keys (absent,
    never 0) and the snapshot is never marked degraded by this read.
    """
    service = service or _data_service(credentials)
    if service is None:
        return None
    today = today or _dt.date.today()
    cutoff = (today - _dt.timedelta(days=since_days)).isoformat()
    try:
        resp = service.channels().list(part="contentDetails", mine=True).execute()
        items = resp.get("items") or []
        if not items:
            return None
        uploads_id = (((items[0].get("contentDetails") or {})
                       .get("relatedPlaylists") or {}).get("uploads"))
        if not uploads_id:
            return None
        out: List[dict] = []
        page_token = None
        for _page in range(60):   # 3,000 items — far past a 35-day window
            kwargs = dict(part="snippet,contentDetails", playlistId=uploads_id,
                          maxResults=50)
            if page_token:
                kwargs["pageToken"] = page_token
            page = service.playlistItems().list(**kwargs).execute()
            older = False
            for it in page.get("items") or []:
                cd = it.get("contentDetails") or {}
                sn = it.get("snippet") or {}
                vid = cd.get("videoId") or (sn.get("resourceId") or {}).get("videoId")
                published = str(cd.get("videoPublishedAt") or sn.get("publishedAt") or "")[:10]
                if not vid:
                    continue
                if published and published < cutoff:
                    older = True
                    break
                out.append({"video_id": vid,
                            "title": str(sn.get("title") or ""),
                            "published": published})
            page_token = page.get("nextPageToken")
            if older or not page_token:
                break
        return out
    except Exception as exc:  # noqa: BLE001 — optional read, never fatal
        logger.warning("Channel uploads read failed: %s", str(exc)[:200])
        return None


def _norm_text(text: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[^\w\s]", "", str(text or "").casefold())).strip()


def _hook_prefix_match(remainder: str, hook: str) -> bool:
    """The feed title's hook part is ``clip_words(hook)`` — a word-boundary
    prefix of the hook (or the whole hook)."""
    a = _norm_text(remainder.rstrip("…. "))
    b = _norm_text(hook)
    if min(len(a), len(b)) < _HOOK_PREFIX_MIN_CHARS:
        return False
    return a.startswith(b) or b.startswith(a)


def attribute_rss_copies(uploads: List[dict], index_rows: List[dict]) -> List[dict]:
    """Diff the uploads playlist against the index rows of the same channel.

    Returns every upload whose id is not in the indexes, newest first. An
    entry whose title reads ``Ep N: <hook prefix>`` with N and the hook
    prefix matching an index row carries ``show_slug``, ``_dir``,
    ``episode`` and ``kind: "rss_copy"``; the others carry only
    ``video_id`` / ``title`` / ``published``. Pure — the fetch and the
    guards both call it.
    """
    known = {str(r.get("video_id")) for r in index_rows if r.get("video_id")}
    by_episode: Dict[int, List[dict]] = defaultdict(list)
    for r in index_rows:
        try:
            by_episode[int(r.get("episode"))].append(r)
        except (TypeError, ValueError):
            continue
    out: List[dict] = []
    for up in uploads or []:
        vid = str(up.get("video_id") or "")
        if not vid or vid in known:
            continue
        entry = {"video_id": vid, "title": str(up.get("title") or ""),
                 "published": str(up.get("published") or "")[:10]}
        m = _RSS_COPY_TITLE_RE.match(entry["title"])
        if m:
            # The long's row first — its hook is the episode's; the Shorts
            # carry the same hook, so any row settles it.
            cands = sorted(by_episode.get(int(m.group(1)), []),
                           key=lambda r: 0 if r.get("kind") == "long" else 1)
            for cand in cands:
                if _hook_prefix_match(m.group(2), cand.get("hook") or ""):
                    entry.update({
                        "show_slug": cand.get("show_slug") or "",
                        "_dir": cand.get("_dir") or "",
                        "episode": cand.get("episode"),
                        "hook": cand.get("hook") or "",
                        "kind": RSS_COPY_KIND,
                    })
                    break
        out.append(entry)
    return out


def _public_unindexed(entries: List[dict]) -> List[dict]:
    """The snapshot's copy of an unindexed entry (no ``_dir``, no hook)."""
    keep = ("video_id", "title", "published", "show_slug", "episode", "kind")
    return [{k: e[k] for k in keep if k in e} for e in entries]


def rss_copy_warnings(payload: Dict[str, object], policy: Optional[Dict[str, object]],
                      ) -> List[str]:
    """One ``::warning::`` line per show that renders its own long-form
    (``publish_long_form`` on in the policy) and still has RSS-ingested
    copies beside it in the uploads window; one ``::notice::`` line per
    channel with any unindexed upload. [] when the uploads read is absent.
    """
    lines: List[str] = []
    pol_channels = ((policy or {}).get("channels") or {}) if isinstance(policy, dict) else {}
    for ch, block in sorted(((payload.get("channels") or {}).items())):
        entries = (block or {}).get("unindexed_recent")
        if not isinstance(entries, list) or not entries:
            continue
        by_show: Dict[str, int] = defaultdict(int)
        for e in entries:
            if e.get("kind") == RSS_COPY_KIND and e.get("show_slug"):
                by_show[str(e["show_slug"])] += 1
        for slug, n in sorted(by_show.items()):
            entry = (pol_channels.get(ch) or {}).get(slug) or {}
            if entry.get("publish_long_form") is True:
                lines.append(
                    f"::warning::YouTube RSS copies — {slug} on {ch}: {n} RSS-ingested "
                    f"cop{'y' if n == 1 else 'ies'} in the last {UPLOADS_SINCE_DAYS} days "
                    "beside its rendered long-form (Studio → Content → Podcasts)")
        lines.append(
            f"::notice::YouTube uploads — channel {ch}: {len(entries)} upload(s) in the "
            f"last {UPLOADS_SINCE_DAYS} days are not in any per-show index "
            f"({sum(by_show.values())} attributed as RSS copies)")
    return lines


def _channel_day_series(service, days: int = 30) -> List[dict]:
    """Channel-level daily views/subscribersGained series (Analytics v2).

    Empty list on any failure — the per-video fetch is the primary read.
    """
    try:
        today = _dt.date.today()
        start = (today - _dt.timedelta(days=days)).isoformat()
        resp = _execute_with_retry(lambda: service.reports().query(
            ids="channel==MINE",
            startDate=start,
            endDate=today.isoformat(),
            metrics="views,subscribersGained,subscribersLost",
            dimensions="day",
            sort="day",
        ), "channel day series")
        headers = [h["name"] for h in resp.get("columnHeaders", [])]
        return [dict(zip(headers, row)) for row in resp.get("rows", []) or []]
    except Exception as exc:  # noqa: BLE001
        _FAILED_QUERIES.append("channel day series")
        logger.warning("Channel day-series query failed: %s", str(exc)[:200])
        return []


_TRAFFIC_KEEP = ("SHORTS", "SUBSCRIBER", "YT_SEARCH", "RELATED_VIDEO")


def _traffic_source_day_series(service, days: int = 30) -> List[dict]:
    """Views per DAY by traffic-source type (Sep 22 2026).

    The 90-day ``traffic_sources`` aggregate could only say that the
    Shorts-feed source was draining out of a rolling window; when every
    channel's new Shorts lost their exploration traffic in the same four
    days of September, nothing here could show WHICH source moved and
    WHEN. One query, pivoted to ``{day, SHORTS, SUBSCRIBER, YT_SEARCH,
    RELATED_VIDEO, other, total}`` rows. Retried on 5xx like the day
    series, but a failure is LOG ONLY — it never joins ``_FAILED_QUERIES``,
    because that list is the degraded marker ``snapshot_regression``
    refuses a snapshot on, and a missing informational series must never
    cost the policy its day. ``[]`` on any failure.
    """
    try:
        today = _dt.date.today()
        start = (today - _dt.timedelta(days=days)).isoformat()
        resp = _execute_with_retry(lambda: service.reports().query(
            ids="channel==MINE",
            startDate=start,
            endDate=today.isoformat(),
            metrics="views",
            dimensions="day,insightTrafficSourceType",
            sort="day",
        ), "traffic-source day series")
    except Exception as exc:  # noqa: BLE001 — informational, never degraded
        logger.info("traffic-source day series skipped: %s", str(exc)[:160])
        return []
    headers = [h["name"] for h in resp.get("columnHeaders", [])]
    by_day: Dict[str, dict] = {}
    for row in resp.get("rows", []) or []:
        rec = dict(zip(headers, row))
        day = str(rec.get("day") or "")
        if not day:
            continue
        src = str(rec.get("insightTrafficSourceType") or "")
        try:
            views = int(float(rec.get("views") or 0))
        except (TypeError, ValueError):
            views = 0
        d = by_day.setdefault(day, {"day": day, **{k: 0 for k in _TRAFFIC_KEEP},
                                    "other": 0, "total": 0})
        d[src if src in _TRAFFIC_KEEP else "other"] += views
        d["total"] += views
    return [by_day[k] for k in sorted(by_day)]


def snapshot_notes(new: Dict[str, object], old: Optional[Dict[str, object]]) -> List[str]:
    """Informational differences worth a ``::notice::`` — never a refusal."""
    notes: List[str] = []
    if not isinstance(old, dict) or not old:
        return notes
    for ch, block in (old.get("channels") or {}).items():
        if (block or {}).get("traffic_day_series") and not (
                ((new.get("channels") or {}).get(ch) or {}).get("traffic_day_series")):
            notes.append(f"channel {ch} lost its traffic-source day series (informational)")
    return notes


def snapshot_regression(new: Dict[str, object], old: Optional[Dict[str, object]],
                        min_video_share: float = 0.6) -> Optional[str]:
    """Why *new* must NOT replace *old* on disk, or ``None`` when it may.

    A snapshot is refused when the fetch recorded failed queries while the
    committed file is clean, when it lists under ``min_video_share`` of
    the videos the committed file has, or when a channel that had a day
    series comes back without one. The nightly step is ``|| true``, so
    the refusal is an ``::error::`` annotation plus an untouched file —
    the dashboard's 36 h freshness alert then says the rest.
    """
    if not isinstance(old, dict) or not old:
        return None
    # Nov 3 2026: the share counts the INDEXED kinds only — an attributed
    # RSS copy (``rss_copy``) is a joined row, not a video the index knows,
    # and the first night with copies must neither pass nor refuse on them.
    def _indexed_n(doc):
        return sum(1 for sh in ((doc or {}).get("shows") or {}).values()
                   for v in ((sh or {}).get("videos") or [])
                   if (v.get("kind") or "") in INDEXED_KINDS)
    old_n = _indexed_n(old)
    new_n = _indexed_n(new)
    degraded = new.get("degraded") or {}
    if degraded.get("failed_queries") and not old.get("degraded"):
        return (f"{len(degraded['failed_queries'])} analytics quer(ies) failed "
                f"({', '.join(sorted(set(degraded['failed_queries'])))}); the committed file is clean")
    if old_n and new_n < min_video_share * old_n:
        return f"only {new_n} videos against {old_n} committed ({100 * new_n / old_n:.0f}%)"
    old_ch = old.get("channels") or {}
    new_ch = new.get("channels") or {}
    for ch, block in old_ch.items():
        if (block or {}).get("day_series") and not ((new_ch.get(ch) or {}).get("day_series")):
            return f"channel {ch!r} lost its day series"
    return None


def append_channel_history(channels: Dict[str, dict],
                           path: Path) -> None:
    """Append today's per-channel snapshot rows (idempotent per day).

    Rows: {date, channel, subscribers, total_views}. Re-runs on the same
    day replace that day's rows instead of duplicating them.
    """
    today = _dt.date.today().isoformat()
    rows: List[dict] = []
    try:
        existing = json.loads(path.read_text(encoding="utf-8"))
        rows = list(existing.get("rows", []))
    except Exception:  # noqa: BLE001 — first run / unreadable = start fresh
        rows = []
    rows = [r for r in rows
            if not (r.get("date") == today and r.get("channel") in channels)]
    for channel, snap in sorted(channels.items()):
        if not snap:
            continue
        rows.append({
            "date": today,
            "channel": channel,
            "subscribers": snap.get("subscribers", 0),
            "total_views": snap.get("total_views", 0),
        })
    rows = rows[-_CHANNEL_HISTORY_MAX_ROWS:]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps({"rows": rows}, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


def _counter_deltas(rows: List[dict]) -> Dict[str, List[tuple]]:
    """Per-channel ``(date, daily delta)`` from the Data API counter rows."""
    by_channel: Dict[str, List[dict]] = {}
    for r in rows:
        if isinstance(r, dict) and r.get("date"):
            by_channel.setdefault(str(r.get("channel") or ""), []).append(r)
    out: Dict[str, List[tuple]] = {}
    for channel, series in by_channel.items():
        series = sorted(series, key=lambda r: r["date"])
        deltas = []
        for prev, cur in zip(series, series[1:]):
            try:
                deltas.append(
                    (cur["date"],
                     float(cur.get("total_views", 0))
                     - float(prev.get("total_views", 0))))
            except (TypeError, ValueError):
                continue
        out[channel] = deltas
    return out


def _analytics_flow(day_series: Optional[Dict[str, List[dict]]]
                    ) -> Dict[str, List[tuple]]:
    """Per-channel ``(day, views)`` from the Analytics API day series."""
    out: Dict[str, List[tuple]] = {}
    for channel, series in (day_series or {}).items():
        flow = []
        for r in series or []:
            if not isinstance(r, dict) or not r.get("day"):
                continue
            try:
                flow.append((str(r["day"]), float(r.get("views") or 0)))
            except (TypeError, ValueError):
                continue
        flow.sort()
        if flow:
            out[str(channel)] = flow
    return out


def detect_view_cliffs(rows: List[dict],
                       min_baseline: float = 200.0,
                       day_series: Optional[Dict[str, List[dict]]] = None,
                       ) -> List[str]:
    """Per-channel daily-views cliff detector (2026-08-21).

    The Aug 17-19 2026 collapse (RU -78%, EN subs +9/day -> +1/day) ran
    for four days before anyone looked: the dashboard tracked freshness
    and totals but nothing compared today's view FLOW to its own recent
    baseline. For each channel, compare the latest day's views against
    the median of the prior seven days; a drop past 50% of a meaningful
    baseline (>= *min_baseline* views/day) returns a warning line. A
    cliff detector by design — the numbers lesson says a rolling
    baseline can't catch a slide, but a one-day halving is exactly what
    it can catch, loudly, the next morning.

    **Sep 9 2026 — the flow comes from the Analytics API, not the Data
    API counter.** The detector originally differenced the channel
    ``statistics.viewCount`` snapshot in the history file. On 2026-09-02
    that counter stopped moving on all three channels at once (@NerraRU
    +19/day against ~4,000 real views/day in Analytics; @NerraFR +9;
    @NerraNetwork about a third of its flow) while every other read —
    Analytics day series, per-video views, subscribers, uploads — was UP.
    The alarm paged "CHANNEL VIEW CLIFF" on three channels for four
    nights over a counter that had simply stopped counting Shorts. When
    *day_series* (``{channel: [{day, views, ...}]}``, the Analytics
    payload) is supplied it is the ONLY source for that channel; the
    counter deltas remain the fallback for channels the Analytics read
    could not cover, and ``detect_counter_divergence`` reports the
    counter stall separately as information.
    """
    import statistics
    warnings: List[str] = []
    flow_by_channel = _analytics_flow(day_series)
    counter_by_channel = _counter_deltas(rows)
    channels = sorted(set(flow_by_channel) | set(counter_by_channel))
    for channel in channels:
        series = flow_by_channel.get(channel) or counter_by_channel.get(channel) or []
        source = "analytics" if channel in flow_by_channel else "counter"
        if len(series) < 8:
            continue
        *baseline, (day, latest) = series[-8:]
        med = statistics.median(d for _, d in baseline)
        if med >= min_baseline and latest < 0.5 * med:
            warnings.append(
                f"{channel}: {latest:.0f} views on {day} vs a "
                f"{med:.0f}/day baseline ({latest / med:.0%}, {source}) — "
                "check recent uploads, metadata changes, and Studio")
    return warnings


def detect_counter_divergence(rows: List[dict],
                              day_series: Optional[Dict[str, List[dict]]],
                              min_flow: float = 200.0) -> List[str]:
    """Report a Data API ``viewCount`` that has stopped tracking the
    Analytics view flow (Sep 9 2026). Information, never an alarm: the
    counter is the investor page's lifetime figure and the history
    file's trend line, and a reader who sees it flat while the channel
    is growing needs to know WHICH number is lying. For each channel with
    both reads, compare the counter's mean daily delta over the last
    three overlapping days with the Analytics mean for the same days;
    below 25% of a meaningful flow (>= *min_flow*) is a divergence.
    """
    notes: List[str] = []
    flow_by_channel = _analytics_flow(day_series)
    counter_by_channel = _counter_deltas(rows)
    for channel in sorted(set(flow_by_channel) & set(counter_by_channel)):
        flow = dict(flow_by_channel[channel])
        counter = dict(counter_by_channel[channel])
        common = sorted(set(flow) & set(counter))[-3:]
        if len(common) < 3:
            continue
        flow_mean = sum(flow[d] for d in common) / 3.0
        counter_mean = sum(counter[d] for d in common) / 3.0
        if flow_mean >= min_flow and counter_mean < 0.25 * flow_mean:
            notes.append(
                f"{channel}: Data API viewCount moved {counter_mean:.0f}/day "
                f"over {common[0]}..{common[-1]} while Analytics counted "
                f"{flow_mean:.0f}/day — the counter is not tracking views "
                "(likely Shorts); trust the Analytics day series, and read "
                "total_views as a lower bound")
    return notes


def fetch(digests_dir: Path, days: int,
          out_path: Optional[Path] = None) -> Optional[dict]:
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
    channels_block: Dict[str, dict] = {}
    # Attributed RSS copies (kind ``rss_copy``) that join the shows block.
    copy_rows: List[dict] = []
    # The night's curve candidates: every long of the last RETENTION_CURVE_DAYS
    # and each channel's top Shorts, queried AFTER the channel loop in ONE
    # newest-first order across the channels, inside RETENTION_CURVE_MAX.
    long_curve_candidates: List[dict] = []
    short_curve_candidates: List[dict] = []
    any_data = False
    del _FAILED_QUERIES[:]
    for channel, rows in by_channel.items():
        creds = get_channel_credentials_from_env(channel)
        if creds is None:
            logger.info("No credentials for channel=%s — skipped", channel)
            continue
        service = _analytics_service(creds)
        if service is None:
            continue
        # Nov 3 2026: the uploads playlist, diffed against the indexes.
        # None = the read failed → no keys (absent, never 0), never degraded.
        uploads = _channel_uploads(creds, today=today)
        unindexed: Optional[List[dict]] = None
        channel_copy_rows: List[dict] = []
        if uploads is not None:
            unindexed = attribute_rss_copies(uploads, rows)
            for e in unindexed:
                if e.get("kind") == RSS_COPY_KIND and e.get("_dir"):
                    channel_copy_rows.append({
                        "video_id": e["video_id"], "show_slug": e.get("show_slug", ""),
                        "episode": e.get("episode"), "kind": RSS_COPY_KIND,
                        "channel": channel, "title": e.get("title", ""),
                        "hook": e.get("hook", ""), "published": e.get("published", ""),
                        "_dir": e["_dir"],
                    })
            copy_rows.extend(channel_copy_rows)
        ids = [r["video_id"] for r in rows] + [r["video_id"] for r in channel_copy_rows]
        for i in range(0, len(ids), _BATCH):
            batch = ids[i:i + _BATCH]
            got = _query_batch(service, batch, start, end)
            if got:
                any_data = True
            metrics_by_video.update(got)
        # Channel-level snapshot + 30-day day-series (subs growth).
        snap = _channel_snapshot(creds) or {}
        series = _channel_day_series(service)

        # Audience demographics + geography (July 2026). Studio shows
        # these per channel but not split by format; the Shorts/long
        # split is the interesting cut, because Shorts skew young
        # everywhere and a channel whose Shorts DON'T is a different
        # strategic situation from one whose long-form drags the average
        # up. The API has no Shorts dimension, so the split comes from
        # filtering on our own index's `kind`.
        demo_start = (today - _dt.timedelta(days=_DEMO_DAYS)).isoformat()
        demo: Dict[str, object] = {"window_days": _DEMO_DAYS}
        all_rows = _viewer_percentages(service, demo_start, end)
        if all_rows:
            demo["all"] = all_rows
            demo["summary"] = _summarise_demographics(all_rows)
            for kind in ("long", "short"):
                kind_ids = [
                    r["video_id"] for r in rows
                    if (r.get("kind") or "") == kind
                    and (r.get("published") or "") >= demo_start
                ]
                if len(kind_ids) < 3:
                    continue    # too few videos for a meaningful split
                kind_rows = _viewer_percentages(service, demo_start, end,
                                                video_ids=kind_ids)
                if kind_rows:
                    demo[kind] = kind_rows
                    demo[f"{kind}_summary"] = _summarise_demographics(kind_rows)
        geo = _geography(service, demo_start, end)
        traffic = _traffic_sources(service, demo_start, end)
        traffic_days = _traffic_source_day_series(service)
        search_terms = _search_terms(service, demo_start, end)

        # Retention curves (Nov 3 2026): EVERY long published in the last
        # RETENTION_CURVE_DAYS — the curve is the measurement the scene
        # scheduler, the hook-first directive and every long-form arm need
        # read at a fixed age — plus the channel's top
        # RETENTION_CURVE_SHORTS_TOP Shorts by views for the hook-Short
        # readouts. They are CANDIDATES here; the queries run after the
        # channel loop, in ONE newest-first order across the channels —
        # spent channel by channel, the EN longs alone (118 in the 14 days
        # to Nov 3) emptied the budget before @NerraRU or @NerraFR was asked
        # for a single curve. A video the metrics batch did not return has
        # nowhere to carry a curve and is not a candidate.
        curve_lo = (today - _dt.timedelta(days=RETENTION_CURVE_DAYS)).isoformat()
        for r in rows:
            if (r.get("kind") or "") != "long" \
                    or (r.get("published") or "") < curve_lo \
                    or metrics_by_video.get(r["video_id"]) is None:
                continue
            long_curve_candidates.append(
                {"service": service, "start": demo_start, "video_id": r["video_id"],
                 "published": str(r.get("published") or "")})
        _top_shorts = sorted(
            (r for r in rows
             if (r.get("kind") or "") == "short"
             and (r.get("published") or "") >= demo_start
             and metrics_by_video.get(r["video_id"]) is not None),
            key=lambda r: -float((metrics_by_video.get(r["video_id"]) or {})
                                 .get("views", 0) or 0))[:RETENTION_CURVE_SHORTS_TOP]
        for r in _top_shorts:
            short_curve_candidates.append(
                {"service": service, "start": demo_start, "video_id": r["video_id"],
                 "views": float((metrics_by_video.get(r["video_id"]) or {})
                                .get("views", 0) or 0)})

        if unindexed is not None:
            snap["unindexed_recent"] = _public_unindexed(unindexed)
            snap["unindexed_recent_count"] = len(unindexed)
            snap["unindexed_since_days"] = UPLOADS_SINCE_DAYS

        if snap or series or all_rows or geo or traffic:
            snap["day_series"] = series
            if all_rows:
                snap["demographics"] = demo
            if geo:
                snap["geography"] = geo
            if traffic:
                snap["traffic_sources"] = traffic
            if traffic_days:
                snap["traffic_day_series"] = traffic_days
            if search_terms:
                snap["search_terms"] = search_terms
            channels_block[channel] = snap

    if not any_data:
        logger.info("No analytics returned (no scope / no data yet) — no-op")
        return None

    # The curve queries, in ONE order across the channels: every long of the
    # last RETENTION_CURVE_DAYS newest first (a long's first nights are its
    # fixed-age reads — a 13-day-old EN long never outranks last night's FR
    # one), then the top Shorts by views, inside the night's budget. One
    # Analytics query each; stamped ``curve_fetched_at`` = tonight. A long
    # past the budget keeps the curve it was fetched on an earlier night.
    long_curve_candidates.sort(key=lambda c: c["published"], reverse=True)
    short_curve_candidates.sort(key=lambda c: -c["views"])
    curve_budget = RETENTION_CURVE_MAX
    for c in long_curve_candidates + short_curve_candidates:
        if curve_budget <= 0:
            logger.info("retention-curve budget (%d) spent — %d candidate(s) wait "
                        "for another night", RETENTION_CURVE_MAX,
                        len(long_curve_candidates) + len(short_curve_candidates)
                        - RETENTION_CURVE_MAX)
            break
        curve_budget -= 1
        curve = _retention_curve(c["service"], c["video_id"], c["start"], end)
        if curve:
            m = metrics_by_video.get(c["video_id"])
            if m is not None:
                m["retention_curve"] = curve
                m["curve_fetched_at"] = end

    # Assemble per-show structure for the updater + dashboard. Keyed by the
    # show's output-dir name (where the updater writes the perf file back).
    # {video_id: (curve, curve_fetched_at)} — a carried-forward curve keeps
    # the date it was fetched (None when the old file never stamped one),
    # so no reader can take it for tonight's.
    prev_curves: Dict[str, tuple] = {}
    try:
        _prev = json.loads(Path(out_path).read_text(encoding="utf-8")) \
            if out_path and Path(out_path).exists() else {}
        for _sh in (_prev.get("shows") or {}).values():
            for _v in _sh.get("videos", []):
                if _v.get("retention_curve") and _v.get("video_id"):
                    prev_curves[_v["video_id"]] = (
                        _v["retention_curve"], _v.get("curve_fetched_at"))
    except Exception:  # noqa: BLE001 — carry-forward is best-effort
        prev_curves = {}

    def _curve_fields(vid: str, m: dict) -> dict:
        if m.get("retention_curve"):
            return {"retention_curve": m["retention_curve"],
                    "curve_fetched_at": m.get("curve_fetched_at")}
        prev = prev_curves.get(vid)
        if prev:
            return {"retention_curve": prev[0], "curve_fetched_at": prev[1]}
        return {}

    shows: Dict[str, dict] = defaultdict(lambda: {"videos": []})
    for v in videos + copy_rows:
        m = metrics_by_video.get(v["video_id"])
        if not m:
            continue
        shows[v["_dir"]]["videos"].append({
            "video_id": v["video_id"],
            "show_slug": v.get("show_slug", ""),
            "episode": v.get("episode"),
            "kind": v.get("kind"),
            # Carried through so the performance updater can keep RU-dub
            # retention out of the EN title hints (and vice versa).
            "channel": (v.get("channel") or "en").lower(),
            # Experiment arm for the Shorts motion A/B. Absent on every
            # video published before the experiment (and on shows not
            # enrolled), which the report treats as "not in the trial"
            # rather than as the control — an unenrolled Short was never
            # eligible to be the treatment.
            "variant": (v.get("variant") or ""),
            # Hook-first window label (July 31 2026): lets reports compare
            # the hook-opening Short against smart-window Shorts.
            "window": (v.get("window") or ""),
            "title": v.get("title", ""),
            "hook": v.get("hook", ""),
            "published": v.get("published", ""),
            "views": int(float(m.get("views", 0) or 0)),
            "estimated_minutes_watched": float(m.get("estimatedMinutesWatched", 0) or 0),
            "average_view_duration_s": float(m.get("averageViewDuration", 0) or 0),
            "average_view_percentage": float(m.get("averageViewPercentage", 0) or 0),
            "subscribers_gained": int(float(m.get("subscribersGained", 0) or 0)),
            "subscribers_lost": int(float(m.get("subscribersLost", 0) or 0)),
            # Retention curve: fetched fresh tonight (every long of the
            # last RETENTION_CURVE_DAYS, the top Shorts), otherwise CARRIED
            # FORWARD from the previous stats file with the date it was
            # fetched — without carry-forward the instrument never
            # accumulated past ~10-15 curves (Sep 2026); without the date a
            # carried curve read as fresh (Nov 2026).
            **_curve_fields(v["video_id"], m),
        })

    payload = {
        # v2 (July 18 2026): adds the top-level "channels" block
        # (per-channel subscriber snapshot + 30d day-series) and
        # per-video subscribers_gained/lost. The "shows" shape is
        # unchanged, so every existing consumer (performance updater,
        # policy builder, gallery retention) keeps working.
        "schema_version": 2,
        # Nov 3 2026: ``generated`` carries the DATE the fetch started on
        # (``end``, the date every ``curve_fetched_at`` is stamped with) and
        # the clock time of assembly. The reach file records a hold only
        # from a curve fetched on the snapshot's own date, so a fetch that
        # crossed UTC midnight between its start and its assembly had
        # stamped two dates and lost every age-7 hold for the night.
        "generated": _dt.datetime.now(_dt.timezone.utc).replace(
            year=today.year, month=today.month, day=today.day).isoformat(),
        "window_days": days,
        "channels": channels_block,
        "shows": shows,
    }
    if _FAILED_QUERIES:
        # Sep 17 2026: a partial fetch says so, and main() refuses to let
        # it replace a clean file (see snapshot_regression).
        payload["degraded"] = {"failed_queries": list(_FAILED_QUERIES)}
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--digests", default="digests",
                        help="Directory holding per-show output dirs")
    parser.add_argument("--out", default="api/youtube_stats.json")
    parser.add_argument("--days", type=int, default=90)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    payload = fetch(_ROOT / args.digests, args.days,
                    out_path=_ROOT / args.out)
    if payload is None:
        return 0

    n_videos = sum(len(s["videos"]) for s in payload["shows"].values())
    logger.info("Fetched analytics for %d videos across %d shows",
                n_videos, len(payload["shows"]))
    if args.dry_run:
        print(json.dumps(payload, indent=2, ensure_ascii=False)[:4000])
        return 0

    out_path = _ROOT / args.out
    try:
        existing = json.loads(out_path.read_text(encoding="utf-8")) if out_path.exists() else None
    except (OSError, ValueError):
        existing = None
    reason = snapshot_regression(payload, existing)
    if reason:
        print(f"::error::YouTube analytics snapshot REFUSED — {reason}. "
              f"{out_path.name} left as committed; the day series, policy and "
              f"early-reach card keep yesterday's numbers.", flush=True)
        logger.error("Snapshot refused: %s", reason)
        return 0
    for note in snapshot_notes(payload, existing):
        print(f"::notice::YouTube analytics — {note}", flush=True)

    if payload.get("channels"):
        append_channel_history(
            payload["channels"], _ROOT / _CHANNEL_HISTORY_PATH,
        )
        logger.info(
            "Channel history appended: %s",
            {c: s.get("subscribers") for c, s in payload["channels"].items()},
        )
        try:
            hist = json.loads(
                (_ROOT / _CHANNEL_HISTORY_PATH).read_text(encoding="utf-8"))
            day_series = {
                ch: (block or {}).get("day_series") or []
                for ch, block in payload["channels"].items()
            }
            for warning in detect_view_cliffs(hist.get("rows", []),
                                              day_series=day_series):
                print(f"::warning::CHANNEL VIEW CLIFF — {warning}",
                      flush=True)
            for note in detect_counter_divergence(hist.get("rows", []),
                                                  day_series):
                print(f"::notice::CHANNEL COUNTER DIVERGENCE — {note}",
                      flush=True)
        except Exception:  # noqa: BLE001 — the alarm never blocks the fetch
            logger.debug("view-cliff check failed", exc_info=True)

    # Nov 3 2026: RSS-ingested copies beside a rendered long-form. The
    # policy file is yesterday's (the policy step runs after this one);
    # unreadable = no policy = notices only.
    try:
        _policy = json.loads((_ROOT / _POLICY_PATH).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        _policy = None
    for line in rss_copy_warnings(payload, _policy):
        print(line, flush=True)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    logger.info("Wrote %s", out_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
