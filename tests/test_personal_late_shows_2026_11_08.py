"""Nov 8 2026 — a member who carries a late show hears it.

The Nerra Personal build wakes when Nerra Daily publishes (7:00 ET);
Vancouver Daily News publishes at 08:15 ET and is choosable only here. The
builder skipped any member already built for the date, so every member who
carried Vancouver got an edition without it, every day since Oct 17. Both
paying members carry it.

Now each edition row records the shows it carried, and a later sweep re-makes
the day once (same GUID, the existing replace path) when a lineup show has
published since.
"""
from __future__ import annotations

from pathlib import Path

from engine.personal_edition import LATE_FILLS_PER_DAY, late_shows

ROOT = Path(__file__).resolve().parents[1]
BUILDER = (ROOT / "scripts" / "build_personal_feeds.py").read_text(encoding="utf-8")

LINEUP = ["tesla", "spacex", "vancouver"]


class TestLateShows:
    def test_a_show_that_published_after_the_build_is_late(self):
        row = {"shows": ["tesla", "spacex"], "late_fills": 0}
        assert late_shows(row, LINEUP, ["tesla", "spacex", "vancouver"]) == ["vancouver"]

    def test_nothing_new_means_no_remake(self):
        row = {"shows": ["tesla", "spacex"]}
        assert late_shows(row, LINEUP, ["tesla", "spacex"]) == []

    def test_a_row_from_before_the_field_is_never_remade(self):
        assert late_shows({"date": "2026-11-08"}, LINEUP, LINEUP) == []
        assert late_shows(None, LINEUP, LINEUP) == []

    def test_one_late_fill_a_day(self):
        row = {"shows": ["tesla"], "late_fills": LATE_FILLS_PER_DAY}
        assert late_shows(row, LINEUP, LINEUP) == []

    def test_a_show_outside_the_lineup_never_triggers(self):
        row = {"shows": ["tesla", "spacex"]}
        assert late_shows(row, LINEUP, ["tesla", "spacex", "mag7"]) == []

    def test_lineup_order_is_kept(self):
        row = {"shows": ["tesla"]}
        assert late_shows(row, LINEUP, ["vancouver", "spacex", "tesla"]) == [
            "spacex", "vancouver"]


class TestTheBuilderWiring:
    def test_the_row_records_what_it_carried(self):
        assert '"shows": [seg.slug for seg in segments]' in BUILDER
        assert '"late_fills": late_fills' in BUILDER

    def test_an_already_built_member_is_checked_for_late_shows(self):
        head = BUILDER.split('logger.info("%s…: already built today"', 1)[0]
        assert "late_shows(previous[0]" in head
