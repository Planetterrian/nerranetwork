"""Models & Agents hooks — recursive narrative memory (Phase 3).

Thin wrapper over engine.show_memory. Injects the narrative-memory section
into the digest/podcast prompts (pre_fetch) and mines recurring themes from
each episode's digest (post_generate). Both are gated on
``config.memory_enabled`` and are non-fatal — a memory failure never blocks an
episode.
"""

from __future__ import annotations

from engine import show_memory

_SLUG = "models_agents"


def pre_fetch(config, *, episode_num=None, today_str=None) -> dict:
    return show_memory.memory_pre_fetch(config, _SLUG)


def post_generate(config, *, digest_text="", episode_num=None) -> None:
    show_memory.memory_post_generate(config, _SLUG, digest_text or "", episode_num or 0)
