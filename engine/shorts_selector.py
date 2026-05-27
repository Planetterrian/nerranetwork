"""Pick the most engaging 55-second window from a podcast episode for
the YouTube Shorts clip.

The legacy Shorts pipeline starts the clip at the first voice frame
(``shorts_start_mode: voice``) — fine for a long-form viewer but
weak for the Shorts surface, where the first 1–2 seconds decide
whether the algorithm gives the clip a chance. Educational /
news-style podcasts usually open with a setup ("Today on the show…",
"Welcome to…") and bury the actual hook 20–60 seconds in.

This module scans the Whisper transcript (segments + per-word
timestamps) and picks a starting timestamp that lands on a high-
engagement beat: a numeric reveal, a surprise framing ("here's the
kicker"), a "you won't believe" hook, etc. Pure heuristic — no LLM
call, no per-episode cost, deterministic and unit-testable.

When no segment scores above the noise threshold, the function falls
back to the legacy ``voice_intro_delay`` start so the operator never
ends up with a worse Shorts clip than the legacy pipeline produced.
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Tuple

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Scoring signals
# ---------------------------------------------------------------------------

# Phrases that signal a hook punchline / surprise framing. Each match
# adds +5 to the segment score. Word-boundary checked.
_HOOK_PHRASES = (
    "the wild part", "the surprising thing", "here's the kicker",
    "what's interesting", "but wait", "the catch is", "the irony",
    "picture this", "imagine if", "imagine that", "here's why",
    "the kicker is", "the twist is", "what's wild", "what's crazy",
    "incredibly", "remarkably", "shockingly", "and the kicker",
    "here's the thing", "what's even", "the real story",
    "here's what", "it turns out", "as it turns out",
    "the punchline", "the bigger story", "no one is talking",
    "nobody saw this coming", "you won't believe",
    "the reason is", "the real reason",
)

# Question framings (often hook openers) — +3 each.
_QUESTION_HOOKS = (
    "why does", "why are", "why is", "how does",
    "what if", "what's the deal", "what's going on",
    "how much", "how many", "what would",
    "could it be", "is it possible", "are we",
)

# Boilerplate openers we explicitly want to avoid starting on. Each
# match is -8 (large penalty — we want to escape these even if they
# happen to contain a numeric).
_BORING_OPENERS = (
    "welcome to", "thanks for tuning in", "thanks for listening",
    "in today's episode", "today on", "today's episode",
    "i'm your host", "your host", "hey everyone", "hey folks",
    "good morning", "good evening", "happy", "as always",
    "you're listening to",
)

# Superlatives — modest signal, +1 each.
_SUPERLATIVES = (
    "biggest", "smallest", "fastest", "slowest", "largest",
    "highest", "lowest", "best", "worst", "most", "least",
    "first ever", "the first", "the only", "all-time",
    "record", "unprecedented",
)

# Numeric patterns — concrete numbers signal high-information content
# that lands well in Shorts. +2 per match.
_NUMERIC_PATTERNS = (
    re.compile(r"\$\d"),                                    # $X
    re.compile(r"\b\d+(?:\.\d+)?\s*%"),                     # X%, X.X%
    re.compile(r"\b\d+(?:\.\d+)?\s*(million|billion|trillion)\b", re.I),
    re.compile(r"\b\d+\s*x\b", re.I),                       # 10x
    re.compile(r"\b\d{4}\b"),                               # years / large numbers
)


# ---------------------------------------------------------------------------
# Data shape
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ScoredWindow:
    """One candidate Shorts window with its engagement score."""
    start_seconds: float  # FINAL-AUDIO seconds (whisper + voice_intro_delay)
    end_seconds: float
    score: float
    # Short text label for debugging — first ~80 chars of the opening
    # segment, surfaced in logs / metrics so the operator can scan the
    # selection without re-running the pipeline.
    opening_text: str = ""


# ---------------------------------------------------------------------------
# Pure scoring helpers
# ---------------------------------------------------------------------------


def score_text(text: str) -> float:
    """Return an engagement score for a single segment's text.

    Pure function, no I/O. Score is unbounded above; ``0.0`` means
    "neutral / no signal", negative scores mean "actively boring"
    (boilerplate openers). Caller decides what threshold counts as
    "worth picking over the legacy start".
    """
    if not text:
        return 0.0
    low = text.lower()
    score = 0.0
    for phrase in _HOOK_PHRASES:
        if phrase in low:
            score += 5.0
    for phrase in _QUESTION_HOOKS:
        if low.startswith(phrase) or f". {phrase}" in low or f", {phrase}" in low:
            score += 3.0
    for phrase in _BORING_OPENERS:
        if phrase in low:
            score -= 8.0
    for phrase in _SUPERLATIVES:
        # Word-boundary check to avoid e.g. "interest" matching "first ever".
        if re.search(rf"\b{re.escape(phrase)}\b", low):
            score += 1.0
    for pat in _NUMERIC_PATTERNS:
        score += 2.0 * len(pat.findall(text))
    return score


def _segment_score(seg: dict) -> Tuple[float, str]:
    text = (seg.get("text") or "").strip()
    return score_text(text), text


def _window_score(
    segments: List[dict],
    start: int,
    *,
    window_duration: float,
    audio_offset: float,
) -> float:
    """Score the window that starts at segments[start].

    The opening segment carries the most weight (first impression in
    Shorts), the next 5 s after it carry 0.6×, and the tail carries
    0.3×. This makes the algorithm prefer windows whose HOOK lands at
    the start of the clip, not 30 s in.
    """
    if not segments or start >= len(segments):
        return 0.0
    window_start_whisper = float(segments[start].get("start") or 0.0)
    window_end_whisper = window_start_whisper + window_duration
    total = 0.0
    for i in range(start, len(segments)):
        seg = segments[i]
        seg_start = float(seg.get("start") or 0.0)
        seg_end = float(seg.get("end") or seg_start)
        if seg_start >= window_end_whisper:
            break
        if seg_end <= window_start_whisper:
            continue
        # Position weight: 1.0 for the first 1.5 s, 0.6 for the next
        # 5 s, 0.3 for everything else inside the window.
        offset_in_window = seg_start - window_start_whisper
        if offset_in_window <= 1.5:
            weight = 1.0
        elif offset_in_window <= 6.5:
            weight = 0.6
        else:
            weight = 0.3
        score, _text = _segment_score(seg)
        total += weight * score
    return total


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def score_candidates(
    transcript_path: Path,
    *,
    audio_offset: float,
    audio_duration: float,
    window_duration: float = 55.0,
    min_start_final: float = 0.0,
    max_late_pct: float = 0.85,
) -> List[ScoredWindow]:
    """Score every segment-anchored window in the transcript.

    Parameters
    ----------
    transcript_path:
        faster-whisper JSON output (``segments`` array with ``start`` /
        ``end`` / ``text``; ``words`` optional and ignored here).
    audio_offset:
        Seconds of music intro the final mix prepends before the
        voice starts. Whisper timestamps are voice-only; final-audio
        timestamps need this added on top. Same role as
        ``audio_offset_seconds`` in ``engine.captions``.
    audio_duration:
        Length of the final mixed MP3 in seconds. Used to reject
        candidate windows that would run past the end of the audio.
    window_duration:
        Shorts clip length in seconds (default 55).
    min_start_final:
        Earliest acceptable start in final-audio seconds. Usually
        equal to ``audio_offset`` (don't start during the music
        intro).
    max_late_pct:
        Reject candidates that would start past this fraction of the
        episode (default: skip the last 15 %). Stops the algorithm
        from picking a great hook that lands in the outro.

    Returns a list of ``ScoredWindow`` sorted by descending score —
    callers usually want index 0.
    """
    try:
        data = json.loads(transcript_path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError) as exc:
        logger.warning(
            "Smart Shorts selector: transcript unreadable (%s) — "
            "falling back. (%s)", transcript_path, exc,
        )
        return []
    segments = data.get("segments", []) if isinstance(data, dict) else []
    if not segments:
        return []

    # Pre-filter: segments must have a numeric start, must be in the
    # acceptable window of the audio, and must carry text.
    valid: List[dict] = []
    for s in segments:
        if not isinstance(s, dict):
            continue
        text = (s.get("text") or "").strip()
        if not text:
            continue
        try:
            seg_start = float(s.get("start") or 0.0)
        except (TypeError, ValueError):
            continue
        final_start = seg_start + audio_offset
        if final_start < min_start_final:
            continue
        if audio_duration > 0 and (
            final_start + window_duration > audio_duration
            or final_start > audio_duration * max_late_pct
        ):
            continue
        valid.append(s)

    if not valid:
        return []

    out: List[ScoredWindow] = []
    for i, seg in enumerate(valid):
        # The window's index in the FULL segments list — _window_score
        # walks forward from there to score overlap.
        try:
            full_idx = segments.index(seg)
        except ValueError:
            full_idx = i
        score = _window_score(
            segments, full_idx,
            window_duration=window_duration,
            audio_offset=audio_offset,
        )
        seg_start_whisper = float(seg.get("start") or 0.0)
        start_final = seg_start_whisper + audio_offset
        text = (seg.get("text") or "").strip()
        out.append(ScoredWindow(
            start_seconds=start_final,
            end_seconds=start_final + window_duration,
            score=score,
            opening_text=text[:80],
        ))
    out.sort(key=lambda w: w.score, reverse=True)
    return out


def pick_engaging_window(
    transcript_path: Path,
    *,
    audio_offset: float,
    audio_duration: float,
    window_duration: float = 55.0,
    min_start_final: Optional[float] = None,
    min_score_threshold: float = 5.0,
) -> Optional[ScoredWindow]:
    """Return the single best ``ScoredWindow``, or ``None`` if no
    candidate exceeds ``min_score_threshold``.

    The threshold exists because heuristic scoring noise on a generic
    episode (no concrete numbers, no kicker phrases, no superlatives)
    can produce a top score of 0–3 that's no better than the legacy
    voice-start pick. In that case ``None`` tells the caller to
    fall back to the legacy pipeline.

    ``min_start_final`` defaults to ``audio_offset`` (don't start
    during the music intro). Pass a higher value to skip past, e.g.,
    a 4 s AI-generated content disclosure that always opens the
    episode.
    """
    floor = audio_offset if min_start_final is None else min_start_final
    candidates = score_candidates(
        transcript_path,
        audio_offset=audio_offset,
        audio_duration=audio_duration,
        window_duration=window_duration,
        min_start_final=floor,
    )
    if not candidates:
        logger.info(
            "Smart Shorts selector: no scorable candidates in %s",
            transcript_path.name,
        )
        return None
    best = candidates[0]
    if best.score < min_score_threshold:
        logger.info(
            "Smart Shorts selector: best score %.1f below threshold %.1f "
            "(opening: %r) — falling back to legacy start",
            best.score, min_score_threshold, best.opening_text,
        )
        return None
    logger.info(
        "Smart Shorts selector: picked start=%.1fs score=%.1f "
        "(opening: %r)",
        best.start_seconds, best.score, best.opening_text,
    )
    return best


def pick_top_n_engaging_windows(
    transcript_path: Path,
    *,
    n: int,
    audio_offset: float,
    audio_duration: float,
    window_duration: float = 55.0,
    min_start_final: Optional[float] = None,
    min_score_threshold: float = 5.0,
    min_gap_seconds: float = 10.0,
) -> List[ScoredWindow]:
    """Return up to ``n`` non-overlapping windows ranked by score.

    Powers the "multiple Shorts per episode" pipeline. Each window's
    start must be at least ``min_gap_seconds`` AFTER the previous
    picked window's end, so the N Shorts cover genuinely different
    moments of the episode rather than near-duplicates.

    Selection is greedy-by-score: take the top-scoring candidate
    first, then filter remaining candidates to those that don't
    overlap (with the gap), then take the next-highest, repeat.
    This produces the N most engaging windows that are also
    temporally distinct.

    Behaviour at the edges:

    * Fewer than ``n`` candidates above ``min_score_threshold`` →
      returns whatever it found (possibly empty). Caller decides
      whether to fall back to legacy voice-start for the missing
      slots.
    * No candidates at all → returns ``[]``.
    * ``n <= 0`` → returns ``[]`` (defensive — caller bug).
    * Transcript unreadable → returns ``[]`` (logged in score_candidates).

    Returned list is sorted by ``start_seconds`` ascending so the
    Shorts publish flow uploads them in chronological order
    (Short 1 from earlier in the episode, Short 2 later) — a small
    but real engagement signal for viewers who watch multiple
    Shorts in a row.
    """
    if n <= 0:
        return []
    floor = audio_offset if min_start_final is None else min_start_final
    candidates = score_candidates(
        transcript_path,
        audio_offset=audio_offset,
        audio_duration=audio_duration,
        window_duration=window_duration,
        min_start_final=floor,
    )
    if not candidates:
        logger.info(
            "Smart Shorts selector (top-%d): no scorable candidates in %s",
            n, transcript_path.name,
        )
        return []

    picked: List[ScoredWindow] = []
    # ``candidates`` is already sorted by score descending. Walk it
    # greedily and accept any that doesn't overlap a previously
    # picked window.
    for cand in candidates:
        if cand.score < min_score_threshold:
            break  # remaining are all below threshold too
        if not _overlaps_any(cand, picked, min_gap_seconds):
            picked.append(cand)
            if len(picked) >= n:
                break

    # Re-sort by start time so the caller can iterate chronologically.
    picked.sort(key=lambda w: w.start_seconds)
    if picked:
        logger.info(
            "Smart Shorts selector (top-%d): picked %d window(s): %s",
            n, len(picked),
            ", ".join(
                f"{w.start_seconds:.1f}s(score={w.score:.1f})" for w in picked
            ),
        )
    else:
        logger.info(
            "Smart Shorts selector (top-%d): no candidate above threshold "
            "%.1f in %s",
            n, min_score_threshold, transcript_path.name,
        )
    return picked


def _overlaps_any(
    candidate: ScoredWindow,
    others: List[ScoredWindow],
    min_gap_seconds: float,
) -> bool:
    """True when ``candidate`` overlaps with any window in ``others``
    OR sits within ``min_gap_seconds`` of one. Two windows are
    "non-overlapping with gap" iff ``other.end + gap <= candidate.start``
    OR ``candidate.end + gap <= other.start``."""
    for other in others:
        if (
            candidate.start_seconds < other.end_seconds + min_gap_seconds
            and other.start_seconds < candidate.end_seconds + min_gap_seconds
        ):
            return True
    return False
