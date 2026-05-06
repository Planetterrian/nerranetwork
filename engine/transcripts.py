"""Episode transcript generation using faster-whisper.

Generates timestamped transcripts from podcast audio files for:
  - Searchable episode text on web players
  - RSS <podcast:transcript> tags
  - SEO indexing
  - Accessibility
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


def generate_transcript(
    audio_path: Path,
    output_dir: Path,
    episode_prefix: str,
    *,
    model_size: str = "base",
    language: Optional[str] = None,
) -> Optional[Path]:
    """Generate a transcript from an MP3 file using faster-whisper.

    Parameters
    ----------
    audio_path:
        Path to the MP3 file.
    output_dir:
        Directory to write transcript files into.
    episode_prefix:
        Filename prefix (e.g. ``"TST_Ep042_20260316"``).
    model_size:
        Whisper model size (``"tiny"``, ``"base"``, ``"small"``).
    language:
        Language code (e.g. ``"en"``, ``"ru"``). None = auto-detect.

    Returns
    -------
    Path or None
        Path to the plain-text transcript file, or None on failure.
    """
    try:
        from faster_whisper import WhisperModel
    except ImportError:
        logger.info("faster-whisper not installed — skipping transcript generation")
        return None

    if not audio_path.exists():
        logger.warning("Audio file not found for transcript: %s", audio_path)
        return None

    logger.info("Generating transcript from %s (model=%s) ...", audio_path.name, model_size)

    # Pass through ``HF_TOKEN`` if present so the faster-whisper model
    # download uses authenticated requests to Hugging Face Hub. Without
    # it every run logs ``Warning: You are sending unauthenticated
    # requests to the HF Hub. Please set a HF_TOKEN to enable higher
    # rate limits and faster downloads.`` (TST Ep465 log, May 6 2026
    # — recurring on every show). Optional — anonymous still works,
    # just slower and rate-limited.
    import os
    hf_token = os.getenv("HF_TOKEN", "").strip()

    try:
        # ``faster-whisper`` reads ``HF_TOKEN`` directly from the env via
        # huggingface_hub. We export it explicitly here so the value
        # picked up matches whatever the operator sets — and so the
        # absence is logged once per run instead of once per HTTP call.
        if hf_token:
            os.environ.setdefault("HF_HUB_DISABLE_TELEMETRY", "1")
        model = WhisperModel(model_size, device="cpu", compute_type="int8")
        segments, info = model.transcribe(
            str(audio_path),
            language=language,
            beam_size=5,
            word_timestamps=True,
        )

        transcript_segments = []
        full_text_parts = []

        for segment in segments:
            seg_data = {
                "start": round(segment.start, 2),
                "end": round(segment.end, 2),
                "text": segment.text.strip(),
            }
            if segment.words:
                seg_data["words"] = [
                    {
                        "word": w.word.strip(),
                        "start": round(w.start, 2),
                        "end": round(w.end, 2),
                        "probability": round(w.probability, 3),
                    }
                    for w in segment.words
                ]
            transcript_segments.append(seg_data)
            full_text_parts.append(segment.text.strip())

        # Write JSON transcript (timestamped segments + word-level data)
        json_path = output_dir / f"{episode_prefix}_transcript.json"
        json_data = {
            "language": info.language,
            "language_probability": round(info.language_probability, 3),
            "duration": round(info.duration, 2),
            "segments": transcript_segments,
        }
        json_path.write_text(json.dumps(json_data, indent=2, ensure_ascii=False), encoding="utf-8")

        # Write plain-text transcript
        txt_path = output_dir / f"{episode_prefix}_transcript.txt"
        txt_path.write_text("\n".join(full_text_parts), encoding="utf-8")

        logger.info(
            "Transcript generated: %s (%d segments, %s detected)",
            txt_path.name, len(transcript_segments), info.language,
        )
        return txt_path

    except Exception as exc:
        logger.warning("Transcript generation failed (non-fatal): %s", exc)
        return None
