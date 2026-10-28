#!/usr/bin/env python3
"""Audience contract — versioned JSON Mission Control pins to.

The portfolio Mission Control needs a stable, documented shape for
Nerra's audience numbers. The dashboard and audience headline already
hold those numbers, but their shapes drift with the management page.
This builder emits ``api/audience_contract.json``: a small, versioned
aggregate that Mission Control can pin to without parsing prose or
re-deriving windows.

Honesty rules (same as the funnel / headline builders):

* Unmeasured → ``null``, never ``0``.
* No network calls — pure read of already-committed
  ``api/dashboard.json``, ``api/audience_headline.json``, and
  ``api/youtube_stats.json``.
* Do not re-fetch analytics. YouTube ``views_7d`` / ``subs_net_7d`` are
  summed from the committed day series (last 7 present rows, no extra
  lag trim — the API already omits unfinalized days).

See ``docs/audience-contract.md`` for the human-readable contract.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import logging
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

logging.basicConfig(
    level=logging.INFO,
    stream=sys.stdout,
    format="%(levelname)s %(message)s",
)
log = logging.getLogger("build_audience_contract")

SCHEMA_VERSION = 1

#: Top-level keys the contract emits. Drift-guarded by the test suite.
TOP_LEVEL_KEYS = (
    "schema_version",
    "generated_at",
    "op3",
    "youtube",
    "spotify",
    "apple",
    "site",
    "newsletter",
)

YOUTUBE_CHANNELS = ("en", "ru", "fr")


def _load(path: Path) -> Dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8")) or {}
    except Exception:  # noqa: BLE001 — missing/corrupt file is unmeasured
        return {}


def _int_or_none(value: Any) -> Optional[int]:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _num_or_none(value: Any) -> Optional[float]:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _configured(block: Any) -> bool:
    return isinstance(block, dict) and bool(block.get("configured"))


def youtube_7d_from_day_series(
    day_series: Any,
) -> Dict[str, Optional[int]]:
    """Sum the last 7 **present** day-series rows.

    YouTube Analytics omits unfinalized days from the series (~2 days
    behind the build). Do **not** trim further — ``generate_dashboard``'s
    scorecard does ``ds[:-2]`` then ``[-7:]``, which double-trims and
    shifts the window two days too far back. The contract uses
    ``day_series[-7:]`` only.
    """
    rows = [d for d in (day_series or []) if isinstance(d, dict)]
    if not rows:
        return {"views_7d": None, "subs_net_7d": None}
    last7 = rows[-7:]
    views = sum(int(d.get("views") or 0) for d in last7)
    subs_net = sum(
        int(d.get("subscribersGained") or 0) - int(d.get("subscribersLost") or 0)
        for d in last7
    )
    return {"views_7d": views, "subs_net_7d": subs_net}


def build_op3(
    audience: Dict[str, Any],
    headline: Dict[str, Any],
) -> Optional[Dict[str, Any]]:
    op3 = audience.get("op3") if isinstance(audience.get("op3"), dict) else {}
    network = (
        headline.get("network")
        if isinstance(headline.get("network"), dict)
        else {}
    )
    if not op3 and not network:
        return None
    if op3 and not _configured(op3) and not network:
        return None

    unindexed = op3.get("unindexed")
    if unindexed is None:
        unindexed = network.get("shows_unindexed")
    if unindexed is None:
        unindexed_list: List[str] = []
    else:
        unindexed_list = [str(s) for s in list(unindexed)]

    # Rolling totals live on the dashboard; WoW on the headline. Prefer
    # the headline for downloads when the dashboard block is empty so a
    # partial input still yields a coherent op3 object.
    downloads_7d = _int_or_none(op3.get("network_downloads_7d"))
    if downloads_7d is None:
        downloads_7d = _int_or_none(network.get("downloads_7d"))
    downloads_30d = _int_or_none(op3.get("network_downloads_30d"))
    if downloads_30d is None:
        downloads_30d = _int_or_none(network.get("downloads_30d"))

    # Provenance stays on the block even when the headline (and thus WoW)
    # is missing — a null wow_pct with a present fetched_at means "headline
    # absent / WoW unmeasured", not "OP3 itself is gone".
    fetched_at = op3.get("fetched_at")
    if fetched_at is None:
        fetched_at = (headline.get("sources") or {}).get("op3_fetched_at")

    return {
        "fetched_at": fetched_at,
        "network_downloads_7d": downloads_7d,
        "network_downloads_30d": downloads_30d,
        "last_week": _int_or_none(network.get("last_week")),
        "prior_week": _int_or_none(network.get("prior_week")),
        "wow_pct": _num_or_none(network.get("wow_pct")),
        "unindexed_shows": unindexed_list,
        "shows_measured": _int_or_none(network.get("shows_measured")),
    }


def build_youtube(
    dashboard: Dict[str, Any],
    youtube_stats: Optional[Dict[str, Any]] = None,
) -> Optional[Dict[str, Any]]:
    audience = (
        dashboard.get("audience")
        if isinstance(dashboard.get("audience"), dict)
        else {}
    )
    yt_aud = (
        audience.get("youtube")
        if isinstance(audience.get("youtube"), dict)
        else {}
    )
    growth = (
        dashboard.get("growth")
        if isinstance(dashboard.get("growth"), dict)
        else {}
    )
    scorecard = (
        growth.get("channel_scorecard")
        if isinstance(growth.get("channel_scorecard"), dict)
        else {}
    )
    yt_stats = youtube_stats if isinstance(youtube_stats, dict) else {}
    stats_channels = (
        yt_stats.get("channels")
        if isinstance(yt_stats.get("channels"), dict)
        else {}
    )

    sc_channels = (
        scorecard.get("channels")
        if isinstance(scorecard.get("channels"), dict)
        else {}
    )
    aud_channels = (
        yt_aud.get("channels")
        if isinstance(yt_aud.get("channels"), dict)
        else {}
    )

    if not stats_channels and not sc_channels and not aud_channels:
        return None
    if (
        not stats_channels
        and not sc_channels
        and yt_aud
        and not _configured(yt_aud)
    ):
        return None

    channels_out: Dict[str, Any] = {}
    views_sum = 0
    views_any = False
    for ch in YOUTUBE_CHANNELS:
        sc = sc_channels.get(ch) if isinstance(sc_channels.get(ch), dict) else {}
        aud = aud_channels.get(ch) if isinstance(aud_channels.get(ch), dict) else {}
        st = stats_channels.get(ch) if isinstance(stats_channels.get(ch), dict) else {}

        # Point-in-time subscriber count: scorecard first, then audience,
        # then the raw youtube_stats channel snap.
        subscribers = _int_or_none(sc.get("subscribers"))
        if subscribers is None:
            subscribers = _int_or_none(aud.get("subscribers"))
        if subscribers is None:
            subscribers = _int_or_none(st.get("subscribers"))

        # 7d window: ALWAYS from day_series[-7:] when present. Never from
        # channel_scorecard.views_7d / subs_net_7d (known double-trimmed).
        window = youtube_7d_from_day_series(st.get("day_series"))
        views_7d = window["views_7d"]
        subs_net = window["subs_net_7d"]
        if views_7d is not None:
            views_sum += views_7d
            views_any = True

        if subscribers is None and views_7d is None and subs_net is None and not st:
            channels_out[ch] = {
                "subscribers": None,
                "subs_net_7d": None,
                "views_7d": None,
            }
            continue

        channels_out[ch] = {
            "subscribers": subscribers,
            "subs_net_7d": subs_net,
            "views_7d": views_7d,
        }

    generated = (
        yt_stats.get("generated")
        or scorecard.get("as_of")
        or yt_aud.get("generated")
    )
    return {
        "generated_at": generated,
        "channels": channels_out,
        "network_views_7d": views_sum if views_any else None,
    }


def build_spotify(audience: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    sp = audience.get("spotify") if isinstance(audience.get("spotify"), dict) else {}
    if not sp or not _configured(sp):
        return None
    totals = sp.get("totals") if isinstance(sp.get("totals"), dict) else {}
    return {
        "fetched_at": sp.get("fetched_at"),
        "streams": _int_or_none(totals.get("streams")),
        "listeners": _int_or_none(totals.get("listeners")),
        "window_days": _int_or_none(sp.get("window_days")),
    }


def build_apple(
    audience: Dict[str, Any],
    dashboard: Dict[str, Any],
) -> Optional[Dict[str, Any]]:
    ap = audience.get("apple") if isinstance(audience.get("apple"), dict) else {}
    if not ap or not _configured(ap):
        return None
    totals = ap.get("totals") if isinstance(ap.get("totals"), dict) else {}
    network = (
        dashboard.get("network")
        if isinstance(dashboard.get("network"), dict)
        else {}
    )
    return {
        "fetched_at": ap.get("fetched_at"),
        "plays": _int_or_none(totals.get("plays")),
        "listeners": _int_or_none(totals.get("listeners")),
        "listening_hours": _num_or_none(totals.get("listening_hours")),
        "shows_reporting": _int_or_none(ap.get("shows_reporting")),
        "shows_in_network": _int_or_none(network.get("shows_count")),
        "window_start": ap.get("first_date"),
        "window_end": ap.get("last_date"),
        "days_retained": _int_or_none(ap.get("days_retained")),
    }


def build_site(audience: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    site = audience.get("site") if isinstance(audience.get("site"), dict) else {}
    if not site or not _configured(site):
        return None
    totals = site.get("totals") if isinstance(site.get("totals"), dict) else {}
    return {
        "fetched_at": site.get("fetched_at"),
        "days": _int_or_none(site.get("days")),
        "totals": {
            "active_users": _int_or_none(totals.get("active_users")),
            "sessions": _int_or_none(totals.get("sessions")),
        },
    }


def build_newsletter(
    audience: Dict[str, Any],
    headline: Dict[str, Any],
) -> Optional[Dict[str, Any]]:
    nl = (
        audience.get("newsletter")
        if isinstance(audience.get("newsletter"), dict)
        else {}
    )
    network = (
        headline.get("network")
        if isinstance(headline.get("network"), dict)
        else {}
    )
    count = None
    fetched_at = None
    if nl and _configured(nl):
        count = _int_or_none(nl.get("subscriber_count"))
        fetched_at = nl.get("fetched_at")
    if count is None:
        count = _int_or_none(network.get("newsletter_subscribers"))
    if fetched_at is None:
        fetched_at = (headline.get("sources") or {}).get("buttondown_fetched_at")
    if count is None and fetched_at is None and not (nl and _configured(nl)):
        return None
    return {
        "fetched_at": fetched_at,
        "subscriber_count": count,
    }


def build_contract(
    dashboard: Dict[str, Any],
    headline: Dict[str, Any],
    youtube_stats: Optional[Dict[str, Any]] = None,
    *,
    now: Optional[dt.datetime] = None,
) -> Dict[str, Any]:
    """Project dashboard + headline + youtube_stats into the v1 shape."""
    audience = (
        dashboard.get("audience")
        if isinstance(dashboard.get("audience"), dict)
        else {}
    )
    when = now or dt.datetime.now(dt.timezone.utc)
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": when.isoformat(),
        "op3": build_op3(audience, headline),
        "youtube": build_youtube(dashboard, youtube_stats),
        "spotify": build_spotify(audience),
        "apple": build_apple(audience, dashboard),
        "site": build_site(audience),
        "newsletter": build_newsletter(audience, headline),
    }


def build_from_root(
    root: Path, *, now: Optional[dt.datetime] = None
) -> Dict[str, Any]:
    dashboard = _load(root / "api" / "dashboard.json")
    headline = _load(root / "api" / "audience_headline.json")
    youtube_stats = _load(root / "api" / "youtube_stats.json")
    return build_contract(dashboard, headline, youtube_stats, now=now)


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--root", type=Path, default=PROJECT_ROOT)
    parser.add_argument(
        "--out",
        type=Path,
        default=None,
        help="default: <root>/api/audience_contract.json",
    )
    args = parser.parse_args(argv)

    doc = build_from_root(args.root)
    out = args.out or (args.root / "api" / "audience_contract.json")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        json.dumps(doc, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    measured = [k for k in TOP_LEVEL_KEYS[2:] if doc.get(k) is not None]
    log.info(
        "wrote %s (schema_version=%s, surfaces=%s)",
        out,
        doc["schema_version"],
        ",".join(measured) or "none",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
