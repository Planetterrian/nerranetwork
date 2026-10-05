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


# Oct 1 2026: seventeen shows' show notes asked for nothing. One network
# default, gated per show on the first episode AFTER this shipped (the
# committed next-episode number on 2026-10-01) so every regenerated older
# post stays byte-identical. A show with its own entry above keeps it. The
# Russian shows get the same ask in Russian; the Age of AI and Nerra
# Voices feeds are built outside run_show and take no default.
DEFAULT_ASK_FROM_EPISODE: dict[str, int] = {
    "ai_chips": 11, "collingwood": 2, "dp_pod": 78, "env_intel": 71,
    "fascinating_frontiers": 211, "finansy_prosto": 86, "first_principles": 118,
    "longevity": 3, "mag7": 10, "models_agents": 191, "models_agents_beginners": 184,
    "modern_investing": 188, "offshore_north": 8, "omni_view": 193,
    "omni_view_africa_mideast": 10, "omni_view_asia_pacific": 10, "omni_view_europe": 10,
    "omni_view_latam": 10, "omni_view_north_america": 10, "omni_view_world": 10,
    "peptides": 4, "planetterrian": 201, "prediction_markets": 10, "privet_russian": 72,
    "tesla": 623, "unintended_consequences": 130, "vancouver": 10,
}
_RUSSIAN_ASK_SHOWS = frozenset({"finansy_prosto"})
_DEFAULT_ASK_EN = (
    "If this episode was useful, a rating or a short review on Apple Podcasts "
    "or Spotify is how the next listener finds the show — and following it "
    "in your app means the next episode is there when you are."
)
_DEFAULT_ASK_RU = (
    "Если выпуск был полезен — оценка или короткий отзыв в Apple Podcasts или "
    "Spotify помогают новым слушателям найти шоу, а подписка в приложении — "
    "не пропустить следующий выпуск."
)


def _default_ask(show_slug: str) -> Optional[dict[str, Any]]:
    floor = DEFAULT_ASK_FROM_EPISODE.get(show_slug or "")
    if floor is None:
        return None
    text = _DEFAULT_ASK_RU if show_slug in _RUSSIAN_ASK_SHOWS else _DEFAULT_ASK_EN
    return {"min_episode": floor, "paragraphs": [text]}


def episode_ask_for(show_slug: str, episode_num: int) -> Optional[dict[str, Any]]:
    """Return the ask payload for this show + episode, or ``None``.

    Returned shape::

        {"paragraphs": ["…", "…"]}
    """
    cfg = SHOW_EPISODE_ASKS.get(show_slug or "") or _default_ask(show_slug)
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
