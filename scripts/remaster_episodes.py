#!/usr/bin/env python3
"""Re-master PUBLISHED episodes in place: a gain to the network's -16 LUFS.

Nov 3 2026: Unintended Consequences, Vancouver and Collingwood — the three
run_show shows with no music file — shipped every episode at -25 LUFS
(161 + 41 + 6 = 208 items on their feeds), 9 LU under every other show in
a listener's queue and a 9.7 LU step inside Nerra Daily. The voice-only
path masters to -16 from the next episode (``engine.audio.master_voice_track``);
the back catalogue stays where it was until someone acts. UC is a
narrative show whose catalogue is listened to as a series, so the gap is
heard by exactly the listeners it should keep.

The committed scripts and the audio are right in every other respect, so
this is a GAIN, not a re-synthesis: no TTS spend, no spoken-text-gate
risk. The Sep 15 2026 rule "never clip, always re-synthesize" is about
REPLACED content and does not apply — no sample moves in time, so the
chapters, the transcript and the VTT describe the re-mastered file
exactly as they did the original.

What this does, per episode, in order:

1. Reads the episode's item from the show's committed feed — title,
   description, enclosure URL, page link and GUID are the published ones
   and are never rebuilt (Oct 20 2026: the repair tool never moves a
   feed item; never from ``publishing.base_url``, which is the SITE).
2. Pulls the published MP3 back down through ``engine.http_download``
   from the bare R2 URL (never through the OP3 prefix — a re-master is
   not a listen) and measures it with ``engine.audio.measure_loudness``.
3. Skips it when it is already inside ``-16 ± 1.5`` LUFS. Otherwise the
   gain is ``engine.personal_edition.segment_gain_db`` — the figure the
   Personal builder already applies when it levels a UC segment.
4. Renders ``volume=+N dB`` through a sample-peak limiter and the shows'
   one master encode (``engine.audio.JOIN_MP3_ENCODE_ARGS``), then
   re-measures. **The upload is REFUSED unless the rendered file reads
   within the band and its true peak is at or under -1 dBTP.**

   Why not a two-pass loudnorm with its linear option: these files sit
   at -3.6 to -4.8 dBTP, so the +9 dB they need would put the peak near
   +5 dBTP, and ffmpeg's loudnorm then falls back SILENTLY to its
   dynamic mode — the "pure gain" claim fails on exactly these files.
   A static gain plus a limiter is the shape the Personal builder ships
   (``segment_gain_cmd``); the loudest words take a few dB of peak
   limiting, which is the accepted cost.

   Why the limiter ceiling is -2.0 dBFS and not the Personal builder's
   -1.0: the refusal line is a TRUE peak, read oversampled and after the
   MP3 encode. Calibrated on the published UC Ep161 (-25.6 LUFS, -4.8
   dBTP): a ceiling of -1.0 dBFS re-measured at -0.5 dBTP (refused), -1.5
   dBFS landed exactly on -1.0, and -2.0 dBFS gives the margin and lands
   where the network's own ``loudnorm`` puts a true peak (-1.5).
5. ``--apply``: uploads to the SAME R2 key (``engine.storage.upload_episode``
   — CLAUDE.md: "Do NOT change R2 bucket paths"), replaces the feed item
   in place keeping its GUID, link and enclosure and correcting only
   duration and byte length, HEADs the key and logs ``cf-cache-status``
   (the edge holds an object for ``max-age`` 14400 s, so a listener may
   get the old bytes for up to four hours), and appends the reading to
   ``digests/<dir>/remaster_log.json``.

``remaster_log.json`` is read by the next audio review and by anyone who
needs to know which published files changed level and when; nothing on
the dashboard reads it yet.

Dry run by default: the plan is printed (before-reading, planned gain,
the render command, the key it would upload to) and nothing is written.
``--skip-upload`` renders and re-measures into a temporary directory so
the after-reading can be read without touching R2, the feed or the log.

Usage:
    python scripts/remaster_episodes.py --show unintended_consequences --episode 161
    python scripts/remaster_episodes.py --show unintended_consequences --episode 161 --apply
    python scripts/remaster_episodes.py --show vancouver --all --limit 50 --apply
    python scripts/remaster_episodes.py --show collingwood --since 20261001 --apply

Run it from Actions ("Re-master Episodes"): the R2 credentials live there.

What this tool deliberately does NOT do: it never touches YouTube (a
video's file cannot be replaced), the Apple video feed's MP4, or a Nerra
Daily edition that spliced the episode — past editions keep their step;
Nerra Personal members already hear UC levelled by the same gain.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import logging
import re
import shutil
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Dict, List, Optional

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import scripts.resynthesize_episode as rs  # noqa: E402  (the feed rules live there)
from engine.audio import (  # noqa: E402
    JOIN_MP3_ENCODE_ARGS,
    LOUDNESS_TOLERANCE_LU,
    PUBLISHED_LOUDNESS_LUFS,
    get_audio_duration,
    measure_loudness,
)
from engine.daily_edition import strip_op3  # noqa: E402
from engine.personal_edition import segment_gain_db  # noqa: E402

logger = logging.getLogger("remaster")

ITUNES_NS = rs.ITUNES_NS

#: The band a rendered file must read inside to be uploaded.
TARGET_LUFS = PUBLISHED_LOUDNESS_LUFS
TOLERANCE_LU = LOUDNESS_TOLERANCE_LU
#: The refusal line for the rendered file's TRUE peak (oversampled, after
#: the encode).
TRUE_PEAK_MAX_DBTP = -1.0
#: The limiter's SAMPLE-peak ceiling. See the module docstring for the
#: calibration; it must sit under the refusal line with room for the
#: inter-sample overshoot the encode adds (~0.5 dB on a voice).
LIMITER_CEILING_DBFS = -2.0
LIMITER_CEILING_LINEAR = round(10 ** (LIMITER_CEILING_DBFS / 20), 3)  # 0.794
#: Episodes rendered per run unless --limit says otherwise: a batch the
#: operator can listen to before the next.
DEFAULT_LIMIT = 20
LOG_NAME = "remaster_log.json"

STATUS_SKIPPED = "skipped_in_band"
STATUS_ALREADY = "already_remastered"
STATUS_PLANNED = "planned"
STATUS_RENDERED = "rendered"
STATUS_APPLIED = "applied"
STATUS_REFUSED = "refused"
STATUS_FAILED = "failed"
STATUS_UNMEASURED = "unmeasured"
STATUS_FOREIGN = "foreign_enclosure"

_BAD_STATUSES = (STATUS_REFUSED, STATUS_FAILED, STATUS_UNMEASURED, STATUS_FOREIGN)


class OutOfBand(RuntimeError):
    """The rendered file does not read inside the band — never uploaded."""


# ---------------------------------------------------------------------------
# The feed is the record of what was published
# ---------------------------------------------------------------------------

def feed_items(rss_path: Path) -> List[dict]:
    """Every item of a show's feed, in feed order (newest first), with the
    published title, description, enclosure URL, page link and GUID.

    The same five keys ``scripts.resynthesize_episode.read_published_item``
    returns, so ``refresh_rss_item`` takes an entry as-is. An item with no
    ``<itunes:episode>`` or no enclosure is listed with ``episode`` None and
    skipped downstream — nothing is guessed from a title.
    """
    if not rss_path.exists():
        return []
    try:
        root = ET.parse(rss_path).getroot()
    except ET.ParseError as exc:
        logger.warning("Could not parse %s: %s", rss_path.name, exc)
        return []
    items: List[dict] = []
    for item in root.iter("item"):
        num_text = (item.findtext(f"{{{ITUNES_NS}}}episode") or "").strip()
        enc = item.find("enclosure")
        enclosure_url = (enc.get("url") if enc is not None else "") or ""
        try:
            episode = int(num_text) if num_text else None
        except ValueError:
            episode = None
        items.append({
            "episode": episode,
            "title": (item.findtext("title") or "").strip(),
            "description": item.findtext("description") or "",
            "enclosure_url": enclosure_url,
            "enclosure_length": (enc.get("length") if enc is not None else "") or "",
            "link": (item.findtext("link") or "").strip(),
            "guid": (item.findtext("guid") or "").strip(),
            "pub_date": (item.findtext("pubDate") or "").strip(),
            "filename": enclosure_url.rsplit("/", 1)[-1] if enclosure_url else "",
        })
    return items


def artifacts_from_item(config, item: dict) -> rs.EpisodeArtifacts:
    """The episode's committed paths, from the enclosure the feed carries.

    ``resynthesize_episode.resolve_artifacts`` starts from the committed
    ``_tts.txt`` because it needs the text; a gain needs only the file,
    and UC Ep093 has an MP3 on the feed and no committed script. The
    paths follow the same shape (``TestArtifactsFromTheFeed`` holds the
    two equal on a real episode).
    """
    filename = item.get("filename") or ""
    if not filename.lower().endswith(".mp3"):
        raise ValueError(f"item carries no MP3 enclosure: {item.get('enclosure_url')!r}")
    if item.get("episode") is None:
        raise ValueError(f"item {filename} carries no <itunes:episode>")
    prefix = filename[:-4]
    found_date = re.search(r"_(\d{8})$", prefix)
    date_str = found_date.group(1) if found_date else ""
    digests_dir = rs.ROOT / config.episode.output_dir
    n = int(item["episode"])
    return rs.EpisodeArtifacts(
        slug=config.slug,
        episode_num=n,
        date_str=date_str,
        prefix=prefix,
        digests_dir=digests_dir,
        script_path=digests_dir / f"{prefix}_tts.txt",
        digest_path=digests_dir / f"{prefix}.md",
        raw_mp3=digests_dir / f"{prefix}_raw.mp3",
        final_mp3=digests_dir / filename,
        chapters_path=digests_dir / f"chapters_ep{n:03d}.json",
        transcript_txt=digests_dir / f"{prefix}_transcript.txt",
        transcript_json=digests_dir / f"{prefix}_transcript.json",
    )


def select_items(items: List[dict], *, episode: Optional[int] = None,
                 all_items: bool = False, since: str = "") -> List[dict]:
    """The items a run looks at, in feed order."""
    chosen = []
    for item in items:
        if item.get("episode") is None or not item.get("filename"):
            continue
        if episode is not None:
            if item["episode"] == episode:
                chosen.append(item)
            continue
        if since:
            found = re.search(r"_(\d{8})\.mp3$", item["filename"])
            if not found or found.group(1) < since:
                continue
            chosen.append(item)
            continue
        if all_items:
            chosen.append(item)
    return chosen


def download_url(item: dict) -> str:
    """The bare R2 URL of the published object — the OP3 redirector is
    never in the path, so pulling a file back is not counted as a play."""
    return strip_op3(item.get("enclosure_url") or "")


# ---------------------------------------------------------------------------
# The gain
# ---------------------------------------------------------------------------

def plan_gain(before: Optional[Dict[str, Optional[float]]]) -> float:
    """0.0 when the file is in band or unmeasured; else the static gain."""
    if not before or before.get("I") is None:
        return 0.0
    return segment_gain_db(before["I"])


def render_cmd(src: Path, dst: Path, gain_db: float) -> List[str]:
    """A static gain through a sample-peak limiter, encoded once with the
    shows' master setting. Nothing else in the chain: the voice chain was
    applied when the episode was made."""
    return [
        "ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-i", str(src),
        "-af", f"volume={gain_db:+.1f}dB,alimiter=limit={LIMITER_CEILING_LINEAR}:level=false",
        *JOIN_MP3_ENCODE_ARGS, str(dst),
    ]


def in_band(after: Optional[Dict[str, Optional[float]]]) -> Optional[str]:
    """None when *after* may be uploaded; otherwise why not."""
    if not after or after.get("I") is None:
        return "the rendered file could not be measured (unmeasured is not a pass)"
    if abs(after["I"] - TARGET_LUFS) > TOLERANCE_LU:
        return (f"rendered loudness {after['I']:.1f} LUFS is outside "
                f"{TARGET_LUFS:.0f} ± {TOLERANCE_LU:.1f}")
    peak = after.get("TP")
    if peak is None:
        return "the rendered file's true peak could not be read"
    if peak > TRUE_PEAK_MAX_DBTP:
        return f"rendered true peak {peak:.1f} dBTP is over {TRUE_PEAK_MAX_DBTP:.0f} dBTP"
    return None


def remaster_file(src: Path, dst: Path, gain_db: float) -> Dict[str, Optional[float]]:
    """Render *src* to *dst* with *gain_db* and re-measure. Raises
    :class:`OutOfBand` (and removes *dst*) unless the result may ship."""
    duration = get_audio_duration(src) or 0.0
    subprocess.run(render_cmd(src, dst, gain_db), check=True, capture_output=True,
                   timeout=max(600, int(duration * 3) + 120))
    after = measure_loudness(dst)
    reason = in_band(after)
    if reason:
        dst.unlink(missing_ok=True)
        raise OutOfBand(reason)
    return after


# ---------------------------------------------------------------------------
# After the upload
# ---------------------------------------------------------------------------

def check_edge(url: str) -> dict:
    """HEAD the public key after an upload and report what the edge serves.
    Never raises: the upload has already happened and this is a reading."""
    try:
        import requests
        resp = requests.head(url, timeout=(10, 20), allow_redirects=True)
        return {
            "status": resp.status_code,
            "cf_cache_status": resp.headers.get("cf-cache-status", ""),
            "content_length": int(resp.headers.get("content-length") or 0) or None,
            "cache_control": resp.headers.get("cache-control", ""),
        }
    except Exception as exc:  # noqa: BLE001 — a reading, never a blocker
        return {"status": None, "cf_cache_status": "", "content_length": None,
                "error": str(exc)}


def read_log(digests_dir: Path) -> List[dict]:
    path = digests_dir / LOG_NAME
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    return data if isinstance(data, list) else []


def append_log(digests_dir: Path, entry: dict) -> Path:
    path = digests_dir / LOG_NAME
    entries = read_log(digests_dir)
    entries.append(entry)
    path.write_text(json.dumps(entries, indent=2, ensure_ascii=False) + "\n",
                    encoding="utf-8")
    return path


def already_remastered(digests_dir: Path, episode: int) -> Optional[dict]:
    """The log entry that says this episode's published file was already
    brought into the band — so a second ``--all`` pass does not pull it
    down again."""
    for entry in read_log(digests_dir):
        if entry.get("episode") != episode or not entry.get("applied"):
            continue
        after = entry.get("after") or {}
        if after.get("I") is not None and abs(after["I"] - TARGET_LUFS) <= TOLERANCE_LU:
            return entry
    return None


# ---------------------------------------------------------------------------
# One episode
# ---------------------------------------------------------------------------

def process_item(config, item: dict, *, apply: bool, skip_upload: bool,
                 workdir: Path, force: bool = False) -> dict:
    """Plan, render or apply one episode. Returns a result dict whose
    ``status`` is one of the ``STATUS_*`` constants."""
    result = {"episode": item.get("episode"), "file": item.get("filename"), "status": None}
    try:
        art = artifacts_from_item(config, item)
    except ValueError as exc:
        logger.warning("Ep%s: %s — skipped", item.get("episode"), exc)
        result["status"] = STATUS_FAILED
        result["reason"] = str(exc)
        return result

    # The object is replaced at the key the feed points to and nowhere
    # else. An enclosure that does not sit at the show's own key would be
    # a second object the feed never serves — refused, not guessed.
    src_url = download_url(item)
    if not src_url.endswith("/" + art.r2_key):
        logger.error("Ep%s: the published enclosure %s is not at this show's key %s — not touching it",
                     art.episode_num, src_url, art.r2_key)
        result["status"] = STATUS_FOREIGN
        return result

    if not force:
        prior = already_remastered(art.digests_dir, art.episode_num)
        if prior:
            logger.info("Ep%s: already re-mastered on %s (%s -> %s LUFS) — skipped",
                        art.episode_num, prior.get("remastered_at", "?"),
                        (prior.get("before") or {}).get("I"), (prior.get("after") or {}).get("I"))
            result["status"] = STATUS_ALREADY
            return result

    logger.info("Ep%s (%s): %s", art.episode_num, art.date_str, art.final_mp3.name)
    logger.info("  R2 key:  %s  (unchanged — subscribers keep their link)", art.r2_key)
    logger.info("  GUID:    %s  (kept)", item.get("guid") or "(none)")

    from engine.http_download import download_to
    downloaded = workdir / art.final_mp3.name
    try:
        bytes_before = download_to(src_url, downloaded, label=art.final_mp3.name)
    except Exception as exc:  # noqa: BLE001 — one file; the batch goes on
        logger.error("Ep%s: download failed: %s", art.episode_num, exc)
        result["status"] = STATUS_FAILED
        result["reason"] = f"download: {exc}"
        return result

    before = measure_loudness(downloaded)
    if not before:
        logger.warning("Ep%s: published audio could not be measured — not touching it", art.episode_num)
        result["status"] = STATUS_UNMEASURED
        return result
    result["before"] = before
    logger.info("  before:  I=%.1f LUFS  LRA=%s LU  TP=%s dBTP  (%d bytes)",
                before["I"], before.get("LRA"), before.get("TP"), bytes_before)

    gain = plan_gain(before)
    result["gain_db"] = gain
    if gain == 0.0:
        logger.info("  in band (%.0f ± %.1f LUFS) — skipped unchanged", TARGET_LUFS, TOLERANCE_LU)
        result["status"] = STATUS_SKIPPED
        return result

    rendered = workdir / f"remastered_{art.final_mp3.name}"
    cmd = render_cmd(downloaded, rendered, gain)
    logger.info("  planned gain: %+.1f dB", gain)
    logger.info("  planned render: %s", " ".join(cmd))

    if not apply and not skip_upload:
        logger.info("  would upload to r2://%s/%s (same key); feed item keeps its GUID, link and enclosure",
                    config.storage.bucket, art.r2_key)
        result["status"] = STATUS_PLANNED
        return result

    try:
        after = remaster_file(downloaded, rendered, gain)
    except OutOfBand as exc:
        logger.error("::error::Ep%s: REFUSED — %s. Nothing uploaded.", art.episode_num, exc)
        result["status"] = STATUS_REFUSED
        result["reason"] = str(exc)
        return result
    except subprocess.CalledProcessError as exc:
        logger.error("Ep%s: render failed: %s", art.episode_num,
                     (exc.stderr or b"").decode("utf-8", "replace")[-400:])
        result["status"] = STATUS_FAILED
        result["reason"] = "render"
        return result
    result["after"] = after
    bytes_after = rendered.stat().st_size
    duration = get_audio_duration(rendered) or 0.0
    logger.info("  after:   I=%.1f LUFS  LRA=%s LU  TP=%s dBTP  (%d bytes, %.0fs)",
                after["I"], after.get("LRA"), after.get("TP"), bytes_after, duration)

    if skip_upload or not apply:
        logger.info("  --skip-upload: rendered and verified; R2, the feed and the log untouched")
        result["status"] = STATUS_RENDERED
        return result

    # --- upload to the SAME key --------------------------------------------
    art.digests_dir.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(rendered, art.final_mp3)
    from engine.storage import upload_episode
    url = upload_episode(art.final_mp3, config)
    if not url:
        logger.error("::error::Ep%s: R2 upload failed or storage is unconfigured. "
                     "The feed still points at the OLD audio; not touching it.", art.episode_num)
        result["status"] = STATUS_FAILED
        result["reason"] = "upload"
        return result
    logger.info("  uploaded to %s", url)

    # --- the feed item, in place -------------------------------------------
    rs.refresh_rss_item(config, art, duration, item, uploaded_url=url)
    logger.info("  RSS item refreshed (duration + byte length; enclosure, link and GUID kept)")

    edge = check_edge(url)
    if edge.get("content_length") and edge["content_length"] != bytes_after:
        logger.info("  edge: cf-cache-status=%s serves %s bytes (old object; cache-control %r) — "
                    "it turns over within max-age", edge.get("cf_cache_status") or "?",
                    edge["content_length"], edge.get("cache_control", ""))
    else:
        logger.info("  edge: cf-cache-status=%s content-length=%s",
                    edge.get("cf_cache_status") or "?", edge.get("content_length"))

    entry = {
        "episode": art.episode_num,
        "file": art.final_mp3.name,
        "r2_key": art.r2_key,
        "guid": item.get("guid") or "",
        "remastered_at": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "before": before,
        "gain_db": gain,
        "after": after,
        "bytes_before": bytes_before,
        "bytes_after": bytes_after,
        "duration_s": round(duration, 1),
        "edge": {"cf_cache_status": edge.get("cf_cache_status", ""),
                 "content_length": edge.get("content_length")},
        "applied": True,
    }
    log_path = append_log(art.digests_dir, entry)
    logger.info("  logged to %s", log_path.relative_to(rs.ROOT) if log_path.is_relative_to(rs.ROOT) else log_path)
    result["status"] = STATUS_APPLIED
    return result


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--show", required=True, help="Show slug (e.g. unintended_consequences)")
    which = ap.add_mutually_exclusive_group(required=True)
    which.add_argument("--episode", type=int, help="One episode number")
    which.add_argument("--all", action="store_true", help="Every item on the show's feed")
    which.add_argument("--since", default="", metavar="YYYYMMDD",
                       help="Every item dated on or after this day")
    ap.add_argument("--limit", type=int, default=DEFAULT_LIMIT,
                    help=f"Episodes rendered per run (default {DEFAULT_LIMIT}; 0 = no cap)")
    ap.add_argument("--apply", action="store_true",
                    help="Upload to the same key, refresh the feed item, write the log. "
                         "Without it, nothing is written.")
    ap.add_argument("--skip-upload", action="store_true",
                    help="Render and re-measure only; do not touch R2, the feed or the log.")
    ap.add_argument("--force", action="store_true",
                    help="Look at an episode the log already lists as re-mastered.")
    args = ap.parse_args(argv)

    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s",
        stream=sys.stdout,
    )

    from engine.config import load_config
    try:
        config = load_config(ROOT / "shows" / f"{args.show}.yaml")
    except (FileNotFoundError, ValueError) as exc:
        logger.error("%s", exc)
        return 1

    rss_path = rs.ROOT / config.publishing.rss_file
    items = select_items(feed_items(rss_path), episode=args.episode,
                         all_items=args.all, since=args.since)
    if not items:
        logger.error("No matching item on %s", rss_path.name)
        return 1

    mode = "APPLY" if args.apply and not args.skip_upload else (
        "render only (--skip-upload)" if args.skip_upload else "DRY RUN")
    logger.info("Re-master %s: %d item(s) selected, limit %s, mode %s, band %.0f ± %.1f LUFS, "
                "true peak <= %.0f dBTP", config.name, len(items),
                args.limit or "none", mode, TARGET_LUFS, TOLERANCE_LU, TRUE_PEAK_MAX_DBTP)

    counts: Dict[str, int] = {}
    rendered_count = 0
    with tempfile.TemporaryDirectory(prefix="remaster_") as tmp:
        workdir = Path(tmp)
        for item in items:
            if args.limit and rendered_count >= args.limit:
                logger.info("Limit of %d rendered episode(s) reached — the rest wait for the next run",
                            args.limit)
                break
            result = process_item(config, item, apply=args.apply, skip_upload=args.skip_upload,
                                  workdir=workdir, force=args.force)
            counts[result["status"]] = counts.get(result["status"], 0) + 1
            if result["status"] in (STATUS_PLANNED, STATUS_RENDERED, STATUS_APPLIED, STATUS_REFUSED):
                rendered_count += 1
            for stale in workdir.glob("*.mp3"):
                stale.unlink(missing_ok=True)

    if not args.apply:
        logger.info("DRY RUN — nothing written. Re-run with --apply to render, verify, "
                    "upload to the same key and refresh the feed.")
    bad = sum(counts.get(s, 0) for s in _BAD_STATUSES)
    summary = " ".join(f"{k}={v}" for k, v in sorted(counts.items()) if k != STATUS_APPLIED)
    logger.info("REMASTER_SUMMARY applied=%d %s", counts.get(STATUS_APPLIED, 0), summary)
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
