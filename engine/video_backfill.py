"""Re-render a past episode's long-form video for the video podcast feed.

Why this exists
---------------
The video-podcast pilot keeps each episode's MP4 from the day it is
rendered onward, which means a freshly enabled show's feed contains
exactly one episode. Apple reviews a feed before it lists the show, and
routinely rejects one with a couple of items — so a new video show needs a
back catalogue before it is worth submitting.

Every *input* to the long-form render survives, even though the MP4s
themselves were deleted:

* the mixed episode MP3 is public on R2 (``audio.nerranetwork.com``),
* the cover art is committed under ``assets/covers/``,
* the scene stills live in the gallery R2 bucket, keyed per episode,
* the transcript JSON is committed, so the burn-in SRT is reproducible,
* ``chapters_ep<NNN>.json`` is committed, so the scene schedule is too.

``engine.video.build_long_form_video`` is pure ffmpeg — no network, no paid
API — so a re-render costs runner time and nothing else. This is the
English long-form counterpart of :mod:`engine.lang_dub`, which already does
exactly this for the dub channels, and it reuses that module's gallery
helpers directly so the two cannot drift apart.

What it deliberately does not touch: the audio feed, the website, summaries
content, YouTube, social. It renders, uploads, and records.

Coverage limit worth knowing: scene stills only exist in the gallery from
roughly tesla ep486 / spacex ep003 / fascinating_frontiers ep101 /
models_agents ep093 / models_agents_beginners ep052 onward. Older episodes
still render, but cover-only — reported as ``scene_count: 0`` rather than
failing, so the operator can see which ones are degraded.
"""

from __future__ import annotations

import logging
import tempfile
from pathlib import Path
from typing import Dict, Optional

from engine.ru_dub import (
    PROJECT_ROOT,
    _cover_path,
    _download_images,
    _fresh_manifest_path,
    gallery_images_for_episode,
)
from engine.summaries_io import load_summaries, upsert_video
from engine.video_feed import upload_episode_video
from engine.video_index import index_path, indexed_episodes, record_from_track

logger = logging.getLogger(__name__)

# The pipeline's fixed lead-in before speech starts; the burn-in SRT must be
# offset by it or every subtitle lands early. Identical (10.0) across all the
# video-podcast shows' ``audio.voice_intro_delay``.
_VOICE_INTRO_DELAY = 10.0


def _download_audio(url: str, dest: Path) -> Optional[Path]:
    """Fetch the published episode MP3. Strips an OP3 prefix if present."""
    if not url:
        return None
    if url.startswith("https://op3.dev/e/"):
        # Summaries stores the raw R2 URL, but be defensive: an OP3-prefixed
        # URL still resolves, it just adds a redirect hop we do not need.
        url = "https://" + url[len("https://op3.dev/e/"):]
    try:
        import requests

        resp = requests.get(url, timeout=300)
        resp.raise_for_status()
        dest.write_bytes(resp.content)
        return dest
    except Exception as exc:  # noqa: BLE001
        logger.warning("video_backfill: could not fetch audio %s: %s", url, exc)
        return None


def _build_srt(config, episode_num: int, date_str: str, dest_dir: Path) -> Optional[Path]:
    """Regenerate the burn-in SRT from the committed transcript JSON."""
    try:
        from engine.captions import find_transcript_for_episode, transcript_to_srt

        digests_dir = PROJECT_ROOT / config.episode.output_dir
        transcript = find_transcript_for_episode(
            digests_dir, config.episode.prefix, episode_num, date_str.replace("-", ""))
        if not transcript:
            return None
        srt = dest_dir / f"ep{episode_num:03d}.srt"
        transcript_to_srt(transcript, srt, audio_offset_seconds=_VOICE_INTRO_DELAY)
        return srt if srt.exists() else None
    except Exception as exc:  # noqa: BLE001 — captions are advisory
        logger.info("video_backfill: no captions for ep%s (%s)", episode_num, exc)
        return None


def _scene_schedule(config, episode_num: int, scenes):
    """Chapter-aligned scene schedule from the committed chapters JSON."""
    if not scenes:
        return None
    try:
        import json

        from engine.scene_scheduler import plan_chapter_schedule

        chapters_path = (PROJECT_ROOT / config.episode.output_dir
                         / f"chapters_ep{episode_num:03d}.json")
        if not chapters_path.exists():
            return None
        return plan_chapter_schedule(
            json.loads(chapters_path.read_text(encoding="utf-8")), scenes)
    except Exception as exc:  # noqa: BLE001 — uniform cadence is a fine fallback
        logger.info("video_backfill: no chapter schedule for ep%s (%s)",
                    episode_num, exc)
        return None


def backfill_episode_video(
    config,
    episode_num: int,
    *,
    force: bool = False,
    verify: bool = False,
    dry_run: bool = False,
) -> Dict[str, object]:
    """Render, upload and record one past episode's long-form video.

    Returns a status dict and never raises, so one bad episode cannot abort
    a batch. ``status`` is one of ``already_done``, ``not_enabled``,
    ``no_record``, ``no_cover``, ``no_audio``, ``render_failed``,
    ``upload_failed``, ``would_render`` (dry run), or ``ok``.

    Nothing is recorded unless the upload returned a URL. That ordering is
    what structurally guarantees the feed can never list an episode whose
    MP4 is missing — the one failure a feed cannot detect on its own.
    """
    from engine.video import build_long_form_video

    slug = config.slug
    vp = getattr(config, "video_podcast", None)
    if not (vp and vp.enabled):
        return {"status": "not_enabled", "episode": episode_num}

    idx = index_path(config)
    existing = indexed_episodes(idx).get(episode_num)
    if existing and not force:
        if not verify:
            return {"status": "already_done", "episode": episode_num,
                    "url": existing["url"]}
        try:
            import requests

            if requests.head(existing["url"], timeout=30,
                             allow_redirects=True).status_code == 200:
                return {"status": "already_done", "episode": episode_num,
                        "url": existing["url"]}
            logger.warning("[%s] ep%s recorded video is unreachable — re-rendering",
                           slug, episode_num)
        except Exception:  # noqa: BLE001 — an unverifiable URL gets re-rendered
            logger.warning("[%s] ep%s video HEAD failed — re-rendering",
                           slug, episode_num)

    summaries_path = PROJECT_ROOT / config.publishing.summaries_json
    try:
        _wrapper, records = load_summaries(summaries_path)
    except Exception as exc:  # noqa: BLE001
        return {"status": "no_record", "episode": episode_num, "error": str(exc)}

    rec = next((r for r in records if r.get("episode_num") == episode_num), None)
    if not rec or not rec.get("audio_url"):
        return {"status": "no_record", "episode": episode_num}

    date_str = str(rec.get("date") or "")[:10]
    cover = _cover_path(config)
    if not cover:
        return {"status": "no_cover", "episode": episode_num}

    if dry_run:
        return {"status": "would_render", "episode": episode_num,
                "audio_url": rec["audio_url"], "date": date_str}

    with tempfile.TemporaryDirectory() as tmp:
        tmp_dir = Path(tmp)

        audio = _download_audio(rec["audio_url"], tmp_dir / f"en_ep{episode_num:03d}.mp3")
        if not audio:
            return {"status": "no_audio", "episode": episode_num}

        # Scene stills: the gallery R2 bucket is the only surviving copy. The
        # public CDN 403s the original JPEGs from CI, so gallery_library falls
        # back to an authenticated S3 GET — which needs R2_GALLERY_BUCKET set.
        scenes = []
        try:
            urls = gallery_images_for_episode(
                slug, episode_num, intended_use="segment_card",
                manifest_path=_fresh_manifest_path(tmp_dir))
            scenes = _download_images(urls, tmp_dir)
        except Exception as exc:  # noqa: BLE001 — degrade to cover-only
            logger.warning("[%s] ep%s scene fetch failed: %s", slug, episode_num, exc)
        if len(scenes) < 2:
            logger.warning("[%s] ep%s has %d scene image(s) — rendering cover-only",
                           slug, episode_num, len(scenes))

        srt = _build_srt(config, episode_num, date_str, tmp_dir)
        schedule = _scene_schedule(config, episode_num, scenes)

        # Derive the filename from the published audio so a backfill and a
        # live run of the same episode converge on one R2 object rather than
        # two under different names.
        stem = Path(rec["audio_url"].split("?")[0]).stem
        out_mp4 = tmp_dir / f"{stem}.mp4"

        try:
            build_long_form_video(
                audio, cover, out_mp4,
                scene_paths=scenes if len(scenes) >= 2 else None,
                subtitles_path=srt,
                show_name=config.name,
                scene_schedule=schedule,
            )
        except Exception as exc:  # noqa: BLE001
            logger.error("[%s] ep%s render failed: %s", slug, episode_num, exc)
            return {"status": "render_failed", "episode": episode_num,
                    "error": str(exc)}

        if not out_mp4.exists():
            return {"status": "render_failed", "episode": episode_num,
                    "error": "renderer produced no file"}

        duration = 0.0
        try:
            from engine.audio import get_audio_duration

            duration = float(get_audio_duration(audio) or 0.0)
        except Exception:  # noqa: BLE001 — duration is advisory
            pass

        track = upload_episode_video(out_mp4, config)
        if not track:
            return {"status": "upload_failed", "episode": episode_num}
        track["duration_sec"] = duration

    record_from_track(
        config, episode_num, track, date=date_str,
        title=rec.get("episode_title") or f"Episode {episode_num}")
    # Best-effort: only lands when the episode is still inside the summaries
    # window. The index above is the durable copy.
    upsert_video(summaries_path, episode_num, track)

    return {
        "status": "ok",
        "episode": episode_num,
        "url": track["url"],
        "bytes": track.get("bytes"),
        "scene_count": len(scenes),
        "captions": bool(srt),
    }
