"""Guards from the six-month network review (Nov 3 2026).

Each class pins one rule the review found broken on main. See
``docs/reviews/network_review_2026_11_03.md`` for the evidence.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def _tracked(*patterns: str) -> list[str]:
    out = subprocess.run(["git", "ls-files", "--", *patterns], cwd=ROOT,
                         capture_output=True, text=True, check=True).stdout
    return [line for line in out.splitlines() if line.strip()]


class TestNoEpisodeAudioIsTracked:
    """Landmine #1, third recurrence: the hook Short's spliced FLAC source
    (``engine/short_furniture.py``, Oct 30) was written into
    ``digests/<dir>/youtube_tmp/`` and the video job's ``git add -A digests/``
    committed thirteen of them (571 MB) in three days."""

    def test_no_audio_or_video_file_under_digests_is_tracked(self):
        media = _tracked("digests/**/*.flac", "digests/*.flac", "digests/**/*.wav",
                         "digests/**/*.mp3", "digests/**/*.mp4", "digests/**/*.m4a",
                         "digests/**/*.ogg", "digests/**/*.aac")
        assert media == [], f"episode media is tracked at HEAD: {media[:5]}"

    def test_the_short_source_intermediates_are_ignored(self):
        ignore = (ROOT / ".gitignore").read_text(encoding="utf-8")
        assert "digests/*/youtube_tmp/*_short_source.flac" in ignore
        assert "digests/*/youtube_tmp/*_short_source.json" in ignore
        assert "digests/**/*.flac" in ignore

    def test_the_word_json_beside_the_flac_is_not_tracked_either(self):
        assert _tracked("digests/*/youtube_tmp/*_short_source.json") == []


class TestMonthAbbreviationsNeedADate:
    """``replace_dates`` expanded every bare ``Mar``/``Jan`` token: Nerra
    Daily aired "March-a-Lago" and "January Ferrigan" (a hyphen and a
    space are both word boundaries). A month abbreviation is a month only
    when a day or a year follows it."""

    @pytest.mark.parametrize("text", ["Mar-a-Lago", "Jan Ferrigan", "Oct-Dec quarter",
                                      "in Mar", "Dec Jones said", "Aug Wilson"])
    def test_names_and_ranges_are_untouched(self, text):
        from assets.pronunciation import replace_dates
        assert replace_dates(text) == text

    @pytest.mark.parametrize("text, spoken", [
        ("Feb 15, 2026", "February fifteenth"),
        ("Jan. 5, 2026", "January fifth"),
        ("Sept 9, 2026", "September ninth"),
        ("the Mar 3 hearing", "March 3"),
        ("Dec 2025", "December 2025"),
    ])
    def test_dates_still_expand(self, text, spoken):
        from assets.pronunciation import replace_dates
        assert spoken in replace_dates(text)
