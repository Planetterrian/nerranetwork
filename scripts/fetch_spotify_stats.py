#!/usr/bin/env python3
"""Fetch Spotify podcast analytics into ``api/spotify_stats.json``.

Spotify re-hosts podcast audio, so its plays never hit the OP3-prefixed
enclosure URLs — Spotify listening is invisible to ``api/op3_stats.json``
and must be fetched from Spotify itself. There is **no official creator
API**; this uses the community `spotifyconnector
<https://github.com/openpodcast/spotify-connector>`_ package, which
authenticates with two session cookies extracted from a logged-in
podcasters.spotify.com browser session:

* ``SPOTIFY_SP_DC``  — the ``sp_dc`` cookie (~160 chars)
* ``SPOTIFY_SP_KEY`` — the ``sp_key`` cookie (36-char UUID)

Cookies live for months but do eventually expire. When every show's
fetch fails, this script logs a loud re-auth hint (and still exits 0 —
stale cookies must degrade to stale data, never a red nightly).

**Runtime is bounded.** A registered feed with no plays yet answers
``500`` on ``/metadata`` and ``/aggregate`` every night, and the
connector's built-in retry loop spends ~124s of exponential backoff on
each such endpoint. With 18 of 24 feeds in that state (measured
2026-07-25) the step ran for over an hour. ``engine.connector_budget``
clamps the retry constants and enforces a wall-clock budget; shows not
reached before the budget expires keep their previously fetched entry.

Show discovery: any ``shows/<slug>.yaml`` with a top-level or
``podcast:``-level ``spotify_show_id:`` key. The operator adds the ID
after submitting each feed at podcasters.spotify.com (it's the
22-character ID in the show URL). No IDs configured → clean no-op,
same convention as every optional integration in this repo.

Usage::

    python scripts/fetch_spotify_stats.py                # write api/spotify_stats.json
    python scripts/fetch_spotify_stats.py --dry-run      # print, write nothing
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import logging
import os
import sys
from pathlib import Path
from typing import Any, Dict

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
logger = logging.getLogger("fetch_spotify_stats")

# Retry budget for the vendored connector's request loop. Three attempts
# with a 1s base costs ~6s of backoff on a permanently-500 endpoint
# (vs ~124s at the package defaults) while still riding out a genuine
# transient. Overridable per-run if Spotify ever gets flakier.
MAX_REQUEST_ATTEMPTS = _env_int("SPOTIFY_MAX_REQUEST_ATTEMPTS", 3)
RETRY_DELAY_BASE = _env_float("SPOTIFY_RETRY_DELAY_BASE", 1.0)
# Hard wall-clock stop for the whole multi-show loop (0 disables).
BUDGET_SECONDS = _env_float("SPOTIFY_FETCH_BUDGET_SECONDS", 900.0)

BASE_URL = os.getenv("SPOTIFY_CONNECTOR_BASE_URL",
                     "https://generic.wg.spotify.com/podcasters/v0")
CLIENT_ID = os.getenv("SPOTIFY_CONNECTOR_CLIENT_ID",
                      "05a1371ee5194c27860b3ff3ff3979d2")


def discover_show_ids() -> Dict[str, str]:
    """slug → spotify_show_id from the show YAMLs."""
    ids: Dict[str, str] = {}
    for path in sorted((REPO_ROOT / "shows").glob("*.yaml")):
        if path.name.startswith("_"):
            continue
        try:
            data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        except yaml.YAMLError:
            continue
        if not isinstance(data, dict):
            continue
        sid = data.get("spotify_show_id") or (
            (data.get("podcast") or {}).get("spotify_show_id")
            if isinstance(data.get("podcast"), dict) else None)
        if isinstance(sid, str) and sid.strip():
            ids[path.stem] = sid.strip()
        dubs = data.get("spotify_show_ids") or (
            (data.get("podcast") or {}).get("spotify_show_ids")
            if isinstance(data.get("podcast"), dict) else None)
        if isinstance(dubs, dict):
            for lang, dsid in dubs.items():
                if isinstance(dsid, str) and dsid.strip():
                    ids[f"{path.stem}_{lang}"] = dsid.strip()
    return ids


def fetch_show(sp_dc: str, sp_key: str, show_id: str) -> Dict[str, Any]:
    """Best-effort per-show fetch; records per-call errors instead of
    raising, since the unofficial endpoints shift shape now and then."""
    from spotifyconnector import SpotifyConnector

    connector = SpotifyConnector(
        base_url=BASE_URL, client_id=CLIENT_ID, podcast_id=show_id,
        sp_dc=sp_dc, sp_key=sp_key,
    )
    end = dt.date.today()
    start = end - dt.timedelta(days=30)
    result: Dict[str, Any] = {"show_id": show_id}

    for name, call in (
        ("metadata", lambda: connector.metadata()),
        ("listeners_30d", lambda: connector.listeners(start, end)),
        ("aggregate_30d", lambda: connector.aggregate(start, end)),
    ):
        try:
            result[name] = call()
        except Exception as exc:  # noqa: BLE001
            result.setdefault("errors", {})[name] = str(exc)
    # Compact convenience fields when metadata came through.
    meta = result.get("metadata") or {}
    if isinstance(meta, dict):
        for key in ("totalEpisodes", "followers", "starts", "streams",
                    "listeners"):
            if key in meta:
                result[key] = meta[key]
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", default=str(REPO_ROOT / "api"
                                             / "spotify_stats.json"))
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    sp_dc = os.getenv("SPOTIFY_SP_DC", "").strip()
    sp_key = os.getenv("SPOTIFY_SP_KEY", "").strip()
    if not (sp_dc and sp_key):
        logger.info("SPOTIFY_SP_DC / SPOTIFY_SP_KEY unset — skipping "
                    "Spotify fetch (clean no-op)")
        return 0

    show_ids = discover_show_ids()
    if not show_ids:
        logger.info("no spotify_show_id configured in any shows/*.yaml — "
                    "skipping (add IDs after submitting feeds)")
        return 0

    try:
        import spotifyconnector  # noqa: F401
        from spotifyconnector import connector as _connector_mod
    except ImportError:
        logger.error("spotifyconnector not installed — add it to "
                     "requirements.txt / pip install spotifyconnector")
        return 0

    applied = clamp_connector_retries(
        _connector_mod,
        attempts_attr="MAX_REQUEST_ATTEMPTS",
        delay_attr="DELAY_BASE",
        attempts=MAX_REQUEST_ATTEMPTS,
        delay_base=RETRY_DELAY_BASE,
    )
    if applied:
        logger.info("connector retry budget: %s", applied)
    else:
        logger.warning(
            "spotifyconnector no longer exposes MAX_REQUEST_ATTEMPTS / "
            "DELAY_BASE — retries are UNBOUNDED this run; the wall-clock "
            "budget is the only guard left")

    # Carry forward last-good entries so a budget stop leaves the file
    # complete rather than silently shrinking the show list.
    previous_shows: Dict[str, Any] = {}
    out_path = Path(args.out)
    if out_path.exists():
        try:
            previous_shows = (json.loads(
                out_path.read_text(encoding="utf-8")) or {}).get("shows") or {}
        except Exception:  # noqa: BLE001
            previous_shows = {}

    budget = FetchBudget(seconds=BUDGET_SECONDS)
    shows: Dict[str, Any] = {}
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
            shows[slug] = fetch_show(sp_dc, sp_key, sid)
            if shows[slug].get("errors") and len(
                    shows[slug]["errors"]) >= 3:
                failures += 1
        except Exception as exc:  # noqa: BLE001
            shows[slug] = {"show_id": sid, "errors": {"fatal": str(exc)}}
            failures += 1
        logger.info("fetched %s (%s)", slug, sid)

    if skipped:
        logger.warning(
            "::warning::spotify fetch budget of %.0fs expired after %d of "
            "%d shows — %s kept their previous entry. Raise "
            "SPOTIFY_FETCH_BUDGET_SECONDS or investigate why the endpoints "
            "are slow.", BUDGET_SECONDS, len(show_ids) - len(skipped),
            len(show_ids), ", ".join(skipped))
    logger.info("spotify fetch took %.0fs for %d shows",
                budget.elapsed(), len(show_ids) - len(skipped))

    if show_ids and failures == len(show_ids):
        logger.error(
            "every Spotify fetch failed — the sp_dc/sp_key cookies have "
            "likely EXPIRED. Re-extract them from a logged-in "
            "podcasters.spotify.com session and update the "
            "SPOTIFY_SP_DC / SPOTIFY_SP_KEY repo secrets.")
        return 0  # degrade to stale data, never a red nightly

    data = {
        "fetched_at": dt.datetime.now(dt.timezone.utc).isoformat(
            timespec="seconds"),
        "window_days": 30,
        "shows": shows,
    }
    if args.dry_run:
        print(json.dumps(data, indent=2, default=str)[:4000])
        return 0
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(data, indent=2, default=str) + "\n",
                        encoding="utf-8")
    logger.info("wrote %s (%d shows)", out_path, len(shows))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
