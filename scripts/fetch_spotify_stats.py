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
from pathlib import Path
from typing import Any, Dict

import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger("fetch_spotify_stats")

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
    except ImportError:
        logger.error("spotifyconnector not installed — add it to "
                     "requirements.txt / pip install spotifyconnector")
        return 0

    shows: Dict[str, Any] = {}
    failures = 0
    for slug, sid in show_ids.items():
        try:
            shows[slug] = fetch_show(sp_dc, sp_key, sid)
            if shows[slug].get("errors") and len(
                    shows[slug]["errors"]) >= 3:
                failures += 1
        except Exception as exc:  # noqa: BLE001
            shows[slug] = {"show_id": sid, "errors": {"fatal": str(exc)}}
            failures += 1
        logger.info("fetched %s (%s)", slug, sid)

    if failures == len(show_ids):
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
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(data, indent=2, default=str) + "\n",
                   encoding="utf-8")
    logger.info("wrote %s (%d shows)", out, len(shows))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
