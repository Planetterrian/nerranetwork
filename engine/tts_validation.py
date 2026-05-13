"""Post-TTS transcription validation using Whisper speech-to-text.

Transcribes generated audio back to text and compares it against the
expected TTS input to catch mispronunciations, garbled words, and
other TTS quality issues before the episode publishes.

Designed as an opt-in quality check — logs warnings but does not
block the pipeline by default.
"""

import difflib
import logging
import re
import threading
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

_model_lock = threading.Lock()
_cached_model = None
_cached_model_size = None


def _get_whisper_model(model_size: str = "base"):
    """Lazy-load a faster-whisper model (singleton, cached across calls)."""
    global _cached_model, _cached_model_size
    with _model_lock:
        if _cached_model is not None and _cached_model_size == model_size:
            return _cached_model
        try:
            from faster_whisper import WhisperModel
        except ImportError:
            logger.error(
                "faster-whisper not installed — run: pip install faster-whisper"
            )
            return None
        logger.info("Loading Whisper model '%s' (this may take a moment)...", model_size)
        model = WhisperModel(model_size, device="cpu", compute_type="int8")
        _cached_model = model
        _cached_model_size = model_size
        logger.info("Whisper model '%s' loaded.", model_size)
        return model


def _normalize_for_comparison(text: str) -> str:
    """Lowercase, strip punctuation, collapse whitespace for fair comparison.

    Both the expected text and the Whisper transcription go through this
    so that minor formatting differences (commas, periods, capitalization)
    don't count as mismatches.
    """
    text = text.lower()
    # Remove punctuation except apostrophes in contractions
    text = re.sub(r"[^\w\s']", " ", text)
    # Collapse whitespace
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _extract_mismatches(expected_words: list, transcribed_words: list, context: int = 3) -> list:
    """Extract mismatched words with surrounding context using SequenceMatcher.

    Returns a list of dicts with 'expected', 'heard', and 'context' keys.
    """
    matcher = difflib.SequenceMatcher(None, expected_words, transcribed_words)
    mismatches = []

    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == "equal":
            continue

        expected_chunk = " ".join(expected_words[i1:i2]) if i1 < i2 else ""
        heard_chunk = " ".join(transcribed_words[j1:j2]) if j1 < j2 else ""

        # Surrounding context from expected text
        ctx_start = max(0, i1 - context)
        ctx_end = min(len(expected_words), i2 + context)
        ctx = " ".join(expected_words[ctx_start:ctx_end])

        mismatches.append({
            "type": tag,  # "replace", "insert", "delete"
            "expected": expected_chunk,
            "heard": heard_chunk,
            "context": ctx,
        })

    return mismatches


def validate_tts_transcription(
    audio_path: Path,
    expected_text: str,
    *,
    model_size: str = "base",
    language: str = "en",
    threshold: float = 0.7,
    transcription: Optional[str] = None,
) -> dict:
    """Transcribe audio and compare to expected text.

    Parameters
    ----------
    audio_path:
        Path to the raw TTS audio file (MP3 or WAV). Only consulted
        when ``transcription`` is not supplied — when the caller
        already has a Whisper transcription on hand (e.g. from
        :func:`engine.transcripts.generate_transcript`), the audio is
        not re-transcribed.
    expected_text:
        The text that was fed to TTS (after pronunciation fixes).
    model_size:
        Whisper model size: "tiny", "base", "small", "medium". Only
        used when ``transcription`` is None.
    language:
        Language code for transcription. Only used when
        ``transcription`` is None.
    threshold:
        Minimum match score (0.0-1.0) to consider validation passed.
    transcription:
        Optional pre-computed transcription. When provided, skips the
        internal Whisper load + transcribe entirely — the caller is
        responsible for supplying the Whisper output. Added May 12
        2026 to consolidate the two Whisper passes that previously
        ran per episode (validation + transcript) into a single pass.

    Returns
    -------
    dict with keys:
        match_score (float), passed (bool), transcription (str),
        mismatched_words (list), expected_word_count (int),
        transcribed_word_count (int)
    """
    result = {
        "match_score": 0.0,
        "passed": False,
        "transcription": "",
        "mismatched_words": [],
        "expected_word_count": 0,
        "transcribed_word_count": 0,
        "error": None,
    }

    if transcription is not None:
        # Reuse the caller-supplied Whisper output — no second pass.
        pass
    else:
        if not audio_path.exists():
            result["error"] = f"Audio file not found: {audio_path}"
            logger.error(result["error"])
            return result

        model = _get_whisper_model(model_size)
        if model is None:
            result["error"] = "Whisper model not available"
            result["passed"] = True  # Don't block if whisper unavailable
            return result

        # Transcribe
        try:
            segments, info = model.transcribe(
                str(audio_path),
                language=language,
                beam_size=5,
                word_timestamps=False,
            )
            transcription = " ".join(seg.text.strip() for seg in segments)
        except Exception as exc:
            result["error"] = f"Transcription failed: {exc}"
            logger.error(result["error"])
            result["passed"] = True  # Don't block on transcription errors
            return result

    result["transcription"] = transcription

    # Normalize both texts
    norm_expected = _normalize_for_comparison(expected_text)
    norm_transcribed = _normalize_for_comparison(transcription)

    expected_words = norm_expected.split()
    transcribed_words = norm_transcribed.split()

    result["expected_word_count"] = len(expected_words)
    result["transcribed_word_count"] = len(transcribed_words)

    if not expected_words:
        result["error"] = "Expected text is empty"
        result["passed"] = True
        return result

    # Compute word-level similarity
    matcher = difflib.SequenceMatcher(None, expected_words, transcribed_words)
    result["match_score"] = matcher.ratio()
    result["passed"] = result["match_score"] >= threshold

    # Extract mismatched words
    result["mismatched_words"] = _extract_mismatches(expected_words, transcribed_words)

    return result
