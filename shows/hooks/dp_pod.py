"""Pre-fetch hook for The DP Pod (The Do Positive Podcast).

Supplies ``{nerra_network_context}`` to both prompts:

* a compact catalog of the network's shows (so the hosts can describe a
  sibling show correctly),
* **FRESH ON THE NETWORK** — the sibling episodes that actually shipped in
  the last ~3 days (real titles from each show's summaries JSON), so every
  episode's network pointer names a real, current episode instead of a
  generic plug (operator direction, July 2026: follow-up episodes should
  regularly point listeners at network shows/episodes worth their queue),
* the most recent First Principles Daily brief as ready-to-discuss network
  material for thin-news days,
* the founders' notes (the only sanctioned source of personal host material),
* **Think Positive rotation memory** — the thinkers featured in recent
  episodes, mined from this show's own digests, so the mindset segment
  rotates instead of converging on one or two names.

Everything is best-effort: a failure returns a smaller context block, never
blocks the episode.
"""

from __future__ import annotations

import datetime
import json
import logging
import re
from pathlib import Path

logger = logging.getLogger(__name__)

_ROOT = Path(__file__).resolve().parent.parent.parent

# Compact, hand-curated catalog (digest dir, name, one-phrase pitch). Kept
# static so a registry hiccup can't garble the on-air description of a
# sibling show. Russian-language shows are deliberately absent — the DP
# audience is English-first. Age of AI joins once it has published episodes.
_NETWORK_SHOWS = [
    ("first_principles", "First Principles Daily", "reasons a thing should cost less — the magic wand number and the Idiot Index, one example a day"),
    ("fascinating_frontiers", "Fascinating Frontiers", "the day's space and science wonders, with a cosmic deep dive"),
    ("tesla_shorts_time", "Tesla Shorts Time", "the daily Tesla briefing — deliveries, FSD, energy, and the stock"),
    ("spacex", "SpaceX Daily", "engineering-first coverage of SpaceX as a public company"),
    ("planetterrian", "Planetterrian Daily", "science, longevity, and health research that changes how you live"),
    ("models_agents", "Models & Agents", "the daily AI briefing for people who build with it"),
    ("models_agents_beginners", "Models & Agents for Beginners", "the same AI news, explained from zero"),
    ("omni_view", "Omni View", "world news with every side steel-manned"),
    ("modern_investing", "Modern Investing Techniques", "markets and investing craft with a transparent track record"),
    ("env_intel", "Environmental Intelligence", "Canada's environmental policy and compliance brief"),
    ("unintended_consequences", "Unintended Consequences", "history's best-intentioned decisions and what they actually did"),
]

# Named thinkers the digest prompt licenses for Think Positive — used to
# mine rotation memory from recent digests. Keep in sync with the roster in
# shows/prompts/dp_pod_digest.txt (a superset is fine).
_THINKERS = [
    "Tony Robbins", "Simon Sinek", "Viktor Frankl", "Carol Dweck",
    "James Clear", "Angela Duckworth", "Mihaly Csikszentmihalyi",
    "Martin Seligman", "Stephen Covey", "Marcus Aurelius", "Epictetus",
    "Brené Brown", "Cal Newport", "Adam Grant", "Charlie Munger",
]


def _founders_notes() -> str:
    """Operator-supplied REAL material from Dan and Patrick.

    shows/dp_pod_founders_notes.md is the honest answer to the
    no-invented-memories rule: the model may use anything written there as
    the hosts' genuine stories and opinions. HTML comments are stripped; an
    empty file (or comments only) is a clean no-op.
    """
    try:
        path = _ROOT / "shows" / "dp_pod_founders_notes.md"
        if not path.exists():
            return ""
        text = re.sub(r"<!--.*?-->", "", path.read_text(encoding="utf-8"), flags=re.DOTALL)
        text = text.strip()
        if not text:
            return ""
        return (
            "FOUNDERS' NOTES (REAL material supplied by Dan and Patrick — "
            "safe to use as their genuine stories, opinions, and phrases; "
            "still never invent anything beyond it):\n" + text
        )
    except Exception as exc:
        logger.warning("dp_pod hook: founders notes unavailable (non-fatal): %s", exc)
        return ""


def _fresh_network_episodes(max_age_days: int = 3, today: datetime.date | None = None) -> str:
    """Real sibling episodes from the last *max_age_days* days.

    Reads each show's committed ``summaries_*.json`` for its latest entry —
    the on-air network pointer must name an actual current episode, never a
    generic show plug. Returns "" when nothing is fresh (never blocks).
    """
    today = today or datetime.date.today()
    lines = []
    for dir_name, display, _pitch in _NETWORK_SHOWS:
        try:
            candidates = sorted((_ROOT / "digests" / dir_name).glob("summaries_*.json"))
            if not candidates:
                continue
            data = json.loads(candidates[-1].read_text(encoding="utf-8"))
            summaries = data.get("summaries") or []
            if not summaries:
                continue
            # Newest entry regardless of file ordering (the pipeline
            # prepends newest-first; be robust to either convention).
            latest = max(summaries, key=lambda e: str(e.get("date", "")))
            ep_date = datetime.date.fromisoformat(str(latest.get("date", ""))[:10])
            age = (today - ep_date).days
            if age < 0 or age > max_age_days:
                continue
            title = str(latest.get("episode_title", "")).strip()
            # "Ep 12: <hook>" → keep the hook part for the pointer.
            title = re.sub(r"^Ep\s*\d+:\s*", "", title)
            if not title:
                continue
            when = "today" if age == 0 else ("yesterday" if age == 1 else f"{age} days ago")
            lines.append(f'- {display} ({when}): "{title[:160]}"')
        except Exception:
            continue
    if not lines:
        return ""
    return (
        "FRESH ON THE NETWORK (real sibling episodes from the last few days "
        "— when you point listeners at a show, point at one of THESE actual "
        "episodes and say what it covers; never invent an episode):\n"
        + "\n".join(lines)
    )


def _recent_think_positive_thinkers(max_digests: int = 8) -> str:
    """Thinkers featured in recent Think Positive segments (rotation memory).

    Mined from this show's own committed digests, newest first. Returns ""
    before enough history exists.
    """
    try:
        md_files = sorted((_ROOT / "digests" / "dp_pod").glob("*.md"), reverse=True)
        seen: list[str] = []
        for md in md_files[:max_digests]:
            text = md.read_text(encoding="utf-8")
            m = re.search(r"###\s*Think Positive\s*\n(.*?)(?:\n[━#]|\Z)", text, re.DOTALL)
            if not m:
                continue
            section = m.group(1)
            for name in _THINKERS:
                if name in section and name not in seen:
                    seen.append(name)
        if not seen:
            return ""
        return (
            "THINK POSITIVE — RECENTLY FEATURED THINKERS (newest first; do "
            "NOT reuse any of these today — rotate to someone the show "
            "hasn't heard from lately): " + ", ".join(seen)
        )
    except Exception as exc:
        logger.warning("dp_pod hook: thinker history unavailable (non-fatal): %s", exc)
        return ""


def _previous_lever_for_dispatch(max_lookback: int = 5) -> str:
    """The most recent aired Lever — for honest Dispatch continuity.

    Ep2/Ep4 invented a 'heat-pump filter swap' callback that never aired.
    Inject the real prior Lever so the digest can only point at something
    that actually happened. Returns "" before Episode 2.
    """
    try:
        md_files = sorted(
            (_ROOT / "digests" / "dp_pod").glob("DP_Pod_Ep*.md"),
            reverse=True,
        )
        for md in md_files[:max_lookback]:
            text = md.read_text(encoding="utf-8")
            m = re.search(
                r"###\s*The Lever\s*\n(.*?)(?:\n[━#]|\Z)", text, re.DOTALL,
            )
            if not m:
                continue
            lever = re.sub(r"\s+", " ", m.group(1)).strip()
            # Drop trailing Source: lines if present.
            lever = re.split(r"\bSource:\s*", lever, maxsplit=1)[0].strip()
            if len(lever) < 40:
                continue
            ep_m = re.search(r"Ep(\d+)", md.name)
            ep_label = f"Ep{int(ep_m.group(1)):03d}" if ep_m else md.stem
            # Keep the first ~40 words so the digest can quote it briefly.
            words = lever.split()
            short = " ".join(words[:40]) + ("…" if len(words) > 40 else "")
            return (
                "PREVIOUS LEVER (the most recent aired action — when the "
                "Dispatch has no listener mail, point at THIS exact lever "
                "only; never invent a different past action like heat pumps "
                f"or filters that did not air): [{ep_label}] {short}"
            )
        return ""
    except Exception as exc:
        logger.warning("dp_pod hook: previous lever unavailable (non-fatal): %s", exc)
        return ""


def _latest_first_principles_brief() -> str:
    """Hook + short excerpt of the newest First Principles Daily digest.

    The operator can PIN discussion-anchor material instead: if
    shows/dp_pod_debut_anchor.md exists with content, it wins over the
    latest FP digest — paste any Nerra material there to hand-pick what
    the hosts discuss.
    """
    try:
        pinned = _ROOT / "shows" / "dp_pod_debut_anchor.md"
        if pinned.exists():
            text = re.sub(
                r"<!--.*?-->", "", pinned.read_text(encoding="utf-8"),
                flags=re.DOTALL,
            ).strip()
            if text:
                words = text.split()
                return (
                    "Pinned Nerra Network anchor material (operator-selected):\n  "
                    + " ".join(words[:900])
                )
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
    catalog = "\n".join(f"- {name} — {pitch}" for _dir, name, pitch in _NETWORK_SHOWS)
    sections = [
        "THE NERRA NETWORK (your sibling shows — the network is ad-free and "
        "these are the club's library; describe them with these pitches, "
        "never read this list aloud):",
        catalog,
    ]
    fresh = _fresh_network_episodes()
    if fresh:
        sections.append("")
        sections.append(fresh)
    fp_brief = _latest_first_principles_brief()
    if fp_brief:
        sections.append("")
        sections.append(fp_brief)
    thinkers = _recent_think_positive_thinkers()
    if thinkers:
        sections.append("")
        sections.append(thinkers)
    prev_lever = _previous_lever_for_dispatch()
    if prev_lever:
        sections.append("")
        sections.append(prev_lever)
    notes = _founders_notes()
    if notes:
        sections.append("")
        sections.append(notes)
    return {"nerra_network_context": "\n".join(sections)}
