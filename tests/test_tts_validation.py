"""Tests for engine.tts_validation — post-TTS Whisper transcription validation.

These tests exercise the text normalization and mismatch extraction logic
without requiring the Whisper model (which is large and slow to load).
"""

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch


sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from engine.tts_validation import (
    _extract_mismatches,
    _normalize_for_comparison,
    validate_tts_transcription,
)


# ── _normalize_for_comparison tests ──


class TestNormalizeForComparison:
    def test_lowercases(self):
        assert _normalize_for_comparison("Hello WORLD") == "hello world"

    def test_strips_punctuation(self):
        assert _normalize_for_comparison("Hello, world!") == "hello world"

    def test_preserves_apostrophes(self):
        assert _normalize_for_comparison("it's a dog's life") == "it's a dog's life"

    def test_collapses_whitespace(self):
        assert _normalize_for_comparison("hello   world\n\nfoo") == "hello world foo"

    def test_strips_special_characters(self):
        assert _normalize_for_comparison("AI — the future!") == "ai the future"

    def test_empty_string(self):
        assert _normalize_for_comparison("") == ""

    def test_numbers_preserved(self):
        assert _normalize_for_comparison("GPT 4 is great") == "gpt 4 is great"

    def test_hyphens_become_spaces(self):
        assert _normalize_for_comparison("AI-powered tool") == "ai powered tool"


# ── _extract_mismatches tests ──


class TestExtractMismatches:
    def test_no_mismatches(self):
        words = ["hello", "world"]
        result = _extract_mismatches(words, words)
        assert result == []

    def test_replacement(self):
        expected = ["hello", "world", "foo"]
        transcribed = ["hello", "earth", "foo"]
        result = _extract_mismatches(expected, transcribed)
        assert len(result) == 1
        assert result[0]["type"] == "replace"
        assert result[0]["expected"] == "world"
        assert result[0]["heard"] == "earth"

    def test_insertion(self):
        expected = ["hello", "world"]
        transcribed = ["hello", "big", "world"]
        result = _extract_mismatches(expected, transcribed)
        assert any(m["type"] == "insert" for m in result)

    def test_deletion(self):
        expected = ["hello", "big", "world"]
        transcribed = ["hello", "world"]
        result = _extract_mismatches(expected, transcribed)
        assert any(m["type"] == "delete" for m in result)

    def test_context_included(self):
        expected = ["the", "quick", "brown", "fox", "jumped"]
        transcribed = ["the", "quick", "green", "fox", "jumped"]
        result = _extract_mismatches(expected, transcribed, context=2)
        assert len(result) == 1
        assert "quick" in result[0]["context"]
        assert "fox" in result[0]["context"]


# ── validate_tts_transcription tests (mocked Whisper) ──


class TestValidateTtsTranscription:
    def test_missing_audio_file(self, tmp_path):
        result = validate_tts_transcription(
            tmp_path / "nonexistent.mp3",
            "hello world",
        )
        assert result["error"] is not None
        assert "not found" in result["error"]
        assert result["match_score"] == 0.0

    def test_empty_expected_text(self, tmp_path):
        audio = tmp_path / "test.mp3"
        audio.write_bytes(b"\x00" * 1000)

        with patch("engine.tts_validation._get_whisper_model") as mock_model:
            mock_model.return_value = None
            result = validate_tts_transcription(audio, "")
            # Model unavailable — should pass gracefully
            assert result["passed"] is True

    @patch("engine.tts_validation._get_whisper_model")
    def test_perfect_match(self, mock_get_model, tmp_path):
        audio = tmp_path / "test.mp3"
        audio.write_bytes(b"\x00" * 1000)

        # Mock Whisper transcription
        mock_segment = MagicMock()
        mock_segment.text = "Hello world this is a test"
        mock_model = MagicMock()
        mock_model.transcribe.return_value = ([mock_segment], MagicMock())
        mock_get_model.return_value = mock_model

        result = validate_tts_transcription(
            audio,
            "Hello world, this is a test!",
            threshold=0.7,
        )
        assert result["match_score"] == 1.0
        assert result["passed"] is True
        assert result["mismatched_words"] == []

    @patch("engine.tts_validation._get_whisper_model")
    def test_partial_match(self, mock_get_model, tmp_path):
        audio = tmp_path / "test.mp3"
        audio.write_bytes(b"\x00" * 1000)

        mock_segment = MagicMock()
        mock_segment.text = "Hello earth this is a quiz"
        mock_model = MagicMock()
        mock_model.transcribe.return_value = ([mock_segment], MagicMock())
        mock_get_model.return_value = mock_model

        result = validate_tts_transcription(
            audio,
            "Hello world, this is a test!",
            threshold=0.9,
        )
        assert 0.0 < result["match_score"] < 1.0
        assert result["passed"] is False
        assert len(result["mismatched_words"]) > 0

    @patch("engine.tts_validation._get_whisper_model")
    def test_low_threshold_passes(self, mock_get_model, tmp_path):
        audio = tmp_path / "test.mp3"
        audio.write_bytes(b"\x00" * 1000)

        mock_segment = MagicMock()
        mock_segment.text = "Hello earth this is a quiz"
        mock_model = MagicMock()
        mock_model.transcribe.return_value = ([mock_segment], MagicMock())
        mock_get_model.return_value = mock_model

        result = validate_tts_transcription(
            audio,
            "Hello world, this is a test!",
            threshold=0.3,
        )
        assert result["passed"] is True

    def test_whisper_unavailable_passes_gracefully(self, tmp_path):
        audio = tmp_path / "test.mp3"
        audio.write_bytes(b"\x00" * 1000)

        with patch("engine.tts_validation._get_whisper_model", return_value=None):
            result = validate_tts_transcription(audio, "hello world")
            assert result["passed"] is True
            assert result["error"] == "Whisper model not available"
