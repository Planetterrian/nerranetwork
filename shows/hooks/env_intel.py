"""Environmental Intelligence pronunciation overrides.

EI's audience is Canadian environmental professionals who know acronyms
like CCME, CEPA, EPA, ESA as spoken letter sequences or words.  The
default pronunciation module in ``assets/pronunciation.py`` expands these
to spaced single letters ("C C M E") which causes ElevenLabs TTS to
insert unnatural pauses between each letter.  This hook tells the
pronunciation module to skip those expansions and let ElevenLabs handle
the uppercase acronyms natively — it does a much better job reading them
as smooth letter sequences without explicit spelling.
"""

from __future__ import annotations

from engine import show_memory

_SLUG = "env_intel"


def pre_fetch(config, *, episode_num=None, today_str=None) -> dict:
    """Narrative memory (Aug 2026 expansion) — thin wrapper over
    engine.show_memory, same shape as shows/hooks/fascinating_frontiers.py.
    EI's compliance beats are multi-year regulatory arcs, the best fit for
    longitudinal memory in the network."""
    return show_memory.memory_pre_fetch(config, _SLUG)


def post_generate(config, *, digest_text="", episode_num=None) -> None:
    show_memory.memory_post_generate(
        config, _SLUG, digest_text or "", episode_num or 0)


def pronunciation_overrides() -> dict:
    """Return EI-specific pronunciation overrides."""
    return {
        "skip_acronyms": {
            "CCME",
            "CEPA",
            "CSR",
            "EMA",
            "ESA",
            "EPA",
            "SVE",
            "PFAS",
            "EPEA",
            "AER",
            "IAA",
            "GHG",
            "SARA",
            "CER",
            "NEB",
        },
    }
