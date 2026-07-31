#!/usr/bin/env python3
"""Join reach, clicks, visits and captures into one funnel — api/funnel.json.

The July 18 2026 audit's verdict was that the factory is world-class and
the funnel is the product gap. The blocker was never missing analytics:
OP3, YouTube Analytics, GA4 and Buttondown all had data. The blocker was
that no two of them shared a key, so nobody could answer the only
question that decides where to spend the next hour of work — *which
surface produces subscribers?*

``engine.funnel`` gave every published link a campaign id that encodes
show / channel / kind / episode / experiment arm. This script reads that
id back out of GA4 and lines the four datasets up into four stages:

    REACH    YouTube views + podcast downloads      (youtube_stats, op3_stats)
    CLICK    sessions attributed to a campaign      (ga4_stats.campaigns)
    VISIT    sessions landing on a funnel page      (ga4_stats.landing_pages)
    CAPTURE  Buttondown subscribers, by tag/source  (buttondown_stats)

and reports the conversion rate between them, per show, per channel, and
for each named pilot.

Honesty rules, because a growth number that flatters is worse than none:

  * Every stage carries ``configured`` and ``fetched_at``. A missing
    input reports ``null``, never ``0`` — "we did not measure" and "it
    was zero" lead to opposite decisions.
  * Rates are ``null`` until the denominator clears
    ``MIN_DENOMINATOR``. A 1-of-2 sample is not a 50% conversion rate.
  * GA4 campaign rows that do not parse as ours are kept, summed, and
    reported under ``unattributed`` rather than dropped, so the report
    shows how much of the picture it is missing.

Usage::

    python scripts/build_funnel.py                  # write api/funnel.json
    python scripts/build_funnel.py --dry-run        # print, write nothing
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import logging
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, List, Optional

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from engine import funnel as F  # noqa: E402

logging.basicConfig(level=logging.INFO, stream=sys.stdout,
                    format="%(levelname)s %(message)s")
log = logging.getLogger("build_funnel")

SCHEMA_VERSION = 1

# Below this many at the top of a ratio, the ratio is noise. Reporting
# "100% conversion" off two sessions is how a pilot gets scaled on
# nothing.
MIN_DENOMINATOR = 30

_API = _ROOT / "api"


def _read_json(path: Path) -> Optional[dict]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001 — a missing input is a normal state
        return None


def _rate(numerator: Optional[float],
          denominator: Optional[float]) -> Optional[float]:
    """Percentage, or None when the sample is too small to mean anything."""
    if numerator is None or denominator is None:
        return None
    if denominator < MIN_DENOMINATOR or denominator <= 0:
        return None
    return round(100.0 * float(numerator) / float(denominator), 3)


# ---------------------------------------------------------------------------
# Stage 1 — REACH
# ---------------------------------------------------------------------------

def _reach(yt: Optional[dict], op3: Optional[dict],
           window_days: int) -> Dict[str, Any]:
    """Views and downloads, split by the surface that produced them."""
    out: Dict[str, Any] = {
        "configured": bool(yt) or bool(op3),
        "youtube_fetched_at": (yt or {}).get("generated"),
        "op3_fetched_at": (op3 or {}).get("fetched_at"),
        "by_show": {},
        "by_channel": {},
        "totals": {"youtube_views": 0, "podcast_downloads": 0,
                   "subscribers_gained": 0},
    }
    cutoff = (dt.date.today() - dt.timedelta(days=window_days)).isoformat()

    per_show: Dict[str, Dict[str, Any]] = defaultdict(
        lambda: {"youtube_views": 0, "youtube_videos": 0,
                 "subscribers_gained": 0, "podcast_downloads_30d": None,
                 "by_channel": defaultdict(
                     lambda: {"views": 0, "videos": 0,
                              "subscribers_gained": 0})})

    for _dir, block in ((yt or {}).get("shows") or {}).items():
        for video in (block or {}).get("videos") or []:
            if (video.get("published") or "") < cutoff:
                continue
            slug = video.get("show_slug") or _dir
            channel = (video.get("channel") or "en").lower()
            views = int(video.get("views") or 0)
            gained = int(video.get("subscribers_gained") or 0)
            row = per_show[slug]
            row["youtube_views"] += views
            row["youtube_videos"] += 1
            row["subscribers_gained"] += gained
            ch = row["by_channel"][channel]
            ch["views"] += views
            ch["videos"] += 1
            ch["subscribers_gained"] += gained

    for slug, block in (((op3 or {}).get("shows")) or {}).items():
        per_show[slug]["podcast_downloads_30d"] = (
            (block or {}).get("downloads_30d")
        )

    by_channel: Dict[str, Dict[str, int]] = defaultdict(
        lambda: {"views": 0, "videos": 0, "subscribers_gained": 0})
    for slug, row in per_show.items():
        row["by_channel"] = {k: dict(v) for k, v in row["by_channel"].items()}
        for channel, ch in row["by_channel"].items():
            by_channel[channel]["views"] += ch["views"]
            by_channel[channel]["videos"] += ch["videos"]
            by_channel[channel]["subscribers_gained"] += \
                ch["subscribers_gained"]
        out["totals"]["youtube_views"] += row["youtube_views"]
        out["totals"]["subscribers_gained"] += row["subscribers_gained"]
        if isinstance(row["podcast_downloads_30d"], int):
            out["totals"]["podcast_downloads"] += row["podcast_downloads_30d"]

    out["by_show"] = {k: dict(v) for k, v in sorted(per_show.items())}
    out["by_channel"] = {k: dict(v) for k, v in sorted(by_channel.items())}
    return out


# ---------------------------------------------------------------------------
# Stage 2 + 3 — CLICK / VISIT
# ---------------------------------------------------------------------------

def _clicks(ga4: Optional[dict]) -> Dict[str, Any]:
    """GA4 sessions, attributed back to the asset that earned them."""
    # `configured` means "this stage was actually measured". A
    # ga4_stats.json written before the campaign report existed has no
    # `campaigns` key at all — reporting that as a configured stage with
    # zero sessions would claim the funnel is dead when it has simply not
    # been read yet.
    out: Dict[str, Any] = {
        "configured": isinstance((ga4 or {}).get("campaigns"), list),
        "fetched_at": (ga4 or {}).get("fetched_at"),
        "window_days": (ga4 or {}).get("days"),
        "by_show": {},
        "by_channel": {},
        "by_campaign": {},
        "by_variant": {},
        "totals": {"sessions": 0, "engaged_sessions": 0},
        # Everything GA4 reported that is NOT one of our campaigns —
        # organic search, direct, referrals, and any surface we have not
        # instrumented yet. Kept visible so the report never implies it
        # can see all of the traffic.
        "unattributed": {"sessions": 0, "top_sources": []},
    }
    if not out["configured"]:
        return out

    per_show: Dict[str, Dict[str, int]] = defaultdict(
        lambda: {"sessions": 0, "engaged_sessions": 0})
    per_channel: Dict[str, Dict[str, int]] = defaultdict(
        lambda: {"sessions": 0, "engaged_sessions": 0})
    per_variant: Dict[str, Dict[str, int]] = defaultdict(
        lambda: {"sessions": 0, "engaged_sessions": 0, "campaigns": 0})
    per_campaign: Dict[str, Dict[str, Any]] = {}
    other: Dict[str, int] = defaultdict(int)

    for row in (ga4.get("campaigns") or []):
        sessions = int(row.get("sessions") or 0)
        engaged = int(row.get("engagedSessions") or 0)
        out["totals"]["sessions"] += sessions
        out["totals"]["engaged_sessions"] += engaged

        name = (row.get("sessionCampaignName") or "").strip()
        parsed = F.parse_campaign_id(name)
        if parsed is None:
            out["unattributed"]["sessions"] += sessions
            source = (row.get("sessionSource") or "(none)").strip()
            medium = (row.get("sessionMedium") or "(none)").strip()
            other[f"{source} / {medium}"] += sessions
            continue

        per_show[parsed.show]["sessions"] += sessions
        per_show[parsed.show]["engaged_sessions"] += engaged
        per_channel[parsed.channel]["sessions"] += sessions
        per_channel[parsed.channel]["engaged_sessions"] += engaged
        if parsed.variant:
            v = per_variant[parsed.variant]
            v["sessions"] += sessions
            v["engaged_sessions"] += engaged
            v["campaigns"] += 1
        entry = per_campaign.setdefault(name, {
            **parsed.as_dict(), "sessions": 0, "engaged_sessions": 0,
        })
        entry["sessions"] += sessions
        entry["engaged_sessions"] += engaged

    # Sessions our campaign ids actually explain. Kept separate from the
    # raw total: "totals.sessions" includes organic/(not set) rows, and
    # presenting it as funnel clicks was the one flattering number in an
    # otherwise honest report.
    out["totals"]["attributed_sessions"] = (
        out["totals"]["sessions"] - out["unattributed"]["sessions"]
    )
    out["by_show"] = {k: dict(v) for k, v in sorted(per_show.items())}
    out["by_channel"] = {k: dict(v) for k, v in sorted(per_channel.items())}
    out["by_variant"] = {k: dict(v) for k, v in sorted(per_variant.items())}
    out["by_campaign"] = dict(sorted(
        per_campaign.items(),
        key=lambda kv: kv[1]["sessions"], reverse=True)[:100])
    out["unattributed"]["top_sources"] = [
        {"source_medium": k, "sessions": v}
        for k, v in sorted(other.items(), key=lambda kv: -kv[1])[:10]
    ]
    return out


def _visits(ga4: Optional[dict], destinations: Dict[str, str]) -> Dict[str, Any]:
    """Sessions that landed on a configured funnel destination."""
    out: Dict[str, Any] = {
        "configured": isinstance((ga4 or {}).get("landing_pages"), list),
        "by_destination": {},
        "totals": {"sessions": 0},
    }
    if not out["configured"]:
        return out
    wanted = {}
    for key, url in destinations.items():
        from urllib.parse import urlparse
        path = urlparse(url).path or "/"
        wanted.setdefault(path, []).append(key)

    agg: Dict[str, Dict[str, Any]] = {}
    for row in (ga4.get("landing_pages") or []):
        raw = (row.get("landingPagePlusQueryString") or "")
        path = raw.split("?", 1)[0] or "/"
        keys = wanted.get(path)
        if not keys:
            continue
        sessions = int(row.get("sessions") or 0)
        for key in keys:
            entry = agg.setdefault(key, {
                "path": path, "sessions": 0, "users": 0,
            })
            entry["sessions"] += sessions
            entry["users"] += int(row.get("activeUsers") or 0)
        out["totals"]["sessions"] += sessions
    out["by_destination"] = dict(sorted(agg.items()))
    return out


# ---------------------------------------------------------------------------
# Stage 4 — CAPTURE
# ---------------------------------------------------------------------------

def _captures(bd: Optional[dict], ga4: Optional[dict]) -> Dict[str, Any]:
    """Subscribers, split by the list they joined and the surface that
    sent them."""
    # Buttondown's total alone cannot attribute anything; the stage is
    # only "configured" once the per-tag breakdown is present.
    out: Dict[str, Any] = {
        "configured": isinstance((bd or {}).get("tag_counts"), dict),
        "total_configured": bool(bd),
        "fetched_at": (bd or {}).get("fetched_at"),
        "total_subscribers": (bd or {}).get("subscriber_count"),
        "by_list": (bd or {}).get("tag_counts"),
        "by_source": {},
        # Signup EVENTS from GA4 (windowed, attributable to a campaign)
        # next to Buttondown's all-time subscriber counts. They answer
        # different questions and are deliberately not added together.
        "signup_events_by_campaign": {},
        "signup_events_total": None,
    }
    for tag, count in ((bd or {}).get("source_counts") or {}).items():
        source = F.source_from_tag(tag)
        if source:
            out["by_source"][source] = count

    events: Dict[str, int] = {}
    total = 0
    have_report = isinstance((ga4 or {}).get("conversions"), list)
    for row in ((ga4 or {}).get("conversions") or []):
        count = int(row.get("eventCount") or 0)
        name = (row.get("sessionCampaignName") or "(direct)").strip()
        events[name] = events.get(name, 0) + count
        total += count
    if have_report:
        out["signup_events_by_campaign"] = dict(sorted(
            events.items(), key=lambda kv: -kv[1])[:50])
        out["signup_events_total"] = total
    return out


# ---------------------------------------------------------------------------
# Pilots
# ---------------------------------------------------------------------------

def _show_funnel_configs() -> Dict[str, Any]:
    """Every show's funnel destinations + capture tag, from the YAMLs."""
    import yaml

    out: Dict[str, Any] = {}
    for path in sorted((_ROOT / "shows").glob("*.yaml")):
        if path.stem.startswith("_") or path.stem in (
                "pronunciation_map", "network_meta", "translation_overrides"):
            continue
        try:
            data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        except Exception:  # noqa: BLE001
            continue
        cfg = data.get("funnel") or {}
        dests = cfg.get("destinations") or {}
        if not dests and not cfg.get("capture_tag"):
            continue
        out[path.stem] = {
            "destinations": dests,
            "capture_tag": (cfg.get("capture_tag") or "").strip(),
        }
    return out


def _pilots(show_funnels: Dict[str, Any], reach: Dict[str, Any],
            clicks: Dict[str, Any], visits: Dict[str, Any],
            captures: Dict[str, Any]) -> Dict[str, Any]:
    """One end-to-end row per configured pilot.

    A pilot is any show that declares a per-channel destination — today
    that is the RU SpaceX pilot, and the shape generalises to the next
    one without a code change.
    """
    out: Dict[str, Any] = {}
    for slug, cfg in show_funnels.items():
        for channel, url in (cfg.get("destinations") or {}).items():
            if channel == "default":
                continue
            key = f"{slug}-{channel}"
            ch_reach = ((reach.get("by_show") or {}).get(slug) or {}) \
                .get("by_channel", {}).get(channel, {})
            views = ch_reach.get("views")
            sessions = ((clicks.get("by_channel") or {})
                        .get(channel, {}).get("sessions"))
            # Show sessions scoped to THIS pilot's channel: by_show[slug]
            # sums the show's campaigns across ALL channels, so once EN
            # spacex campaign traffic exists it would inflate the RU
            # pilot's click-through. by_campaign rows carry the parsed
            # show+channel, so the scoped sum costs nothing extra.
            show_sessions = ((clicks.get("by_show") or {})
                             .get(slug, {}).get("sessions"))
            pilot_sessions = None
            if isinstance(clicks.get("by_campaign"), dict):
                matched = [
                    int(row.get("sessions") or 0)
                    for row in clicks["by_campaign"].values()
                    if row.get("show") == slug
                    and row.get("channel") == channel
                ]
                pilot_sessions = sum(matched) if matched else 0
            landed = ((visits.get("by_destination") or {})
                      .get(key, {}).get("sessions"))
            tag = cfg.get("capture_tag")
            subscribers = ((captures.get("by_list") or {}) or {}).get(tag)
            # Windowed signup EVENTS attributable to this pilot's
            # campaigns — same window as `landed`, so the rate compares
            # like with like. The all-time Buttondown tag count stays in
            # the stages block as the cumulative truth, but dividing it
            # by a windowed session count drifts upward forever (and past
            # 100%), so it no longer feeds a rate.
            pilot_signups = None
            events = captures.get("signup_events_by_campaign")
            if isinstance(events, dict) and captures.get(
                    "signup_events_total") is not None:
                import engine.funnel as _F
                total_ev = 0
                for name, count in events.items():
                    parsed_ev = _F.parse_campaign_id(str(name))
                    if (parsed_ev is not None
                            and parsed_ev.show == slug
                            and parsed_ev.channel == channel):
                        total_ev += int(count or 0)
                pilot_signups = total_ev

            out[key] = {
                "show": slug,
                "channel": channel,
                "destination": url,
                "capture_tag": tag,
                "stages": {
                    "reach_views": views,
                    "clicks_sessions": show_sessions,
                    "visits_sessions": landed,
                    "captures_subscribers": subscribers,
                },
                "rates": {
                    # Reach -> click is the number this pilot exists to
                    # move: how many of the people who watched came.
                    # Channel-scoped sessions over channel-scoped reach.
                    "click_through_pct": _rate(pilot_sessions, views),
                    # Windowed signups over windowed landings.
                    "capture_pct": _rate(pilot_signups, landed),
                },
                "channel_sessions": sessions,
                "show_sessions_all_channels": show_sessions,
            }
    return out


# ---------------------------------------------------------------------------

def build(window_days: int = 30) -> Dict[str, Any]:
    yt = _read_json(_API / "youtube_stats.json")
    op3 = _read_json(_API / "op3_stats.json")
    ga4 = _read_json(_API / "ga4_stats.json")
    bd = _read_json(_API / "buttondown_stats.json")

    show_funnels = _show_funnel_configs()
    destinations: Dict[str, str] = {}
    for slug, cfg in show_funnels.items():
        for channel, url in (cfg.get("destinations") or {}).items():
            destinations[f"{slug}-{channel}"] = url

    reach = _reach(yt, op3, window_days)
    clicks = _clicks(ga4)
    visits = _visits(ga4, destinations)
    captures = _captures(bd, ga4)

    # Null-vs-0 rule applied precisely: only an UNMEASURED input (or a
    # denominator below the floor) yields null — a measured zero in the
    # NUMERATOR is a real rate of 0. The previous `x or None` on the
    # numerators made 0% coverage (the honest launch state: campaigns
    # exist, none parse yet) unrepresentable — it rendered as "not
    # measured", the exact inversion the honesty rules forbid.
    _clicks_measured = bool(clicks.get("configured"))
    _attributed = (
        clicks["totals"]["attributed_sessions"] if _clicks_measured else None
    )
    network_rates = {
        # Attributed sessions only: dividing ALL site sessions (organic
        # included) by YouTube views flattered the funnel.
        "reach_to_click_pct": _rate(
            _attributed,
            reach["totals"]["youtube_views"] or None),
        "visit_to_capture_pct": _rate(
            captures.get("signup_events_total"),
            visits["totals"]["sessions"] or None),
        # How much of GA4's traffic our campaign ids can explain. A low
        # number here means the funnel report is describing a minority of
        # reality and should be read as such.
        "attribution_coverage_pct": _rate(
            _attributed,
            clicks["totals"]["sessions"] if _clicks_measured else None),
    }

    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(
            timespec="seconds"),
        "window_days": window_days,
        "min_denominator": MIN_DENOMINATOR,
        "stages": {
            "reach": reach,
            "click": clicks,
            "visit": visits,
            "capture": captures,
        },
        "network_rates": network_rates,
        "pilots": _pilots(show_funnels, reach, clicks, visits, captures),
        "notes": [
            "Rates are null until the denominator reaches "
            f"{MIN_DENOMINATOR}; a small sample is reported as unknown, "
            "not as a percentage.",
            "A stage with configured=false was never measured — read it "
            "as unknown, not as zero.",
        ],
    }


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", default=str(_API / "funnel.json"))
    parser.add_argument("--window-days", type=int, default=30)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)

    data = build(window_days=args.window_days)
    if args.dry_run:
        print(json.dumps(data, indent=2, ensure_ascii=False))
        return 0

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n",
                   encoding="utf-8")
    stages = data["stages"]
    missing = [name for name, block in stages.items()
               if not block.get("configured")]
    log.info("wrote %s (reach=%s views, click=%s sessions, capture=%s subs)",
             out, stages["reach"]["totals"]["youtube_views"],
             stages["click"]["totals"]["sessions"],
             stages["capture"].get("total_subscribers"))
    if missing:
        log.warning("::warning::funnel stages with no data source: %s — "
                    "those stages report null, not zero", ", ".join(missing))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
