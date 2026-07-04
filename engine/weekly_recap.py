"""Weekly-summary segment synthesis.

Sunday episodes used to short-circuit into a FULL weekly-recap episode
(the news fetch + daily digest were skipped and the whole show became a
"week in review"). That mode was retired in July 2026: Sunday is now a
normal daily episode that simply includes ONE short "week in review"
*segment*. This module builds that compact segment.

When a daily show ticks on a Sunday with ``weekly_summary_segment: true``
in its YAML, the runner generates the ordinary daily digest AND asks this
module for a small host-instruction block summarising the past 7 days of
that show's episodes (pulled from the content lake). That block is appended
to the *podcast-only* copy of the digest (never the published digest), so
the host weaves a brief weekly recap into the episode without any of the
instruction text leaking into the blog / RSS / newsletter.

Returning ``None`` (content lake unavailable, or fewer than two episodes in
the trailing week) is the clean no-op: the runner ships a plain daily
episode with no weekly-summary segment.
"""

from __future__ import annotations

import logging
import re
from datetime import date, timedelta
from typing import Optional

logger = logging.getLogger(__name__)


# Patterns that must not survive into the weekly-summary segment. These come
# from the source daily digests (a "Read more (sources)" line, raw or markdown
# links, a real-time stock-price header) and would read as garbage aloud.
_HTML_TAG_RE = re.compile(r"</?[a-zA-Z][^>]*>")
_MD_LINK_RE = re.compile(r"\[([^\]]+)\]\((?:[^)]+)\)")
_BARE_URL_RE = re.compile(r"https?://\S+")
_READ_MORE_RE = re.compile(r"(?im)^\s*(?:\*+\s*)?read more.*$")
_PRICE_HDR_RE = re.compile(
    r"(?im)^\s*\*{0,2}\s*(?:REAL-?TIME\s+)?TSLA(?:\s+today)?\b.*$"
)


def _sanitize_recap_body(text: str, keep_links: bool = True) -> str:
    """Clean a per-episode hook/body of residue that reads badly aloud.

    Raw HTML anchors, "Read more" lines, stock-price headers, and bare URLs
    read as garbage and are removed. Markdown links (``[label](url)``) are
    kept by default; pass ``keep_links=False`` for plain-text contexts (e.g. a
    story-title line) so ``[Google News](url)`` collapses to ``Google News``.
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


def build_weekly_summary_segment(
    show_slug: str,
    show_name: str,
    week_ending: date,
) -> Optional[str]:
    """Build a COMPACT weekly-summary segment for a Sunday episode.

    Unlike the retired full weekly-recap mode (which replaced the entire
    Sunday episode), this returns a short host-instruction block that the
    runner appends to the *podcast-only* copy of the daily digest so the host
    weaves ONE brief "week in review" segment into an otherwise-normal daily
    episode.

    Returns ``None`` when the content lake is unavailable or has fewer than
    two episodes in the trailing 7-day window (no meaningful week to
    summarise) — the runner then ships a plain daily episode with no segment.
    """
    try:
        from engine.content_lake import query_show_range
    except Exception as exc:  # pragma: no cover — content lake optional in tests
        logger.warning(
            "weekly_summary: content lake unavailable (%s) — no segment", exc,
        )
        return None

    start_date = (week_ending - timedelta(days=6)).isoformat()
    end_date = week_ending.isoformat()

    try:
        episodes = query_show_range(show_slug, start_date, end_date) or []
    except Exception as exc:  # pragma: no cover
        logger.warning("weekly_summary: query_show_range failed (%s)", exc)
        return None

    if len(episodes) < 2:
        logger.info(
            "weekly_summary: only %d episode(s) in window for %s — no segment",
            len(episodes), show_slug,
        )
        return None

    # Sort by date ascending so the highlights read chronologically.
    episodes = sorted(
        episodes,
        key=lambda ep: (ep.get("date") or "", ep.get("episode_num") or 0),
    )

    # Deterministic "biggest events" signal: an entity covered on multiple days
    # is, by definition, the week's most consequential ongoing thread. Counting
    # per-episode recurrence (from the content lake's stored entities) gives the
    # host concrete grounding for the segment instead of leaving "what was
    # biggest" entirely to LLM judgment.
    from collections import Counter
    _ent_days: Counter = Counter()
    for ep in episodes:
        ents = ep.get("entities") or []
        if isinstance(ents, list):
            for ent in {str(e).strip() for e in ents if str(e).strip()}:
                _ent_days[ent] += 1
    recurring_threads = [ent for ent, n in _ent_days.most_common() if n >= 2][:4]

    # One tight highlight line per episode (hook only — no body paragraphs; this
    # is a segment, not a recap episode).
    highlights: list[str] = []
    for ep in episodes:
        ep_num = ep.get("episode_num") or "?"
        ep_date = ep.get("date") or ""
        ep_hook = _sanitize_recap_body((ep.get("hook") or "").strip(), keep_links=False)
        if not ep_hook:
            continue
        highlights.append(f"- Ep {ep_num} ({ep_date}): {ep_hook}")
    highlights = highlights[:7]
    if not highlights:
        return None

    parts: list[str] = [
        "━━━━━━━━━━━━━━━━━━━━",
        "## WEEKLY SUMMARY SEGMENT (host instructions — do not read this heading aloud)",
        (
            "Today is Sunday. This is a NORMAL daily episode built on today's "
            "news above — that stays the main focus. In ADDITION, weave in ONE "
            "short 'week in review' segment (about 45-90 seconds, 3-5 sentences) "
            "at a natural spot: a brief beat just after the intro, or right "
            "before the close. In it, catch listeners up on the 2-3 biggest "
            "threads from the PAST WEEK and where each stands now, in a warm "
            "'here's what you may have missed' tone. Keep it TIGHT — this is a "
            "segment, not the whole episode. Do NOT recite a calendar date "
            "range, do NOT re-report today's stories inside it, and never read "
            "URLs aloud."
        ),
    ]
    if recurring_threads:
        parts.append(
            "The week's biggest recurring threads (each appeared across 2+ "
            "episodes this week — strongest candidates for the segment): "
            + ", ".join(recurring_threads) + "."
        )
    parts.append("This week's episode highlights (for your reference):")
    parts.append("\n".join(highlights))

    return "\n\n".join(parts)
