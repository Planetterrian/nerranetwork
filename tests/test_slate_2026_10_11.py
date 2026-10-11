"""Oct 11 2026 slate review — guards for the fixes it shipped.

Review: docs/reviews/slate_review_2026_10_11.md. Each class pins one finding
from the committed episodes of 2026-10-11, so a revert names the episode it
would bring back.
"""

from __future__ import annotations

import re
from pathlib import Path
from types import SimpleNamespace

import sys

import yaml

from engine.config import load_config

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "pipelines" / "voices"))


def _read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


# --- Narrative research floor (UC Ep139) ----------------------------------

class TestNarrativeResearchFloor:
    """UC Ep139 was written from a queue brief alone (0 research sources) and
    aired a fabricated case: Argentina licensing toothfish off South Georgia,
    a British territory."""

    def test_both_narrative_shows_require_two_sources(self):
        for slug in ("unintended_consequences", "first_principles"):
            cfg = load_config(ROOT / "shows" / f"{slug}.yaml")
            assert cfg.narrative_research >= cfg.narrative_research_min == 2, slug

    def test_floor_defaults_off(self):
        assert load_config(ROOT / "shows" / "tesla.yaml").narrative_research_min == 0

    def test_picker_can_move_past_a_tried_topic(self, tmp_path):
        from engine.topic_queue import pick_next_topic

        q = tmp_path / "q.yaml"
        q.write_text(yaml.safe_dump({"queue": [
            {"id": "a", "title": "A", "brief": "Brief A.", "produced": False},
            {"id": "b", "title": "B", "brief": "Brief B.", "produced": False},
        ]}), encoding="utf-8")
        assert pick_next_topic(q)["id"] == "a"
        assert pick_next_topic(q, exclude_ids={"a"})["id"] == "b"
        assert pick_next_topic(q, exclude_ids={"a", "b"}) is None

    def test_run_show_skips_rather_than_writing_from_the_brief(self):
        src = _read("run_show.py")
        assert "narrative_research_min" in src
        assert '"narrative_research_thin",' in src
        # A thin topic is annotated so the picker defers it after two days,
        # but only when the search returned something (an outage returns []).
        assert "record_gate_block(" in src
        assert "if _found:\n                        try:\n                            record_gate_block(" in src
        assert "exclude_ids=" in src

    def test_the_correction_is_filed(self):
        from engine.corrections import load_corrections

        entries = load_corrections(ROOT / "digests" / "unintended_consequences")
        ep139 = [e for e in entries if e["episode"] == 139]
        assert ep139 and ep139[0]["where"] == "both"
        assert "South Georgia" in ep139[0]["text"]


# --- Sources ----------------------------------------------------------------

class TestNoChatbotSources:
    def test_no_show_reads_the_grok_account(self):
        # SpaceX Ep126's deep dive was seeded by @grok replies to users.
        for path in sorted((ROOT / "shows").glob("*.yaml")):
            data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
            handles = {str(a.get("handle", "")).lower()
                       for a in (data.get("x_accounts") or []) if isinstance(a, dict)}
            assert "grok" not in handles, path.name


# --- The Age of AI ------------------------------------------------------------

class TestAgeOfAiPublish:
    def test_feed_title_fits_and_keeps_the_guest(self):
        from engine.titles import PODCAST_EPISODE_TITLE_MAX
        from publish_episode import interview_episode_title

        thesis = ("A digital-marketing agency CEO weighs whether generative tools "
                  "for copy, targeting and optimization are eroding or sharpening "
                  "demand for specialized human oversight in equity-crowdfunding "
                  "campaigns.")
        title = interview_episode_title(11, "Jason Fishman", thesis)
        assert len(title) <= PODCAST_EPISODE_TITLE_MAX
        assert title.startswith("Ep11: Jason Fishman — A digital-marketing")
        assert not title.endswith(("—", " ", "-"))
        assert interview_episode_title(3, "Ann", "Short thesis.") == "Ep3: Ann — Short thesis."

    def test_the_summary_line_is_never_a_heading(self):
        from publish_episode import notes_lede

        notes = "**Episode Summary**\n\nJason Fishman said AI helps with ideation."
        assert notes_lede(notes) == "Jason Fishman said AI helps with ideation."
        assert notes_lede("## Summary\nOne real sentence here.") == "One real sentence here."
        assert notes_lede("") == ""

    def test_ep011_page_no_longer_prints_the_heading(self):
        text = _read("digests/age_of_ai/Age_of_AI_Ep011_20261010.md")
        assert "**What You Need to Know:** **Episode Summary**" not in text


# --- Multilingual workflow ----------------------------------------------------

class TestMultilingualConcurrency:
    def _wf(self):
        return yaml.safe_load(_read(".github/workflows/multilingual.yml"))

    def test_no_workflow_level_group(self):
        # A workflow-level group keeps one pending run and cancelled the rest.
        assert "concurrency" not in self._wf()

    def test_translate_serializes_per_show(self):
        conc = self._wf()["jobs"]["translate"]["concurrency"]
        assert conc["group"] == "multilingual-${{ matrix.show }}"
        assert conc["cancel-in-progress"] is False

    def test_a_skipped_show_is_not_swept(self):
        src = _read(".github/workflows/multilingual.yml")
        assert "_skipped_today" in src
        assert '.skip_{stamp}.json' in src


# --- Nerra Daily fallback -------------------------------------------------------

class TestNerraDailyFallback:
    def _seg(self, hook, content="", name="Omni View"):
        return SimpleNamespace(hook=hook, episode_title=f"Ep 1: {hook}",
                               content=content, show_name=name)

    def test_clipped_hook_is_restored_from_the_digest(self):
        from engine.daily_edition import spoken_hook

        full = ("Panama declares a state of emergency after two major earthquakes "
                "damage buildings across every province.")
        seg = self._seg("Panama declares a state of emergency after two major "
                        "earthquakes damage…", content=f"# Omni View\n\n> **{full}**\n")
        assert spoken_hook(seg) == full

    def test_without_the_digest_the_fragment_is_dropped(self):
        from engine.daily_edition import spoken_hook

        out = spoken_hook(self._seg("Rates held, and the bank signalled two more…"))
        assert out == "Rates held."
        assert "…" not in out

    def test_fallback_speaks_no_ellipsis(self):
        import datetime as dt

        from engine.daily_edition import fallback_links

        spec = SimpleNamespace(name="Nerra Daily", host="Mira")
        segs = [self._seg("First story is about rockets landing on…"),
                self._seg("Second story, with a clause that runs…", name="Tesla")]
        links = fallback_links(spec, segs, dt.date(2026, 10, 11))
        assert "…" not in links["intro"] + "".join(links["handoffs"])

    def test_a_refused_reply_names_its_reason(self):
        from engine.daily_edition import links_reply_problem

        assert links_reply_problem("", 3) == "empty reply"
        assert "truncated" in links_reply_problem('{"intro": "x"', 3)
        assert links_reply_problem('{"intro": "a", "signoff": "b", "handoffs": ["c"]}', 3) \
            == "1 handoffs for 3 segments"
        assert links_reply_problem('{"signoff": "b", "handoffs": []}', 0) == "missing intro"

    def test_the_links_call_gets_a_second_attempt(self):
        src = _read("scripts/build_daily_edition.py")
        assert "for attempt in (1, 2):" in src
        assert "links_reply_problem" in src


# --- Visuals --------------------------------------------------------------------

class TestVisuals:
    def test_a_decimal_title_keeps_its_number(self):
        from engine.youtube_titles import _clean_title

        assert _clean_title("7.7 Quake Hits Panama") == "7.7 Quake Hits Panama"
        assert _clean_title("1. Quake Hits Panama") == "Quake Hits Panama"
        assert _clean_title("2) Quake Hits Panama") == "Quake Hits Panama"

    def test_story_briefs_are_topped_up_not_padded(self):
        from engine.grok_imagine import MIN_STORY_SET, build_image_prompts

        queries = [f"static query {i}" for i in range(12)]
        two_briefs = build_image_prompts(
            hook="Dragon cargo launch", image_queries=queries, count=15,
            scene_briefs=["A Dragon capsule on a pad at dawn under clouds",
                          "Engineers watching telemetry screens in a control room"])
        assert len(two_briefs) == MIN_STORY_SET
        no_briefs = build_image_prompts(hook="x", image_queries=queries, count=8)
        assert len(no_briefs) == 8

    def test_duplicate_briefs_collapse(self):
        from engine.scene_briefs import dedupe_briefs

        out = dedupe_briefs([
            "Collapsed concrete apartment blocks in Panama City after the quake",
            "Collapsed concrete apartment blocks in Panama City after the earthquake",
            "Rescue workers in orange vests at a hospital entrance at night",
        ])
        assert len(out) == 2

    def test_essay_sections_supply_scene_contexts(self):
        from engine.scene_briefs import essay_section_leads

        digest = (
            "## Top News\n\n1. **Item:** body\n\n"
            "### Engineering Deep Dive\n\n"
            "The core difference in development speed lies in testing philosophy "
            "and contract structure. More text.\n\n"
            "### Closing\n\nThanks for listening to the show today, see you.\n"
        )
        assert essay_section_leads(digest) == [
            "The core difference in development speed lies in testing philosophy "
            "and contract structure."]
        assert "essay_section_leads(" in _read("run_show.py")

    def test_dub_thumbnails_use_a_scene_not_the_cover(self):
        for rel in ("engine/ru_dub.py", "engine/lang_dub.py"):
            src = _read(rel)
            assert "thumb_base = _thumb_scenes[0] if _thumb_scenes else cover" in src, rel

    def test_a_short_without_a_hook_takes_the_episode_title(self):
        src = _read("run_show.py")
        assert re.search(r"if not _opt_short_title and not \(this_hook or \"\"\)\.strip\(\):", src)


# --- Prompts and structure (⚠️ A/B-listen) ---------------------------------------

class TestPromptFixes:
    def test_twins_say_twelve_not_fifteen(self):
        for show in ("fascinating_frontiers", "planetterrian"):
            for kind in ("digest", "podcast"):
                text = _read(f"shows/prompts/{show}_{kind}.txt")
                assert "Top 15" not in text and "12-14 stories" not in text, (show, kind)

    def test_the_twins_headers_still_match_their_patterns(self):
        from engine.validation import SHOW_VALIDATION_CONFIGS

        for show, header in (("fascinating_frontiers", "### Top 12 Space & Astronomy Stories"),
                             ("planetterrian", "### Top 12 Science & Health Discoveries")):
            assert header in _read(f"shows/prompts/{show}_digest.txt")
            cfg = SHOW_VALIDATION_CONFIGS[show]()
            assert any(re.search(r.pattern, header + "\n\n1. **x**\nbody\n", re.S | re.I)
                       for r in cfg.sections), show

    def test_tesla_x_takeover_is_up_to_five(self):
        assert "Tesla X Takeover section included with up to 5" in _read(
            "shows/prompts/tesla_digest.txt")

    def test_mit_market_mechanics_has_no_fill_in_opener(self):
        text = _read("shows/prompts/modern_investing_digest.txt")
        assert "Imagine you bought [ETF/stock]" not in text

    def test_spacex_deep_dive_numbers_have_provenance(self):
        pod = _read("shows/prompts/spacex_podcast.txt")
        assert "never an estimate stated as a reported fact" in pod
        assert "an X post replying to a user is never that source" in _read(
            "shows/prompts/spacex_digest.txt")

    def test_both_sides_runs_only_on_a_named_disagreement(self):
        from engine.validation import omni_desk_validation_config, omni_world_validation_config

        for rel in ("shows/prompts/_shared/omni_desk_digest_body.txt",
                    "shows/prompts/omni_view_world_digest.txt"):
            text = _read(rel)
            assert "the fact both sides accept" not in text, rel
            assert "otherwise omit this section, header included" in text, rel
        for cfg in (omni_desk_validation_config(), omni_world_validation_config(saturday=False)):
            rule = [r for r in cfg.sections if r.name == "Both Sides"][0]
            assert rule.optional is True

    def test_sunday_segment_supplies_no_stock_phrase(self):
        src = _read("engine/weekly_recap.py")
        assert "looking back over the past week" not in src
        assert "may have missed" not in src

    def test_teasers_never_restate_the_calendar(self):
        assert "never an item the horizon just read" in _read("shows/prompts/ai_chips_podcast.txt")
        assert "never an item the calendar just read" in _read("shows/prompts/mag7_podcast.txt")

    def test_mit_pick_chapter_skips_the_disclaimer(self):
        data = yaml.safe_load(_read("shows/modern_investing.yaml"))

        def patterns(o):
            if isinstance(o, dict):
                for v in o.values():
                    yield from patterns(v)
            elif isinstance(o, list):
                for v in o:
                    if isinstance(v, dict) and "pattern" in v and "title" in v:
                        yield v
                    else:
                        yield from patterns(v)

        pat = [p["pattern"] for p in patterns(data)
               if p["title"] == "Practice Investment of the Day"][0]
        disclaimer = "The Practice Investment of the Day uses simulated trades with no real money."
        assert not re.search(pat, disclaimer, re.I)
        assert re.search(pat, "This is a simulated trade for educational purposes only.", re.I)
        assert re.search(pat, "Now for the practice investment.", re.I)


class TestAgeOfAiVideo:
    def test_publisher_renders_when_the_edit_path_left_no_video(self):
        src = _read("pipelines/voices/publish_episode.py")
        assert "def render_episode_video(" in src
        assert "render_locally = True" in src
        assert "from audio.waveform_video import render as render_waveform" in src

    def test_publish_job_has_room_for_the_render(self):
        wf = yaml.safe_load(_read(".github/workflows/nerra_voices_publish.yml"))
        assert wf["jobs"]["publish"]["timeout-minutes"] >= 90
