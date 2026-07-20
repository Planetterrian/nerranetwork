"""Waveform video for YouTube (Nerra Voices, spec §5.4).

Single-ffmpeg render: episode cover (or brand color card) + animated
waveform + title text → 1280×720 H.264. Deliberately simple — the voices
pipeline publishes this independently of engine/video.py's slideshow path.
"""

from __future__ import annotations

import logging
import subprocess
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

BRAND_COLOR = "0x7C3AED"  # Age of AI purple (shows/network_meta.yaml)


def render(audio_path: Path, out_mp4: Path, *,
           cover_image: Optional[Path] = None,
           title: str = "") -> Path:
    out_mp4.parent.mkdir(parents=True, exist_ok=True)
    wave = (
        "showwaves=s=1280x240:mode=cline:colors=White@0.9:rate=25,"
        "format=rgba[wave]"
    )
    drawtitle = ""
    if title:
        safe = title.replace("'", "’").replace(":", "\\:")
        drawtitle = (
            ";[canvas2]drawtext=text='" + safe + "':fontcolor=white:"
            "fontsize=44:x=(w-text_w)/2:y=120:box=1:boxcolor=black@0.35:"
            "boxborderw=18[canvas3]"
        )

    if cover_image and Path(cover_image).exists():
        base = ["-loop", "1", "-i", str(cover_image)]
        bg = "[0:v]scale=1280:720:force_original_aspect_ratio=increase,crop=1280:720,boxblur=8[canvas]"
        audio_idx = "1"
    else:
        base = ["-f", "lavfi", "-i", f"color=c={BRAND_COLOR}:s=1280x720:r=25"]
        bg = "[0:v]copy[canvas]"
        audio_idx = "1"

    graph = (
        f"{bg};"
        f"[{audio_idx}:a]{wave};"
        "[canvas][wave]overlay=0:400[canvas2]"
        + (drawtitle if drawtitle else ";[canvas2]copy[canvas3]")
    )
    cmd = ["ffmpeg", "-y", *base, "-i", str(audio_path),
           "-filter_complex", graph,
           "-map", "[canvas3]", "-map", f"{audio_idx}:a",
           "-c:v", "libx264", "-preset", "medium", "-crf", "23",
           "-c:a", "aac", "-b:a", "192k", "-shortest", str(out_mp4)]
    logger.info("Rendering waveform video → %s", out_mp4)
    proc = subprocess.run(cmd, capture_output=True, timeout=7200, text=True)
    if proc.returncode != 0:
        # Surface the real ffmpeg error — capture_output previously
        # swallowed it, leaving only an opaque exit code (July 20 2026).
        logger.error("ffmpeg waveform render failed (exit %d):\n%s",
                     proc.returncode, (proc.stderr or "")[-2000:])
        raise RuntimeError(f"waveform render failed (exit {proc.returncode})")
    return out_mp4
