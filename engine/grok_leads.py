"""Grok on X as a research desk for the deep-dive segments (Oct 11 2026).

@grok answers thousands of questions a day on X. Read as a SOURCE it is
unreliable by construction: the fetch asked for its "most recent posts" with
no topic, so what reached a show was whatever it happened to be replying to,
and the claims gate verified a fact against Grok having said it (SpaceX
Ep127's deep dive used a @grok reply's Saturn V and SLS dates; they happened
to be right, and nothing checked them).

Read as a LEAD it is valuable: the questions people put to Grok about a
show's subject are the questions a deep dive should answer, and Grok's
answer sketches the angle. So this module:

1. asks x_search for @grok's EXPLANATORY replies on the show's own topics
   (how / why / history / engineering / economics — never price calls,
   jokes, opinions on people);
2. grounds each lead with one web search for primary sources, keeps only
   sources whose PAGE was fetched, and drops any lead with fewer than
   ``min_sources`` of them;
3. renders the surviving leads as a writer-only block that names Grok's
   answer as unverified and requires every fact to come from the listed
   sources.

The lead's sources go to the claims gate's local texts (page text only, as
for narrative research); the @grok post itself is never an article, never a
Source line and never verification. Config: ``grok_leads`` in a show YAML.
Every failure returns no leads; the episode runs as before.
"""

from __future__ import annotations

import logging
import re
from typing import Callable, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

#: The block's heading — the model is told never to print it.
LEADS_HEADING = "DEEP-DIVE LEADS (writer-only input — never print this heading or quote it)"

_FIELD_RE = re.compile(r"^LEAD_(QUESTION|ANSWER|URL|DATE):\s*(.*)$")


#: Most x_search calls one lead request may make (one per subject).
MAX_SEARCHES = 8


def lead_subjects(topics: str) -> List[str]:
    """The show's beat as separate subjects: the part after a dash, split on
    commas ("Tesla engineering — batteries, Optimus, FSD" -> three). A topic
    string with no list stays one subject."""
    head, sep, tail = (topics or "").partition("—")
    items = [t.strip(" .;") for t in (tail if sep else head).split(",")]
    items = [re.sub(r"^and\s+", "", t).strip() for t in items if t.strip(" .;")]
    return items[:MAX_SEARCHES] or ([topics.strip()] if topics.strip() else [])


def build_lead_prompt(topics: str, max_leads: int, lookback_hours: int) -> str:
    # Oct 12 2026: one search over the whole beat came back NO_LEADS on all
    # four shows in ~7 s; a probe the same day found leads when the model
    # searched subject by subject (x_search over @grok's posts, 2-5 calls).
    # Grok answers thousands of narrow questions; a search for the whole
    # list matches none of them.
    subjects = lead_subjects(topics)
    subject_lines = "\n".join(f"- {s}" for s in subjects)
    return (
        f"Search X for replies posted by @grok in the last {lookback_hours} hours "
        f"in which Grok answers someone's question. The show's beat is: {topics}.\n\n"
        "Run a SEPARATE search for each subject below, using its own key "
        "terms — one search per subject, not one search for the whole list:\n"
        f"{subject_lines}\n\n"
        "Choose EXPLANATIONS only — how or why something works, its history, "
        "the engineering, physics or economics behind it, or a comparison of "
        "two programs. Skip price or date predictions, jokes, opinions about a "
        "person, roleplay, image requests, and anything off the subjects above.\n\n"
        "Return ONLY a structured list, one block per reply, separated by blank "
        "lines:\n\n"
        "LEAD_QUESTION: [the question Grok was answering, in one plain sentence]\n"
        "LEAD_ANSWER: [Grok's reply text]\n"
        "LEAD_URL: [https://x.com/grok/status/...]\n"
        "LEAD_DATE: [YYYY-MM-DD]\n\n"
        f"Up to {max_leads} replies, the most substantive first. If none "
        "qualify after searching every subject, return exactly: NO_LEADS\n"
    )


def parse_leads(text: str) -> List[Dict[str, str]]:
    """``LEAD_*`` blocks -> dicts. Incomplete blocks are dropped."""
    if not text or "NO_LEADS" in text:
        return []
    leads: List[Dict[str, str]] = []
    cur: Dict[str, str] = {}
    last = ""
    for raw in text.splitlines():
        line = raw.strip()
        m = _FIELD_RE.match(line)
        if m:
            key = m.group(1).lower()
            if key == "question" and cur:
                leads.append(cur)
                cur = {}
            cur[key] = m.group(2).strip()
            last = key
        elif line and last == "answer":
            cur["answer"] = (cur.get("answer", "") + " " + line).strip()
    if cur:
        leads.append(cur)
    out = []
    for lead in leads:
        q, a = lead.get("question", ""), lead.get("answer", "")
        if len(q.split()) >= 4 and len(a.split()) >= 15:
            out.append(lead)
    return out


def fetch_grok_leads(topics: str, *, max_leads: int = 2,
                     lookback_hours: int = 48,
                     generate: Optional[Callable] = None) -> List[Dict[str, str]]:
    """One x_search call restricted to @grok. Never raises."""
    if not (topics or "").strip() or max_leads <= 0:
        return []
    try:
        if generate is None:
            from digests.xai_grok import grok_generate_text as generate
        text, _meta = generate(
            prompt=build_lead_prompt(topics, max_leads * 2, lookback_hours),
            enable_x_search=True, x_handles=["grok"], max_turns=MAX_SEARCHES,
            cache_key="nerra-grok-leads",
        )
    except Exception as exc:  # noqa: BLE001 — leads are optional
        logger.warning("Grok leads: x_search failed (%s) — no leads today", exc)
        return []
    return parse_leads(text)[: max_leads * 2]


def ground_leads(
    leads: List[Dict[str, str]],
    *,
    max_leads: int = 2,
    min_sources: int = 2,
    research_max: int = 4,
    slug: str = "",
    research: Optional[Callable] = None,
    enrich: Optional[Callable] = None,
) -> Tuple[List[Dict], List[Dict]]:
    """Find primary sources for each lead; keep a lead only when at least
    *min_sources* of them have fetched PAGE text.

    Returns ``(kept_leads, sources)``; each kept lead carries ``sources``.
    *sources* is every kept source, for the claims gate's local texts.
    """
    if research is None:
        from engine.fetcher import fetch_topic_research_articles as research
    if enrich is None:
        from engine.article_text import enrich_articles_with_full_text as enrich
    from engine.hook_articles import normalize_hook_articles

    kept: List[Dict] = []
    all_sources: List[Dict] = []
    seen: set = set()
    for lead in leads:
        if len(kept) >= max_leads:
            break
        try:
            raw = research(lead.get("question", ""), lead.get("answer", ""),
                           max_results=research_max)
            found = normalize_hook_articles(raw, slug=slug)
        except Exception as exc:  # noqa: BLE001
            logger.warning("Grok leads: research failed (%s)", exc)
            continue
        found = [a for a in found
                 if "x.com/" not in (a.get("url") or "")
                 and "twitter.com/" not in (a.get("url") or "")
                 and (a.get("url") or "") not in seen]
        for art in found:
            art["source_kind"] = "research"
        try:
            enrich(found, max_articles=len(found))
        except Exception as exc:  # noqa: BLE001
            logger.warning("Grok leads: page fetch failed (%s)", exc)
        paged = [a for a in found if a.get("full_text_source") == "page"
                 and len(str(a.get("full_text") or "")) >= 300]
        if len(paged) < min_sources:
            logger.info("Grok lead dropped (%d fetched source(s), need %d): %s",
                        len(paged), min_sources, lead.get("question", "")[:90])
            continue
        seen.update(a.get("url") for a in paged)
        kept.append({**lead, "sources": paged})
        all_sources.extend(paged)
    return kept, all_sources


def render_leads_block(leads: List[Dict], *, excerpt_chars: int = 1200) -> str:
    """The writer-only prompt block, or "" when there are no leads."""
    if not leads:
        return ""
    parts = [
        LEADS_HEADING,
        "Questions people asked Grok on X about this show's subject in the last "
        "two days, each with primary sources found and fetched for it. Use ONE "
        "as the angle for the deep-dive section when it fits today's material "
        "better than the news does; otherwise ignore them. Grok's answer is "
        "UNVERIFIED and is never a source: never cite, quote or link x.com/grok, "
        "and never say Grok told us. Every fact the deep dive takes from a lead "
        "comes from that lead's sources, cited by their URL; a fact found only "
        "in Grok's answer is left out.",
    ]
    for i, lead in enumerate(leads, 1):
        parts.append(f"\nLead {i} — the question: {lead.get('question', '').strip()}")
        parts.append(f"Grok's answer (unverified, for the angle only): "
                     f"{lead.get('answer', '').strip()}")
        parts.append("Sources:")
        for src in lead.get("sources", []):
            text = re.sub(r"\s+", " ", str(src.get("full_text") or "")).strip()
            parts.append(f"- {src.get('title', '').strip()} — {src.get('url', '')}")
            parts.append(f"  Excerpt: {text[:excerpt_chars]}")
    return "\n".join(parts) + "\n"
