#!/usr/bin/env python3
"""Fetch Apple Podcasts Connect analytics into ``api/apple_stats.json``.

OP3 already counts Apple *downloads* (Apple pulls the OP3-prefixed
enclosure like any RSS client), so this is NOT about download volume.
What Apple has and nothing else in the network does is **engagement**:
Followers, Plays, Listeners, and Time Listened — Apple is the only
platform that reports whether people actually finished an episode.

Apple ships **no official creator analytics API** (verified July 2026;
Podcasts Connect is a web dashboard only). This uses the community
`appleconnector <https://github.com/openpodcast/apple-connector>`_
package against the same unofficial endpoints the dashboard itself
calls, authenticated with two cookies from a logged-in
podcastsconnect.apple.com session:

* ``APPLE_MYACINFO`` — the ``myacinfo`` cookie (long, account auth)
* ``APPLE_ITCTX``    — the ``itctx`` cookie

This is the same trade-off already accepted for Spotify
(``fetch_spotify_stats.py``): unofficial + cookie auth, degrading to
stale data rather than a red nightly when the cookies expire. Apple can
change these endpoints without notice — treat a sustained all-shows
failure as "re-auth or drop the integration", never as data loss.

Show discovery: any ``shows/<slug>.yaml`` with an ``apple_show_id:``
key (the numeric ID visible in the Podcasts Connect show URL, e.g.
``6794048682``). No IDs configured → clean no-op, the same convention
every optional integration in this repo follows.

Usage::

    python scripts/fetch_apple_stats.py              # write api/apple_stats.json
    python scripts/fetch_apple_stats.py --dry-run    # print, write nothing
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import logging
import os
import sys
from pathlib import Path
from typing import Any

import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from engine.connector_budget import (  # noqa: E402  (after sys.path fix)
    FetchBudget,
    _env_float,
    _env_int,
    clamp_connector_retries,
)

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger("fetch_apple_stats")

WINDOW_DAYS = 30

# Same bounded-retry contract as the Spotify fetcher — six endpoints per
# show here, so an unbounded backoff loop would be even more expensive.
# (appleconnector spells its constant MAX_RETRY_ATTEMPTS, not
# MAX_REQUEST_ATTEMPTS; the clamp helper only writes what it finds.)
MAX_RETRY_ATTEMPTS = _env_int("APPLE_MAX_RETRY_ATTEMPTS", 3)
RETRY_DELAY_BASE = _env_float("APPLE_RETRY_DELAY_BASE", 1.0)
BUDGET_SECONDS = _env_float("APPLE_FETCH_BUDGET_SECONDS", 900.0)


def discover_show_ids() -> dict[str, str]:
    """slug → apple_show_id from the show YAMLs (dubs included)."""
    ids: dict[str, str] = {}
    for path in sorted((REPO_ROOT / "shows").glob("*.yaml")):
        if path.name.startswith("_"):
            continue
        try:
            data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        except yaml.YAMLError:
            continue
        if not isinstance(data, dict):
            continue
        podcast = data.get("podcast") if isinstance(data.get("podcast"), dict) else {}
        sid = data.get("apple_show_id") or podcast.get("apple_show_id")
        if sid is not None and str(sid).strip():
            ids[path.stem] = str(sid).strip()
        dubs = data.get("apple_show_ids") or podcast.get("apple_show_ids")
        if isinstance(dubs, dict):
            for lang, dsid in dubs.items():
                if dsid is not None and str(dsid).strip():
                    ids[f"{path.stem}_{lang}"] = str(dsid).strip()
    return ids


def _overview_scalars(overview: Any) -> dict[str, int]:
    """Pull the headline scalars out of an ``overview()`` response.

    This is the reliable source and it is what the Connect dashboard itself
    renders. ``overview.showPlayCount.latestValue`` carries::

        {"playscount": 2041.0, "uniquelistenerscount": 164.0,
         "uniqueengagedlistenerscount": 94.0, "totaltimelistened": 445323.0}

    and ``followerAllTimeTrends`` is ``[[yyyymmdd, followers, ...], ...]``.

    Why this exists: the previous implementation derived every scalar from
    the ``trends()`` payloads via :func:`_totals_from_trends`, which walks
    for dicts carrying ``value``/``count``/``total``. Those payloads put
    their data in ``content`` as a **list of lists of scalars**, so no key
    ever matched, every metric came back ``None``, and the dashboard summed
    those into a confident-looking ``0`` — while 4,486 real plays across 14
    shows sat in this field, fetched and then discarded. The failure was
    invisible because a parse miss produces no ``errors`` entry, so the
    "cookies expired" hint could never fire for it either.

    Returns only the keys it could actually read, so a missing metric stays
    absent (rendered "—") rather than becoming a false zero.
    """
    if not isinstance(overview, dict):
        return {}
    out: dict[str, int] = {}

    latest = (overview.get("showPlayCount") or {}).get("latestValue") or {}
    if isinstance(latest, dict):
        for key, field in (
            ("plays", "playscount"),
            ("listeners", "uniquelistenerscount"),
            ("engaged_listeners", "uniqueengagedlistenerscount"),
            ("time_listened", "totaltimelistened"),
        ):
            val = latest.get(field)
            if isinstance(val, (int, float)) and not isinstance(val, bool):
                out[key] = int(val)

    # [[yyyymmdd, followers, ...]] — newest row last. An empty list means
    # Apple has no follower data for this show, which is not zero followers.
    trends = overview.get("followerAllTimeTrends")
    if isinstance(trends, list) and trends:
        row = trends[-1]
        if isinstance(row, list) and len(row) >= 2:
            val = row[1]
            if isinstance(val, (int, float)) and not isinstance(val, bool):
                out["followers"] = int(val)

    return out


def _totals_from_trends(payload: Any) -> int | None:
    """Best-effort scalar total out of a trends() response.

    Retained as a FALLBACK only — :func:`_overview_scalars` is the primary
    source. Kept because the trends payload shape has shifted before and
    may grow dict-shaped nodes again; when it does, this picks them up
    without another outage.

    The unofficial endpoint's shape shifts; rather than pin one schema we
    walk the common containers and sum any numeric ``value``/``count``.
    Returns None when nothing numeric is found (rendered as "—").
    """
    if payload is None:
        return None
    total = 0
    found = False

    def _walk(node: Any) -> None:
        nonlocal total, found
        if isinstance(node, dict):
            for key in ("value", "count", "total"):
                v = node.get(key)
                if isinstance(v, (int, float)) and not isinstance(v, bool):
                    total += v
                    found = True
                    return
            for v in node.values():
                _walk(v)
        elif isinstance(node, list):
            for v in node:
                _walk(v)

    _walk(payload)
    return int(total) if found else None


def fetch_show(myacinfo: str, itctx: str, show_id: str) -> dict[str, Any]:
    """Best-effort per-show fetch; per-call errors are recorded, not raised."""
    from appleconnector import AppleConnector, Metric, Mode

    connector = AppleConnector(
        podcast_id=show_id, myacinfo=myacinfo, itctx=itctx)
    end = dt.date.today()  # noqa: DTZ011 — Apple reports in local dates
    start = end - dt.timedelta(days=WINDOW_DAYS)
    result: dict[str, Any] = {"show_id": show_id}

    calls = [
        ("overview", lambda: connector.overview(start=start, end=end)),
        ("episodes", lambda: connector.episodes(date=start, mode=Mode.ROLLING_60)),
    ]
    for metric_name, metric in (
        ("plays", Metric.PLAYS),
        ("listeners", Metric.LISTENERS),
        ("followers", Metric.FOLLOWERS),
        ("time_listened", Metric.TIME_LISTENED),
    ):
        calls.append((
            f"trend_{metric_name}",
            lambda m=metric: connector.trends(start=start, end=end, metric=m),
        ))

    for name, call in calls:
        try:
            result[name] = call()
        except Exception as exc:  # noqa: BLE001 — one endpoint must not kill the show
            result.setdefault("errors", {})[name] = str(exc)[:300]

    # Compact scalars the dashboard renders without knowing the raw shape.
    # The overview is authoritative — it is what Connect's own dashboard
    # shows. Trends are consulted only for anything the overview omits, so
    # a future shape change on either side degrades rather than zeroes.
    scalars = _overview_scalars(result.get("overview"))
    for metric_name in ("plays", "listeners", "followers",
                        "time_listened", "engaged_listeners"):
        if metric_name in scalars:
            result[metric_name] = scalars[metric_name]
            continue
        val = _totals_from_trends(result.get(f"trend_{metric_name}"))
        if val is not None:
            result[metric_name] = val

    # A show that returned neither an overview nor any usable trend is not
    # a show with zero plays — record it so the dashboard can tell the two
    # apart instead of rendering a confident 0.
    if not any(k in result for k in ("plays", "listeners", "followers",
                                     "time_listened")):
        result["no_data"] = True
    return result


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Fetch Apple Podcasts Connect analytics")
    parser.add_argument("--out", default=str(REPO_ROOT / "api" / "apple_stats.json"))
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)

    myacinfo = os.getenv("APPLE_MYACINFO", "").strip()
    itctx = os.getenv("APPLE_ITCTX", "").strip()
    if not (myacinfo and itctx):
        logger.info("APPLE_MYACINFO / APPLE_ITCTX unset — skipping Apple "
                    "fetch (clean no-op)")
        return 0

    show_ids = discover_show_ids()
    if not show_ids:
        logger.info("no apple_show_id configured in any shows/*.yaml — "
                    "skipping (record the numeric ID from each show's "
                    "Podcasts Connect URL)")
        return 0

    try:
        import appleconnector  # noqa: F401
        from appleconnector import connector as _connector_mod
    except ImportError:
        logger.error("appleconnector not installed — add it to "
                     "requirements.txt / pip install appleconnector")
        return 0

    applied = clamp_connector_retries(
        _connector_mod,
        attempts_attr="MAX_RETRY_ATTEMPTS",
        delay_attr="DELAY_BASE",
        attempts=MAX_RETRY_ATTEMPTS,
        delay_base=RETRY_DELAY_BASE,
    )
    if applied:
        logger.info("connector retry budget: %s", applied)
    else:
        logger.warning(
            "appleconnector no longer exposes MAX_RETRY_ATTEMPTS / "
            "DELAY_BASE — retries are UNBOUNDED this run; the wall-clock "
            "budget is the only guard left")

    out = Path(args.out)
    previous_shows: dict[str, Any] = {}
    if out.exists():
        try:
            previous_shows = (json.loads(
                out.read_text(encoding="utf-8")) or {}).get("shows") or {}
        except Exception:  # noqa: BLE001
            previous_shows = {}

    budget = FetchBudget(seconds=BUDGET_SECONDS)
    shows: dict[str, Any] = {}
    failures = 0
    skipped: list[str] = []
    for slug, sid in show_ids.items():
        if budget.exhausted():
            skipped.append(slug)
            prior = previous_shows.get(slug)
            if isinstance(prior, dict):
                shows[slug] = {**prior, "not_refreshed_this_run": True}
            continue
        try:
            shows[slug] = fetch_show(myacinfo, itctx, sid)
            if len(shows[slug].get("errors") or {}) >= 4:
                failures += 1
        except Exception as exc:  # noqa: BLE001
            shows[slug] = {"show_id": sid, "errors": {"fatal": str(exc)[:300]}}
            failures += 1
        logger.info("fetched %s (%s)", slug, sid)

    if skipped:
        logger.warning(
            "::warning::apple fetch budget of %.0fs expired after %d of %d "
            "shows — %s kept their previous entry.", BUDGET_SECONDS,
            len(show_ids) - len(skipped), len(show_ids), ", ".join(skipped))
    logger.info("apple fetch took %.0fs for %d shows",
                budget.elapsed(), len(show_ids) - len(skipped))

    if show_ids and failures == len(show_ids):
        logger.error(
            "every Apple fetch failed — the myacinfo/itctx cookies have "
            "likely EXPIRED. Re-extract them from a logged-in "
            "podcastsconnect.apple.com session (dev tools → Application → "
            "Cookies) and update the APPLE_MYACINFO / APPLE_ITCTX repo "
            "secrets.")
        return 0  # degrade to stale data, never a red nightly

    data = {
        "fetched_at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "window_days": WINDOW_DAYS,
        "shows": shows,
    }
    if args.dry_run:
        print(json.dumps(data, indent=2, default=str)[:4000])
        return 0
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(data, indent=2, default=str) + "\n", encoding="utf-8")
    logger.info("wrote %s (%d shows)", out, len(shows))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
