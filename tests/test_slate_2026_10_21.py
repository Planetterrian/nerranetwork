"""Oct 21 2026 slate review guards."""
from pathlib import Path

from engine.digest_lint import also_today_items, story_item_count

ROOT = Path(__file__).resolve().parents[1]


class TestAlsoTodayCountsEveryShape:
    """The Oct 19 counter wanted a bold title alone on its line and read 0
    beside Planetterrian's, Omni View's and Models & Agents' runs."""

    def test_inline_heads_count(self):
        digest = (
            "### Top News\n1. **A story: Outlet**\nBody. Source: https://a.example/1\n\n"
            "### Also Today\n"
            "**Lagoon needs repairs: Phys.org** One sentence. Source: https://b.example/2\n\n"
            "**Madry returns — Sam Altman:** One sentence. https://c.example/3\n\n"
            "**Storm warning:** The BBC reports wind. Source: [bbc.co.uk](https://d.example/4)\n"
        )
        assert also_today_items(digest) == 3

    def test_title_alone_still_counts(self):
        digest = "### Also Today\n**Title alone: Outlet**\nOne sentence. Source: https://a.example/1\n"
        assert also_today_items(digest) == 1

    def test_no_section_is_zero(self):
        assert also_today_items("### Top News\n1. **A: B**\nBody.\n") == 0


class TestStoryItemCount:
    def test_heading_items_and_inline_items(self):
        digest = (
            "## Major world stories (2)\n"
            "### 2) Australian MP attacked\nBody. Source: https://a.example/1\n"
            "### 3) Nigeria confirms Ebola\nBody. Source: https://a.example/2\n"
            "## Also Today\n**Storm warning:** Body. Source: https://a.example/3\n"
        )
        assert story_item_count(digest) == 3

    def test_a_field_line_without_a_url_is_not_a_story(self):
        digest = "### Practice Investment of the Day\n**Ticker:** XYZ\n\n**Entry:** 12.50\n"
        assert story_item_count(digest) == 0


class TestRecordedOnEveryShow:
    def test_metrics_sit_outside_the_opt_in_absence_filter(self):
        src = (ROOT / "run_show.py").read_text(encoding="utf-8")
        start = src.index('metrics.record("digest_also_today_items"')
        block = src[src.rindex("\n        try:", 0, start):start]
        # Eight-space indent: the run-level try, not the opt-in branch's.
        assert "from engine.digest_lint import also_today_items" in block
        opt_in = src.index('if getattr(config, "absence_sentence_filter", False):')
        assert opt_in < start
        assert src.index("except Exception as _abs_exc", opt_in) < start
