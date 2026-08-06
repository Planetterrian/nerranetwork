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


def _probe_audio(path: Path) -> tuple[int, bool]:
    """Return (channels, is_narrowband). Narrowband = telephony source:
    almost no energy above 5 kHz relative to the speech band."""
    out = subprocess.run(
        ["ffprobe", "-v", "quiet", "-select_streams", "a:0",
         "-show_entries", "stream=channels", "-of", "csv=p=0", str(path)],
        check=True, capture_output=True, text=True, timeout=120,
    )
    channels = int((out.stdout.strip().splitlines() or ["1"])[0] or 1)

    def band_mean(lo: int, hi: int) -> float:
        # For stereo recordings, probe the GUEST channel (left) alone —
        # Mira's full-band channel otherwise masks a narrowband PSTN
        # guest and the telephony repair never engages (Aug 5 2026,
        # Dan Perra phone interview).
        pre = "pan=mono|c0=c0," if channels >= 2 else ""
        r = subprocess.run(
            ["ffmpeg", "-v", "info", "-t", "60", "-i", str(path),
             "-af", f"{pre}highpass=f={lo},lowpass=f={hi},volumedetect",
             "-f", "null", "-"],
            capture_output=True, text=True, timeout=300,
        )
        for line in r.stderr.splitlines():
            if "mean_volume" in line:
                try:
                    return float(line.split("mean_volume:")[1].split("dB")[0])
                except ValueError:
                    pass
        return -90.0

    speech, high = band_mean(300, 3000), band_mean(5000, 12000)
    narrowband = (speech - high) > 30.0  # PSTN: HF ~absent below the speech band
    logger.info("mix_interview probe: channels=%d speech=%.1fdB high=%.1fdB narrowband=%s",
                channels, speech, high, narrowband)
    return channels, narrowband


def mix_interview(stereo_path: Path, out_path: Path) -> Path:
    """Leveled mono mix of the conversation for STT + episode assembly.

    MODE-AWARE (dry-run 2, July 20 2026): the telephony-repair chain is
    ONLY for genuinely narrowband (PSTN) guest channels. Applying it to a
    full-band WebRTC recording — or blindly channel-splitting a MONO
    source that ffmpeg silently upmixes — sums a filtered and unfiltered
    copy of the same signal (comb filtering, mud). Paths:

      - stereo + narrowband guest  → per-channel: guest repair chain + mix
      - stereo + full-band guest   → gentle shared chain, no band surgery
      - mono (legacy single-file)  → gentle chain only, never split
    """
    out_path.parent.mkdir(parents=True, exist_ok=True)
    channels, narrowband = _probe_audio(stereo_path)
    gentle = ("highpass=f=60,"
              "acompressor=threshold=-21dB:ratio=3:attack=20:release=250,"
              "dynaudnorm=f=250:g=15")
    if channels >= 2 and narrowband:
        _run(["ffmpeg", "-y", "-i", stereo_path,
              "-filter_complex",
              "[0:a]channelsplit=channel_layout=stereo[g][m];"
              f"[g]{_GUEST_ENHANCE}[ge];"
              "[m]highpass=f=70[me];"
              "[ge][me]amix=inputs=2:duration=longest:normalize=0,"
              "dynaudnorm=f=250:g=15[out]",
              "-map", "[out]", "-ar", "48000", out_path])
    elif channels >= 2:
        # Full-band WebRTC recording with true per-speaker channels:
        # sidechain-duck the GUEST under Mira — when Mira speaks, the
        # guest channel (and its room noise) pulls down hard. This is the
        # real per-speaker "mute" the first-episode notes asked for,
        # impossible on mono single-file recordings.
        _run(["ffmpeg", "-y", "-i", stereo_path,
              "-filter_complex",
              "[0:a]channelsplit=channel_layout=stereo[g][m];"
              "[m]asplit=2[m1][m2];"
              "[g][m1]sidechaincompress=threshold=0.02:ratio=10:"
              "attack=5:release=400[gd];"
              "[gd][m2]amix=inputs=2:duration=longest:normalize=0,"
              f"{gentle}[out]",
              "-map", "[out]", "-ar", "48000", out_path])
    else:
        _run(["ffmpeg", "-y", "-i", stereo_path,
              "-af", gentle, "-ar", "48000", out_path])
    return out_path


def duration_seconds(path: Path) -> float:
    out = subprocess.run(
        ["ffprobe", "-v", "quiet", "-show_entries", "format=duration",
         "-of", "csv=p=0", str(path)],
        check=True, capture_output=True, text=True, timeout=120,
    )
    return float(out.stdout.strip() or 0.0)
