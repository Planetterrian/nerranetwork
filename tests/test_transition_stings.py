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


# =========================================================================
# 8. TestSectionConcatAcrossfade
# =========================================================================

class TestSectionConcatAcrossfade:
    """Pin the May 8 2026 fix that replaced ``-f concat`` demuxer with
    chained ``acrossfade`` operations on section boundaries.

    Operator caught audible clicks/ticks at every section boundary —
    Grok TTS chunks frequently end at non-zero amplitude (no trailing
    fade-out), and the demuxer joined them straight into the silent
    leading edge of ``padded_sting`` with no smoothing. The amplitude
    discontinuity at each junction was the audible click.

    These tests verify the new ffmpeg command structure carries the
    acrossfade filter chain so a future "let's go back to demuxer for
    speed" refactor surfaces with a specific error.
    """

    def test_uses_acrossfade_filter_complex_for_multi_section(self, tmp_path):
        """The ffmpeg command MUST use ``-filter_complex`` with chained
        ``acrossfade=...:c1=tri:c2=tri`` operations, not ``-f concat``."""
        sections = [tmp_path / f"sec_{i}.mp3" for i in range(3)]
        for s in sections:
            s.write_bytes(b"fake mp3")
        sting = tmp_path / "sting.mp3"
        sting.write_bytes(b"fake sting")
        output = tmp_path / "out.mp3"

        captured_cmds: list[list[str]] = []

        def _fake_run(cmd, **kwargs):
            captured_cmds.append(list(cmd))
            # Make output file exist so the function returns cleanly.
            for i, arg in enumerate(cmd):
                if arg.endswith(".mp3") and i == len(cmd) - 1:
                    Path(arg).parent.mkdir(parents=True, exist_ok=True)
                    Path(arg).write_bytes(b"\x00")
            class _R:
                returncode = 0
                stderr = b""
                stdout = b""
            return _R()

        with patch("engine.audio.subprocess.run", _fake_run):
            concatenate_with_stings(sections, output, sting_path=sting)

        # The FINAL ffmpeg invocation (the section concat) must use
        # acrossfade-based filter_complex, not the demuxer concat.
        # Filter the captured commands to find the one that produced
        # the output path.
        section_concat = next(
            c for c in captured_cmds
            if any(arg.endswith(output.name) for arg in c)
        )
        assert "-filter_complex" in section_concat, (
            "Section concat must use -filter_complex (acrossfade chain), "
            "not -f concat demuxer. The demuxer joins at sample "
            "boundaries with no smoothing — produces clicks at every "
            "section boundary."
        )
        assert "-f" not in section_concat or "concat" not in section_concat, (
            "Section concat must NOT use -f concat demuxer."
        )
        fc_idx = section_concat.index("-filter_complex")
        graph = section_concat[fc_idx + 1]
        # Acrossfade with tri/tri curves is the smoothing primitive.
        assert "acrossfade" in graph
        assert "c1=tri" in graph and "c2=tri" in graph

    def test_acrossfade_duration_is_30ms(self, tmp_path):
        """The crossfade duration is 30 ms — long enough to mask the
        amplitude discontinuity, short enough to be imperceptible as
        content overlap. Pinning so a future "smaller" tweak doesn't
        regress to a value that re-introduces audible clicks."""
        sections = [tmp_path / f"sec_{i}.mp3" for i in range(2)]
        for s in sections:
            s.write_bytes(b"fake mp3")
        sting = tmp_path / "sting.mp3"
        sting.write_bytes(b"fake sting")
        output = tmp_path / "out.mp3"

        captured: list[list[str]] = []

        def _fake_run(cmd, **kwargs):
            captured.append(list(cmd))
            for arg in cmd:
                if arg.endswith(output.name):
                    Path(arg).parent.mkdir(parents=True, exist_ok=True)
                    Path(arg).write_bytes(b"\x00")
            class _R:
                returncode = 0
                stderr = b""
                stdout = b""
            return _R()

        with patch("engine.audio.subprocess.run", _fake_run):
            concatenate_with_stings(sections, output, sting_path=sting)

        section_concat = next(
            c for c in captured if any(arg.endswith(output.name) for arg in c)
        )
        graph = section_concat[section_concat.index("-filter_complex") + 1]
        # 30 ms duration must be present.
        assert "d=0.03" in graph, (
            f"Acrossfade duration must be 0.03 s; filter graph: {graph}"
        )

    def test_chains_acrossfade_for_n_inputs(self, tmp_path):
        """For N inputs (sections + interleaved padded stings), the
        graph must chain N-1 acrossfade operations producing a single
        ``[out]`` label."""
        # 3 sections + 2 stings = 5 inputs interleaved → 4 acrossfades
        sections = [tmp_path / f"sec_{i}.mp3" for i in range(3)]
        for s in sections:
            s.write_bytes(b"x")
        sting = tmp_path / "sting.mp3"
        sting.write_bytes(b"x")
        output = tmp_path / "out.mp3"

        captured: list[list[str]] = []

        def _fake_run(cmd, **kwargs):
            captured.append(list(cmd))
            for arg in cmd:
                if arg.endswith(output.name):
                    Path(arg).parent.mkdir(parents=True, exist_ok=True)
                    Path(arg).write_bytes(b"\x00")
            class _R:
                returncode = 0
                stderr = b""
                stdout = b""
            return _R()

        with patch("engine.audio.subprocess.run", _fake_run):
            concatenate_with_stings(sections, output, sting_path=sting)

        section_concat = next(
            c for c in captured if any(arg.endswith(output.name) for arg in c)
        )
        graph = section_concat[section_concat.index("-filter_complex") + 1]
        # Final label is [out].
        assert "[out]" in graph
        # 4 acrossfade operations for 5 inputs.
        assert graph.count("acrossfade") == 4
        # -map [out] used as output target.
        assert "-map" in section_concat
        assert section_concat[section_concat.index("-map") + 1] == "[out]"
