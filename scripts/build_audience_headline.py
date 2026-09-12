#!/usr/bin/env python3
"""Audience headline — the number every review starts from (Sep 12 2026).

The network measured its pipeline in ninety-nine keys per episode and its
audience in a card halfway down the dashboard. This builder turns the
audience files the nightly already fetches into ONE small document,
``api/audience_headline.json``, that the dashboard's first tile, the
review snapshot's first section and the daily summary line all read:

* per show — RSS downloads in the last 7 and 30 days, the last-complete
  week against the week before (``wow_pct``), the median first-week
  downloads of episodes old enough to have had a first week, YouTube
  average view percentage over the window (views-weighted, Shorts and
  long-form separately);
* network — the same numbers rolled up, plus newsletter subscribers.

Honesty rules (the funnel report's): a number that cannot be measured is
``null``, never 0; a week-over-week change needs a non-zero prior week;
the CURRENT OP3 week is partial and is never compared.

Reads:  api/op3_stats.json, api/youtube_stats.json, api/buttondown_stats.json
Writes: api/audience_headline.json (``--out``)
"""
from __future__ import annotations

import argparse
import datetime as _dt
import json
import statistics
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

#: Analytics window for YouTube retention (days). Matches the policy's
#: velocity window so the two numbers describe the same videos.
YOUTUBE_WINDOW_DAYS = 28
#: An episode has "had its first week" once it is at least this old.
FIRST_WEEK_MIN_AGE_DAYS = 7
#: ...and is still inside OP3's per-episode 30-day window.
FIRST_WEEK_MAX_AGE_DAYS = 30


def _load(path: Path) -> Dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8")) or {}
    except Exception:  # noqa: BLE001 — a missing file is "unmeasured"
        return {}


def _pct_change(current: Optional[float], prior: Optional[float]) -> Optional[float]:
    if current is None or prior is None or prior <= 0:
        return None
    return round((float(current) - float(prior)) / float(prior) * 100.0, 1)


def _parse_day(value: Any) -> Optional[_dt.date]:
    if not value:
        return None
    try:
        return _dt.datetime.fromisoformat(str(value).replace("Z", "+00:00")).date()
    except ValueError:
        try:
            return _dt.date.fromisoformat(str(value)[:10])
        except ValueError:
            return None


def weekly_wow(weekly: List[Any]) -> Dict[str, Optional[float]]:
    """Last COMPLETE week vs the week before it. OP3's series ends on the
    current, partial week (w0), so the comparison is w-1 against w-2."""
    series = [int(x or 0) for x in (weekly or [])]
    if len(series) < 3:
        return {"last_week": None, "prior_week": None, "wow_pct": None}
    last, prior = series[-2], series[-3]
    return {"last_week": last, "prior_week": prior, "wow_pct": _pct_change(last, prior)}


def first_week_downloads(episodes: List[dict], today: _dt.date) -> Dict[str, Any]:
    """Median downloads_7d over episodes published 7-30 days ago — every
    such episode's downloads_7d IS its first week."""
    values: List[int] = []
    for ep in episodes or []:
        pub = _parse_day(ep.get("pubdate"))
        if pub is None:
            continue
        age = (today - pub).days
        if FIRST_WEEK_MIN_AGE_DAYS <= age <= FIRST_WEEK_MAX_AGE_DAYS and ep.get("downloads_7d") is not None:
            values.append(int(ep.get("downloads_7d") or 0))
    if not values:
        return {"median": None, "episodes": 0}
    return {"median": int(statistics.median(values)), "episodes": len(values)}


def youtube_retention(videos: List[dict], today: _dt.date) -> Dict[str, Any]:
    """Views-weighted average view percentage by kind over the window."""
    out: Dict[str, Any] = {"short": None, "long": None, "videos": 0, "views": 0}
    acc: Dict[str, List[float]] = {"short": [0.0, 0.0], "long": [0.0, 0.0]}
    n = 0
    total_views = 0
    for v in videos or []:
        pub = _parse_day(v.get("published"))
        if pub is None or (today - pub).days > YOUTUBE_WINDOW_DAYS:
            continue
        kind = "short" if str(v.get("kind") or "") == "short" else "long"
        views = int(v.get("views") or 0)
        avp = v.get("average_view_percentage")
        if avp is None or views <= 0:
            continue
        acc[kind][0] += float(avp) * views
        acc[kind][1] += views
        n += 1
        total_views += views
    for kind, (num, den) in acc.items():
        out[kind] = round(num / den, 1) if den > 0 else None
    out["videos"] = n
    out["views"] = total_views
    return out


def build_headline(root: Path, today: Optional[_dt.date] = None) -> Dict[str, Any]:
    today = today or _dt.date.today()
    op3 = _load(root / "api" / "op3_stats.json")
    yt = _load(root / "api" / "youtube_stats.json")
    bd = _load(root / "api" / "buttondown_stats.json")

    shows: Dict[str, Any] = {}
    op3_shows = op3.get("shows") or {}
    yt_shows = yt.get("shows") or {}
    network_weekly: List[int] = []
    for slug in sorted(set(op3_shows) | set(yt_shows)):
        s = op3_shows.get(slug) or {}
        entry: Dict[str, Any] = {
            "downloads_7d": s.get("downloads_7d") if s else None,
            "downloads_30d": s.get("downloads_30d") if s else None,
            "weekly_downloads": list(s.get("weekly_downloads") or []) if s else [],
        }
        entry.update(weekly_wow(entry["weekly_downloads"]))
        entry["first_week"] = first_week_downloads(s.get("episodes") or [], today) if s else {"median": None, "episodes": 0}
        entry["youtube"] = youtube_retention((yt_shows.get(slug) or {}).get("videos") or [], today)
        shows[slug] = entry
        wk = entry["weekly_downloads"]
        if wk:
            if len(network_weekly) < len(wk):
                network_weekly = [0] * (len(wk) - len(network_weekly)) + network_weekly
            for i, n in enumerate(reversed(wk)):
                network_weekly[len(network_weekly) - 1 - i] += int(n or 0)

    measured = [e for e in shows.values() if e.get("downloads_30d") is not None]
    # OP3 lists only a show's top episodes, so a show's first-week median
    # rests on a handful of episodes; the network view names the shows
    # that carry the audience rather than averaging eighteen medians into
    # a number nobody can act on.
    fw_top = sorted(
        ((slug, e["first_week"]["median"]) for slug, e in shows.items()
         if e["first_week"]["median"] is not None),
        key=lambda t: t[1], reverse=True,
    )[:3]
    all_videos = [v for s in yt_shows.values() for v in (s.get("videos") or [])]
    network = {
        "downloads_7d": sum(int(e["downloads_7d"] or 0) for e in measured) if measured else None,
        "downloads_30d": sum(int(e["downloads_30d"] or 0) for e in measured) if measured else None,
        "weekly_downloads": network_weekly,
        **weekly_wow(network_weekly),
        "first_week_top_shows": [{"show": slug, "median": m} for slug, m in fw_top],
        "youtube": youtube_retention(all_videos, today),
        "newsletter_subscribers": bd.get("subscriber_count") if bd else None,
        "shows_measured": len(measured),
    }
    return {
        "generated_at": _dt.datetime.now(_dt.timezone.utc).isoformat(),
        "as_of": today.isoformat(),
        "sources": {
            "op3_fetched_at": op3.get("fetched_at"),
            "youtube_generated": yt.get("generated"),
            "buttondown_fetched_at": bd.get("fetched_at"),
        },
        "definitions": {
            "wow_pct": "last COMPLETE week of RSS downloads vs the week before (the current week is partial and never compared); null when the prior week is 0 or unmeasured",
            "first_week": "median downloads_7d of episodes published 7-30 days ago — each such episode's downloads_7d is its first week",
            "youtube": f"views-weighted averageViewPercentage over videos published in the last {YOUTUBE_WINDOW_DAYS} days, Shorts and long-form separately",
        },
        "network": network,
        "shows": shows,
    }


def headline_line(doc: Dict[str, Any]) -> str:
    """One line for the daily summary / review snapshot."""
    n = (doc or {}).get("network") or {}
    parts = []
    d7 = n.get("downloads_7d")
    parts.append(f"RSS downloads 7d: {d7 if d7 is not None else 'unmeasured'}")
    wow = n.get("wow_pct")
    if wow is not None:
        parts.append(f"last full week {'+' if wow >= 0 else ''}{wow}% WoW ({n.get('prior_week')} → {n.get('last_week')})")
    else:
        parts.append("WoW: unmeasured")
    top = n.get("first_week_top_shows") or []
    if top:
        parts.append("first-week/ep: " + ", ".join(f"{t['show']} {t['median']}" for t in top))
    else:
        parts.append("first-week/ep: unmeasured")
    yt = n.get("youtube") or {}
    if yt.get("short") is not None or yt.get("long") is not None:
        parts.append(f"YouTube retention shorts {yt.get('short') if yt.get('short') is not None else '—'}% / long {yt.get('long') if yt.get('long') is not None else '—'}%")
    subs = n.get("newsletter_subscribers")
    parts.append(f"newsletter: {subs if subs is not None else 'unmeasured'}")
    return "Audience headline — " + " · ".join(parts)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--root", type=Path, default=PROJECT_ROOT)
    parser.add_argument("--out", type=Path, default=None,
                        help="default: <root>/api/audience_headline.json")
    parser.add_argument("--print", action="store_true", help="print the headline line")
    args = parser.parse_args(argv)
    doc = build_headline(args.root)
    out = args.out or (args.root / "api" / "audience_headline.json")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(doc, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(headline_line(doc))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
