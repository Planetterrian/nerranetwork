#!/usr/bin/env python3
"""Create YouTube playlists for every Nerra Network show, set them as
podcasts, and write the resulting playlist IDs into shows/<slug>.yaml.

This bypasses the Studio UI (which sometimes throws "Oops, something
went wrong" on brand-new brand-account channels) by going straight to
the YouTube Data API ``playlists.insert`` endpoint with the
``podcastStatus="enabled"`` flag.

Run once per channel (English + Russian). The script:

  1. Walks the standard ``InstalledAppFlow`` for the channel you choose
     at the brand-account picker.
  2. For every show whose ``shows/<slug>.yaml`` has ``youtube.channel:``
     matching the channel you picked, creates a public playlist named
     after the show, sets it as a podcast, and prints the playlist ID.
  3. Writes the IDs into the show YAMLs in-place.

Usage::

    # Run from repo root
    python3 scripts/create_youtube_playlists.py path/to/client_secrets.json en
    python3 scripts/create_youtube_playlists.py path/to/client_secrets.json ru

The ``client_secrets.json`` file is the same Desktop-app OAuth credential
you used for the publish-pipeline bootstrap. If you deleted it, re-download
from Google Cloud Console → APIs & Services → Credentials.

You'll see the same "Google hasn't verified this app" warning during
consent — Advanced → Continue.

If a show already has ``podcast_playlist_id:`` set, it's skipped (idempotent).
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Dict


SCOPES = ["https://www.googleapis.com/auth/youtube"]


# Display titles + descriptions for each show. Keep in sync with
# shows/<slug>.yaml ``name`` if you ever rename a show.
SHOWS: Dict[str, Dict[str, str]] = {
    # English channel (Nerra Network)
    "tesla": {
        "channel": "en",
        "title": "Tesla Shorts Time Daily",
        "description": (
            "Daily AI-narrated podcast covering everything Tesla — "
            "Full Self-Driving updates, earnings, factory news, the "
            "Musk-iverse, and the EV market at large. Editorial content "
            "is curated and written by Patrick from primary news sources; "
            "narration is AI-synthesized (ElevenLabs). New episode every day.\n\n"
            "https://nerranetwork.com/tesla.html"
        ),
        "default_language": "en",
    },
    "fascinating_frontiers": {
        "channel": "en",
        "title": "Fascinating Frontiers",
        "description": (
            "Space, astronomy, and the science of frontier exploration — "
            "from SpaceX launch coverage to NASA missions to deep-space "
            "discoveries. AI-narrated, editorially curated by Nerra Network.\n\n"
            "https://nerranetwork.com/fascinating-frontiers.html"
        ),
        "default_language": "en",
    },
    "models_agents": {
        "channel": "en",
        "title": "Models & Agents",
        "description": (
            "Daily AI industry briefing — frontier model releases, agent "
            "frameworks, OpenAI/Anthropic/Google/Meta news, and the build "
            "patterns that work in production. AI-narrated, editorially "
            "curated by Nerra Network.\n\n"
            "https://nerranetwork.com/models-agents.html"
        ),
        "default_language": "en",
    },
    "models_agents_beginners": {
        "channel": "en",
        "title": "Models & Agents for Beginners",
        "description": (
            "AI explained from first principles for newcomers and teens. "
            "Same daily AI news as Models & Agents, rewritten without the "
            "jargon. AI-narrated, editorially curated by Nerra Network.\n\n"
            "https://nerranetwork.com/models-agents-beginners.html"
        ),
        "default_language": "en",
    },
    "modern_investing": {
        "channel": "en",
        "title": "Modern Investing Techniques",
        "description": (
            "Daily investing podcast covering Canadian and US markets, "
            "portfolio construction, and the lessons we're learning out "
            "loud. AI-narrated, editorially curated by Nerra Network.\n\n"
            "https://nerranetwork.com/modern-investing.html"
        ),
        "default_language": "en",
    },
    "omni_view": {
        "channel": "en",
        "title": "Omni View",
        "description": (
            "Balanced news from across the political spectrum — multiple "
            "sources, multiple framings, on the day's biggest stories. "
            "AI-narrated, editorially curated by Nerra Network.\n\n"
            "https://nerranetwork.com/omni-view.html"
        ),
        "default_language": "en",
    },
    "planetterrian": {
        "channel": "en",
        "title": "Planetterrian Daily",
        "description": (
            "Longevity, neuroscience, and frontier health science — what "
            "the latest research actually says and what to do with it. "
            "AI-narrated, editorially curated by Nerra Network.\n\n"
            "https://nerranetwork.com/planetterrian.html"
        ),
        "default_language": "en",
    },
    "env_intel": {
        "channel": "en",
        "title": "Env Intel",
        "description": (
            "Environmental compliance, climate policy, and sustainability "
            "news for Canadian operators. AI-narrated, editorially curated "
            "by Nerra Network.\n\n"
            "https://nerranetwork.com/env-intel.html"
        ),
        "default_language": "en",
    },

    # Russian channel (Nerra RU)
    "finansy_prosto": {
        "channel": "ru",
        "title": "Финансы Просто",
        "description": (
            "Финансовая грамотность для русскоговорящих женщин в Канаде. "
            "Сбережения, инвестиции, налоги, RRSP / TFSA — простым языком, "
            "несколько раз в неделю. Озвучка AI (ElevenLabs), редактура "
            "Nerra Network.\n\n"
            "https://nerranetwork.com/ru/finansy-prosto.html"
        ),
        "default_language": "ru",
    },
    "privet_russian": {
        "channel": "ru",
        "title": "Привет, Русский!",
        "description": (
            "Двуязычный подкаст для изучающих русский язык. Реальные "
            "разговоры, грамматика и культура — параллельно по-английски "
            "и по-русски. Озвучка AI (ElevenLabs), уроки от Nerra Network.\n\n"
            "https://nerranetwork.com/ru/privet-russian.html"
        ),
        "default_language": "ru",
    },
    # Nov 4 2026: the first two launch-cohort shows on the EN channel.
    "ai_chips": {
        "channel": "en",
        "title": "AI Chips & Data Centres Daily",
        "description": (
            "The silicon, the buildings and the power behind AI. Every day: "
            "the chips and systems that shipped, the data centres that broke "
            "ground or switched on, and the grid, cooling and supply-chain "
            "constraints underneath them, with the numbers. AI-narrated, "
            "every story sourced, from the Nerra Network.\n\n"
            "https://nerranetwork.com/ai-chips.html"
        ),
        "default_language": "en",
    },
    "mag7": {
        "channel": "en",
        "title": "MAG 7 Daily",
        "description": (
            "Alphabet, Amazon, Apple, Meta, Microsoft, NVIDIA and Tesla as "
            "one daily desk: what they shipped, the research they published "
            "and the rulings and deals that change what they can do. "
            "Developments and numbers, never picks. Not financial advice. "
            "AI-narrated, every story sourced, from the Nerra Network.\n\n"
            "https://nerranetwork.com/mag7.html"
        ),
        "default_language": "en",
    },
}


REPO_ROOT = Path(__file__).resolve().parent.parent
SHOWS_DIR = REPO_ROOT / "shows"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Create YouTube podcast playlists and write IDs to YAMLs."
    )
    parser.add_argument(
        "client_secrets",
        type=Path,
        help="Path to the OAuth Desktop client secrets JSON.",
    )
    parser.add_argument(
        "channel",
        choices=["en", "ru"],
        help="Which channel to authorize against ('en' = Nerra Network, "
             "'ru' = Nerra RU).",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=0,
        help="OAuth callback port (0 = pick automatically).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print what would be created without calling YouTube.",
    )
    return parser.parse_args()


def get_youtube_client(client_secrets: Path, port: int):
    try:
        from google_auth_oauthlib.flow import InstalledAppFlow
        from googleapiclient.discovery import build
    except ImportError:
        sys.exit(
            "Run `pip3 install google-auth-oauthlib google-api-python-client` "
            "and try again."
        )

    flow = InstalledAppFlow.from_client_secrets_file(str(client_secrets), SCOPES)
    print("Opening browser. Sign in with the Google account that owns the "
          "channel; pick the matching brand account at the picker.")
    creds = flow.run_local_server(port=port, prompt="consent",
                                  access_type="offline")
    return build("youtube", "v3", credentials=creds)


EXPECTED_CHANNEL_TITLE = {
    "en": "Nerra Network",
    "ru": "Nerra RU",
}


def confirm_active_channel(youtube, channel_arg: str) -> str:
    """Verify the currently authorized channel matches the one the
    operator picked at the CLI. Aborts (no playlists created) on
    mismatch — this guards against Google silently re-using a previous
    grant for the wrong brand account.
    """
    resp = youtube.channels().list(part="snippet", mine=True).execute()
    items = resp.get("items", [])
    if not items:
        sys.exit("No channel found for this OAuth token.")
    title = items[0]["snippet"]["title"]
    chan_id = items[0]["id"]
    print(f"Authorized channel: {title}  (id={chan_id})")

    expected = EXPECTED_CHANNEL_TITLE[channel_arg]
    if title.strip().casefold() != expected.casefold():
        print()
        print(f"❌ ABORT: expected channel '{expected}', got '{title}'.")
        print()
        print("This usually happens because Google silently re-used a")
        print("previous OAuth grant. Fix:")
        print("  1. Open https://myaccount.google.com/permissions")
        print("  2. Find 'Nerra Network YouTube Uploader', click Remove access")
        print("  3. Re-run this script — Google will then show the brand")
        print("     account picker. Pick the correct channel.")
        print()
        print("No playlists were created. No YAMLs were modified.")
        sys.exit(2)

    return title


def create_one_playlist(youtube, *, title: str, description: str,
                        default_language: str) -> str:
    """POST /youtube/v3/playlists with ``podcastStatus=enabled``.

    Returns the new playlist's ID.
    """
    body = {
        "snippet": {
            "title": title,
            "description": description,
            "defaultLanguage": default_language,
        },
        "status": {
            "privacyStatus": "public",
            "podcastStatus": "enabled",
        },
    }
    resp = youtube.playlists().insert(
        part="snippet,status",
        body=body,
    ).execute()
    return resp["id"]


PLAYLIST_ID_LINE = re.compile(r"^(\s*)podcast_playlist_id:\s*(.*)$", re.M)
YOUTUBE_BLOCK_HEAD = re.compile(r"^youtube:\s*$", re.M)


def update_yaml_with_playlist_id(yaml_path: Path, playlist_id: str) -> None:
    """In-place edit shows/<slug>.yaml so the youtube: block has
    ``podcast_playlist_id: PL...``.

    Replaces an existing line if present; otherwise inserts a new line
    immediately after the ``youtube:`` block header.
    """
    text = yaml_path.read_text()

    if PLAYLIST_ID_LINE.search(text):
        new_text = PLAYLIST_ID_LINE.sub(
            lambda m: f"{m.group(1)}podcast_playlist_id: {playlist_id}",
            text,
        )
    else:
        match = YOUTUBE_BLOCK_HEAD.search(text)
        if not match:
            print(f"  WARNING: no `youtube:` block in {yaml_path.name} — "
                  f"appending one")
            new_text = (
                text.rstrip()
                + "\n\nyoutube:\n"
                f"  podcast_playlist_id: {playlist_id}\n"
            )
        else:
            insert_at = match.end()
            new_text = (
                text[:insert_at]
                + f"\n  podcast_playlist_id: {playlist_id}"
                + text[insert_at:]
            )

    yaml_path.write_text(new_text)


def yaml_already_has_id(yaml_path: Path) -> bool:
    text = yaml_path.read_text()
    m = PLAYLIST_ID_LINE.search(text)
    if not m:
        return False
    value = m.group(2).strip()
    return bool(value) and value != "null" and value.lower() != "none"


def main() -> int:
    args = parse_args()

    if not args.client_secrets.exists():
        sys.exit(f"client_secrets not found: {args.client_secrets}")

    eligible = {
        slug: meta for slug, meta in SHOWS.items()
        if meta["channel"] == args.channel
    }
    if not eligible:
        sys.exit(f"No shows configured for channel='{args.channel}'.")

    print(f"\nWill create {len(eligible)} playlists on the "
          f"{'Nerra Network' if args.channel == 'en' else 'Nerra RU'} "
          f"channel:\n")
    for slug, meta in eligible.items():
        print(f"  - {slug:30s}  →  {meta['title']}")
    print()

    if args.dry_run:
        print("Dry run — no playlists created, no YAMLs touched.")
        return 0

    youtube = get_youtube_client(args.client_secrets, args.port)
    confirm_active_channel(youtube, args.channel)

    results: Dict[str, str] = {}
    for slug, meta in eligible.items():
        yaml_path = SHOWS_DIR / f"{slug}.yaml"
        if not yaml_path.exists():
            print(f"  ⚠️  {slug}: shows/{slug}.yaml not found — skipping")
            continue
        if yaml_already_has_id(yaml_path):
            print(f"  ↪︎  {slug}: already has podcast_playlist_id — skipping")
            continue

        try:
            playlist_id = create_one_playlist(
                youtube,
                title=meta["title"],
                description=meta["description"],
                default_language=meta["default_language"],
            )
        except Exception as exc:  # noqa: BLE001
            print(f"  ❌  {slug}: insert failed → {exc}")
            continue

        update_yaml_with_playlist_id(yaml_path, playlist_id)
        results[slug] = playlist_id
        print(f"  ✓  {slug}: {playlist_id}  →  shows/{slug}.yaml")

    out = REPO_ROOT / f"youtube_playlists_{args.channel}.json"
    out.write_text(json.dumps(results, indent=2))
    print(f"\nWrote {out.relative_to(REPO_ROOT)}")
    print("\nNext step: review the YAML edits with `git diff shows/`, then "
          "commit and push.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
