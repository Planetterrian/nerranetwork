#!/usr/bin/env python3
"""Build a vertical (9:16) YouTube Short from recovered 16:9 video clips.

The recovered Grok clips are 16:9 long-form visuals with no audio; the
episode narration is the separate R2 mp3. This tool takes a contiguous run
of clips, reframes them to 1080x1920 (centered over a blurred fill — the
Reels/Shorts look), and muxes the matching slice of the episode audio so the
narration lines up with what's on screen.

Because the full episode video is the clips concatenated in order with the
audio laid over the top, clip N's audio sits at offset = sum of the durations
of the clips before it. So a Short from clips [a..b] uses the audio window
[sum(durations[:a]), sum(durations[:b+1])]. We probe each clip to compute it.

Usage:
    # Tesla: a ~50s Short from clips 2-5 (1-based; skips clip 1 which overlaps
    # the 10s music intro), audio auto-filled from the embedded set:
    python3 scripts/make_short_from_clips.py --set tesla_ep519 \
        --clips-dir recovered_ep519/ --range 2-5 --out Tesla_Ep519_short1.mp4

    # SpaceX, a different beat:
    python3 scripts/make_short_from_clips.py --set spacex_ep12 \
        --clips-dir recovered_spacex_ep12/ --range 2-5 --out SpaceX_Ep12_short1.mp4

Requires: ffmpeg + ffprobe on PATH.
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
import tempfile
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# Episode audio URLs for the known recovered sets.
try:
    from scripts.recover_grok_video import EMBEDDED_SETS  # noqa: E402
    _SET_AUDIO = {k: v[1] for k, v in EMBEDDED_SETS.items()}
except Exception:  # noqa: BLE001 — fall back to a static map
    _SET_AUDIO = {
        "tesla_ep519": "https://audio.nerranetwork.com/tesla/Tesla_Shorts_Time_Pod_Ep519_20260623.mp3",
        "spacex_ep12": "https://audio.nerranetwork.com/spacex/SpaceX_Daily_Ep012_20260623.mp3",
    }

# 9:16 reframe: scale the clip to full width, center it over a blurred,
# zoomed copy of itself filling 1080x1920 (modern Shorts/Reels look).
_VERTICAL_FILTER = (
    "[0:v]split[bg][fg];"
    "[bg]scale=1080:1920:force_original_aspect_ratio=increase,"
    "crop=1080:1920,gblur=sigma=22[bg2];"
    "[fg]scale=1080:-2[fg2];"
    "[bg2][fg2]overlay=(W-w)/2:(H-h)/2,setsar=1[v]"
)


def _clip_index(path: Path) -> int:
    m = re.search(r"clip(\d+)", path.stem)
    return int(m.group(1)) if m else 10**9


def _sorted_clips(clips_dir: Path) -> list[Path]:
    clips = sorted((p for p in clips_dir.glob("*.mp4") if "clip" in p.stem), key=_clip_index)
    return clips


def _duration(path: Path) -> float:
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=nokey=1:noprint_wrappers=1", str(path)],
        capture_output=True, text=True, check=True,
    ).stdout.strip()
    try:
        return float(out)
    except ValueError:
        return 0.0


def _resolve_audio(audio: str, work_dir: Path) -> Path:
    if audio.startswith(("http://", "https://")):
        dest = work_dir / "episode_audio.mp3"
        print(f"Downloading episode audio: {audio}")
        resp = requests.get(audio, timeout=180, stream=True)
        resp.raise_for_status()
        with open(dest, "wb") as fh:
            for chunk in resp.iter_content(chunk_size=8192):
                if chunk:
                    fh.write(chunk)
        return dest
    return Path(audio)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--clips-dir", type=Path, required=True, help="Dir with the recovered clipNN.mp4 files")
    ap.add_argument("--out", type=Path, required=True, help="Output Short MP4 (9:16)")
    ap.add_argument("--set", dest="ep", choices=sorted(_SET_AUDIO), help="Episode set (auto-fills audio)")
    ap.add_argument("--audio", help="Episode audio (URL or path) — overrides --set")
    ap.add_argument("--range", default="2-5", help="1-based inclusive clip range, e.g. 2-5")
    ap.add_argument("--max-seconds", type=float, default=58.0, help="Hard cap (Shorts must be <= 60s)")
    args = ap.parse_args()

    clips = _sorted_clips(args.clips_dir)
    if not clips:
        print(f"ERROR: no clip*.mp4 in {args.clips_dir}", file=sys.stderr)
        return 2

    m = re.fullmatch(r"(\d+)-(\d+)", args.range.strip())
    if not m:
        print("ERROR: --range must look like '2-5' (1-based, inclusive).", file=sys.stderr)
        return 2
    a, b = int(m.group(1)), int(m.group(2))
    if not (1 <= a <= b <= len(clips)):
        print(f"ERROR: --range out of bounds (have {len(clips)} clips).", file=sys.stderr)
        return 2

    audio_src = args.audio or (_SET_AUDIO.get(args.ep) if args.ep else None)
    if not audio_src:
        print("ERROR: provide --set or --audio for the narration track.", file=sys.stderr)
        return 2

    durations = [_duration(c) for c in clips]
    audio_start = sum(durations[: a - 1])
    seg_duration = min(sum(durations[a - 1 : b]), args.max_seconds)
    selected = clips[a - 1 : b]
    print(
        f"Short from clips {a}-{b} ({len(selected)} clips): "
        f"audio {audio_start:.1f}s → {audio_start + seg_duration:.1f}s "
        f"({seg_duration:.1f}s)"
    )

    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        audio_path = _resolve_audio(audio_src, tmp)

        # Concat the selected clips (same codec/params → demuxer copy is fine).
        concat_txt = tmp / "clips.txt"
        concat_txt.write_text(
            "".join(f"file '{c.resolve()}'\n" for c in selected), encoding="utf-8"
        )
        joined = tmp / "joined.mp4"
        subprocess.run(
            ["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(concat_txt),
             "-c", "copy", str(joined)],
            check=True, capture_output=True,
        )

        # Reframe to 9:16 and mux the matching audio slice.
        args.out.parent.mkdir(parents=True, exist_ok=True)
        cmd = [
            "ffmpeg", "-y",
            "-i", str(joined),
            "-ss", f"{audio_start:.3f}", "-i", str(audio_path),
            "-filter_complex", _VERTICAL_FILTER,
            "-map", "[v]", "-map", "1:a",
            "-t", f"{seg_duration:.3f}",
            "-c:v", "libx264", "-preset", "medium", "-crf", "20",
            "-pix_fmt", "yuv420p",
            "-c:a", "aac", "-b:a", "192k",
            "-movflags", "+faststart",
            str(args.out),
        ]
        proc = subprocess.run(cmd, capture_output=True, text=True)
        if proc.returncode != 0:
            print(proc.stderr[-1500:], file=sys.stderr)
            print("ERROR: ffmpeg failed building the Short.", file=sys.stderr)
            return 1

    print(f"\nDONE → {args.out} (1080x1920, {seg_duration:.0f}s) — ready for YouTube Shorts.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
