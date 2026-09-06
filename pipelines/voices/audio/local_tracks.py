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


def describe_manifest(manifest: Optional[Dict[str, Any]]) -> str:
    """One-line human summary for logs/notes."""
    if not isinstance(manifest, dict):
        return "no manifest"
    return json.dumps({
        "chunks": len(manifest.get("chunks") or []),
        "missing": len(manifest.get("missing") or []),
        "duration_ms": manifest.get("duration_ms"),
    })
