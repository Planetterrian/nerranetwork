"""Pre-fetch hook for The DP Pod (The Do Positive Podcast).

Supplies ``{nerra_network_context}`` to both prompts: a compact catalog of
the network's shows (so the hosts can point listeners at a sibling show when
a story overlaps its beat) plus the most recent First Principles Daily brief
(hook + excerpt) as ready-to-discuss network material — the debut episode's
anchor discussion, and a recurring well for any thin-news day. Everything is
best-effort: a failure returns a smaller context block, never blocks the
episode.
"""

from __future__ import annotations

import logging
import re
from pathlib import Path

logger = logging.getLogger(__name__)

_ROOT = Path(__file__).resolve().parent.parent.parent

# Compact, hand-curated catalog (name — one-phrase pitch). Kept static so a
# registry hiccup can't garble the on-air description of a sibling show.
_NETWORK_SHOWS = [
    ("First Principles Daily", "reasons a thing should cost less — the magic wand number and the Idiot Index, one example a day"),
    ("Fascinating Frontiers", "the day's space and science wonders, with a cosmic deep dive"),
    ("Tesla Shorts Time", "the daily Tesla briefing — deliveries, FSD, energy, and the stock"),
    ("SpaceX Daily", "engineering-first coverage of SpaceX as a public company"),
    ("Planetterrian Daily", "science, longevity, and health research that changes how you live"),
    ("Models & Agents", "the daily AI briefing for people who build with it"),
    ("Models & Agents for Beginners", "the same AI news, explained from zero"),
    ("Omni View", "world news with every side steel-manned"),
    ("Modern Investing Techniques", "markets and investing craft with a transparent track record"),
    ("Environmental Intelligence", "Canada's environmental policy and compliance brief"),
    ("Unintended Consequences", "history's best-intentioned decisions and what they actually did"),
]


def _latest_first_principles_brief() -> str:
    """Hook + short excerpt of the newest First Principles Daily digest."""
    try:
        fp_dir = _ROOT / "digests" / "first_principles"
        md_files = sorted(fp_dir.glob("*.md"))
        if not md_files:
            return ""
        text = md_files[-1].read_text(encoding="utf-8")
        hook = ""
        m = re.search(r"\*\*HOOK:\*\*\s*(.+)", text)
        if m:
            hook = m.group(1).strip()
        # First ~120 words of body prose after the hook line as the excerpt.
        body = text[m.end():] if m else text
        body = re.sub(r"[━#*]+", " ", body)
        words = body.split()
        excerpt = " ".join(words[:120])
        parts = ["Most recent First Principles Daily episode:"]
        if hook:
            parts.append(f'  Hook: "{hook}"')
        if excerpt:
            parts.append(f"  Excerpt: {excerpt}…")
        return "\n".join(parts)
    except Exception as exc:
        logger.warning("dp_pod hook: FP brief unavailable (non-fatal): %s", exc)
        return ""


def pre_fetch(config, *, episode_num=None, today_str=None) -> dict:
    catalog = "\n".join(f"- {name} — {pitch}" for name, pitch in _NETWORK_SHOWS)
    sections = [
        "THE NERRA NETWORK (your sibling shows — reference at most ONE per "
        "episode, only when a story genuinely overlaps its beat; name the "
        "show naturally, never read this list aloud):",
        catalog,
    ]
    fp_brief = _latest_first_principles_brief()
    if fp_brief:
        sections.append("")
        sections.append(fp_brief)
    return {"nerra_network_context": "\n".join(sections)}
