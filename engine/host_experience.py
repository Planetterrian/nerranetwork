"""Host-experience lines are not content (Oct 30 2026, Offshore North).

From Ep006 the Offshore North prompts REQUIRED one line a week drawn from
the host's own life (the airline flight deck, a wing foil on Georgian Bay,
Lasers and Hobies, family charters), named in the brief as "Dan's lens". A
listener review of Ep011 ("The RORC Transatlantic pairs weather-routing
decisions across the North Atlantic with the same pressure systems I read
from the flight deck.") found them too brief and without context: they
confused people. The prompts no longer ask for them, and the network rule
for an instruction a model may keep following is code: this module removes
such a sentence from the digest and the script.

A sentence is a host-experience line when it speaks in the first person or
names Dan AND mentions one of his frames, or when it is the brief's
"Dan's lens" label. A ``Source:`` tail on the same line is kept, so an
item never loses its citation. Opt-in per show (``host_experience_filter``).
"""

from __future__ import annotations

import re
from typing import Tuple

_PERSON_RE = re.compile(r"\b(?:I|I'm|I've|I'd|I'll|my|me|myself|Dan|Dan's)\b")
_FRAME_RE = re.compile(
    r"flight[- ]deck|cockpit|\b737\b|\bairline\b|\bpilot|\bI fly\b|\bI(?:'ve)? flown\b|"
    r"\bflying over\b|wing[- ]?foil|Georgian Bay|\bHobie|\bLasers?\b|bareboat|\bcharters?\b",
    re.IGNORECASE)
_LABEL_RE = re.compile(r"^\W*Dan(?:'s|’s)\s+lens\b", re.IGNORECASE)
_SENT_RE = re.compile(r"(?<=[.!?])\s+(?=\S)")
_SOURCE_RE = re.compile(r"\s*\**Source:\**\s", re.IGNORECASE)


def is_host_experience_sentence(sentence: str) -> bool:
    s = (sentence or "").strip()
    if not s:
        return False
    if _LABEL_RE.search(s):
        return True
    return bool(_PERSON_RE.search(s) and _FRAME_RE.search(s))


def _split_source(line: str) -> Tuple[str, str]:
    m = _SOURCE_RE.search(line)
    if not m:
        return line, ""
    return line[:m.start()], line[m.start():].strip()


def strip_host_experience(text: str) -> Tuple[str, int]:
    """Remove host-experience sentences. Returns ``(text, removed)``.

    Headings and fenced blocks are left alone. A line left with nothing but
    its ``Source:`` tail keeps the tail; a line left with nothing is dropped
    along with one blank line after it.
    """
    if not text:
        return text, 0
    out: list = []
    removed = 0
    in_fence = False
    skip_blank = False
    for line in text.split("\n"):
        if line.lstrip().startswith("```"):
            in_fence = not in_fence
            out.append(line)
            skip_blank = False
            continue
        if skip_blank and not line.strip():
            skip_blank = False
            continue
        skip_blank = False
        if in_fence or not line.strip() or line.lstrip().startswith("#"):
            out.append(line)
            continue
        indent = line[:len(line) - len(line.lstrip())]
        body, source = _split_source(line.strip())
        sentences = [s for s in _SENT_RE.split(body.strip()) if s]
        kept = [s for s in sentences if not is_host_experience_sentence(s)]
        if len(kept) == len(sentences):
            out.append(line)
            continue
        removed += len(sentences) - len(kept)
        new = " ".join(kept + ([source] if source else [])).strip()
        if new:
            out.append(indent + new)
        else:
            skip_blank = True
    return "\n".join(out), removed
