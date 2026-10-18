#!/usr/bin/env python3
"""Release a produced members-only series (see engine/specials.py).

Run it after listening to the episodes. It:

1. marks the series ``released`` in specials/catalog.json — from the next
   Personal builder run every paying member's feed carries every episode;
2. puts the trailer at the top of each teaser show's free feed (an
   ``itunes:episodeType trailer`` item, OP3-prefixed);
3. posts the X teaser from each account in the series' ``x_env_prefixes``;
4. renders the trailer as a Short and uploads it to the English channel.

The newsletters (a line in each teaser show's next emails for 14 days), the
show pages, the homepage and specials.html read the released catalog, so
they follow on their next build.

    python scripts/release_special.py --series spacex-tesla-merger            # dry run
    python scripts/release_special.py --series spacex-tesla-merger --confirm
"""
from __future__ import annotations

import argparse
import datetime as dt
import logging
import sys
from pathlib import Path
from typing import List, Optional

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from engine import specials as S  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s",
                    stream=sys.stdout)
logger = logging.getLogger("release_special")


def _feed_path(slug: str) -> Path:
    from engine.config import load_config
    cfg = load_config(str(ROOT / "shows" / f"{slug}.yaml"))
    return ROOT / cfg.publishing.rss_file


def publish_trailer_short(series: S.Series, entry: dict) -> str:
    """Render the trailer as a YouTube Short (host show cover, burned-in
    captions, a members-only end card) and upload it to the network's
    English channel. Returns the watch URL. Best-effort: the caller records
    the reason when it fails."""
    import tempfile

    import requests

    from engine.captions import transcript_to_ass_window
    from engine.config import load_config
    from engine.titles import YOUTUBE_TITLE_MAX, clip_words
    from engine.transcripts import generate_transcript
    from engine.video import build_short_video
    from engine.youtube import get_channel_credentials_from_env, upload_video

    creds = get_channel_credentials_from_env("en")
    if creds is None:
        raise S.SpecialsError("no YouTube credentials")
    cfg = load_config(str(ROOT / "shows" / f"{series.host_show}.yaml"))
    trailer = entry["trailer"]
    cover = ROOT / "assets" / "covers" / Path(cfg.publishing.rss_image or "").name
    if not cover.is_file():
        raise S.SpecialsError(f"no cover image at {cover}")
    with tempfile.TemporaryDirectory() as tmp:
        work = Path(tmp)
        audio = work / "trailer.mp3"
        resp = requests.get(trailer["audio_url"], timeout=120)
        resp.raise_for_status()
        audio.write_bytes(resp.content)
        duration = min(float(trailer.get("duration_seconds") or 58), 58.0)
        subs = None
        result = generate_transcript(audio, work, "trailer", language="en")
        if result is not None:
            subs = work / "trailer.ass"
            transcript_to_ass_window(result.json_path, subs, window_start_seconds=0.0,
                                     window_duration_seconds=duration)
            subs = subs if subs.exists() else None
        out = build_short_video(
            audio, cover, work / "trailer_short.mp4", duration=duration,
            hook=series.title, show_name=cfg.name, subtitles_path=subs,
            end_card=True, end_card_main_text="MEMBERS ONLY",
            end_card_sub_text="nerranetwork.com/join")
        up = upload_video(
            out, credentials=creds,
            title=clip_words(f"{series.title} | Members-only series #Shorts", YOUTUBE_TITLE_MAX),
            description=(f"{series.teaser or series.summary}\n\n{series.total_parts} episodes for "
                         f"Nerra Personal members: {S.series_page_url(series.id)}\n\n"
                         "Narrated with an AI voice clone of the host."),
            tags=[cfg.name, "Nerra Network", "members only", "deep dive"],
            category_id=int(getattr(cfg.youtube, "category_id", 28) or 28),
            contains_synthetic_media=True)
    return up.watch_url


def main(argv: Optional[List[str]] = None) -> int:
    from engine.publisher import apply_op3_prefix

    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--series", required=True)
    ap.add_argument("--confirm", action="store_true", help="actually release (default: dry run)")
    ap.add_argument("--skip-x", action="store_true")
    ap.add_argument("--skip-feeds", action="store_true")
    ap.add_argument("--skip-short", action="store_true")
    args = ap.parse_args(argv)

    series = S.find_series(args.series)
    catalog = S.load_catalog()
    entry = S.series_entry(catalog, series)
    missing = [e.id for e in series.episodes
               if entry["episodes"].get(e.id, {}).get("status") != "produced"]
    if missing:
        logger.error("%s is not fully produced; missing: %s", series.id, missing)
        return 1
    trailer = entry.get("trailer") or {}
    if not trailer.get("audio_url"):
        logger.error("%s has no trailer yet (produce_special.py makes it)", series.id)
        return 1

    today = dt.date.today()
    title = f"Members-only series: {series.title}"
    description = (f"{series.summary} {series.total_parts} episodes, available now to "
                   f"Nerra Personal members in their personal feed. Join at "
                   f"{S.SITE}/{S.JOIN_PAGE}")
    plan = [f"mark {series.id} released ({series.total_parts} episodes)"]
    if not args.skip_feeds:
        plan += [f"trailer item in {_feed_path(s).name}" for s in series.tease_shows]
    if not args.skip_x:
        plan += [f"X teaser from {p}*" for p in series.x_env_prefixes]
    if not args.skip_short:
        plan.append("trailer Short on the English YouTube channel")
    for line in plan:
        logger.info("%s %s", "DO" if args.confirm else "WOULD", line)
    if not args.confirm:
        logger.info("dry run — pass --confirm to release")
        return 0

    entry["status"] = "released"
    entry["released_date"] = today.isoformat()
    results = entry.setdefault("release", {})

    if not args.skip_feeds:
        pub = dt.datetime.combine(today, dt.time(11, 0), tzinfo=dt.timezone.utc)
        for slug in series.tease_shows:
            guid = S.trailer_guid(slug, series.id)
            item = S.trailer_item_xml(
                guid=guid, title=title, description=description,
                audio_url=apply_op3_prefix(trailer["audio_url"]),
                length=int(trailer.get("bytes") or 0),
                duration_seconds=float(trailer.get("duration_seconds") or 0),
                pub_date=pub, link=S.series_page_url(series.id))
            added = S.insert_trailer_item(_feed_path(slug), item, guid)
            results[f"feed_{slug}"] = "added" if added else "already_present"
            logger.info("trailer in %s feed: %s", slug, results[f"feed_{slug}"])

    if not args.skip_x:
        from engine.x_post import post_teaser
        text = S.x_teaser_text(entry, series.id)
        for prefix in series.x_env_prefixes:
            key = f"x_{prefix.rstrip('_').lower()}"
            if results.get(key) == "posted":
                continue
            posted, reason = post_teaser(env_prefix=prefix, title=text.split("\n\n")[0],
                                         link=S.series_page_url(series.id),
                                         label=f"special {series.id}")
            results[key] = "posted" if posted else (reason or "failed")
            logger.info("X teaser %s: %s", prefix, results[key])

    if not args.skip_short and not str(results.get("short", "")).startswith("http"):
        try:
            results["short"] = publish_trailer_short(series, entry)
        except Exception as exc:  # noqa: BLE001 — the feeds and X already went out
            logger.error("::warning::trailer Short not published: %s", exc)
            results["short"] = f"failed: {exc}"[:200]
        logger.info("trailer Short: %s", results["short"])

    S.save_catalog(catalog)
    logger.info("%s released %s", series.id, today.isoformat())
    return 0


if __name__ == "__main__":
    sys.exit(main())
