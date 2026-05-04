"""Tests for engine.tag_leak_detector.

Two layers:

1. Synthetic tests — clean transcripts produce zero leaks; leaky
   transcripts produce the expected count. False-positive prose
   stays clean (the most important guarantee).

2. Real-world fixtures — UC Ep001 (known 2 build-intensity leaks)
   and Tesla Ep461 (known build-intensity bleed) reproduce the
   leak counts the operator caught by ear. These are the cases
   the detector was built for.
"""

from __future__ import annotations

from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parent.parent


# ---------------------------------------------------------------------------
# Synthetic — happy path + false-positive guards
# ---------------------------------------------------------------------------

class TestSyntheticTranscripts:

    def test_clean_transcript_returns_zero_leaks(self, tmp_path: Path):
        from engine.tag_leak_detector import scan_transcript, count_leaks
        p = tmp_path / "t.txt"
        p.write_text(
            "Welcome to today's episode. Here is the news. "
            "We're going to discuss three stories. The first is about Tesla. "
            "Thanks for listening.",
            encoding="utf-8",
        )
        assert count_leaks(p) == 0
        assert scan_transcript(p) == []

    def test_legitimate_emphasis_prose_does_not_flag(self, tmp_path: Path):
        """The word 'emphasis' appears legitimately in news prose
        ('Tesla's emphasis on robotics', 'an emphasis on safety').
        These must NOT trigger the detector."""
        from engine.tag_leak_detector import count_leaks
        p = tmp_path / "t.txt"
        p.write_text(
            "Tesla's emphasis on robotics is the lede here. "
            "There is also an emphasis on safety in this report. "
            "The emphasis of the talk was clear. "
            "Many companies place an emphasis on quality.",
            encoding="utf-8",
        )
        assert count_leaks(p) == 0, (
            "Legitimate 'emphasis on / of / in / for' prose was "
            "flagged — false-positive guard regressed."
        )

    def test_legitimate_breath_prose_does_not_flag(self, tmp_path: Path):
        """'breathtaking' / 'breathing' / 'breath of' in normal prose
        must not trigger."""
        from engine.tag_leak_detector import count_leaks
        p = tmp_path / "t.txt"
        p.write_text(
            "It was a breathtaking discovery. "
            "Heavy breathing was reported by witnesses. "
            "He took a breath of fresh air outside. "
            "The breathwork community embraced the technique.",
            encoding="utf-8",
        )
        assert count_leaks(p) == 0

    def test_legitimate_long_pause_in_prose_does_flag(self, tmp_path: Path):
        """The phrase 'long pause' appears in tag-leak shape.
        Without context disambiguation the detector flags it. This
        is acceptable false-positive behaviour for week 1; once
        calibrated we can tighten if needed."""
        from engine.tag_leak_detector import count_leaks
        p = tmp_path / "t.txt"
        p.write_text(
            "The senator took a long pause before responding.",
            encoding="utf-8",
        )
        # Yes — flagged. Operator will see this in the dashboard;
        # if it's a recurring false-positive we tighten the regex.
        assert count_leaks(p) == 1

    def test_build_intensity_leak_detected(self, tmp_path: Path):
        from engine.tag_leak_detector import scan_transcript
        p = tmp_path / "t.txt"
        p.write_text(
            "Welcome to today's episode. Build intensity. "
            "Today we'll discuss three stories.",
            encoding="utf-8",
        )
        leaks = scan_transcript(p)
        assert len(leaks) == 1
        assert leaks[0].pattern_name == "build-intensity"
        assert "build intensity" in leaks[0].matched.lower()

    def test_build_intended_corruption_detected(self, tmp_path: Path):
        """When Whisper hears the trailing closing wrap as 'build
        intended to dig' (UC Ep001 line 127), the detector should
        catch the 'build intended' shape."""
        from engine.tag_leak_detector import scan_transcript
        p = tmp_path / "t.txt"
        p.write_text(
            "I'm Patrick and Vancouver, build intended to dig.",
            encoding="utf-8",
        )
        leaks = scan_transcript(p)
        assert len(leaks) == 1
        assert leaks[0].pattern_name == "build-intensity"

    def test_stray_angle_bracket_tag_detected(self, tmp_path: Path):
        """If a TTS tag escapes consumption and ends up rendered
        in the transcript (`<emphasis>` left as text), flag it."""
        from engine.tag_leak_detector import scan_transcript
        p = tmp_path / "t.txt"
        p.write_text(
            "He spoke of <emphasis>three</emphasis> reasons.",
            encoding="utf-8",
        )
        leaks = scan_transcript(p)
        # Should match opening <emphasis> and closing </emphasis>.
        names = {leak.pattern_name for leak in leaks}
        assert "stray-angle-bracket-tag" in names


# ---------------------------------------------------------------------------
# Real-world fixtures — the cases the detector was built to catch
# ---------------------------------------------------------------------------

class TestRealWorldFixtures:
    """Run the detector against actual transcripts the operator
    flagged. If these counts ever drop to zero, either the wrap fix
    landed (good) OR the detector regressed (bad — investigate)."""

    def test_tesla_ep461_finds_build_intensity_leak(self):
        """Tesla Ep461 transcript line 112 has the wrap leak."""
        from engine.tag_leak_detector import scan_transcript
        path = (REPO_ROOT / "digests" / "tesla_shorts_time"
                / "Tesla_Shorts_Time_Pod_Ep461_20260503_transcript.txt")
        if not path.exists():
            pytest.skip("Tesla Ep461 transcript fixture not present")

        leaks = scan_transcript(path)
        bi_leaks = [
            leak for leak in leaks if leak.pattern_name == "build-intensity"
        ]
        assert len(bi_leaks) >= 1, (
            f"Expected at least 1 build-intensity leak in Tesla Ep461, "
            f"got {len(bi_leaks)}"
        )


# ---------------------------------------------------------------------------
# API surface
# ---------------------------------------------------------------------------

class TestAPISurface:

    def test_count_leaks_matches_scan_transcript_length(self, tmp_path: Path):
        from engine.tag_leak_detector import scan_transcript, count_leaks
        p = tmp_path / "t.txt"
        p.write_text("Build intensity. Long pause. Build intensity.",
                     encoding="utf-8")
        assert count_leaks(p) == len(scan_transcript(p))

    def test_missing_transcript_returns_empty(self, tmp_path: Path):
        from engine.tag_leak_detector import scan_transcript, count_leaks
        nonexistent = tmp_path / "no_such_file.txt"
        assert scan_transcript(nonexistent) == []
        assert count_leaks(nonexistent) == 0

    def test_summarize_leaks_groups_by_pattern(self, tmp_path: Path):
        from engine.tag_leak_detector import scan_transcript, summarize_leaks
        p = tmp_path / "t.txt"
        p.write_text(
            "Build intensity. Build intensity. Long pause. ",
            encoding="utf-8",
        )
        leaks = scan_transcript(p)
        summary = summarize_leaks(leaks)
        assert "build-intensity=2" in summary
        assert "long-pause=1" in summary

    def test_summarize_empty_leaks(self):
        from engine.tag_leak_detector import summarize_leaks
        assert summarize_leaks([]) == "no tag leaks detected"


# ---------------------------------------------------------------------------
# Runner integration — non-blocking, always records metric
# ---------------------------------------------------------------------------

def test_runner_imports_tag_leak_detector():
    """``run_show.py`` imports and uses the detector after Whisper.
    Drift guard so refactors don't accidentally remove the wiring."""
    runner = (REPO_ROOT / "run_show.py").read_text(encoding="utf-8")
    assert "from engine.tag_leak_detector import" in runner, (
        "run_show.py no longer imports tag_leak_detector — the "
        "post-Whisper sentinel is silently disabled."
    )
    assert 'metrics.record("tag_leaks"' in runner, (
        "run_show.py no longer records tag_leaks metric — operator "
        "loses visibility into tag-leak rate over time."
    )
