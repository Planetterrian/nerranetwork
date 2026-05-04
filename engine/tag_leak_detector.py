"""Tag-leak regression detector for Whisper-transcribed podcast audio.

When Grok TTS fails to consume a speech tag (because the tag isn't in
its documented set, or is malformed, or is wrapped weirdly), the
listener hears the tag as literal spoken text. The May 2026
``<build-intensity>`` regression cost a full network day before the
operator caught it by ear; a regex scan of the Whisper transcript
would have flagged it on the first episode.

This module is the post-pipeline sentinel:

  - ``scan_transcript(path)`` returns a list of ``Leak`` records, one
    per match with line number + matched substring + pattern name.

  - ``count_leaks(path)`` returns just the integer count (used for
    metrics).

  - ``LEAK_PATTERNS`` is the public regex registry; tests pin both
    the patterns themselves AND their behaviour against real
    fixtures.

The detector is **prose-aware** — words like "emphasis" appear
legitimately in news prose ("Tesla's emphasis on robotics") and we
must not flag those. Each pattern includes a positive context guard
that requires the surrounding text to look like a leaked tag (e.g.,
the word ``intensity`` only flags when paired with ``build`` in the
specific tag-shape that Grok produces when it fails).

Reuses the documented Grok tag inventory from ``engine/utils.py`` so
the patterns are kept in sync with the strip-side.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from pathlib import Path
from typing import List, Pattern, Tuple

logger = logging.getLogger(__name__)


@dataclass
class Leak:
    """A single suspected tag-leak detection.

    Attributes
    ----------
    pattern_name:
        Human-readable name from ``LEAK_PATTERNS``. Used for metrics
        + the operator's dashboard ("seen 3 build-intensity leaks
        this week").
    line_no:
        1-indexed line number in the transcript where the match was
        found.
    snippet:
        ~80-char window around the match for operator triage.
    matched:
        The exact substring that triggered the regex.
    """

    pattern_name: str
    line_no: int
    snippet: str
    matched: str


# Each entry: (compiled-regex, human-readable-name).
# Regexes are case-insensitive. The patterns are deliberately
# narrow to avoid false-positives on legitimate prose that happens
# to share keywords with Grok tags.
_RAW_PATTERNS: List[Tuple[str, str]] = [
    # `<build-intensity>` was the network's wrap May 3-4 2026; Grok
    # spoke it as "build intensity" or, in word-corrupted form,
    # "build intended" / "build intending". Whisper sometimes
    # transcribes the same audio as "build intensity" and sometimes
    # as "build intended" depending on the surrounding phonetic
    # context — both shapes caught here.
    (r"\bbuild[ -]inten(?:sity|ded|ding|sified)\b", "build-intensity"),
    # `<long-pause>` / `[long-pause]` — Grok occasionally speaks
    # these as "long pause" (two words) or "long-pause" (hyphenated)
    # when it fails to consume the tag.
    (r"\blong[ -]pause\b", "long-pause"),
    # `[breath]` — the most common bracketed inline tag. Whisper
    # transcribes leaks as the literal word "breath" mid-sentence.
    # Bare-word matches are too noisy ("breathtaking", "breathing")
    # so we look for "breath" surrounded by sentence-boundary
    # punctuation, which is how a leaked bracketed tag would appear.
    (r"(?:^|[.!?]\s+)breath(?:\s+|[.!?]|$)", "breath"),
    # `<emphasis>` — same word-boundary problem. Real prose uses
    # "emphasis on X" / "Tesla's emphasis on robotics" all the time.
    # Only flag when the surrounding shape suggests a tag-leak: the
    # word "emphasis" alone surrounded by sentence boundaries with
    # no preposition (no "on", "of", "in") near it.
    (r"(?:^|[.!?]\s+)emphasis(?:\s*[.!?]|\s+(?!on|of|in|for|over|with))",
     "emphasis"),
    # Stray angle-bracket fragments from any TTS tag that escaped
    # consumption. Pattern: `<word>` or `</word>` left in transcript
    # text (Whisper sometimes preserves them when they're spoken).
    (r"<\s*/?\s*[a-z][a-z-]{2,}\s*>", "stray-angle-bracket-tag"),
    # Stray bracketed-tag fragments. Pattern: `[word]` where word
    # is a known TTS-tag-shape (3+ chars, all lowercase / hyphens)
    # left in the transcript text. Rare, but covers the case where
    # Whisper transcribes both the bracket and the contents.
    (r"\[\s*(?:pause|breath|sigh|gasp|laugh|cry|sniff|kiss|"
     r"throat-clear|long-pause)\s*\]", "stray-bracketed-tag"),
]

LEAK_PATTERNS: List[Tuple[Pattern[str], str]] = [
    (re.compile(rx, flags=re.IGNORECASE), name)
    for rx, name in _RAW_PATTERNS
]


def _snippet_around(text: str, start: int, end: int, width: int = 80) -> str:
    """Return ~width chars of text centered on the match."""
    lo = max(0, start - width // 2)
    hi = min(len(text), end + width // 2)
    snip = text[lo:hi].replace("\n", " ")
    if lo > 0:
        snip = "…" + snip
    if hi < len(text):
        snip = snip + "…"
    return snip.strip()


def scan_transcript(path: Path) -> List[Leak]:
    """Return every suspected tag-leak in ``path``.

    Empty/missing transcript returns an empty list (caller treats as
    a no-op — tag-leak detection is best-effort and never blocks
    the pipeline on the first week).
    """
    if not path.exists():
        logger.debug("Tag-leak detector: transcript missing at %s", path)
        return []

    text = path.read_text(encoding="utf-8", errors="replace")
    if not text.strip():
        return []

    # Compute line offsets once so we can map character match
    # positions back to 1-indexed line numbers.
    line_starts: List[int] = [0]
    for i, ch in enumerate(text):
        if ch == "\n":
            line_starts.append(i + 1)

    def line_of(pos: int) -> int:
        # Binary search would be faster but transcripts are <500
        # lines; linear is fine and clearer.
        for ln, start in enumerate(line_starts):
            if start > pos:
                return ln  # 1-indexed because line_starts[0] is line 1's start
        return len(line_starts)

    leaks: List[Leak] = []
    seen: set = set()  # dedupe overlapping match spans
    for pattern, name in LEAK_PATTERNS:
        for m in pattern.finditer(text):
            key = (m.start(), m.end(), name)
            if key in seen:
                continue
            seen.add(key)
            leaks.append(Leak(
                pattern_name=name,
                line_no=line_of(m.start()),
                snippet=_snippet_around(text, m.start(), m.end()),
                matched=m.group(0).strip(),
            ))
    return leaks


def count_leaks(path: Path) -> int:
    """Return just the leak count — convenience wrapper for metrics."""
    return len(scan_transcript(path))


def summarize_leaks(leaks: List[Leak]) -> str:
    """Format a leak list for log output / metrics."""
    if not leaks:
        return "no tag leaks detected"
    by_name: dict = {}
    for leak in leaks:
        by_name.setdefault(leak.pattern_name, []).append(leak)
    parts = []
    for name in sorted(by_name):
        cnt = len(by_name[name])
        first = by_name[name][0]
        parts.append(
            f"{name}={cnt} (line {first.line_no}: {first.matched!r})"
        )
    return "; ".join(parts)
