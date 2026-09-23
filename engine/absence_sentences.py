"""Absence sentences: sentences whose only content is that a fact is missing.

"No energization date was stated." "Current reporting supplies no release
date." "Alphabet has not yet released additional information." Every one of
the Sep 2026 new shows' first episodes carried them — AI Chips Ep1 closed 8
of its 10 digest items on one, MAG 7 Ep1's script spent 9 of 66 sentences
on them — although all four digest prompts banned the shape outright after
the dry runs. An instruction the model breaks is enforced in code (CLAUDE.md,
DP Pod's Network-pick rotation), so this module removes them.

Deliberately narrow. It matches only the DISCLOSURE shape — a detail that was
not given, stated, released, disclosed. It never matches the health shows'
required caveats ("No regulatory body has approved…", "…has not been tested
in people", "…remains unknown"): what science has not established is
content; what a press release left out is not. Opt-in per show
(``absence_sentence_filter: true``); every other show is untouched.
"""

from __future__ import annotations

import re
from typing import Tuple

_VERBS = (
    r"disclosed|provided|released|specified|detailed|given|listed|stated|"
    r"announced|mentioned|named|shared|supplied|outlined|included|made public|"
    r"offered|published|revealed|itemi[sz]ed|quantified|broken down"
)

_PATTERNS = [
    # "No energization date was stated." / "No further details … were provided"
    re.compile(
        r"^(?:but\s+|however,?\s+|yet\s+)?(?:no|neither)\b[^.!?]{0,120}?\b"
        r"(?:was|were|has been|have been|is|are|had been)\s+(?:yet\s+)?"
        r"(?:" + _VERBS + r")\b",
        re.IGNORECASE,
    ),
    # "Alphabet has not yet released additional information." /
    # "The company did not disclose the price."
    re.compile(
        r"\b(?:did|does|do|has|have|had)\s+not\s+(?:yet\s+)?"
        r"(?:disclose|provide|specify|detail|give|list|state|announce|mention|"
        r"name|release|share|supply|outline|reveal|quantify|put a number on)\b",
        re.IGNORECASE,
    ),
    # "Regulatory review status has not been detailed in the report."
    re.compile(
        r"\b(?:has|have|had|was|were|is|are)\s+not\s+(?:yet\s+)?(?:been\s+)?"
        r"(?:" + _VERBS + r")\b",
        re.IGNORECASE,
    ),
    # "Current reporting supplies no release date."
    re.compile(
        r"\b(?:supplies|supplied|provides|provided|gives|gave|includes|included|"
        r"carries|carried|offers|offered|contains|contained|lists|listed)\s+no\b",
        re.IGNORECASE,
    ),
    # "No energization date appears in the release." / "No new capabilities
    # received mention alongside the update."
    re.compile(
        r"^(?:no|neither)\b[^.!?]{0,120}?\b(?:appears?|appeared|received\s+mention|"
        r"were\s+mentioned|accompanied)\b",
        re.IGNORECASE,
    ),
    # "No release date or specific design elements have been confirmed in
    # the current reporting." — "confirmed" only when the sentence names the
    # document that failed to confirm it.
    re.compile(
        r"^(?:no|neither)\b[^.!?]{0,120}?\b(?:has|have|had)\s+been\s+confirmed\b"
        r"[^.!?]{0,60}\b(?:report|reporting|announcement|release|statement|"
        r"filing|article|coverage)\b",
        re.IGNORECASE,
    ),
    # "Terms remain undisclosed." (never "unknown"/"unclear": science's open
    # questions are content on the health shows)
    re.compile(r"\bremains?\s+(?:undisclosed|unspecified|unannounced)\b", re.IGNORECASE),
]

# Lines that are structure, not prose.
_SKIP_LINE = re.compile(r"^\s*(?:#|>|\*\*[^*]+\*\*\s*$|[-*]\s|\d+[.)]\s|```|Source:)")
_SENT_SPLIT = re.compile(r"(?<=[.!?])\s+(?=[A-Z\"“‘'(\[])")


# A sentence whose only content is WHERE something was read, naming a
# spoken domain (Peptides Ep1: "The source for these statements appears in
# reports linked from x dot com."). The run's spoken-URL tripwire only
# counts these on every show; on the opt-in shows they are removed.
_SPOKEN_DOMAIN_RE = re.compile(
    r"\b[a-z0-9-]+ dot (?:com|org|net|io|gov|ca|co|uk|ai)\b", re.IGNORECASE)
_ATTRIBUTION_RE = re.compile(
    r"\b(?:source|sources|sourced|link|links|linked|appears?|posted|according to|"
    r"reported (?:on|by|at)|read (?:on|at))\b", re.IGNORECASE)


def is_attribution_only_sentence(sentence: str) -> bool:
    """Never the network's own address: the closings and promos point
    listeners at nerranetwork dot com on purpose."""
    s = sentence.strip()
    domains = [m.group(0).lower() for m in _SPOKEN_DOMAIN_RE.finditer(s)]
    if not domains or all(d.startswith("nerranetwork") for d in domains):
        return False
    return bool(_ATTRIBUTION_RE.search(s))


def is_absence_sentence(sentence: str) -> bool:
    s = sentence.strip()
    if not s or s.lower().startswith("source:"):
        return False
    return any(p.search(s) for p in _PATTERNS) or is_attribution_only_sentence(s)


def strip_absence_sentences(text: str) -> Tuple[str, int]:
    """Remove absence sentences from prose lines. Returns (text, removed).

    Headings, list items, blockquotes, fenced blocks and ``Source:`` lines
    are left alone. A line whose every prose sentence matches keeps its
    first sentence, so no paragraph is ever emptied.
    """
    if not text:
        return text, 0
    out = []
    removed = 0
    in_fence = False
    for line in text.split("\n"):
        if line.lstrip().startswith("```"):
            in_fence = not in_fence
            out.append(line)
            continue
        if in_fence or not line.strip() or _SKIP_LINE.match(line):
            out.append(line)
            continue
        lead = line[: len(line) - len(line.lstrip())]
        parts = _SENT_SPLIT.split(line.strip())
        keep = [p for p in parts if not is_absence_sentence(p)]
        prose_kept = [p for p in keep if not p.lower().startswith("source:")]
        if not prose_kept:
            # Every sentence was an absence sentence. A one-sentence line
            # (a script line) goes; a multi-sentence item keeps its first.
            if len(parts) == 1:
                removed += 1
                continue
            keep = [parts[0]] + [p for p in keep if p.lower().startswith("source:")]
        removed += len(parts) - len(keep)
        out.append(lead + " ".join(keep))
    result = "\n".join(out)
    result = re.sub(r"\n{3,}", "\n\n", result)
    return result, removed


# An item heading with nothing under it (MAG 7 Ep1: "**Microsoft (MSFT):**
# The Information" and then the next section). Same opt-in flag: it is the
# same failure — the model filling a slot it had nothing for.
_ITEM_HEADING_RE = re.compile(r"^\s*\*\*[^*\n]{2,160}\*\*[^.!?\n]{0,80}$")
_SECTION_RE = re.compile(r"^\s*#{1,6}\s")


def drop_empty_items(text: str) -> Tuple[str, int]:
    """Remove bold item headings that carry no body before the next heading."""
    if not text:
        return text, 0
    lines = text.split("\n")
    keep = [True] * len(lines)
    removed = 0
    for i, line in enumerate(lines):
        if not _ITEM_HEADING_RE.match(line):
            continue
        j = i + 1
        while j < len(lines) and not lines[j].strip():
            j += 1
        if (j >= len(lines) or _SECTION_RE.match(lines[j])
                or _ITEM_HEADING_RE.match(lines[j])):
            keep[i] = False
            removed += 1
    out = "\n".join(line for line, k in zip(lines, keep) if k)
    return re.sub(r"\n{3,}", "\n\n", out), removed
