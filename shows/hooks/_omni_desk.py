"""Shared pre_fetch / post_generate for the Omni View regional desks
(docs/new_shows_plan_2026_09_22.md §4.7).

pre_fetch: the desk's narrative memory, plus a SUB-REGION BALANCE note built
from the last ten committed digests (engine.omni_desks.balance_note): the
sub-regions none of them reached are named as a preference among qualifying
stories — never a quota, never a roll-call. post_generate: theme mining.

Every step is non-fatal; each desk's hook module is two lines.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import List

from engine import show_memory
from engine.omni_desks import balance_note, desk

logger = logging.getLogger(__name__)

#: How many recent digests the balance note reads.
BALANCE_WINDOW = 10


def recent_digests(config, n: int = BALANCE_WINDOW) -> List[str]:
    out_dir = Path(getattr(getattr(config, "episode", None), "output_dir", "") or "")
    prefix = getattr(getattr(config, "episode", None), "prefix", "") or ""
    if not out_dir.is_dir() or not prefix:
        return []
    files = sorted(p for p in out_dir.glob(f"{prefix}_Ep*.md")
                   if not p.name.endswith(("_formatted.md",)))
    texts = []
    for p in files[-n:]:
        try:
            texts.append(p.read_text(encoding="utf-8"))
        except OSError:
            continue
    return texts


def pre_fetch(config, slug: str) -> dict:
    context = show_memory.memory_pre_fetch(config, slug)
    try:
        context["hook_context"] = balance_note(recent_digests(config), desk(slug))
    except Exception as exc:  # noqa: BLE001 — never block a run
        logger.warning("%s: sub-region balance note failed (non-fatal): %s", slug, exc)
        context["hook_context"] = ""
    return context


def post_generate(config, slug: str, *, digest_text: str = "", episode_num=None) -> None:
    show_memory.memory_post_generate(config, slug, digest_text or "", episode_num or 0)
