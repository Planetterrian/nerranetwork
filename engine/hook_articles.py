"""Articles supplied by a show's ``pre_fetch`` hook (Sep 2026).

Until this module, a hook could only add PROMPT VARIABLES: its return dict
was merged into ``template_vars`` / ``pod_vars`` and never reached the
fetched ``articles`` list. So hook-held material — the week's merged PRs,
a road-events API, a journal search, a sibling desk's digest — could be
read by the model but not by anything that checks the model: the
no-articles skip, dedup, the stale gate, the numbered ``news_section``
the digest cites from, and ``engine.claims.build_local_texts``, which is
what lets a claim verify against the copy the pipeline already holds
instead of a live HTTP fetch that a publisher may 403.

Contract: ``pre_fetch`` may return ``{"articles": [ {...}, ... ]}``. Each
entry needs a ``title`` and a ``url``; ``description``, ``content_text``,
``source_name`` and ``published_date`` are optional and take the same
meaning they have on a fetched article. ``exempt_stale: True`` excuses an
article from ``stale_article_days`` (for hook data that is inherently
dated in the past, like a week's merged PRs). Everything else about the
article is handled exactly like an RSS item.

A malformed entry is dropped with a warning, never raised: a hook failure
must degrade to "no hook articles", the same way a hook exception already
degrades to ``{}``.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Tuple

logger = logging.getLogger(__name__)

#: Key a hook uses in its ``pre_fetch`` return dict.
HOOK_ARTICLES_KEY = "articles"

#: Marks an article's origin so metrics and debugging can tell them apart.
SOURCE_KIND_HOOK = "hook"

#: Title similarity at or above which a hook article is treated as a
#: duplicate of an article the RSS/X fetch already returned. Same value the
#: X-post merge uses, for the same reason: both compare a headline against
#: headlines written by different outlets.
HOOK_DEDUP_THRESHOLD = 0.65

_TEXT_KEYS = ("description", "content_text", "source_name", "published_date")


def pop_hook_articles(extra_context: Dict[str, Any] | None, slug: str = "") -> List[Dict]:
    """Remove and validate the hook's ``articles`` entry.

    Popped (not just read) so a list of dicts never lands in the prompt
    template variables, where ``{articles}`` would render as a Python repr.
    """
    if not isinstance(extra_context, dict):
        return []
    raw = extra_context.pop(HOOK_ARTICLES_KEY, None)
    return normalize_hook_articles(raw, slug=slug)


def normalize_hook_articles(raw: Any, slug: str = "") -> List[Dict]:
    if raw is None:
        return []
    if not isinstance(raw, (list, tuple)):
        logger.warning(
            "%s: pre_fetch 'articles' is %s, not a list — ignored",
            slug or "hook", type(raw).__name__,
        )
        return []
    out: List[Dict] = []
    seen_urls: set[str] = set()
    for i, item in enumerate(raw):
        if not isinstance(item, dict):
            logger.warning("%s: hook article %d is not a dict — dropped", slug or "hook", i)
            continue
        title = str(item.get("title") or "").strip()
        url = str(item.get("url") or item.get("link") or "").strip()
        if not title or not url:
            logger.warning(
                "%s: hook article %d lacks a title or url — dropped", slug or "hook", i,
            )
            continue
        if url in seen_urls:
            continue
        seen_urls.add(url)
        art: Dict[str, Any] = {"title": title, "url": url}
        for key in _TEXT_KEYS:
            val = item.get(key)
            if val:
                art[key] = str(val)
        art.setdefault("source_name", "Nerra hook")
        art.setdefault("description", "")
        art["source_kind"] = SOURCE_KIND_HOOK
        if item.get("exempt_stale"):
            art["exempt_stale"] = True
        out.append(art)
    return out


def merge_hook_articles(
    articles: List[Dict], hook_articles: List[Dict],
) -> Tuple[List[Dict], int]:
    """Append hook articles that do not duplicate a fetched one.

    Returns ``(merged, n_added)``. A hook article whose URL, or whose
    headline (at :data:`HOOK_DEDUP_THRESHOLD`), matches an article already
    fetched is dropped — the fetched copy wins because it came through the
    feed's own date and filter checks.
    """
    if not hook_articles:
        return list(articles), 0
    from engine.utils import calculate_similarity

    have_urls = {str(a.get("url") or "").strip() for a in articles}
    merged = list(articles)
    added = 0
    for ha in hook_articles:
        if ha["url"] in have_urls:
            continue
        ha_title = ha["title"][:200]
        dup = False
        for art in articles:
            at = str(art.get("title") or "")[:200]
            if at and calculate_similarity(ha_title, at) >= HOOK_DEDUP_THRESHOLD:
                dup = True
                break
        if dup:
            logger.info("Hook article deduped against a fetched article: %s", ha_title[:80])
            continue
        merged.append(ha)
        have_urls.add(ha["url"])
        added += 1
    return merged, added
