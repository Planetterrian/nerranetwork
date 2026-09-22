"""AI Chips & Data Centres Daily hooks (Sep 2026).

pre_fetch: the show's narrative memory plus a sibling-coverage block from
the last day of Models & Agents digests, so a chip launch that sister show
already covered is treated as covered — this show adds only the hardware
and economics lens (docs/new_shows_plan_2026_09_22.md §4.1).
post_generate: theme mining into the memory history.

Both are non-fatal: a failure returns what it has and never blocks an
episode.
"""

from __future__ import annotations

import logging

from engine import show_memory
from engine.sibling_coverage import sibling_block

logger = logging.getLogger(__name__)

_SLUG = "ai_chips"

_SIBLING_LENS = (
    "This show may add a story's hardware, facility, power, supply-chain or "
    "cost facts that the sister show did not report; its model and software "
    "angle is already told."
)


def pre_fetch(config, *, episode_num=None, today_str=None) -> dict:
    context = show_memory.memory_pre_fetch(config, _SLUG)
    try:
        context["hook_context"] = sibling_block(
            "Models & Agents", "digests/models_agents", days=1, lens=_SIBLING_LENS)
    except Exception as exc:  # noqa: BLE001 — never block an episode
        logger.warning("ai_chips sibling block failed (non-fatal): %s", exc)
        context["hook_context"] = ""
    return context


def post_generate(config, *, digest_text="", episode_num=None) -> None:
    show_memory.memory_post_generate(config, _SLUG, digest_text or "", episode_num or 0)
