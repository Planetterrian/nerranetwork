"""Vancouver Daily News hooks (Sep 2026, docs/new_shows_plan_2026_09_22.md §4.5).

pre_fetch: the show's narrative memory, plus the Getting Around data as hook
ARTICLES (engine/local_conditions.py): DriveBC's major Metro Vancouver road
events and the Environment Canada forecast for Vancouver. Articles, not
prompt text, so the digest cites them by URL and the claims gate verifies
them against the copy the run already holds. A ``hook_context`` block tells
the digest the section is built from those articles only — and, on a day
the feeds fail, to say so in one sentence rather than invent a forecast.
post_generate: theme mining into the memory history.

Every step is non-fatal.
"""

from __future__ import annotations

import logging

from engine import show_memory
from engine.local_conditions import (
    conditions_block,
    drivebc_article,
    gather,
    weather_article,
)

logger = logging.getLogger(__name__)

_SLUG = "vancouver"
_SECTION = "Getting Around"

#: Environment Canada's Vancouver location (the city-centre coordinates its
#: own site uses for the Vancouver forecast page).
VANCOUVER_LAT, VANCOUVER_LON = 49.245, -123.115


def pre_fetch(config, *, episode_num=None, today_str=None) -> dict:
    context = show_memory.memory_pre_fetch(config, _SLUG)
    articles = gather([
        drivebc_article,
        lambda: weather_article(VANCOUVER_LAT, VANCOUVER_LON, "Vancouver"),
    ])
    if articles:
        context["articles"] = articles
    context["hook_context"] = conditions_block(articles, _SECTION)
    return context


def post_generate(config, *, digest_text="", episode_num=None) -> None:
    show_memory.memory_post_generate(config, _SLUG, digest_text or "", episode_num or 0)
