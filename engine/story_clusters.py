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
    # Oct 17 2026: an article flagged ``recurrence_exempt`` (a Board market)
    # never joins a cluster — Kalshi's and Polymarket's prices on one
    # question are two readings, and the SAME-STORY note folded them away.
    toks = [frozenset() if articles[i].get("recurrence_exempt") else s - common
            for i, s in enumerate(toks)]

    def _same_story(i: int, j: int) -> bool:
        if len(toks[i]) < min_shared or len(toks[j]) < min_shared:
            return False
        shared = toks[i] & toks[j]
        if len(shared) < min_shared:
            return False
        return len(shared) / min(len(toks[i]), len(toks[j])) >= min_share

    # Every member must match the cluster's LEAD itself, never only another
    # member. Oct 18 2026: single-link chaining (A~B, B~C => A+C) put Korean
    # insurance losses, a first FSD drive in Slovakia, a family's Model Y and
    # a Ninth Circuit ruling in one Tesla cluster, and the regeneration note
    # then told the model to write all six as ONE item.
    owner = [-1] * len(articles)
    groups: Dict[int, List[int]] = {}
    for i in range(len(toks)):
        if owner[i] != -1:
            continue
        for j in range(i + 1, len(toks)):
            if owner[j] == -1 and _same_story(i, j):
                owner[j] = i
                groups.setdefault(i, [i]).append(j)
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
    return len(retold_clusters(digest_text, articles, clusters))


#: A word in at least this share of a digest's own item headlines is the
#: show's furniture for the retold check ("tesla" sits in 15 of 19 on a
#: Tesla digest). Half, not ``COMMON_DF``: a story told as three items of
#: nine would make its own words "common" at 30%.
TITLE_FURNITURE_DF = 0.5
TITLE_FURNITURE_MIN_TITLES = 8


def _title_furniture(title_toks: Sequence[frozenset]) -> frozenset:
    """Tokens that say nothing about WHICH story an item tells: the show's
    furniture words and bare numbers ("000", "2026", "3")."""
    common = (common_tokens(title_toks, df=TITLE_FURNITURE_DF)
              if len(title_toks) >= TITLE_FURNITURE_MIN_TITLES else frozenset())
    digits = frozenset(t for s in title_toks for t in s if t.isdigit())
    return common | digits


def retold_clusters(
    digest_text: str,
    articles: Sequence[dict],
    clusters: Sequence[Sequence[int]],
) -> List[List[str]]:
    """For every cluster that surfaced as more than one digest item, the
    headlines of those items (digest order). ``cluster_retold_in_digest``
    is the length of this list.

    Oct 24 2026: a cluster is retold only when ONE of its stories is told as
    several items. Each member joined the cluster on the words it shares
    with the lead (its core); an item tells that story when it carries the
    core's words, the show's furniture and bare numbers removed. Tesla
    Ep644 mapped each member to whichever headline shared three words with
    it ("tesla", "2026", "000" count) — a roundup lead whose teaser touched
    the merger committees, Optimus output and Japan's V2L adapter made those
    three different stories one "retold" cluster, and the regeneration it
    triggered cut the digest from 1,591 prose words to 1,210 to fix nothing."""
    titles = digest_item_titles(digest_text)
    if not titles or not clusters:
        return []
    title_toks = [salient_tokens(t) for t in titles]
    furniture = _title_furniture(title_toks)
    title_toks = [t - furniture for t in title_toks]
    out: List[List[str]] = []
    for group in clusters:
        members = [i for i in group if 0 <= i < len(articles)]
        if len(members) < 2:
            continue
        lead, rest = members[0], members[1:]
        lead_toks = _article_tokens(articles[lead]) - furniture
        hit_items = set()
        for idx in rest:
            core = (lead_toks & _article_tokens(articles[idx])) - furniture
            if len(core) < 2:
                continue
            need = min(3, len(core))
            hits = {k for k, tt in enumerate(title_toks) if len(core & tt) >= need}
            if len(hits) > 1:
                hit_items |= hits
        if len(hit_items) > 1:
            out.append([titles[k] for k in sorted(hit_items)])
    return out


def dropped_clusters(
    digest_text: str,
    retold_before: Sequence[Sequence[str]],
    *,
    min_shared: int = 3,
) -> List[List[str]]:
    """The retold groups a retry left with NO item at all (Oct 21 2026).

    The retry is asked to fold a story told as several items into ONE; Tesla
    Ep641's retry folded the Tesla-SpaceX merger committees — the day's
    biggest Tesla story, the lead on SpaceX and MAG 7 — into nothing, and
    the retold count read 0, so the retry was kept. A group survives when
    some item headline shares ``min_shared`` salient words with one of its
    original headlines."""
    titles = [salient_tokens(t) for t in digest_item_titles(digest_text)]
    out: List[List[str]] = []
    for heads in retold_before or []:
        toks = [salient_tokens(h) for h in heads]
        if not any(len(t & tt) >= min_shared for t in toks for tt in titles):
            out.append(list(heads))
    return out


def retold_cluster_note(retold: Sequence[Sequence[str]], *, max_clusters: int = 3) -> str:
    """The structural-regeneration note for clusters told as several items
    (Oct 17 2026 readout of story-clusters-2026-10-01: Tesla retold a
    clustered story on 12 of its first 14 post-merge episodes, so the
    inline annotation is read past and the rule rides the one-shot
    regeneration, like a missing section). ``""`` when nothing was retold.
    Names the items, never a sentence to write."""
    if not retold:
        return ""
    parts = []
    for heads in list(retold)[:max_clusters]:
        parts.append(" / ".join(f"“{h[:70]}”" for h in heads))
    return (
        f"{len(retold)} story(ies) appear as more than one item ("
        + "; ".join(parts)
        + ") — each is ONE story told by several outlets: write it as ONE "
        "item that folds in every outlet's angle and keeps every Source URL"
    )


__all__ = [
    "MIN_SHARED", "MIN_SHARE", "COMMON_DF",
    "cluster_articles", "annotate_articles", "annotation_for",
    "cluster_retold_in_digest", "retold_clusters", "retold_cluster_note",
    "dropped_clusters",
    "digest_item_titles", "common_tokens",
]
