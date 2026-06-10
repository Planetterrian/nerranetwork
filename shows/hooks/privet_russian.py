"""Привет, Русский! hooks — vocabulary memory (June 10 2026 review).

Closes the show's biggest pedagogical gap: vocabulary was taught in
complete isolation (words never reappeared across episodes) and themes
repeated back-to-back (Animals ran Ep33/34/35) because nothing
remembered what had been taught. See ``engine/vocab_tracker.py``.

``pre_fetch`` always returns the ``vocab_review_section`` key (empty
string when there's no history) so prompt substitution can never
KeyError; ``post_generate`` mines and records the episode's vocabulary.
"""

from __future__ import annotations

import logging
from pathlib import Path

from engine import vocab_tracker

logger = logging.getLogger(__name__)


def pre_fetch(config, *, episode_num: int | None = None, today_str: str | None = None) -> dict:
    section = ""
    try:
        output_dir = Path(config.episode.output_dir)
        section = vocab_tracker.build_review_section(output_dir, int(episode_num or 0))
    except Exception as exc:  # noqa: BLE001
        logger.warning("Vocab review section failed (non-fatal): %s", exc)
    return {"vocab_review_section": section}


def post_generate(config, *, digest_text: str = "", episode_num: int = 0) -> None:
    try:
        output_dir = Path(config.episode.output_dir)
        vocab_tracker.record_episode_vocab(output_dir, int(episode_num), digest_text)
    except Exception as exc:  # noqa: BLE001
        logger.warning("Vocab recording failed (non-fatal): %s", exc)
