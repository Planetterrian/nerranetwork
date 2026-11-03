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


class TestDubViewersLandOnTheirLanguage:
    """``engine.funnel.destination_for`` sent every @NerraRU / @NerraFR Short
    of a show with no per-channel destination to the ENGLISH show page
    (Fascinating Frontiers and Modern Investing on both channels; Tesla and
    SpaceX on French). The language's front page is the fallback; a
    language the site does not publish in keeps the show page."""

    @pytest.fixture(scope="class")
    def load(self):
        from engine.config import load_config
        return lambda slug: load_config(ROOT / "shows" / f"{slug}.yaml")

    @pytest.mark.parametrize("slug", ["fascinating_frontiers", "modern_investing"])
    def test_ru_and_fr_dubs_point_at_the_language_hub(self, load, slug):
        from engine import funnel
        cfg = load(slug)
        assert funnel.destination_for(cfg, channel="ru") == "https://nerranetwork.com/ru/index.html"
        assert funnel.destination_for(cfg, channel="fr") == "https://nerranetwork.com/fr/index.html"

    def test_a_configured_destination_still_wins(self, load):
        from engine import funnel
        assert funnel.destination_for(load("spacex"), channel="ru") == \
            "https://nerranetwork.com/ru/spacex.html"
        assert funnel.destination_for(load("spacex"), channel="fr") == \
            "https://nerranetwork.com/fr/index.html"

    def test_english_and_unpublished_languages_are_unchanged(self, load):
        from engine import funnel
        cfg = load("fascinating_frontiers")
        assert funnel.destination_for(cfg, channel="en") == cfg.publishing.rss_link
        assert funnel.destination_for(cfg, channel="zh") == cfg.publishing.rss_link

    def test_the_hubs_the_fallback_names_are_generated(self):
        from engine import funnel
        for lang in funnel._hub_languages():
            assert (ROOT / lang / "index.html").exists(), f"{lang}/index.html is linked but not generated"
