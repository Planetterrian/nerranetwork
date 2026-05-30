"""Publish a Short to Instagram Reels / TikTok (credential-gated, no-op by default).

This is the integration seam for cross-posting the safe-zone Short MP4 produced
by the pipeline. It is a **clean no-op until the platform credentials are set**
(via env vars), so wiring it in is safe before the operator has finished the
one-time developer-app setup. Each call returns a structured status dict
(``posted`` / ``skipped`` / ``error``) and never raises — distribution must
never block an episode.

Reality check (why this needs operator setup, not just code):
  * **Instagram Reels** uses the Instagram Graph API, which requires a
    Business/Creator account linked to a Facebook Page + an approved Meta app
    with ``instagram_content_publish``. It is **URL-based**: you create a media
    container pointing at a *publicly reachable* video URL, then publish it —
    so the Short must be hosted first (e.g. the gallery R2 bucket). Env:
    ``IG_ACCESS_TOKEN``, ``IG_USER_ID``.
  * **TikTok** uses the Content Posting API, which requires a registered TikTok
    developer app with the ``video.publish`` scope (app review) and a user
    OAuth access token. Supports direct file upload. Env:
    ``TIKTOK_ACCESS_TOKEN``.

See ``docs/social_distribution.md`` for the full setup. Until then, the
pipeline still emits a ``<short>.social.json`` sidecar + safe-zone MP4 so the
operator can post manually.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Dict, Optional

logger = logging.getLogger(__name__)

_GRAPH_BASE = "https://graph.facebook.com/v21.0"
_TIKTOK_BASE = "https://open.tiktokapis.com/v2"


def _status(platform: str, state: str, **extra) -> Dict:
    out = {"platform": platform, "status": state}
    out.update(extra)
    return out


# ---------------------------------------------------------------------------
# Instagram Reels (Graph API — container then publish; needs a public video URL)
# ---------------------------------------------------------------------------

def publish_to_instagram(
    *,
    video_public_url: str,
    caption: str,
    access_token: Optional[str] = None,
    ig_user_id: Optional[str] = None,
    timeout: int = 60,
) -> Dict:
    access_token = access_token or os.getenv("IG_ACCESS_TOKEN", "").strip()
    ig_user_id = ig_user_id or os.getenv("IG_USER_ID", "").strip()
    if not access_token or not ig_user_id:
        return _status("instagram_reels", "skipped", reason="IG_ACCESS_TOKEN / IG_USER_ID not set")
    if not video_public_url:
        return _status("instagram_reels", "skipped", reason="no public video URL (host the MP4 first, e.g. R2)")
    try:
        import requests
        # 1) create a REELS media container pointing at the hosted MP4
        r = requests.post(
            f"{_GRAPH_BASE}/{ig_user_id}/media",
            data={
                "media_type": "REELS",
                "video_url": video_public_url,
                "caption": caption,
                "access_token": access_token,
            },
            timeout=timeout,
        )
        r.raise_for_status()
        creation_id = r.json().get("id")
        if not creation_id:
            return _status("instagram_reels", "error", detail="no creation id returned")
        # 2) publish the container (the operator should poll container status
        #    for large videos; small Reels are usually ready quickly).
        pub = requests.post(
            f"{_GRAPH_BASE}/{ig_user_id}/media_publish",
            data={"creation_id": creation_id, "access_token": access_token},
            timeout=timeout,
        )
        pub.raise_for_status()
        return _status("instagram_reels", "posted", media_id=pub.json().get("id"))
    except Exception as exc:  # noqa: BLE001
        logger.warning("Instagram publish failed (non-fatal): %s", exc)
        return _status("instagram_reels", "error", detail=str(exc))


# ---------------------------------------------------------------------------
# TikTok (Content Posting API — direct file upload)
# ---------------------------------------------------------------------------

def publish_to_tiktok(
    *,
    video_path: Path,
    caption: str,
    access_token: Optional[str] = None,
    timeout: int = 120,
) -> Dict:
    access_token = access_token or os.getenv("TIKTOK_ACCESS_TOKEN", "").strip()
    if not access_token:
        return _status("tiktok", "skipped", reason="TIKTOK_ACCESS_TOKEN not set")
    video_path = Path(video_path)
    if not video_path.exists():
        return _status("tiktok", "error", detail=f"video not found: {video_path}")
    try:
        import requests
        size = video_path.stat().st_size
        headers = {"Authorization": f"Bearer {access_token}"}
        # 1) init a direct-post upload (single chunk for a short clip)
        init = requests.post(
            f"{_TIKTOK_BASE}/post/publish/video/init/",
            headers={**headers, "Content-Type": "application/json; charset=UTF-8"},
            json={
                "post_info": {"title": caption[:2200], "privacy_level": "SELF_ONLY"},
                "source_info": {
                    "source": "FILE_UPLOAD",
                    "video_size": size,
                    "chunk_size": size,
                    "total_chunk_count": 1,
                },
            },
            timeout=timeout,
        )
        init.raise_for_status()
        data = (init.json() or {}).get("data", {})
        upload_url = data.get("upload_url")
        publish_id = data.get("publish_id")
        if not upload_url:
            return _status("tiktok", "error", detail="no upload_url returned")
        # 2) upload the bytes
        with video_path.open("rb") as fh:
            up = requests.put(
                upload_url,
                headers={
                    "Content-Type": "video/mp4",
                    "Content-Range": f"bytes 0-{size - 1}/{size}",
                },
                data=fh.read(),
                timeout=timeout,
            )
        up.raise_for_status()
        # NOTE: privacy_level is SELF_ONLY until the app passes TikTok review;
        # operator flips it to PUBLIC_TO_EVERYONE after audit. Status can be
        # polled via /post/publish/status/fetch/ with publish_id.
        return _status("tiktok", "posted", publish_id=publish_id)
    except Exception as exc:  # noqa: BLE001
        logger.warning("TikTok publish failed (non-fatal): %s", exc)
        return _status("tiktok", "error", detail=str(exc))


# ---------------------------------------------------------------------------
# Dispatcher
# ---------------------------------------------------------------------------

def publish_short(
    *,
    video_path: Path,
    metadata: Dict,
    video_public_url: str = "",
    instagram: bool = False,
    tiktok: bool = False,
) -> Dict[str, Dict]:
    """Post a Short to the enabled platforms. Returns {platform: status}.

    Each platform is independent and best-effort: a failure or missing
    credential on one never affects the others or the episode. ``metadata`` is
    the dict from ``engine.social_metadata.build_social_metadata``.
    """
    results: Dict[str, Dict] = {}
    if instagram:
        cap = (metadata.get("instagram_reels") or {}).get("caption", "")
        results["instagram_reels"] = publish_to_instagram(
            video_public_url=video_public_url, caption=cap,
        )
    if tiktok:
        cap = (metadata.get("tiktok") or {}).get("caption", "")
        results["tiktok"] = publish_to_tiktok(video_path=Path(video_path), caption=cap)
    return results
