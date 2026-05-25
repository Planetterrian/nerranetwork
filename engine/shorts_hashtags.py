"""Extract YouTube-style hashtags from a podcast hook line.

YouTube treats the **first 3** hashtags in a video description as
"topic tags" rendered above the title as clickable links — the
biggest discovery lever on Shorts after the title itself. Beyond
the first 3 they still index for search but stop being visible
above the fold; YouTube ignores all hashtags entirely past the
first 15.

This module is a pure-function parser over the episode hook (the
one-line topic of the day) + the show's network tag list. No
LLM call, no per-episode cost. Heuristics:

* Multi-word Title-Case phrases ("Tesla Cybercab", "Modern
  Investing Techniques") collapse to a single hashtag
  (``#TeslaCybercab``) — the entity reads as one search target.
* Single-word capitalised proper nouns ("Tesla", "Cybercab")
  become hashtags too, after the multi-word forms claim their
  spots so we don't double-rank the same entity.
* Short all-caps acronyms (``AI``, ``TSLA``, ``GPT``) survive
  verbatim; they're high-value search tokens.
* Show-level tags from the YAML (``keywords``) are blended in at
  the tail so each Short carries the show's evergreen discovery
  set even when the hook is generic.

The output is ranked: multi-word entities first (highest signal),
then single-word capitalised entities, then acronyms, then show
keywords. The caller decides how many to splice into the
description (typically the top 5 — 3 for YouTube's visible row
+ 2 buffer for de-dupe collisions).
"""

from __future__ import annotations

import logging
import re
from typing import Iterable, List, Optional, Sequence

logger = logging.getLogger(__name__)


# Tokens we never hashtag — sentence connectives, "common" capitalised
# words that lead a sentence ("The", "And") aren't entity signals.
_STOPWORDS = frozenset((
    "The", "A", "An", "And", "Or", "But", "If", "Then", "So",
    "This", "That", "These", "Those", "Here", "There",
    "Today", "Tomorrow", "Yesterday", "Now", "Soon",
    "Why", "How", "What", "When", "Where", "Who", "Which",
    "Is", "Are", "Was", "Were", "Be", "Been", "Being",
    "Has", "Have", "Had", "Do", "Does", "Did",
    "Just", "Even", "Also", "Only", "Still", "More", "Less",
    "May", "June", "July", "August", "September", "October",
    "November", "December", "January", "February", "March", "April",
    "Monday", "Tuesday", "Wednesday", "Thursday", "Friday",
    "Saturday", "Sunday",
))

# Acronyms shorter than 2 chars are noise (single-letter capitals
# show up in "I" / "U" framings). Longer than 6 is usually a
# noun-cased token, not an acronym.
_MIN_ACRONYM_LEN = 2
_MAX_ACRONYM_LEN = 6

# Hashtag character class — YouTube accepts letters / digits /
# underscores after the ``#``. Anything else terminates the tag.
_HASHTAG_BODY_RE = re.compile(r"[A-Za-z0-9_]+")


# ---------------------------------------------------------------------------
# Token extraction
# ---------------------------------------------------------------------------


def _clean_for_tag(token: str) -> str:
    """Return the alphanumeric body of a token suitable for use after
    a ``#``. Strips punctuation, internal whitespace, hyphens."""
    parts = _HASHTAG_BODY_RE.findall(token)
    return "".join(parts)


def _is_acronym(token: str) -> bool:
    body = _clean_for_tag(token)
    if not body or len(body) < _MIN_ACRONYM_LEN or len(body) > _MAX_ACRONYM_LEN:
        return False
    # All-caps with at least one letter (drop pure-digit tokens like
    # "2026" which are years, not acronyms).
    return body.isupper() and any(c.isalpha() for c in body)


def _is_proper_noun(token: str) -> bool:
    body = _clean_for_tag(token)
    if not body or not body[0].isupper():
        return False
    if body in _STOPWORDS:
        return False
    # Title-case with at least one lower-case letter (drop full-caps
    # tokens — those go through the acronym branch).
    return any(c.islower() for c in body)


def _extract_multi_word_entities(hook: str) -> List[str]:
    """Find consecutive runs of Title-Case words (e.g. "Tesla Cybercab",
    "Modern Investing Techniques"). Returns the entities preserving
    document order; duplicates dropped on first appearance."""
    if not hook:
        return []
    tokens = hook.split()
    out: List[str] = []
    seen: set = set()
    i = 0
    while i < len(tokens):
        if _is_proper_noun(tokens[i]):
            run = [tokens[i]]
            j = i + 1
            while j < len(tokens) and _is_proper_noun(tokens[j]):
                run.append(tokens[j])
                j += 1
            if len(run) >= 2:
                joined = "".join(_clean_for_tag(t) for t in run)
                key = joined.lower()
                if joined and key not in seen:
                    seen.add(key)
                    out.append(joined)
            i = j
        else:
            i += 1
    return out


def _extract_single_proper_nouns(hook: str) -> List[str]:
    if not hook:
        return []
    out: List[str] = []
    seen: set = set()
    for token in hook.split():
        if not _is_proper_noun(token):
            continue
        body = _clean_for_tag(token)
        if not body:
            continue
        key = body.lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(body)
    return out


def _extract_acronyms(hook: str) -> List[str]:
    if not hook:
        return []
    out: List[str] = []
    seen: set = set()
    for token in hook.split():
        if not _is_acronym(token):
            continue
        body = _clean_for_tag(token)
        if not body:
            continue
        key = body.lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(body)
    return out


def _normalise_show_keywords(raw: Iterable[str]) -> List[str]:
    """Convert YAML keywords ("tesla cybertruck", "ai agents") into
    hashtag bodies ("TeslaCybertruck", "AiAgents"). Lowercases then
    Title-cases each word and concatenates so a single keyword
    becomes a single tag."""
    out: List[str] = []
    seen: set = set()
    for kw in raw:
        if not isinstance(kw, str):
            continue
        words = [w for w in re.split(r"[\s_-]+", kw.strip()) if w]
        if not words:
            continue
        body = "".join(w[:1].upper() + w[1:].lower() for w in words)
        body = _clean_for_tag(body)
        if not body:
            continue
        key = body.lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(body)
    return out


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def extract_hashtags(
    hook: str,
    *,
    show_keywords: Optional[Sequence[str]] = None,
    max_hashtags: int = 5,
) -> List[str]:
    """Return up to ``max_hashtags`` hashtag bodies (no leading ``#``)
    ranked by signal strength: multi-word entities first, then
    single-word proper nouns, then acronyms, then show keywords.

    De-duplication is **case-insensitive across the priority bands** —
    if "Tesla Cybercab" lands as a multi-word entity, neither
    "Tesla" nor "Cybercab" gets a second hashtag from the
    single-word band. This prevents the same entity occupying
    multiple hashtag slots.

    Returns ``[]`` when nothing extractable, in which case the
    caller falls back to the static ``#Shorts #podcast`` line.
    """
    if not hook and not show_keywords:
        return []

    ordered: List[str] = []
    seen: set = set()

    def _add(token: str) -> bool:
        body = _clean_for_tag(token)
        if not body:
            return False
        key = body.lower()
        if key in seen:
            return False
        # Also block adding "Tesla" if "TeslaCybercab" was already
        # picked — substring match in both directions.
        for picked in seen:
            if key in picked or picked in key:
                # Prefer the LONGER form. If we already have a
                # superset, skip the substring. If the new entity
                # is longer than an existing one, the existing one
                # already won its slot — accept the duplicate-by-
                # substring just to keep ordering predictable.
                if key in picked:
                    return False
        seen.add(key)
        ordered.append(body)
        return True

    for token in _extract_multi_word_entities(hook):
        if len(ordered) >= max_hashtags:
            break
        _add(token)
    for token in _extract_single_proper_nouns(hook):
        if len(ordered) >= max_hashtags:
            break
        _add(token)
    for token in _extract_acronyms(hook):
        if len(ordered) >= max_hashtags:
            break
        _add(token)
    if show_keywords:
        for token in _normalise_show_keywords(show_keywords):
            if len(ordered) >= max_hashtags:
                break
            _add(token)
    return ordered


def format_hashtag_line(
    hashtag_bodies: Iterable[str], static_tags: Sequence[str] = (),
) -> str:
    """Build a single-line ``#A #B #C`` string from hashtag bodies.

    ``static_tags`` are appended verbatim (already include the ``#``)
    so callers can pin ``#Shorts`` / ``#podcast`` at the tail without
    going through the extractor.
    """
    parts = [f"#{b}" for b in hashtag_bodies if b]
    parts.extend(static_tags)
    return " ".join(parts)
