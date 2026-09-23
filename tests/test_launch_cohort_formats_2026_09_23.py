"""Launch-cohort pass, PR B (2026-09-23): formats, openings and fixed-clock
segments on the 13 new shows. Pins the shapes the plan's Part 3 and Part 4
table named so a later edit cannot quietly undo one of them.
"""

from __future__ import annotations

import datetime as _dt
import re
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
PROMPTS = ROOT / "shows" / "prompts"
DESKS = ("omni_view_europe", "omni_view_asia_pacific", "omni_view_africa_mideast",
         "omni_view_latam", "omni_view_north_america")
COHORT = DESKS + ("omni_view_world", "ai_chips", "mag7", "peptides", "longevity",
                  "prediction_markets", "vancouver", "collingwood")


def _yaml(slug):
    return yaml.safe_load((ROOT / "shows" / f"{slug}.yaml").read_text(encoding="utf-8"))


def _prompt(name):
    return (PROMPTS / name).read_text(encoding="utf-8")


class TestHookShapeEverywhere:
    def test_every_cohort_digest_prompt_includes_hook_shape(self):
        shared = _prompt("_shared/omni_desk_digest_body.txt")
        assert "<<include: hook_shape.txt>>" in shared
        for slug in ("omni_view_world", "ai_chips", "mag7", "peptides", "longevity",
                     "prediction_markets", "vancouver", "collingwood"):
            assert "<<include: _shared/hook_shape.txt>>" in _prompt(f"{slug}_digest.txt"), slug


class TestDeskFormatV2:
    def test_shared_body_has_lead_two_developed_and_also_today(self):
        body = _prompt("_shared/omni_desk_digest_body.txt")
        assert "### Lead\n**1 item**" in body
        assert "### Across the Region\n**2 items**, developed" in body
        assert "### Also Today\n**2 to 4 items, one sentence each**" in body
        assert "omitted when fewer than two" in body
        # Consequence-first opening when the actor is outside the region.
        assert "opens on the consequence INSIDE the region" in body
        # WYNTK-1 = the hook's story.
        assert "Its FIRST sentence is the hook's story" in body

    def test_notes_say_story_count_follows_supply(self):
        assert "STORY COUNT FOLLOWS SUPPLY" in _prompt("_shared/omni_desk_digest_notes.txt")

    def test_podcast_body_speaks_also_today_only_when_present(self):
        pod = _prompt("_shared/omni_desk_podcast_body.txt")
        assert '[Also Today] Only when the briefing has the section' in pod
        assert '"also today" once' in pod

    def test_validator_floor_is_two_and_stops_at_also_today(self):
        from engine.validation import omni_desk_validation_config
        cfg = omni_desk_validation_config()
        rule = next(r for r in cfg.sections if r.name == "Across the Region")
        assert rule.min_items == 2
        assert "Also Today" in rule.pattern

    def test_every_desk_has_an_also_today_chapter(self):
        for slug in DESKS:
            markers = _yaml(slug)["chapters"]["section_markers"]
            titles = [m["title"] for m in markers]
            assert titles.index("Also Today") == titles.index("Across the Region") + 1, slug
            m = next(m for m in markers if m["title"] == "Also Today")
            assert m["where"] == "body" and m["pattern"] == "also today"

    def test_desk_items_reads_also_today(self):
        from engine.omni_desks import DESK_ITEM_SECTIONS, desk_items
        assert "Also Today" in DESK_ITEM_SECTIONS
        md = ("### Lead\n**Big story: Reuters**\nBody.\nSource: https://reuters.com/a\n\n"
              "### Also Today\n**Small story: AP**\nOne sentence.\nSource: https://apnews.com/b\n")
        secs = [i["section"] for i in desk_items(md)]
        assert secs == ["Lead", "Also Today"]

    def test_desks_and_ai_chips_fetch_sixteen_full_texts(self):
        for slug in DESKS + ("ai_chips",):
            assert _yaml(slug)["fetch_full_text"] == 16, slug


class TestNorthAmericaFloorAndRotation:
    def test_region_prompt_has_the_floor_and_rotation_rule(self):
        txt = _prompt("omni_desks/north_america.txt")
        assert "FLOOR:" in txt and "Canadian story" in txt
        assert "Both Sides rotates off the US federal government" in txt

    def test_rotation_note_names_recent_questions_and_the_federal_run(self):
        from engine.omni_desks import both_sides_rotation_note, desk
        na = desk("omni_view_north_america")
        recent = [
            "### Both Sides: Should Ottawa cap immigration?\nx",
            "### Both Sides: Should Congress pass the shutdown bill?\nx",
            "### Both Sides: Should the White House impose the tariff?\nx",
        ]
        note = both_sides_rotation_note(recent, na)
        assert "Should Ottawa cap immigration?" in note
        assert "The last two questions were US-federal." in note
        # Another desk never gets the federal sentence.
        eu = desk("omni_view_europe")
        assert "US-federal" not in both_sides_rotation_note(recent, eu)
        assert both_sides_rotation_note([], na) == ""

    def test_desk_hook_joins_balance_and_rotation(self):
        src = (ROOT / "shows" / "hooks" / "_omni_desk.py").read_text(encoding="utf-8")
        assert "both_sides_rotation_note(recent, d)" in src


class TestTopWorld:
    def test_intake_line_is_data_side(self):
        from shows.hooks.omni_view_world import intake_line
        assert "all 5" in intake_line(5, 5)
        assert "3 of the 5" in intake_line(3, 5)
        assert "no regional desk" in intake_line(0, 5).lower()

    def test_edition_note_switches_on_saturday(self):
        from shows.hooks.omni_view_world import edition_note
        assert "Saturday" in edition_note(_dt.date(2026, 9, 26))  # a Saturday
        assert "weekday edition" in edition_note(_dt.date(2026, 9, 25))

    def test_payload_carries_metrics_and_intake(self, tmp_path):
        from shows.hooks import omni_view_world as h
        out = h.build_payload(tmp_path, _dt.date(2026, 9, 25))
        assert out["metrics"] == {"desks_live_at_publish": 0, "desks_total": 5}
        assert "intake line" in out["hook_context"]

    def test_digest_prompt_has_rubric_line_intake_and_saturday(self):
        d = _prompt("omni_view_world_digest.txt")
        assert "`Ranks: `" in d
        assert "Items six to ten: ONE sentence each" in d
        assert "the intake line supplied in TODAY'S REGIONAL DESKS" in d
        assert "On a Saturday, the edition is different" in d
        p = _prompt("omni_view_world_podcast.txt")
        assert "The ranking lines are for readers — never spoken" in p
        assert "On a Saturday the briefing carries one story" in p

    def test_validator_saturday_is_one_long_story(self):
        from engine.validation import omni_world_validation_config
        sat = omni_world_validation_config(saturday=True)
        rule = next(r for r in sat.sections if r.name == "The Ten")
        assert rule.min_items == 0 and rule.min_chars >= 1500
        wk = omni_world_validation_config(saturday=False)
        assert next(r for r in wk.sections if r.name == "The Ten").min_items == 8

    def test_run_show_records_hook_metrics(self):
        src = (ROOT / "run_show.py").read_text(encoding="utf-8")
        assert 'extra_context.pop("metrics", None)' in src


class TestPredictionMarkets:
    def test_board_week_parses_the_committed_ep1(self):
        from engine.board_week import board_lines
        files = sorted((ROOT / "digests" / "prediction_markets").glob("*_Ep001_*.md"))
        assert files
        lines = board_lines(files[-1].read_text(encoding="utf-8"))
        assert len(lines) >= 3
        assert all(0 <= ln["prob"] <= 100 for ln in lines)

    def test_week_block_pairs_first_and_latest_readings(self, tmp_path):
        from engine.board_week import week_board_block
        d = tmp_path
        (d / "PM_Ep010_20260921.md").write_text(
            "### The Board\n- Will X happen by October?: 40% implied probability (Polymarket)\n"
            "- Will Y pass?: 70% implied probability (Kalshi)\n### New and Notable\n", encoding="utf-8")
        (d / "PM_Ep011_20260923.md").write_text(
            "### The Board\n- Will X happen by October?: 55% implied probability (Polymarket)\n"
            "### New and Notable\n", encoding="utf-8")
        block = week_board_block(d, _dt.date(2026, 9, 25))
        assert "### The Week's Board" in block
        assert "40% on Monday → 55% on Wednesday (+15 points)" in block
        assert "Will Y pass? (Kalshi): 70% on Monday; no later reading" in block
        assert week_board_block(tmp_path / "empty", _dt.date(2026, 9, 25)) == ""

    def test_hook_wires_the_friday_block(self):
        src = (ROOT / "shows" / "hooks" / "prediction_markets.py").read_text(encoding="utf-8")
        assert "from engine.board_week import week_board_block" in src
        assert "today.weekday() == 4" in src

    def test_prompts_carry_price_not_odds_week_board_and_critic(self):
        d = _prompt("prediction_markets_digest.txt")
        assert "PRICE, NOT ODDS" in d and "INDEPENDENCE" in d
        assert "### The Week's Board\nFRIDAYS ONLY" in d
        assert "counter-argument from a NAMED critic" in d
        assert "FOUR fields, never fewer" in d
        p = _prompt("prediction_markets_podcast.txt")
        assert '"the week\'s board" once' in p
        assert 'never "the odds"' in p

    def test_validator_board_stops_at_week_board(self):
        from engine.validation import prediction_markets_validation_config
        rule = next(r for r in prediction_markets_validation_config().sections if r.name == "The Board")
        assert "The Week's Board" in rule.pattern

    def test_curriculum_restocked(self):
        data = yaml.safe_load((ROOT / "shows" / "curricula" / "prediction_markets.yaml").read_text(encoding="utf-8"))
        unproduced = [e for e in data["queue"] if not e.get("produced")]
        assert len(unproduced) >= 40
        ids = [e["id"] for e in data["queue"]]
        assert len(ids) == len(set(ids))


class TestCalendarClose:
    def test_mag7_calendar_section_chapter_and_counterpoint_keyed_to_lead(self):
        d = _prompt("mag7_digest.txt")
        assert "### On the Calendar" in d and "Never an earnings date" in d
        assert "strongest factual case against the LEAD story" in d
        p = _prompt("mag7_podcast.txt")
        assert "[On the Calendar] Only when the briefing has the section: it is read LAST" in p
        assert '"top of the tape" once' in p
        titles = [m["title"] for m in _yaml("mag7")["chapters"]["section_markers"]]
        assert "Top News" in titles and "On the Calendar" in titles

    def test_ai_chips_horizon_read_last_and_dc_state_words(self):
        d = _prompt("ai_chips_digest.txt")
        assert "announced, under construction, or energized" in d
        p = _prompt("ai_chips_podcast.txt")
        assert "[On the Horizon] Read LAST before the teaser" in p
        titles = [m["title"] for m in _yaml("ai_chips")["chapters"]["section_markers"]]
        assert "On the Horizon" in titles
        assert "dc_items_unlabelled" in _yaml("ai_chips")["digest_lints"]


class TestHealthShows:
    def test_peptides_spotlight_card_matches_the_lint_labels(self):
        from engine.digest_lint import SPOTLIGHT_CARD_LABELS as SPOTLIGHT_LABELS
        d = _prompt("peptides_digest.txt")
        for label in SPOTLIGHT_LABELS:
            assert label in d, label
        lints = _yaml("peptides")["digest_lints"]
        assert "spotlight_card" in lints and "evidence_rung" in lints

    def test_longevity_names_one_hallmark_never_the_framework(self):
        d = _prompt("longevity_digest.txt")
        assert "never list the hallmarks, never count them" in d
        p = _prompt("longevity_podcast.txt")
        assert "never a recital" in p
        assert "evidence_rung" in _yaml("longevity")["digest_lints"]
        pats = _yaml("longevity")["exclude_title_patterns"]
        assert any("Sj" in p for p in pats)
        assert re.search(pats[-1], "Sjogren's syndrome drug wins Phase 3")
        assert not re.search(pats[-1], "Rapamycin trial in older adults")


class TestLocalShows:
    def test_mira_says_she_does_not_live_there(self):
        from engine.intros import _SHOW_PERSONALITIES
        for slug in ("vancouver", "collingwood"):
            tail = _SHOW_PERSONALITIES[slug]["identity_tail"]
            assert "I'm Mira" in tail and "don't live in" in tail, slug

    def test_collingwood_slow_news_library_loads(self):
        from engine.slow_news import load_segment_library
        cfg = _yaml("collingwood")["slow_news"]
        assert cfg["enabled"] is True
        segs = load_segment_library(cfg["library_file"])
        assert len(segs) >= 10
        for s in segs:
            assert s["type"] == "deep_dive" and s["prompt_template"].startswith("Write a ")
            # Evergreen: never a claim about this week.
            assert "this week" not in s["prompt_template"].lower()

    def test_latam_has_spanish_and_portuguese_publishers(self):
        labels = {s["label"] for s in _yaml("omni_view_latam")["sources"]}
        for want in ("El País América", "Folha de S.Paulo", "O Globo", "La Nación", "Reforma", "Infobae"):
            assert want in labels, want


@pytest.mark.parametrize("slug", COHORT)
def test_prompts_still_render(slug):
    """Every cohort prompt survives the include resolver (the fidelity test
    covers this network-wide; this names the cohort in the failure)."""
    from engine.generator import load_prompt
    for kind in ("digest", "podcast"):
        p = PROMPTS / f"{slug}_{kind}.txt"
        if p.exists():
            assert load_prompt(str(p)).strip()
