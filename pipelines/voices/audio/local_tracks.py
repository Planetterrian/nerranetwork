"""Local browser recordings (Phase 2 co-host, Sept 2026 — Riverside model).

Both humans in a Mira interview (guest + Patrick as co-host) record their
own mic in the studio page with ``MediaRecorder`` (webm/opus, 48 kHz,
192 kbps, 5 s timeslices) and upload the chunks during the call. The
Worker writes a manifest at ``<r2_prefix>/local/<run_id>/<role>/manifest.json``
(see workers/voices/src/index.ts ``handleUploadDone``)::

    {"run_id": ..., "role": "guest"|"host", "mime": "audio/webm;codecs=opus",
     "started_at": iso|null, "duration_ms": int, "chunks": [key, ...],
     "missing": [key, ...], "bytes": int, ...}

``interview_runs.local_<role>_url`` holds that manifest KEY. This module
turns a manifest into a 48 kHz mono WAV lined up with the Voximplant
recording of the same speaker, so post-production can prefer the clean
local track and fall back to the call track per speaker when the upload
is incomplete.

Design notes
* MediaRecorder timeslice chunks are NOT independent files — they are
  consecutive byte ranges of ONE webm stream (only the first carries the
  EBML header). Concatenating the bytes in seq order rebuilds the stream;
  ffmpeg then decodes it as a single input.
* Alignment: the local recording starts when the page arms the recorder
  (before or after the call connects), so its clock is unrelated to the
  Voximplant recorder's. We estimate the offset by cross-correlating the
  speech envelopes of the first ~60 s (numpy only; 8 kHz envelope) and
  trim/pad the local track. Low correlation → no offset (the Voximplant
  fallback is still there if the result sounds wrong).
"""

from __future__ import annotations

import json
import logging
import subprocess
import wave
from pathlib import Path
from typing import Any, Callable, Dict, Optional, Tuple

import numpy as np

logger = logging.getLogger(__name__)

TARGET_SR = 48000
ENVELOPE_SR = 8000
CORRELATION_WINDOW_SEC = 60.0
MAX_OFFSET_SEC = 30.0
MIN_CORRELATION = 0.2   # normalized envelope correlation below this → no offset

# Placing a whole leg on the room's clock (Sept 15 2026). Every leg's
# recorder starts when Voximplant starts recording it, which is neither the
# room opening nor the moment the person joined: in the Dan Perra interview
# the co-host joined 4.1 s after the room opened and his recording began at
# 17.2 s, while Mira's own leg began at 16.4 s. Both tracks were laid into
# the mix from zero, so for forty-seven minutes the three people were in
# three different time frames. Join timestamps cannot fix this because they
# are not when the recorder started. The guest's right channel — everything
# the guest HEARD — is the room, so we measure each other track against it
# across the whole recording and take the median of the windows that
# correlate. One window at the head is not enough: a conversation has long
# stretches where a given person says nothing.
ROOM_WINDOW_SEC = 150.0
ROOM_STEP_SEC = 200.0
# Blind search range. A leg can start a long way from the reference: the
# room opens when the co-host arrives and the guest may be minutes behind
# him, so Mira's leg began 268 s before the guest's in the Adrian Wolfberg
# interview (Sept 15 2026) and a +/-180 s search could not reach the true
# peak — it picked a noise peak at -35.7 s and the episode came back
# misaligned again. Callers that know roughly where the leg belongs pass
# ``expected`` and get a tight search around it instead.
ROOM_MAX_OFFSET_SEC = 900.0
ROOM_EXPECTED_SPAN_SEC = 120.0
ROOM_AGREE_SEC = 2.5    # windows this close are measuring the same offset
ROOM_RESIDUAL_SEC = 1.0  # a placed track must verify this close to zero
ROOM_MIN_WINDOW_SEC = 40.0   # shortest useful correlation window
ROOM_STRONG_CORR = 0.70      # one window this good stands on its own
ROOM_MIN_CORRELATION = 0.45   # per window; noise peaks sit well below this
ROOM_MIN_WINDOWS = 2          # agreeing windows needed to trust the median
ROOM_ENVELOPE_SR = 50         # 20 ms resolution is plenty for whole legs
ROOM_SEAM_WINDOW_SEC = 20.0   # resolution for locating a clock jump in a leg


def _run(cmd: list) -> None:
    logger.info("ffmpeg: %s", " ".join(str(c) for c in cmd[:12]) + " …")
    subprocess.run([str(c) for c in cmd], check=True, capture_output=True,
                   timeout=1800)


# ---------------------------------------------------------------------------
# Manifest → concatenated WAV
# ---------------------------------------------------------------------------

def _default_read_json(key: str) -> Optional[Dict[str, Any]]:
    from common import r2_read_json
    return r2_read_json(key)


def _default_download(key: str, dest: Path) -> Path:
    from common import r2_download
    return r2_download(key, dest)


def manifest_is_complete(manifest: Optional[Dict[str, Any]]) -> bool:
    """A manifest is usable only when every chunk landed: a gap in the
    middle of a continuous webm stream makes the decoder drop everything
    after it, and a partial track cannot be aligned honestly."""
    if not isinstance(manifest, dict):
        return False
    chunks = manifest.get("chunks") or []
    if not chunks:
        return False
    if manifest.get("missing"):
        return False
    return True


def concat_chunks_to_wav(chunk_paths: list, workdir: Path,
                         name: str = "local") -> Path:
    """Byte-concatenate MediaRecorder chunks (in order) → 48 kHz mono WAV."""
    workdir = Path(workdir)
    workdir.mkdir(parents=True, exist_ok=True)
    joined = workdir / f"{name}_concat.webm"
    with joined.open("wb") as out:
        for p in chunk_paths:
            out.write(Path(p).read_bytes())
    wav = workdir / f"{name}.wav"
    _run(["ffmpeg", "-y", "-i", joined, "-vn", "-ar", TARGET_SR, "-ac", "1",
          "-c:a", "pcm_s16le", wav])
    return wav


def fetch_local_track(manifest_key: str, workdir: Path, *,
                      read_json: Optional[Callable[[str], Any]] = None,
                      download: Optional[Callable[[str, Path], Path]] = None,
                      ) -> Optional[Path]:
    """Manifest key → 48 kHz mono WAV of the local recording, or ``None``
    when the manifest is absent/incomplete (caller falls back to the
    Voximplant track). ``read_json`` / ``download`` default to the R2
    helpers in ``common``; tests inject fakes."""
    if not manifest_key:
        return None
    read_json = read_json or _default_read_json
    download = download or _default_download
    workdir = Path(workdir)
    try:
        manifest = read_json(manifest_key)
    except Exception as exc:  # noqa: BLE001 — R2 hiccup = no local track
        logger.warning("local track manifest %s unreadable: %s", manifest_key, exc)
        return None
    if not manifest_is_complete(manifest):
        logger.info("local track %s: manifest absent/incomplete → fallback",
                    manifest_key)
        return None
    role = str(manifest.get("role") or "local")
    chunk_dir = workdir / f"{role}_chunks"
    chunk_dir.mkdir(parents=True, exist_ok=True)
    local_paths = []
    try:
        for i, key in enumerate(manifest["chunks"]):
            local_paths.append(download(key, chunk_dir / f"{i:05d}.webm"))
        wav = concat_chunks_to_wav(local_paths, workdir, name=f"local_{role}")
    except Exception as exc:  # noqa: BLE001 — never block post-production
        logger.warning("local track %s: download/decode failed (%s) → fallback",
                       manifest_key, exc)
        return None
    if wav.stat().st_size < 1000:
        return None
    logger.info("local track %s: %d chunks, %s bytes", manifest_key,
                len(local_paths), manifest.get("bytes"))
    return wav


# ---------------------------------------------------------------------------
# Alignment against the Voximplant channel of the same speaker
# ---------------------------------------------------------------------------

def _read_wav_mono(path: Path, max_seconds: float) -> Tuple[np.ndarray, int]:
    """First ``max_seconds`` of a 16-bit PCM WAV as float32 mono."""
    with wave.open(str(path), "rb") as wf:
        sr = wf.getframerate()
        ch = wf.getnchannels()
        width = wf.getsampwidth()
        n = min(wf.getnframes(), int(max_seconds * sr))
        raw = wf.readframes(n)
    if width != 2:
        raise ValueError(f"{path}: expected 16-bit PCM, got {width * 8}-bit")
    data = np.frombuffer(raw, dtype="<i2").astype(np.float32) / 32768.0
    if ch > 1:
        data = data.reshape(-1, ch)[:, 0]
    return data, sr


def _envelope(samples: np.ndarray, sr: int) -> np.ndarray:
    """Rectified, smoothed loudness envelope resampled to ENVELOPE_SR."""
    factor = max(1, sr // ENVELOPE_SR)
    usable = (len(samples) // factor) * factor
    if usable == 0:
        return np.zeros(0, dtype=np.float32)
    env = np.abs(samples[:usable]).reshape(-1, factor).mean(axis=1)
    win = max(1, ENVELOPE_SR // 100)  # 10 ms smoothing
    kernel = np.ones(win, dtype=np.float32) / win
    return np.convolve(env, kernel, mode="same").astype(np.float32)


def estimate_offset(track_wav: Path, reference_wav: Path,
                    *, window_sec: float = CORRELATION_WINDOW_SEC,
                    max_offset_sec: float = MAX_OFFSET_SEC,
                    ) -> Tuple[float, float]:
    """Return ``(offset_seconds, correlation)``.

    ``offset`` is how far the local TRACK's clock is ahead of the
    REFERENCE: ``track[t + offset] ≈ reference[t]``. Positive → the local
    recording started earlier (trim its head); negative → later (pad).
    ``correlation`` is the normalized envelope correlation at the peak
    (0..1); callers treat values below MIN_CORRELATION as "unknown".
    """
    a, sr_a = _read_wav_mono(Path(track_wav), window_sec + max_offset_sec)
    b, sr_b = _read_wav_mono(Path(reference_wav), window_sec)
    ea, eb = _envelope(a, sr_a), _envelope(b, sr_b)
    if len(ea) < ENVELOPE_SR or len(eb) < ENVELOPE_SR:
        return 0.0, 0.0
    ea = ea - ea.mean()
    eb = eb - eb.mean()
    if not ea.any() or not eb.any():
        return 0.0, 0.0
    n = len(ea) + len(eb) - 1
    nfft = 1 << (n - 1).bit_length()
    fa = np.fft.rfft(ea, nfft)
    fb = np.fft.rfft(eb, nfft)
    # full[k] = sum_t ea[t + k] * eb[t] (circular; nfft >= n so no wrap
    # aliasing). Positive lags live at the front, negative at the tail.
    full = np.fft.irfft(fa * np.conj(fb), nfft)
    neg = full[nfft - (len(eb) - 1):nfft] if len(eb) > 1 else full[:0]
    corr = np.concatenate([neg, full[:len(ea)]])
    lags = np.arange(-(len(eb) - 1), len(ea))
    max_lag = int(max_offset_sec * ENVELOPE_SR)
    mask = (lags >= -max_lag) & (lags <= max_lag)
    corr, lags = corr[mask], lags[mask]
    k = int(np.argmax(corr))
    norm = float(np.linalg.norm(ea) * np.linalg.norm(eb)) or 1.0
    strength = float(max(0.0, corr[k] / norm))
    offset = float(lags[k]) / ENVELOPE_SR
    return offset, strength


def align_to_reference(track_wav: Path, reference_wav: Path, workdir: Path,
                       *, min_correlation: float = MIN_CORRELATION) -> Path:
    """Trim or pad ``track_wav`` so it lines up with ``reference_wav``
    (the Voximplant channel of the same speaker). Returns the aligned
    48 kHz mono WAV. Low correlation → the track is returned re-encoded
    with no offset (an honest "unknown" beats a wrong shift)."""
    workdir = Path(workdir)
    workdir.mkdir(parents=True, exist_ok=True)
    track_wav, reference_wav = Path(track_wav), Path(reference_wav)
    out = workdir / (track_wav.stem + "_aligned.wav")
    try:
        offset, strength = estimate_offset(track_wav, reference_wav)
    except Exception as exc:  # noqa: BLE001 — unreadable → no offset
        logger.warning("align_to_reference: offset estimate failed (%s)", exc)
        offset, strength = 0.0, 0.0
    offset = max(-MAX_OFFSET_SEC, min(MAX_OFFSET_SEC, offset))
    if strength < min_correlation:
        logger.warning("align_to_reference: correlation %.2f < %.2f — no offset "
                       "applied (estimate was %+.3fs)", strength, min_correlation,
                       offset)
        offset = 0.0
    logger.info("align_to_reference: %s offset %+.3fs (corr %.2f)",
                track_wav.name, offset, strength)
    cmd = ["ffmpeg", "-y"]
    if offset > 0.001:
        cmd += ["-ss", f"{offset:.3f}", "-i", track_wav]
    elif offset < -0.001:
        ms = int(round(-offset * 1000))
        cmd += ["-i", track_wav, "-af", f"adelay=delays={ms}:all=1"]
    else:
        cmd += ["-i", track_wav]
    cmd += ["-ar", TARGET_SR, "-ac", "1", "-c:a", "pcm_s16le", out]
    _run(cmd)
    return out


def _whole_envelope(path: Path, workdir: Path) -> np.ndarray:
    """Loudness envelope of an ENTIRE recording at ROOM_ENVELOPE_SR.

    A 47-minute 48 kHz WAV is a quarter of a gigabyte; ffmpeg down-samples
    it to 1 kHz mono first so the whole thing fits in a few megabytes and
    the correlation is cheap.
    """
    workdir.mkdir(parents=True, exist_ok=True)
    small = workdir / (Path(path).stem + "_1k.wav")
    # The cache is keyed on the name; a file rewritten under the same name
    # (a leg placed a second time) must not verify against its old self.
    if not small.exists() or small.stat().st_mtime < Path(path).stat().st_mtime:
        _run(["ffmpeg", "-y", "-i", path, "-ac", "1", "-ar", "1000",
              "-c:a", "pcm_s16le", small])
    with wave.open(str(small)) as wf:
        sr = wf.getframerate()
        data = np.frombuffer(wf.readframes(wf.getnframes()),
                             dtype="<i2").astype(np.float32) / 32768.0
    win = max(1, sr // ROOM_ENVELOPE_SR)
    usable = (len(data) // win) * win
    if usable == 0:
        return np.zeros(0, dtype=np.float32)
    return np.abs(data[:usable]).reshape(-1, win).mean(axis=1).astype(np.float32)


def _window_offset(a: np.ndarray, b: np.ndarray,
                   lo: float = -ROOM_MAX_OFFSET_SEC,
                   hi: float = ROOM_MAX_OFFSET_SEC,
                   ) -> Tuple[Optional[float], float]:
    """Lag (seconds) at which ``a`` best matches ``b``, plus its strength."""
    a, b = a - a.mean(), b - b.mean()
    if not a.any() or not b.any():
        return None, 0.0
    n = len(a) + len(b) - 1
    nfft = 1 << (n - 1).bit_length()
    full = np.fft.irfft(np.fft.rfft(a, nfft) * np.conj(np.fft.rfft(b, nfft)), nfft)
    corr = np.concatenate([full[nfft - (len(b) - 1):nfft], full[:len(a)]])
    lags = np.arange(-(len(b) - 1), len(a))
    keep = ((lags >= int(lo * ROOM_ENVELOPE_SR))
            & (lags <= int(hi * ROOM_ENVELOPE_SR)))
    corr, lags = corr[keep], lags[keep]
    if not len(corr):
        return None, 0.0
    k = int(np.argmax(corr))
    norm = float(np.linalg.norm(a) * np.linalg.norm(b)) or 1.0
    return float(lags[k]) / ROOM_ENVELOPE_SR, float(max(0.0, corr[k] / norm))


def _window_picks(track: np.ndarray, room: np.ndarray, window: int,
                  step: int, lo: float, hi: float, base: float,
                  ) -> list[Tuple[float, float, float]]:
    """Per-window ``(start_seconds, delay, strength)`` for a track that has
    already been shifted by ``base``. A window that finds nothing inside the
    expected span is tried again across the whole range: a leg whose clock
    jumped part-way through is 160 s out for the rest of the file, and a
    search that only looks near the expectation reports that stretch as
    silence rather than as the jump it is (Sheldon Poon, Sept 17 2026)."""
    covered = min(len(track), len(room))
    picks: list[Tuple[float, float, float]] = []
    for start in range(0, max(0, covered - window), step):
        a, b = track[start:start + window], room[start:start + window]
        lag, strength = _window_offset(a, b, lo, hi)
        if (lag is None or strength < ROOM_MIN_CORRELATION) and (
                lo > -ROOM_MAX_OFFSET_SEC or hi < ROOM_MAX_OFFSET_SEC):
            lag, strength = _wide_offset(track, room, start, window)
        if lag is None or strength < ROOM_MIN_CORRELATION:
            continue
        picks.append((start / ROOM_ENVELOPE_SR, base - lag, strength))
    return picks


def _wide_offset(track: np.ndarray, room: np.ndarray, start: int, window: int,
                 ) -> Tuple[Optional[float], float]:
    """The lag of one track window against a much longer stretch of the
    room. ``_window_offset`` compares the same seconds of both files, so it
    cannot see a lag longer than its window; here the room side is padded
    by the whole allowed range and the lag is corrected for the padding.
    The strength is re-scored on the exact overlap so it compares with the
    narrow search."""
    pad = int(ROOM_MAX_OFFSET_SEC * ROOM_ENVELOPE_SR)
    a = track[start:start + window]
    lo = max(0, start - pad)
    b = room[lo:start + window + pad]
    if not a.any() or not b.any():
        return None, 0.0
    lag, _ = _window_offset(a, b, -2 * ROOM_MAX_OFFSET_SEC, 2 * ROOM_MAX_OFFSET_SEC)
    if lag is None:
        return None, 0.0
    lag += (start - lo) / ROOM_ENVELOPE_SR
    if abs(lag) > ROOM_MAX_OFFSET_SEC:
        return None, 0.0
    b_lo = start - int(round(lag * ROOM_ENVELOPE_SR))
    if b_lo < 0 or b_lo + window > len(room):
        return None, 0.0
    b = room[b_lo:b_lo + window]
    a, b = a - a.mean(), b - b.mean()
    norm = float(np.linalg.norm(a) * np.linalg.norm(b))
    return lag, (float(np.dot(a, b) / norm) if norm else 0.0)


def _runs(picks: list[Tuple[float, float, float]],
          ) -> list[list[Tuple[float, float, float]]]:
    """Consecutive windows that agree on one delay. A lone window that agrees
    with neither neighbour is noise and is dropped; a run of one survives
    only when it is emphatic."""
    runs: list[list[Tuple[float, float, float]]] = []
    for pick in picks:
        if runs and abs(runs[-1][-1][1] - pick[1]) <= ROOM_AGREE_SEC:
            runs[-1].append(pick)
        else:
            runs.append([pick])
    return [r for r in runs
            if len(r) >= ROOM_MIN_WINDOWS
            or (len(r) == 1 and r[0][2] >= ROOM_STRONG_CORR)]


def _seam(track: np.ndarray, room: np.ndarray, base: float, t0: float,
          t1: float, delay_a: float, delay_b: float) -> float:
    """Where, between ``t0`` and ``t1`` (track seconds), the track stops
    sitting at ``delay_a`` and starts sitting at ``delay_b``. Short windows
    are scored at exactly the two candidate lags; the seam is the change
    point that best splits them. Falls back to the midpoint."""
    win = int(ROOM_SEAM_WINDOW_SEC * ROOM_ENVELOPE_SR)
    lag_a = int(round((base - delay_a) * ROOM_ENVELOPE_SR))
    lag_b = int(round((base - delay_b) * ROOM_ENVELOPE_SR))

    def score(start: int, lag: int) -> float:
        a = track[start:start + win]
        b_lo = start - lag  # lag < 0: the track runs early, the room is later
        if b_lo < 0 or b_lo + win > len(room) or len(a) < win:
            return 0.0
        b = room[b_lo:b_lo + win]
        a, b = a - a.mean(), b - b.mean()
        norm = float(np.linalg.norm(a) * np.linalg.norm(b))
        return float(np.dot(a, b) / norm) if norm else 0.0

    starts = list(range(int(t0 * ROOM_ENVELOPE_SR), int(t1 * ROOM_ENVELOPE_SR), win))
    if not starts:
        return (t0 + t1) / 2
    # The one change point that best explains the scan: everything before
    # it prefers the first delay, everything after prefers the second. A
    # single window that happens to like the second lag (a repeated cadence
    # in the room) does not move the seam on its own.
    diff = np.array([score(st, lag_b) - score(st, lag_a) for st in starts])
    after = np.concatenate([np.cumsum(diff[::-1])[::-1], [0.0]])  # sum of diff[k:]
    before = np.concatenate([[0.0], np.cumsum(diff)])            # sum of diff[:k]
    k = int(np.argmax(after - before))
    if k >= len(starts):
        return t1
    return starts[k] / ROOM_ENVELOPE_SR


def room_pieces(track_wav: Path, room_wav: Path, workdir: Path,
                expected: Optional[float] = None,
                span: float = ROOM_EXPECTED_SPAN_SEC,
                ) -> list[dict]:
    """The stretches of ``track_wav`` that sit on the room's clock at one
    delay each, in the track's own seconds: ``[{"from", "to", "delay",
    "windows", "agreement"}, ...]``. One entry is the normal case. Two or
    more means the recorder lost time part-way through — Mira's leg on
    Sept 17 2026 dropped 160 s while her session was handed over, and every
    word after that sat 160 s early in the mix. Empty means it never
    correlated."""
    workdir = Path(workdir)
    track = _whole_envelope(Path(track_wav), workdir)
    room = _whole_envelope(Path(room_wav), workdir)
    total = len(track) / ROOM_ENVELOPE_SR
    window = int(ROOM_WINDOW_SEC * ROOM_ENVELOPE_SR)
    step = int(ROOM_STEP_SEC * ROOM_ENVELOPE_SR)
    lo, hi, base = -ROOM_MAX_OFFSET_SEC, ROOM_MAX_OFFSET_SEC, 0.0
    if expected is not None:
        base = float(expected)
        lo, hi = -span, span
        cut = int(round(-base * ROOM_ENVELOPE_SR))
        if cut > 0:
            track = track[cut:]
        elif cut < 0:
            track = np.concatenate([np.zeros(-cut, dtype=np.float32), track])
    covered = min(len(track), len(room))
    if covered < 2 * window:
        window = max(int(ROOM_MIN_WINDOW_SEC * ROOM_ENVELOPE_SR), covered // 3)
        step = max(1, window // 2)
    runs = _runs(_window_picks(track, room, window, step, lo, hi, base))
    pieces: list[dict] = []
    for i, run in enumerate(runs):
        delay = float(np.median([d for _, d, _ in run]))
        # Window starts are in the shifted track's clock; the piece bounds
        # are wanted in the file's own clock, so undo the shift.
        shift = -base if expected is not None else 0.0
        start = 0.0 if i == 0 else pieces[-1]["to"]
        if i + 1 < len(runs):
            nxt = runs[i + 1]
            seam = _seam(track, room, base, run[-1][0] + window / ROOM_ENVELOPE_SR,
                         nxt[0][0], delay, float(np.median([d for _, d, _ in nxt])))
            end = min(total, max(start, seam + shift))
        else:
            end = total
        pieces.append({"from": round(start, 3), "to": round(end, 3),
                       "delay": round(delay, 3), "windows": len(run),
                       "agreement": round(float(np.median([s for *_, s in run])), 3)})
    return pieces


def estimate_room_delay(track_wav: Path, room_wav: Path, workdir: Path,
                        expected: Optional[float] = None,
                        span: float = ROOM_EXPECTED_SPAN_SEC,
                        ) -> Tuple[float, float, int]:
    """How long to DELAY ``track_wav`` so it sits on the room's clock.

    ``room_wav`` is the reference the whole episode is built on — the
    guest's right channel, which carries everything the guest heard.
    Returns ``(delay_seconds, agreement, windows_used)``. ``agreement`` is
    the median per-window correlation; ``windows_used`` is how many windows
    cleared ROOM_MIN_CORRELATION. A caller that gets fewer than
    ROOM_MIN_WINDOWS should treat the answer as unknown and say so rather
    than shipping a mix nobody checked.
    """
    workdir = Path(workdir)
    track = _whole_envelope(Path(track_wav), workdir)
    room = _whole_envelope(Path(room_wav), workdir)
    window = int(ROOM_WINDOW_SEC * ROOM_ENVELOPE_SR)
    step = int(ROOM_STEP_SEC * ROOM_ENVELOPE_SR)
    # ``expected`` is the delay the room's own timeline implies — this leg's
    # join, against the reference leg's. It is never exact, because a
    # recorder starts seconds after its leg connects, so it is applied to
    # the envelope first and the correlation then measures what is left.
    #
    # Applying it matters as much as knowing it. These windows compare the
    # same stretch of both files, so a correlation can only ever find a lag
    # shorter than the window: with Mira's leg 268 s ahead of the guest's,
    # a 150 s window of one holds no part of the conversation in the other,
    # and the search returned nothing however wide its lag range (Adrian
    # Wolfberg, second attempt, Sept 15 2026). Shifting the envelope by the
    # expectation puts the two roughly on top of each other, and what
    # remains is the few seconds of recorder lag the correlation is good at.
    lo, hi = -ROOM_MAX_OFFSET_SEC, ROOM_MAX_OFFSET_SEC
    base = 0.0
    if expected is not None:
        base = float(expected)
        lo, hi = -span, span
        cut = int(round(-base * ROOM_ENVELOPE_SR))
        if cut > 0:
            track = track[cut:]
        elif cut < 0:
            track = np.concatenate(
                [np.zeros(-cut, dtype=np.float32), track])
    covered = min(len(track), len(room))
    # A two-minute reconnection cannot hold two 150-second windows. The
    # window follows the material: a short leg is measured in short windows
    # rather than not measured at all (Adrian Wolfberg's second, third and
    # fourth legs were 118s, 373s and 28s).
    if covered < 2 * window:
        window = max(int(ROOM_MIN_WINDOW_SEC * ROOM_ENVELOPE_SR), covered // 3)
        step = max(1, window // 2)
    picks: list[Tuple[float, float]] = []
    for start in range(0, max(0, covered - window), step):
        lag, strength = _window_offset(track[start:start + window],
                                       room[start:start + window], lo, hi)
        if lag is None or strength < ROOM_MIN_CORRELATION:
            continue
        picks.append((base - lag, strength))  # lag<0 = runs early = delay it
    if not picks:
        logger.warning("room alignment: %s never correlated with the room",
                       Path(track_wav).name)
        return 0.0, 0.0, 0
    # One leg has one offset, so the answer is the value the windows AGREE
    # on, not the middle of everything they said. A plain median let two
    # noise windows drag Mira's estimate 35 s off the truth. Anchor on the
    # window that correlated best and keep only the others that land within
    # a couple of seconds of it; those are the ones measuring the same
    # thing.
    picks.sort(key=lambda p: p[1], reverse=True)
    anchor = picks[0][0]
    cluster = [d for d, _ in picks if abs(d - anchor) <= ROOM_AGREE_SEC]
    strengths = [st for d, st in picks if abs(d - anchor) <= ROOM_AGREE_SEC]
    delays = np.array(cluster)
    delay = float(np.median(delays))
    agreement = float(np.median(strengths))
    spread = float(np.max(np.abs(delays - delay))) if len(delays) > 1 else 0.0
    picks = [(d, st) for d, st in zip(cluster, strengths)]
    logger.info("room alignment: %s delay %+.2fs (%d windows, corr %.2f, "
                "spread %.2fs)", Path(track_wav).name, delay, len(picks),
                agreement, spread)
    return delay, agreement, len(picks)


def _cut(track_wav: Path, start: float, end: float, out: Path) -> Path:
    _run(["ffmpeg", "-y", "-ss", f"{start:.3f}", "-to", f"{end:.3f}",
          "-i", track_wav, "-ar", TARGET_SR, "-ac", "1", "-c:a", "pcm_s16le", out])
    return out


def place_pieces(track_wav: Path, pieces: list[dict], workdir: Path) -> Path:
    """Cut a leg at its clock jumps and lay each piece at its own delay."""
    from audio.mix_tracks import mix_same_clock  # local import: no cycle
    workdir = Path(workdir)
    workdir.mkdir(parents=True, exist_ok=True)
    stem = Path(track_wav).stem
    placed = []
    for i, piece in enumerate(pieces):
        part = _cut(track_wav, piece["from"], piece["to"],
                    workdir / f"{stem}_piece{i}.wav")
        # The piece starts at piece["from"] in its own file, so it lands at
        # from + delay on the room's clock.
        placed.append(place_at(part, piece["from"] + piece["delay"], workdir))
    return mix_same_clock(placed, workdir / f"{stem}_room.wav")


def align_to_room(track_wav: Path, room_wav: Path, workdir: Path,
                  expected: Optional[float] = None,
                  pieces_out: Optional[list] = None,
                  ) -> Tuple[Path, float, int]:
    """Shift ``track_wav`` onto the room's clock. Returns the new path, the
    delay applied, and how many windows agreed (0 = left untouched)."""
    workdir = Path(workdir)
    workdir.mkdir(parents=True, exist_ok=True)
    pieces = room_pieces(track_wav, room_wav, workdir, expected=expected)
    if pieces_out is not None:
        pieces_out[:] = pieces
    if len(pieces) > 1:
        # The leg's clock jumped. Each stretch is placed on its own; the
        # first piece's delay is what the caller records as "the" delay.
        logger.warning("room alignment: %s has %d clock pieces: %s",
                       Path(track_wav).name, len(pieces),
                       ", ".join(f"{p['from']:.0f}-{p['to']:.0f}s at "
                                 f"{p['delay']:+.2f}s" for p in pieces))
        out = place_pieces(track_wav, pieces, workdir)
        delay = pieces[0]["delay"]
        windows = sum(p["windows"] for p in pieces)
    else:
        delay, agreement, windows = estimate_room_delay(
            track_wav, room_wav, workdir, expected=expected)
        # Two agreeing windows, or one that agrees with the room
        # emphatically — a short leg has only one window to give and
        # refusing it throws the co-host out of his own interview.
        enough = windows >= ROOM_MIN_WINDOWS or (windows == 1
                                                 and agreement >= ROOM_STRONG_CORR)
        if not enough or abs(delay) < 0.05:
            return Path(track_wav), 0.0, windows if enough else 0
        out = workdir / (Path(track_wav).stem + "_room.wav")
        cmd = ["ffmpeg", "-y"]
        if delay > 0:
            cmd += ["-i", track_wav, "-af", f"adelay=delays={int(round(delay * 1000))}:all=1"]
        else:
            cmd += ["-ss", f"{-delay:.3f}", "-i", track_wav]
        cmd += ["-ar", TARGET_SR, "-ac", "1", "-c:a", "pcm_s16le", out]
        _run(cmd)
    # Check the work. Measuring an offset and applying it are two different
    # things, and three episodes went out misaligned while the pipeline
    # believed it had done the arithmetic. The shifted track is measured
    # again against the room: it should now be sitting at zero, and if it
    # is not, this is reported as a track that could not be placed rather
    # than shipped as one that was.
    #
    # And the check has to cover the whole file. Measured as one number, a
    # track whose second half is 160 s out still "verifies": the windows
    # that agree are at zero and the ones that do not are simply not
    # counted. Every stretch that correlates at all must sit at zero.
    check = room_pieces(out, room_wav, workdir, expected=0.0, span=30.0)
    off = [p for p in check if abs(p["delay"]) > ROOM_RESIDUAL_SEC]
    if check and not off:
        logger.info("room alignment: %s verified at %+.2fs (corr %.2f)",
                    Path(track_wav).name, check[0]["delay"], check[0]["agreement"])
        return out, delay, windows
    logger.warning("room alignment: %s still out after placing at %+.2fs "
                   "(%s) — treating as unplaced", Path(track_wav).name, delay,
                   ", ".join(f"{p['from']:.0f}-{p['to']:.0f}s {p['delay']:+.2f}s"
                             for p in off) or "no check windows")
    return out, delay, 0


def place_at(track_wav: Path, delay: float, workdir: Path) -> Path:
    """Shift a track by a delay somebody else worked out.

    A leg too short or too quiet to correlate can still be placed: every
    leg of the same participant is recorded by the same machinery, so the
    gap between a leg connecting and its recorder starting is the same
    gap each time. On Adrian Wolfberg's four legs it was 12.23s, 12.40s
    and — where the correlation could be checked — 12.5s. Taking the
    measured lag from a leg that did correlate and applying it to one that
    did not put the second leg within 0.21s of its own measurement.
    """
    workdir = Path(workdir)
    workdir.mkdir(parents=True, exist_ok=True)
    out = workdir / (Path(track_wav).stem + "_placed.wav")
    cmd = ["ffmpeg", "-y"]
    if delay > 0:
        cmd += ["-i", track_wav,
                "-af", f"adelay=delays={int(round(delay * 1000))}:all=1"]
    elif delay < 0:
        cmd += ["-ss", f"{-delay:.3f}", "-i", track_wav]
    else:
        cmd += ["-i", track_wav]
    cmd += ["-ar", TARGET_SR, "-ac", "1", "-c:a", "pcm_s16le", out]
    _run(cmd)
    return out


def describe_manifest(manifest: Optional[Dict[str, Any]]) -> str:
    """One-line human summary for logs/notes."""
    if not isinstance(manifest, dict):
        return "no manifest"
    return json.dumps({
        "chunks": len(manifest.get("chunks") or []),
        "missing": len(manifest.get("missing") or []),
        "duration_ms": manifest.get("duration_ms"),
    })
