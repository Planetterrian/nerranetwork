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


class TestClockTimes:
    """AI Chips Ep030 aired "four fifty-three A M in the afternoon"."""

    def test_day_part_after_a_bare_time_adds_no_half_of_day(self):
        from assets.pronunciation import replace_times
        assert replace_times("at 4:53 in the afternoon") == "at four fifty-three in the afternoon"
        assert replace_times("at 11:15 tonight") == "at eleven fifteen tonight"
        assert replace_times("at 2:37 local time") == "at two thirty-seven local time"

    def test_a_bare_single_digit_hour_is_said_plainly(self):
        from assets.pronunciation import replace_times
        out = replace_times("the call came at 4:53 yesterday")
        assert "A M" not in out and "P M" not in out
        assert "four fifty-three" in out

    def test_stated_and_24_hour_times_keep_their_half(self):
        from assets.pronunciation import replace_times
        assert "P M" in replace_times("at 4:53 p.m.")
        assert "two thirty P M UTC" in replace_times("launched at 14:30:00 UTC today")
        assert "nine thirty A M" in replace_times("at 09:30 the market")
        assert "next" in replace_times("at 10:30 next week")


class TestChapters:
    def test_first_chapter_starts_at_zero(self, tmp_path):
        import json
        from engine.chapters import Chapter, write_chapters_json
        chs = [Chapter(title="Introduction", startTime=17.6, endTime=28.1),
               Chapter(title="Lead", startTime=28.1, endTime=60.0)]
        out = write_chapters_json(chs, tmp_path / "c.json")
        data = json.loads(out.read_text())["chapters"]
        assert data[0]["startTime"] == 0.0 and data[1]["startTime"] == 28.1

    def test_a_bold_wrapped_title_is_never_an_item_title(self):
        from engine.chapters import _digest_item_titles
        digest = "**# Models & Agents**\n\n### Top Story\n1. **LoWAgent ships a low-resource agent**\nBody.\n"
        titles = _digest_item_titles(digest)
        assert not any(t.startswith("#") for t in titles)

    def test_no_chapter_starts_on_the_map_sentence(self):
        from engine.chapters import parse_chapters
        script = (
            "Magnetar fields grew three hundred times in a millisecond.\n\n"
            "This is Fascinating Frontiers, episode two hundred twenty-nine.\n\n"
            "A deep dive on magnetar fields follows, then Galileo's navigation module.\n\n"
            "Japan's Fugaku supercomputer modelled two merging neutron stars and their magnetar fields "
            + "in detail across the merger. " * 12 + "\n\n"
            "The European Space Agency tested a reprogrammable Galileo navigation module "
            + "in orbit for the second generation. " * 12 + "\n"
        )
        digest = ("> **Magnetar fields grew three hundred times in a millisecond.**\n\n"
                  "### Space Stories\n1. **Magnetar forms when two neutron stars touch: Phys.org**\n"
                  "Body. Source: https://a.example/1\n\n"
                  "2. **Galileo Second Generation gains reprogrammable navigation module: ESA**\n"
                  "Body. Source: https://a.example/2\n")
        chs = parse_chapters(script, [], show_name="FF",
                             story_headlines=["Magnetar forms when two neutron stars touch",
                                              "Galileo Second Generation gains reprogrammable navigation module"],
                             digest_text=digest)
        map_at = script.index("A deep dive")
        lead_at = script.index("Japan's Fugaku")
        for c in chs[1:]:
            assert not (script.index("This is") <= c.char_start < lead_at), c.title
        assert map_at < lead_at


class TestClusterRetryNeverDropsTheStory:
    HEADS = [["Tesla and SpaceX take first step towards merger, would dilute all shar",
              "Elon Musk's Full Comments on Potential Tesla-SpaceX Merger"]]

    def test_a_retry_that_lost_the_story_is_flagged(self):
        from engine.story_clusters import dropped_clusters
        digest = "### Top 12 News Items\n1. **Porsche 911 owner reviews Model Y: Teslarati**\nBody.\n"
        assert dropped_clusters(digest, self.HEADS) == self.HEADS

    def test_a_merged_item_keeps_the_story(self):
        from engine.story_clusters import dropped_clusters
        digest = ("### Top 12 News Items\n1. **Tesla and SpaceX boards form committees to study "
                  "a merger: Reuters**\nBody. Source: https://x.example/1\n")
        assert dropped_clusters(digest, self.HEADS) == []

    def test_run_show_rejects_the_retry_when_a_story_is_dropped(self):
        src = (ROOT / "run_show.py").read_text(encoding="utf-8")
        fn = src[src.index("def _cluster_retry_worse"):]
        fn = fn[:fn.index("\n\n# ")]
        assert "dropped_clusters" in fn and "or bool(dropped)" in fn


class TestSharedLinkIsNotADuplicateStory:
    """MAG 7 Ep029 dropped the Joel Kaplan item from Also Today for sharing a
    source page with the Tesla-SpaceX merger item; the script still told it."""

    def test_short_differently_titled_item_survives_a_shared_url(self):
        from engine.digest_overlap import dedupe_cross_section_items
        url = "https://www.theinformation.com/briefings/today"
        digest = (
            "### Company Desk\n"
            "**Tesla and SpaceX boards are examining a combination: Financial Times**\n"
            "The Financial Times reported that the boards of SpaceX and Tesla are exploring a "
            "potential merger, and The Information said each company formed a special committee "
            f"of independent directors. Source: {url}\n\n"
            "### Also Today\n"
            "**Meta's policy chief is leaving: The Information**\n"
            f"Joel Kaplan plans to leave Meta. Source: {url}\n"
        )
        result = dedupe_cross_section_items(digest, show_name="MAG 7 Daily")
        assert result.count == 0
        assert "Kaplan" in result.text


class TestMapSentence:
    def test_narrative_shows_get_their_own_map(self):
        from engine.intros import build_cold_open_spec
        news = build_cold_open_spec("tesla")
        narrative = build_cold_open_spec("first_principles", narrative=True)
        assert "never more than three" in news and "no length or duration word" in news
        assert "segment or section label" in narrative
        assert "two or three stories" not in narrative

    def test_pipeline_passes_the_narrative_flag(self):
        src = (ROOT / "engine" / "pipeline.py").read_text(encoding="utf-8")
        assert 'narrative=bool(getattr(config, "narrative_mode", False))' in src


class TestRecordStartPhrase:
    def test_index_line_names_the_portfolio_opening(self):
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "mit_hook", ROOT / "shows" / "hooks" / "modern_investing.py")
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        phrase = mod._record_start_phrase({"metadata": {"inception_date": "2026-03-16"}})
        assert phrase == "since the practice portfolio opened on March 16, 2026"
        assert "record began" not in phrase


class TestPromptRules:
    def test_rules_shipped(self):
        p = ROOT / "shows" / "prompts"
        cd = (p / "_shared" / "content_discipline.txt").read_text(encoding="utf-8")
        assert "named once for the run" in cd
        assert "never wedged into a sentence after its subject" in cd
        assert "it is spoken only once per intervention" not in cd  # wording owned by Longevity
        lon = (p / "longevity_system.txt").read_text(encoding="utf-8")
        assert "Say it once per intervention" in lon
        uc = (p / "unintended_consequences_episode.txt").read_text(encoding="utf-8")
        assert "vivid, specific detail or anecdote" not in uc
        assert "same unit and period the source gives it" in uc
        assert "there is no Counterpoint" in (p / "tesla_podcast.txt").read_text(encoding="utf-8")
        assert "an Also Today item included" in (p / "omni_view_podcast.txt").read_text(encoding="utf-8")


class TestCorrectionsFiled:
    def test_six_corrections_load(self):
        from engine.corrections import corrections_for
        for show_dir, ep in [("unintended_consequences", 149), ("first_principles", 137),
                             ("spacex", 137), ("modern_investing", 207), ("ai_chips", 30),
                             ("fascinating_frontiers", 229)]:
            assert corrections_for(ROOT / "digests" / show_dir, ep), (show_dir, ep)


class TestMapDetection:
    """A pre-map script's lead line must never be read as the map, or its
    lead chapter would be pushed a line late (FF Ep225 'El Gordo…')."""

    def _first_after_identity(self, path):
        import re
        lines = [ln.strip() for ln in path.read_text(encoding="utf-8").splitlines() if ln.strip()]
        for i, ln in enumerate(lines[:8]):
            if re.match(r"(?i)^\W*this is .{2,60}episode", ln) and i + 1 < len(lines):
                return lines[i + 1]
        return None

    def test_pre_map_lead_lines_are_not_maps(self):
        from engine.chapters import _looks_like_map
        files = sorted((ROOT / "digests").glob("*/*_2026101[0-9]_tts.txt"))
        seen = [ln for ln in (self._first_after_identity(f) for f in files) if ln]
        if len(seen) < 50:
            return  # a checkout without the October scripts has nothing to judge
        misread = [ln for ln in seen if _looks_like_map(ln)]
        assert len(misread) <= max(1, len(seen) // 50), misread[:5]

    def test_oct_21_maps_are_maps(self):
        from engine.chapters import _looks_like_map
        files = sorted((ROOT / "digests").glob("*/*_20261021_tts.txt"))
        seen = [ln for ln in (self._first_after_identity(f) for f in files) if ln]
        if not seen:
            return
        assert sum(_looks_like_map(ln) for ln in seen) >= len(seen) - 1
