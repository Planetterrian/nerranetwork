"""Story-recurrence memory — inline "already covered" annotations.

The problem (Aug 15 2026 Tesla review): the Fort Bend solar-factory story
ran in 5 of 10 episodes and four times inside Ep573 alone, each time
re-told from scratch as if new. Three defenses already existed and all
three missed it:

* ``content_freshness`` title-similarity dedup (0.72 threshold, 2-day
  lookback) — re-headlined versions ("Tesla plans $10B solar cell
  factory" vs "Tesla seeks Texas tax incentive for USD-10bn solar cell
  factory") score below the threshold, and day-4/6/9 recurrences are
  outside the window entirely.
* ``ContentTracker.get_summary_for_prompt`` — a flat "DO NOT repeat
  these" headline list, 3-day window, placed in a block far from the
  article listing. Blanket-banning is also editorially WRONG for a
  developing story: the new filing deserves coverage — as an UPDATE,
  not a re-telling.
* The within-episode duplicate-headline strip — exact/near matches only.

This module is the DP Pod lever-memory pattern applied to news: the
recurrence signal is computed DATA-side (no LLM calls, no new storage —
it reads the dated headline window ``ContentTracker`` already persists)
and delivered INLINE, attached to the exact article the model is
deciding about, with update-don't-retell framing instead of a ban.

Matching is salient-token overlap with an automatic per-show common-token
filter: tokens appearing in a large share of the window's headlines
("tesla", "spacex", "launch"…) carry no signal and are excluded, so the
brand name can never manufacture a match. Deterministic, cheap, and the
same doc-frequency idea the gallery-retention style miner uses.

Wired in ``run_show.py``: annotations render into the news_section under
each matched article; after the digest ships, the recurrence count of
the SHIPPED stories is recorded as a metric so reviews can score the
lever mechanically (``story_recurrence_in_digest``).
"""

from __future__ import annotations

import logging
import re
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# Generic English stopwords + article-title furniture. Deliberately small:
# the doc-frequency filter below handles show-specific noise ("tesla",
# "spacex", "starship") without hand-curation.
_STOPWORDS = frozenset("""
a an and are as at be but by for from has have how in into is it its new
of on or over says say said that the their this to today up was were what
when who will with after amid announces announced report reports reveals
revealed here why you your
""".split())

_TOKEN_RE = re.compile(r"[a-z0-9]+(?:['’][a-z0-9]+)*")

# A window headline shares this many salient tokens with an article title
# (or covers this fraction of the smaller token set) => same story.
_MIN_OVERLAP = 3
_MIN_FRACTION = 0.6

# Tokens present in at least this share of window headlines are "common"
# for the show and never count toward an overlap.
_COMMON_DF = 0.30


def salient_tokens(title: str) -> frozenset:
    """Normalized salient tokens of a headline (pre common-token filter)."""
    tokens = _TOKEN_RE.findall((title or "").lower())
    return frozenset(
        t for t in tokens
        if t not in _STOPWORDS and (len(t) >= 3 or t.isdigit())
    )


class RecurrenceIndex:
    """Token index over the tracker's recent-episode headline window."""

    def __init__(self, episodes: List[dict], *, exclude_date: str = ""):
        """*episodes* is ``ContentTracker.data["episodes"]`` (dicts with
        ``date`` + ``headlines``). ``exclude_date`` drops that calendar
        day's record — required when scoring today's own digest against
        the window (the FF Ep128 self-match lesson)."""
        self._entries: List[Tuple[str, str, frozenset]] = []
        df: Dict[str, int] = {}
        for ep in episodes or []:
            date = ep.get("date", "")
            if exclude_date and date == exclude_date:
                continue
            for headline in ep.get("headlines", []) or []:
                toks = salient_tokens(headline)
                if not toks:
                    continue
                self._entries.append((date, headline, toks))
                for t in toks:
                    df[t] = df.get(t, 0) + 1
        n = len(self._entries)
        self.common: frozenset = frozenset(
            t for t, c in df.items() if n >= 5 and c / n >= _COMMON_DF
        )

    def __len__(self) -> int:
        return len(self._entries)

    def match(self, title: str) -> Optional[dict]:
        """Best window match for *title*, or None.

        Returns ``{"date", "headline", "times"}`` — ``times`` is how many
        DISTINCT DAYS in the window covered the story (a story that ran
        4 days reads differently than one that ran once; counting raw
        headline matches would inflate multi-section coverage).
        """
        probe = salient_tokens(title) - self.common
        if len(probe) < 2:
            return None
        matches: List[Tuple[str, str, int]] = []
        for date, headline, toks in self._entries:
            cand = toks - self.common
            if not cand:
                continue
            overlap = len(probe & cand)
            smaller = min(len(probe), len(cand))
            if overlap >= _MIN_OVERLAP or (
                smaller >= 2 and overlap / smaller >= _MIN_FRACTION
                and overlap >= 2
            ):
                matches.append((date, headline, overlap))
        if not matches:
            return None
        # Cite the MOST RECENT day the story ran ("most recently on …"
        # must not point at an older copy), quoting that day's
        # highest-overlap headline.
        latest = max(d for d, _h, _o in matches)
        quote = max((m for m in matches if m[0] == latest),
                    key=lambda m: m[2])[1]
        return {"date": latest, "headline": quote,
                "times": len({d for d, _h, _o in matches})}


def annotation_for(match: dict) -> str:
    """The inline note rendered under a matched article in news_section.

    Instruction-shaped, not content-shaped: nothing here should be
    quotable as digest prose (de-seed rule), and a scrub guard in
    ``engine.newsletter_sanitizer`` removes the marker if the model ever
    echoes it.
    """
    times = match.get("times", 1)
    seen = (f"covered on {times} recent days, most recently "
            if times > 1 else "covered ")
    return (
        f"   [ALREADY-COVERED NOTE — instruction, not content: this story was "
        f"{seen}on {match['date']} "
        f"(“{match['headline'][:90]}”). Include it ONLY if today's "
        f"item adds a genuinely NEW development beyond that coverage; if so, "
        f"cover it as a short UPDATE — one clause of recap at most, lead with "
        f"what changed — never re-tell the story from scratch, and do not "
        f"make it the hook again. If nothing is new, pick a different story.]"
    )


def annotate_articles(articles: List[dict],
                      index: "RecurrenceIndex") -> Dict[int, str]:
    """Map article-list index -> annotation line for matched articles."""
    notes: Dict[int, str] = {}
    if not len(index):
        return notes
    for i, art in enumerate(articles):
        title = art.get("title") or ""
        if not title:
            continue
        m = index.match(title)
        if m:
            notes[i] = annotation_for(m)
    return notes


def recurrence_in_digest(digest_text: str,
                         index: "RecurrenceIndex") -> int:
    """How many of the shipped digest's story headlines match the window.

    THE scoreable metric for this lever: the annotations aim to convert
    re-tellings into brief updates and drop no-news repeats, so this
    count (recorded as ``story_recurrence_in_digest``) should fall
    relative to the Aug-2026 baseline (Fort Bend class: same story in
    5 of 10 Tesla episodes).
    """
    if not digest_text or not len(index):
        return 0
    from engine.grok_imagine import extract_story_headlines

    count = 0
    for headline in extract_story_headlines(digest_text, max_count=24):
        if index.match(headline):
            count += 1
    return count
