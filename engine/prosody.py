"""Programmatic prosody injection for Grok TTS scripts.

Grok TTS supports a small set of documented speech tags
(`[breath]`, `[pause]`, `[long-pause]`, `<emphasis>...</emphasis>`,
`<whisper>`, `<slow>`, `<soft>`). The May 2026 audit found the LLM
ignores prompt-level instructions to insert these tags — last 56
`_tts.txt` files generated, only 10 had any tags at all.

Rather than depend on LLM compliance, this module deterministically
wraps news-anchor-style emphasis points (currency amounts,
percentages, stock-ticker cashtags) in `<emphasis>...</emphasis>` at
script-save time. Grok consumes the tag and lifts the affected
syllables, producing the cadence a financial / tech news anchor
naturally uses without depending on prompt compliance.

Tags are stripped before reaching any non-TTS surface (blog, RSS,
newsletter, YouTube description) via `engine.utils.strip_speech_tags`.
"""

from __future__ import annotations

import re

# Matches things news anchors emphasize. Order doesn't matter — each
# pattern is mutually exclusive on the kinds of characters it accepts.
#
# - cashtag: $TSLA, $NVDA — 1-5 caps after $ with no trailing letter.
# - money:   $390.82, $1,234, +$5.50 — digits/commas/decimals after $.
# - pct:     2.5%, 100%, 0.5% — digits/decimal followed by %.
#
# All three use negative-lookbehind for word-char to avoid mid-word
# matches (e.g. "USD$5" should not match the $5 portion as a separate
# emphasis), and negative-lookahead for word-char to avoid grabbing
# only a prefix of a longer token.
_PROSODY_RE = re.compile(
    r"""
    (?<!\w)
    (?:
        (?P<cashtag>\$[A-Z]{1,5}(?![A-Za-z]))
      | (?P<money>[+\-−]?\$\d{1,3}(?:,\d{3})*(?:\.\d{1,2})?(?!\w))
      | (?P<pct>\d+(?:\.\d+)?%)
    )
    """,
    re.VERBOSE,
)

# Splits a body of text into ``<emphasis>...</emphasis>`` regions vs.
# everything else so wrap-injection never double-wraps an already-
# emphasised span. Captured groups preserve the wrapped regions intact.
_EMPHASIS_REGION_RE = re.compile(r"(<emphasis>.*?</emphasis>)", re.DOTALL)


def inject_prosody_tags(text: str) -> str:
    """Wrap currency / percentage / cashtag tokens in ``<emphasis>``.

    Idempotent: regions already inside ``<emphasis>...</emphasis>`` are
    left untouched, so calling this twice produces the same output as
    calling it once.

    Empty / falsy input passes through unchanged.
    """
    if not text:
        return text

    parts = _EMPHASIS_REGION_RE.split(text)
    out: list[str] = []
    for part in parts:
        if part.startswith("<emphasis>"):
            out.append(part)
        else:
            out.append(
                _PROSODY_RE.sub(
                    lambda m: f"<emphasis>{m.group(0)}</emphasis>",
                    part,
                )
            )
    return "".join(out)
