"""Longevity Weekly hooks (Sep 2026, docs/new_shows_plan_2026_09_22.md §4.3).

pre_fetch: narrative memory; this week's curriculum spotlight
(shows/curricula/longevity.yaml, engine/curriculum.py); real Europe PMC
abstracts for the spotlight as hook ARTICLES, so every evidence claim can
cite a paper the pipeline already holds and the claims gate can verify it
without HTTP; and, for Longevity, what Planetterrian Daily covered this week.
post_generate: marks the spotlight produced (committed by run-show.yml's
success path only, so a skipped episode re-picks it) and mines themes.
"""

from __future__ import annotations

import logging

from engine import show_memory
from engine.curriculum import health_weekly_pre_fetch, mark_spotlight_done

logger = logging.getLogger(__name__)

_SLUG = "longevity"
_LABEL = "Mechanism of the Week"
_SIBLING = ("Planetterrian Daily", "digests/planetterrian", 7,
           "This show may add mechanism, evidence quality and context the daily "
           "did not give; the news itself is already told.")

# The spotlight chosen in pre_fetch, for post_generate (same process).
_selected: dict = {}


def pre_fetch(config, *, episode_num=None, today_str=None) -> dict:
    context, topic = health_weekly_pre_fetch(config, _SLUG, _LABEL, sibling=_SIBLING)
    _selected.clear()
    if topic:
        _selected.update(topic)
    return context


def post_generate(config, *, digest_text="", episode_num=None) -> None:
    if _selected.get("id") and digest_text:
        try:
            mark_spotlight_done(_SLUG, _selected["id"], int(episode_num or 0))
        except Exception as exc:  # noqa: BLE001
            logger.warning("%s: could not mark spotlight produced: %s", _SLUG, exc)
    show_memory.memory_post_generate(config, _SLUG, digest_text or "", episode_num or 0)
