#!/usr/bin/env python3
"""Publish a RECOVERED episode (audio already on R2) to the podcast RSS feed.

Some episodes (e.g. Tesla Ep519 / SpaceX Ep12, 2026-06-23) finished their
audio — it was uploaded to R2 — but the pipeline timed out during video
generation, BEFORE the RSS/blog/commit steps. Their text artifacts (digest,
show notes, chapters) were never committed and are lost. This one-off tool
re-derives the minimum and adds the episode to the feed, reusing the SAME
engine.publisher.update_rss_feed the daily pipeline uses (so the entry is
byte-for-byte the right shape).

What it does:
  1. Downloads the episode audio from R2 (for duration + transcript).
  2. Re-transcribes it (faster-whisper) → the standard _transcript.{txt,json}.
  3. Builds the title from the known hook + the standard AI disclosure /
     show-notes footer / transcript link.
  4. Calls update_rss_feed on the show's local .rss file.
  5. (Optional) writes a minimal digest .md and a blog post.

It does NOT touch YouTube — for a one-off, upload the stitched MP4 by hand in
YouTube Studio (title = the hook). It does NOT commit or push unless you pass
--commit / --push, so you can review the RSS diff first.

Usage:
    # Review-only (writes the transcript + edits the local .rss, no push):
    python3 scripts/publish_recovered_episode.py --set tesla_ep519
    git diff -- podcast.rss            # eyeball the new <item>

    # When happy:
    python3 scripts/publish_recovered_episode.py --set spacex_ep12 --commit --push

Requires: the repo's deps (faster-whisper etc.) and network access to R2.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from urllib.request import urlretrieve

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from engine.audio import format_duration, get_audio_duration  # noqa: E402
from engine.config import load_config  # noqa: E402
from engine.publisher import (  # noqa: E402
    apply_op3_prefix,
    build_show_notes_footer,
    update_rss_feed,
)
from engine.transcripts import generate_transcript  # noqa: E402

_AI_DISCLOSURE_RSS = (
    "AI Disclosure: This podcast is curated by Patrick but uses AI-generated "
    "voice synthesis for audio production."
)

# Known recovered episodes (audio already on R2). Hooks are from the run logs.
EPISODES = {
    "tesla_ep519": {
        "show": "tesla",
        "episode": 519,
        "date": "20260623",
        "hook": (
            "Tesla's $4-5 billion battery storage partnership with NatPower will "
            "deploy Megapacks across the UK and Italy to stabilize grids with "
            "rising renewables."
        ),
        "audio_url": "https://audio.nerranetwork.com/tesla/Tesla_Shorts_Time_Pod_Ep519_20260623.mp3",
    },
    "spacex_ep12": {
        "show": "spacex",
        "episode": 12,
        "date": "20260623",
        "hook": (
            "Starship's planned every-eight-day cadence from Kennedy now collides "
            "with infrastructure limits that could stretch the first lunar landing "
            "timeline."
        ),
        "audio_url": "https://audio.nerranetwork.com/spacex/SpaceX_Daily_Ep012_20260623.mp3",
    },
}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--set", dest="ep", choices=sorted(EPISODES), help="A known recovered episode")
    ap.add_argument("--show", help="Show slug (if not using --set)")
    ap.add_argument("--episode", type=int, help="Episode number (if not using --set)")
    ap.add_argument("--date", help="YYYYMMDD (if not using --set)")
    ap.add_argument("--hook", help="Episode hook/headline (if not using --set)")
    ap.add_argument("--audio-url", help="R2 audio URL (if not using --set)")
    ap.add_argument("--youtube-url", default="", help="Watch link to add to the RSS description")
    ap.add_argument("--model", default="base", help="Whisper model size (tiny/base/small)")
    ap.add_argument("--commit", action="store_true", help="git add+commit the new artifacts")
    ap.add_argument("--push", action="store_true", help="git push (implies --commit)")
    args = ap.parse_args()

    if args.ep:
        spec = EPISODES[args.ep]
    else:
        if not all([args.show, args.episode, args.date, args.hook, args.audio_url]):
            ap.error("without --set you must pass --show --episode --date --hook --audio-url")
        spec = {
            "show": args.show, "episode": args.episode, "date": args.date,
            "hook": args.hook, "audio_url": args.audio_url,
        }

    slug = spec["show"]
    ep_num = int(spec["episode"])
    date = datetime.strptime(str(spec["date"]), "%Y%m%d").date()
    hook = spec["hook"]
    audio_url = spec["audio_url"]

    config = load_config(f"shows/{slug}.yaml")
    digests_dir = ROOT / config.publishing.audio_subdir
    digests_dir.mkdir(parents=True, exist_ok=True)

    # 1. Audio (download from R2 if not already local).
    mp3_name = audio_url.rsplit("/", 1)[-1]
    local_mp3 = digests_dir / mp3_name
    if not local_mp3.exists():
        print(f"Downloading audio: {audio_url}")
        urlretrieve(audio_url, local_mp3)  # noqa: S310 — known R2 URL
    duration = get_audio_duration(local_mp3) or 0.0
    print(f"Audio: {local_mp3.name} ({format_duration(duration)})")

    # 2. Transcript (standard prefix so the URL matches the feed convention).
    ep_prefix = f"{config.episode.prefix}_Ep{ep_num:03d}_{date:%Y%m%d}"
    transcript_url = None
    try:
        tr = generate_transcript(local_mp3, digests_dir, ep_prefix, model_size=args.model)
        if tr and tr.json_path.exists():
            transcript_url = (
                f"{config.publishing.base_url}/{config.publishing.audio_subdir}"
                f"/{tr.json_path.name}"
            )
            print(f"Transcript: {tr.txt_path.name}")
    except Exception as exc:  # noqa: BLE001 — transcript is a nice-to-have
        print(f"Transcript failed (continuing without): {exc}", file=sys.stderr)

    # 3. Title + description (mirror run_show's RSS shaping).
    episode_title = f"Ep {ep_num}: {hook}"
    episode_desc = hook.rstrip() + "\n\n" + _AI_DISCLOSURE_RSS
    if args.youtube_url:
        episode_desc += f"\n\n🎬 Watch on YouTube: {args.youtube_url}"
    try:
        from generate_html import NETWORK_SHOWS as _NS
        has_blog = slug in _NS
    except Exception:  # noqa: BLE001
        has_blog = False
    footer = build_show_notes_footer(config.publishing.base_url, slug, ep_num, has_blog=has_blog)
    if footer:
        episode_desc += "\n\n" + footer

    feed_audio_url = audio_url
    if config.analytics.enabled:
        feed_audio_url = apply_op3_prefix(audio_url, config.analytics.prefix_url)

    channel_desc = (
        config.publishing.rss_description.rstrip() + "\n\n" + _AI_DISCLOSURE_RSS
    )

    rss_path = ROOT / config.publishing.rss_file
    print(f"Updating RSS feed: {rss_path.name}")
    update_rss_feed(
        rss_path=rss_path,
        episode_num=ep_num,
        episode_title=episode_title,
        episode_description=episode_desc,
        episode_date=date,
        mp3_filename=mp3_name,
        mp3_duration=duration,
        mp3_path=local_mp3,
        base_url=config.publishing.base_url,
        audio_subdir=config.publishing.audio_subdir,
        channel_title=config.publishing.rss_title,
        channel_link=config.publishing.rss_link,
        channel_description=channel_desc,
        channel_language=config.publishing.rss_language,
        channel_author=config.publishing.rss_author,
        channel_email=config.publishing.rss_email,
        channel_image=config.publishing.rss_image,
        channel_category=config.publishing.rss_category,
        channel_subcategory=getattr(config.publishing, "rss_subcategory", ""),
        channel_keywords=getattr(config.publishing, "rss_keywords", ""),
        guid_prefix=config.publishing.guid_prefix,
        format_duration_func=format_duration,
        audio_url=feed_audio_url,
        transcript_url=transcript_url,
        funding_url=f"{config.publishing.base_url}/#newsletter",
        funding_label="Free newsletter — best of the network weekly",
        person_name=config.publishing.host_name or "Patrick",
        person_url=f"{config.publishing.base_url}/about.html",
    )
    print("RSS updated. Review the change before pushing:")
    subprocess.run(["git", "diff", "--stat", "--", str(rss_path.name)], cwd=ROOT, check=False)

    if args.commit or args.push:
        paths = [str(rss_path.name)]
        for p in (digests_dir / f"{ep_prefix}_transcript.txt",
                  digests_dir / f"{ep_prefix}_transcript.json"):
            if p.exists():
                paths.append(str(p.relative_to(ROOT)))
        subprocess.run(["git", "add", *paths], cwd=ROOT, check=True)
        msg = f"Publish recovered {slug} Ep{ep_num} ({date:%Y-%m-%d}) to RSS"
        subprocess.run(["git", "commit", "-m", msg], cwd=ROOT, check=True)
        print(f"Committed: {msg}")
        if args.push:
            subprocess.run(["git", "push"], cwd=ROOT, check=True)
            print("Pushed.")

    print(
        "\nNext steps:\n"
        f"  • RSS entry for Ep{ep_num} is in {rss_path.name} (review the diff above).\n"
        "  • YouTube: upload the stitched MP4 by hand in YouTube Studio\n"
        f"    (title: \"Ep {ep_num}: {hook[:60]}…\").\n"
        "  • If you didn't pass --push, commit + push when the diff looks right."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
