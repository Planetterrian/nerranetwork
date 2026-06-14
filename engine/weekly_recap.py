"""Sunday weekly-recap digest synthesis.

When a daily show ticks on a Sunday with ``weekly_recap_on_sunday: true``
in its YAML, the runner short-circuits the news-fetch + daily-digest
stages and instead asks this module to produce a digest-shaped
markdown blob synthesised from the past 7 days of that show's
episodes. The rest of the pipeline (podcast script generation, TTS,
publish) runs unchanged on this synthetic digest.

Why digest-shaped, not direct podcast-script: the existing podcast
prompt knows how to turn a digest into ~15-minute spoken narration.
Re-using that path keeps the recap feel consistent with daily
episodes rather than introducing a parallel "weekly podcast" prompt
ladder for every show. Per-show flavour can still be added by
appending a brief "RECAP MODE" instruction to the podcast prompt
when the runner detects Sunday — but the v1 cut keeps prompts
unchanged.
"""

from __future__ import annotations

import logging
import re
from datetime import date, timedelta
from typing import Optional

logger = logging.getLogger(__name__)


# Patterns that must not survive into a per-episode recap body. These come
# from the source daily digests (a "Read more (sources)" line, raw or markdown
# links, a real-time stock-price header) and were leaking verbatim into the
# Sunday recap newsletter/blog before being scrubbed (June 2026).
_HTML_TAG_RE = re.compile(r"</?[a-zA-Z][^>]*>")
_MD_LINK_RE = re.compile(r"\[([^\]]+)\]\((?:[^)]+)\)")
_BARE_URL_RE = re.compile(r"https?://\S+")
_READ_MORE_RE = re.compile(r"(?im)^\s*(?:\*+\s*)?read more.*$")
_PRICE_HDR_RE = re.compile(
    r"(?im)^\s*\*{0,2}\s*(?:REAL-?TIME\s+)?TSLA(?:\s+today)?\b.*$"
)


# Matches a properly-attributed source citation: ``Source: [label](url)`` or
# a bare ``Source: https://…``. The published blog/summary/RSS all render these
# as real links, so the weekly recap must PRESERVE them (transparent sourcing),
# not strip them — the June-2026 strip was the cause of the unsourced Sunday blog.
_SOURCE_CITE_RE = re.compile(
    r"Source:\s*(?:\[([^\]]+)\]\((https?://[^)\s]+)\)|(https?://[^)\s]+))",
    re.IGNORECASE,
)


def _sanitize_recap_body(text: str, keep_links: bool = True) -> str:
    """Clean a per-episode recap body of residue that reads badly aloud while
    PRESERVING proper markdown source citations so the blog/summary stay sourced.

    The recap scaffold feeds the podcast LLM, the blog, and the summary/RSS. Raw
    HTML anchors, "Read more" lines, stock-price headers, and bare URLs read as
    garbage and are removed. Markdown links (``[label](url)``) are kept by
    default so the published surfaces render clickable sources — the spoken
    script omits them because the host framing instructs the LLM not to read
    URLs aloud (same contract as a daily digest). Pass ``keep_links=False`` for
    plain-text contexts (e.g. a story title line).
    """
    if not text:
        return text
    # Protect markdown links from the bare-URL strip (their URLs would match).
    stash: dict[str, str] = {}

    def _hide(m):
        key = f"\0L{len(stash)}\0"
        stash[key] = m.group(0)
        return key

    if keep_links:
        text = _MD_LINK_RE.sub(_hide, text)
    else:
        text = _MD_LINK_RE.sub(r"\1", text)  # [Google News](url) -> Google News
    text = _HTML_TAG_RE.sub("", text)        # drop <a ...>, </a>, etc.
    text = _READ_MORE_RE.sub("", text)       # drop "Read more (sources): ..."
    text = _PRICE_HDR_RE.sub("", text)       # drop "REAL-TIME TSLA price:" lines
    text = _BARE_URL_RE.sub("", text)        # drop any leftover bare URLs
    for key, val in stash.items():           # restore protected markdown links
        text = text.replace(key, val)
    # Collapse the blank lines the removals leave behind.
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = re.sub(r"[ \t]{2,}", " ", text)
    return text.strip()


def _extract_sources(digest_md: str) -> list[tuple[str, str]]:
    """Pull every ``Source:`` citation from an episode digest as (label, url)
    pairs (label falls back to the publisher domain for bare-URL citations)."""
    out: list[tuple[str, str]] = []
    for m in _SOURCE_CITE_RE.finditer(digest_md or ""):
        label, url_md, url_bare = m.group(1), m.group(2), m.group(3)
        url = url_md or url_bare
        if not url:
            continue
        if not label:
            # Derive a readable label from the domain for bare-URL citations.
            label = re.sub(r"^www\.", "", url.split("//", 1)[-1].split("/", 1)[0])
        out.append((label.strip(), url.strip()))
    return out


def build_weekly_recap_digest(
    show_slug: str,
    show_name: str,
    week_ending: date,
    articles: Optional[list] = None,
) -> Optional[str]:
    """Build a digest-shaped markdown summary of the past 7 days for
    *show_slug*. Returns ``None`` if the content lake has fewer than
    two episodes in window (recap with one or zero episodes is not
    meaningful — the runner falls back to a normal daily fetch).

    The output is intentionally minimal and uses the same surface
    structure as a daily digest (title heading, hook, "Top Stories"
    list with title + summary per item) so the existing podcast
    prompt can ingest it without any branching.
    """
    try:
        from engine.content_lake import query_show_range
    except Exception as exc:  # pragma: no cover — content lake optional in tests
        logger.warning(
            "weekly_recap: content lake unavailable (%s) — falling back",
            exc,
        )
        return None

    start_date = (week_ending - timedelta(days=6)).isoformat()
    end_date = week_ending.isoformat()

    try:
        episodes = query_show_range(show_slug, start_date, end_date) or []
    except Exception as exc:  # pragma: no cover
        logger.warning("weekly_recap: query_show_range failed (%s)", exc)
        return None

    if len(episodes) < 2:
        logger.info(
            "weekly_recap: only %d episode(s) in window for %s — falling back",
            len(episodes), show_slug,
        )
        return None

    # Sort by date ascending so the recap reads chronologically.
    episodes = sorted(
        episodes,
        key=lambda ep: (ep.get("date") or "", ep.get("episode_num") or 0),
    )

    # Headline: a recap-flavoured one-liner that signals this isn't a normal
    # daily WITHOUT reciting the date range (operator feedback: the formulaic
    # "from <start> to <end>" open reads like a database query, not a digest).
    # The podcast prompt turns this hook into the spoken opener, so it stays
    # intuitive and theme-forward.
    # The H1/blog title carries the week-ending date so each recap is a unique,
    # archivable page (identical titles every week kill per-episode SEO). This
    # is the WRITTEN title only — the spoken intro is driven by the hook +
    # framing below and stays date-free/intuitive per operator feedback.
    week_title_date = f"{week_ending.strftime('%B')} {week_ending.day}, {week_ending.year}"
    title = f"# {show_name} — Weekly Recap (Week of {week_title_date})"
    hook = (
        "**HOOK:** The week's biggest developments, pulled together — "
        "what actually moved, why it matters, and what to watch next."
    )

    # Each episode contributes a "Top Story" entry AND its source citations.
    # We collect every source across the week so the published recap (blog +
    # summary + RSS) is fully, transparently sourced — the daily contract.
    items: list[str] = []
    sources: list[tuple[str, str]] = []
    seen_urls: set[str] = set()
    for idx, ep in enumerate(episodes, start=1):
        ep_num = ep.get("episode_num") or "?"
        ep_date = ep.get("date") or ""
        ep_hook = (ep.get("hook") or "").strip()
        digest_md = (ep.get("digest_md") or "").strip()

        # Harvest sources from the FULL digest (not just the trimmed body) so
        # the week's Sources section is comprehensive even when prose is cut.
        for label, url in _extract_sources(digest_md):
            if url not in seen_urls:
                seen_urls.add(url)
                sources.append((label, url))

        # Pull the first 3 substantive paragraphs of the canonical digest as
        # the body — more than before so the host has material for a genuine
        # deep dive, capped ~1500 chars to stay within the LLM context window
        # across a full 7-episode week. Source citations are PRESERVED.
        paragraphs = [p.strip() for p in digest_md.split("\n\n") if p.strip()]
        body_paragraphs: list[str] = []
        for p in paragraphs:
            if (
                p.startswith("#")
                or p.startswith(("**HOOK:", "**Date:", "**Дата:",
                                 "**REAL-TIME TSLA price:", "**TSLA today:",
                                 "**Theme:", "**Тема:", "**ЗАГОЛОВОК:"))
            ):
                continue
            body_paragraphs.append(p)
            if len(body_paragraphs) >= 3:
                break
        body = _sanitize_recap_body("\n\n".join(body_paragraphs))[:1500]

        title_line = _sanitize_recap_body(ep_hook, keep_links=False) or f"Episode {ep_num}"
        items.append(
            f"{idx}. **From Ep {ep_num} ({ep_date}): {title_line}**\n"
            f"   {body}"
        )

    # NEW: fresh developments. On Sunday the pipeline still fetches the day's
    # news (the recap just normally ignores it). Surfacing the freshest,
    # not-yet-covered items lets the weekly episode break genuinely new ground
    # instead of only rehashing — each carried with its source link.
    fresh_items: list[str] = []
    for art in (articles or [])[:6]:
        if not isinstance(art, dict):
            continue
        a_title = (art.get("title") or "").strip()
        a_url = (art.get("url") or art.get("link") or "").strip()
        if not a_title:
            continue
        a_src = (art.get("source") or "").strip()
        if a_url and a_url not in seen_urls:
            seen_urls.add(a_url)
            label = a_src or re.sub(r"^www\.", "", a_url.split("//", 1)[-1].split("/", 1)[0])
            sources.append((label, a_url))
        cite = f" Source: [{a_src or 'link'}]({a_url})" if a_url else ""
        fresh_items.append(f"- {a_title}{cite}")

    # The published "Sources" section — every citation, deduplicated. This is
    # what guarantees the recap blog/summary is sourced as transparently as a
    # daily episode (the bug this fix closes).
    sources_block = ""
    if sources:
        lines = [f"- [{label}]({url})" for label, url in sources]
        sources_block = "## Sources\n" + "\n".join(lines)

    parts: list[str] = [
        title,
        hook,
        "━━━━━━━━━━━━━━━━━━━━",
        "### This Week's Top Stories",
        *items,
    ]
    if fresh_items:
        parts += [
            "━━━━━━━━━━━━━━━━━━━━",
            "### Fresh this week (not yet covered)",
            "\n".join(fresh_items),
        ]
    parts += [
        "━━━━━━━━━━━━━━━━━━━━",
        "## Recap framing for the host",
        (
            "This is a Sunday weekly recap — a 'where we are now' episode, "
            "NOT a flat list of news items, and NOT a database-style readout. "
            "Open INTUITIVELY: lead with the single most important theme or "
            "development of the week in a natural, conversational hook — do "
            "NOT open by reciting the calendar date range ('from June 8th to "
            "June 14th'). Then weave the stories into one coherent narrative "
            "built on these beats:\n\n"
            "1. GO DEEP ON THE BIGGEST EVENTS — identify the 2-3 single most "
            "consequential developments of the week and give each a genuine "
            "deep-dive segment: the full context, the mechanism, the "
            "competing interpretations, and the second-order implications. "
            "Do not treat every story equally — the biggest events earn real "
            "airtime; minor items get a sentence or a quick round-up.\n"
            "2. CONTINUITY — situate each major thread in its ongoing arc so a "
            "returning listener feels the through-line. Use natural language: "
            "'since we last covered...', 'the ongoing story of...', 'where "
            "the story stands now'. Group related threads rather than walking "
            "episode by episode.\n"
            "3. NEW GROUND — if a 'Fresh this week' section is present above, "
            "work those genuinely new developments into the narrative so the "
            "recap advances the story rather than only looking backward. "
            "Attribute them to their sources; never invent details beyond "
            "what the source supports.\n"
            "4. STAKES — for each major thread, say plainly WHY THIS MATTERS "
            "for the listener and the practical consequence. Don't just "
            "report that something happened; explain why they should care.\n"
            "5. SPECIFICS — keep the concrete numbers from the week (prices, "
            "percentages, counts). Specific figures make a recap credible.\n"
            "6. FORWARD LOOK — close by naming the single most consequential "
            "development, an explicit 'what to watch for next week' beat, the "
            "biggest open question heading into next week, and one practical "
            "takeaway listeners can use.\n\n"
            "SOURCING: the stories above carry their source citations and a "
            "Sources list follows — these exist for the written blog/show "
            "notes and must stay accurate, but NEVER read URLs or 'Source: ...' "
            "links aloud in the spoken script. Reference outlets by name in "
            "speech where natural ('according to NASA', 'Ars Technica reported').\n\n"
            "Keep the same voice and pacing as a daily episode, and give the "
            "week the depth it deserves — this is a full-length episode, not a "
            "quick skim."
        ),
    ]

    recap = "\n\n".join(parts)

    # TST-specific enhancement: inject narrative memory framing when available.
    # This is intentionally best-effort (the narrative tracker lives in the
    # gitignored content lake + digests/ on the runner). If anything fails we
    # just ship the plain recap.
    if show_slug == "tesla":
        try:
            from engine import tesla_memory
            from pathlib import Path as _Path
            tracker = tesla_memory.load_narrative_tracker(
                _Path("digests/tesla_shorts_time")
            )
            narrative_block = tesla_memory.build_narrative_status_block(tracker)
            if narrative_block:
                recap += (
                    "\n\n" + narrative_block +
                    "\n\nUse the narrative status above to highlight meaningful "
                    "progress or open questions across the week."
                )
        except Exception as exc:
            # Still best-effort, but never silent: a corrupt tracker means
            # the Sunday recap ships without its narrative framing.
            logger.warning(
                "Tesla narrative injection into weekly recap failed "
                "(recap ships without it): %s", exc,
            )

    # Phase 3: same narrative framing for the generalized memory shows
    # (Models & Agents, Fascinating Frontiers, Planetterrian). Best-effort.
    else:
        try:
            from pathlib import Path as _Path
            from engine import show_memory
            mcfg = show_memory.get_config(show_slug)
            if mcfg is not None:
                tracker = show_memory.load_narrative_tracker(
                    _Path("digests") / show_slug, mcfg
                )
                narrative_block = show_memory.build_narrative_status_block(tracker, mcfg.label)
                if narrative_block:
                    recap += (
                        "\n\n" + narrative_block +
                        "\n\nUse the narrative status above to highlight meaningful "
                        "progress or open questions across the week."
                    )
        except Exception as exc:
            logger.warning(
                "Narrative injection into weekly recap failed for %s "
                "(recap ships without it): %s", show_slug, exc,
            )

    # The Sources block is appended LAST (after host framing + narrative memory)
    # so the runner can lift it verbatim onto the republished recap digest —
    # the published blog/summary/RSS stay transparently sourced even though the
    # spoken script (which becomes the rest of the published digest) carries no
    # URLs. The "## Sources" marker is the agreed handoff between the two files.
    if sources_block:
        recap += "\n\n━━━━━━━━━━━━━━━━━━━━\n\n" + sources_block

    return recap
