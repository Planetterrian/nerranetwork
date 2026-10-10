"""Native media on X: upload a clip or an image, then post it (Oct 10 2026).

Since April 2026 X bills a post that contains a URL at $0.20, a plain post
at $0.015, and each uploaded media object as one more $0.015. A show's own
Short uploaded as native video with a one-line hook and no link costs about
$0.03, and native video reaches further on X than a link post; the profile
link carries people to nerranetwork.com. (Patrick, Oct 10 2026: every show
except Tesla Shorts Time posts this way on @nerranetwork.)

The upload is X's v2 chunked flow, signed with the same OAuth 1.0a user keys
tweepy uses for the post:

    POST /2/media/upload/initialize        JSON  media_type, total_bytes, media_category
    POST /2/media/upload/{id}/append       form  segment_index + media (<= 5 MB each)
    POST /2/media/upload/{id}/finalize
    GET  /2/media/upload?command=STATUS&media_id={id}   until "succeeded"

The old ``command=INIT/APPEND/FINALIZE`` form is deprecated. Every failure is
logged and returned as ``None``; nothing here raises into an episode.
"""
from __future__ import annotations

import logging
import mimetypes
import re
import time
from pathlib import Path
from typing import Callable, Optional

logger = logging.getLogger(__name__)

UPLOAD_URL = "https://api.x.com/2/media/upload"
CHUNK_BYTES = 4 * 1024 * 1024          # X asks for <= 5 MB per segment
STATUS_TIMEOUT_S = 300                  # a one-minute Short processes in seconds

_CATEGORY = {
    "video/mp4": "tweet_video",
    "image/jpeg": "tweet_image",
    "image/png": "tweet_image",
    "image/webp": "tweet_image",
    "image/gif": "tweet_gif",
}


def _auth(creds: dict):
    from requests_oauthlib import OAuth1
    return OAuth1(creds["consumer_key"], creds["consumer_secret"],
                  creds["access_token"], creds["access_token_secret"])


def _describe(exc: Exception) -> str:
    resp = getattr(exc, "response", None)
    if resp is not None:
        body = (getattr(resp, "text", "") or "")[:300]
        return f"HTTP {getattr(resp, 'status_code', '?')}: {body}"
    return f"{type(exc).__name__}: {exc}"


def _info(resp) -> dict:
    try:
        return ((resp.json() or {}).get("data") or {}).get("processing_info") or {}
    except ValueError:
        return {}


def upload_media(path, creds: dict, *, session=None,
                 sleep: Callable[[float], None] = time.sleep,
                 timeout: int = 120) -> Optional[str]:
    """Upload one file and return its media id, or ``None`` on any failure."""
    path = Path(path)
    if not path.is_file():
        logger.warning("X media upload skipped: %s does not exist", path)
        return None
    media_type = mimetypes.guess_type(path.name)[0] or ""
    category = _CATEGORY.get(media_type)
    if not category:
        logger.warning("X media upload skipped: %s is not a video or image (%r)",
                       path.name, media_type)
        return None
    import requests
    http = session or requests.Session()
    auth = _auth(creds)
    try:
        r = http.post(f"{UPLOAD_URL}/initialize", auth=auth, timeout=timeout,
                      json={"media_type": media_type, "total_bytes": path.stat().st_size,
                            "media_category": category})
        r.raise_for_status()
        media_id = str(r.json()["data"]["id"])
        with path.open("rb") as fh:
            index = 0
            while True:
                chunk = fh.read(CHUNK_BYTES)
                if not chunk:
                    break
                r = http.post(f"{UPLOAD_URL}/{media_id}/append", auth=auth, timeout=timeout,
                              data={"segment_index": str(index)},
                              files={"media": (path.name, chunk, "application/octet-stream")})
                r.raise_for_status()
                index += 1
        r = http.post(f"{UPLOAD_URL}/{media_id}/finalize", auth=auth, timeout=timeout)
        r.raise_for_status()
        info, waited = _info(r), 0.0
        while info.get("state") in ("pending", "in_progress"):
            if waited >= STATUS_TIMEOUT_S:
                logger.warning("X media %s still processing after %ss; giving up",
                               media_id, int(waited))
                return None
            delay = max(1.0, float(info.get("check_after_secs") or 5))
            sleep(delay)
            waited += delay
            r = http.get(UPLOAD_URL, auth=auth, timeout=timeout,
                         params={"command": "STATUS", "media_id": media_id})
            r.raise_for_status()
            info = _info(r)
        if info.get("state") == "failed":
            logger.warning("X rejected media %s: %s", path.name, info.get("error"))
            return None
        logger.info("Uploaded %s to X as media %s", path.name, media_id)
        return media_id
    except Exception as exc:  # noqa: BLE001 — never raise into the episode
        logger.warning("X media upload failed for %s: %s", path.name, _describe(exc))
        return None


# X turns any URL in the text into a link, and a post with a link is billed
# at $0.20 instead of $0.015. Hooks rarely carry one, but one stray URL
# should not cost thirteen posts.
_URL = re.compile(r"(?i)\b(?:https?://|www\.)\S+")


def strip_links(text: str) -> str:
    out = _URL.sub("", text or "")
    return re.sub(r"[ \t]{2,}", " ", out).strip()
