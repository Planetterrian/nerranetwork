"""Planetterrian Daily hooks — recursive narrative memory (Phase 3).

Thin wrapper over engine.show_memory; see shows/hooks/models_agents.py.
"""

from __future__ import annotations

from engine import show_memory

_SLUG = "planetterrian"


def pre_fetch(config, *, episode_num=None, today_str=None) -> dict:
    return show_memory.memory_pre_fetch(config, _SLUG)


def post_generate(config, *, digest_text="", episode_num=None) -> None:
    show_memory.memory_post_generate(config, _SLUG, digest_text or "", episode_num or 0)
