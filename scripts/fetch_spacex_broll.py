#!/usr/bin/env python3
"""Fetch SpaceX footage b-roll candidates — ONLY from CC-licensed videos.

The licensing reality (verified 2026-08-01), because "SpaceX is open
access" is only partly true and the differences are load-bearing for a
monetized channel:

* **SpaceX Flickr photos are CC BY-NC 2.0** since December 2019 (they
  were CC0/public domain 2015-2019; SpaceX quietly relicensed). The NC
  term fails a monetized YouTube channel. Photos are out regardless —
  this pipeline wants video.
* **SpaceX's YouTube back-catalog is the usable slice.** Videos a
  channel marks with YouTube's "Creative Commons Attribution (reuse
  allowed)" option are licensed CC BY (3.0 before YouTube's Aug 2025
  switch, 4.0 after) — commercial reuse is allowed WITH attribution.
  This is per-video, not per-channel: every video must be checked, and
  this script refuses to download anything whose own metadata does not
  say Creative Commons. There is no override flag on purpose.
* **2024+ streams live on X**, which grants no reuse license at all.
  X-hosted video is never fetched here.
* NASA-produced footage of SpaceX missions is public domain regardless
  — see ``fetch_nasa_broll.py`` for that (often the better source for
  Crew Dragon / ISS material).

CC BY's attribution requirement is handled end-to-end: every download
records an ``attribution`` line in ``_provenance.json``, which
``build_broll_pool.py`` copies into ``broll.json``, and the render
pipeline appends a "Footage:" credit block to the YouTube description
of any episode that actually uses the clip.

Workflow::

    # 1. Discover which recent channel videos are CC-licensed:
    python scripts/fetch_spacex_broll.py --list-cc --max 40

    # 2. Download a bounded section of a CC video (webcasts run hours —
    #    grab the 30-60s you actually want, e.g. liftoff or landing):
    python scripts/fetch_spacex_broll.py --out-dir spacex_broll \
        --clip "https://www.youtube.com/watch?v=VIDEO_ID" 19:45-20:40

    # 3. Watch + curate, then publish keepers (attribution flows in
    #    automatically from _provenance.json):
    python scripts/build_broll_pool.py --show spacex \
        spacex_broll/keeper1.mp4 ...

Requires ``yt-dlp`` on PATH (``pip install yt-dlp``). This is an
operator-run curation tool like the NASA fetcher — it is not wired into
any workflow.
"""

from __future__ import annotations

import argparse
import json
import logging
import re
import shutil
import subprocess
import sys
from pathlib import Path

logging.basicConfig(level=logging.INFO, stream=sys.stdout,
                    format="%(levelname)s %(message)s")
logger = logging.getLogger("fetch_spacex_broll")

DEFAULT_CHANNEL = "https://www.youtube.com/@SpaceX/videos"
# Bare (section-less) downloads only below this duration — anything
# longer is a webcast and the operator must name the seconds they want.
MAX_FULL_DOWNLOAD_SECONDS = 15 * 60

_SECTION_RE = re.compile(
    r"^(?P<start>\d{1,2}(?::\d{2}){0,2})-(?P<end>\d{1,2}(?::\d{2}){0,2})$"
)


def is_cc_license(license_str: str | None) -> bool:
    """True only for YouTube's Creative Commons license strings.

    yt-dlp reports the watch-page value verbatim — e.g. ``"Creative
    Commons Attribution license (reuse allowed)"`` — and ``None`` or
    ``"Standard YouTube License"`` otherwise. Substring match so the
    post-Aug-2025 CC BY 4.0 wording also passes.
    """
    return "creative commons" in (license_str or "").lower()


def cc_short_label(license_str: str | None, upload_date: str | None) -> str:
    """Compact CC label for attribution lines.

    YouTube's CC option was CC BY 3.0 until 2025-08-01 and CC BY 4.0
    after (non-retroactive), keyed off the upload date.
    """
    if not is_cc_license(license_str):
        return ""
    if upload_date and upload_date >= "20250801":
        return "CC BY 4.0"
    return "CC BY 3.0"


def parse_section(section: str | None) -> str | None:
    """Validate ``MM:SS-MM:SS`` / ``H:MM:SS-…`` / ``full`` → yt-dlp form.

    Returns the ``*start-end`` string yt-dlp's ``--download-sections``
    expects, or ``None`` for a full download. Raises ValueError on any
    other shape so a typo can't silently download four hours of webcast.
    """
    if section is None or section.strip().lower() == "full":
        return None
    m = _SECTION_RE.match(section.strip())
    if not m:
        raise ValueError(
            f"bad section {section!r} — expected START-END like 19:45-20:40")
    return f"*{m.group('start')}-{m.group('end')}"


def build_attribution(title: str, video_id: str, license_str: str | None,
                      upload_date: str | None, uploader: str = "SpaceX") -> str:
    """One-line CC BY credit for the YouTube description Footage block."""
    label = cc_short_label(license_str, upload_date) or "CC BY"
    short_title = (title or video_id).strip()
    if len(short_title) > 70:
        short_title = short_title[:67].rstrip() + "..."
    return (f"{uploader} — \"{short_title}\" "
            f"({label}, https://youtu.be/{video_id})")


def safe_name(video_id: str, title: str, section: str | None) -> str:
    slug = re.sub(r"[^A-Za-z0-9]+", "_", (title or video_id))[:50].strip("_")
    tag = ""
    if section:
        tag = "__" + re.sub(r"[^0-9]+", "-", section).strip("-")
    return f"{video_id}__{slug}{tag}.mp4"


def _require_ytdlp() -> str:
    exe = shutil.which("yt-dlp")
    if not exe:
        logger.error("yt-dlp not found on PATH — install with: "
                     "pip install yt-dlp")
        raise SystemExit(1)
    return exe


def _probe(url: str) -> dict:
    """Fetch a single video's metadata (no download)."""
    exe = _require_ytdlp()
    out = subprocess.run(  # noqa: S603
        [exe, "-J", "--no-download", "--no-playlist", url],
        capture_output=True, text=True, timeout=120, check=True,
    ).stdout
    return json.loads(out)


def _list_channel_ids(channel_url: str, max_videos: int) -> list:
    exe = _require_ytdlp()
    out = subprocess.run(  # noqa: S603
        [exe, "-J", "--flat-playlist", "--playlist-end", str(max_videos),
         channel_url],
        capture_output=True, text=True, timeout=300, check=True,
    ).stdout
    data = json.loads(out)
    return [e.get("id") for e in (data.get("entries") or []) if e.get("id")]


def _merge_provenance(out_dir: Path, rows: list) -> None:
    """Merge this run's rows into ``_provenance.json`` keyed by file name.

    (The NASA fetcher overwrites with only the current run's rows; here
    curation typically spans several runs, so earlier rows must survive.)
    """
    path = out_dir / "_provenance.json"
    existing: list = []
    if path.exists():
        try:
            loaded = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(loaded, list):
                existing = loaded
        except Exception as exc:  # noqa: BLE001
            logger.warning("existing _provenance.json unreadable (%s) — "
                           "starting fresh", exc)
    by_file = {r.get("file"): r for r in existing if isinstance(r, dict)}
    for row in rows:
        by_file[row["file"]] = row
    path.write_text(json.dumps(list(by_file.values()), indent=2),
                    encoding="utf-8")


def _download_clip(url: str, section_raw: str, out_dir: Path) -> dict | None:
    try:
        ytdlp_section = parse_section(section_raw)
    except ValueError as exc:
        logger.error("%s: %s — skipped", url, exc)
        return None
    try:
        info = _probe(url)
    except Exception as exc:  # noqa: BLE001
        logger.error("%s: metadata probe failed (%s) — skipped", url, exc)
        return None
    license_str = info.get("license")
    video_id = info.get("id") or ""
    title = info.get("title") or ""
    uploader = info.get("uploader") or info.get("channel") or "SpaceX"
    upload_date = info.get("upload_date") or ""
    if not is_cc_license(license_str):
        logger.error(
            "REFUSED %s — license is %r, not Creative Commons. Only "
            "CC-marked videos can be reused on a monetized channel; find "
            "CC candidates with --list-cc, or use fetch_nasa_broll.py "
            "for public-domain NASA coverage.", url, license_str)
        return None
    duration = float(info.get("duration") or 0)
    if ytdlp_section is None and duration > MAX_FULL_DOWNLOAD_SECONDS:
        logger.error(
            "REFUSED full download of %s — %.0f min long. Webcasts must "
            "be fetched as sections (e.g. --clip URL 19:45-20:40).",
            url, duration / 60)
        return None

    dest = out_dir / safe_name(video_id, title, section_raw
                               if ytdlp_section else None)
    if dest.exists():
        logger.info("skip (exists): %s", dest.name)
        return None
    exe = _require_ytdlp()
    cmd = [exe,
           # Video-only ≤1080p: b-roll is silent garnish, and skipping
           # audio keeps webcast sections small.
           "-f", "bv*[height<=1080][ext=mp4]/bv*[height<=1080]/bv*",
           "--remux-video", "mp4",
           "--no-playlist",
           "-o", str(dest)]
    if ytdlp_section:
        cmd += ["--download-sections", ytdlp_section,
                "--force-keyframes-at-cuts"]
    cmd.append(url)
    logger.info("downloading %s (%s): %s", video_id,
                section_raw if ytdlp_section else "full", title[:70])
    try:
        subprocess.run(cmd, timeout=1800, check=True)  # noqa: S603
    except Exception as exc:  # noqa: BLE001
        logger.error("download failed for %s: %s", url, exc)
        dest.unlink(missing_ok=True)
        return None
    if not dest.exists():
        logger.error("yt-dlp reported success but %s is missing", dest)
        return None
    return {
        "video_id": video_id,
        "title": title,
        "uploader": uploader,
        "upload_date": upload_date,
        "source_url": f"https://www.youtube.com/watch?v={video_id}",
        "license": license_str,
        "section": section_raw if ytdlp_section else "full",
        "file": dest.name,
        "attribution": build_attribution(
            title, video_id, license_str, upload_date, uploader),
    }


def _list_cc(channel_url: str, max_videos: int) -> int:
    logger.info("scanning %s (newest %d videos; one metadata request "
                "each, so this takes a minute)...", channel_url, max_videos)
    try:
        ids = _list_channel_ids(channel_url, max_videos)
    except Exception as exc:  # noqa: BLE001
        logger.error("channel listing failed: %s", exc)
        return 1
    found = 0
    for vid in ids:
        try:
            info = _probe(f"https://www.youtube.com/watch?v={vid}")
        except Exception as exc:  # noqa: BLE001
            logger.warning("%s: probe failed (%s)", vid, exc)
            continue
        if is_cc_license(info.get("license")):
            found += 1
            dur = float(info.get("duration") or 0)
            print(f"CC  {vid}  {info.get('upload_date', '????????')}  "
                  f"{dur / 60:6.1f}min  {info.get('title', '')[:70]}")
    logger.info("%d of %d scanned videos are CC-licensed. Note: SpaceX's "
                "2024+ launch streams moved to X (no license grant), so "
                "expect CC hits to skew toward the back-catalog — scan "
                "deeper with --max, or pass known video URLs directly "
                "via --clip.", found, len(ids))
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--clip", nargs=2, action="append", default=[],
                        metavar=("URL", "SECTION"),
                        help='video URL + section ("19:45-20:40" or "full")')
    parser.add_argument("--list-cc", action="store_true",
                        help="scan the channel and list CC-licensed videos")
    parser.add_argument("--channel", default=DEFAULT_CHANNEL,
                        help=f"channel URL for --list-cc "
                             f"(default: {DEFAULT_CHANNEL})")
    parser.add_argument("--max", type=int, default=40,
                        help="videos to scan with --list-cc")
    parser.add_argument("--out-dir", default="spacex_broll")
    args = parser.parse_args()

    if not args.list_cc and not args.clip:
        parser.error("nothing to do — pass --list-cc and/or --clip")

    rc = 0
    if args.list_cc:
        rc = _list_cc(args.channel, args.max)

    if args.clip:
        out_dir = Path(args.out_dir)
        out_dir.mkdir(parents=True, exist_ok=True)
        rows = []
        for url, section in args.clip:
            row = _download_clip(url, section, out_dir)
            if row:
                rows.append(row)
        if rows:
            _merge_provenance(out_dir, rows)
        logger.info(
            "downloaded %d clip(s) to %s — now WATCH and curate, then "
            "publish keepers with scripts/build_broll_pool.py (attribution "
            "carries over from _provenance.json automatically).",
            len(rows), out_dir)
        if not rows and rc == 0:
            rc = 1
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
