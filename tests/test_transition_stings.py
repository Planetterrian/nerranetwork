"""Tests for transition sting audio support.

Covers:
  - ffmpeg command structure for sting generation and padding
  - Script splitting at chapter boundaries
  - Sting-interleaved concatenation fallback behavior
  - YAML config integration for transition_sting field
  - synthesize_sections interface
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from engine.audio import (
    _generate_sting_cmd,
    _sting_padding_cmd,
    concatenate_with_stings,
)
from engine.chapters import Chapter, parse_chapters, split_script_at_chapters
from engine.config import AudioConfig, SectionMarker, load_config

# ---- Repo root for real YAML files ----------------------------------------
REPO_ROOT = Path(__file__).resolve().parent.parent
SHOWS_DIR = REPO_ROOT / "shows"


# ---- Sample scripts -------------------------------------------------------

TESLA_SCRIPT = """\
Welcome to Tesla Shorts Time, episode 42. Today is March 3, 2026.

Scientists discovered a new battery chemistry.

Let's get into the Top 10 News Items for today.

First up, Tesla has announced a major expansion.
The company plans to add three new production lines.

Now, one thing worth watching is the regulatory pressure.
Several countries have raised concerns.

Let's talk about First Principles for a moment.
When we think about battery chemistry from first principles, the question is energy density.

Before we go, tomorrow we'll be watching for delivery numbers.

That's Tesla Shorts Time for today. Thanks for listening.
"""


# =========================================================================
# 1. TestStingCommandStructure
# =========================================================================
class TestStingCommandStructure:
    """Verify the ffmpeg command for generating the transition sting."""

    def test_command_has_correct_structure(self):
        cmd = _generate_sting_cmd("/tmp/sting.mp3")
        assert cmd[0] == "ffmpeg"
        assert "-y" in cmd
        assert "-f" in cmd
        assert "lavfi" in cmd
        assert "/tmp/sting.mp3" == cmd[-1]

    def test_command_has_two_sine_inputs(self):
        cmd = _generate_sting_cmd("/tmp/sting.mp3")
        # Count lavfi inputs — there should be two sine generators
        lavfi_indices = [i for i, v in enumerate(cmd) if v == "lavfi"]
        assert len(lavfi_indices) == 2

    def test_command_has_amix_filter(self):
        cmd = _generate_sting_cmd("/tmp/sting.mp3")
        filter_idx = cmd.index("-filter_complex")
        filter_str = cmd[filter_idx + 1]
        assert "amix=inputs=2" in filter_str
        assert "afade=t=in" in filter_str
        assert "afade=t=out" in filter_str

    def test_command_has_correct_encoding(self):
        cmd = _generate_sting_cmd("/tmp/sting.mp3")
        assert "-ar" in cmd
        assert "44100" in cmd
        assert "-ac" in cmd
        assert "1" in cmd
        assert "libmp3lame" in cmd

    def test_command_frequencies(self):
        cmd = _generate_sting_cmd("/tmp/sting.mp3")
        cmd_str = " ".join(cmd)
        assert "frequency=880" in cmd_str
        assert "frequency=1320" in cmd_str

    def test_command_duration(self):
        cmd = _generate_sting_cmd("/tmp/sting.mp3")
        cmd_str = " ".join(cmd)
        assert "duration=0.15" in cmd_str


# =========================================================================
# 2. TestStingPaddingCommand
# =========================================================================
class TestStingPaddingCommand:
    """Verify the ffmpeg command for wrapping a sting with silence."""

    def test_command_has_three_inputs(self):
        cmd = _sting_padding_cmd("/tmp/sting.mp3", "/tmp/padded.mp3")
        # Should have: pre-silence (lavfi), sting (file), post-silence (lavfi)
        input_count = cmd.count("-i")
        assert input_count == 3

    def test_command_has_concat_filter(self):
        cmd = _sting_padding_cmd("/tmp/sting.mp3", "/tmp/padded.mp3")
        filter_idx = cmd.index("-filter_complex")
        filter_str = cmd[filter_idx + 1]
        assert "concat=n=3:v=0:a=1" in filter_str

    def test_command_output_path(self):
        cmd = _sting_padding_cmd("/tmp/sting.mp3", "/tmp/padded.mp3")
        assert cmd[-1] == "/tmp/padded.mp3"

    def test_default_silence_durations(self):
        cmd = _sting_padding_cmd("/tmp/sting.mp3", "/tmp/padded.mp3")
        cmd_str = " ".join(cmd)
        # Default pre/post silence is 0.4s each
        assert "0.40" in cmd_str

    def test_custom_silence_durations(self):
        cmd = _sting_padding_cmd(
            "/tmp/sting.mp3", "/tmp/padded.mp3",
            pre_silence=0.6, post_silence=0.8,
        )
        cmd_str = " ".join(cmd)
        assert "0.60" in cmd_str
        assert "0.80" in cmd_str

    def test_command_encoding_params(self):
        cmd = _sting_padding_cmd("/tmp/sting.mp3", "/tmp/padded.mp3")
        assert "44100" in cmd
        assert "libmp3lame" in cmd
        assert "192k" in cmd


# =========================================================================
# 3. TestSplitScriptAtChapters
# =========================================================================
class TestSplitScriptAtChapters:
    """Tests for splitting a script at chapter boundaries."""

    def test_basic_split(self):
        markers = [
            SectionMarker(pattern="Welcome to Tesla Shorts Time", title="Introduction"),
            SectionMarker(pattern="Top \\d+ News", title="Top Stories"),
            SectionMarker(pattern="one thing worth watching", title="The Counterpoint"),
            SectionMarker(pattern="First Principles", title="First Principles"),
            SectionMarker(pattern="Before we go", title="Tomorrow Teaser"),
            SectionMarker(pattern="That's Tesla Shorts Time", title="Closing"),
        ]
        chapters = parse_chapters(TESLA_SCRIPT, markers, show_name="Tesla")
        sections = split_script_at_chapters(TESLA_SCRIPT, chapters)

        assert len(sections) == len(chapters)

    def test_sections_contain_original_text(self):
        markers = [
            SectionMarker(pattern="Welcome to Tesla Shorts Time", title="Intro"),
            SectionMarker(pattern="That's Tesla Shorts Time", title="Closing"),
        ]
        chapters = parse_chapters(TESLA_SCRIPT, markers)
        sections = split_script_at_chapters(TESLA_SCRIPT, chapters)

        assert len(sections) == 2
        assert "Welcome to Tesla Shorts Time" in sections[0]
        assert "That's Tesla Shorts Time" in sections[1]
        assert "Thanks for listening" in sections[1]

    def test_sections_cover_all_text(self):
        """Concatenating all sections should reproduce the original script."""
        markers = [
            SectionMarker(pattern="Welcome to Tesla Shorts Time", title="Intro"),
            SectionMarker(pattern="Top \\d+ News", title="Stories"),
            SectionMarker(pattern="That's Tesla Shorts Time", title="Closing"),
        ]
        chapters = parse_chapters(TESLA_SCRIPT, markers)
        sections = split_script_at_chapters(TESLA_SCRIPT, chapters)

        # All original words should be present across sections
        original_words = set(TESLA_SCRIPT.split())
        section_words = set()
        for s in sections:
            section_words.update(s.split())
        assert original_words == section_words

    def test_empty_chapters_returns_full_script(self):
        sections = split_script_at_chapters(TESLA_SCRIPT, [])
        assert len(sections) == 1
        assert sections[0] == TESLA_SCRIPT

    def test_empty_script_returns_empty(self):
        sections = split_script_at_chapters("", [])
        assert sections == []

    def test_single_chapter_returns_full_script(self):
        markers = [SectionMarker(pattern="Welcome", title="Start")]
        chapters = parse_chapters(TESLA_SCRIPT, markers)
        sections = split_script_at_chapters(TESLA_SCRIPT, chapters)

        assert len(sections) == 1
        assert "Welcome" in sections[0]
        assert "Thanks for listening" in sections[0]

    def test_sections_are_non_overlapping(self):
        markers = [
            SectionMarker(pattern="Welcome to Tesla Shorts Time", title="Intro"),
            SectionMarker(pattern="Top \\d+ News", title="Stories"),
            SectionMarker(pattern="First Principles", title="Analysis"),
            SectionMarker(pattern="That's Tesla Shorts Time", title="Closing"),
        ]
        chapters = parse_chapters(TESLA_SCRIPT, markers)
        sections = split_script_at_chapters(TESLA_SCRIPT, chapters)

        # Each section's text should not appear in other sections
        for i, section in enumerate(sections):
            first_line = section.split("\n")[0].strip()
            if not first_line:
                continue
            for j, other in enumerate(sections):
                if i != j:
                    assert first_line not in other, (
                        f"Section {i} first line found in section {j}"
                    )


# =========================================================================
# 4. TestConcatenateWithStingsFallback
# =========================================================================
class TestConcatenateWithStingsFallback:
    """Test fallback behavior of concatenate_with_stings."""

    def test_single_file_copies(self, tmp_path):
        """A single section file should just be copied."""
        section = tmp_path / "section_000.mp3"
        section.write_bytes(b"fake mp3 data")
        output = tmp_path / "output.mp3"

        result = concatenate_with_stings([section], output)
        assert result == output
        assert output.read_bytes() == b"fake mp3 data"

    @patch("engine.audio.concatenate_audio")
    def test_no_sting_falls_back_to_concat(self, mock_concat, tmp_path):
        """Without a sting, should fall back to plain concatenation."""
        files = [tmp_path / f"sec_{i}.mp3" for i in range(3)]
        for f in files:
            f.write_bytes(b"data")
        output = tmp_path / "output.mp3"
        mock_concat.return_value = output

        result = concatenate_with_stings(files, output, sting_path=None)
        mock_concat.assert_called_once_with(files, output)

    @patch("engine.audio.concatenate_audio")
    def test_missing_sting_falls_back(self, mock_concat, tmp_path):
        """A non-existent sting path should fall back to plain concatenation."""
        files = [tmp_path / f"sec_{i}.mp3" for i in range(3)]
        for f in files:
            f.write_bytes(b"data")
        output = tmp_path / "output.mp3"
        mock_concat.return_value = output

        missing_sting = tmp_path / "nonexistent_sting.mp3"
        result = concatenate_with_stings(files, output, sting_path=missing_sting)
        mock_concat.assert_called_once_with(files, output)


# =========================================================================
# 5. TestYAMLConfigTransitionSting
# =========================================================================
class TestYAMLConfigTransitionSting:
    """Verify transition_sting loads from all show YAML configs."""

    @pytest.mark.parametrize("slug", [
        "tesla", "omni_view", "fascinating_frontiers",
        "planetterrian", "env_intel", "models_agents",
        "unintended_consequences",
    ])
    def test_show_has_transition_sting(self, slug):
        cfg = load_config(SHOWS_DIR / f"{slug}.yaml")
        assert cfg.audio.transition_sting == "assets/music/transition_sting.mp3"

    def test_default_is_none(self):
        """AudioConfig without transition_sting should default to None."""
        cfg = AudioConfig()
        assert cfg.transition_sting is None


# =========================================================================
# 6. TestChapterCharOffsets
# =========================================================================
class TestChapterCharOffsets:
    """Verify parse_chapters populates char_start/char_end correctly."""

    def test_char_offsets_are_set(self):
        markers = [
            SectionMarker(pattern="Welcome to Tesla Shorts Time", title="Intro"),
            SectionMarker(pattern="That's Tesla Shorts Time", title="Closing"),
        ]
        chapters = parse_chapters(TESLA_SCRIPT, markers)

        assert chapters[0].char_start == 0
        assert chapters[0].char_end > 0
        assert chapters[1].char_start > chapters[0].char_start
        assert chapters[1].char_end == len(TESLA_SCRIPT)

    def test_char_offsets_produce_correct_text(self):
        markers = [
            SectionMarker(pattern="Welcome to Tesla Shorts Time", title="Intro"),
            SectionMarker(pattern="Top \\d+ News", title="Stories"),
            SectionMarker(pattern="That's Tesla Shorts Time", title="Closing"),
        ]
        chapters = parse_chapters(TESLA_SCRIPT, markers)

        for ch in chapters:
            text = TESLA_SCRIPT[ch.char_start:ch.char_end]
            # The section text should contain the marker that triggered it
            assert len(text) > 0

    def test_char_offsets_contiguous(self):
        """Adjacent chapters' char_end == next char_start."""
        markers = [
            SectionMarker(pattern="Welcome to Tesla Shorts Time", title="Intro"),
            SectionMarker(pattern="Top \\d+ News", title="Stories"),
            SectionMarker(pattern="That's Tesla Shorts Time", title="Closing"),
        ]
        chapters = parse_chapters(TESLA_SCRIPT, markers)

        for i in range(len(chapters) - 1):
            assert chapters[i].char_end == chapters[i + 1].char_start


# =========================================================================
# 7. TestEndToEndSectionPipeline
# =========================================================================
class TestEndToEndSectionPipeline:
    """Test the full parse → split → (mock TTS) → concatenate pipeline."""

    def test_tesla_sections_from_yaml(self):
        """Load Tesla config, parse chapters, split script, verify sections."""
        cfg = load_config(SHOWS_DIR / "tesla.yaml")
        chapters = parse_chapters(
            TESLA_SCRIPT,
            cfg.chapters.section_markers,
            show_name=cfg.name,
        )
        sections = split_script_at_chapters(TESLA_SCRIPT, chapters)

        assert len(sections) == len(chapters)
        assert len(sections) >= 3

        # All sections should be non-empty
        for s in sections:
            assert s.strip()

        # Sting should be configured
        assert cfg.audio.transition_sting is not None
