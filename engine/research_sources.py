"""Research sources on the narrative shows (Oct 14 2026).

Unintended Consequences and First Principles write from the topic brief and
the pages ``narrative_research`` retrieved for it (Oct 9 2026), and the
claims gate verifies against those pages — but the pages reached no reader:
the digest carried no Source: lines and no Sources section, so the blog's
Sources card was empty, the show notes listed nothing, and an outside
review of the Oct 13 slate read FPD Ep129 and UC Ep141 as unsourced. This
module renders the research articles as a trailing ``### Sources`` section
on the canonical digest, which is the one shape every reader surface
already understands (``engine.blog._extract_source_urls`` reads a trailing
Sources list; ``engine.show_notes.sources_footer`` reads the blog's list).
The podcast copy strips the section (``engine.listener_noise``
``READER_ONLY_EXACT_SECTIONS``), so nothing here is spoken.

Render, never block: a topic with no retrievable sources is already skipped
upstream by ``narrative_research_min``; a digest that has a Sources section
of its own is left alone.
"""

from __future__ import annotations

import re
from typing import Iterable, List
from urllib.parse import urlparse

SOURCES_HEADING = "### Sources"
_EXISTING_SOURCES_RE = re.compile(
    r"^\s*#{1,6}\s*(?:sources?|references?)\s*:?\s*$", re.IGNORECASE | re.MULTILINE)


def _domain(url: str) -> str:
    try:
        host = (urlparse(url).netloc or "").lower().split(":")[0]
    except Exception:  # noqa: BLE001
        return ""
    return host[4:] if host.startswith("www.") else host


def research_articles(articles: Iterable[dict]) -> List[dict]:
    """The research-search articles among *articles*, deduplicated by URL,
    in the order the search returned them."""
    seen: set = set()
    out: List[dict] = []
    for a in articles or []:
        if not isinstance(a, dict) or a.get("source_kind") != "research":
            continue
        url = str(a.get("link") or a.get("url") or "").strip()
        if not url.startswith("http") or url in seen:
            continue
        seen.add(url)
        out.append(a)
    return out


def research_sources_block(articles: Iterable[dict]) -> str:
    """``### Sources`` plus one ``- [domain](url) — title`` line per research
    article, or ``""`` when there are none."""
    rows = []
    for a in research_articles(articles):
        url = str(a.get("link") or a.get("url") or "").strip()
        dom = _domain(url)
        if not dom:
            continue
        title = " ".join(str(a.get("title") or "").split())
        rows.append(f"- [{dom}]({url})" + (f" — {title}" if title else ""))
    if not rows:
        return ""
    return SOURCES_HEADING + "\n" + "\n".join(rows) + "\n"


def append_research_sources(digest: str, articles: Iterable[dict]) -> str:
    """The digest with the research Sources section appended; unchanged when
    there is nothing to list or the digest already carries a Sources section."""
    block = research_sources_block(articles)
    if not block or not digest or _EXISTING_SOURCES_RE.search(digest):
        return digest
    return digest.rstrip("\n") + "\n\n" + block
