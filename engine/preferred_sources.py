"""Preferred primary publishers for a show's lead claims (Sep 23 2026).

A show YAML may list ``preferred_domains`` — regulators, courts, journals,
the city's own newsroom. The launch-cohort review found the digest leaning
on whatever was newest (Prediction Markets Ep1 credited a rule change to an
X post, Peptides Ep1 to status posts) while the primary source sat further
down the fetch. This module is the whole mechanism:

* :func:`is_preferred_url` — host match (exact or a subdomain of a listed
  domain; ``www.`` is ignored).
* :func:`mark_preferred_articles` — bumps ``relevance_score`` by
  :data:`PREFERRED_BONUS` so the article survives run_show's prompt cap, and
  sets ``preferred_source`` so the listing line carries the
  ``[preferred primary source]`` tag.

An empty list is a byte-identical no-op. It never removes or reorders
anything on its own — run_show's existing relevance sort does the rest.
"""

from __future__ import annotations

from typing import Iterable, List, Optional
from urllib.parse import urlparse

#: Added to ``relevance_score`` for a preferred article. Feed articles start
#: at 0.0 and X posts at 0.7, so 1.0 puts a primary source ahead of any post
#: without disturbing the order among preferred articles themselves.
PREFERRED_BONUS = 1.0

#: The tag run_show appends to the article's listing line in the digest
#: prompt. A label, never a sentence — nothing here is quotable prose.
PROMPT_TAG = "[preferred primary source]"


def normalise_domains(domains: Optional[Iterable[str]]) -> List[str]:
    out: List[str] = []
    for d in domains or []:
        d = (d or "").strip().lower()
        if d.startswith("www."):
            d = d[4:]
        if d and d not in out:
            out.append(d)
    return out


def is_preferred_url(url: str, domains: Iterable[str]) -> bool:
    """True when *url*'s host is one of *domains* or a subdomain of one."""
    try:
        host = (urlparse(url or "").netloc or "").lower().split(":")[0]
    except Exception:  # noqa: BLE001 — a malformed URL is simply not preferred
        return False
    if host.startswith("www."):
        host = host[4:]
    if not host:
        return False
    for d in normalise_domains(domains):
        if host == d or host.endswith("." + d):
            return True
    return False


def mark_preferred_articles(articles: List[dict], domains: Iterable[str]) -> int:
    """Flag and boost every article from a preferred domain. Returns the count.

    Idempotent: an article already flagged is not boosted twice.
    """
    doms = normalise_domains(domains)
    if not doms or not articles:
        return 0
    n = 0
    for art in articles:
        if not isinstance(art, dict) or art.get("preferred_source"):
            continue
        if is_preferred_url(str(art.get("url") or ""), doms):
            art["preferred_source"] = True
            art["relevance_score"] = float(art.get("relevance_score") or 0.0) + PREFERRED_BONUS
            n += 1
    return n
