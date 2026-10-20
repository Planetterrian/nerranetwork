"""Speech tags where a new story starts (Oct 20 2026, operator-directed).

Measured on Oct 19 2026 against a human newscast (NPR's hourly cast, Up
First) with the same pitch analysis: a human reader does not pause longer
between stories than between sentences (0.5-0.7 s either way), and marks
the change with the voice instead — a modest lift opening an ordinary
sentence (+2 to +8 Hz) and a much bigger one opening a new story (+34 Hz),
with a firmer landing on the story's last words. Grok TTS on the custom
voice lifts ~+20 Hz at EVERY sentence and exactly the same at a new story,
and lands identically at a story end and a sentence end — so nothing in
the audio told a listener a story had changed, and the Oct 13/14 fixes
(a longer pause, then music under it) treated the symptom. The operator
heard the longer pause as forced and the music as interludes; both are
retired in favour of marks the voice itself makes.

This module puts Grok's own speech tags at the boundaries
:mod:`engine.story_breaks` already finds — the same boundaries the audio
beat uses — BEFORE synthesis, so the committed ``*_tts.txt`` is what was
spoken:

* an inline tag (default ``[breath]``, a tag the delivery spec already
  sanctions and the model already writes) opens the first line of each new
  story — an audible breath is what a reader does at a story change;
* optionally a wrapping tag (``tts.story_tag_close``, e.g. ``low`` for
  ``<low>...</low>``) around the LAST sentence of the story before it, so
  the voice lands. It is empty by default: which pitch tag Grok consumes
  on this voice is read from the TTS-tags probe (Actions "Probe TTS tags")
  and set in ``shows/_defaults.yaml``, never assumed from documentation —
  an unknown tag is spoken aloud (M&A Ep045 "Fast.", UC Ep001 "Build
  intensity.").

Rules that bind: boundaries are found on the TAG-STRIPPED script (a tag at
a line's opening would otherwise defeat the Whisper anchor that places the
beat); a line already opening on a tag is left alone; a closing sentence
longer than :data:`MAX_CLOSE_SENTENCE_WORDS` or already carrying a tag is
not wrapped; dialogue shows never get tags here (their turns are the
boundaries). Everything downstream that reads the spoken script for
matching (story_breaks, chapter alignment, the spoken-text gate) strips
tags first.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import List, Tuple

from engine.story_breaks import story_boundary_lines
from engine.utils import strip_speech_tags

#: The tag that opens a new story's first line. ``[breath]`` is in the
#: sanctioned set (``engine.intros._SANCTIONED_TAGS``).
DEFAULT_OPEN_TAG = "[breath]"
#: Wrapping-tag NAME (without brackets) for the previous story's last
#: sentence; "" = none. Set from probe evidence, see the module docstring.
DEFAULT_CLOSE_TAG = ""
#: A closing sentence longer than this is left unwrapped — a pitch tag over
#: forty words is a register change, not a landing.
MAX_CLOSE_SENTENCE_WORDS = 40

_LEADING_TAG_RE = re.compile(r"^\s*(?:\[[a-z-]+\]|<[a-z-]+>)", re.IGNORECASE)
_SENTENCE_END_RE = re.compile(r"(?<=[.!?…])[\"”»)]?\s+(?=\S)")
_TAG_NAME_RE = re.compile(r"^[a-z][a-z-]{1,24}$")


@dataclass
class TagResult:
    script: str
    boundaries: int
    opened: int
    closed: int


def _nonempty_indices(raw_lines: List[str]) -> Tuple[List[int], str]:
    """Indices of the raw lines that survive tag-stripping as non-empty, and
    the stripped script built from them — so ``story_boundary_lines``'s
    indices map back onto the original text line for line."""
    idx: List[int] = []
    clean: List[str] = []
    for i, line in enumerate(raw_lines):
        stripped = strip_speech_tags(line).strip()
        if stripped:
            idx.append(i)
            clean.append(stripped)
    return idx, "\n".join(clean)


def last_sentence_span(line: str) -> Tuple[int, int]:
    """``(start, end)`` of the last sentence in *line* (end excludes trailing
    whitespace). A one-sentence line is the whole line."""
    body = line.rstrip()
    end = len(body)
    starts = [m.end() for m in _SENTENCE_END_RE.finditer(body)]
    start = starts[-1] if starts else len(body) - len(body.lstrip())
    return start, end


def _wrap_last_sentence(line: str, tag: str) -> Tuple[str, bool]:
    start, end = last_sentence_span(line)
    sentence = line[start:end]
    if not sentence.strip() or "<" in sentence or "[" in sentence:
        return line, False
    if len(sentence.split()) > MAX_CLOSE_SENTENCE_WORDS:
        return line, False
    return f"{line[:start]}<{tag}>{sentence}</{tag}>{line[end:]}", True


def tag_story_boundaries(script: str, digest_md: str, *,
                         open_tag: str = DEFAULT_OPEN_TAG,
                         close_tag: str = DEFAULT_CLOSE_TAG) -> TagResult:
    """Return *script* with speech tags at every story boundary.

    *open_tag* is inserted verbatim before the first line of each new story
    (``""`` = none). *close_tag* is a tag NAME wrapped around the last
    sentence of the preceding story (``""`` = none). Boundaries come from
    :func:`engine.story_breaks.story_boundary_lines` on the tag-stripped
    script, so a script the pipeline has already tagged is tagged once.
    """
    if not script or not script.strip():
        return TagResult(script, 0, 0, 0)
    open_tag = (open_tag or "").strip()
    close_tag = (close_tag or "").strip().strip("<>/")
    if close_tag and not _TAG_NAME_RE.match(close_tag):
        raise ValueError(f"story_tag_close must be a bare tag name, got {close_tag!r}")
    raw = script.split("\n")
    nonempty, clean = _nonempty_indices(raw)
    boundaries = [k for k in story_boundary_lines(clean, digest_md or "") if 0 < k < len(nonempty)]
    opened = closed = 0
    for k in boundaries:
        line_i = nonempty[k]
        prev_i = nonempty[k - 1]
        if open_tag and not _LEADING_TAG_RE.match(raw[line_i]):
            indent = raw[line_i][: len(raw[line_i]) - len(raw[line_i].lstrip())]
            raw[line_i] = f"{indent}{open_tag} {raw[line_i].lstrip()}"
            opened += 1
        if close_tag:
            raw[prev_i], did = _wrap_last_sentence(raw[prev_i], close_tag)
            closed += int(did)
    return TagResult("\n".join(raw), len(boundaries), opened, closed)
