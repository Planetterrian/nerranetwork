"""Put a speaker's own room tone back where a gate left digital silence.

Oct 22 2026, Stan Lewis. His take was kept only where the call leg showed
him talking (``local_tracks.gate_to_reference``) and muted where the bleed
gate heard Mira (``bleed.strip_bleed``). Both leave exact zeros. On a clean
microphone nobody hears that. On his iPhone, where the room sat about 24 dB
under his voice and the edit lifted him 24 dB, the background switched off
and on 1,181 times in a 55-minute episode, 11% of it in dead silence: the
pumping Patrick called terrible audio. Filling those holes with the
speaker's own pauses changed nothing a speech-quality model can measure
(STOI 0.936 -> 0.937, PESQ 1.70 -> 1.71 on the same minute) and the
background stopped switching.

Only the edit bed gets this (``post_interview.build_leg_local``). The
processed per-speaker tracks keep their zeros: the transcript and the
overlap measurements read them, and silence is the truth there.
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Tuple

import numpy as np

from audio.local_tracks import TARGET_SR, _pcm, _write_pcm

logger = logging.getLogger("nerra.voices.room_tone")

HOP = TARGET_SR // 100          # 10 ms frames
HOLE_ABS = 1                    # |sample| <= this (int16) is the gate's zero
MIN_BED_FRAMES = 15             # a pause of 150 ms or more is room tone
BED_MAX_SEC = 60.0              # enough tone to loop without a pattern
TONE_UNDER_SPEECH_DB = 12.0     # tone louder than this under the voice is not tone
FADE_SEC = 0.01


def _levels(x: np.ndarray, n: int) -> np.ndarray:
    fr = x[: n * HOP].reshape(n, HOP)
    return 20 * np.log10(np.sqrt((fr ** 2).mean(1)) + 1e-9)


def room_tone_bed(x: np.ndarray, hole: np.ndarray, level: np.ndarray) -> np.ndarray:
    """The speaker's own quiet frames, joined: the pauses between their words."""
    n = len(hole)
    ok = ~hole
    if ok.sum() < 100:
        return np.zeros(0, dtype=np.float32)
    voiced = level[ok]
    speech = float(np.percentile(voiced, 90))
    thr = min(float(np.percentile(voiced, 15)) + 4.0, speech - TONE_UNDER_SPEECH_DB)
    quiet = ok & (level < thr)
    bed, total, i = [], 0, 0
    while i < n and total < BED_MAX_SEC * TARGET_SR:
        if quiet[i]:
            j = i
            while j < n and quiet[j]:
                j += 1
            if j - i >= MIN_BED_FRAMES:
                # Leave 20 ms either side: the edges are the gate's ramps.
                piece = x[(i + 2) * HOP:(j - 2) * HOP]
                bed.append(piece)
                total += len(piece)
            i = j
        else:
            i += 1
    return np.concatenate(bed).astype(np.float32) if bed else np.zeros(0, dtype=np.float32)


def fill_gate_holes(track_wav: Path, out_wav: Path) -> Tuple[Path, dict]:
    """``(path, stats)``: the track with every run of digital silence filled
    with the speaker's own room tone, faded in and out over 10 ms. The track
    comes back untouched when it has no holes or no pauses to take tone from."""
    x = _pcm(Path(track_wav)).astype(np.float32)
    n = len(x) // HOP
    if n == 0:
        return Path(track_wav), {"filled_sec": 0.0}
    frames = np.abs(x[: n * HOP]).reshape(n, HOP)
    hole = frames.max(1) <= HOLE_ABS
    if not hole.any():
        return Path(track_wav), {"filled_sec": 0.0}
    level = _levels(x, n)
    tone = room_tone_bed(x, hole, level)
    if len(tone) < TARGET_SR // 2:
        logger.info("room tone: no pauses to take tone from; holes left as they are")
        return Path(track_wav), {"filled_sec": 0.0, "bed_sec": round(len(tone) / TARGET_SR, 2)}
    out = x.copy()
    fade = int(FADE_SEC * TARGET_SR)
    pos, filled, i = 0, 0, 0
    while i < n:
        if not hole[i]:
            i += 1
            continue
        j = i
        while j < n and hole[j]:
            j += 1
        a, b = i * HOP, j * HOP
        length = b - a
        seg = np.resize(np.roll(tone, -pos), length)
        pos = (pos + length) % len(tone)
        ramp = np.ones(length, dtype=np.float32)
        k = min(fade, length // 2)
        if k:
            ramp[:k] = np.linspace(0.0, 1.0, k, dtype=np.float32)
            ramp[-k:] = np.linspace(1.0, 0.0, k, dtype=np.float32)
        out[a:b] = out[a:b] + seg * ramp
        filled += length
        i = j
    _write_pcm(out, Path(out_wav))
    tone_db = float(20 * np.log10(np.sqrt((tone ** 2).mean()) / 32768 + 1e-12))
    stats = {"filled_sec": round(filled / TARGET_SR, 1),
             "bed_sec": round(len(tone) / TARGET_SR, 1),
             "tone_dbfs": round(tone_db, 1)}
    logger.info("room tone: %s", stats)
    return Path(out_wav), stats
