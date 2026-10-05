"""Same-story clustering — inline "SAME STORY" annotations for the digest prompt.

Oct 1 2026 (network readout of the first post-merge slate). Tesla Ep622's
digest carried the Model 3 refresh as EIGHT items from eight outlets (the
China screen-and-V2L upgrade, the Australian price cut, the black headliner,
the NZ launch…), and the script then told the same facts five times. The
cross-section dedupe (``engine/digest_overlap.py``) is blind to this shape:
each outlet covers a different ANGLE, so headline and body vocabulary
overlap stays under its thresholds, and the prompt's "one story = one item"
line is the kind of instruction the model breaks. The repetition the
operator hears is this: not exact duplicates, a story told once per outlet.

The lever is data-side and upstream of generation, the shape the Fort Bend
``story_recurrence`` memory uses: the fetched article list is clustered
deterministically (salient-token overlap on title + teaser, with the
show's common tokens filtered out so "tesla" or "model" can never make a
match), and every later member of a cluster carries an inline instruction
under its listing — write ONE item, fold this outlet's angle in, cite both
URLs. Nothing is dropped: an angle the model needs is still in the prompt.

The scoreable metric is ``cluster_retold_in_digest``: clusters whose
members each surfaced as a SEPARATE digest item. The annotations aim to
drive it to 0; the readout reads it beside ``story_clusters_annotated``.

Calibrated on the trackers' last four days of headlines for tesla, spacex,
models_agents and omni_view (titles only, 2026-09-28..10-01): every cluster
proposed at ``MIN_SHARED`` 4 / ``MIN_SHARE`` 0.35 was a real same-story
pair except one arXiv pair on Models & Agents joined on "language models",
which the window-wide common-token filter removes.
"""
from __future__ import annotations

import logging
import re
from typing import Dict, Iterable, List, Optional, Sequence

from engine.story_recurrence import salient_tokens

logger = logging.getLogger(__name__)

#: Two articles are one story when their salient title+teaser tokens share
#: at least this many tokens AND the shared set is at least ``MIN_SHARE``
#: of the smaller article's set.
MIN_SHARED = 4
MIN_SHARE = 0.35

#: A token present in at least this share of the batch (or of the show's
#: recent headline window, when supplied) is the show's furniture and never
#: counts toward a match.
COMMON_DF = 0.30

#: A batch stands in for the headline window as the furniture pool only
#: when it is at least this large.
MIN_POOL_FOR_BATCH_DF = 20

#: Teaser text beyond this many characters is ignored — a full article body
#: in the teaser field would swamp the headline's signal.
TEASER_MAX_CHARS = 400

_WS_RE = re.compile(r"\s+")


def _article_tokens(article: dict) -> frozenset:
    title = str(article.get("title") or "")
    teaser = str(article.get("description") or article.get("summary") or "")[:TEASER_MAX_CHARS]
    return salient_tokens(_WS_RE.sub(" ", f"{title} {teaser}"))


def common_tokens(token_sets: Sequence[frozenset], *, df: float = COMMON_DF) -> frozenset:
    """Tokens present in at least ``df`` of the sets."""
    n = len(token_sets)
    if n < 4:
        return frozenset()
    counts: Dict[str, int] = {}
    for s in token_sets:
        for tok in s:
            counts[tok] = counts.get(tok, 0) + 1
    return frozenset(t for t, c in counts.items() if c / n >= df)


def cluster_articles(
    articles: Sequence[dict],
    *,
    window_headlines: Optional[Iterable[str]] = None,
    min_shared: int = MIN_SHARED,
    min_share: float = MIN_SHARE,
) -> List[List[int]]:
    """Groups of article indices that tell one story (size >= 2), each
    group in list order so ``group[0]`` is the lead article.

    ``window_headlines`` — the show's recent headline window (the content
    tracker's) — widens the common-token filter so a show's standing
    vocabulary ("starship", "language models") never joins two stories.
    """
    toks = [_article_tokens(a) for a in articles]
    # The furniture filter needs a POOL large enough that one well-covered
    # story cannot make its own tokens "common" (three outlets in a batch
    # of six would). The show's headline window (hundreds of titles) is
    # that pool; a batch stands in only when it is large and no window
    # was supplied.
    pool: List[frozenset] = [salient_tokens(h) for h in (window_headlines or [])]
    if not pool and len(toks) >= MIN_POOL_FOR_BATCH_DF:
        pool = list(toks)
    common = common_tokens(pool) if pool else frozenset()
    toks = [s - common for s in toks]

    parent = list(range(len(articles)))

    def find(x: int) -> int:
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    for i in range(len(toks)):
        if len(toks[i]) < min_shared:
            continue
        for j in range(i + 1, len(toks)):
            if len(toks[j]) < min_shared:
                continue
            shared = toks[i] & toks[j]
            if len(shared) < min_shared:
                continue
            if len(shared) / min(len(toks[i]), len(toks[j])) < min_share:
                continue
            parent[find(j)] = find(i)

    groups: Dict[int, List[int]] = {}
    for i in range(len(toks)):
        groups.setdefault(find(i), []).append(i)
    return [sorted(g) for g in groups.values() if len(g) > 1]


def annotation_for(lead_index: int, lead_title: str) -> str:
    """The inline instruction under a later member of a cluster. Shape only —
    it names the lead article, never a sentence the model could copy."""
    short = _WS_RE.sub(" ", lead_title or "").strip()
    if len(short) > 90:
        short = short[:87].rstrip() + "…"
    return (
        f"   [SAME-STORY NOTE — instruction, not content: this is the same story "
        f"as article #{lead_index + 1} (\"{short}\"). Write it as ONE item — fold "
        f"this outlet's angle and any new fact into that item and cite both "
        f"URLs on its Source line. Never a second item that re-tells it.]"
    )


def annotate_articles(
    articles: Sequence[dict],
    *,
    window_headlines: Optional[Iterable[str]] = None,
) -> Dict[int, str]:
    """Map article-list index -> annotation line for every non-lead member
    of a cluster. The lead carries nothing: it is the item."""
    notes: Dict[int, str] = {}
    for group in cluster_articles(articles, window_headlines=window_headlines):
        lead = group[0]
        lead_title = str(articles[lead].get("title") or "")
        for idx in group[1:]:
            notes[idx] = annotation_for(lead, lead_title)
    return notes


_DIGEST_ITEM_RE = re.compile(
    r"^\s*(?:\d+\.\s*)?\*\*(?P<title>[^*\n]{10,})\*\*", re.MULTILINE)


def digest_item_titles(digest_text: str) -> List[str]:
    """Bold item headlines in a digest (numbered or full-line bold)."""
    return [m.group("title").strip() for m in _DIGEST_ITEM_RE.finditer(digest_text or "")]


def cluster_retold_in_digest(
    digest_text: str,
    articles: Sequence[dict],
    clusters: Sequence[Sequence[int]],
) -> int:
    """How many clusters surfaced as MORE than one digest item — the
    scoreable outcome. An article "surfaces" as the item whose headline
    shares the most salient tokens with it (at least 3)."""
    titles = digest_item_titles(digest_text)
    if not titles or not clusters:
        return 0
    title_toks = [salient_tokens(t) for t in titles]
    retold = 0
    for group in clusters:
        hit_items = set()
        for idx in group:
            art = salient_tokens(str(articles[idx].get("title") or ""))
            best, best_n = None, 0
            for k, tt in enumerate(title_toks):
                n = len(art & tt)
                if n > best_n:
                    best, best_n = k, n
            if best is not None and best_n >= 3:
                hit_items.add(best)
        if len(hit_items) > 1:
            retold += 1
    return retold


__all__ = [
    "MIN_SHARED", "MIN_SHARE", "COMMON_DF",
    "cluster_articles", "annotate_articles", "annotation_for",
    "cluster_retold_in_digest", "digest_item_titles", "common_tokens",
]
