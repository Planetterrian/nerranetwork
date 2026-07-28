#!/usr/bin/env python3
"""Report whether each YouTube channel token can upload caption tracks.

``captions.insert`` requires the ``youtube.force-ssl`` OAuth scope.
Tokens minted before that scope was added to ``YOUTUBE_SCOPES`` do not
carry it, and the failure is quiet by design: ``engine.youtube`` logs a
warning and returns False so a caption problem can never cost the video
upload. The cost of that quietness is that a channel can go months
shipping episodes with **no selectable CC track** — which also disables
YouTube's automatic caption translation, the cheapest international
reach the network has — while every run still reports success.

This makes the state visible without waiting for a run: it asks Google
what scopes each refresh token actually holds.

Usage::

    python scripts/check_youtube_caption_scope.py
    python scripts/check_youtube_caption_scope.py --channel fr

Exit status is 1 if any configured channel is missing the scope, so it
can gate a workflow step.

Fix when a channel fails: re-run the OAuth consent flow for that channel
with ``https://www.googleapis.com/auth/youtube.force-ssl`` included, and
replace that channel's ``YOUTUBE_REFRESH_TOKEN*`` secret. The videos
already uploaded stay as they are — captions can be added to them
afterwards, but the pipeline only attaches them at upload time.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.parse
import urllib.request
from pathlib import Path
from typing import List

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

FORCE_SSL = "https://www.googleapis.com/auth/youtube.force-ssl"
_TOKEN_URL = "https://oauth2.googleapis.com/token"

CHANNELS = ["en", "fr", "ru", "es", "zh"]


def _refresh_token_env(channel: str) -> str:
    """Mirrors engine.youtube.get_channel_credentials_from_env exactly.

    Every channel takes a suffix — ``en`` is ``YOUTUBE_REFRESH_TOKEN_EN``,
    not the bare name — while the client id and secret are shared across
    channels. Getting this wrong would report "not configured" for a
    channel that is in fact live, which is the opposite of useful.
    """
    import re as _re

    ch = (channel or "en").strip().lower() or "en"
    suffix = _re.sub(r"[^A-Z0-9]", "", ch.upper()) or "EN"
    return f"YOUTUBE_REFRESH_TOKEN_{suffix}"


def _granted_scopes(channel: str) -> List[str]:
    """Exchange the refresh token and read the scopes Google returns."""
    refresh = os.getenv(_refresh_token_env(channel), "").strip()
    client_id = os.getenv("YOUTUBE_CLIENT_ID", "").strip()
    secret = os.getenv("YOUTUBE_CLIENT_SECRET", "").strip()
    if not (refresh and client_id and secret):
        raise LookupError("not configured")

    body = urllib.parse.urlencode({
        "client_id": client_id,
        "client_secret": secret,
        "refresh_token": refresh,
        "grant_type": "refresh_token",
    }).encode()
    req = urllib.request.Request(
        _TOKEN_URL, data=body,
        headers={"Content-Type": "application/x-www-form-urlencoded"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        payload = json.loads(resp.read().decode())
    # Google returns the granted scopes space-delimited on refresh.
    return (payload.get("scope") or "").split()


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--channel", default="", help="Check one channel only")
    args = ap.parse_args()

    channels = [args.channel] if args.channel else CHANNELS
    failures = 0
    checked = 0

    for channel in channels:
        try:
            scopes = _granted_scopes(channel)
        except LookupError:
            print(f"{channel:<4} not configured — skipped")
            continue
        except Exception as exc:  # noqa: BLE001 — report, don't crash
            print(f"{channel:<4} ERROR  could not refresh token: {exc}")
            failures += 1
            continue

        checked += 1
        if FORCE_SSL in scopes:
            print(f"{channel:<4} OK     caption uploads will work")
        else:
            failures += 1
            print(f"{channel:<4} FAIL   missing youtube.force-ssl — every "
                  f"caption track upload on this channel is silently "
                  f"rejected with HTTP 403")
            print(f"       granted: {' '.join(scopes) or '(none reported)'}")

    if not checked:
        print("\nNo channels configured in this environment. Run this where "
              "the YOUTUBE_* secrets are available.")
        return 0
    if failures:
        print(f"\n{failures} channel(s) need re-consent with {FORCE_SSL}")
    else:
        print("\nAll configured channels can upload captions.")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
