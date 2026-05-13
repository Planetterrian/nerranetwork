"""Verify the Whisper-call consolidation in the TTS validation path.

Before May 12 2026 every episode ran Whisper twice — once inside
``engine.transcripts.generate_transcript`` (to write the RSS-side
JSON + TXT transcript) and once inside
``engine.tts_validation.validate_tts_transcription`` (to compare
audio against the script). Same MP3, same model, two passes.

Consolidated path:
  1. ``generate_transcript()`` runs Whisper once and now returns a
     ``TranscriptResult`` carrying the plain-text output in memory.
  2. ``validate_tts_transcription()`` accepts ``transcription=...``
     and skips its own Whisper call entirely when supplied.

These tests pin the new contract.
"""

from pathlib import Path
from unittest.mock import MagicMock, patch


# ---------------------------------------------------------------------------
# generate_transcript: returns TranscriptResult with paths AND text
# ---------------------------------------------------------------------------

def test_transcript_result_carries_text_in_memory(tmp_path: Path):
    """The TranscriptResult must contain the plain-text transcript
    so validation can reuse it without re-reading from disk or
    re-transcribing."""
    from engine.transcripts import TranscriptResult, generate_transcript

    mp3 = tmp_path / "episode.mp3"
    mp3.write_bytes(b"\xff\xfb\x90")  # minimal MP3 magic — content is mocked

    # Fake faster_whisper.WhisperModel that returns one segment.
    fake_seg = MagicMock(start=0.0, end=2.5, text="Hello world.", words=[])
    fake_info = MagicMock(language="en", language_probability=0.99, duration=2.5)
    fake_model = MagicMock()
    fake_model.transcribe.return_value = ([fake_seg], fake_info)

    fake_module = MagicMock()
    fake_module.WhisperModel.return_value = fake_model

    with patch.dict("sys.modules", {"faster_whisper": fake_module}):
        result = generate_transcript(
            mp3, tmp_path, "Show_Ep001_20260512",
            model_size="base", language="en",
        )

    assert result is not None
    assert isinstance(result, TranscriptResult)
    assert result.text == "Hello world."
    assert result.txt_path.exists()
    assert result.json_path.exists()
    # Disk content matches the in-memory text — no drift between callers.
    assert result.txt_path.read_text(encoding="utf-8") == result.text


# ---------------------------------------------------------------------------
# validate_tts_transcription: skip Whisper when transcription is supplied
# ---------------------------------------------------------------------------

def test_validation_skips_whisper_when_transcription_supplied(tmp_path: Path):
    """Caller-supplied transcription → no model load, no transcribe."""
    from engine.tts_validation import validate_tts_transcription

    # No audio file — would fail if Whisper actually tried to run.
    fake_audio = tmp_path / "does_not_exist.mp3"

    with patch("engine.tts_validation._get_whisper_model") as mock_loader:
        result = validate_tts_transcription(
            fake_audio,
            expected_text="Hello world.",
            transcription="hello world",  # ← pre-computed, lowercased on purpose
        )

    # Whisper never touched.
    mock_loader.assert_not_called()
    # Validation still ran — comparison + match_score populated.
    assert result["transcription"] == "hello world"
    assert result["match_score"] > 0.0
    assert result["passed"] is True


def test_validation_still_runs_whisper_when_transcription_missing(tmp_path: Path):
    """Backward-compat: no ``transcription`` arg → Whisper still runs.

    Lets callers that don't yet pipe a transcript in keep working
    without modification."""
    from engine.tts_validation import validate_tts_transcription

    mp3 = tmp_path / "audio.mp3"
    mp3.write_bytes(b"\xff\xfb\x90")

    fake_seg = MagicMock(text="Hello world.")
    fake_info = MagicMock(language="en")
    fake_model = MagicMock()
    fake_model.transcribe.return_value = ([fake_seg], fake_info)

    with patch(
        "engine.tts_validation._get_whisper_model",
        return_value=fake_model,
    ) as mock_loader:
        result = validate_tts_transcription(
            mp3, expected_text="Hello world.", model_size="base",
        )

    mock_loader.assert_called_once_with("base")
    fake_model.transcribe.assert_called_once()
    assert result["transcription"].strip() == "Hello world."


def test_validation_with_supplied_transcription_handles_perfect_match(tmp_path: Path):
    """When the supplied transcription matches expected, score is 1.0."""
    from engine.tts_validation import validate_tts_transcription

    fake_audio = tmp_path / "audio.mp3"
    result = validate_tts_transcription(
        fake_audio,
        expected_text="The quick brown fox jumps over the lazy dog.",
        transcription="The quick brown fox jumps over the lazy dog.",
    )
    assert result["match_score"] == 1.0
    assert result["passed"] is True
    assert result["mismatched_words"] == []


def test_validation_with_supplied_transcription_handles_mismatch(tmp_path: Path):
    """Mismatched supplied transcription → low score, mismatches recorded."""
    from engine.tts_validation import validate_tts_transcription

    fake_audio = tmp_path / "audio.mp3"
    result = validate_tts_transcription(
        fake_audio,
        expected_text="The quick brown fox jumps over the lazy dog.",
        transcription="A slow purple cat sleeps under a heavy log.",
        threshold=0.7,
    )
    assert result["match_score"] < 0.7
    assert result["passed"] is False
    assert len(result["mismatched_words"]) > 0
