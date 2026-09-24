"""A Sources line for the podcast show notes (Sep 24 2026).

The RSS ``<description>`` a listener reads in Apple Podcasts or Spotify
carried the first 500 characters of the digest, the AI disclosure and the
site links — and no source at all. Every ``Source:`` line had been scrubbed
from that copy as leakage. The launch-cohort research put visible sourcing
first among the things that repair trust in AI-produced news (a list of the
sources used offsets the AI label where an explanation does not), and the
blog post already renders one; the feed, where most listeners are, did not.

:func:`sources_footer` builds one compact markdown line from the digest's
``Source:`` links — publisher domains, each linked to the first article
cited from it, in document order, deduplicated by registrable domain, at
most :data:`MAX_SOURCES` — that ``engine.publisher._markdown_to_rss_html``
turns into anchors. No sources, no line. It reads the digest only; it never
touches audio, the claims ledger or the digest itself.
"""

from __future__ import annotations

from typing import List, Tuple
from urllib.parse import urlparse

from engine.blog import _extract_source_urls

#: Domains listed per episode. Enough to show the sourcing; short enough
#: that podcast apps show it without a "more" fold of its own.
MAX_SOURCES = 8

#: The label the line opens with, per feed language.
LABELS = {"en": "Sources", "ru": "Источники", "fr": "Sources"}

_SOCIAL_HOSTS = ("x.com", "twitter.com")


def display_domain(url: str) -> str:
    """``https://www.bbc.com/news/…`` -> ``bbc.com``; empty on a bad URL."""
    try:
        host = (urlparse(url).netloc or "").lower().split(":")[0]
    except Exception:  # noqa: BLE001
        return ""
    if host.startswith("www."):
        host = host[4:]
    return host


def source_pairs(digest_md: str, max_sources: int = MAX_SOURCES) -> List[Tuple[str, str]]:
    """``[(domain, url), …]`` in document order, one per domain, publishers
    before social posts (an x.com source is real but is listed last)."""
    seen: set = set()
    publishers: List[Tuple[str, str]] = []
    social: List[Tuple[str, str]] = []
    for url in _extract_source_urls(digest_md or ""):
        dom = display_domain(url)
        if not dom or dom in seen:
            continue
        seen.add(dom)
        (social if dom in _SOCIAL_HOSTS else publishers).append((dom, url))
    return (publishers + social)[:max_sources]


def sources_footer(digest_md: str, *, language: str = "en",
                   max_sources: int = MAX_SOURCES) -> str:
    """One markdown line, or ``""`` when the digest cites nothing."""
    pairs = source_pairs(digest_md, max_sources=max_sources)
    if not pairs:
        return ""
    label = LABELS.get((language or "en").lower()[:2], LABELS["en"])
    return f"{label}: " + " · ".join(f"[{dom}]({url})" for dom, url in pairs)
