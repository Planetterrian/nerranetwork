"""Curriculum spotlights for education shows that still fetch news (Sep 2026).

Peptides Weekly and Longevity Weekly run a normal news week PLUS one
spotlight from a planned curriculum (docs/new_shows_plan_2026_09_22.md
§4.3). That is neither narrative mode (which skips the news fetch) nor a
deep dive, so the spotlight comes from the show's hook: the next
unproduced entry of ``shows/curricula/<slug>.yaml`` (same format as the
topic queues, so engine.topic_queue does the reading and writing).

Curricula live outside ``shows/topic_queues/`` on purpose: that directory
is the narrative shows' queue, swept by the restock automation and its
runway guards. A curriculum is hand-planned and is not auto-restocked.
"""

from __future__ import annotations

import datetime as _dt
import logging
from pathlib import Path
from typing import Optional

from engine.topic_queue import mark_topic_produced, pick_next_topic

logger = logging.getLogger(__name__)

ROOT = Path(__file__).resolve().parent.parent


def curriculum_path(slug: str, root: Path | None = None) -> Path:
    return (root or ROOT) / "shows" / "curricula" / f"{slug}.yaml"


def next_spotlight(slug: str, root: Path | None = None) -> Optional[dict]:
    path = curriculum_path(slug, root)
    if not path.exists():
        logger.warning("%s: no curriculum at %s", slug, path)
        return None
    return pick_next_topic(path)


def spotlight_block(topic: Optional[dict], label: str) -> str:
    """Digest-prompt block naming this week's spotlight, or a fallback rule."""
    if not topic:
        return (
            f"### THIS WEEK'S {label.upper()} (instruction — do not include in output)\n"
            "The curriculum is empty this week: choose the spotlight subject "
            "from the week's most-covered item above, and say plainly in the "
            "section what is and is not established about it."
        )
    return (
        f"### THIS WEEK'S {label.upper()} (instruction — do not include in output)\n"
        f"Subject: {topic['title']}\n"
        f"Brief: {topic['brief']}\n"
        "Write the spotlight on exactly this subject. The brief is direction, "
        "not facts: every factual claim still needs a source from the articles "
        "above or the claims ledger, and anything you cannot source is left out."
    )


def mark_spotlight_done(slug: str, topic_id: str, episode_num: int,
                        root: Path | None = None) -> bool:
    return mark_topic_produced(curriculum_path(slug, root), topic_id,
                               episode_num, _dt.date.today().isoformat())


def health_weekly_pre_fetch(config, slug: str, label: str, *, sibling=None) -> tuple:
    """Shared pre_fetch for the two health weeklies.

    Returns ``(context, topic)``: the hook context dict (narrative memory,
    ``hook_context`` block, Europe PMC ``articles`` for the spotlight) and
    the selected curriculum topic (or None) so the hook can mark it
    produced in post_generate. ``sibling`` is an optional
    ``(name, digest_dir, days, lens)`` for engine.sibling_coverage.
    """
    from engine import show_memory
    from engine.europe_pmc import abstracts_for

    context = show_memory.memory_pre_fetch(config, slug)
    parts = []
    topic = None
    try:
        topic = next_spotlight(slug)
    except Exception as exc:  # noqa: BLE001
        logger.warning("%s: spotlight selection failed (non-fatal): %s", slug, exc)
    parts.append(spotlight_block(topic, label))
    if topic and topic.get("search"):
        try:
            arts = abstracts_for(str(topic["search"]))
            if arts:
                context["articles"] = arts
                logger.info("%s: %d Europe PMC abstract(s) for the spotlight", slug, len(arts))
        except Exception as exc:  # noqa: BLE001
            logger.warning("%s: Europe PMC fetch failed (non-fatal): %s", slug, exc)
    if sibling:
        try:
            from engine.sibling_coverage import sibling_block
            name, digest_dir, days, lens = sibling
            sib = sibling_block(name, digest_dir, days=days, lens=lens)
            if sib:
                parts.append(sib)
        except Exception as exc:  # noqa: BLE001
            logger.warning("%s: sibling block failed (non-fatal): %s", slug, exc)
    context["hook_context"] = "\n\n".join(p for p in parts if p)
    return context, topic
