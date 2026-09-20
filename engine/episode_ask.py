"""Per-show rating/review asks for episode show notes and blog footers.

One module owns the copy so RSS show notes (Apple / Spotify) and the blog
episode page cannot drift. A show without an entry is a clean no-op.

SpaceX Ask B (hero-week paste, Sep 2026) ships from Ep 99 onward.
"""

from __future__ import annotations

from typing import Any, Optional

# Closed vocabulary: slug → ask. ``min_episode`` gates when the ask starts
# shipping so a regen of older posts stays byte-identical.
SHOW_EPISODE_ASKS: dict[str, dict[str, Any]] = {
    "spacex": {
        "min_episode": 99,
        "paragraphs": [
            (
                "Enjoyed this episode? A rating or short review on Apple "
                "Podcasts or Spotify helps SpaceX Daily reach the next "
                "listener who wants the same thing: sourced updates, zero "
                "ads, no outrage diet."
            ),
            (
                "SpaceX Daily is part of Nerra Network — 18 ad-free shows, "
                "most of them daily."
            ),
        ],
    },
}


def episode_ask_for(show_slug: str, episode_num: int) -> Optional[dict[str, Any]]:
    """Return the ask payload for this show + episode, or ``None``.

    Returned shape::

        {"paragraphs": ["…", "…"]}
    """
    cfg = SHOW_EPISODE_ASKS.get(show_slug or "")
    if not cfg:
        return None
    try:
        ep = int(episode_num or 0)
    except (TypeError, ValueError):
        return None
    if ep < int(cfg.get("min_episode") or 0):
        return None
    paragraphs = [p.strip() for p in (cfg.get("paragraphs") or []) if str(p).strip()]
    if not paragraphs:
        return None
    return {"paragraphs": list(paragraphs)}


def episode_ask_markdown(show_slug: str, episode_num: int) -> str:
    """Plain markdown paragraphs for RSS show-notes footers (``\\n\\n``-joined)."""
    ask = episode_ask_for(show_slug, episode_num)
    if not ask:
        return ""
    return "\n\n".join(ask["paragraphs"])
