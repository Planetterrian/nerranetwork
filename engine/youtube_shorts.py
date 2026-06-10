"""Shorts clip timing helpers for the YouTube pipeline."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)


def _read_chapter_starts(chapters_path: Optional[Path]) -> list[float]:
    """Return sorted chapter start times (seconds) from a chapters JSON file."""
    if not chapters_path or not chapters_path.exists():
        return []
    try:
        data = json.loads(chapters_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        logger.warning("Could not read chapters for Shorts offset: %s", exc)
        return []
    chapters = data.get("chapters") if isinstance(data, dict) else data
    if not isinstance(chapters, list):
        return []
    starts: list[float] = []
    for ch in chapters:
        if not isinstance(ch, dict):
            continue
        start = ch.get("startTime", ch.get("start_time", ch.get("start")))
        if start is None:
            continue
        try:
            starts.append(max(0.0, float(start)))
        except (TypeError, ValueError):
            continue
    return sorted(set(starts))


def resolve_shorts_start_offset(
    config: Any,
    chapters_path: Optional[Path] = None,
    *,
    audio_duration: float = 0.0,
    transcript_path: Optional[Path] = None,
) -> float:
    """Pick where the Shorts audio clip begins in the final mixed MP3.

    The mixed MP3 places voice at ``voice_intro_delay`` seconds (music-only
    intro before that). Summing ``intro_duration + voice_intro_delay`` was
    wrong and skipped the first ~10s of narration.

    Modes (``youtube.shorts_start_mode``):

      ``voice`` (default) — start at ``voice_intro_delay``.
      ``first_chapter`` — start at the first chapter marker after the cold
          open (second chapter when ≥2 exist, else first chapter > 45s).
      ``smart`` — scan the Whisper transcript for the most engaging
          beat (numeric reveal, hook phrase, surprise framing) and
          start there. Falls back to ``voice`` if no segment scores
          above the noise threshold. Requires ``transcript_path``;
          without it (or on transcript I/O failure) silently falls
          back to ``voice`` too. See engine.shorts_selector for the
          scoring details.
    """
    yt = getattr(config, "youtube", None)
    explicit = getattr(yt, "shorts_start_offset", None) if yt else None
    if explicit is not None:
        return max(0.0, float(explicit))

    mode = (
        (getattr(yt, "shorts_start_mode", None) or "voice") if yt else "voice"
    ).strip().lower()

    if mode == "first_chapter":
        starts = _read_chapter_starts(chapters_path)
        if len(starts) >= 2:
            offset = starts[1]
        elif len(starts) == 1 and starts[0] > 45.0:
            offset = starts[0]
        else:
            offset = float(getattr(config.audio, "voice_intro_delay", 0.0) or 0.0)
        if audio_duration > 0:
            short_dur = float(
                getattr(yt, "short_duration_seconds", 55.0) or 55.0
            )
            max_start = max(0.0, audio_duration - short_dur - 1.0)
            offset = min(offset, max_start)
        logger.info(
            "Shorts start offset (first_chapter): %.1fs", offset,
        )
        return offset

    voice_offset = float(
        getattr(config.audio, "voice_intro_delay", 0.0) or 0.0
    )

    if mode == "smart":
        # Smart mode is best-effort: it falls back to voice on any
        # missing dep (no transcript path), unreadable transcript,
        # empty transcript, or no candidate above the score
        # threshold. Operators see the chosen path in the log line
        # so a regression in the heuristic is obvious from CI logs.
        from engine.shorts_selector import pick_engaging_window
        if transcript_path is not None and transcript_path.exists():
            short_dur = float(
                getattr(yt, "short_duration_seconds", 55.0) or 55.0
            )
            # June 10 2026: pass the per-show noise floor. Tesla's 3.5
            # override (May retune) never reached this path — the YAML
            # field wasn't declared on YouTubeConfig AND this call left
            # the selector at its 5.0 default, so measured/narrative
            # shows fell back to the legacy voice start almost daily.
            threshold = float(
                getattr(yt, "shorts_min_score_threshold", 5.0) or 5.0
            )
            best = pick_engaging_window(
                transcript_path,
                audio_offset=voice_offset,
                audio_duration=audio_duration,
                window_duration=short_dur,
                min_start_final=voice_offset,
                min_score_threshold=threshold,
            )
            if best is not None:
                logger.info(
                    "Shorts start offset (smart): %.1fs (score=%.1f, "
                    "opening=%r)",
                    best.start_seconds, best.score, best.opening_text,
                )
                return best.start_seconds
        logger.info(
            "Shorts start offset (smart→voice fallback): %.1fs",
            voice_offset,
        )
        return voice_offset

    logger.info("Shorts start offset (voice): %.1fs", voice_offset)
    return voice_offset


def should_upload_shorts_today(config: Any, *, episode_num: int) -> bool:
    """Honor ``youtube.shorts_upload_schedule`` quota-stagger knob."""
    yt = getattr(config, "youtube", None)
    if not yt or not getattr(yt, "publish_shorts", True):
        return False
    schedule = (
        getattr(yt, "shorts_upload_schedule", None) or "always"
    ).strip().lower()
    if schedule == "alternate_episodes":
        upload = episode_num % 2 == 0
        if not upload:
            logger.info(
                "Shorts upload skipped (shorts_upload_schedule=alternate_episodes, "
                "ep %d).",
                episode_num,
            )
        return upload
    return True
