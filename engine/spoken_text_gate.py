"""Spoken-text gate: what the TTS engine SPOKE must be the script we SENT.

Tesla Shorts Time Ep605 (2026-09-14) opened with forty-five seconds of
Grok TTS reading its own text-normalizer's reasoning aloud — "One thing,
the input has line breaks, preserve them. The text ends abruptly ...
Rules. Do not convert at sign in code ... So the output should be the
entire text unchanged" — in place of the hook, the identity line and
the first two sentences. The saved ``_tts.txt`` was clean; the defect
was injected server-side, between our request and the audio. Every
check the pipeline ran on that episode passed: the tag-leak detector
looks for a fixed registry of tag WORDS, the opt-in transcription
validator (off everywhere) scores the WHOLE episode (the leak replaced
~50 of 1,083 words, so it would have read ~0.9 and passed), and nothing
compared the opening of the audio with the opening of the script. The
episode shipped to RSS, both YouTube Shorts (the hook-first Short IS
the leaked passage), the Apple video feed and Nerra Daily Ep025.

This module is the structural check that was missing. It is
deterministic (``difflib`` only, no model call, no network) and it
reads the Whisper transcript the pipeline already produces for every
episode, so it costs nothing per episode.

Two measures, either one fails the gate:

* ``opening_match`` — the share of the first ``opening_words`` spoken
  words that are found, in order, inside the script's opening. A leak
  of the Ep605 shape scores ~0.1; every healthy English episode since
  June 2026 scores >= 0.5 (calibrated on 1,137 committed pairs).
* ``longest_unmatched_run`` — after aligning the whole transcript
  against the whole script, the longest run of spoken words that the
  script does not contain (single matched words such as "the" do not
  break a run). Ep605's leak measures 61; the legitimate maximum since
  June is 22 (benchmark numbers Whisper writes as digits), so the
  threshold of 40 has roughly 2x margin on both sides.

Two Whisper artifacts are filtered BEFORE scoring, because a Whisper
failure must never block an episode:

* a segment whose word rate is implausible for speech (Models & Agents
  Ep140 carried 70 words inside a 2.3 s segment — a hallucination over
  a stretch Whisper could not decode; the audio was fine);
* a repetition loop (Modern Investing Ep162's transcript wrote
  "S&P-S&P-S&P-…" forty times at a segment boundary where the audio
  says "the S&P 500 closed at"; collapsed to one copy).

Russian-language shows run the gate in SHADOW mode: Whisper transcribes
Привет, Русский!'s English halves as Cyrillic sound-alikes and sometimes
translates Финансы Просто into English, so the measures are not
trustworthy there yet. The runner records the numbers and warns; it
never blocks on them.
"""

from __future__ import annotations

import difflib
import json
import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable, List, Optional, Sequence, Tuple

logger = logging.getLogger(__name__)

# Thresholds — calibrated 2026-09-14 on every committed English episode
# since 2026-06-01 (n=1,137). See ``scripts/audit_spoken_text.py`` to
# re-run the calibration before moving any of them.
DEFAULT_OPENING_WORDS = 30
DEFAULT_MIN_OPENING_MATCH = 0.5
DEFAULT_MAX_UNMATCHED_RUN = 40
# A single matched word inside a foreign passage ("hello", "the") does
# not end the passage. Two consecutive matched words do.
UNMATCHED_RUN_BRIDGE = 1
# Whisper hallucination filter: real speech on this network runs
# 2-3.5 words/s; the Ep140 artifact ran 30 words/s.
MAX_WORDS_PER_SECOND = 6.0
# Repetition-loop filter: an n-gram (n <= 3) repeated more than this
# many times back to back is collapsed to one copy before scoring.
MAX_LOOP_REPEATS = 3

GATE_MODES = ("enforce", "shadow", "off")

_TAG_RE = re.compile(r"<[^>]+>|\[[^\]]+\]")
_NON_WORD_RE = re.compile(r"[^\w\s']", flags=re.UNICODE)


def normalize_words(text: str) -> List[str]:
    """Lower-case word tokens with speech tags and punctuation removed.

    Both sides of every comparison go through this, so casing,
    punctuation and the ``<fast>`` / ``[pause]`` tags never count as
    differences. Digits are kept: the script spells most numbers out
    and Whisper writes digits, which produces SHORT mismatches the
    thresholds tolerate.
    """
    if not text:
        return []
    text = _TAG_RE.sub(" ", text.lower())
    text = _NON_WORD_RE.sub(" ", text)
    return text.split()


def filter_segments(segments: Iterable[dict],
                    max_words_per_second: float = MAX_WORDS_PER_SECOND,
                    ) -> Tuple[List[str], int]:
    """Return the transcript's words with hallucinated segments dropped.

    A segment is dropped when its word rate exceeds
    ``max_words_per_second`` — impossible for speech, characteristic of
    Whisper emitting text over audio it could not decode. Returns
    ``(words, dropped_count)``.
    """
    words: List[str] = []
    dropped = 0
    for seg in segments:
        seg_words = normalize_words(str(seg.get("text", "")))
        if not seg_words:
            continue
        try:
            span = float(seg.get("end", 0.0)) - float(seg.get("start", 0.0))
        except (TypeError, ValueError):
            span = 0.0
        if span > 0 and len(seg_words) / span > max_words_per_second:
            dropped += 1
            continue
        words.extend(seg_words)
    return words, dropped


def collapse_loops(words: Sequence[str],
                   max_repeats: int = MAX_LOOP_REPEATS,
                   ) -> Tuple[List[str], int]:
    """Collapse back-to-back repetition of 1-3 word n-grams.

    ``s p s p s p s p …`` (Whisper's rendering of its own "S&P-S&P-…"
    loop) becomes ``s p``. Returns ``(words, loops_collapsed)`` where the
    count is the number of loops found, not the words removed. No
    script on the network legitimately repeats a phrase more than
    ``max_repeats`` times in a row.
    """
    out: List[str] = list(words)
    collapsed = 0
    for n in (1, 2, 3):
        i = 0
        result: List[str] = []
        while i < len(out):
            gram = out[i:i + n]
            if len(gram) < n:
                result.extend(gram)
                break
            repeats = 1
            j = i + n
            while out[j:j + n] == gram:
                repeats += 1
                j += n
            if repeats > max_repeats:
                result.extend(gram)
                collapsed += 1
                i = j
            else:
                result.append(out[i])
                i += 1
        out = result
    return out, collapsed


def opening_match(script_words: Sequence[str], spoken_words: Sequence[str],
                  opening_words: int = DEFAULT_OPENING_WORDS) -> float:
    """Share of the first ``opening_words`` spoken words found, in order,
    in the script's opening (the first ``1.5 * opening_words`` script
    words, so a slightly slower Whisper start still aligns)."""
    spoken = list(spoken_words[:opening_words])
    if not spoken:
        return 0.0
    script = list(script_words[:int(opening_words * 1.5)])
    matcher = difflib.SequenceMatcher(None, script, spoken, autojunk=False)
    matched = sum(block.size for block in matcher.get_matching_blocks())
    return round(matched / len(spoken), 3)


def longest_unmatched_run(script_words: Sequence[str],
                          spoken_words: Sequence[str],
                          bridge: int = UNMATCHED_RUN_BRIDGE,
                          ) -> Tuple[int, str, float]:
    """Longest run of spoken words the script does not contain.

    Returns ``(run_length, snippet, position)`` where ``position`` is
    the run's start as a fraction of the transcript (0.0 = the opening).
    A matched stretch of at most ``bridge`` words inside a run does not
    end it.
    """
    a = list(script_words)
    b = list(spoken_words)
    if not b:
        return 0, "", 0.0
    matcher = difflib.SequenceMatcher(None, a, b, autojunk=False)
    best = 0
    best_start = 0
    cur = 0
    cur_start: Optional[int] = None
    for tag, _i1, _i2, j1, j2 in matcher.get_opcodes():
        if tag == "equal":
            if (j2 - j1) <= bridge and cur > 0:
                cur += j2 - j1
                continue
            if cur > best:
                best, best_start = cur, cur_start or 0
            cur, cur_start = 0, None
        else:
            if cur_start is None:
                cur_start = j1
            cur += j2 - j1
    if cur > best:
        best, best_start = cur, cur_start or 0
    snippet = " ".join(b[best_start:best_start + 14])
    return best, snippet, round(best_start / len(b), 3)


@dataclass(frozen=True)
class SpokenTextReport:
    """Result of one gate evaluation. ``passed`` is the verdict; the
    numbers are recorded as per-episode metrics either way."""

    passed: bool
    reasons: Tuple[str, ...]
    opening_match: float
    longest_unmatched_run: int
    unmatched_snippet: str
    unmatched_position: float
    script_words: int
    spoken_words: int
    segments_dropped: int
    loops_collapsed: int
    thresholds: dict = field(default_factory=dict)

    def summary(self) -> str:
        verdict = "PASS" if self.passed else "FAIL"
        parts = [
            f"spoken-text gate {verdict}",
            f"opening_match={self.opening_match:.2f}",
            f"longest_unmatched_run={self.longest_unmatched_run}",
        ]
        if self.reasons:
            parts.append("reasons=" + ",".join(self.reasons))
        if self.longest_unmatched_run:
            parts.append(
                f"at {self.unmatched_position:.0%}: {self.unmatched_snippet!r}"
            )
        if self.segments_dropped or self.loops_collapsed:
            parts.append(
                f"whisper_artifacts(dropped_segments={self.segments_dropped},"
                f" loops={self.loops_collapsed})"
            )
        return " ".join(parts)


def check_spoken_text(
    script_text: str,
    *,
    segments: Optional[Iterable[dict]] = None,
    transcript_text: Optional[str] = None,
    opening_words: int = DEFAULT_OPENING_WORDS,
    min_opening_match: float = DEFAULT_MIN_OPENING_MATCH,
    max_unmatched_run: int = DEFAULT_MAX_UNMATCHED_RUN,
) -> SpokenTextReport:
    """Compare what was spoken (``segments`` from the Whisper JSON, or a
    plain ``transcript_text``) with the ``script_text`` sent to TTS.

    Prefer ``segments``: only they carry the timings the hallucination
    filter needs. ``transcript_text`` is the fallback for callers that
    only have the ``.txt`` file.
    """
    script_words = normalize_words(script_text)
    if segments is not None:
        spoken, dropped = filter_segments(segments)
    else:
        spoken, dropped = normalize_words(transcript_text or ""), 0
    spoken, loops = collapse_loops(spoken)

    reasons: List[str] = []
    if not script_words:
        reasons.append("empty_script")
    if not spoken:
        reasons.append("empty_transcript")

    opening = opening_match(script_words, spoken, opening_words) if spoken else 0.0
    run, snippet, position = longest_unmatched_run(script_words, spoken)

    if spoken and script_words:
        if opening < min_opening_match:
            reasons.append("opening_mismatch")
        if run >= max_unmatched_run:
            reasons.append("foreign_passage")

    return SpokenTextReport(
        passed=not reasons,
        reasons=tuple(reasons),
        opening_match=opening,
        longest_unmatched_run=run,
        unmatched_snippet=snippet,
        unmatched_position=position,
        script_words=len(script_words),
        spoken_words=len(spoken),
        segments_dropped=dropped,
        loops_collapsed=loops,
        thresholds={
            "opening_words": opening_words,
            "min_opening_match": min_opening_match,
            "max_unmatched_run": max_unmatched_run,
        },
    )


def load_segments(json_path: Path) -> Optional[List[dict]]:
    """Segments from a committed ``*_transcript.json`` (None if unreadable)."""
    try:
        data = json.loads(Path(json_path).read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        logger.debug("spoken-text gate: cannot read %s: %s", json_path, exc)
        return None
    segs = data.get("segments") if isinstance(data, dict) else None
    return segs if isinstance(segs, list) else None


def check_transcript_files(script_text: str, json_path: Path,
                           txt_path: Optional[Path] = None, **thresholds,
                           ) -> SpokenTextReport:
    """Convenience for the runner and the audit script: JSON segments
    when present, the plain transcript otherwise."""
    segments = load_segments(json_path)
    if segments is not None:
        return check_spoken_text(script_text, segments=segments, **thresholds)
    text = ""
    if txt_path is not None:
        try:
            text = Path(txt_path).read_text(encoding="utf-8", errors="replace")
        except OSError:
            text = ""
    return check_spoken_text(script_text, transcript_text=text, **thresholds)


def resolve_gate_mode(configured: str, transcript_language: str) -> str:
    """The mode the runner actually applies.

    ``enforce`` downgrades to ``shadow`` for any transcript language other
    than English: the measures are not calibrated there (see the module
    docstring), and a gate that blocks on its own instrument's noise
    would cost a Russian show its episode. ``off`` and ``shadow`` pass
    through unchanged; an unknown value is treated as ``shadow`` so a
    YAML typo can neither disable nor weaponize the gate.
    """
    mode = (configured or "").strip().lower()
    if mode not in GATE_MODES:
        logger.warning(
            "spoken_text_gate: unknown mode %r — running in shadow", configured,
        )
        mode = "shadow"
    if mode == "enforce" and (transcript_language or "en").lower() != "en":
        logger.info(
            "spoken_text_gate: transcript language %r is not calibrated — "
            "enforce downgraded to shadow", transcript_language,
        )
        mode = "shadow"
    return mode
