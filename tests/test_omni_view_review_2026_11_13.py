"""Omni View review (Nov 13 2026) — drift guards.

The daily audit scored Omni View 5.7/10, the lowest daily show, and flagged
it Repetitive on 12 of its last 14 episodes. Its sibling Top World, from the
same day's news, scored 8. Three causes were measured and fixed:

* the digest prompt steered the show OFF the day's biggest stories ("change
  course" when a sibling told a story) and the feed list let market ticks,
  gadget news and Reddit links crowd the world's newsrooms out of the 150
  newest articles the prompt sees;
* both prompts asked for framing sentences on stories the articles gave no
  framing for ("the coverage presents...", "authorities will monitor..."),
  and the podcast prompt still carried a worked example and a 1,700-word
  "must" — script fact-free share median 53% against Top World's 19%;
* a 1,500-word digest floor fired the expansion retry on every episode and
  padded it (now 1,000; the depth targets are ceilings).

Review: docs/reviews/omni_view_review_2026_11_13.md.
"""

from __future__ import annotations

from pathlib import Path

import yaml

from engine.config import load_config

ROOT = Path(__file__).resolve().parent.parent
PROMPTS = ROOT / "shows" / "prompts"
DIGEST = (PROMPTS / "omni_view_digest.txt").read_text(encoding="utf-8")
PODCAST = (PROMPTS / "omni_view_podcast.txt").read_text(encoding="utf-8")


def _cfg():
    return load_config(ROOT / "shows" / "omni_view.yaml")


class TestStorySelection:
    def test_sibling_coverage_never_steers_the_show_away(self):
        assert "change course" not in DIGEST
        assert "never a reason to skip it" in DIGEST

    def test_the_digest_reads_full_text(self):
        assert "titles + short descriptions" not in DIGEST
        assert "full text where it is printed" in DIGEST

    def test_selection_shares_the_network_rules(self):
        assert "<<include: _shared/interesting_first.txt>>" in DIGEST
        assert "<<include: _shared/hook_supported.txt>>" in DIGEST

    def test_non_stories_are_named(self):
        assert "NOT A STORY" in DIGEST
        assert "analysis or opinion piece" in DIGEST

    def test_progress_watch_is_a_result_never_an_announcement(self):
        block = DIGEST.split("PROGRESS WATCH (instruction", 1)[1].split("STORY DEPTH", 1)[0]
        for word in ("appointment", "proposal", "announcement of intent",
                     "never a story told elsewhere in this digest"):
            assert word in block


class TestNoFramingFiller:
    def test_digest_bans_coverage_sentences_and_invented_next_steps(self):
        assert "SENTENCES THAT ARE NEVER WRITTEN" in DIGEST
        assert '"will monitor"' in DIGEST
        assert "a sentence about the coverage instead of the event" in DIGEST

    def test_digest_no_longer_demands_two_outlets_per_story(self):
        assert "two or more with genuinely different vantage points" not in DIGEST

    def test_depth_targets_are_ceilings(self):
        assert "CEILINGS" in DIGEST
        assert "fewer than four concrete facts" in DIGEST

    def test_deep_dive_may_explain_any_story_and_never_retells_it(self):
        dd = DIGEST.split("## Understanding the Issue", 1)[1]
        assert "ONE of today's stories" in dd
        assert "never re-tells the story it explains" in dd

    def test_podcast_bans_coverage_sentences_and_invented_next_steps(self):
        assert "NEVER A SENTENCE ABOUT THE COVERAGE" in PODCAST
        assert "NEVER AN INVENTED NEXT STEP" in PODCAST
        assert "cite AT LEAST two named outlets" not in PODCAST


class TestNoSeedsNoLengthPressure:
    def test_worked_example_is_gone(self):
        # Sep 5 2026: every worked example sentence leaves the podcast prompts.
        # Omni View's survived and had already bled verbatim (Ep145).
        assert "EXAMPLE OF IDEAL STORY COVERAGE" not in PODCAST
        assert "Host: The European Union has officially" not in PODCAST
        assert "SHAPE OF IDEAL STORY COVERAGE" in PODCAST

    def test_no_podcast_side_length_lever(self):
        # Network do_not_retry: podcast-side length levers.
        for gone in ("must be at least 1,700 words", "DEEPEN the slate",
                     "1,700 to 2,000 spoken words", "280-330 words"):
            assert gone not in PODCAST

    def test_no_quotable_cross_promo_lines(self):
        assert "Models & Agents covers the AI side daily." not in PODCAST
        assert "For deeper Tesla coverage" not in PODCAST

    def test_chapter_anchors_survive(self):
        assert '"to really understand"' in PODCAST
        assert "progress worth knowing" in PODCAST


class TestConfig:
    def test_the_show_runs_grok_47_like_its_siblings(self):
        # Nov 13 2026, round 2: the operator moved Omni View onto the
        # grok-4.7 arm (both stages, low effort, one combined call). The fact
        # floor stays a staged network decision (test_digest_fact_floor).
        cfg = _cfg()
        assert cfg.llm.model == "grok-4.7"
        assert cfg.llm.reasoning_effort == "low"
        assert cfg.llm.stream is True
        assert not cfg.llm.podcast_model
        assert not cfg.llm.min_digest_facts

    def test_word_floor_no_longer_pads_every_day(self):
        cfg = _cfg()
        assert cfg.llm.digest_expand_below_target is True
        assert cfg.llm.min_digest_words == 1000
        assert cfg.llm.min_podcast_words == 1400  # the skip floor's base never moves

    def test_full_text_matches_top_world(self):
        cfg = _cfg()
        assert cfg.fetch_full_text == 24
        assert cfg.fetch_full_text_chars == 4000

    def test_sources(self):
        cfg = _cfg()
        labels = {s.label for s in cfg.sources}
        for kept in ("Fox News", "Newsmax", "Reason", "Mother Jones",
                     "The Intercept", "RealClearPolitics"):
            assert kept in labels, f"{kept}: the spectrum outlets are the show's perspectives"
        for added in ("The New York Times World", "The Globe and Mail World", "CBC World"):
            assert added in labels
        urls = " ".join(s.url for s in cfg.sources)
        for gone in ("reddit.com", "wired.com", "arstechnica.com", "bloomberg.com/markets"):
            assert gone not in urls
        for dom in ("nytimes.com", "theglobeandmail.com", "cbc.ca"):
            assert dom in cfg.preferred_domains

    def test_live_blogs_and_obituaries_are_excluded(self):
        from engine.utils import drop_excluded_titles  # noqa: PLC0415

        raw = yaml.safe_load((ROOT / "shows" / "omni_view.yaml").read_text(encoding="utf-8"))
        pats = raw["exclude_title_patterns"]
        arts = [{"title": t, "url": "https://example.com/x"} for t in (
            "Ukraine war live updates: talks resume",
            "Week in pictures: the world",
            "Obituary: a former minister",
            "Spain holds first general strike in 14 years",
        )]
        kept, dropped = drop_excluded_titles(arts, pats)
        assert dropped == 3
        assert kept[0]["title"].startswith("Spain")


def test_also_today_is_one_item_per_story():
    assert "ONE ITEM PER STORY in Also Today" in DIGEST


class TestRoundTwoFromEp235:
    """Ep235 (Nov 13), the first episode on the new prompts: the filler was
    gone, the expansion retry did not fire and the script's fact-free share
    fell to 35.7% (median 53% before). What remained: the deep dive re-told
    item 5 from the same article, one official supplied both sides of a
    "contested" story, unnamed "analysts" and what-it-means lines survived,
    and the script's deep dive blurred its subjects into passive fragments."""

    def test_the_deep_dive_gate_fires_on_this_show(self):
        lints = _cfg().digest_lints
        assert "deep_dive_distinct" in lints
        assert "deep_dive_distinct_measure" in lints

    def test_ep235_deep_dive_would_have_been_regenerated(self):
        from engine.digest_lint import run_digest_lints  # noqa: PLC0415

        digest = (ROOT / "digests" / "omni_view" / "Omni_View_Ep235_20261113.md").read_text(encoding="utf-8")
        findings, metrics = run_digest_lints(digest, _cfg().digest_lints)
        assert [f.lint for f in findings if f.note] == ["deep_dive_distinct"]
        assert metrics["deep_dive_contains_body_item"] >= 0.5

    def test_two_sides_need_two_holders(self):
        assert "two DIFFERENT named holders" in DIGEST
        assert "two different named holders" in PODCAST

    def test_uncredited_claims_are_never_written(self):
        assert "a claim credited to nobody" in DIGEST
        assert "mark, signal or mean" in DIGEST

    def test_an_analysis_headline_does_not_hide_a_result(self):
        assert "The rule judges the EVENT, not the headline" in DIGEST

    def test_the_spoken_deep_dive_never_blurs_its_subjects(self):
        assert "Every sentence names its own subject" in PODCAST

    def test_go_deeper_is_a_fact_never_a_coverage_sentence(self):
        assert "Only if the briefing has a \"Go deeper\" line" in PODCAST
        assert "what actually differs in how each frames" not in PODCAST
        assert "frames it as" not in PODCAST
