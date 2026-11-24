#!/usr/bin/env python3
"""The YouTube growth readout (Nov 24 2026) -> ``api/youtube_growth.json``.

Three questions the Nov 24 review had to answer by hand, answered nightly
from files the nightly already writes (no API call, no secret):

1. **Is each channel growing?** Net subscribers and views per week for the
   last twelve weeks, from ``api/youtube_channel_history.json``.
2. **Same episode, different channel.** The hook Short of one episode is
   published on EN, RU and FR. Its median views at a fixed age, per show per
   channel, says whether a show's reach is the content or the channel.
3. **The long-form map A/B** (``long-form-skip-map-2026-11-24``): long-forms
   rendered without the map sentence against those with it, read at a fixed
   age, with the retention curve at 30 and 60 seconds where one exists.

Honesty rules, as everywhere: an unmeasured number is ``null``, never 0; a
median is printed only over ``MIN_N`` videos; a verdict only over
``AB_MIN_N`` videos in BOTH arms; every video is read at one age.

    python scripts/build_youtube_growth.py            # writes the file
    python scripts/build_youtube_growth.py --print    # prints, writes nothing
"""

from __future__ import annotations

import argparse
import datetime as _dt
import json
import statistics
import sys
from collections import defaultdict
from pathlib import Path
from typing import Dict, Iterable, List, Optional

ROOT = Path(__file__).resolve().parent.parent
OUT_PATH = ROOT / "api" / "youtube_growth.json"

WEEKS = 12
#: A Short is read at this age (days); a long-form at LONG_AGE.
SHORT_AGE = 3
LONG_AGE = 7
#: The same-episode comparison looks this far back.
SAME_EPISODE_DAYS = 28
MIN_N = 5
#: Videos needed in each arm before the A/B prints a verdict.
AB_MIN_N = 20
ARMS = ("map_cut", "map_kept")
#: The cut arm must beat the kept arm by this much retention at 30 s (in
#: points of the audience) to be called; less is "no difference".
AB_MIN_POINTS = 0.04


def _load(path: Path) -> Optional[dict]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else None
    except (OSError, ValueError):
        return None


def _median(values: Iterable[float], min_n: int = MIN_N) -> Optional[float]:
    vals = [float(v) for v in values if v is not None]
    return round(statistics.median(vals), 2) if len(vals) >= min_n else None


def weekly_series(history: Optional[dict], weeks: int = WEEKS) -> Dict[str, List[dict]]:
    """Per channel: ``[{week_ending, subscribers, net_subscribers, views}]``.

    A week is the seven days ending on the channel's latest snapshot date,
    stepped back; each row is the difference between two snapshots exactly
    seven days apart. A week missing either snapshot is left out.
    """
    by: Dict[str, Dict[str, dict]] = defaultdict(dict)
    for row in (history or {}).get("rows") or []:
        if row.get("channel") and row.get("date"):
            by[str(row["channel"])][str(row["date"])] = row
    out: Dict[str, List[dict]] = {}
    for ch, days in by.items():
        last = _dt.date.fromisoformat(max(days))
        rows = []
        for i in range(weeks):
            end = last - _dt.timedelta(days=7 * i)
            a, b = days.get((end - _dt.timedelta(days=7)).isoformat()), days.get(end.isoformat())
            if not a or not b:
                continue
            try:
                rows.append({
                    "week_ending": end.isoformat(),
                    "subscribers": int(b["subscribers"]),
                    "net_subscribers": int(b["subscribers"]) - int(a["subscribers"]),
                    "views": int(b["total_views"]) - int(a["total_views"]),
                })
            except (KeyError, TypeError, ValueError):
                continue
        out[ch] = list(reversed(rows))
    return out


def growth_summary(series: List[dict]) -> dict:
    """The last four weeks against the four before them."""
    def _sum(rows, key):
        return sum(r[key] for r in rows) if len(rows) == 4 else None

    recent, prior = series[-4:], series[-8:-4]
    return {
        "net_subscribers_4w": _sum(recent, "net_subscribers"),
        "net_subscribers_prior_4w": _sum(prior, "net_subscribers"),
        "views_4w": _sum(recent, "views"),
        "views_prior_4w": _sum(prior, "views"),
    }


def _at_age(video: dict, field: str, age: int) -> Optional[float]:
    value = (video.get(field) or {}).get(str(age))
    return float(value) if value is not None else None


def same_episode(reach: Optional[dict], today: _dt.date,
                 days: int = SAME_EPISODE_DAYS, age: int = SHORT_AGE) -> Dict[str, dict]:
    """Per show: the hook Short's median views at *age* days on each channel.

    Only the hook Short (``window == "hook_open"``): it is the one clip every
    channel cuts from the same place in the same episode.
    """
    lo = (today - _dt.timedelta(days=days)).isoformat()
    cells: Dict[str, Dict[str, List[float]]] = defaultdict(lambda: defaultdict(list))
    for v in ((reach or {}).get("videos") or {}).values():
        if v.get("kind") != "short" or v.get("window") != "hook_open":
            continue
        if str(v.get("published") or "") < lo:
            continue
        views = _at_age(v, "views_by_age", age)
        if views is None:
            continue
        cells[str(v.get("show") or "?")][str(v.get("channel") or "en")].append(views)
    out: Dict[str, dict] = {}
    for show, chans in sorted(cells.items()):
        if len(chans) < 2:
            continue
        row = {ch: {"n": len(vals), "median_views": _median(vals)}
               for ch, vals in sorted(chans.items())}
        en = (row.get("en") or {}).get("median_views")
        for ch, cell in row.items():
            m = cell["median_views"]
            cell["times_en"] = (round(m / en, 1) if ch != "en" and m is not None and en
                                else None)
        out[show] = row
    return out


def _retention_at(video: dict, seconds: float) -> Optional[float]:
    """The retention ratio at *seconds* from a stats row's curve."""
    curve = video.get("retention_curve") or []
    avd = float(video.get("average_view_duration_s") or 0.0)
    pct = float(video.get("average_view_percentage") or 0.0)
    if not curve or avd <= 0 or pct <= 0:
        return None
    frac = seconds / (avd / (pct / 100.0))
    if frac > 1:
        return None
    point = min(curve, key=lambda p: abs(float(p.get("t", 0.0)) - frac))
    return float(point.get("ratio", 0.0))


def map_ab(reach: Optional[dict], stats: Optional[dict], age: int = LONG_AGE) -> dict:
    """The long-form map A/B, both arms read at *age* days."""
    curves = {}
    for show in ((stats or {}).get("shows") or {}).values():
        for v in show.get("videos") or []:
            if v.get("retention_curve"):
                curves[v.get("video_id")] = v
    arms: Dict[str, dict] = {}
    for arm in ARMS:
        rows = [(vid, v) for vid, v in ((reach or {}).get("videos") or {}).items()
                if v.get("kind") == "long" and (v.get("channel") or "en") == "en"
                and v.get("variant") == arm
                and _at_age(v, "views_by_age", age) is not None]
        views = [_at_age(v, "views_by_age", age) for _, v in rows]
        subs = [_at_age(v, "subs_by_age", age) or 0.0 for _, v in rows]
        total = sum(views)
        r30 = [_retention_at(curves[vid], 30) for vid, _ in rows if vid in curves]
        r60 = [_retention_at(curves[vid], 60) for vid, _ in rows if vid in curves]
        arms[arm] = {
            "n": len(rows),
            "median_views": _median(views),
            "median_avd_s": _median(_at_age(v, "avd_by_age", age) for _, v in rows),
            "median_view_pct": _median(_at_age(v, "avp_by_age", age) for _, v in rows),
            "subs_per_1000_views": (round(1000.0 * sum(subs) / total, 2)
                                    if len(rows) >= MIN_N and total else None),
            "curves": len([x for x in r30 if x is not None]),
            "retention_30s": _median(r30),
            "retention_60s": _median(r60),
        }
    cut, kept = arms["map_cut"], arms["map_kept"]
    verdict = None
    if (min(cut["curves"], kept["curves"]) >= AB_MIN_N
            and cut["retention_30s"] is not None and kept["retention_30s"] is not None):
        diff = cut["retention_30s"] - kept["retention_30s"]
        verdict = ("cut_ahead" if diff >= AB_MIN_POINTS
                   else "kept_ahead" if diff <= -AB_MIN_POINTS else "no_difference")
    return {"age_days": age, "min_n_per_arm": AB_MIN_N, "arms": arms, "verdict": verdict}


def reach_instrument(reach_file: Optional[dict]) -> dict:
    """Whether impressions and click-through are being read at all."""
    chans = (reach_file or {}).get("channels") or {}
    status = {ch: str((b or {}).get("status") or "unread") for ch, b in sorted(chans.items())}
    # A file written before the status existed carries the raw 403.
    for ch, b in chans.items():
        if "has not been used in project" in str((b or {}).get("error") or ""):
            status[ch] = "api_disabled"
    return {
        "channels": status,
        "videos_with_data": len((reach_file or {}).get("videos") or {}),
        "blocked": bool(status) and all(s in ("api_disabled", "error") for s in status.values()),
    }


def build(root: Path = ROOT, today: Optional[_dt.date] = None) -> dict:
    api = root / "api"
    history = _load(api / "youtube_channel_history.json")
    reach = _load(api / "youtube_early_reach.json")
    stats = _load(api / "youtube_stats.json")
    today = today or _dt.datetime.now(_dt.timezone.utc).date()
    series = weekly_series(history)
    return {
        "schema_version": 1,
        "generated": today.isoformat(),
        "channels": {ch: {"weeks": rows, **growth_summary(rows)}
                     for ch, rows in sorted(series.items())},
        "same_episode_hook_short": {
            "age_days": SHORT_AGE, "window_days": SAME_EPISODE_DAYS,
            "shows": same_episode(reach, today),
        },
        "long_form_map_ab": map_ab(reach, stats),
        "reach_instrument": reach_instrument(_load(api / "youtube_reach.json")),
    }


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--out", default=str(OUT_PATH))
    parser.add_argument("--print", action="store_true", dest="show")
    args = parser.parse_args(argv)
    data = build()
    text = json.dumps(data, ensure_ascii=False, indent=1, sort_keys=True)
    if args.show:
        print(text)
        return 0
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(text + "\n", encoding="utf-8")
    print(f"wrote {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
