"""Live web + X research for time-sensitive deep-dive episodes.

A deep dive normally runs off its static ``brief`` (engine/topic_queue +
run_show deep-dive mode), with no news fetch. That's fine for an evergreen
subject, but it leaves a time-sensitive topic (an imminent IPO, a breaking
policy change) grounded only in the LLM's training data — which goes stale.
Modern Investing Ep059 (the first SpaceX IPO deep dive) shipped repeating
"no announced IPO ... speculative" because the model had no live grounding.

When a deep-dive queue entry carries ``web_search_queries``, run_show calls
``research_current_context`` here to pull the *current, sourced* state of the
topic via Grok's web_search + x_search tools and injects it into the brief
prompt as a ``{current_research}`` block, which the prompt is instructed to
prioritize over the model's prior.

Always best-effort: any failure (no API key, network, tool error) returns an
empty string so the deep dive degrades to the static brief rather than
blocking the episode.
"""

from __future__ import annotations

import datetime as _dt
import logging
import os
import re as _re
from typing import List, Optional

logger = logging.getLogger(__name__)


def research_current_context(
    topic_title: str,
    queries: List[str],
    *,
    x_handles: Optional[List[str]] = None,
    today: Optional[_dt.date] = None,
    max_turns: int = 6,
) -> str:
    """Return a concise, source-attributed briefing on the CURRENT state of
    *topic_title*, or ``""`` if research is unavailable.

    Uses Grok's web_search and x_search tools so the result reflects what is
    being reported *today* (including discussion on X), not the model's
    training cutoff. The caller injects the result into the deep-dive brief
    prompt's ``{current_research}`` placeholder.
    """
    if not queries:
        return ""

    api_key = (os.getenv("GROK_API_KEY") or os.getenv("XAI_API_KEY") or "").strip()
    if not api_key:
        logger.warning(
            "Deep-dive research: no GROK_API_KEY/XAI_API_KEY — skipping live "
            "research (episode will rely on the static brief).",
        )
        return ""

    today = today or _dt.date.today()
    query_lines = "\n".join(f"  - {q}" for q in queries)
    prompt = (
        f"Today's date is {today.isoformat()}. Research the CURRENT, "
        f"up-to-the-day state of: {topic_title}.\n\n"
        f"Use web search AND X (Twitter) to find the LATEST verified "
        f"information available right now. Investigate specifically:\n"
        f"{query_lines}\n\n"
        f"Return a concise factual briefing (bullet points, NOT an essay) of "
        f"the current state. Requirements:\n"
        f"- Lead with the most recent, concrete, decision-relevant facts: "
        f"filing status (e.g. an S-1 or draft registration), reported "
        f"timeline/dates, valuation, deal structure, who is underwriting, "
        f"how retail could participate.\n"
        f"- Attribute EVERY claim to its source — name the publication or the "
        f"X account, with the date where possible (e.g. 'per Reuters, May 28' "
        f"or 'per @account').\n"
        f"- Mark anything rumored or unconfirmed as [UNCONFIRMED]. If sources "
        f"disagree, give both numbers and say so.\n"
        f"- Include the freshest analysis investors are publishing right now "
        f"(notable takes on X / from analysts), labeled as opinion.\n"
        f"- Do NOT speculate beyond the sources. If you cannot verify "
        f"something, say so explicitly rather than guessing.\n"
        f"- If you genuinely find nothing current, reply exactly: "
        f"NO_CURRENT_INFORMATION_FOUND\n"
    )

    try:
        from digests.xai_grok import grok_generate_text

        text, _meta = grok_generate_text(
            prompt=prompt,
            enable_web_search=True,
            enable_x_search=True,
            max_turns=max_turns,
        )
    except Exception as exc:  # noqa: BLE001 — research is best-effort
        logger.warning(
            "Deep-dive research failed for %r (%s) — falling back to static brief.",
            topic_title, exc,
        )
        return ""

    text = (text or "").strip()
    if not text or "NO_CURRENT_INFORMATION_FOUND" in text:
        logger.warning(
            "Deep-dive research returned no current information for %r.",
            topic_title,
        )
        return ""

    logger.info(
        "Deep-dive research: retrieved %d chars of current context for %r.",
        len(text), topic_title,
    )
    return text


# ---------------------------------------------------------------------------
# Nov 10 2026: a special's Sources come from the run's own research.
#
# A deep dive fetches no articles, and its prompts never asked for Source
# lines, so the Nov 9 publish guard ("an episode page with no Sources is
# never published") skipped the first special run under it (Flight 15,
# Nov 10). The research briefing above is the record this run read: every
# claim in it carries a link the search returned. When the digest cites no
# URL of its own, its Sources list is those links, and only those. Nothing
# is added from memory and nothing is added when the research is empty, so
# a special with no research still skips at the guard.
# ---------------------------------------------------------------------------

_URL_RE = _re.compile(r"https?://[^\s<>\"')\]]+")


def research_source_urls(research_block: str) -> List[str]:
    """Every http(s) URL in *research_block*, deduped, in order."""
    seen: set = set()
    out: List[str] = []
    for m in _URL_RE.finditer(research_block or ""):
        url = m.group(0).rstrip(".,;:")
        if url not in seen:
            seen.add(url)
            out.append(url)
    return out


def append_research_sources(digest_md: str, research_block: str) -> tuple:
    """Return ``(digest, n_added)``.

    Appends a ``## Sources`` list of the research briefing's own links when
    the digest would otherwise render with no Sources panel. A digest that
    already cites a URL is returned unchanged.
    """
    from engine.blog import _extract_source_urls

    if _extract_source_urls(digest_md or ""):
        return digest_md, 0
    urls = research_source_urls(research_block)
    if not urls:
        return digest_md, 0
    block = "\n\n## Sources\n\n" + "\n".join(f"- {u}" for u in urls) + "\n"
    return (digest_md or "").rstrip() + block, len(urls)
