"""Muted preview loops for the homepage Shorts reel (Oct 18 2026).

The front page's Shorts reel (``templates/network_page.html.j2``,
``shorts_reel``) plays a short, silent, looping preview of each Short while
its card is on screen. The preview is cut from the Short MP4 the video stage
already rendered, so it costs one ffmpeg pass and one small R2 upload — no
new render, no new model call.

* :func:`make_short_preview` cuts ~6 s from the Short: no audio, 360 px wide
  (9:16), H.264 yuv420p, ~24 fps, CRF ~30, ``+faststart`` so a browser can
  start it before the whole file arrives, and roughly 600 KB at most (one
  re-encode at a lower bitrate when the first pass runs over). Returns
  ``False`` on ANY failure — a preview is never worth a publish.
* :func:`upload_short_preview` puts it on R2 at
  ``previews/<slug>/ep<NNN>-short<index>.mp4`` with ``video/mp4`` — its own
  keyspace, never ``<slug>/...``, which is the audio keyspace every published
  enclosure depends on (CLAUDE.md "Do NOT change R2 bucket paths"). Returns
  the public URL, or ``""`` when R2 is not configured or the upload fails.

The caller records the URL as ``preview_url`` on the Short's row in
``digests/<dir>/youtube_videos.json``; a row without one renders the still
scene image, exactly as before.
"""
from __future__ import annotations

import logging
import os
import shutil
import subprocess
from pathlib import Path

logger = logging.getLogger(__name__)

#: Preview geometry and encode settings (the reel card is ~180-240 css px
#: wide, so 360 px covers a 2x screen).
PREVIEW_WIDTH = 360
PREVIEW_HEIGHT = 640
PREVIEW_FPS = 24
PREVIEW_CRF = 30
PREVIEW_SECONDS = 6.0
#: Soft cap: a first pass over this re-encodes once at a bitrate that fits.
PREVIEW_MAX_BYTES = 600_000

#: R2 layout. The bucket and public host follow the audio bucket by default
#: (one CDN, one credential set) under a prefix of their own.
R2_PREFIX = "previews"
R2_BUCKET = os.getenv("SHORT_PREVIEW_R2_BUCKET", "podcast-audio")
R2_PUBLIC_BASE = os.getenv("SHORT_PREVIEW_R2_PUBLIC_BASE",
                           "https://audio.nerranetwork.com").rstrip("/")
CONTENT_TYPE = "video/mp4"

_TIMEOUT_S = 120


def preview_r2_key(show_slug: str, episode: int, index: int = 1) -> str:
    """``previews/tesla/ep638-short1.mp4``."""
    return f"{R2_PREFIX}/{show_slug}/ep{int(episode):03d}-short{int(index)}.mp4"


def _encode_cmd(src: Path, dst: Path, *, start_s: float, seconds: float,
                bitrate_k: int = 0) -> list:
    # Fill a 9:16 frame whatever the source shape: scale to cover, centre crop.
    vf = (f"scale={PREVIEW_WIDTH}:{PREVIEW_HEIGHT}:force_original_aspect_ratio=increase,"
          f"crop={PREVIEW_WIDTH}:{PREVIEW_HEIGHT},fps={PREVIEW_FPS},setsar=1,format=yuv420p")
    cmd = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
           "-ss", f"{max(0.0, float(start_s)):.3f}", "-i", str(src),
           "-t", f"{max(0.5, float(seconds)):.3f}",
           "-an", "-sn", "-dn", "-vf", vf,
           "-c:v", "libx264", "-preset", "veryfast", "-profile:v", "main",
           "-pix_fmt", "yuv420p"]
    if bitrate_k:
        cmd += ["-b:v", f"{bitrate_k}k", "-maxrate", f"{bitrate_k}k",
                "-bufsize", f"{bitrate_k * 2}k"]
    else:
        cmd += ["-crf", str(PREVIEW_CRF), "-maxrate", "900k", "-bufsize", "1800k"]
    cmd += ["-movflags", "+faststart", str(dst)]
    return cmd


def _run(cmd: list) -> bool:
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=_TIMEOUT_S)
    if proc.returncode != 0:
        logger.warning("short preview: ffmpeg failed: %s", (proc.stderr or "").strip()[-300:])
        return False
    return True


def make_short_preview(short_mp4: Path, out_path: Path, *, start_s: float = 0.0,
                       seconds: float = PREVIEW_SECONDS) -> bool:
    """Cut a muted 9:16 preview loop from *short_mp4* into *out_path*.

    True only when *out_path* exists, is non-empty and fits the size cap.
    Never raises.
    """
    try:
        src, dst = Path(short_mp4), Path(out_path)
        if not src.is_file() or not shutil.which("ffmpeg"):
            return False
        dst.parent.mkdir(parents=True, exist_ok=True)
        if not _run(_encode_cmd(src, dst, start_s=start_s, seconds=seconds)):
            dst.unlink(missing_ok=True)
            return False
        if dst.stat().st_size > PREVIEW_MAX_BYTES:
            # One retry at a bitrate that fits the cap (90% of it, for the
            # container). A busy scene at CRF 30 is the only way here.
            kbps = max(120, int(PREVIEW_MAX_BYTES * 8 * 0.9 / max(0.5, seconds) / 1000))
            if not _run(_encode_cmd(src, dst, start_s=start_s, seconds=seconds,
                                    bitrate_k=kbps)):
                dst.unlink(missing_ok=True)
                return False
        size = dst.stat().st_size if dst.exists() else 0
        if not size or size > PREVIEW_MAX_BYTES * 1.1:
            logger.warning("short preview: %s is %d bytes, not shipping it", dst.name, size)
            dst.unlink(missing_ok=True)
            return False
        return True
    except Exception as exc:  # noqa: BLE001 — a preview never blocks a publish
        logger.warning("short preview failed (non-fatal): %s", exc)
        try:
            Path(out_path).unlink(missing_ok=True)
        except Exception:  # noqa: BLE001
            pass
        return False


def upload_short_preview(path: Path, show_slug: str, episode: int, index: int = 1) -> str:
    """Upload a preview to ``previews/<slug>/ep<NNN>-short<index>.mp4``.

    Returns the public URL, or ``""`` (R2 credentials unset, no file, any
    failure). Never raises.
    """
    try:
        path = Path(path)
        if not (show_slug and path.is_file() and int(episode) > 0):
            return ""
        endpoint = os.getenv("R2_ENDPOINT_URL", "").strip()
        access = os.getenv("R2_ACCESS_KEY_ID", "").strip()
        secret = os.getenv("R2_SECRET_ACCESS_KEY", "").strip()
        if not (endpoint and access and secret):
            logger.info("short preview: R2 credentials unset, not uploaded")
            return ""
        from engine.storage import upload_to_r2
        url = upload_to_r2(path, preview_r2_key(show_slug, episode, index),
                           bucket=R2_BUCKET, endpoint_url=endpoint,
                           access_key=access, secret_key=secret,
                           public_base_url=R2_PUBLIC_BASE, content_type=CONTENT_TYPE)
        return url if isinstance(url, str) and url.startswith("https://") else ""
    except Exception as exc:  # noqa: BLE001
        logger.warning("short preview upload failed (non-fatal): %s", exc)
        return ""
