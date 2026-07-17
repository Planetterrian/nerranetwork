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


# Guest-channel telephony repair (July 2026, first dry run: PSTN guest
# audio sounded rough next to Mira's full-bandwidth TTS track). The guest
# arrives as ~8 kHz narrowband phone audio; this chain can't create
# bandwidth but makes it clean and present: denoise, warmth shelf, de-box,
# presence boost for intelligibility, hiss cut above the PSTN band, then
# level. Mira's synthetic track needs none of it.
_GUEST_ENHANCE = (
    "highpass=f=90,"
    "afftdn=nf=-25,"
    "equalizer=f=250:t=q:w=1:g=2,"
    "equalizer=f=450:t=q:w=1:g=-2,"
    "equalizer=f=2800:t=q:w=1.2:g=4,"
    "lowpass=f=4300,"
    "acompressor=threshold=-21dB:ratio=3:attack=20:release=250"
)


def mix_interview(stereo_path: Path, out_path: Path) -> Path:
    """Leveled mono mix of the conversation for STT + episode assembly.

    Channels are processed separately BEFORE mixing (guest left, Mira
    right): the guest gets the telephony-repair chain above; Mira's TTS
    track is passed through nearly untouched. Final episode loudness is
    still normalized once at assembly (-16 LUFS network target).
    """
    out_path.parent.mkdir(parents=True, exist_ok=True)
    _run(["ffmpeg", "-y", "-i", stereo_path,
          "-filter_complex",
          "[0:a]channelsplit=channel_layout=stereo[g][m];"
          f"[g]{_GUEST_ENHANCE}[ge];"
          "[m]highpass=f=70[me];"
          "[ge][me]amix=inputs=2:duration=longest:normalize=0,"
          "dynaudnorm=f=250:g=15[out]",
          "-map", "[out]", "-ar", "48000", out_path])
    return out_path


def duration_seconds(path: Path) -> float:
    out = subprocess.run(
        ["ffprobe", "-v", "quiet", "-show_entries", "format=duration",
         "-of", "csv=p=0", str(path)],
        check=True, capture_output=True, text=True, timeout=120,
    )
    return float(out.stdout.strip() or 0.0)
