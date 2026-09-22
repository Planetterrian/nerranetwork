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
ECHO_MAX_LAG_SEC = 1.5      # how far behind the other track the echo can sit
ECHO_MARGIN_DB = 4.0        # how far above the predicted echo a real voice must be
_EPS = 1e-6


def _db(x: np.ndarray) -> np.ndarray:
    return 20.0 * np.log10(np.maximum(x, _EPS))


def _dilate(mask: np.ndarray, frames: int) -> np.ndarray:
    if frames <= 0 or not mask.any():
        return mask
    kernel = np.ones(2 * frames + 1)
    return np.convolve(mask.astype(np.float32), kernel, mode="same") > 0


def _own_level(track: np.ndarray, others_on: np.ndarray) -> Optional[float]:
    """This speaker's own level, measured where nobody else is talking."""
    tdb = _db(track)
    alone = tdb[(~others_on) & (tdb > BLEED_FLOOR_DB)]
    if len(alone) < 50 * ROOM_ENVELOPE_SR:
        return None
    return float(np.percentile(alone, 75))


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


def echo_fit(track: np.ndarray, others: np.ndarray, others_on: np.ndarray,
             own_db: float) -> Optional[Tuple[int, float]]:
    """``(lag_frames, offset_db)`` describing this track's echo of the others.

    Sept 21 2026, Sameer Ranjan. A level gate cannot separate a loud echo
    from a quiet speaker: his own voice measured -46.5 dB and the echo of
    Mira through his laptop speakers peaked within six of that, so the gate
    landed at -49.5 dB — three decibels under his voice — and her louder
    syllables walked straight through it. Her words then appear in his
    transcript, attributed to him, which is what the producer's pass reads
    when it decides what Mira did wrong.

    But the echo is not an unknown signal. It is a delayed, quieter copy of
    a track we already have, so it can be predicted rather than guessed at:
    find the delay, find how far under the original it sits, and anything
    that matches that prediction is echo however loud it is. What the
    speaker actually says is not predictable from someone else's track, so
    it survives.
    """
    tdb, odb = _db(track), _db(others)
    # Fit on every frame where the others are talking. The temptation is to
    # exclude frames louder than the speaker's own level, on the grounds that
    # those must be the speaker — but a loud echo lives exactly there, and
    # excluding it leaves nothing to fit (the first version of this returned
    # "no echo" for the loudest cases, which are the ones that matter). The
    # speaker's genuine overlaps are a minority of these frames, so a median
    # and an interquartile spread survive them.
    base = others_on & (tdb > BLEED_FLOOR_DB)
    if base.sum() < 5 * ROOM_ENVELOPE_SR:
        return None
    best: Optional[Tuple[int, float]] = None
    best_spread = None
    for lag in range(0, int(ECHO_MAX_LAG_SEC * ROOM_ENVELOPE_SR) + 1):
        shifted = np.roll(odb, lag)
        usable = base.copy()
        if lag:
            usable[:lag] = False
        if usable.sum() < 5 * ROOM_ENVELOPE_SR:
            continue
        diff = tdb[usable] - shifted[usable]
        # The right lag is the one where the gap between the two tracks is
        # most nearly CONSTANT: that is what "the same sound, quieter and
        # later" means. A wrong lag lines speech up against silence and the
        # gap scatters.
        spread = float(np.percentile(diff, 75) - np.percentile(diff, 25))
        if best_spread is None or spread < best_spread:
            best_spread, best = spread, (lag, float(np.median(diff)))
    if best is None or best_spread is None or best_spread > 12.0:
        # Nothing that behaves like a copy of the other track.
        return None
    logger.info("bleed: echo fits at %.2fs behind, %.1f dB under (spread %.1f dB)",
                best[0] / ROOM_ENVELOPE_SR, -best[1], best_spread)
    return best


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
    others_on = _dilate(_db(other) > BLEED_FLOOR_DB + 10,
                        int(BLEED_REACH_SEC * ROOM_ENVELOPE_SR))
    tdb = _db(track)
    found = measure_bleed(track, other)
    if found is None:
        # A level test alone says "nothing safe to remove" in two opposite
        # situations: there is no echo, and the echo is so loud it looks like
        # the speaker. The second one is the dangerous one, so before giving
        # up, ask whether this track can be PREDICTED from the others'. If it
        # can, the level test was simply the wrong instrument.
        own_db = _own_level(track, others_on)
        fit = echo_fit(track, other, others_on, own_db) if own_db is not None else None
        if fit is None:
            logger.info("bleed: %s is clean", label)
            return Path(track_wav), {"bleed": False}
        logger.warning("bleed: %s carries the others almost as loudly as its "
                       "owner — muting by prediction alone", label)
        bleed_db, gate_db = own_db, BLEED_FLOOR_DB
    else:
        own_db, bleed_db, gate_db = found
    # Mute where the others are talking and this track is no louder than
    # the bleed would be. A speaker who talks over someone is above the
    # gate and stays.
    loud = tdb >= gate_db
    # Where the echo can be predicted from the track it came from, the level
    # gate is only the floor: this track must also be louder than the echo
    # the others' audio predicts before it counts as its owner speaking.
    fit = echo_fit(track, other, others_on, own_db)
    if fit is not None:  # noqa: SIM102 — the predictor is the primary rule
        lag, offset_db = fit
        predicted = np.roll(_db(other), lag) + offset_db
        if lag:
            predicted[:lag] = BLEED_FLOOR_DB
        # Never demand more of the speaker than their own ordinary volume.
        # Without this cap a guest who interrupts quietly while the host is
        # loud gets muted for it, and "your microphone carries only you"
        # would quietly come to mean "only when you are the loudest".
        threshold = np.minimum(predicted + ECHO_MARGIN_DB, own_db)
        loud = loud & (tdb >= threshold)
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
    # How much of what this gate silenced was too loud to have been bleed.
    # Bleed sits at least BLEED_MIN_GAP_DB under its owner by definition, so
    # anything muted ABOVE that line is this speaker's own voice going out of
    # the episode. It is the one number that says whether the strip overreached,
    # and the edit reads it before deciding to cut from these tracks at all
    # (Sept 22 2026): the predictor is the primary discriminator now, and a
    # predictor that is wrong about a tape is wrong quietly.
    loud_muted_sec = float((mute & (tdb >= own_db - BLEED_MIN_GAP_DB)).sum()) \
        / ROOM_ENVELOPE_SR
    stats = {"bleed": True, "own_db": round(own_db, 1),
             "bleed_db": round(bleed_db, 1), "gate_db": round(gate_db, 1),
             "muted_sec": round(muted_sec, 1),
             "loud_muted_sec": round(loud_muted_sec, 1),
             "echo_lag_sec": (round(fit[0] / ROOM_ENVELOPE_SR, 2)
                              if fit is not None else None),
             "echo_under_db": round(-fit[1], 1) if fit is not None else None}
    logger.info("bleed: %s carries the others at %.0f dB under the voice; "
                "muting %.0fs of it (%.1fs of that was loud enough to be the "
                "speaker)", label, own_db - bleed_db, muted_sec, loud_muted_sec)
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
