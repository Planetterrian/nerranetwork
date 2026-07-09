"""Spoken network cross-promo for the end of each podcast.

Every English show's spoken closing gets a short plug for the Nerra Network
plus ONE rotating sibling show, plus ONE rotating network *surface*
(website gallery, blogs, story trackers, data hub, etc.). The featured
sibling and surface are chosen deterministically from the date, so:

  - they vary every day for every show,
  - different shows feature different siblings on the same day, and
  - over a full rotation each show's closing eventually features every other
    English show and every discovery surface (no sibling or surface is left
    unadvertised).

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
        "tagline": "the daily companion for following SpaceX as a public company, from Starship to the stock ticker",
    },
    # Appended July 2026 — keep at end so prior sibling rotations stay stable.
    "first_principles": {
        "spoken_name": "First Principles Daily",
        "tagline": "reasoning from raw materials, not analogy, on the breakthroughs that actually cut cost",
    },
    "dp_pod": {
        "spoken_name": "The Do Positive Pod",
        "tagline": "good news in science and tech, plus one concrete action you can take",
    },
}

# Fixed rotation order (insertion order of the dict above).
ENGLISH_ORDER: list[str] = list(ENGLISH_SHOWS.keys())

# Shows that must never receive or appear in the cross-promo.
RUSSIAN_SHOWS = ("finansy_prosto", "privet_russian")

# Network discovery surfaces — website destinations beyond sibling shows.
# Spoken copy must avoid chapter-marker trigger phrases (bare "deep dive",
# "next time", "under the hood") that collide with show YAML chapter patterns.
# ``x_line`` is the short X/YouTube/newsletter form; ``url`` is the path under
# nerranetwork.com (no leading slash). Append new surfaces at the end.
NETWORK_SURFACES: list[dict[str, str]] = [
    {
        "id": "gallery",
        "spoken": (
            "And on the website: every episode's visuals live in our free "
            "image gallery at nerranetwork.com/gallery — royalty-free under "
            "Creative Commons, download with attribution."
        ),
        "x_line": (
            "More from the Nerra Network: free CC BY-SA episode images "
            "in the gallery"
        ),
        "url": "gallery.html",
    },
    {
        "id": "blogs",
        "spoken": (
            "Prefer reading? Today's full write-up, sources, and transcript "
            "are on the episode blog at nerranetwork.com — same briefing, "
            "readable format."
        ),
        "x_line": (
            "More from the Nerra Network: full write-ups, sources, and "
            "transcripts on every episode blog"
        ),
        "url": "blog.html",
    },
    {
        "id": "summaries",
        "spoken": (
            "Want the written briefing with source links? Each show keeps "
            "a summaries page on nerranetwork.com — scannable, dated, and "
            "free."
        ),
        "x_line": (
            "More from the Nerra Network: dated written briefings on every "
            "show's summaries page"
        ),
        "url": "start-here.html",
    },
    {
        "id": "story_trackers",
        "spoken": (
            "Following the long arcs? Story Trackers on nerranetwork.com "
            "follow major programs across episodes — Tesla, SpaceX, AI, "
            "space science, and more."
        ),
        "x_line": (
            "More from the Nerra Network: Story Trackers follow major "
            "programs across episodes"
        ),
        "url": "data.html",
    },
    {
        "id": "data_hub",
        "spoken": (
            "Live dashboards — TSLA, SpaceX launches, the investing "
            "scoreboard — are all at nerranetwork.com/data."
        ),
        "x_line": (
            "More from the Nerra Network: live dashboards at the Data Hub"
        ),
        "url": "data.html",
    },
    {
        "id": "start_here",
        "spoken": (
            "New to the network? nerranetwork.com/start-here picks the "
            "right daily briefing for you in about two minutes."
        ),
        "x_line": (
            "More from the Nerra Network: Start Here picks your next show"
        ),
        "url": "start-here.html",
    },
    {
        "id": "age_of_ai",
        "spoken": (
            "The Age of AI puts real builders on the phone with an AI host "
            "— apply at nerranetwork.com/age-of-ai-apply."
        ),
        "x_line": (
            "More from the Nerra Network: apply to be a guest on The Age of AI"
        ),
        "url": "age-of-ai-apply.html",
    },
    {
        "id": "dp_club",
        "spoken": (
            "The Do Positive Pod is the club for people who do something "
            "about it — episodes and the Dispatch Wall at "
            "nerranetwork.com/thedppod."
        ),
        "x_line": (
            "More from the Nerra Network: The Do Positive Pod club and "
            "Dispatch Wall"
        ),
        "url": "thedppod.html",
    },
]


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


def pick_featured_surface(
    show_slug: str, date: _dt.date
) -> Optional[dict[str, str]]:
    """Return the network discovery surface to plug on *date* for *show_slug*.

    Same date-deterministic rotation as :func:`pick_featured_show`, with a
    different offset so the surface and sibling rotate independently.
    """
    if show_slug not in ENGLISH_SHOWS or not NETWORK_SURFACES:
        return None
    offset = ENGLISH_ORDER.index(show_slug) * 3  # diverge from sibling idx
    idx = (date.toordinal() + offset) % len(NETWORK_SURFACES)
    return NETWORK_SURFACES[idx]


def build_surface_x_reply(show_slug: str, date: _dt.date) -> str:
    """Build an X-length discovery reply that plugs a website surface.

    Used on alternate days instead of the sibling-show reply so listeners
    also discover gallery / blogs / trackers / apply without blowing the
    280-char budget by stacking both plugs.
    """
    surface = pick_featured_surface(show_slug, date)
    if not surface:
        return ""
    url = (
        f"https://nerranetwork.com/{surface['url']}"
        "?utm_source=x&utm_medium=social&utm_campaign=network_discovery"
    )
    return f"{surface['x_line']}\n{url}"


def build_network_promo(
    show_slug: str,
    date: _dt.date,
    episode_num: Optional[int] = None,
) -> str:
    """Build the spoken network cross-promo sentence(s) for *show_slug* on
    *date*, or ``""`` for Russian / unknown shows (which get no promo).

    The returned text carries no host prefix — it is appended to an already
    host-prefixed ``closing_block``. Includes a sibling-show plug plus a
    rotating website-surface sentence (gallery, blogs, trackers, etc.).
    """
    featured = pick_featured_show(show_slug, date)
    if not featured:
        return ""
    name = ENGLISH_SHOWS[featured]["spoken_name"]
    tagline = ENGLISH_SHOWS[featured]["tagline"]
    promo = (
        "And before you go: this show is part of the Nerra Network — a family "
        "of daily podcasts on tech, science, and markets, each one a short, "
        "sharp briefing you can finish on the commute. "
        f"If today earned its place in your feed, here's your next listen — "
        f"{name}, {tagline}. "
        "Find every show, free, at nerranetwork.com."
    )
    surface = pick_featured_surface(show_slug, date)
    if surface and surface.get("spoken"):
        promo = f"{promo} {surface['spoken']}"
    return promo
