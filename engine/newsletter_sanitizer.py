"""Output sanitizer for newsletter bodies.

Two layers of defense against LLM scaffold leaks ending up in subscribers'
inboxes (the May 2 daily emails shipped with literal labels like
``**HOOK:**``, ``**Date:**``, ``**Theme:**``, ``ЗАГОЛОВОК:``,
``**The Surprising Truth:**`` and box-drawing horizontal rules).

Public API:

  - ``scrub_scaffold(text)`` — soft layer; strips every known label /
    box-rule / production-note artefact from the rendered body before it
    reaches the email wrapper. Idempotent.

  - ``find_scaffold_leaks(text) -> list[str]`` — hard layer; returns the
    list of patterns that survived ``scrub_scaffold``. Caller raises
    ``ScaffoldLeakError`` to block-send.

  - ``ScaffoldLeakError`` — raised by ``send_show_newsletter`` when leaks
    are detected after scrubbing. Operator surfaces this via the run
    log so a human can fix the prompt or extend the blocklist.

The patterns are also exposed as ``SCAFFOLD_PATTERNS`` so tests can
assert coverage when new labels appear in the LLM output.
"""

from __future__ import annotations

import logging
import re
from typing import List, Pattern, Tuple

logger = logging.getLogger(__name__)


class ScaffoldLeakError(RuntimeError):
    """Raised when the post-scrub body still contains LLM scaffold.

    Attributes
    ----------
    leaks:
        List of human-readable descriptions of what survived. Includes
        the matched substring (truncated to 80 chars) so the operator
        can locate the offender in the digest source.
    """

    def __init__(self, leaks: List[str]) -> None:
        self.leaks = leaks
        joined = "\n  - ".join(leaks)
        super().__init__(
            f"Newsletter body contains LLM scaffold leaks "
            f"(blocking send):\n  - {joined}"
        )


# ---------------------------------------------------------------------------
# Patterns
# ---------------------------------------------------------------------------

# Each entry: (compiled-regex, replacement-string, human-readable-name).
# Replacement defaults to "" — patterns matched against the whole label
# line including the trailing newline, so removing the line outright
# usually works. Some labels are part of an editorial section header
# we want to keep but strip the "label:" prefix from — those use a
# replacement that preserves the content after the colon.
#
# Order matters: more specific patterns run first so a generic
# fallback doesn't eat a structured one.

# Bracketed production-notes blocks — strip wholesale. Several Russian
# prompts end production notes with a heading line that's inadvertently
# emitted ("[PRODUCTION NOTES — DO NOT READ ALOUD]" ... continues into
# the script body even though the whole block was meant to be silent).
_RAW_RULES: List[Tuple[str, str, str]] = [
    # Inline bracketed production-notes paragraphs the LLM sometimes
    # echoes back after the closing bracket. Catches both English and
    # Russian variants; the closing token is `[END PRODUCTION NOTES]`.
    (
        r"\[PRODUCTION NOTES[^\]]*\][\s\S]*?\[END PRODUCTION NOTES\]\s*",
        "",
        "production-notes block",
    ),
    # Tesla / generic single-line labels at the top of a daily digest.
    # Match the whole line including a trailing newline.
    (r"(?im)^\s*\*\*HOOK:\*\*\s*", "", "**HOOK:**"),
    (r"(?im)^\s*\*\*Date:\*\*[^\n]*\n?", "", "**Date:** line"),
    (r"(?im)^\s*\*\*Theme:\*\*[^\n]*\n?", "", "**Theme:** line"),
    (r"(?im)^\s*\*\*Episode:\*\*[^\n]*\n?", "", "**Episode:** line"),
    # Russian (Cyrillic) header label — same role as **HOOK:**
    (r"(?im)^\s*\*\*ЗАГОЛОВОК:\*\*\s*", "", "**ЗАГОЛОВОК:**"),
    (r"(?im)^\s*\*\*ТЕМА:\*\*\s*", "", "**ТЕМА:**"),
    # Tesla First Principles — keep the section but strip the labeled
    # bullets, leaving prose paragraphs.
    (
        r"(?im)^\s*\*\*The Surprising Truth:\*\*\s*",
        "",
        "**The Surprising Truth:**",
    ),
    (
        r"(?im)^\s*\*\*The Fundamental Question:\*\*\s*",
        "",
        "**The Fundamental Question:**",
    ),
    (r"(?im)^\s*\*\*The Data Says:\*\*\s*", "", "**The Data Says:**"),
    (r"(?im)^\s*\*\*The Tesla Approach:\*\*\s*", "", "**The Tesla Approach:**"),
    (r"(?im)^\s*\*\*The Bottom Line:\*\*\s*", "", "**The Bottom Line:**"),
    # Prompt-template instruction headers occasionally echoed verbatim.
    # These are the worst kind of leak: pure prompt scaffold the LLM
    # mistakenly mirrored into the output. Strip the entire line
    # (including any trailing instruction text on the same line).
    (
        r"(?im)^\s*\*\*TOPIC SELECTION:\*\*[^\n]*\n?",
        "",
        "**TOPIC SELECTION:** ... line",
    ),
    (
        r"(?im)^\s*\*\*TOPIC FRESHNESS\b[^\n]*\n?",
        "",
        "**TOPIC FRESHNESS:** ... line",
    ),
    (
        r"(?im)^\s*\*\*WHAT TO SKIP\b[^\n]*\n?",
        "",
        "**WHAT TO SKIP:** ... line",
    ),
    (
        r"(?im)^\s*\*\*LENGTH TARGET\b[^\n]*\n?",
        "",
        "**LENGTH TARGET:** ... line",
    ),
    # Tesla Short Spot ``**Catchy Title: <real title>...**`` — the LLM
    # mirrored the prompt's placeholder ``Catchy Title:`` instead of
    # replacing it with an actual title. Strip the placeholder prefix
    # but keep the real title that follows. Capture group 1 is the
    # rest of the bold line (the title + dateline + source).
    (
        r"(?im)\*\*\s*Catchy Title:\s*([^*\n]+?)\s*\*\*",
        r"**\1**",
        "**Catchy Title: ...**",
    ),
    # M&AB / Russian-language-show labels.
    (r"(?im)^\s*\*\*What's Cool Today:\*\*\s*", "", "**What's Cool Today:**"),
    (r"(?im)^\s*\*\*What's today's hot story:\*\*\s*", "", "**What's today's hot story:**"),
    (
        r"(?im)^\s*\*\*Vocabulary List \([^)]+\):\*\*\s*",
        "",
        "**Vocabulary List (..):**",
    ),
    (r"(?im)^\s*\*\*Memory hook:\*\*\s*", "", "**Memory hook:**"),
    # Stray tagline echoed by the X-takeover prompt.
    (
        r"(?im)^\s*🎙️\s*Tesla X Takeover\s*-\s*What's breaking in the Tesla world today!\s*\n?",
        "",
        "Tesla X Takeover subtitle",
    ),
    # First-principles intro tagline that Grok still echoes on TST.
    (
        r"(?im)^\s*🧠\s*Tesla First Principles\s*-\s*Cutting Through the Noise\s*\n?",
        "",
        "First Principles subtitle",
    ),
    # Source attribution leaks. The fetcher attaches a real URL but the
    # LLM occasionally outputs literal placeholder text instead.
    (r"(?im)^\s*Source:\s*General concept\s*\n?", "", "Source: General concept"),
    (r"\(full URL from pre-fetched:\s*[^)]*\)", "", "(full URL from pre-fetched: …)"),
    (r"\(full URL from pre[ -]?fetched\s*[^)]*\)", "", "(full URL from pre-fetched: variant)"),
    # NOTE: box-drawing horizontal rules (━━━ / ─── / ═══) are NOT
    # scrubbed here — they're converted to proper ``<hr>`` separators
    # by ``engine.newsletter_body.replace_box_rules_with_hr`` in the
    # body-transform stage. Stripping them here would leave the
    # transform with nothing to convert. The pattern-coverage test
    # in ``tests/test_newsletter_sanitizer.py`` keeps the name in
    # the required-list so a future regression to "strip them
    # entirely" is caught.
]

SCAFFOLD_PATTERNS: List[Tuple[Pattern[str], str, str]] = [
    (re.compile(pat), repl, name) for pat, repl, name in _RAW_RULES
]


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def scrub_scaffold(text: str) -> str:
    """Apply every blocklist substitution in order, return cleaned text.

    Idempotent — running this twice produces the same result as once.
    Empty / None input is a no-op.
    """
    if not text:
        return text
    out = text
    for pat, repl, _name in SCAFFOLD_PATTERNS:
        out = pat.sub(repl, out)
    # Collapse the 3+ blank lines a removed-line scrub can leave behind.
    out = re.sub(r"\n{4,}", "\n\n\n", out)
    return out


def find_scaffold_leaks(text: str) -> List[str]:
    """Return descriptions of every blocklist pattern still present.

    Used as the hard send-block: the operator runs ``scrub_scaffold``
    first (which removes everything we know how to fix automatically),
    then this function as a tripwire that catches anything which slipped
    through. A leak after scrubbing means the prompt regressed or a new
    label appeared — extend ``SCAFFOLD_PATTERNS`` and re-run.
    """
    if not text:
        return []
    leaks: List[str] = []
    for pat, _repl, name in SCAFFOLD_PATTERNS:
        m = pat.search(text)
        if m:
            sample = m.group(0).strip().replace("\n", " ")
            if len(sample) > 80:
                sample = sample[:77] + "..."
            leaks.append(f"{name}: {sample!r}")
    # Generic catch-all: any line that's literally `**Anything Capitalized:**`
    # at the start of a line is suspicious. We keep this *after* the
    # specific-label pass so legit prose like "**Tesla:** A car company"
    # mid-sentence doesn't trip — the start-of-line anchor + the rest of
    # the line being *only* the label is the giveaway.
    bare_label = re.compile(r"(?m)^\s*\*\*[A-Z][\w '-]{2,40}:\*\*\s*$")
    for m in bare_label.finditer(text):
        sample = m.group(0).strip()
        if len(sample) > 80:
            sample = sample[:77] + "..."
        leaks.append(f"bare-label line: {sample!r}")
    return leaks


def assert_clean(text: str) -> None:
    """Raise ``ScaffoldLeakError`` if any leaks remain after scrubbing.

    Convenience wrapper: scrub first, then check. The caller passes the
    *post-scrub* text to ``send_newsletter`` so the email goes out clean
    even if the assertion is ever silenced.
    """
    leaks = find_scaffold_leaks(scrub_scaffold(text))
    if leaks:
        raise ScaffoldLeakError(leaks)
