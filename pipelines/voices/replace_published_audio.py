"""Put a re-assembled edit behind an episode that is already published.

Oct 7 2026, Vincent Rylan. His episode went out on the call audio while his
own browser recording sat whole in R2, and once that recording was found the
edit was assembled again from it. Publishing again is refused (and would mint
a new episode number and a duplicate feed entry), and pointing the feed at the
new file would re-download the episode for every subscriber (see the OP3 note
in publish_episode.py). The feed, the site, the summaries and the YouTube
description all name ONE file, so the new edit goes over that file and only
the feed's byte length and running time change.

The published file is kept beside itself first (``<name>.as-published.mp3``),
once, so the original can always be put back.

Run it only after listening to the new assembly: publishing is a human act,
and so is changing what is published.

    INTERVIEW_ID=<id> python pipelines/voices/replace_published_audio.py [--dry-run]

Then commit the feed, push, and run the publish workflow with the interview id
and "refresh_post" ticked, so the site's cards pick up the new running time.
The CDN can serve the old file for up to four hours.
"""
from __future__ import annotations

import datetime as dt
import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import requests  # noqa: E402

from common import _r2_client, logger, sb_select, sb_update  # noqa: E402
from shows import show_for  # noqa: E402

PUBLIC_BASE = (os.environ.get("R2_PUBLIC_BASE_URL", "")
               or "https://audio.nerranetwork.com").rstrip("/")


def _key(url: str) -> str:
    url = re.sub(r"^https://op3\.dev/e/", "https://", url.split("?")[0])
    if not url.startswith(PUBLIC_BASE + "/"):
        raise SystemExit(f"{url} is not on {PUBLIC_BASE}")
    return url[len(PUBLIC_BASE) + 1:]


def rewrite_feed_item(rss: str, published_key: str, length: int,
                      duration: str) -> str:
    """The feed with one item's enclosure length and running time changed.
    The item is found by its enclosure; nothing else in the feed moves."""
    items = list(re.finditer(r"<item>.*?</item>", rss, flags=re.S))
    hits = [m for m in items if published_key in m.group(0)]
    if len(hits) != 1:
        raise SystemExit(f"{len(hits)} feed items name {published_key}; expected one")
    item = hits[0].group(0)
    new = re.sub(r'(<enclosure [^>]*length=")\d+(")', rf"\g<1>{length}\2", item, count=1)
    new = re.sub(r"(<itunes:duration>)[^<]*(</itunes:duration>)", rf"\g<1>{duration}\2",
                 new, count=1)
    return rss[:hits[0].start()] + new + rss[hits[0].end():]


def replace(interview_id: str, dry_run: bool = False) -> int:
    from engine.audio import format_duration

    interview = sb_select("interviews", f"id=eq.{interview_id}")[0]
    if interview.get("status") != "published":
        raise SystemExit(f"interview {interview_id} is {interview.get('status')!r}, "
                         "not published; publish it the normal way")
    app = sb_select("guest_applications", f"id=eq.{interview['application_id']}")[0]
    show = show_for(interview, app)
    pkg = sb_select("editorial_packages",
                    f"interview_id=eq.{interview_id}&status=eq.published"
                    "&order=created_at.desc&limit=1")[0]
    run = sb_select("interview_runs", f"id=eq.{pkg['interview_run_id']}")[0]
    episode_num = int(interview.get("episode_number") or 0)
    data = json.loads(show.summaries_path.read_text(encoding="utf-8")) or {}
    entry = next((e for e in data.get("episodes") or []
                  if int(e.get("episode") or 0) == episode_num), None)
    if entry is None:
        raise SystemExit(f"no Ep{episode_num} in {show.summaries_path}")
    published_url = str(entry["audio_url"])
    log = dict(run.get("grok_session_log") or {})
    tracks = dict(log.get("tracks") or {})
    edit = dict(tracks.get("edit") or {})
    new_url = str(edit.get("url") or "")
    if not new_url or new_url.split("?")[0] == published_url.split("?")[0]:
        logger.info("Ep%d already plays %s; assemble the new edit first",
                    episode_num, published_url)
        return 0

    published_key, new_key = _key(published_url), _key(new_url)
    backup_key = re.sub(r"\.mp3$", ".as-published.mp3", published_key)
    with tempfile.TemporaryDirectory() as tmp:
        mp3 = Path(tmp) / "new.mp3"
        with requests.get(new_url, stream=True, timeout=900) as resp:
            resp.raise_for_status()
            with mp3.open("wb") as fh:
                for chunk in resp.iter_content(1 << 16):
                    fh.write(chunk)
        seconds = float(subprocess.run(
            ["ffprobe", "-v", "quiet", "-show_entries", "format=duration",
             "-of", "csv=p=0", str(mp3)],
            check=True, capture_output=True, text=True).stdout.strip() or 0)
        length = mp3.stat().st_size
        logger.info("Ep%d: %s (%.1f min, %d bytes) goes over %s",
                    episode_num, new_key, seconds / 60, length, published_key)
        if dry_run:
            return 0
        s3, bucket = _r2_client()
        try:
            s3.head_object(Bucket=bucket, Key=backup_key)
            logger.info("the published original is already kept at %s", backup_key)
        except Exception:  # noqa: BLE001 — not there yet: keep it
            s3.copy_object(Bucket=bucket, Key=backup_key,
                           CopySource={"Bucket": bucket, "Key": published_key},
                           ContentType="audio/mpeg", MetadataDirective="REPLACE")
            logger.info("kept the published original at %s", backup_key)
        s3.upload_file(str(mp3), bucket, published_key,
                       ExtraArgs={"ContentType": "audio/mpeg"})

    rss_path = show.rss_path
    rss_path.write_text(rewrite_feed_item(rss_path.read_text(encoding="utf-8"),
                                          published_key, length,
                                          format_duration(seconds)),
                        encoding="utf-8")
    edit.update({"url": published_url, "duration_sec": round(seconds, 1),
                 "assembled_url": new_url,
                 "replaced_published_at": dt.datetime.now(dt.timezone.utc).isoformat()})
    tracks["edit"] = edit
    log["tracks"] = tracks
    sb_update("interview_runs", f"id=eq.{run['id']}", {"grok_session_log": log})
    logger.info("Ep%d now plays the new edit at its old address; the feed says "
                "%s. Commit %s, then refresh the post.", episode_num,
                format_duration(seconds), rss_path.name)
    return 0


if __name__ == "__main__":
    iid = os.environ.get("INTERVIEW_ID", "").strip() or (sys.argv[1] if len(sys.argv) > 1
                                                          and not sys.argv[1].startswith("-") else "")
    if not iid:
        raise SystemExit("INTERVIEW_ID is required")
    raise SystemExit(replace(iid, dry_run="--dry-run" in sys.argv))
