"""Collingwood Weekly hooks (Sep 2026, docs/new_shows_plan_2026_09_22.md §4.6).

pre_fetch: the show's narrative memory, plus the Roads & Weather Ahead data
as hook ARTICLES (engine/local_conditions.py): Ontario 511 events inside a
box around Collingwood and the south Georgian Bay towns, and the Environment
Canada forecast for Collingwood — which runs into the weekend, because the
show publishes on Friday. Articles, not prompt text, so the digest cites
them and the claims gate verifies them. On a day the feeds fail, the
``hook_context`` block tells the digest to say so in one sentence.
post_generate: theme mining into the memory history.

Every step is non-fatal.
"""

from __future__ import annotations

import logging

from engine import show_memory
from engine.local_conditions import (
    conditions_block,
    gather,
    ontario511_article,
    weather_article,
)

logger = logging.getLogger(__name__)

_SLUG = "collingwood"
_SECTION = "Roads & Weather Ahead"

#: Collingwood, Wasaga Beach, Clearview (Stayner), The Blue Mountains
#: (Thornbury) and Meaford's edge, as (south, west, north, east).
SOUTH_GEORGIAN_BAY_BOX = (44.35, -80.65, 44.62, -79.95)
COLLINGWOOD_LAT, COLLINGWOOD_LON = 44.5, -80.217


def pre_fetch(config, *, episode_num=None, today_str=None) -> dict:
    context = show_memory.memory_pre_fetch(config, _SLUG)
    articles = gather([
        lambda: ontario511_article(SOUTH_GEORGIAN_BAY_BOX,
                                   "Collingwood and south Georgian Bay"),
        lambda: weather_article(COLLINGWOOD_LAT, COLLINGWOOD_LON, "Collingwood"),
    ])
    if articles:
        context["articles"] = articles
    context["hook_context"] = conditions_block(articles, _SECTION)
    return context


def post_generate(config, *, digest_text="", episode_num=None) -> None:
    show_memory.memory_post_generate(config, _SLUG, digest_text or "", episode_num or 0)
