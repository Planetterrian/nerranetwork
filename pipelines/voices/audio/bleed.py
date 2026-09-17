"""Take the other voices back out of a participant's own microphone.

Sept 17 2026, Sheldon Poon. He had no headphones in, so his laptop
microphone picked up Mira from his speakers, about fifteen decibels under
his own voice and a few hundred milliseconds behind her real track. In the
mix that is every one of her questions twice, slightly apart; in the
transcript it is her lines attributed to him, because the recogniser on his
track heard them too. Patrick's ask: his track should carry his voice and
nothing else.

The tracks all sit on one clock by the time this runs, so the rule is
simple. Wherever another placed track is speaking and this one is only
quiet enough to be the bleed, this one is muted. Where this one is loud
enough to be the person actually talking — including over the top of
someone else — it is left alone. The threshold sits between the bleed's
level and the speaker's own, measured from the tape rather than assumed.
"""
from __future__ import annotations

import logging
import wave
from pathlib import Path
from typing import Iterable, Optional, Tuple

import numpy as np

from audio.local_tracks import ROOM_ENVELOPE_SR, _whole_envelope

logger = logging.getLogger("nerra.voices.bleed")

BLEED_MIN_GAP_DB = 6.0      # bleed must sit at least this far under the voice
BLEED_FLOOR_DB = -60.0      # anything under this is silence, not bleed
BLEED_REACH_SEC = 1.0       # the other voice's reach either side (transmission lag)
BLEED_HOLD_SEC = 0.25       # mute/unmute smoothing so words are not clipped
_EPS = 1e-6


def _db(x: np.ndarray) -> np.ndarray:
    return 20.0 * np.log10(np.maximum(x, _EPS))


def _dilate(mask: np.ndarray, frames: int) -> np.ndarray:
    if frames <= 0 or not mask.any():
        return mask
    kernel = np.ones(2 * frames + 1)
    return np.convolve(mask.astype(np.float32), kernel, mode="same") > 0


def measure_bleed(track: np.ndarray, others: np.ndarray,
                  ) -> Optional[Tuple[float, float, float]]:
    """``(own_db, bleed_db, gate_db)`` for a track against the envelope of
    everyone else, or None when the track does not carry the others.

    ``own_db`` is the speaker's level when nobody else is talking;
    ``bleed_db`` the track's level while someone else is and it is not
    obviously the speaker; ``gate_db`` sits halfway between."""
    others_on = _dilate(_db(others) > BLEED_FLOOR_DB + 10,
                        int(BLEED_REACH_SEC * ROOM_ENVELOPE_SR))
    tdb = _db(track)
    alone = tdb[(~others_on) & (tdb > BLEED_FLOOR_DB)]
    during = tdb[others_on & (tdb > BLEED_FLOOR_DB)]
    if len(alone) < 50 * ROOM_ENVELOPE_SR or len(during) < 10 * ROOM_ENVELOPE_SR:
        return None
    own_db = float(np.percentile(alone, 75))
    # While the others speak, this track is mostly bleed with the speaker's
    # occasional overlaps on top. The bleed's typical level is the median;
    # its loudest moments sit near the 90th percentile, and the gate has to
    # clear those or the loud syllables of every question leak through.
    bleed_db = float(np.percentile(during, 50))
    bleed_peak = float(np.percentile(during, 90))
    if own_db - bleed_db < BLEED_MIN_GAP_DB:
        # The track is as loud under the others as on its own: either the
        # speaker talks over everyone or there is no bleed to find. Either
        # way there is nothing safe to remove.
        return None
    gate_db = min(bleed_peak + 3.0, own_db - 3.0)
    return own_db, bleed_db, gate_db


def strip_bleed(track_wav: Path, others: Iterable[Path], workdir: Path,
                label: str = "track") -> Tuple[Path, dict]:
    """Return ``(path, stats)``: the track with the others' bleed muted, or
    the track untouched (and ``stats["bleed"] = False``) when it is clean.
    Every path must already be on the same clock."""
    workdir = Path(workdir)
    workdir.mkdir(parents=True, exist_ok=True)
    others = [Path(o) for o in others if o is not None]
    track = _whole_envelope(Path(track_wav), workdir)
    if not others or not len(track):
        return Path(track_wav), {"bleed": False}
    envs = [_whole_envelope(o, workdir) for o in others]
    n = min([len(track)] + [len(e) for e in envs])
    if n == 0:
        return Path(track_wav), {"bleed": False}
    track = track[:n]
    other = np.max(np.stack([e[:n] for e in envs]), axis=0)
    found = measure_bleed(track, other)
    if found is None:
        logger.info("bleed: %s is clean", label)
        return Path(track_wav), {"bleed": False}
    own_db, bleed_db, gate_db = found
    others_on = _dilate(_db(other) > BLEED_FLOOR_DB + 10,
                        int(BLEED_REACH_SEC * ROOM_ENVELOPE_SR))
    tdb = _db(track)
    # Mute where the others are talking and this track is no louder than
    # the bleed would be. A speaker who talks over someone is above the
    # gate and stays.
    loud = tdb >= gate_db
    # The speaker talking over someone is loud for a sustained stretch; the
    # bleed's loudest syllables are isolated frames. Open the gate only for
    # a run that stays loud most of the time, then widen it so the edges of
    # the speaker's words are not clipped.
    reach = int(BLEED_HOLD_SEC * ROOM_ENVELOPE_SR)
    kernel = np.ones(2 * reach + 1)
    density = np.convolve(loud.astype(np.float32), kernel, mode="same") / len(kernel)
    speaking = _dilate(density >= 0.5, reach)
    mute = others_on & ~speaking
    muted_sec = float(mute.sum()) / ROOM_ENVELOPE_SR
    stats = {"bleed": True, "own_db": round(own_db, 1),
             "bleed_db": round(bleed_db, 1), "gate_db": round(gate_db, 1),
             "muted_sec": round(muted_sec, 1)}
    logger.info("bleed: %s carries the others at %.0f dB under the voice; "
                "muting %.0fs of it", label, own_db - bleed_db, muted_sec)
    out = workdir / (Path(track_wav).stem + "_clean.wav")
    _apply_gain(Path(track_wav), out, (~mute).astype(np.float32))
    return out, stats


def _apply_gain(src: Path, dst: Path, gain_frames: np.ndarray) -> None:
    """Multiply ``src`` by a per-frame gain (ROOM_ENVELOPE_SR frames/s),
    linearly interpolated so the gate opens and closes without clicks.
    Streams the file in chunks: a 48 kHz hour is far too big to hold twice."""
    with wave.open(str(src)) as wf, wave.open(str(dst), "wb") as out:
        sr, ch, width = wf.getframerate(), wf.getnchannels(), wf.getsampwidth()
        if width != 2:
            raise ValueError(f"{src}: expected 16-bit PCM, got {width * 8}-bit")
        out.setnchannels(ch)
        out.setsampwidth(width)
        out.setframerate(sr)
        per_frame = sr / ROOM_ENVELOPE_SR
        total = wf.getnframes()
        chunk = int(60 * sr)
        pos = 0
        while pos < total:
            raw = wf.readframes(chunk)
            if not raw:
                break
            data = np.frombuffer(raw, dtype="<i2").astype(np.float32)
            n = len(data) // ch
            idx = (pos + np.arange(n)) / per_frame
            g = np.interp(idx, np.arange(len(gain_frames)), gain_frames,
                          left=1.0, right=1.0)
            if ch > 1:
                g = np.repeat(g, ch)
            out.writeframes(np.clip(data * g, -32768, 32767).astype("<i2").tobytes())
            pos += n
