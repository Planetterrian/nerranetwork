"""Offshore North hooks — recursive narrative memory (Aug 2026 field review).

Thin wrapper over engine.show_memory; see shows/hooks/models_agents.py.
The show's spine is a two-year longitudinal story (the first Canadian
campaign to finish the Vendée Globe, 12 Nov 2028) — the exact shape the
show_memory engine chronicles.
"""

from __future__ import annotations

from engine import show_memory

_SLUG = "offshore_north"


def pre_fetch(config, *, episode_num=None, today_str=None) -> dict:
    return show_memory.memory_pre_fetch(config, _SLUG)


def post_generate(config, *, digest_text="", episode_num=None) -> None:
    show_memory.memory_post_generate(config, _SLUG, digest_text or "", episode_num or 0)
