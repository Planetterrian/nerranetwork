"""Drift guards for P2-1 (Apple provenance) and P2-4 (chapters on the site).

P2-1: two Apple sources now exist — the official token-authenticated
Reporter feed and the fragile cookie scrape — and they will disagree.
The dashboard ranks Reporter first, keeps the scrape as a *labelled*
fallback, and carries `provenance` + `fetched_at` for both so the card
can say which one it is showing.

Absence handling is the load-bearing part. Apple suppresses metrics it
will not disclose and a show with no listening has no row at all, so
"not measured" must never render as 0 — this repo has fixed that same
bug in three separate places already.

P2-4: chapters have been generated, committed and shipped in the podcast
feeds for months while the website surfaced them nowhere.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import generate_dashboard as gd  # noqa: E402
from engine.blog import _format_timestamp, _load_chapters  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parent.parent


# ---------------------------------------------------------------------------
# P2-1 — Apple source provenance
# ---------------------------------------------------------------------------

REPORTER = {
    "source": "apple_reporter",
    "fetched_at": "2026-07-28T06:00:00Z",
    "first_date": "2026-07-24", "last_date": "2026-07-27", "days_retained": 4,
    "shows_reported": ["1234"],
    "shows": {"1234": {"slug": "tesla", "show_name": "Tesla Shorts Time",
                       "plays": 200, "listeners": 80,
                       "engaged_listeners": 55, "listening_hours": 31.5,
                       "days_reported": 4}},
}

SCRAPE = {
    "fetched_at": "2026-07-28T05:00:00Z", "window_days": 30,
    "shows": {"tesla": {"plays": 120, "listeners": 40,
                        "followers": None, "time_listened": 900}},
}


def _root(tmp_path, *, reporter=None, scrape=None) -> Path:
    (tmp_path / "api").mkdir(parents=True, exist_ok=True)
    if reporter is not None:
        (tmp_path / "api" / "apple_reporter.json").write_text(
            json.dumps(reporter), encoding="utf-8")
    if scrape is not None:
        (tmp_path / "api" / "apple_stats.json").write_text(
            json.dumps(scrape), encoding="utf-8")
    return tmp_path


class TestAbsencePreservingTotals:
    """The repo's signature bug: absence rendered as zero."""

    def test_no_shows_gives_none_not_zero(self):
        assert gd._absent_preserving_totals({}, ("plays",)) == {"plays": None}

    def test_all_missing_gives_none(self):
        totals = gd._absent_preserving_totals({"a": {"plays": None}}, ("plays",))
        assert totals["plays"] is None

    def test_genuine_zero_is_preserved_as_zero(self):
        """A real measured 0 must stay 0 — the distinction cuts both ways."""
        totals = gd._absent_preserving_totals({"a": {"plays": 0}}, ("plays",))
        assert totals["plays"] == 0

    def test_partial_reporting_sums_only_what_exists(self):
        totals = gd._absent_preserving_totals(
            {"a": {"plays": 5}, "b": {"plays": None}}, ("plays",))
        assert totals["plays"] == 5


class TestAppleSourceRanking:
    def test_reporter_wins_when_it_has_data(self, tmp_path):
        apple = gd.build_audience_section(
            _root(tmp_path, reporter=REPORTER, scrape=SCRAPE))["apple"]
        assert apple["primary_source"] == "reporter"
        assert "official" in apple["provenance"].lower()
        assert apple["totals"]["plays"] == 200  # Reporter's number, not 120

    def test_scrape_is_the_labelled_fallback(self, tmp_path):
        """Today's real state: Reporter has produced no file yet."""
        apple = gd.build_audience_section(_root(tmp_path, scrape=SCRAPE))["apple"]
        assert apple["primary_source"] == "connect_scrape"
        assert "fallback" in apple["provenance"].lower()
        assert apple["totals"]["plays"] == 120

    def test_empty_reporter_file_does_not_displace_the_scrape(self, tmp_path):
        """A file that exists but holds no show is not a source of truth."""
        empty = {**REPORTER, "shows": {}, "shows_reported": []}
        apple = gd.build_audience_section(
            _root(tmp_path, reporter=empty, scrape=SCRAPE))["apple"]
        assert apple["primary_source"] == "connect_scrape"

    def test_both_sources_are_retained_for_comparison(self, tmp_path):
        apple = gd.build_audience_section(
            _root(tmp_path, reporter=REPORTER, scrape=SCRAPE))["apple"]
        assert set(apple["sources"]) == {"reporter", "connect_scrape"}
        for src in apple["sources"].values():
            assert src["provenance"]
            assert src["fetched_at"]

    def test_scrape_absence_survives_into_totals(self, tmp_path):
        apple = gd.build_audience_section(_root(tmp_path, scrape=SCRAPE))["apple"]
        # Apple disclosed no follower count — that is not zero followers.
        assert apple["totals"]["followers"] is None

    def test_no_apple_data_at_all_is_unconfigured(self, tmp_path):
        apple = gd.build_audience_section(_root(tmp_path))["apple"]
        assert apple["configured"] is False

    def test_corrupt_reporter_file_falls_back_cleanly(self, tmp_path):
        root = _root(tmp_path, scrape=SCRAPE)
        (root / "api" / "apple_reporter.json").write_text("{oops", encoding="utf-8")
        apple = gd.build_audience_section(root)["apple"]
        assert apple["primary_source"] == "connect_scrape"
        assert apple["sources"]["reporter"]["error"]


class TestDashboardRendersAbsenceAsDash:
    def test_management_html_has_an_absence_preserving_formatter(self):
        html = (REPO_ROOT / "management.html").read_text(encoding="utf-8")
        assert "fmtOrDash" in html
        # And the Apple card must use it, not the zero-coercing `fmt`.
        apple_card = html.split('sectionCard("Apple Podcasts"')[1][:4000]
        assert "fmtOrDash(t.plays)" in apple_card
        assert "fmt(t.plays)" not in apple_card

    def test_apple_card_shows_provenance(self):
        html = (REPO_ROOT / "management.html").read_text(encoding="utf-8")
        apple_card = html.split('sectionCard("Apple Podcasts"')[1][:4000]
        assert "ap.provenance" in apple_card


# ---------------------------------------------------------------------------
# P2-4 — chapters on the episode page
# ---------------------------------------------------------------------------

class TestTimestampFormatting:
    @pytest.mark.parametrize(
        "seconds,expected",
        [(0, "0:00"), (20.0, "0:20"), (210.9, "3:31"), (527.1, "8:47"),
         (3600, "1:00:00"), (3725, "1:02:05")],
    )
    def test_format(self, seconds, expected):
        assert _format_timestamp(seconds) == expected


class TestChapterLoading:
    def _write(self, tmp_path, payload):
        md = tmp_path / "Show_Ep047_20260728.md"
        md.write_text("# Show", encoding="utf-8")
        (tmp_path / "chapters_ep047.json").write_text(
            json.dumps(payload), encoding="utf-8")
        return md

    def test_loads_and_formats(self, tmp_path):
        md = self._write(tmp_path, {"version": "1.2.0", "chapters": [
            {"startTime": 20.0, "title": "Introduction", "endTime": 210.9},
            {"startTime": 210.9, "title": "The Counterpoint", "endTime": 272.0},
        ]})
        chapters = _load_chapters(md, 47)
        assert [c["title"] for c in chapters] == ["Introduction", "The Counterpoint"]
        assert [c["time"] for c in chapters] == ["0:20", "3:31"]
        assert chapters[0]["seconds"] == 20.0

    def test_sorted_by_start_time(self, tmp_path):
        md = self._write(tmp_path, {"chapters": [
            {"startTime": 300.0, "title": "Later"},
            {"startTime": 10.0, "title": "Earlier"},
        ]})
        assert [c["title"] for c in _load_chapters(md, 47)] == ["Earlier", "Later"]

    def test_entries_without_title_or_time_are_dropped(self, tmp_path):
        md = self._write(tmp_path, {"chapters": [
            {"startTime": 10.0, "title": "Good"},
            {"startTime": 20.0, "title": "   "},
            {"title": "No time"},
            {"startTime": "abc", "title": "Bad time"},
        ]})
        assert [c["title"] for c in _load_chapters(md, 47)] == ["Good"]

    def test_missing_file_returns_empty(self, tmp_path):
        md = tmp_path / "Show_Ep099_20260728.md"
        md.write_text("# Show", encoding="utf-8")
        assert _load_chapters(md, 99) == []

    def test_corrupt_file_never_raises(self, tmp_path):
        md = tmp_path / "Show_Ep047_20260728.md"
        md.write_text("# Show", encoding="utf-8")
        (tmp_path / "chapters_ep047.json").write_text("{broken", encoding="utf-8")
        assert _load_chapters(md, 47) == []

    def test_no_path_or_episode_returns_empty(self):
        assert _load_chapters(None, 47) == []
        assert _load_chapters("x.md", 0) == []

    def test_real_committed_chapter_file_parses(self):
        """Guards the on-disk schema, not just a fixture of it."""
        md = REPO_ROOT / "digests" / "spacex" / "SpaceX_Daily_Ep047_20260728.md"
        if not md.exists():
            pytest.skip("fixture episode no longer present")
        chapters = _load_chapters(md, 47)
        assert len(chapters) >= 3
        assert all(c["title"] and c["time"] for c in chapters)


class TestChapterTemplate:
    def test_section_and_styles_exist(self):
        tpl = (REPO_ROOT / "templates" / "blog_post.html.j2").read_text(encoding="utf-8")
        assert '<section class="blog-chapters" id="chapters">' in tpl
        assert "{% if chapters %}" in tpl
        assert ".blog-chapter-list" in tpl

    def test_seeking_is_progressive_enhancement(self):
        """No inline player on English-only episodes — the list must still work."""
        tpl = (REPO_ROOT / "templates" / "blog_post.html.j2").read_text(encoding="utf-8")
        script = tpl.split('id="chapters"')[1][:2500]
        assert 'getElementById("nn-i18n-audio")' in script
        assert "if (!audio) return;" in script
        # Only claim clickability once a player is actually attached.
        assert "is-seekable" in script

    def test_blog_passes_chapters_to_the_template(self):
        source = (REPO_ROOT / "engine" / "blog.py").read_text(encoding="utf-8")
        assert '"chapters": chapters,' in source
        assert "_load_chapters(" in source
