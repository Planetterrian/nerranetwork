"""Tests for _clean_podcast_script — speaker prefix stripping for TTS.

Ensures that speaker labels like "Host:", "Patrick:", etc. never leak into
the text sent to TTS synthesis, regardless of LLM output format.
"""

import re
import sys
import textwrap
from pathlib import Path

import pytest

# Ensure run_show can be imported for its helper functions.
# We use AST extraction to avoid triggering top-level imports.
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


def _load_clean_fn():
    """Extract _clean_podcast_script from run_show.py via exec to avoid
    heavy top-level imports (dotenv, openai, etc.)."""
    import ast

    source = (PROJECT_ROOT / "run_show.py").read_text(encoding="utf-8")
    tree = ast.parse(source)

    # Find the function definitions we need
    needed = {
        "_clean_podcast_script",
        "_break_long_paragraphs",
        "_strip_trailing_sources_block",
    }
    funcs = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name in needed:
            funcs[node.name] = ast.get_source_segment(source, node)

    assert needed <= set(funcs), f"Missing functions: {needed - set(funcs)}"

    # Also extract the module-level _SENTENCE_SPLIT_RE
    ns = {"_SENTENCE_SPLIT_RE": None}
    for name in (
        "_break_long_paragraphs",
        "_strip_trailing_sources_block",
        "_clean_podcast_script",
    ):
        exec(funcs[name], ns)  # noqa: S102

    return ns["_clean_podcast_script"]


_clean_podcast_script = _load_clean_fn()


# ---------------------------------------------------------------------------
# Basic prefix stripping
# ---------------------------------------------------------------------------

class TestBasicPrefixStripping:
    """Test that speaker prefixes are stripped from line starts."""

    def test_host_prefix(self):
        script = "Host: Welcome to the show.\nHost: Let's begin."
        result = _clean_podcast_script(script, host_name="Host")
        assert "Host:" not in result
        assert "Welcome to the show." in result
        assert "Let's begin." in result

    def test_patrick_prefix(self):
        script = "Patrick: Welcome to the show.\nPatrick: Let's begin."
        result = _clean_podcast_script(script, host_name="Patrick")
        assert "Patrick:" not in result

    def test_russian_prefix(self):
        script = "Ведущая: Добро пожаловать.\nВедущий: Начнём."
        result = _clean_podcast_script(script, host_name="Ведущая")
        assert "Ведущая:" not in result
        assert "Ведущий:" not in result

    def test_narrator_prefix(self):
        script = "Narrator: Once upon a time."
        result = _clean_podcast_script(script)
        assert "Narrator:" not in result

    def test_no_prefix_preserved(self):
        script = "This line has no prefix."
        result = _clean_podcast_script(script)
        assert result == "This line has no prefix."


# ---------------------------------------------------------------------------
# Multi-prefix lines (the core bug scenario)
# ---------------------------------------------------------------------------

class TestMultiPrefixLines:
    """Test that Host: labels mid-line are stripped after paragraph breaking."""

    def test_multiple_host_on_single_line(self):
        """When the LLM generates multiple Host: segments on one line,
        all should be stripped after paragraph breaking."""
        script = (
            "Host: Welcome to the show. Host: Multiple perspectives. "
            "Host: We cover what happened."
        )
        result = _clean_podcast_script(script, host_name="Host")
        assert "Host:" not in result
        assert "Welcome to the show." in result
        assert "Multiple perspectives." in result

    def test_long_line_with_embedded_host(self):
        """A long line where _break_long_paragraphs splits at a sentence
        boundary that happens to precede a Host: label."""
        # Build a long line (>400 chars) with Host: mid-text
        line = (
            "Host: " + "A" * 200 + " important development. "
            "Host: The next major point. "
            "Host: And a final thought on this."
        )
        result = _clean_podcast_script(line, host_name="Host")
        assert "Host:" not in result

    def test_patrick_mid_line(self):
        """Same test with Patrick: prefix."""
        script = (
            "Patrick: Welcome to Tesla Shorts Time. Patrick: Today we "
            "cover the latest developments."
        )
        result = _clean_podcast_script(script, host_name="Patrick")
        assert "Patrick:" not in result


# ---------------------------------------------------------------------------
# LLM preamble filtering
# ---------------------------------------------------------------------------

class TestPreambleFiltering:
    """Test that LLM retry/expansion preambles are dropped."""

    @pytest.mark.parametrize("preamble", [
        "Here's your expanded script (approximately 1780 words):",
        "Here is your rewritten script with more depth:",
        "I've expanded the script to cover more ground:",
        "Here's the revised version:",
        "Here's my updated script:",
    ])
    def test_preamble_dropped(self, preamble):
        script = f"{preamble}\nHost: Welcome to the show."
        result = _clean_podcast_script(script, host_name="Host")
        assert "expanded" not in result.lower()
        assert "rewritten" not in result.lower()
        assert "revised" not in result.lower()
        assert "Welcome to the show." in result


# ---------------------------------------------------------------------------
# Stage direction and metadata filtering
# ---------------------------------------------------------------------------

class TestStageDirections:

    def test_bracketed_notes_skipped(self):
        script = "[Intro music]\nHost: Welcome.\n[Pause]"
        result = _clean_podcast_script(script, host_name="Host")
        assert "[" not in result
        assert "Welcome." in result

    def test_word_count_metadata_not_spoken(self):
        """Word count metadata should not appear in spoken output."""
        script = "Host: Main content here.\nWord count: 1500"
        result = _clean_podcast_script(script, host_name="Host")
        assert "Main content here." in result
        # The metadata line itself should not be treated as spoken content
        assert "1500" not in result or "Word count" not in result

    def test_leaked_prompt_instructions_dropped(self):
        script = (
            "RULES:\n"
            "- Start every line with Host:\n"
            "Host: Welcome to the show."
        )
        result = _clean_podcast_script(script, host_name="Host")
        assert "RULES" not in result
        assert "Welcome to the show." in result


# ---------------------------------------------------------------------------
# Real-world regression: actual Ep018 TTS file content
# ---------------------------------------------------------------------------

class TestRealWorldRegression:
    """Test against actual episode content that had the bug."""

    def test_omni_view_ep018_pattern(self):
        """Reproduce the exact pattern from OV Ep018 where Host: labels
        appeared at topic transitions in the TTS file."""
        script = textwrap.dedent("""\
            Host: Welcome to Omni View, episode eighteen.
            Host: Multiple perspectives, one briefing.
            Host: We begin with the escalating conflict in Iran.
            Attacks on critical energy infrastructure have disrupted flows.
            This has triggered an immediate jump in prices.
            Host: Different outlets have framed this energy crisis differently.
            The BBC places the story in historical context.
            Host: What stands out is how quickly a regional conflict translated into pain.
            Host: That wraps up today's Omni View.
            Host: See you tomorrow.
        """)
        result = _clean_podcast_script(script, host_name="Host")
        host_count = len(re.findall(r"Host:", result))
        assert host_count == 0, f"Found {host_count} leaked Host: labels"

    def test_actual_ep018_file(self):
        """If the actual Ep018 TTS file exists, verify cleaning removes
        all Host: labels."""
        tts_file = PROJECT_ROOT / "digests/omni_view/Omni_View_Ep018_20260319_tts.txt"
        if not tts_file.exists():
            pytest.skip("Ep018 TTS file not present")
        content = tts_file.read_text(encoding="utf-8")
        result = _clean_podcast_script(content, host_name="Host")
        host_count = len(re.findall(r"^Host:", result, re.MULTILINE))
        assert host_count == 0, f"Found {host_count} leaked Host: labels in cleaned Ep018"

    def test_actual_ma_ep020_file(self):
        """If the actual M&A Ep020 TTS file exists, verify cleaning removes
        all Host: labels."""
        tts_file = PROJECT_ROOT / "digests/models_agents/Models_Agents_Ep020_20260319_tts.txt"
        if not tts_file.exists():
            pytest.skip("M&A Ep020 TTS file not present")
        content = tts_file.read_text(encoding="utf-8")
        result = _clean_podcast_script(content, host_name="Host")
        host_count = len(re.findall(r"^Host:", result, re.MULTILINE))
        assert host_count == 0, f"Found {host_count} leaked Host: labels in cleaned M&A Ep020"


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------

class TestEdgeCases:

    def test_empty_script(self):
        assert _clean_podcast_script("") == ""

    def test_only_prefixes(self):
        script = "Host:\nHost:\nHost:"
        result = _clean_podcast_script(script, host_name="Host")
        assert result == ""

    def test_host_in_content_not_stripped(self):
        """The word 'host' mid-sentence should NOT be stripped."""
        script = "The host city for the Olympics was announced today."
        result = _clean_podcast_script(script)
        assert "host city" in result

    def test_colon_in_content_preserved(self):
        """Colons in normal content should not trigger stripping."""
        script = "The answer is simple: invest early."
        result = _clean_podcast_script(script)
        assert "simple: invest" in result
