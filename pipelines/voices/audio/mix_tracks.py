"""FFmpeg helpers for the raw interview recording (Nerra Voices).

The Voximplant recorder produces one stereo file: guest on the left
channel, Mira on the right (VoxEngine stereo recorder convention — each
media source lands on its own channel). This module splits the channels
for per-speaker STT and produces the leveled mix used for the episode.
"""

from __future__ import annotations

import logging
import subprocess
from pathlib import Path
from typing import Tuple

logger = logging.getLogger(__name__)


def _run(cmd: list) -> None:
    logger.info("ffmpeg: %s", " ".join(str(c) for c in cmd[:12]) + " …")
    subprocess.run([str(c) for c in cmd], check=True, capture_output=True,
                   timeout=1800)


def split_channels(stereo_path: Path, out_dir: Path) -> Tuple[Path, Path]:
    """Split the dual-track recording → (guest_wav, mira_wav) mono files."""
    out_dir.mkdir(parents=True, exist_ok=True)
    guest = out_dir / "guest.wav"
    mira = out_dir / "mira.wav"
    _run(["ffmpeg", "-y", "-i", stereo_path,
          "-filter_complex",
          "[0:a]channelsplit=channel_layout=stereo[l][r]",
          "-map", "[l]", "-ar", "48000", guest,
          "-map", "[r]", "-ar", "48000", mira])
    return guest, mira


def mix_interview(stereo_path: Path, out_path: Path) -> Path:
    """Leveled mono mix of the conversation for STT + episode assembly.

    Light chain only — the final episode loudness is normalized once at
    assembly (same -16 LUFS target as the rest of the network).
    """
    out_path.parent.mkdir(parents=True, exist_ok=True)
    _run(["ffmpeg", "-y", "-i", stereo_path,
          "-af",
          "pan=mono|c0=0.5*c0+0.5*c1,"
          "highpass=f=80,lowpass=f=12000,"
          "acompressor=threshold=-21dB:ratio=3:attack=20:release=250,"
          "dynaudnorm=f=250:g=15",
          "-ar", "48000", out_path])
    return out_path


def duration_seconds(path: Path) -> float:
    out = subprocess.run(
        ["ffprobe", "-v", "quiet", "-show_entries", "format=duration",
         "-of", "csv=p=0", str(path)],
        check=True, capture_output=True, text=True, timeout=120,
    )
    return float(out.stdout.strip() or 0.0)
