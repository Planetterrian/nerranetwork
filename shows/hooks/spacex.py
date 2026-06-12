"""SpaceX Daily hooks — narrative memory wiring (launch-day standard).

Thin adapter over engine.show_memory, same pattern as Models & Agents /
Fascinating Frontiers. Gated on ``memory_enabled`` in shows/spacex.yaml.
"""

from __future__ import annotations

from engine import show_memory


def pre_fetch(config, *, episode_num=None, today_str=None) -> dict:
    return show_memory.memory_pre_fetch(config, "spacex")


def post_generate(config, *, digest_text: str = "", episode_num: int = 0) -> None:
    show_memory.memory_post_generate(config, "spacex", digest_text, episode_num)
