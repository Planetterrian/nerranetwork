"""Cross-platform distribution for a single Short (orchestrator).

For each YouTube Short the pipeline publishes, this (when
``config.youtube.multi_platform_enabled``) additionally:

  1. renders a **safe-zone variant** MP4 — overlays lifted out of the bottom/
     right bands that Instagram Reels & TikTok draw their own UI over (drops the
     bottom URL pill + end-card, raises the captions);
  2. writes a **``<short>.social.json`` sidecar** with per-platform caption +
     hashtags (``engine.social_metadata``);
  3. optionally **hosts the MP4 on R2** (needed so Instagram's URL-based Graph
     API — and the operator — can fetch a non-ephemeral asset);
  4. **posts** to the enabled platforms via ``engine.social_publisher`` (a
     no-op until credentials are configured).

Every step is best-effort and non-fatal: a distribution failure must never
block the episode. The whole thing is a no-op unless the show opts in.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Dict, Optional, Sequence

logger = logging.getLogger(__name__)


def _maybe_upload_r2(local_path: Path, key_prefix: str) -> str:
    """Upload to the gallery R2 bucket and return a public URL, or "" if R2
    isn't configured (clean fall-through)."""
    try:
        from engine.gallery_uploader import gallery_config_from_env
        from engine.storage import upload_to_r2
        cfg = gallery_config_from_env()
        if not (cfg.is_configured and cfg.public_base_url):
            return ""
        key = f"{key_prefix.strip('/')}/{local_path.name}"
        return upload_to_r2(
            local_path, key,
            bucket=cfg.bucket, endpoint_url=cfg.endpoint_url,
            access_key=cfg.access_key, secret_key=cfg.secret_key,
            public_base_url=cfg.public_base_url, content_type="video/mp4",
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("Social R2 upload failed (non-fatal): %s", exc)
        return ""


def distribute_short(
    config,
    *,
    audio_path: Path,
    cover_path: Path,
    work_dir: Path,
    base_name: str,
    short_suffix: str = "",
    start_offset: float = 0.0,
    duration: float = 55.0,
    hook: str = "",
    show_name: str = "",
    show_url: str = "",
    scene_paths: Optional[Sequence[Path]] = None,
    subtitles_path: Optional[Path] = None,
    long_form_url: str = "",
    short_youtube_url: str = "",
    show_keywords: Optional[Sequence[str]] = None,
    is_ru: bool = False,
) -> Dict:
    """Produce + (optionally) post the social variant of one Short.

    Returns a summary dict (paths + per-platform post status). No-op (returns
    ``{}``) unless ``config.youtube.multi_platform_enabled``.
    """
    yt = getattr(config, "youtube", None)
    if not getattr(yt, "multi_platform_enabled", False):
        return {}

    result: Dict = {}
    social_mp4 = work_dir / f"{base_name}_short{short_suffix}_social.mp4"

    # 1) Safe-zone variant MP4 (no URL pill, no end-card, captions lifted).
    try:
        from engine.video import build_short_video
        build_short_video(
            audio_path, cover_path, social_mp4,
            start_offset=start_offset, duration=duration,
            hook=hook, scene_paths=scene_paths, show_name=show_name,
            subtitles_path=subtitles_path,
            end_card=False,
            drop_url_pill=getattr(yt, "social_drop_url_pill", True),
            caption_margin_v=getattr(yt, "social_caption_margin_v", 480),
        )
        result["video"] = str(social_mp4)
    except Exception as exc:  # noqa: BLE001
        logger.warning("Social safe-zone Short render failed (non-fatal): %s", exc)
        return result

    # 2) Per-platform metadata sidecar.
    try:
        from engine.social_metadata import build_social_metadata
        meta = build_social_metadata(
            hook=hook, show_name=show_name, show_url=show_url,
            long_form_url=long_form_url, short_youtube_url=short_youtube_url,
            show_keywords=show_keywords, is_ru=is_ru,
        )
        sidecar = social_mp4.with_suffix(".social.json")
        sidecar.write_text(json.dumps(meta, indent=2, ensure_ascii=False), encoding="utf-8")
        result["sidecar"] = str(sidecar)
    except Exception as exc:  # noqa: BLE001
        logger.warning("Social metadata sidecar failed (non-fatal): %s", exc)
        return result

    # 3) Host on R2 (so IG can fetch it + the operator can grab it).
    public_url = ""
    prefix = getattr(yt, "social_r2_prefix", "") or ""
    if prefix:
        public_url = _maybe_upload_r2(social_mp4, prefix)
        if public_url:
            result["public_url"] = public_url

    # 4) Post to enabled platforms (no-op without credentials).
    try:
        from engine.social_publisher import publish_short
        result["posted"] = publish_short(
            video_path=social_mp4, metadata=meta, video_public_url=public_url,
            instagram=getattr(yt, "instagram_enabled", False),
            tiktok=getattr(yt, "tiktok_enabled", False),
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("Social publish dispatch failed (non-fatal): %s", exc)

    return result
