"""Tests for engine/chapters.py — podcast chapter parsing and generation."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from engine.chapters import (
    Chapter,
    calculate_timestamps,
    parse_chapters,
    split_script_at_chapters,
    write_chapters_json,
)
from engine.config import ChaptersConfig, SectionMarker, load_config

# ---- Repo root for real show YAML files ----------------------------------
REPO_ROOT = Path(__file__).resolve().parent.parent
SHOWS_DIR = REPO_ROOT / "shows"


# =========================================================================
# Sample podcast scripts for testing
# =========================================================================

TESLA_SCRIPT = """\
Welcome to Tesla Shorts Time, episode 42. Today is March 3, 2026. Here's what's making news.

Scientists discovered a new battery chemistry that could double range.

Let's get into the Top 10 News Items for today.

First up, Tesla has announced a major expansion of its Gigafactory in Austin, Texas.
The company plans to add three new production lines dedicated to the Cybertruck.
This is significant because it signals continued confidence in the truck's market demand.
According to Teslarati, the expansion could boost annual production capacity by 200,000 units.

Next, Tesla's Full Self-Driving software has reached a new milestone.
The latest update includes improved handling of unprotected left turns.
This has been one of the most challenging scenarios for the system.

Now, one thing worth watching is the ongoing regulatory pressure in Europe.
Several countries have raised concerns about autonomous driving features.
This could slow Tesla's rollout of FSD in key European markets.
However, Tesla has been proactive in working with regulators.

Let's talk about First Principles for a moment.
When we think about battery chemistry from first principles, the question isn't just about energy density.
It's about the entire supply chain, from mining to recycling.

Before we go, tomorrow we'll be watching for Tesla's quarterly delivery numbers.

That's Tesla Shorts Time for today. If you enjoyed this episode, a rating or review
on Apple Podcasts or Spotify really helps new listeners find the show.
I'm Patrick in Vancouver. Thanks for listening, and I'll see you tomorrow.
"""

ENV_INTEL_SCRIPT = """\
Good morning. This is Environmental Intelligence, episode 15, for March 3, 2026.
Your daily briefing on environmental regulatory, science, and compliance developments.

The BC Ministry has released new contaminated sites guidelines.

Here's what matters most today in our executive summary.
The federal government has announced new PFAS limits, and BC has updated its CSR Schedule 10.

Let's dive into our lead story. The most significant development today is the updated
PFAS drinking water guidelines from Health Canada. The new maximum acceptable concentration
has been lowered from 200 nanograms per litre to 30 nanograms per litre.

Moving to our regulatory and policy watch section. Alberta's Energy Regulator has published
new requirements for tailings pond monitoring. Ontario has opened a 60-day consultation
on changes to its Environmental Protection Act.

On the science and technical front, a new study in Nature Climate Change has found that
permafrost thaw is accelerating faster than models predicted.

Looking at industry and practice developments, several major consulting firms have begun
offering PFAS-specific site assessment services.

Here are your action items for the week. If you're working on contaminated sites in BC,
review the updated CSR Schedule 10.

Mark your calendar for the week ahead. The CCME meeting is Thursday.

Before we wrap, tomorrow watch for the Ontario EPA consultation deadline.

That's Environmental Intelligence for March 3, 2026. If this briefing is useful to your
practice, share it with a colleague. We're back tomorrow. Have a productive day.
"""

SIMPLE_SCRIPT = """\
Welcome to the show, episode 1.

Here is our first story about technology.

Now shifting to our second story about science.

That's all for today. See you tomorrow.
"""


# =========================================================================
# 1. TestParseChapters
# =========================================================================
class TestParseChapters:
    """Tests for the parse_chapters function."""

    def test_tesla_markers(self):
        markers = [
            SectionMarker(pattern="Welcome to Tesla Shorts Time", title="Introduction"),
            SectionMarker(pattern="Top \\d+ News", title="Top Stories"),
            SectionMarker(pattern="one thing worth watching|challenge worth discussing", title="The Counterpoint"),
            SectionMarker(pattern="First Principles", title="First Principles"),
            SectionMarker(pattern="Before we go", title="Tomorrow Teaser"),
            SectionMarker(pattern="That's Tesla Shorts Time", title="Closing"),
        ]
        chapters = parse_chapters(TESLA_SCRIPT, markers, show_name="Tesla")

        titles = [c.title for c in chapters]
        assert "Introduction" in titles
        assert "Top Stories" in titles
        assert "The Counterpoint" in titles
        assert "First Principles" in titles
        assert "Tomorrow Teaser" in titles
        assert "Closing" in titles

    def test_env_intel_markers(self):
        markers = [
            SectionMarker(pattern="This is Environmental Intelligence", title="Introduction"),
            SectionMarker(pattern="executive summary|here's what matters", title="Executive Summary"),
            SectionMarker(pattern="lead story|most significant", title="Lead Story"),
            SectionMarker(pattern="regulatory|policy watch", title="Regulatory & Policy Watch"),
            SectionMarker(pattern="science|technical", title="Science & Technical"),
            SectionMarker(pattern="industry|practice", title="Industry & Practice"),
            SectionMarker(pattern="action items", title="Action Items"),
            SectionMarker(pattern="week ahead|mark your calendar", title="Week Ahead"),
            SectionMarker(pattern="Before we wrap", title="Tomorrow Teaser"),
            SectionMarker(pattern="That's Environmental Intelligence", title="Closing"),
        ]
        chapters = parse_chapters(ENV_INTEL_SCRIPT, markers, show_name="Env Intel")

        assert len(chapters) >= 5
        titles = [c.title for c in chapters]
        assert "Introduction" in titles
        assert "Closing" in titles

    def test_chapters_have_ordered_word_boundaries(self):
        markers = [
            SectionMarker(pattern="Welcome to Tesla Shorts Time", title="Introduction"),
            SectionMarker(pattern="Top \\d+ News", title="Top Stories"),
            SectionMarker(pattern="That's Tesla Shorts Time", title="Closing"),
        ]
        chapters = parse_chapters(TESLA_SCRIPT, markers)

        for i in range(len(chapters) - 1):
            assert chapters[i].word_start < chapters[i + 1].word_start
            assert chapters[i].word_end == chapters[i + 1].word_start

    def test_last_chapter_extends_to_end(self):
        markers = [
            SectionMarker(pattern="Welcome to Tesla Shorts Time", title="Introduction"),
            SectionMarker(pattern="That's Tesla Shorts Time", title="Closing"),
        ]
        chapters = parse_chapters(TESLA_SCRIPT, markers)
        total_words = len(TESLA_SCRIPT.split())
        assert chapters[-1].word_end == total_words

    def test_empty_markers_returns_empty(self):
        chapters = parse_chapters(TESLA_SCRIPT, [])
        assert chapters == []

    def test_no_matches_returns_empty(self):
        markers = [SectionMarker(pattern="XYZZY_NEVER_MATCHES", title="Nothing")]
        chapters = parse_chapters(TESLA_SCRIPT, markers)
        assert chapters == []

    def test_empty_script_returns_empty(self):
        markers = [SectionMarker(pattern="Hello", title="Greeting")]
        chapters = parse_chapters("", markers)
        assert chapters == []

    def test_case_insensitive_matching(self):
        markers = [
            SectionMarker(pattern="welcome to the show", title="Intro"),
            SectionMarker(pattern="that's all for today", title="Closing"),
        ]
        chapters = parse_chapters(SIMPLE_SCRIPT, markers)
        assert len(chapters) == 2

    def test_dict_markers_accepted(self):
        """parse_chapters should accept dicts as well as SectionMarker objects."""
        markers = [
            {"pattern": "Welcome to Tesla Shorts Time", "title": "Introduction"},
            {"pattern": "That's Tesla Shorts Time", "title": "Closing"},
        ]
        chapters = parse_chapters(TESLA_SCRIPT, markers)
        assert len(chapters) == 2
        assert chapters[0].title == "Introduction"
        assert chapters[1].title == "Closing"

    def test_invalid_regex_skipped(self):
        markers = [
            SectionMarker(pattern="[invalid regex", title="Bad"),
            SectionMarker(pattern="Welcome to Tesla Shorts Time", title="Good"),
        ]
        chapters = parse_chapters(TESLA_SCRIPT, markers)
        assert len(chapters) >= 1
        assert chapters[0].title == "Good"

    def test_no_duplicate_consecutive_titles(self):
        """If the same marker matches multiple consecutive lines, only one chapter is created."""
        script = "Welcome line one\nWelcome line two\nGoodbye"
        markers = [
            SectionMarker(pattern="Welcome", title="Intro"),
            SectionMarker(pattern="Goodbye", title="End"),
        ]
        chapters = parse_chapters(script, markers)
        intro_count = sum(1 for c in chapters if c.title == "Intro")
        assert intro_count == 1


# =========================================================================
# 2. TestCalculateTimestamps
# =========================================================================
class TestCalculateTimestamps:
    """Tests for the calculate_timestamps function."""

    def test_basic_proportional_mapping(self):
        chapters = [
            Chapter(title="Intro", word_start=0, word_end=100),
            Chapter(title="Main", word_start=100, word_end=400),
            Chapter(title="Closing", word_start=400, word_end=500),
        ]
        result = calculate_timestamps(chapters, total_duration=500.0, music_intro_offset=0.0)

        assert result[0].startTime == 0.0
        assert result[0].endTime == 100.0
        assert result[1].startTime == 100.0
        assert result[1].endTime == 400.0
        assert result[2].startTime == 400.0
        assert result[2].endTime == 500.0  # Clamped to total

    def test_music_intro_offset(self):
        chapters = [
            Chapter(title="Intro", word_start=0, word_end=100),
            Chapter(title="Main", word_start=100, word_end=200),
        ]
        result = calculate_timestamps(chapters, total_duration=120.0, music_intro_offset=20.0)

        # Voice content: 120 - 20 = 100s
        # Intro: 0/200 * 100 + 20 = 20.0
        assert result[0].startTime == 20.0
        # Main: 100/200 * 100 + 20 = 70.0
        assert result[1].startTime == 70.0
        assert result[1].endTime == 120.0

    def test_empty_chapters(self):
        result = calculate_timestamps([], total_duration=300.0)
        assert result == []

    def test_zero_duration(self):
        chapters = [Chapter(title="Test", word_start=0, word_end=100)]
        result = calculate_timestamps(chapters, total_duration=0.0)
        assert result[0].startTime == 0.0

    def test_single_chapter(self):
        chapters = [Chapter(title="Full Episode", word_start=0, word_end=1000)]
        result = calculate_timestamps(chapters, total_duration=600.0, music_intro_offset=10.0)

        assert result[0].startTime == 10.0
        assert result[0].endTime == 600.0

    def test_timestamps_are_rounded(self):
        chapters = [
            Chapter(title="A", word_start=0, word_end=33),
            Chapter(title="B", word_start=33, word_end=66),
            Chapter(title="C", word_start=66, word_end=100),
        ]
        result = calculate_timestamps(chapters, total_duration=100.0)

        for ch in result:
            # All should be rounded to 1 decimal
            assert ch.startTime == round(ch.startTime, 1)
            assert ch.endTime == round(ch.endTime, 1)


# =========================================================================
# 3. TestWriteChaptersJson
# =========================================================================
class TestWriteChaptersJson:
    """Tests for writing Podcasting 2.0 chapter JSON files."""

    def test_writes_valid_json(self, tmp_path):
        chapters = [
            Chapter(title="Introduction", startTime=0.0, endTime=30.5),
            Chapter(title="Top Stories", startTime=30.5, endTime=300.0),
            Chapter(title="Closing", startTime=300.0, endTime=360.0),
        ]
        out = tmp_path / "chapters_ep001.json"
        result = write_chapters_json(chapters, out, episode_title="Ep 1: Test")

        assert result == out
        assert out.exists()

        data = json.loads(out.read_text())
        assert data["version"] == "1.2.0"
        assert data["title"] == "Ep 1: Test"
        assert len(data["chapters"]) == 3
        assert data["chapters"][0]["title"] == "Introduction"
        assert data["chapters"][0]["startTime"] == 0.0
        assert data["chapters"][1]["startTime"] == 30.5
        assert data["chapters"][2]["startTime"] == 300.0

    def test_chapter_has_endtime(self, tmp_path):
        chapters = [
            Chapter(title="A", startTime=0.0, endTime=100.0),
            Chapter(title="B", startTime=100.0, endTime=200.0),
        ]
        out = tmp_path / "chapters.json"
        write_chapters_json(chapters, out)

        data = json.loads(out.read_text())
        assert data["chapters"][0]["endTime"] == 100.0

    def test_no_endtime_when_zero(self, tmp_path):
        chapters = [Chapter(title="Only", startTime=0.0, endTime=0.0)]
        out = tmp_path / "chapters.json"
        write_chapters_json(chapters, out)

        data = json.loads(out.read_text())
        assert "endTime" not in data["chapters"][0]

    def test_empty_chapters_returns_none(self, tmp_path):
        out = tmp_path / "chapters.json"
        result = write_chapters_json([], out)
        assert result is None
        assert not out.exists()

    def test_no_episode_title(self, tmp_path):
        chapters = [Chapter(title="A", startTime=0.0, endTime=10.0)]
        out = tmp_path / "chapters.json"
        write_chapters_json(chapters, out)

        data = json.loads(out.read_text())
        assert "title" not in data

    def test_creates_parent_dirs(self, tmp_path):
        chapters = [Chapter(title="A", startTime=0.0, endTime=10.0)]
        out = tmp_path / "nested" / "deep" / "chapters.json"
        result = write_chapters_json(chapters, out)

        assert result == out
        assert out.exists()


# =========================================================================
# 4. TestEndToEndPipeline
# =========================================================================
class TestEndToEndPipeline:
    """Test the full parse → timestamp → write pipeline."""

    def test_tesla_full_pipeline(self, tmp_path):
        markers = [
            SectionMarker(pattern="Welcome to Tesla Shorts Time", title="Introduction"),
            SectionMarker(pattern="Top \\d+ News", title="Top Stories"),
            SectionMarker(pattern="one thing worth watching", title="The Counterpoint"),
            SectionMarker(pattern="First Principles", title="First Principles"),
            SectionMarker(pattern="Before we go", title="Tomorrow Teaser"),
            SectionMarker(pattern="That's Tesla Shorts Time", title="Closing"),
        ]

        chapters = parse_chapters(TESLA_SCRIPT, markers, show_name="Tesla")
        assert len(chapters) >= 4

        # Simulate a 10-minute episode with 10s music intro
        chapters = calculate_timestamps(chapters, total_duration=600.0, music_intro_offset=10.0)

        # All chapters should have positive timestamps
        for ch in chapters:
            assert ch.startTime >= 0
            assert ch.endTime > ch.startTime or ch.title == "Closing"

        # First chapter starts at or after the music intro
        assert chapters[0].startTime >= 10.0

        # Last chapter ends at total duration
        assert chapters[-1].endTime == 600.0

        # Write JSON
        out = tmp_path / "chapters_ep042.json"
        result = write_chapters_json(chapters, out, episode_title="Ep 42: Battery Breakthrough")
        assert result == out

        data = json.loads(out.read_text())
        assert data["version"] == "1.2.0"
        assert data["title"] == "Ep 42: Battery Breakthrough"
        assert len(data["chapters"]) == len(chapters)

    def test_env_intel_full_pipeline(self, tmp_path):
        markers = [
            SectionMarker(pattern="This is Environmental Intelligence", title="Introduction"),
            SectionMarker(pattern="executive summary|here's what matters", title="Executive Summary"),
            SectionMarker(pattern="lead story|most significant", title="Lead Story"),
            SectionMarker(pattern="regulatory|policy watch", title="Regulatory & Policy Watch"),
            SectionMarker(pattern="science|technical", title="Science & Technical"),
            SectionMarker(pattern="industry|practice", title="Industry & Practice"),
            SectionMarker(pattern="action items", title="Action Items"),
            SectionMarker(pattern="week ahead|mark your calendar", title="Week Ahead"),
            SectionMarker(pattern="Before we wrap", title="Tomorrow Teaser"),
            SectionMarker(pattern="That's Environmental Intelligence", title="Closing"),
        ]

        chapters = parse_chapters(ENV_INTEL_SCRIPT, markers, show_name="Env Intel")
        chapters = calculate_timestamps(chapters, total_duration=480.0, music_intro_offset=10.0)

        out = tmp_path / "chapters_ep015.json"
        write_chapters_json(chapters, out, episode_title="Ep 15: PFAS Update")

        data = json.loads(out.read_text())
        assert len(data["chapters"]) >= 5


# =========================================================================
# 5. TestYAMLConfigIntegration
# =========================================================================
class TestYAMLConfigIntegration:
    """Verify chapter configs load correctly from real show YAML files."""

    @pytest.mark.parametrize("slug", [
        "tesla", "omni_view", "fascinating_frontiers",
        "planetterrian", "env_intel", "models_agents",
        "unintended_consequences",
    ])
    def test_show_has_chapters_config(self, slug):
        cfg = load_config(SHOWS_DIR / f"{slug}.yaml")
        assert cfg.chapters.enabled is True
        assert len(cfg.chapters.section_markers) >= 2

    def test_tesla_markers_parse_script(self):
        cfg = load_config(SHOWS_DIR / "tesla.yaml")
        chapters = parse_chapters(
            TESLA_SCRIPT,
            cfg.chapters.section_markers,
            show_name=cfg.name,
        )
        assert len(chapters) >= 3
        titles = [c.title for c in chapters]
        assert "Introduction" in titles

    def test_env_intel_markers_parse_script(self):
        cfg = load_config(SHOWS_DIR / "env_intel.yaml")
        chapters = parse_chapters(
            ENV_INTEL_SCRIPT,
            cfg.chapters.section_markers,
            show_name=cfg.name,
        )
        assert len(chapters) >= 4


# =========================================================================
# 6. TestPreambleBehavior
# =========================================================================

# Script where the first marker ("First Principles") does NOT start at
# position 0 — the opening content has no matching marker.
PREAMBLE_SCRIPT = """\
Hey everyone, welcome back to the show. Today we have some big news.
TSLA is up 5 percent and here are the stories you need to know about.

Story 1: Tesla Semi gets wireless charging in a new Jay Leno segment.
Story 2: Model Y arrives at Giga Texas with production lines confirmed.
Story 3: FSD investigation update from NHTSA moves to engineering analysis.

Here is our First Principles segment for today.
The idea here is about vertical integration and why it matters for Tesla.
Manufacturing your own batteries changes the entire cost structure.

Before we go, here is what to watch tomorrow.
Keep your eyes on European delivery numbers coming out this week.
That wraps it up for today, thanks for listening.
"""


class TestPreambleBehavior:
    """Tests for preamble handling when content precedes the first marker."""

    MARKERS = [
        {"pattern": "First Principles", "title": "First Principles"},
        {"pattern": "Before we go", "title": "Tomorrow Teaser"},
    ]

    def test_preamble_section_included(self):
        """Content before the first marker is returned as a section."""
        chapters = parse_chapters(PREAMBLE_SCRIPT, self.MARKERS)
        sections = split_script_at_chapters(PREAMBLE_SCRIPT, chapters)

        assert len(sections) >= 3
        assert "welcome back to the show" in sections[0]

    def test_preamble_chapter_inserted(self):
        """A Preamble Chapter object is inserted at index 0."""
        chapters = parse_chapters(PREAMBLE_SCRIPT, self.MARKERS)
        split_script_at_chapters(PREAMBLE_SCRIPT, chapters)

        assert chapters[0].title == "Preamble"
        assert chapters[0].word_start == 0
        assert chapters[0].char_start == 0

    def test_preamble_chapter_word_boundaries(self):
        """Preamble word_end matches the original first chapter's word_start."""
        chapters = parse_chapters(PREAMBLE_SCRIPT, self.MARKERS)
        # The original first chapter ("First Principles") will be at index 1
        # after preamble insertion.
        original_first_word_start = chapters[0].word_start
        split_script_at_chapters(PREAMBLE_SCRIPT, chapters)

        assert chapters[0].title == "Preamble"
        assert chapters[0].word_end == original_first_word_start
        assert chapters[1].title == "First Principles"

    def test_sections_equal_chapters_with_preamble(self):
        """len(sections) == len(chapters) even when preamble is added."""
        chapters = parse_chapters(PREAMBLE_SCRIPT, self.MARKERS)
        sections = split_script_at_chapters(PREAMBLE_SCRIPT, chapters)

        assert len(sections) == len(chapters)

    def test_no_preamble_when_marker_at_start(self):
        """No preamble chapter when the first marker matches at position 0."""
        script = "First Principles: here we go.\nBefore we go, goodbye."
        chapters = parse_chapters(script, self.MARKERS)
        original_len = len(chapters)
        sections = split_script_at_chapters(script, chapters)

        assert len(chapters) == original_len  # No insertion
        assert chapters[0].title == "First Principles"
        assert len(sections) == len(chapters)

    def test_preamble_timestamps_shift_subsequent_chapters(self):
        """calculate_timestamps() accounts for preamble proportion."""
        chapters = parse_chapters(PREAMBLE_SCRIPT, self.MARKERS)
        split_script_at_chapters(PREAMBLE_SCRIPT, chapters)

        calculate_timestamps(chapters, 120.0, music_intro_offset=5.0)

        # Preamble starts right after music intro
        assert chapters[0].title == "Preamble"
        assert chapters[0].startTime == 5.0

        # First Principles must start AFTER preamble, not at 5.0
        assert chapters[1].title == "First Principles"
        assert chapters[1].startTime > 5.0

        # All timestamps should be monotonically increasing
        for i in range(1, len(chapters)):
            assert chapters[i].startTime >= chapters[i - 1].startTime

    def test_preamble_content_coverage(self):
        """All original script words appear across the sections."""
        chapters = parse_chapters(PREAMBLE_SCRIPT, self.MARKERS)
        sections = split_script_at_chapters(PREAMBLE_SCRIPT, chapters)

        original_words = set(PREAMBLE_SCRIPT.split())
        section_words = set()
        for s in sections:
            section_words.update(s.split())
        assert original_words == section_words


# ---------------------------------------------------------------------------
# Auto-segmentation fallback (May 2026 fix — TST chapter quality)
# ---------------------------------------------------------------------------

class TestAutoSegmentFallback:
    """Operator caught a regression where TST episodes ship with only
    ``Introduction`` + ``Closing`` chapters because the per-show regex
    don't tolerate Whisper transcription variations. The auto-segment
    fallback splits the head chapter into roughly-90-second segments
    when the matched chapter count is below the floor."""

    def _long_script(self, paragraphs: int) -> str:
        # Each paragraph has ~50 words → ~18s of speech at 165wpm.
        # Five paragraphs ≈ 90s, the auto-segment target.
        para = (
            "This is a fairly long paragraph that contains roughly fifty "
            "words spread across several sentences. The intent is to give "
            "the auto-segmenter enough material to choose paragraph "
            "breaks at sensible boundaries inside the head chapter, "
            "without exceeding the configured words-per-segment threshold."
        )
        return "Welcome back to the show. " + (
            "\n\n".join([para] * paragraphs)
        ) + "\n\nThanks for listening."

    def test_auto_segment_fires_when_marker_count_below_min(self):
        from engine.chapters import parse_chapters
        # Only the Welcome marker matches — should yield 1 chapter
        # without auto-segmentation. Auto-segment lifts that to >=4.
        markers = [{"pattern": "Welcome", "title": "Introduction"}]
        chapters = parse_chapters(
            self._long_script(paragraphs=20),
            markers,
            show_name="test_show",
            min_chapters=4,
            auto_segment_target_seconds=90.0,
        )
        assert len(chapters) >= 4, (
            f"Auto-segment fallback should produce >=4 chapters, got "
            f"{len(chapters)} — titles: {[c.title for c in chapters]}"
        )
        # First chapter keeps the operator-supplied title; later ones
        # are generic.
        assert chapters[0].title == "Introduction"
        assert chapters[1].title.startswith("Segment ")

    def test_auto_segment_skips_when_enough_chapters_already(self):
        from engine.chapters import parse_chapters
        # Three markers all match — three chapters, above min. No auto
        # segments should be added.
        markers = [
            {"pattern": "Welcome", "title": "Introduction"},
            {"pattern": "fifty", "title": "Body"},
            {"pattern": "Thanks for listening", "title": "Closing"},
        ]
        chapters = parse_chapters(
            "Welcome to the show.\n\nThis paragraph has the word fifty.\n\nThanks for listening to the show.",
            markers,
            show_name="test_show",
            min_chapters=2,
        )
        # Three matched chapters, no auto-segmentation.
        assert len(chapters) == 3
        assert all(not c.title.startswith("Segment ") for c in chapters)

    def test_auto_segment_word_boundaries_remain_consistent(self):
        """Word boundaries on the rebuilt chapter list must still cover
        the entire script — no gaps, no overlaps."""
        from engine.chapters import parse_chapters

        markers = [{"pattern": "Welcome", "title": "Introduction"}]
        chapters = parse_chapters(
            self._long_script(paragraphs=12),
            markers,
            show_name="test_show",
            min_chapters=4,
            auto_segment_target_seconds=60.0,
        )
        for i in range(len(chapters) - 1):
            assert chapters[i].word_end == chapters[i + 1].word_start, (
                f"Gap or overlap between chapter {i} ({chapters[i].title}) "
                f"and {i+1} ({chapters[i+1].title})"
            )
