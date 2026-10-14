"""The hook's story is item one (Oct 14 2026, data-side).

The digest prompt writes the hook from the most important story and the
numbered list in fetch order, so the story the cold open sold sat at item
7 on Fascinating Frontiers Ep216, item 5 on Tesla Ep629 and item 2-4 on
three of eight Planetterrian episodes; the script tells the items in order,
so the body opened on a different story from the hook (the Oct 3 rule,
``script_hook_leads_body_pct``) and an outside review read Ep221's headline
as not matching its opening story. :func:`promote_hook_item` moves the
numbered item that shares the most salient words with the hook to the top
of its section and renumbers; nothing is rewritten, dropped or added. Opt-in
per show (``hook_item_first: true``); runs after the overlap dedupe, before
the validator, on every regeneration.

Threshold: the best item must share ``MIN_SHARED_TOKENS`` salient words with
the hook and beat item one by ``PROMOTION_MARGIN``. A digest whose hook matches nothing
strongly enough is returned unchanged — the hook may be an essay's story or
a synthesis, and a wrong promotion is worse than none.
"""

from __future__ import annotations

import re
from typing import List, Tuple

from engine.digest_overlap import (
    _BOLD_RE,
    _NUMBERED_RE,
    _renumber,
    _salient_tokens,
    _split_blocks,
)

#: Salient words the promoted item must share with the hook.
MIN_SHARED_TOKENS = 3
#: ...and by how many it must beat item one — a near tie is left alone.
PROMOTION_MARGIN = 2

_HOOK_RE = re.compile(r"^\s*>\s*\*\*(.+?)\*\*\s*$", re.MULTILINE)


def digest_hook(digest: str) -> str:
    """The blockquoted hook sentence, or ``""``."""
    m = _HOOK_RE.search(digest or "")
    return m.group(1).strip() if m else ""


def _item_tokens(block: str) -> frozenset:
    """Salient words of an item's bold headline plus its body (Source lines
    excluded); the headline is counted twice so a headline match outranks a
    passing mention in another item's body."""
    title = ""
    m = _BOLD_RE.search(block)
    if m:
        title = m.group(1)
    body = "\n".join(
        ln for ln in block.split("\n")
        if not re.match(r"\s*Source(?:/Post)?\s*:", ln, re.IGNORECASE)
    )
    return _salient_tokens(title) | _salient_tokens(_BOLD_RE.sub(" ", body))


def _first_item_run(blocks: List[str]) -> Tuple[int, int]:
    """``(start, end)`` of the first run of two or more numbered items, in
    block indices; ``(-1, -1)`` when the digest has none."""
    i = 0
    while i < len(blocks):
        if _NUMBERED_RE.match(blocks[i]) and _BOLD_RE.search(blocks[i]):
            j = i
            while j < len(blocks) and _NUMBERED_RE.match(blocks[j]) and _BOLD_RE.search(blocks[j]):
                j += 1
            if j - i >= 2:
                return i, j
            i = j
            continue
        i += 1
    return -1, -1


def promote_hook_item(digest: str, *, min_shared: int = MIN_SHARED_TOKENS) -> Tuple[str, int]:
    """Return ``(digest, moved_from)`` — *moved_from* is the 1-based position
    the hook's item held before promotion, 0 when nothing moved."""
    hook = digest_hook(digest)
    if not hook or not digest:
        return digest, 0
    hook_tokens = _salient_tokens(hook)
    if not hook_tokens:
        return digest, 0
    blocks = _split_blocks(digest)
    start, end = _first_item_run(blocks)
    if start < 0:
        return digest, 0
    scores = [len(_item_tokens(b) & hook_tokens) for b in blocks[start:end]]
    # Tie-break on the headline: an item whose TITLE carries the hook's
    # words outranks one that mentions them in passing.
    title_hits = []
    for b in blocks[start:end]:
        m = _BOLD_RE.search(b)
        title_hits.append(len(_salient_tokens(m.group(1)) & hook_tokens) if m else 0)
    best = max(range(len(scores)), key=lambda k: (scores[k], title_hits[k], -k))
    if (best == 0 or scores[best] < min_shared
            or scores[best] < scores[0] + PROMOTION_MARGIN):
        return digest, 0
    item = blocks.pop(start + best)
    blocks.insert(start, item)
    return "\n\n".join(_renumber(blocks)), best + 1
