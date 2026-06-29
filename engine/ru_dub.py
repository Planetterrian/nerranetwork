"""Russian-dubbed YouTube videos for the English shows (@NerraRU).

The English shows already auto-generate a Russian *audio* track per episode
(``engine.multilingual`` → ``languages: [ru, …]``) which today only becomes an
R2 file + a per-language podcast RSS feed. This module turns that existing
Russian track into a **video** and uploads it to the @NerraRU YouTube channel,
reusing the episode's already-generated Grok scene images (pulled from the
gallery manifest's public R2 URLs — zero extra image-generation cost).

Design contract (mirrors every optional integration here):
  - Runs in the **decoupled multilingual workflow**, never the episode's
    critical path — so it cannot re-introduce the timeout/partial-publish
    landmine that decoupling exists to prevent.
  - Fully best-effort + self-guarding: returns a status dict, never raises.
    No-ops cleanly when the show hasn't opted in (``youtube.ru_dub_enabled``),
    the RU track doesn't exist yet, the @NerraRU credentials
    (``YOUTUBE_REFRESH_TOKEN_RU``) aren't set, or anything fails.
  - English upload + the RU podcast feed are completely unaffected.

See ``docs/ru_youtube_dubs.md``.
"""

from __future__ import annotations

import logging
import tempfile
from pathlib import Path
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parent.parent
_MANIFEST = PROJECT_ROOT / "site" / "data" / "gallery-manifest.json"

# Russian AI-voice disclosure appended to every RU description (same text the
# native RU shows speak; kept in sync with run_show._AI_DISCLOSURE_RU).
_AI_DISCLOSURE_RU = (
    "Дисклеймер об ИИ: подкаст курирует Патрик, "
    "а озвучка создаётся с помощью ИИ-синтеза голоса."
)


def _episode_id(episode_num: int) -> str:
    return f"ep{episode_num:03d}"


def gallery_images_for_episode(
    show_slug: str, episode_num: int, *,
    intended_use: str = "segment_card",
    manifest_path: Path = _MANIFEST,
) -> List[str]:
    """Public R2 URLs of this episode's scene images, in document order.

    Filters the committed gallery manifest by ``show_slug`` + ``episode_id``
    + ``intended_use`` (``segment_card`` = the 16:9 long-form scenes;
    ``social`` = the 9:16 Shorts scenes). Empty list when the manifest has no
    entry yet (the manifest rebuild can lag the newest episode — caller falls
    back to the cover image, and a later sweep picks up the real scenes).
    """
    import json
    try:
        data = json.loads(Path(manifest_path).read_text(encoding="utf-8"))
    except Exception as exc:  # noqa: BLE001
        logger.info("ru_dub: gallery manifest unreadable (%s) — no scenes", exc)
        return []
    eid = _episode_id(episode_num)
    urls: List[str] = []
    for img in data.get("images", []):
        if (img.get("show_slug") == show_slug
                and (img.get("episode_id") or "").lower() == eid
                and img.get("intended_use") == intended_use
                and img.get("original_url")):
            urls.append(img["original_url"])
    return urls


def _download_images(urls: List[str], dest_dir: Path) -> List[Path]:
    """Best-effort download of *urls* → dest_dir. Skips any that fail."""
    import requests
    paths: List[Path] = []
    for i, url in enumerate(urls):
        try:
            resp = requests.get(url, timeout=60)
            resp.raise_for_status()
            ext = ".jpg" if ".jpg" in url.lower() or ".jpeg" in url.lower() else ".png"
            p = dest_dir / f"scene_{i:02d}{ext}"
            p.write_bytes(resp.content)
            paths.append(p)
        except Exception as exc:  # noqa: BLE001
            logger.warning("ru_dub: failed to fetch scene %s: %s", url, exc)
    return paths


def _resolve_ru_audio(config, episode_num: int, rec: dict,
                      ru_track: dict, dest_dir: Path) -> Optional[Path]:
    """Local path to the RU mp3 — the freshly-rendered local file if present,
    else downloaded from the track's R2 ``audio_url``."""
    output_dir = PROJECT_ROOT / config.episode.output_dir
    local = sorted(output_dir.glob(f"*_Ep{episode_num:03d}_*.ru.mp3"))
    if local:
        return local[-1]
    url = ru_track.get("audio_url", "")
    if not url:
        return None
    try:
        import requests
        resp = requests.get(url, timeout=120)
        resp.raise_for_status()
        p = dest_dir / f"ru_audio_ep{episode_num:03d}.mp3"
        p.write_bytes(resp.content)
        return p
    except Exception as exc:  # noqa: BLE001
        logger.warning("ru_dub: could not fetch RU audio %s: %s", url, exc)
        return None


def _cover_path(config) -> Optional[Path]:
    cands = [
        PROJECT_ROOT / "assets" / "covers" / f"{config.slug.replace('_', '-')}.jpg",
        PROJECT_ROOT / "assets" / "covers" / f"{config.slug}.jpg",
    ]
    rss_image = getattr(config.publishing, "rss_image", "") or ""
    base = rss_image.rstrip("/").rsplit("/", 1)[-1]
    if base:
        cands.append(PROJECT_ROOT / "assets" / "covers" / base)
    return next((c for c in cands if c.exists()), None)


def _hashtags(config) -> str:
    tags = [t for t in (getattr(config, "keywords", []) or [])][:3]
    parts = []
    for t in tags:
        cleaned = "".join(ch for ch in t.title() if ch.isalnum())
        if cleaned:
            parts.append("#" + cleaned)
    return " ".join(parts)


def _ru_long_description(config, ru_desc: str) -> str:
    base_url = getattr(config.publishing, "base_url", "https://nerranetwork.com")
    lines = [ru_desc.strip(), "", f"🎧 {base_url}", "", _AI_DISCLOSURE_RU]
    tags = _hashtags(config)
    if tags:
        lines += ["", tags]
    return "\n".join(lines).strip()


def _cap_title(title: str, limit: int = 95) -> str:
    title = (title or "").strip()
    return title if len(title) <= limit else title[: limit - 1].rstrip() + "…"


def publish_ru_dub(
    config, episode_num: int, *,
    build_short: bool = True,
    dry_run: bool = False,
) -> Dict[str, object]:
    """Build + upload the Russian-dubbed long-form (and optional Short) for
    one episode of an English show. Returns a status dict; never raises."""
    result: Dict[str, object] = {"status": "skip"}
    yt = getattr(config, "youtube", None)
    if not (yt and getattr(yt, "ru_dub_enabled", False)):
        return result
    ml = getattr(config, "multilingual", None)
    if not (ml and ml.enabled and "ru" in (ml.languages or [])):
        result["status"] = "no_ru_lang"
        return result

    # The RU audio track must already exist (the multilingual sweep makes it).
    from engine.summaries_io import load_summaries
    summaries_path = PROJECT_ROOT / config.publishing.summaries_json
    try:
        _w, records = load_summaries(summaries_path)
    except Exception as exc:  # noqa: BLE001
        logger.warning("ru_dub: cannot read summaries: %s", exc)
        return result
    rec = next((r for r in records if r.get("episode_num") == episode_num), None)
    if not rec:
        result["status"] = "no_record"
        return result
    ru_track = (rec.get("translations", {}) or {}).get("ru")
    if not ru_track:
        result["status"] = "no_ru_track"  # translation hasn't run yet
        return result

    ru_title = _cap_title(ru_track.get("title") or rec.get("episode_title") or "")
    ru_desc = ru_track.get("description") or ru_title

    # Dry-run is creds-independent so the operator can preview the resolved
    # RU title before doing the @NerraRU OAuth.
    if dry_run:
        result.update(status="dryrun", title=ru_title)
        return result

    from engine.youtube import get_channel_credentials_from_env
    creds = get_channel_credentials_from_env("ru")
    if creds is None:
        result["status"] = "no_ru_credentials"  # YOUTUBE_REFRESH_TOKEN_RU unset
        return result

    cover = _cover_path(config)
    if cover is None:
        logger.warning("ru_dub: no cover art for %s — skip", config.slug)
        result["status"] = "no_cover"
        return result

    from engine.video import build_long_form_video, build_short_video
    from engine.youtube import upload_video, add_video_to_playlist
    from engine.youtube_index import record_video

    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        audio = _resolve_ru_audio(config, episode_num, rec, ru_track, tmp)
        if audio is None:
            result["status"] = "no_ru_audio"
            return result

        # Reuse the episode's already-generated 16:9 scene images (zero cost).
        long_urls = gallery_images_for_episode(
            config.slug, episode_num, intended_use="segment_card")
        long_scenes = _download_images(long_urls, tmp) if long_urls else []
        date_str = (rec.get("date") or "")[:10]

        # --- Long-form ---
        try:
            from engine.publisher import generate_episode_thumbnail
            thumb = tmp / "ru_thumb.jpg"
            generate_episode_thumbnail(
                cover, episode_num, date_str, thumb,
                hook=ru_title, show_name=config.name)
            thumb_path = thumb if thumb.exists() else None
        except Exception as exc:  # noqa: BLE001
            logger.warning("ru_dub: thumbnail failed (%s) — uploading without", exc)
            thumb_path = None

        long_mp4 = tmp / f"ru_long_ep{episode_num:03d}.mp4"
        try:
            build_long_form_video(
                audio, cover, long_mp4,
                scene_paths=long_scenes if len(long_scenes) >= 2 else None,
                show_name=config.name)
        except Exception as exc:  # noqa: BLE001
            logger.error("ru_dub: long-form render failed for Ep%s: %s",
                         episode_num, exc)
            result["status"] = "render_failed"
            return result

        long_url = ""
        try:
            up = upload_video(
                long_mp4, credentials=creds,
                title=ru_title,
                description=_ru_long_description(config, ru_desc),
                tags=list(getattr(config, "keywords", []) or []),
                category_id=int(getattr(yt, "category_id", 28)),
                default_language="ru",
                privacy_status=getattr(yt, "privacy_status", "public"),
                thumbnail_path=thumb_path,
            )
            long_url = up.watch_url
            result["long_url"] = long_url
            record_video(
                video_id=up.video_id, show_slug=config.slug, episode=episode_num,
                kind="long", title=ru_title, hook=ru_title, published=date_str,
                watch_url=long_url, channel="ru",
                index_path=PROJECT_ROOT / config.episode.output_dir
                / "youtube_videos.ru.json")
            pl = (getattr(yt, "ru_podcast_playlist_id", None) or "").strip()
            if pl:
                try:
                    add_video_to_playlist(credentials=creds,
                                          video_id=up.video_id, playlist_id=pl)
                except Exception as exc:  # noqa: BLE001
                    logger.warning("ru_dub: playlist add failed: %s", exc)
            else:
                logger.info("ru_dub: no ru_podcast_playlist_id — skipped playlist")
        except Exception as exc:  # noqa: BLE001
            logger.error("ru_dub: long-form upload failed for Ep%s: %s",
                         episode_num, exc)
            result["status"] = "upload_failed"
            return result

        result["status"] = "done"

        # --- Short (best-effort; failure never blocks the long-form result) ---
        if build_short and getattr(yt, "publish_shorts", True):
            try:
                short_urls = gallery_images_for_episode(
                    config.slug, episode_num, intended_use="social")
                short_scenes = _download_images(short_urls, tmp) if short_urls else []
                short_mp4 = tmp / f"ru_short_ep{episode_num:03d}.mp4"
                build_short_video(
                    audio, cover, short_mp4,
                    start_offset=float(getattr(yt, "shorts_start_offset", 0.0) or 0.0),
                    duration=float(getattr(yt, "short_duration_seconds", 55.0)),
                    hook=ru_title,
                    scene_paths=short_scenes if len(short_scenes) >= 2 else None,
                    show_name=config.name)
                sup = upload_video(
                    short_mp4, credentials=creds,
                    title=_cap_title(ru_title, 90) + " #Shorts",
                    description=_ru_long_description(config, ru_desc),
                    tags=list(getattr(config, "keywords", []) or []),
                    category_id=int(getattr(yt, "category_id", 28)),
                    default_language="ru",
                    privacy_status=getattr(yt, "privacy_status", "public"))
                result["short_url"] = sup.watch_url
                record_video(
                    video_id=sup.video_id, show_slug=config.slug,
                    episode=episode_num, kind="short", title=ru_title,
                    hook=ru_title, published=date_str, watch_url=sup.watch_url,
                    channel="ru",
                    index_path=PROJECT_ROOT / config.episode.output_dir
                    / "youtube_videos.ru.json")
                pl = (getattr(yt, "ru_podcast_playlist_id", None) or "").strip()
                if pl:
                    try:
                        add_video_to_playlist(credentials=creds,
                                              video_id=sup.video_id, playlist_id=pl)
                    except Exception:  # noqa: BLE001
                        pass
            except Exception as exc:  # noqa: BLE001
                logger.warning("ru_dub: Short failed for Ep%s (non-fatal): %s",
                               episode_num, exc)
                result["short_error"] = str(exc)

    return result
