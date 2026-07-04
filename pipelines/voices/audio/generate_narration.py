"""Mira narration TTS batch (Nerra Voices production stage).

Takes the narration segments written by produce_episode.py's narration LLM
pass (cold open, act intros, sign-off) and synthesizes each with Mira's
Grok voice (`ara`) via the network's existing TTS path. One MP3 per
segment; assembly stitches them around the interview audio.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Dict, List

logger = logging.getLogger(__name__)

MIRA_VOICE = os.environ.get("MIRA_VOICE_PRESET", "ara")


def synthesize_segments(segments: List[Dict[str, str]], out_dir: Path) -> Dict[str, Path]:
    """``segments``: [{"id": "cold_open", "text": "..."}, ...] in episode
    order. Returns {segment_id: mp3_path}."""
    from engine.tts import synthesize

    api_key = os.environ.get("GROK_API_KEY") or os.environ.get("XAI_API_KEY")
    if not api_key:
        raise RuntimeError("GROK_API_KEY / XAI_API_KEY required for narration TTS")

    out_dir.mkdir(parents=True, exist_ok=True)
    paths: Dict[str, Path] = {}
    for seg in segments:
        seg_id, text = seg["id"], (seg.get("text") or "").strip()
        if not text:
            logger.warning("Narration segment %s is empty — skipped", seg_id)
            continue
        target = out_dir / f"narration_{seg_id}.mp3"
        synthesize(
            text,
            str(target),
            provider="grok",
            voice_id=MIRA_VOICE,
            api_key=api_key,
            language_code="en",
        )
        paths[seg_id] = target
        logger.info("Narration synthesized: %s (%d chars)", seg_id, len(text))
    return paths
