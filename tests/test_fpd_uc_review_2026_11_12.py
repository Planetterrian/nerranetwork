"""First Principles Daily and Unintended Consequences review (Nov 12 2026).

Review: docs/reviews/first_principles_unintended_consequences_review_2026_11_12.md.
The guards pin what the pass changed: the tool's name, the kind of topic the
First Principles queue holds, the restock's story-level dedup, the length
chain and the missing map sentence on the narrative shows.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

import restock_topic_queues as restock  # noqa: E402

PROMPTS = ROOT / "shows" / "prompts"
FPD_PROMPTS = sorted(PROMPTS.glob("first_principles_*.txt"))
UC_PROMPTS = sorted(PROMPTS.glob("unintended_consequences_*.txt"))


def _queue(slug: str) -> list[dict]:
    return yaml.safe_load(
        (ROOT / "shows" / "topic_queues" / f"{slug}.yaml").read_text())["queue"]


def _show(slug: str) -> dict:
    return yaml.safe_load((ROOT / "shows" / f"{slug}.yaml").read_text())


class TestTheToolsName:
    def test_no_first_principles_prompt_says_the_old_name(self):
        assert FPD_PROMPTS
        for path in FPD_PROMPTS:
            assert "idiot" not in path.read_text().lower(), path.name

    def test_show_yaml_and_intros_use_the_new_name(self):
        text = (ROOT / "shows" / "first_principles.yaml").read_text()
        assert "idiot" not in text.lower()
        assert "First Principles Ratio" in text
        assert "idiot" not in (ROOT / "engine" / "intros.py").read_text().lower()

    def test_system_prompt_defines_it_as_a_measurement(self):
        text = (PROMPTS / "first_principles_system.txt").read_text()
        assert "First Principles Ratio" in text
        assert "a measurement, never a verdict" in text

    def test_unproduced_topics_use_the_new_name(self):
        for entry in _queue("first_principles"):
            if not entry.get("produced"):
                blob = (entry["title"] + " " + entry["brief"]).lower()
                assert "idiot" not in blob, entry["id"]

    def test_ratio_line_is_not_swallowed_by_the_first_principle_marker(self):
        text = (ROOT / "shows" / "first_principles.yaml").read_text()
        assert "first principle(?!s ratio)" in text


class TestFirstPrinciplesTopics:
    #: A price set by where a thing is sold, or a fee for borrowing it.
    VENUE = re.compile(
        r"\b(stadium|airport|hotel|theme park|cinema|movie theat|mini ?bar|"
        r"coat check|rental|locker|vending|concession|valet)\b", re.I)

    def test_no_pending_opportunity_is_a_venue_or_rental_price(self):
        for entry in _queue("first_principles"):
            if entry.get("produced") or entry.get("category") != "opportunity_area":
                continue
            assert not self.VENUE.search(entry["title"]), entry["title"]

    #: The modern concrete examples written by hand on Nov 12. Each stays in
    #: the queue (pending, then produced); the restock keeps the arm modern.
    MODERN = re.compile(
        r"lidar|diamond|crispr|starlink|gigacast|cubesat|raspberry|"
        r"wind turbine|shale|tsmc|southwest|aravind|m-pesa|rehydration", re.I)

    def test_concrete_arm_reaches_the_present(self):
        concrete = [e for e in _queue("first_principles")
                    if e.get("category") == "concrete_example"]
        assert len([e for e in concrete if self.MODERN.search(e["title"])]) >= 12

    def test_restock_prompt_aims_at_things_designed_and_made(self):
        text = (PROMPTS / "first_principles_restock.txt").read_text()
        assert "DESIGNED AND MADE" in text
        assert "NEVER an opportunity area" in text
        assert "personally paid the markup" not in text
        assert "after 1980" in text


class TestStoryLevelDedup:
    def _keys(self, *entries):
        return [restock.story_keys(e) for e in entries]

    def test_a_retelling_under_a_new_title_is_rejected(self):
        told = {"title": "The Nile Perch in Lake Victoria", "brief": ""}
        assert restock.story_too_similar(
            "The Fish That Emptied Lake Victoria", self._keys(told))

    def test_names_in_the_brief_count(self):
        told = {"title": "The Cleaner Coolant",
                "brief": "After the ozone treaty the Montreal Protocol moved "
                         "makers to a new family of gases."}
        assert restock.story_too_similar(
            "The Montreal Protocol and the Gas That Replaced It", self._keys(told))

    def test_a_different_story_passes(self):
        told = {"title": "The Nile Perch in Lake Victoria", "brief": ""}
        assert not restock.story_too_similar(
            "The Aswan Dam and the Vanishing Sardines", self._keys(told))

    def test_generic_words_alone_never_match(self):
        told = {"title": "The Tax Reform Act and the Market Surge", "brief": ""}
        assert not restock.story_too_similar(
            "The Subsidy Program and the Price Boom", self._keys(told))

    def test_validate_and_dedupe_uses_it(self):
        cfg = restock.RESTOCK_CONFIGS["unintended_consequences"]
        queue = [{"id": "nile", "title": "The Nile Perch in Lake Victoria",
                  "brief": "x" * 90, "category": "classic", "produced": True}]
        cand = [{"title": "The Fish That Emptied Lake Victoria",
                 "brief": "y" * 90, "category": "classic"}]
        assert restock.validate_and_dedupe(cand, queue, cfg, 1) == []

    def test_both_restock_prompts_say_a_new_angle_is_a_repeat(self):
        assert "A new angle on a subject already listed is a repeat" in \
            (PROMPTS / "first_principles_restock.txt").read_text()
        assert "is a repeat" in \
            (PROMPTS / "unintended_consequences_restock.txt").read_text()


class TestLengthFollowsTheBrief:
    @pytest.mark.parametrize("slug,target,floor", [
        ("first_principles", 1200, 840),
        ("unintended_consequences", 1100, 780),
    ])
    def test_targets_and_pinned_skip_floors(self, slug, target, floor):
        llm = _show(slug)["llm"]
        assert llm["min_podcast_words"] == target
        assert llm["min_podcast_publish_words"] == floor
        assert llm["min_digest_words"] == 900
        assert not llm.get("podcast_expand_below_target", False)

    @pytest.mark.parametrize("name", [
        "first_principles_podcast.txt", "unintended_consequences_podcast.txt"])
    def test_script_prompt_takes_its_length_from_the_brief(self, name):
        text = (PROMPTS / name).read_text()
        assert "the brief sets the length" in text.lower()
        for stale in ("2200", "2,200", "2800", "2,400", "15–18 minute"):
            assert stale not in text, stale

    def test_brief_prompts_carry_no_stale_word_target(self):
        for name in ("first_principles_episode.txt",
                     "unintended_consequences_episode.txt"):
            text = (PROMPTS / name).read_text()
            for stale in ("1500–2200", "2200–2800", "15–18 minute"):
                assert stale not in text, (name, stale)

    def test_cross_promo_is_described_never_quoted(self):
        text = (PROMPTS / "first_principles_podcast.txt").read_text()
        block = text[text.index("CROSS-PROMO"):]
        assert "check out" not in block and "Write the sentence fresh" in block

    def test_no_quoted_tone_specimen_in_the_uc_script_prompt(self):
        text = (PROMPTS / "unintended_consequences_podcast.txt").read_text()
        assert "EXAMPLE OF IDEAL NARRATIVE TONE" not in text


class TestNumbersAndPeople:
    def test_first_principles_brief_builds_the_floor_from_sources(self):
        text = (PROMPTS / "first_principles_episode.txt").read_text()
        assert "THE NUMBERS" in text

    def test_uc_prompts_ask_for_the_people(self):
        brief = (PROMPTS / "unintended_consequences_episode.txt").read_text()
        script = (PROMPTS / "unintended_consequences_podcast.txt").read_text()
        assert "the people the sources name" in brief
        assert "PEOPLE STAY IN" in script

    def test_research_search_asks_for_people_and_prices_in_one_call(self):
        src = (ROOT / "engine" / "fetcher.py").read_text()
        body = src[src.index("def fetch_topic_research_articles"):]
        nxt = body.find("\ndef ", 10)
        body = body if nxt == -1 else body[:nxt]
        assert "NAMES the" in body and "prices and quantities" in body
        assert body.count("grok_generate_text(") == 1


class TestNoMapOnANarrativeShow:
    def test_narrative_open_has_no_map(self):
        from engine.intros import build_cold_open_spec
        spec = build_cold_open_spec("unintended_consequences", narrative=True)
        assert "NO MAP on this show" in spec
        assert "THE MAP" not in spec

    def test_news_open_keeps_its_map(self):
        from engine.intros import build_cold_open_spec
        assert "THE MAP" in build_cold_open_spec("tesla", narrative=False)
