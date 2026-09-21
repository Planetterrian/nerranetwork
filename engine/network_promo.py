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
    "offshore_north": {
        "spoken_name": "Offshore North",
        "tagline": "offshore ocean racing explained every Monday, with a Canadian angle",
    },
}

# Fixed rotation order (insertion order of the dict above).
ENGLISH_ORDER: list[str] = list(ENGLISH_SHOWS.keys())

# Shows that must never receive or appear in the cross-promo.
RUSSIAN_SHOWS = ("finansy_prosto", "privet_russian")

# Shows whose sign-off is "one line, then out": they always speak the
# shortest promo frame and never the website-surface add-on (Aug 2026,
# offshore_north editorial review — no stacked cross-promos).
COMPACT_PROMO_SHOWS = frozenset({"offshore_north"})

# Network discovery surfaces — website destinations beyond sibling shows.
# Spoken copy must avoid chapter-marker trigger phrases (bare "deep dive",
# "next time", "under the hood") that collide with show YAML chapter patterns.
# ``x_line`` is the short X/YouTube/newsletter form; ``url`` is the path under
# nerranetwork.com (no leading slash). Append new surfaces at the end.
# Optional ``weight`` (default 1) biases the date-deterministic rotation
# without dropping other surfaces. Gallery is weighted higher (July 2026
# improvements pack) so the free CC gallery gets more discovery airtime.
NETWORK_SURFACES: list[dict[str, str]] = [
    {
        "id": "gallery",
        # 3 -> 2 (Sep 21 2026, operator-directed). At weight 3 the free image
        # gallery took 3 of 12 slots — a quarter of every spoken outro, X reply
        # and YouTube description — while the paid product and the two newest
        # properties took one each. It still outweighs every peer 2:1 and still
        # never airs on consecutive days.
        "weight": "2",
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
        # blog/index.html, never "blog.html" — the latter has never existed
        # and every rotation of this surface shipped a 404 to X.
        "url": "blog/index.html",
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
        # Sep 19 2026 — NEITHER of the next two was in this pool. Gallery's
        # weight of 3 is left alone: it is a July 2026 operator decision, and
        # adding two entries already dilutes every surface proportionally, so
        # there was nothing to make room for. The network's
        # combined daily edition and its only paid product were never mentioned
        # on air or in the X replies, while the free image gallery had triple
        # airtime. Nerra Daily is also the cheapest show to make ($0.085/ep),
        # the only one trending up (+22.7% WoW) and the site's most-visited
        # show page — the one thing a listener of one show most plausibly
        # wants next.
        #
        # Spoken copy changes shipped audio on every English show:
        # A/B-LISTEN before merging (landmine #17). Revert = delete these two
        # dicts. De-seeded by shape: no quotable sentence a model can copy,
        # and no example of what a "personal edition" sounds like.
        "id": "nerra_daily",
        "spoken": (
            "If you follow more than one of our shows, Nerra Daily stitches "
            "the whole network into one morning listen — free, with chapters, "
            "at nerranetwork.com/nerra-daily."
        ),
        "x_line": (
            "More from the Nerra Network: Nerra Daily puts the whole network "
            "in one daily listen"
        ),
        "url": "nerra-daily.html",
    },
    {
        "id": "personal",
        "spoken": (
            "And if you would rather hear only your shows, in your order, "
            "Nerra Personal builds you a private daily edition — the details "
            "are at nerranetwork.com/join."
        ),
        "x_line": (
            "More from the Nerra Network: Nerra Personal builds you a private "
            "daily edition from the shows you pick"
        ),
        "url": "join.html",
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
    # Sep 21 2026 — the two newest properties were advertised NOWHERE on air.
    # The interview shows carry the network's sharpest and most contestable
    # claim, and the topic hubs are the whole of its search surface; neither
    # had a rotation entry, so a listener could not be told either existed.
    # Copy stays inside the narrow claim engine/brand.py owns: an AI asks the
    # questions and the guest decides whether it ships. Do not widen it here —
    # this text is handed to the model as {closing_block}, so a sentence
    # written loosely is a sentence aired loosely.
    {
        "id": "mira",
        "spoken": (
            "Our interviews are hosted by Mira, the network's AI "
            "documentarian, and the guest decides whether the conversation "
            "is published at all — how that works is at "
            "nerranetwork.com/mira."
        ),
        "x_line": (
            "More from the Nerra Network: Mira hosts our interviews, and the "
            "guest decides whether the episode ships"
        ),
        "url": "mira.html",
    },
    {
        "id": "topics",
        "spoken": (
            "And if you would rather browse by subject than by show, every "
            "subject the network covers has its own page at "
            "nerranetwork.com/topics."
        ),
        "x_line": (
            "More from the Nerra Network: browse every subject the network "
            "covers by topic"
        ),
        "url": "topics/index.html",
    },
]


def _weighted_surface_pool() -> list[dict[str, str]]:
    """Expand NETWORK_SURFACES by optional per-entry weight (default 1).

    The extra copies are INTERLEAVED, not clustered. The rotation walks
    the pool one step per day, so appending ``[gallery] * 3`` back-to-back
    would air the identical gallery paragraph three days running on every
    show — the repeated-boilerplate tic the playbook bans — instead of
    spreading it across the cycle. Round-robin passes place copy *n* of a
    weighted surface a full base-cycle apart.
    """
    if not NETWORK_SURFACES:
        return []
    weights: list[int] = []
    for surface in NETWORK_SURFACES:
        try:
            weights.append(max(1, int(surface.get("weight") or 1)))
        except (TypeError, ValueError):
            weights.append(1)

    total = sum(weights)
    slots: list[Optional[dict[str, str]]] = [None] * total
    # Heaviest first so it gets the evenly-spaced slots; the rest fill the
    # gaps in declaration order, preserving their relative rotation.
    for i in sorted(range(len(NETWORK_SURFACES)), key=lambda n: (-weights[n], n)):
        weight = weights[i]
        for copy_index in range(weight):
            target = (copy_index * total) // weight
            for step in range(total):
                pos = (target + step) % total
                if slots[pos] is None:
                    slots[pos] = NETWORK_SURFACES[i]
                    break
    pool = [s for s in slots if s is not None]
    return pool or list(NETWORK_SURFACES)


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
    Surfaces with ``weight`` > 1 appear proportionally more often.
    """
    pool = _weighted_surface_pool()
    if show_slug not in ENGLISH_SHOWS or not pool:
        return None
    offset = ENGLISH_ORDER.index(show_slug) * 3  # diverge from sibling idx
    idx = (date.toordinal() + offset) % len(pool)
    return pool[idx]


def build_surface_x_reply(
    show_slug: str, date: _dt.date, episode_num: Optional[int] = None
) -> str:
    """Build an X-length discovery reply that plugs a website surface.

    Used on alternate days instead of the sibling-show reply so listeners
    also discover gallery / blogs / trackers / apply without blowing the
    280-char budget by stacking both plugs.

    The link is built by :func:`engine.funnel.network_link` so the click is
    attributable to the episode that carried it and to the surface that was
    plugged. The old hand-rolled ``utm_campaign=network_discovery`` did not
    parse, so those clicks were invisible in ``api/funnel.json``. Without
    *episode_num* the link is left untagged rather than tagged wrongly.
    """
    surface = pick_featured_surface(show_slug, date)
    if not surface:
        return ""
    if episode_num:
        from engine.funnel import network_link
        url = network_link(
            surface["url"], show_slug, int(episode_num),
            surface=surface["id"],
        )
    else:
        url = f"https://nerranetwork.com/{surface['url']}"
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
    # July 16 2026 — outro-fatigue fix: the single ~40-word promo frame was
    # verbatim in 146 of 176 in-window episodes, so a multi-show listener
    # heard the identical minute several times a day (only the sibling name
    # rotated). Four frames now rotate date-deterministically, offset per
    # show so two shows on the SAME day usually speak different frames.
    # Frame 3 is deliberately short — some days the plug is one sentence.
    # Changes shipped audio -> A/B-listen per landmine #17.
    frames = (
        (
            "And before you go: this show is part of the Nerra Network — a "
            "family of daily podcasts on tech, science, and markets, each "
            "one a short, sharp briefing you can finish on the commute. "
            f"If today earned its place in your feed, here's your next "
            f"listen — {name}, {tagline}. "
            "Find every show, free, at nerranetwork.com."
        ),
        (
            f"One more thing — if you liked today's episode, our sister "
            f"show {name} is worth a spot in your feed: {tagline}. "
            "It's one of the Nerra Network's daily briefings, all free at "
            "nerranetwork.com."
        ),
        (
            f"Quick tip from the network: try {name} next — {tagline}. "
            "Every Nerra Network show is free at nerranetwork.com."
        ),
        (
            f"This show comes to you from the Nerra Network. If you want "
            f"another sharp daily briefing, {name} has you covered — "
            f"{tagline}. All our shows are free at nerranetwork.com."
        ),
    )
    frame_idx = (date.toordinal() + ENGLISH_ORDER.index(show_slug)) % len(frames)
    promo = frames[frame_idx]
    # Compact-promo shows (Aug 2026, offshore_north editorial review: the
    # sign-off is "one line, then out — no stacked cross-promos"). Ep2
    # shipped a sibling plug AND a website-surface plug back to back. These
    # shows always speak the shortest frame and never the surface add-on:
    # one compact plug, then out.
    if show_slug in COMPACT_PROMO_SHOWS:
        return frames[2]
    surface = pick_featured_surface(show_slug, date)
    if surface and surface.get("spoken"):
        promo = f"{promo} {surface['spoken']}"
    return promo
