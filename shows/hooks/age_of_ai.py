"""Hooks for The Age of AI (AI-hosted interview show).

pre_fetch peeks at the upcoming interview packet (the same entry
``pick_next_topic`` will select) and:

* injects ``{guest_dossier}`` — the guest/voicing block both prompts consume;
* sets the per-episode voicing on the run's config: ``quoted`` packets flip
  ``tts.dialogue_mode`` off (single-narrator episode), ``ai_voiced`` packets
  keep dialogue mode and may override the GUEST voice with the packet's
  consented ``guest_voice_id``.

post_generate advances the interviewed guest to ``published`` in the guest
queue. It honours ``NERRA_HOOKS_READONLY`` (set by run_show for ``--test`` /
``--rehearse``) so rehearsals never advance CRM state.

Everything is best-effort: a hook failure degrades to a default-voiced
episode without a dossier block, never a KeyError (run_show setdefaults the
template var).
"""

from __future__ import annotations

import logging
import os
from pathlib import Path

logger = logging.getLogger(__name__)

_ROOT = Path(__file__).resolve().parent.parent.parent
_GUEST_QUEUE = _ROOT / "shows" / "guest_queues" / "age_of_ai.yaml"


def _hooks_readonly() -> bool:
    return os.environ.get("NERRA_HOOKS_READONLY", "").strip() == "1"


def _peek_next_packet(config) -> dict:
    from engine.topic_queue import pick_next_topic
    queue_file = getattr(config, "topic_queue_file", "") or ""
    if not queue_file:
        return {}
    return pick_next_topic(_ROOT / queue_file) or {}


def pre_fetch(config, *, episode_num=None, today_str=None) -> dict:
    try:
        packet = _peek_next_packet(config)
    except Exception as exc:  # noqa: BLE001 — never block the episode
        logger.warning("age_of_ai hook: packet peek failed (non-fatal): %s", exc)
        return {}
    if not packet:
        # Empty queue — run_show's narrative branch will skip the episode.
        return {}

    from engine.interview import build_guest_dossier, resolve_voice_mode

    # Re-apply the consent gate at air time (defence in depth: a hand-edited
    # packet can't bypass what compile enforced).
    voice_mode = resolve_voice_mode(packet)

    try:
        if voice_mode != "ai_voiced":
            if getattr(config.tts, "dialogue_mode", False):
                config.tts.dialogue_mode = False
                logger.info(
                    "age_of_ai: quoted-mode interview — single-narrator "
                    "episode (dialogue mode off for this run)",
                )
        else:
            guest_voice = str(packet.get("guest_voice_id", "") or "").strip()
            if guest_voice:
                voices = dict(getattr(config.tts, "dialogue_voices", {}) or {})
                voices["GUEST"] = guest_voice
                config.tts.dialogue_voices = voices
                logger.info(
                    "age_of_ai: using per-guest voice override for GUEST",
                )
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "age_of_ai hook: voicing setup failed (non-fatal): %s", exc,
        )

    packet = {**packet, "voice_mode": voice_mode}
    return {"guest_dossier": build_guest_dossier(packet)}


def post_generate(config, *, digest_text="", episode_num=None) -> None:
    """Advance the interviewed guest to ``published`` after the episode."""
    if _hooks_readonly():
        logger.info("age_of_ai post_generate: read-only run — guest queue untouched")
        return
    try:
        import datetime as _dt

        import yaml

        from engine.interview import mark_guest_published

        queue_file = getattr(config, "topic_queue_file", "") or ""
        if not queue_file:
            return
        data = yaml.safe_load((_ROOT / queue_file).read_text(encoding="utf-8")) or {}
        produced = [
            e for e in data.get("queue", [])
            if isinstance(e, dict)
            and e.get("produced") is True
            and e.get("episode_number") == episode_num
            and e.get("guest_id")
        ]
        for entry in produced:
            mark_guest_published(
                _GUEST_QUEUE,
                entry["guest_id"],
                episode_num or 0,
                str(entry.get("produced_date") or _dt.date.today().isoformat()),
            )
    except Exception as exc:  # noqa: BLE001 — CRM bookkeeping must never fail the run
        logger.warning("age_of_ai post_generate failed (non-fatal): %s", exc)
