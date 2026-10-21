"""Story ids: one story, followed across days and shows (Oct 21 2026).

``engine.aired_items`` says which stories an episode told; this module says
which of them are the SAME story — the merger on SpaceX, Tesla and MAG 7 on
one morning, or the Fort Bend factory on five Tesla days — and gives each one
a stable id. The content lake (SQLite, rebuilt from the repo in every CI job)
and the story catalog (Supabase, durable) both store the ids this module
computes, so the two never disagree.

Matching is the network's salient-token idea (``engine.story_recurrence``)
made stricter, because a false merge across shows is worse than a missed one:

* an item's tokens are its title's salient tokens (the body's first sentence
  when the title is too short to say anything);
* tokens that sit in at least :data:`COMMON_DF` of the window's items are
  ignored, so "tesla", "spacex", "ai" never make two stories one;
* an item joins the story of the window item it best overlaps when they share
  :data:`MIN_OVERLAP` tokens, or :data:`MIN_FRACTION` of the smaller set with at
  least :data:`MIN_FRACTION_TOKENS`;
* the window is :data:`WINDOW_DAYS` of the story's last appearance.

Deterministic: items are processed by date, then show, episode and position,
so a full rebuild gives every past item the same id. A story id is ``st_`` +
a hash of the key of its first item.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import re
from collections import defaultdict, deque
from dataclasses import dataclass, field
from typing import Deque, Dict, Iterable, List, Optional, Set, Tuple

from engine.story_recurrence import HOOK_GENERIC, salient_tokens

WINDOW_DAYS = 14
COMMON_DF = 0.03
#: A token in this share of ONE show's window items is that show's furniture
#: ("starlink", "launch" on SpaceX) and never joins two of its stories.
SHOW_COMMON_DF = 0.12
MIN_OVERLAP = 3
MIN_FRACTION = 0.6
MIN_FRACTION_TOKENS = 3
#: Below this many salient title tokens the body's first sentence is read too.
MIN_TITLE_TOKENS = 3
#: A story with this many members is matched on its CORE too — the tokens in
#: at least half of them — so a story cannot drift one shared word at a time
#: (a 55-item "self-driving" chain on the first corpus run).
CORE_MIN_MEMBERS = 3
CORE_SHARE = 0.5
CORE_MIN_OVERLAP = 2

#: Words that name no story: spelled numbers (Modern Investing writes "seven
#: point four five percent", which made every rate one story) and the generic
#: set the hook gate already ignores.
_NOISE = frozenset(HOOK_GENERIC) | frozenset("""
zero eleven twelve thirteen fourteen fifteen sixteen seventeen eighteen
nineteen twenty thirty forty fifty sixty seventy eighty ninety point
percent dollars dollar cents trillion quarter half
""".split())

_SENT_RE = re.compile(r"(?<=[.!?])\s+")
_MD_RE = re.compile(r"\[([^\]]*)\]\([^)]*\)|\*\*|https?://\S+")


def item_key(show_slug: str, episode: int, position: int) -> str:
    return f"{show_slug}:{int(episode)}:{int(position)}"


def story_id_for(first_item_key: str) -> str:
    return "st_" + hashlib.sha1(first_item_key.encode("utf-8")).hexdigest()[:12]


#: Lines the weekly segment and show furniture print as bold heads that name
#: no story ("From Ep 89 (2026-06-03)").
_NOT_A_STORY_RE = re.compile(r"^(?:from ep\.? ?\d+|ep(?:isode)? \d+\b)", re.IGNORECASE)


def _fold(tokens: Iterable[str]) -> Set[str]:
    """Plural folding ("boards" = "board", "launches" = "launch")."""
    out: Set[str] = set()
    for t in tokens:
        if len(t) > 4 and not t.isdigit():
            if t.endswith("ies"):
                t = t[:-3] + "y"
            elif t.endswith(("ches", "shes", "sses", "xes")):
                t = t[:-2]
            elif t.endswith("s") and not t.endswith(("ss", "us", "is")):
                t = t[:-1]
        out.add(t)
    return out


def item_tokens(title: str, body: str = "") -> frozenset:
    if _NOT_A_STORY_RE.match((title or "").strip()):
        return frozenset()
    toks = _fold(salient_tokens(title)) - _NOISE
    if len(toks) < MIN_TITLE_TOKENS and body:
        lines = [ln for ln in body.splitlines() if ln.strip()]
        prose = _MD_RE.sub(" ", " ".join(lines[1:3] if len(lines) > 1 else lines))
        first = _SENT_RE.split(prose.strip(), 1)[0] if prose.strip() else ""
        toks |= _fold(salient_tokens(first)) - _NOISE
    return frozenset(toks)


@dataclass(eq=False)
class _Entry:
    date: str
    story_id: str
    tokens: frozenset
    show: str = ""


@dataclass
class StoryAssigner:
    """Assigns story ids to items in chronological order (see module doc).

    ``assign`` must be called with dates that never go backwards."""

    window_days: int = WINDOW_DAYS
    _window: Deque[_Entry] = field(default_factory=deque)
    _df: Dict[str, int] = field(default_factory=lambda: defaultdict(int))
    _show_df: Dict[str, Dict[str, int]] = field(
        default_factory=lambda: defaultdict(lambda: defaultdict(int)))
    _show_n: Dict[str, int] = field(default_factory=lambda: defaultdict(int))
    _index: Dict[str, List[_Entry]] = field(default_factory=lambda: defaultdict(list))
    _story_tok: Dict[str, Dict[str, int]] = field(
        default_factory=lambda: defaultdict(lambda: defaultdict(int)))
    _story_n: Dict[str, int] = field(default_factory=lambda: defaultdict(int))

    def _core(self, sid: str) -> Optional[Set[str]]:
        n = self._story_n.get(sid, 0)
        if n < CORE_MIN_MEMBERS:
            return None
        return {t for t, c in self._story_tok[sid].items() if c >= CORE_SHARE * n}

    def _evict(self, today: str) -> None:
        cutoff = (dt.date.fromisoformat(today) - dt.timedelta(days=self.window_days)).isoformat()
        while self._window and self._window[0].date < cutoff:
            e = self._window.popleft()
            self._show_n[e.show] -= 1
            self._story_n[e.story_id] -= 1
            for t in e.tokens:
                self._story_tok[e.story_id][t] -= 1
            for t in e.tokens:
                self._df[t] -= 1
                self._show_df[e.show][t] -= 1
                lst = self._index.get(t)
                if lst:
                    try:
                        lst.remove(e)
                    except ValueError:
                        pass
                    if not lst:
                        del self._index[t]

    def _network_common(self) -> Set[str]:
        n = len(self._window)
        if n < 20:
            return set()
        floor = max(2, COMMON_DF * n)
        return {t for t, c in self._df.items() if c >= floor}

    def _show_common(self, show: str, cache: Dict[str, Set[str]]) -> Set[str]:
        if show in cache:
            return cache[show]
        n = self._show_n.get(show, 0)
        out: Set[str] = set()
        if n >= 20:
            floor = max(2, SHOW_COMMON_DF * n)
            out = {t for t, c in self._show_df[show].items() if c >= floor}
        cache[show] = out
        return out

    @staticmethod
    def _joins(probe: frozenset, cand: frozenset) -> int:
        overlap = len(probe & cand)
        smaller = min(len(probe), len(cand))
        if overlap >= MIN_OVERLAP or (
            smaller >= MIN_FRACTION_TOKENS and overlap / smaller >= MIN_FRACTION
        ):
            return overlap
        return 0

    def _best(self, tokens: frozenset, show: str, entries: Iterable[_Entry],
              net: Set[str], cache: Dict[str, Set[str]]) -> Optional[str]:
        probe = tokens - net - self._show_common(show, cache)
        if len(probe) < 2:
            return None
        best: Optional[Tuple[int, str, str]] = None
        for e in entries:
            cand = e.tokens - net - self._show_common(e.show, cache) - self._show_common(show, cache)
            ov = self._joins(probe - self._show_common(e.show, cache), cand)
            # Across shows only the plain overlap counts: the fractional rule
            # merged "TSMC foundry market share" with Tesla's Norway share.
            if ov and e.show != show and ov < MIN_OVERLAP:
                ov = 0
            if ov:
                core = self._core(e.story_id)
                if core is not None and len(probe & core) < CORE_MIN_OVERLAP:
                    continue
                key = (ov, e.date, e.story_id)
                if best is None or key > best:
                    best = key
        return best[2] if best else None

    def _add(self, e: _Entry) -> None:
        self._window.append(e)
        self._show_n[e.show] += 1
        self._story_n[e.story_id] += 1
        for t in e.tokens:
            self._story_tok[e.story_id][t] += 1
            self._df[t] += 1
            self._show_df[e.show][t] += 1
            self._index[t].append(e)

    def observe(self, date: str, items: Iterable[Tuple]) -> None:
        """Take in items that already carry a story id —
        ``[(story_id, tokens, show), ...]`` for one date — so new items can be
        matched against them without recomputing their ids (the lake seeds a
        single episode's assignment from the ids it stored)."""
        self._evict(date)
        for sid, tokens, show in items:
            if sid and tokens:
                self._add(_Entry(date, sid, tokens, show))

    def match_story(self, tokens: frozenset, show: str) -> Optional[str]:
        """The story *tokens* would join, without recording anything."""
        return self._best(tokens, show, self._candidates(tokens),
                          self._network_common(), {})

    def _candidates(self, tokens: frozenset) -> List[_Entry]:
        seen: Dict[int, _Entry] = {}
        for t in tokens:
            for e in self._index.get(t, ()):
                seen[id(e)] = e
        return list(seen.values())

    def assign(self, date: str, items: Iterable[Tuple]) -> List[str]:
        """``items`` is ``[(item_key, tokens, show[, kind]), ...]`` for one
        date, in the canonical order. Returns their story ids, in order. An
        ``essay`` item (a narrative episode) is its own story and is never
        matched or indexed."""
        self._evict(date)
        net = self._network_common()
        cache: Dict[str, Set[str]] = {}
        out: List[str] = []
        pending: List[_Entry] = []
        for row in items:
            key, tokens, show = row[0], row[1], row[2]
            kind = row[3] if len(row) > 3 else "item"
            if kind == "essay" or not tokens:
                out.append(story_id_for(key))
                continue
            sid = self._best(tokens, show, self._candidates(tokens), net, cache)
            if sid is None:
                sid = self._best(tokens, show, pending, net, cache)
            if sid is None:
                sid = story_id_for(key)
            out.append(sid)
            pending.append(_Entry(date, sid, tokens, show))
        for e in pending:
            self._add(e)
        return out


__all__ = ["StoryAssigner", "item_key", "item_tokens", "story_id_for",
           "WINDOW_DAYS", "COMMON_DF", "MIN_OVERLAP"]
