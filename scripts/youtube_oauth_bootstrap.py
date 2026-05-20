#!/usr/bin/env python3
"""One-time OAuth refresh-token bootstrap for the YouTube publishing pipeline.

Run **locally** (not in CI) — this script opens a browser, walks the
Google OAuth consent flow, and prints the resulting refresh token. Paste
the token into the appropriate GitHub Secret:

  - English channel  → ``YOUTUBE_REFRESH_TOKEN_EN``
  - Russian channel  → ``YOUTUBE_REFRESH_TOKEN_RU``

You'll also need to create a Google Cloud project, enable the YouTube
Data API v3, and download an OAuth 2.0 "Desktop app" client_secrets JSON.
See ``docs/youtube_setup.md`` for the full sequence.

Usage::

    python scripts/youtube_oauth_bootstrap.py path/to/client_secrets.json

The token is granted ``youtube.upload`` + ``youtube`` scopes (the second
is needed for ``thumbnails.set`` and channel reads). Run once per
channel, signing into the matching Google account each time.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


SCOPES = [
    "https://www.googleapis.com/auth/youtube.upload",
    "https://www.googleapis.com/auth/youtube",
    # Required for captions.insert (CC track upload after long-form).
    "https://www.googleapis.com/auth/youtube.force-ssl",
]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument(
        "client_secrets",
        type=Path,
        help="Path to the OAuth 2.0 client secrets JSON downloaded from "
             "Google Cloud Console (Desktop application credential type).",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=0,
        help="Port for the local OAuth callback server (0 = pick automatically).",
    )
    args = parser.parse_args()

    if not args.client_secrets.exists():
        print(f"client_secrets not found: {args.client_secrets}",
              file=sys.stderr)
        return 1

    try:
        from google_auth_oauthlib.flow import InstalledAppFlow
    except ImportError:
        print(
            "google-auth-oauthlib is not installed. Run "
            "`pip install google-auth-oauthlib` and try again.",
            file=sys.stderr,
        )
        return 1

    flow = InstalledAppFlow.from_client_secrets_file(
        str(args.client_secrets), SCOPES,
    )
    print(
        "Opening browser for consent. Sign in with the Google account "
        "that owns the target YouTube channel."
    )
    creds = flow.run_local_server(port=args.port, prompt="consent",
                                  access_type="offline")

    if not creds.refresh_token:
        print(
            "ERROR: Google did not return a refresh token. This usually "
            "means the consent screen was not shown (e.g. you've already "
            "authorized this client). Revoke access at "
            "https://myaccount.google.com/permissions and re-run.",
            file=sys.stderr,
        )
        return 2

    print()
    print("=" * 68)
    print("SUCCESS — paste the value below into the matching GitHub secret")
    print("(YOUTUBE_REFRESH_TOKEN_EN or YOUTUBE_REFRESH_TOKEN_RU):")
    print("=" * 68)
    print(creds.refresh_token)
    print("=" * 68)
    print()
    print("Also set these once (same for both channels):")
    print(f"  YOUTUBE_CLIENT_ID     = {creds.client_id}")
    print(f"  YOUTUBE_CLIENT_SECRET = {creds.client_secret}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
