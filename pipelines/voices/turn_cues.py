"""When has the guest finished? What the tape says (Oct 28 2026).

Patrick, after the Oct 28 test room: Mira waits about four seconds after
every answer (median 4.4 s from his last word to her first), which is safe
and sounds slow. He asked whether the guest's own cues, on camera and in the
voice, can tell the room an answer is over sooner, without ever cutting in.

This module answers that from recordings, not from opinion. For every pause
in the guest's speech it asks one question with a known answer: did the
guest go on (a HOLD), or did they stop and wait for the host (an END)? Then
it measures what was observable at the moment the pause began:

* voice: the pitch movement over the last half second (a fall to the
  bottom of the speaker's range is the classic end), how low the last pitch
  sits in the speaker's range, the energy fade, and how long the last voiced
  stretch ran against the speaker's usual (a drawn-out last word);
* words, when per-word timestamps are supplied: whether the last word is a
  connective or a filler ("and", "so", "um" hold the floor);
* camera, when the guest's browser take is placed on the leg's clock
  (video_take.py): how much the picture moves in the second before the
  pause against the first moments of it, over the whole frame and the face
  region (people tend to keep gesturing, or look away, while they hold the
  floor, and settle when they hand it over).

It scores two ways of deciding:

1. silence alone: take the turn once the guest has been quiet for T
   seconds, for a range of T (what the room does now, at about 4 s);
2. cues: a small logistic model, trained with each room left out in turn,
   takes the turn early (T_fast) when the cues say END with confidence
   theta, and otherwise waits the full T_slow.

and reports, for each, how many holds it would have cut into per hundred
answers and how long the guest waits at a real end. A cue is worth building
into the room only if it moves that frontier. The labels come from the
recordings themselves, so a room where Mira interrupted teaches the wrong
thing at that pause; an END counts only when the guest stayed quiet at
least ``END_MIN_WAIT_SEC`` before anyone spoke and did not start again
straight over her.

Run::

    python pipelines/voices/turn_cues.py --recent 20 --out turn_cues.md
    python pipelines/voices/turn_cues.py --run <run id> [--run ...] --video

Nothing here touches a live room or a published file.
"""

from __future__ import annotations

import argparse
import json
import logging
import math
import re
import statistics
import subprocess
import sys
import warnings
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

import numpy as np

logger = logging.getLogger(__name__)

SR = 8000                 #: analysis sample rate (pitch stays under 400 Hz)
FRAME = 160               #: 20 ms frames
HOP_SEC = FRAME / SR
#: A pause shorter than this is the space between words.
MIN_PAUSE_SEC = 0.25
#: ... and one longer than this is not part of a conversation (a hold, a
#: dropped line, a guest who left the desk).
MAX_PAUSE_SEC = 20.0
#: An END: the guest stayed quiet at least this long before anyone spoke.
END_MIN_WAIT_SEC = 1.0
#: A guest who starts again within this long of the host's first word was
#: not finished: the pause was cut into, and teaches nothing either way.
RESUME_OVER_SEC = 1.0
#: Speech runs shorter than this are clicks and breaths.
MIN_SPEECH_SEC = 0.15
#: Gaps shorter than this inside speech are closed (stop consonants).
FILL_GAP_SEC = 0.12

SILENCE_GRID = (0.5, 0.7, 1.0, 1.25, 1.5, 2.0, 2.5, 3.0, 4.0)
FAST_GRID = (0.5, 0.7, 1.0)
SLOW_GRID = (2.0, 3.0, 4.0)
THETA_GRID = (0.6, 0.7, 0.8, 0.9)

#: Words that hold the floor when they are the last thing said.
HOLDING_WORDS = frozenset("""
and but so or because cause 'cause um uh er erm like which that where when
if then also plus the a an of to with for in on my our your their is was
""".split())


# ---------------------------------------------------------------------------
# Audio in
# ---------------------------------------------------------------------------

Source = Any   #: a path or URL, or ``(path or URL, channel)`` for one side of a stereo file


def load_audio(source: Source, sr: int = SR) -> np.ndarray:
    """A track (path or URL) as mono float32 at ``sr``. ``(source, n)`` takes
    channel ``n`` of a stereo file (a rehearsal room's recording carries the
    guest on the left and Mira on the right). URLs are fetched with curl and
    piped through ffmpeg, so a 45-minute WAV never lands on disk."""
    src, channel = (source if isinstance(source, (tuple, list)) else (source, None))
    src = str(src)
    mix = ["-af", f"pan=mono|c0=c{int(channel)}"] if channel is not None else ["-ac", "1"]
    cmd = ["ffmpeg", "-v", "error", "-i", "pipe:0" if _is_url(src) else src,
           *mix, "-ar", str(sr), "-f", "s16le", "pipe:1"]
    if _is_url(src):
        curl = subprocess.Popen(["curl", "-sSfL", "--max-time", "900", src],
                                stdout=subprocess.PIPE)
        out = subprocess.run(cmd, stdin=curl.stdout, capture_output=True, timeout=1000)
        curl.stdout.close()
        curl.wait()
    else:
        out = subprocess.run(cmd, capture_output=True, timeout=1000)
    if out.returncode != 0:
        raise RuntimeError(f"could not decode {src[:80]}: {out.stderr[-300:]!r}")
    return np.frombuffer(out.stdout, dtype=np.int16).astype(np.float32) / 32768.0


def _is_url(source: str) -> bool:
    return str(source).startswith(("http://", "https://"))


def frame_db(audio: np.ndarray) -> np.ndarray:
    """RMS level of each 20 ms frame, in dB."""
    n = len(audio) // FRAME
    if n == 0:
        return np.zeros(0, dtype=np.float32)
    frames = audio[: n * FRAME].reshape(n, FRAME)
    rms = np.sqrt(np.mean(frames * frames, axis=1) + 1e-12)
    return (20.0 * np.log10(rms + 1e-9)).astype(np.float32)


def otsu_threshold(values: np.ndarray, bins: int = 200) -> float:
    """The level that best splits a track's frames into two classes (quiet
    and speech): Otsu's method on the frame-level histogram."""
    h, e = np.histogram(values, bins=bins)
    c = (e[:-1] + e[1:]) / 2.0
    w0 = np.cumsum(h).astype(np.float64)
    w1 = w0[-1] - w0
    m0 = np.cumsum(h * c)
    mt = m0[-1]
    with np.errstate(divide="ignore", invalid="ignore"):
        mu0 = m0 / w0
        mu1 = (mt - m0) / w1
        between = w0 * w1 * (mu0 - mu1) ** 2
    between = np.where((w0 == 0) | (w1 == 0), -1.0, between)
    return float(c[int(np.argmax(between))])


def speech_runs(db: np.ndarray, *, hysteresis_db: float = 6.0) -> List[Tuple[float, float]]:
    """``(start, end)`` seconds where a track carries speech.

    The tracks are not levelled the same way and some carry stretches of
    digital silence (a gated or missing take), so the threshold is the
    track's own: Otsu's split of its non-silent frames into quiet and
    speech. A run starts above it and continues while the level stays
    within ``hysteresis_db`` below it (soft syllables do not split a word);
    short gaps are closed and blips dropped. On Glenn Broder's guest track
    (Oct 27) this finds 30 minutes of speech in a 52-minute room."""
    if len(db) == 0:
        return []
    live = db[db > -100.0]
    if len(live) < 50:
        return []
    hi = otsu_threshold(live)
    # A track whose quiet is one narrow level (a clean gate) puts Otsu at the
    # top edge of the quiet; keep the threshold clear of it.
    below = live[live <= hi]
    quiet = float(np.median(below)) if len(below) else hi - 20.0
    hi = max(hi, quiet + 8.0)
    lo = max(hi - hysteresis_db, quiet + 3.0)
    runs: List[Tuple[float, float]] = []
    start = None
    for i, level in enumerate(db):
        if start is None:
            if level > hi:
                start = i
        elif level <= lo:
            runs.append((start * HOP_SEC, i * HOP_SEC))
            start = None
    if start is not None:
        runs.append((start * HOP_SEC, len(db) * HOP_SEC))
    merged: List[List[float]] = []
    for a, b in runs:
        if merged and a - merged[-1][1] < FILL_GAP_SEC:
            merged[-1][1] = b
        else:
            merged.append([a, b])
    return [(a, b) for a, b in merged if b - a >= MIN_SPEECH_SEC]


def runs_from_words(words: Iterable[dict], *, join_gap: float = FILL_GAP_SEC
                    ) -> List[Tuple[float, float]]:
    """Speech runs from per-word timestamps (Whisper ``start``/``end``)."""
    spans = sorted((float(w["start"]), float(w["end"])) for w in words or []
                   if isinstance(w, dict) and w.get("start") is not None
                   and w.get("end") is not None and float(w["end"]) > float(w["start"]))
    out: List[List[float]] = []
    for a, b in spans:
        if out and a - out[-1][1] < join_gap:
            out[-1][1] = max(out[-1][1], b)
        else:
            out.append([a, b])
    return [(a, b) for a, b in out]


# ---------------------------------------------------------------------------
# Pauses, labelled by what happened next
# ---------------------------------------------------------------------------

@dataclass
class Pause:
    at: float                  #: the guest's last speech before the pause ended here
    length: float              #: how long the guest stayed quiet (to their own next word or the host's)
    label: str                 #: "hold" | "end" | "cut"
    host_after: Optional[float] = None   #: seconds from ``at`` to the host's first word
    turn_sec: float = 0.0      #: how long this answer had run when the pause began
    features: Dict[str, float] = field(default_factory=dict)


def _first_start_in(runs: Sequence[Tuple[float, float]], lo: float, hi: float) -> Optional[float]:
    for a, _b in runs:
        if a >= hi:
            return None
        if a >= lo:
            return a
    return None


def _active_at(runs: Sequence[Tuple[float, float]], t: float) -> bool:
    return any(a <= t < b for a, b in runs)


def label_pauses(guest: Sequence[Tuple[float, float]],
                 others: Sequence[Tuple[float, float]]) -> List[Pause]:
    """Every pause in the guest's speech, labelled.

    * HOLD — nobody else spoke and the guest went on.
    * END — someone else spoke after at least ``END_MIN_WAIT_SEC`` of the
      guest's silence, and the guest did not start again over them within
      ``RESUME_OVER_SEC``.
    * CUT — someone else spoke sooner, or the guest started again straight
      over them: the room decided for the guest, and the pause is set aside.

    A pause that begins while someone else is already talking is skipped
    (the guest was being talked over, not deciding)."""
    others = sorted(others)
    out: List[Pause] = []
    turn_start = guest[0][0] if guest else 0.0
    for i in range(len(guest) - 1):
        a = guest[i][1]
        b = guest[i + 1][0]
        gap = b - a
        if gap < MIN_PAUSE_SEC:
            continue
        if _active_at(others, a - 0.05):
            turn_start = b
            continue
        host = _first_start_in(others, a, b)
        turn_sec = a - turn_start
        if host is None:
            if gap <= MAX_PAUSE_SEC:
                out.append(Pause(at=a, length=gap, label="hold", turn_sec=turn_sec))
            continue
        wait = host - a
        # The guest came back over the host's first words: not finished.
        resumed_over = b - host < RESUME_OVER_SEC
        label = "end" if (wait >= END_MIN_WAIT_SEC and not resumed_over) else "cut"
        if wait <= MAX_PAUSE_SEC:
            out.append(Pause(at=a, length=wait, label=label, host_after=wait, turn_sec=turn_sec))
        turn_start = b
    return out


# ---------------------------------------------------------------------------
# Voice cues at the moment the pause begins
# ---------------------------------------------------------------------------

def pitch_track(segment: np.ndarray, sr: int = SR, *, fmin: float = 70.0,
                fmax: float = 400.0, win: int = 320, hop: int = 80,
                voicing: float = 0.45) -> np.ndarray:
    """f0 in Hz every 10 ms (0 where unvoiced): normalised autocorrelation,
    which is plenty for a contour over half a second."""
    lo, hi = int(sr / fmax), int(sr / fmin)
    out = []
    for s in range(0, max(0, len(segment) - win), hop):
        x = segment[s:s + win]
        x = x - x.mean()
        energy = float(np.dot(x, x))
        if energy < 1e-6:
            out.append(0.0)
            continue
        ac = np.correlate(x, x, mode="full")[win - 1:]
        ac = ac / (ac[0] + 1e-12)
        seg = ac[lo:hi]
        if len(seg) == 0:
            out.append(0.0)
            continue
        k = int(np.argmax(seg))
        out.append(sr / (lo + k) if seg[k] >= voicing else 0.0)
    return np.asarray(out, dtype=np.float32)


def _slope(y: np.ndarray, dt: float) -> Optional[float]:
    if len(y) < 3:
        return None
    x = np.arange(len(y)) * dt
    return float(np.polyfit(x, y, 1)[0])


def voice_features(audio: np.ndarray, at: float, speaker_f0: Tuple[float, float],
                   speaker_run_sec: float, runs: Sequence[Tuple[float, float]]) -> Dict[str, float]:
    """What the voice was doing in the half second before ``at``."""
    feats: Dict[str, float] = {}
    s = max(0, int((at - 0.6) * SR))
    e = min(len(audio), int(at * SR))
    seg = audio[s:e]
    f0 = pitch_track(seg)
    voiced = f0[f0 > 0]
    lo, hi = speaker_f0
    if len(voiced) >= 4:
        st = 12.0 * np.log2(voiced / max(lo, 1.0))
        slope = _slope(st, 0.01)
        feats["f0_slope_st_per_s"] = round(slope, 3) if slope is not None else 0.0
        span = max(hi - lo, 1.0)
        feats["f0_final_in_range"] = round(float((np.median(voiced[-4:]) - lo) / span), 3)
        feats["voiced_share"] = round(len(voiced) / max(len(f0), 1), 3)
    db = frame_db(audio[max(0, int((at - 0.4) * SR)):e])
    slope_db = _slope(db, HOP_SEC)
    if slope_db is not None:
        feats["energy_slope_db_per_s"] = round(slope_db, 2)
    last = next(((a, b) for a, b in reversed(runs) if b <= at + 1e-6), None)
    if last and speaker_run_sec > 0:
        feats["last_run_rel"] = round((last[1] - last[0]) / speaker_run_sec, 3)
    return feats


def speaker_profile(audio: np.ndarray, runs: Sequence[Tuple[float, float]],
                    sample: int = 60) -> Tuple[Tuple[float, float], float]:
    """The speaker's pitch range (10th and 90th percentiles over a sample of
    their speech) and their median speech-run length."""
    if not runs:
        return (100.0, 200.0), 1.0
    step = max(1, len(runs) // sample)
    f0s: List[float] = []
    for a, b in runs[::step]:
        seg = audio[int(a * SR):int(min(b, a + 2.0) * SR)]
        f = pitch_track(seg)
        f0s.extend(float(v) for v in f[f > 0])
    if len(f0s) < 20:
        rng = (100.0, 200.0)
    else:
        rng = (float(np.percentile(f0s, 10)), float(np.percentile(f0s, 90)))
    return rng, float(statistics.median(b - a for a, b in runs))


#: The room's own test for an unfinished clause (age_of_ai_interview.js
#: UNFINISHED_TAIL_RE / looksFinished), mirrored so the tape can say how
#: well it separates the guest thinking from the guest done.
UNFINISHED_TAIL_RE = re.compile(
    r"(?:^|\s)(and|but|so|or|because|although|though|um|uh|like|the|a|an|to|of|that|"
    r"which|if|when|then|also|with|for|in|on|at|is|was|are|were|i|we|you|it|they|he|"
    r"she|my|our|your|their|this|these|those|as|than|by|from|into|about)[,.\s]*$", re.I)


def room_reads_finished(text: str) -> bool:
    """The room's looksFinished, in Python."""
    t = str(text or "").strip()
    if not t:
        return False
    if re.search(r"[.?!][\"')\]]?$", t):
        return True
    if re.search(r"[,;:\-–—]$", t):
        return False
    return not UNFINISHED_TAIL_RE.search(t)


def clip_word_features(audio16: np.ndarray, at: float, model: Any,
                       before: float = 4.0) -> Dict[str, float]:
    """The guest's last words before ``at``, transcribed from the four
    seconds before it (16 kHz audio): whether the last word holds the floor
    (a connective, an article, a filler: the room's own tail list, read
    without punctuation) and whether the room's rule would read the clause
    as finished."""
    s = max(0, int((at - before) * 16000))
    e = min(len(audio16), int((at + 0.1) * 16000))
    clip = audio16[s:e]
    if len(clip) < 8000:
        return {}
    segments, _info = model.transcribe(clip, language="en", beam_size=1, word_timestamps=True,
                                       vad_filter=False, condition_on_previous_text=False)
    words = [w for seg in segments for w in (seg.words or [])]
    if not words:
        return {}
    text = "".join(w.word for w in words).strip()
    bare = re.sub(r"[^\w\s']+", "", text).strip()
    return {"last_word_holds": 1.0 if UNFINISHED_TAIL_RE.search(bare) else 0.0,
            "room_reads_finished": 1.0 if room_reads_finished(text) else 0.0,
            "last_word_question": 1.0 if text.endswith("?") else 0.0}


def word_features(words: Sequence[dict], at: float) -> Dict[str, float]:
    """The last word before ``at``: a connective or filler holds the floor;
    a question mark hands it over."""
    last = None
    for w in words:
        try:
            if float(w["end"]) <= at + 0.15:
                last = w
            else:
                break
        except (KeyError, TypeError, ValueError):
            continue
    if not last:
        return {}
    raw = str(last.get("word") or "").strip()
    token = re.sub(r"[^\w']+", "", raw.lower())
    return {"last_word_holds": 1.0 if token in HOLDING_WORDS else 0.0,
            "last_word_question": 1.0 if raw.endswith("?") else 0.0,
            "last_word_sentence_end": 1.0 if raw.endswith((".", "!", "?")) else 0.0}


# ---------------------------------------------------------------------------
# Camera cues (the guest's browser take, placed by video_take.place_take)
# ---------------------------------------------------------------------------

VIDEO_W, VIDEO_H, VIDEO_FPS = 96, 54, 10


def load_video_frames(source: str) -> np.ndarray:
    """The take as small grey frames, ``(n, 54, 96)`` uint8 at 10 fps."""
    cmd = ["ffmpeg", "-v", "error", "-i", str(source), "-an", "-vf",
           f"fps={VIDEO_FPS},scale={VIDEO_W}:{VIDEO_H},format=gray",
           "-f", "rawvideo", "pipe:1"]
    if _is_url(source):
        curl = subprocess.Popen(["curl", "-sSfL", "--max-time", "1800", source],
                                stdout=subprocess.PIPE)
        cmd[cmd.index(str(source))] = "pipe:0"
        out = subprocess.run(cmd, stdin=curl.stdout, capture_output=True, timeout=2000)
        curl.stdout.close()
        curl.wait()
    else:
        out = subprocess.run(cmd, capture_output=True, timeout=2000)
    if out.returncode != 0:
        raise RuntimeError(f"could not decode video {source}: {out.stderr[-300:]!r}")
    raw = np.frombuffer(out.stdout, dtype=np.uint8)
    n = len(raw) // (VIDEO_W * VIDEO_H)
    return raw[: n * VIDEO_W * VIDEO_H].reshape(n, VIDEO_H, VIDEO_W)


def motion_series(frames: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
    """Mean absolute change between consecutive frames: the whole picture,
    and the face region (the middle half across, the top two thirds down,
    where a webcam guest's head sits)."""
    if len(frames) < 2:
        return np.zeros(0), np.zeros(0)
    d = np.abs(np.diff(frames.astype(np.int16), axis=0)).astype(np.float32)
    whole = d.mean(axis=(1, 2))
    y1 = int(VIDEO_H * 2 / 3)
    x0, x1 = int(VIDEO_W / 4), int(VIDEO_W * 3 / 4)
    face = d[:, :y1, x0:x1].mean(axis=(1, 2))
    return whole, face


def video_features(whole: np.ndarray, face: np.ndarray, video_t: float,
                   *, look: float = 0.5) -> Dict[str, float]:
    """Motion in the second before the pause against the first ``look``
    seconds of it (what the room could see by the time it decides)."""
    i = int(round(video_t * VIDEO_FPS))
    before = slice(max(0, i - VIDEO_FPS), i)
    after = slice(i, min(len(whole), i + max(1, int(look * VIDEO_FPS))))
    if i <= 1 or after.stop - after.start < 1 or before.stop - before.start < 2:
        return {}
    eps = 0.05
    wb, wa = float(whole[before].mean()), float(whole[after].mean())
    fb, fa = float(face[before].mean()), float(face[after].mean())
    return {"motion_before": round(wb, 3), "motion_after": round(wa, 3),
            "motion_drop": round(math.log((wa + eps) / (wb + eps)), 3),
            "face_motion_drop": round(math.log((fa + eps) / (fb + eps)), 3)}


# ---------------------------------------------------------------------------
# Deciding: silence alone against cues
# ---------------------------------------------------------------------------

def silence_policy(pauses: Sequence[Pause], grid: Sequence[float] = SILENCE_GRID
                   ) -> List[Dict[str, Any]]:
    """Take the turn after T seconds of silence: for each T, holds cut into
    per hundred real ends, and the ends that waited at least T on the tape
    (only those can say the guest would still have been quiet at T)."""
    holds = [p for p in pauses if p.label == "hold"]
    ends = [p for p in pauses if p.label == "end"]
    rows = []
    for t in grid:
        cut = sum(1 for p in holds if p.length > t)
        rows.append({"wait_sec": t, "holds_cut": cut,
                     "cut_per_100_answers": round(100.0 * cut / max(len(ends), 1), 1),
                     "ends_observable": sum(1 for p in ends if p.length >= t)})
    return rows


#: Per-guest waits tried by ``adaptive_policy``: the quantile of this
#: guest's own mid-answer pauses so far, plus a margin, between the bounds.
ADAPT_QUANTILES = (0.97, 0.98, 0.99)
ADAPT_MARGINS = (0.3, 0.5, 0.8)
ADAPT_WARMUP = 20            #: holds heard before the room trusts the guest's own habit
ADAPT_START_SEC = 3.0        #: the wait until then
ADAPT_BOUNDS = (1.5, 4.0)


def adaptive_policy(rooms: Dict[str, Sequence[Pause]]) -> List[Dict[str, Any]]:
    """Wait as long as THIS guest has paused mid-answer: after
    ``ADAPT_WARMUP`` holds, the wait is a high quantile of their own holds so
    far plus a margin (bounded); until then ``ADAPT_START_SEC``. Each pause
    is decided before it is added to the history, in the order the room
    heard them, so nothing is learned from the future."""
    rows = []
    for q in ADAPT_QUANTILES:
        for margin in ADAPT_MARGINS:
            cut = ends = 0
            waits: List[float] = []
            for pauses in rooms.values():
                hist: List[float] = []
                for p in sorted(pauses, key=lambda x: x.at):
                    if p.label not in ("hold", "end"):
                        continue
                    wait = (ADAPT_START_SEC if len(hist) < ADAPT_WARMUP else
                            float(np.clip(np.quantile(hist, q) + margin, *ADAPT_BOUNDS)))
                    if p.label == "hold":
                        cut += 1 if p.length > wait else 0
                        hist.append(p.length)
                    else:
                        ends += 1
                        waits.append(wait)
            if ends:
                rows.append({"quantile": q, "margin_sec": margin,
                             "cut_per_100_answers": round(100.0 * cut / ends, 1),
                             "mean_wait_sec": round(float(np.mean(waits)), 2),
                             "median_wait_sec": round(float(np.median(waits)), 2)})
    return rows


def _design(pauses: Sequence[Pause], names: Sequence[str]) -> np.ndarray:
    return np.array([[p.features.get(n, np.nan) for n in names] for p in pauses],
                    dtype=np.float64)


def _fit_logistic(x: np.ndarray, y: np.ndarray, *, l2: float = 1.0,
                  steps: int = 400, lr: float = 0.2) -> Tuple[np.ndarray, float]:
    w = np.zeros(x.shape[1])
    b = 0.0
    n = max(len(y), 1)
    for _ in range(steps):
        z = x @ w + b
        p = 1.0 / (1.0 + np.exp(-np.clip(z, -30, 30)))
        g = p - y
        w -= lr * (x.T @ g / n + l2 * w / n)
        b -= lr * float(g.mean())
    return w, b


def cue_scores(pauses: Sequence[Pause], room_of: Sequence[str],
               names: Sequence[str], at_least: float = 0.0
               ) -> Tuple[np.ndarray, Dict[str, float], Optional[float]]:
    """P(END) for every hold and end still silent ``at_least`` seconds in
    (the pauses a room deciding at that moment would face; a breath the
    guest ended sooner never reaches the decision), each scored by a model
    trained on the OTHER rooms (leave one room out). Also the all-rooms
    weights, and the AUC of the held-out scores (0.5: the cues say nothing).
    Missing features take the training mean."""
    idx = [i for i, p in enumerate(pauses)
           if p.label in ("hold", "end") and p.length >= at_least]
    scores = np.full(len(pauses), np.nan)
    if not idx:
        return scores, {}, None
    x = _design([pauses[i] for i in idx], names)
    y = np.array([1.0 if pauses[i].label == "end" else 0.0 for i in idx])
    rooms = np.array([room_of[i] for i in idx])

    def prep(train: np.ndarray, test: np.ndarray):
        # A cue no pause carries (no camera that day) is an all-NaN column:
        # its mean becomes 0 and it needs no warning.
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", RuntimeWarning)
            mu = np.nanmean(train, axis=0)
            sd = np.nanstd(train, axis=0)
        mu = np.where(np.isnan(mu), 0.0, mu)
        sd = np.where((sd == 0) | np.isnan(sd), 1.0, sd)
        fill = lambda m: np.where(np.isnan(m), mu, m)  # noqa: E731
        return (fill(train) - mu) / sd, (fill(test) - mu) / sd

    for room in sorted(set(rooms)):
        tr, te = rooms != room, rooms == room
        if tr.sum() < 20 or len(set(y[tr])) < 2:
            continue
        xtr, xte = prep(x[tr], x[te])
        w, b = _fit_logistic(xtr, y[tr])
        pr = 1.0 / (1.0 + np.exp(-(xte @ w + b)))
        for k, i in enumerate(np.array(idx)[te]):
            scores[i] = pr[k]
    weights: Dict[str, float] = {}
    if len(idx) >= 20 and len(set(y)) == 2:
        xall, _ = prep(x, x)
        w, _b = _fit_logistic(xall, y)
        weights = {n: round(float(v), 3) for n, v in zip(names, w)}
    scored = [(scores[i], pauses[i].label) for i in idx if not np.isnan(scores[i])]
    pos = [sc for sc, lab in scored if lab == "end"]
    neg = [sc for sc, lab in scored if lab == "hold"]
    auc = round(_auc(pos, neg), 3) if pos and neg else None
    return scores, weights, auc


def cue_policy(pauses: Sequence[Pause], room_of: Sequence[str],
               names: Sequence[str]) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    """Take the turn at T_fast when P(END) >= theta, else at T_slow.

    For each T_fast the model is trained and scored on the pauses still
    silent at T_fast (the only ones that decision ever meets). A hold is cut
    into when the policy speaks before the guest went on: scored at or over
    theta and longer than T_fast, or longer than T_slow. Only ends that
    waited at least T_slow on the tape are scored for latency, so the guest
    is known to have still been quiet at whichever moment the policy
    chose."""
    rows: List[Dict[str, Any]] = []
    models: Dict[str, Any] = {}
    holds_all = [p for p in pauses if p.label == "hold"]
    for fast in FAST_GRID:
        scores, weights, auc = cue_scores(pauses, room_of, names, at_least=fast)
        models[str(fast)] = {"auc": auc, "weights": weights}
        for slow in SLOW_GRID:
            ends = [(p, scores[i]) for i, p in enumerate(pauses)
                    if p.label == "end" and p.length >= slow and not np.isnan(scores[i])]
            if not ends:
                continue
            holds = [(p, scores[i]) for i, p in enumerate(pauses)
                     if p.label == "hold" and p.length >= fast and not np.isnan(scores[i])]
            base_cut = sum(1 for p in holds_all if p.length > slow)
            for theta in THETA_GRID:
                cut = sum(1 for p, sc in holds if (sc >= theta and p.length > fast)
                          or p.length > slow)
                waits = [fast if sc >= theta else slow for _p, sc in ends]
                rows.append({
                    "fast_sec": fast, "slow_sec": slow, "theta": theta,
                    "ends_scored": len(ends),
                    "early_share": round(sum(1 for w in waits if w == fast) / len(waits), 3),
                    "mean_wait_sec": round(sum(waits) / len(waits), 2),
                    "cut_per_100_answers": round(100.0 * cut / len(ends), 1),
                    "silence_only_cut_per_100": round(100.0 * base_cut / len(ends), 1),
                })
    return rows, models


# ---------------------------------------------------------------------------
# One room
# ---------------------------------------------------------------------------

VOICE_FEATURES = ("f0_slope_st_per_s", "f0_final_in_range", "voiced_share",
                  "energy_slope_db_per_s", "last_run_rel", "turn_sec")
WORD_FEATURES = ("last_word_holds", "last_word_question", "last_word_sentence_end",
                 "room_reads_finished")
VIDEO_FEATURES = ("motion_drop", "face_motion_drop", "motion_before")


def analyse_room(guest_src: Source, other_srcs: Sequence[Source], *,
                 guest_words: Optional[Sequence[dict]] = None,
                 video: Optional[Dict[str, Any]] = None,
                 whisper: Any = None, words_from_sec: float = 0.7) -> Dict[str, Any]:
    """Every labelled pause of one room with its features. ``video`` is the
    ``tracks.video`` record a run carries (url + pieces per take).
    ``whisper`` (a faster-whisper model) transcribes the last words before
    every pause still silent ``words_from_sec`` in, when the run has no
    word timestamps of its own."""
    audio16 = None
    if whisper is not None:
        audio16 = load_audio(guest_src, sr=16000)
        # The 8 kHz analysis copy: pairs averaged (a gentle low-pass) and kept.
        n = len(audio16) // 2 * 2
        guest_audio = audio16[:n].reshape(-1, 2).mean(axis=1).astype(np.float32)
    else:
        guest_audio = load_audio(guest_src)
    guest_runs = (runs_from_words(guest_words) if guest_words
                  else speech_runs(frame_db(guest_audio)))
    other_runs: List[Tuple[float, float]] = []
    for src in other_srcs:
        if src:
            other_runs.extend(speech_runs(frame_db(load_audio(src))))
    other_runs.sort()
    pauses = label_pauses(guest_runs, other_runs)
    f0_range, run_med = speaker_profile(guest_audio, guest_runs)
    for p in pauses:
        p.features.update(voice_features(guest_audio, p.at, f0_range, run_med, guest_runs))
        p.features["turn_sec"] = round(p.turn_sec, 2)
        if guest_words:
            p.features.update(word_features(guest_words, p.at))
        elif audio16 is not None and p.length >= words_from_sec and p.label in ("hold", "end"):
            try:
                p.features.update(clip_word_features(audio16, p.at, whisper))
            except Exception as exc:  # noqa: BLE001 — one clip never stops a room
                logger.debug("words at %.1f: %s", p.at, exc)
    has_video = False
    for take in (video or {}).get("takes") or []:
        try:
            frames = load_video_frames(take["url"])
        except Exception as exc:  # noqa: BLE001 — a bad take is no take
            logger.warning("video take %s unreadable: %s", take.get("sid"), exc)
            continue
        whole, face = motion_series(frames)
        for p in pauses:
            for piece in take.get("pieces") or []:
                vt = p.at - float(piece["delay"])
                if float(piece["from"]) + 1.0 <= vt < float(piece["to"]) - 1.0:
                    feats = video_features(whole, face, vt)
                    if feats:
                        p.features.update(feats)
                        has_video = True
                    break
    return {"pauses": pauses, "guest_f0_range": f0_range, "has_video": has_video,
            "counts": {k: sum(1 for p in pauses if p.label == k) for k in ("hold", "end", "cut")}}


def _feature_table(pauses: Sequence[Pause], names: Sequence[str],
                   at_least: float = 0.0) -> List[Dict[str, Any]]:
    rows = []
    for n in names:
        h = [p.features[n] for p in pauses if p.label == "hold" and n in p.features
             and p.length >= at_least]
        e = [p.features[n] for p in pauses if p.label == "end" and n in p.features
             and p.length >= at_least]
        if len(h) < 5 or len(e) < 5:
            continue
        # How often a random END scores above a random HOLD on this cue
        # (0.5 = no signal; 1.0 or 0.0 = perfect, in one direction or the other).
        auc = _auc(e, h)
        rows.append({"feature": n, "hold_median": round(statistics.median(h), 3),
                     "end_median": round(statistics.median(e), 3),
                     "n_hold": len(h), "n_end": len(e), "auc": round(auc, 3)})
    return rows


def _auc(pos: Sequence[float], neg: Sequence[float]) -> float:
    allv = sorted([(v, 1) for v in pos] + [(v, 0) for v in neg])
    rank_sum = 0.0
    i = 0
    while i < len(allv):
        j = i
        while j < len(allv) and allv[j][0] == allv[i][0]:
            j += 1
        avg = (i + j + 1) / 2.0
        rank_sum += avg * sum(1 for k in range(i, j) if allv[k][1] == 1)
        i = j
    n1, n0 = len(pos), len(neg)
    return (rank_sum - n1 * (n1 + 1) / 2.0) / max(n1 * n0, 1)


def report(rooms: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
    """The whole answer: the pause distributions, each cue's separation, and
    the two policies' frontiers."""
    pauses: List[Pause] = []
    room_of: List[str] = []
    for rid, r in rooms.items():
        pauses.extend(r["pauses"])
        room_of.extend([rid] * len(r["pauses"]))
    holds = [p.length for p in pauses if p.label == "hold"]
    ends = [p.length for p in pauses if p.label == "end"]
    names = list(VOICE_FEATURES)
    if any("last_word_holds" in p.features for p in pauses):
        names += list(WORD_FEATURES)
    video_rooms = [rid for rid, r in rooms.items() if r.get("has_video")]
    if video_rooms:
        names += list(VIDEO_FEATURES)
    policy, models = cue_policy(pauses, room_of, names)
    return {
        "rooms": {rid: r["counts"] for rid, r in rooms.items()},
        "per_room": {rid: _room_row(r["pauses"]) for rid, r in rooms.items()},
        "video_rooms": video_rooms,
        "hold_pause_sec": _quantiles(holds),
        "end_wait_sec": _quantiles(ends),
        # Each cue, over the pauses a room deciding at one second would face.
        "features": _feature_table(pauses, names, at_least=DECISION_SEC),
        "silence_policy": silence_policy(pauses),
        "adaptive_policy": adaptive_policy({rid: r["pauses"] for rid, r in rooms.items()}),
        "cue_policy": policy,
        "models": models,
    }


#: The moment the cue table is read at: a pause still silent one second in.
DECISION_SEC = 1.0


def _room_row(pauses: Sequence[Pause]) -> Dict[str, Any]:
    holds = [p.length for p in pauses if p.label == "hold"]
    ends = [p for p in pauses if p.label == "end"]
    return {"holds": len(holds), "ends": len(ends),
            "cut": sum(1 for p in pauses if p.label == "cut"),
            "holds_over_2s": sum(1 for h in holds if h > 2.0),
            "holds_over_3s": sum(1 for h in holds if h > 3.0),
            "end_wait_p50": round(statistics.median(p.length for p in ends), 2) if ends else None}


def _quantiles(vals: Sequence[float]) -> Dict[str, Any]:
    if not vals:
        return {"n": 0}
    v = sorted(vals)
    q = lambda f: round(float(np.percentile(v, f)), 2)  # noqa: E731
    return {"n": len(v), "p50": q(50), "p90": q(90), "p95": q(95), "p99": q(99),
            "over_1s": sum(1 for x in v if x > 1.0), "over_2s": sum(1 for x in v if x > 2.0),
            "over_3s": sum(1 for x in v if x > 3.0)}


def to_markdown(rep: Dict[str, Any]) -> str:
    out = ["# When has the guest finished?", ""]
    counts = rep["rooms"]
    out.append(f"{len(counts)} rooms; {sum(c['hold'] for c in counts.values())} pauses where the "
               f"guest went on (holds), {sum(c['end'] for c in counts.values())} where they "
               f"stopped and waited (ends), {sum(c['cut'] for c in counts.values())} set aside "
               f"(someone spoke inside {END_MIN_WAIT_SEC:.0f} s, or the guest came back over them).")
    out.append(f"Rooms with the guest's camera placed: {len(rep['video_rooms'])}.")
    out += ["", "## How long guests pause and then go on", "",
            f"Holds: {json.dumps(rep['hold_pause_sec'])}", "",
            f"Ends (how long the guest had waited when the host spoke): "
            f"{json.dumps(rep['end_wait_sec'])}", "",
            "## Silence alone", "",
            "| wait (s) | holds cut | cut per 100 answers | ends observable |",
            "|---|---|---|---|"]
    for r in rep["silence_policy"]:
        out.append(f"| {r['wait_sec']} | {r['holds_cut']} | {r['cut_per_100_answers']} | "
                   f"{r['ends_observable']} |")
    out += ["", "## The guest's own habit (a wait learned from their pauses so far)", "",
            f"Until {ADAPT_WARMUP} mid-answer pauses are heard the wait is {ADAPT_START_SEC:g} s; "
            f"then a quantile of this guest's own pauses plus a margin, within "
            f"{ADAPT_BOUNDS[0]:g}-{ADAPT_BOUNDS[1]:g} s.", "",
            "| quantile | margin (s) | cut per 100 answers | mean wait (s) | median wait (s) |",
            "|---|---|---|---|---|"]
    for r in rep.get("adaptive_policy") or []:
        out.append(f"| {r['quantile']} | {r['margin_sec']} | {r['cut_per_100_answers']} | "
                   f"{r['mean_wait_sec']} | {r['median_wait_sec']} |")
    out += ["", "## Room by room", "",
            "| room | holds | ends | set aside | holds over 2 s | over 3 s | median wait at an end (s) |",
            "|---|---|---|---|---|---|---|"]
    for rid, r in (rep.get("per_room") or {}).items():
        out.append(f"| {rid} | {r['holds']} | {r['ends']} | {r['cut']} | {r['holds_over_2s']} | "
                   f"{r['holds_over_3s']} | {r['end_wait_p50']} |")
    out += ["", f"## Each cue on its own, at a pause still silent {DECISION_SEC:g} s in", "",
            "AUC: the chance a random end scores above a random hold on this cue "
            "(0.5 is no signal; far from 0.5 either way is a usable cue).", "",
            "| cue | hold median | end median | n hold | n end | AUC |", "|---|---|---|---|---|---|"]
    for r in rep["features"]:
        out.append(f"| {r['feature']} | {r['hold_median']} | {r['end_median']} | {r['n_hold']} | "
                   f"{r['n_end']} | {r['auc']} |")
    rows = sorted(rep["cue_policy"], key=lambda r: (r["slow_sec"], r["fast_sec"], r["theta"]))
    out += ["", "## Cues, then silence (each room scored by a model trained on the others)", ""]
    for fast, m in (rep.get("models") or {}).items():
        out.append(f"- deciding at {fast} s: held-out AUC {m.get('auc')}; weights "
                   f"(standardised, positive = says END) {json.dumps(m.get('weights') or {})}")
    out += ["",
            "| fast (s) | slow (s) | theta | early share | mean wait (s) | cut per 100 | silence-only cut per 100 at slow | ends |",
            "|---|---|---|---|---|---|---|---|"]
    for r in rows:
        out.append(f"| {r['fast_sec']} | {r['slow_sec']} | {r['theta']} | {r['early_share']} | "
                   f"{r['mean_wait_sec']} | {r['cut_per_100_answers']} | "
                   f"{r['silence_only_cut_per_100']} | {r['ends_scored']} |")
    return "\n".join(out) + "\n"


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _runs_from_db(run_ids: Sequence[str], recent: int) -> List[dict]:
    from common import sb_select
    cols = "id,session_kind,duration_sec,grok_session_log,recording_guest_url"
    if run_ids:
        rows = []
        for rid in run_ids:
            rows.extend(sb_select("interview_runs", f"id=eq.{rid}&select={cols}") or [])
        return rows
    return sb_select("interview_runs",
                     f"session_kind=eq.interview&status=eq.completed&duration_sec=gt.600"
                     f"&order=created_at.desc&limit={int(recent)}&select={cols}") or []


def room_sources(run: dict) -> Optional[Tuple[Source, List[Source]]]:
    """The guest's track and everyone else's for one run: the processed
    per-speaker tracks of an interview, or, for a test room (which is never
    post-processed), the two sides of the room's stereo recording."""
    tracks = ((run.get("grok_session_log") or {}).get("tracks") or {})
    processed = tracks.get("processed") or {}
    if processed.get("guest") and processed.get("mira"):
        return processed["guest"], [processed["mira"], processed.get("host") or ""]
    stereo = str(run.get("recording_guest_url") or "")
    if stereo:
        return (stereo, 0), [(stereo, 1)]
    return None


def room_video(run: dict, guest: Source, workdir: Path) -> Optional[Dict[str, Any]]:
    """The run's placed camera takes: ``tracks.video`` when post-production
    built it, else built here from the takes the studio listed (a test room
    is never post-processed), placed against the guest's own track."""
    tracks = ((run.get("grok_session_log") or {}).get("tracks") or {})
    if (tracks.get("video") or {}).get("takes"):
        return tracks["video"]
    from video_take import build_video_track, video_takes
    if not video_takes(run):
        return None
    ref = Path(workdir) / "guest_ref.wav"
    audio = load_audio(guest, sr=16000)
    import wave
    with wave.open(str(ref), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(16000)
        w.writeframes((np.clip(audio, -1, 1) * 32767).astype(np.int16).tobytes())
    # Nothing is uploaded: the analysis reads the assembled takes in place.
    return build_video_track(run, ref, Path(workdir) / "takes",
                             upload=lambda path, _key: str(path), key_for=lambda name: name)


def main(argv: Optional[Sequence[str]] = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--run", action="append", default=[], help="interview_runs id (repeatable)")
    ap.add_argument("--recent", type=int, default=0, help="the last N completed interviews")
    ap.add_argument("--video", action="store_true", help="read the guest's camera takes")
    ap.add_argument("--words", action="store_true",
                    help="transcribe the last words before each pause (faster-whisper)")
    ap.add_argument("--out", default="turn_cues.md")
    ap.add_argument("--json", default="")
    args = ap.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    import tempfile
    whisper = None
    if args.words:
        from faster_whisper import WhisperModel
        whisper = WhisperModel("base.en", device="cpu", compute_type="int8")
    runs = _runs_from_db(args.run, args.recent or (0 if args.run else 20))
    rooms: Dict[str, Dict[str, Any]] = {}
    for run in runs:
        rid = run["id"][:8]
        sources = room_sources(run)
        if not sources:
            logger.info("%s: no tracks to read, skipped", rid)
            continue
        try:
            with tempfile.TemporaryDirectory(prefix="turn_cues_") as tmp:
                video = room_video(run, sources[0], Path(tmp)) if args.video else None
                rooms[rid] = analyse_room(sources[0], sources[1], video=video,
                                          whisper=whisper, words_from_sec=1.0)
            logger.info("%s: %s%s", rid, rooms[rid]["counts"],
                        " (camera placed)" if rooms[rid]["has_video"] else "")
        except Exception as exc:  # noqa: BLE001 — one bad room never stops the report
            logger.warning("%s: %s", rid, exc)
    rep = report(rooms)
    Path(args.out).write_text(to_markdown(rep), encoding="utf-8")
    if args.json:
        Path(args.json).write_text(json.dumps(rep, indent=1), encoding="utf-8")
    print(to_markdown(rep))
    return 0


if __name__ == "__main__":
    sys.exit(main())
