"""Spoken network cross-promo for the end of each podcast.

Every English show's spoken closing gets a short plug for the Nerra Network
plus ONE rotating sibling show. The featured sibling is chosen deterministically
from the date, so:

  - it varies every day for every show,
  - different shows feature different siblings on the same day, and
  - over a full rotation each show's closing eventually features every other
    English show (no sibling is left unadvertised).

Russian shows (Финансы Просто, Привет Русский!) are intentionally excluded:
they neither receive a promo nor get advertised by the English shows (operator
decision — keep the cross-promo English-only for now).

The promo is appended to the resolved ``closing_block`` in
``engine.pipeline.run_generation_phase`` so it covers every English show
including ones whose hook supplies its own closing (e.g. Tesla) and episode 1.
"""

from __future__ import annotations

import datetime as _dt
import logging
from typing import Optional

logger = logging.getLogger(__name__)

# English shows only. ``spoken_name`` avoids the ``&`` ampersand (Models &
# Agents → "Models and Agents") so TTS never reads a stray symbol; ``tagline``
# is a short spoken fragment that reads naturally after "give X a listen:".
# Order is fixed (used as the per-show rotation offset) — append new shows at
# the end rather than reordering, so existing rotations stay stable.
ENGLISH_SHOWS: dict[str, dict[str, str]] = {
    "tesla": {
        "spoken_name": "Tesla Shorts Time",
        "tagline": "your daily deep dive into everything Tesla",
    },
    "omni_view": {
        "spoken_name": "Omni View",
        "tagline": "a balanced daily world-news briefing that takes every side seriously",
    },
    "fascinating_frontiers": {
        "spoken_name": "Fascinating Frontiers",
        "tagline": "the most fascinating news from space and science",
    },
    "planetterrian": {
        "spoken_name": "Planetterrian Daily",
        "tagline": "daily breakthroughs in science, health, and longevity",
    },
    "env_intel": {
        "spoken_name": "Environmental Intelligence",
        "tagline": "the environment and climate-policy brief for Canada",
    },
    "models_agents": {
        "spoken_name": "Models and Agents",
        "tagline": "your daily briefing on AI models and agents",
    },
    "models_agents_beginners": {
        "spoken_name": "Models and Agents for Beginners",
        "tagline": "artificial intelligence explained simply, for beginners and curious teens",
    },
    "modern_investing": {
        "spoken_name": "Modern Investing Techniques",
        "tagline": "modern strategies for Canadian and U.S. investors",
    },
    "unintended_consequences": {
        "spoken_name": "Unintended Consequences",
        "tagline": "true stories of good intentions that backfired",
    },
    "spacex": {
        "spoken_name": "SpaceX Daily",
        "tagline": "daily SpaceX news, from Starship to Starlink, with the engineering behind it",
    },
}

# Fixed rotation order (insertion order of the dict above).
ENGLISH_ORDER: list[str] = list(ENGLISH_SHOWS.keys())

# Shows that must never receive or appear in the cross-promo.
RUSSIAN_SHOWS = ("finansy_prosto", "privet_russian")


def pick_featured_show(show_slug: str, date: _dt.date) -> Optional[str]:
    """Return the sibling English show to feature in *show_slug*'s closing on
    *date*, or ``None`` if there is no eligible sibling / the show is not an
    English show.

    Deterministic and coverage-complete: the candidate list is every English
    show except ``show_slug``, indexed by ``date.toordinal()`` plus a per-show
    offset. The daily ordinal increment walks the whole candidate list over
    consecutive days (so every sibling is eventually featured), and the per-show
    offset means two shows airing the same day feature different siblings.
    """
    if show_slug not in ENGLISH_SHOWS:
        return None
    candidates = [s for s in ENGLISH_ORDER if s != show_slug]
    if not candidates:
        return None
    offset = ENGLISH_ORDER.index(show_slug)
    idx = (date.toordinal() + offset) % len(candidates)
    return candidates[idx]


def build_network_promo(
    show_slug: str,
    date: _dt.date,
    episode_num: Optional[int] = None,
) -> str:
    """Build the spoken network cross-promo sentence(s) for *show_slug* on
    *date*, or ``""`` for Russian / unknown shows (which get no promo).

    The returned text carries no host prefix — it is appended to an already
    host-prefixed ``closing_block``.
    """
    featured = pick_featured_show(show_slug, date)
    if not featured:
        return ""
    name = ENGLISH_SHOWS[featured]["spoken_name"]
    tagline = ENGLISH_SHOWS[featured]["tagline"]
    return (
        "And before you go — this show is part of the Nerra Network, "
        "a family of daily podcasts covering tech, science, markets, and more. "
        f"If you enjoyed today's episode, give {name} a listen: {tagline}. "
        "You can explore the whole lineup at nerranetwork.com."
    )
