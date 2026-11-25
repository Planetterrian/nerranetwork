"""Keep a script inside one voice call by shortening its Also Today run.

Nov 25 2026 (operator pick 4a). Omni View's script ran 14,190 to 19,524
characters on eight straight episodes against ``tts.max_chars`` 14,000, so
synthesis split into chunks and the network's ``<fast>`` delivery wrap was
dropped every day (landmine #17: the wrap is single-call only). The prompt
had stated a ceiling since Nov 14 and the model wrote past it.

The spoken Also Today run is the one part of a news script made of
independent one-sentence items: the Nov 24 episode spoke 21 of them, 540
words. This module removes whole items from the END of that run, in code,
until the text fits one call. It never touches a story, the deep dive, the
teaser or the closing, never cuts inside a sentence, and never leaves fewer
than ``keep_min`` items. A script it cannot bring under the limit is returned
unchanged (the wrap drops as before and the metric says so): a shorter
episode that still loses its speed would be a cut for nothing.

The digest is untouched, so every item stays on the page and in the feed.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Callable, List, Optional, Tuple

#: The spoken deep dive's first sentence carries this phrase by prompt rule
#: (podcast-app chapters key off it), so the Also Today run ends just before.
ANCHOR_PHRASE = "to really understand"

#: Items the run keeps whatever the length.
KEEP_MIN = 4

_ALSO_TODAY_RE = re.compile(r"^#{2,3}\s+Also Today\s*$", re.I | re.M)
_NEXT_HEADING_RE = re.compile(r"^#{2,3}\s+\S", re.M)
_SENT_RE = re.compile(r"\S.*?(?:[.!?][\"”’)\]]*(?=\s|$)|$)", re.S)
_WORD_RE = re.compile(r"[^\W\d_]{4,}", re.U)

_STOP = frozenset(
    """about after again against also among another around because been before
    being between both could does down during each even ever every first from
    have having here into just last less like made make many more most much
    must near next once only other over said same says should since some such
    than that their them then there these they this those through today told
    under until very were what when where which while will with would year
    years week weeks month months percent million billion thousand hundred
    people government minister president officials brief source""".split()
)


@dataclass
class FitResult:
    script: str
    outcome: str  # fits | trimmed | no_run | cannot
    removed: int = 0
    run_items: int = 0
    chars_before: int = 0
    chars_after: int = 0
    removed_sentences: List[str] = field(default_factory=list)


def _tokens(text: str) -> set:
    return {w for w in (m.group(0).lower() for m in _WORD_RE.finditer(text))
            if w not in _STOP}


def also_today_items(digest: str) -> List[set]:
    """Salient words of each Also Today item in the digest."""
    m = _ALSO_TODAY_RE.search(digest or "")
    if not m:
        return []
    rest = digest[m.end():]
    nxt = _NEXT_HEADING_RE.search(rest)
    block = rest[:nxt.start()] if nxt else rest
    block = re.sub(r"```.*?```", "", block, flags=re.S)
    items = []
    for chunk in re.split(r"\n\s*\n", block):
        chunk = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", chunk)
        chunk = re.sub(r"https?://\S+", "", chunk)
        toks = _tokens(chunk)
        if len(toks) >= 3:
            items.append(toks)
    return items


def _spans(script: str) -> List[Tuple[int, int]]:
    """(start, end) of every sentence, line by line, in script order."""
    out = []
    pos = 0
    for line in script.split("\n"):
        for m in _SENT_RE.finditer(line):
            if m.group(0).strip():
                out.append((pos + m.start(), pos + m.end()))
        pos += len(line) + 1
    return out


def find_run(script: str, digest: str) -> List[Tuple[int, int]]:
    """Sentence spans of the spoken Also Today run, in order.

    The run is the unbroken stretch of sentences just before the deep dive's
    opening sentence in which each sentence shares at least two salient words
    with one of the digest's Also Today items.
    """
    items = also_today_items(digest)
    if not items:
        return []
    spans = _spans(script)
    anchor = next((i for i, (a, b) in enumerate(spans)
                   if ANCHOR_PHRASE in script[a:b].lower()), None)
    if anchor is None:
        return []
    run = []
    for i in range(anchor - 1, -1, -1):
        toks = _tokens(script[spans[i][0]:spans[i][1]])
        if max((len(toks & it) for it in items), default=0) < 2:
            break
        run.append(spans[i])
    run.reverse()
    return run


def _remove(script: str, span: Tuple[int, int]) -> str:
    a, b = span
    # Take the separating space with the sentence; an emptied line goes too.
    while a > 0 and script[a - 1] in " \t":
        a -= 1
    out = script[:a] + script[b:]
    return re.sub(r"\n[ \t]*\n(?:[ \t]*\n)+", "\n\n", out)


def fit_single_call(
    script: str,
    digest: str,
    limit: int,
    *,
    keep_min: int = KEEP_MIN,
    measure: Optional[Callable[[str], int]] = None,
) -> FitResult:
    """Shorten the Also Today run until ``measure(script) <= limit``."""
    measure = measure or len
    before = measure(script)
    if limit <= 0 or before <= limit:
        return FitResult(script, "fits", chars_before=before, chars_after=before)
    run = find_run(script, digest)
    if len(run) <= keep_min:
        return FitResult(script, "no_run", run_items=len(run),
                         chars_before=before, chars_after=before)
    out = script
    removed: List[str] = []
    # Later spans first, so the earlier offsets stay valid.
    for span in reversed(run[keep_min:]):
        removed.append(script[span[0]:span[1]].strip())
        out = _remove(out, span)
        if measure(out) <= limit:
            return FitResult(out, "trimmed", removed=len(removed),
                             run_items=len(run), chars_before=before,
                             chars_after=measure(out),
                             removed_sentences=removed)
    return FitResult(script, "cannot", run_items=len(run),
                     chars_before=before, chars_after=before)
