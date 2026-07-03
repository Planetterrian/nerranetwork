"""Drift guards for The DP Pod (July 2026 launch shape).

Pins the launch decisions so a partial revert or config drift fails CI:
- two-host dialogue TTS wiring (voices, no speech wrap, Patrick fallback)
- daily cadence with NO Sunday recap (operator decision: fresh episode daily)
- main-site registration under show_page thedppod.html + network.rss feed
- chapter markers: Sign-Off listed before the body markers (EI June-11
  ordering rule) with where anchors
- intros personality emits speaker-labeled dialogue whose every closing
  variant ends with the exact sign-off "Do something about it."
"""

from __future__ import annotations

import datetime
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from engine.config import load_config  # noqa: E402

CFG = load_config(PROJECT_ROOT / "shows" / "dp_pod.yaml")


class TestDialogueTTSWiring:
    def test_dialogue_mode_with_both_hosts(self):
        assert CFG.tts.dialogue_mode is True
        assert CFG.tts.dialogue_voices.get("PATRICK") == "kdif6sqjcyiq"
        assert CFG.tts.dialogue_voices.get("DAN") == "0vscf8u8yrxc"

    def test_no_speech_wrap_in_dialogue_mode(self):
        # Per-turn wraps are the landmine-#17 "Fast." leak shape multiplied
        # by every speaker handoff — dp_pod pins the wrap empty.
        assert CFG.tts.speech_wrap_open == ""
        assert CFG.tts.speech_wrap_close == ""

    def test_single_voice_fallback_stays_on_network_voice(self):
        assert CFG.tts.voice_id == "kdif6sqjcyiq"


class TestCadence:
    def test_daily_no_sunday_recap(self):
        # Operator decision: fresh episode every day including Sunday.
        assert CFG.weekly_recap_on_sunday is False


class TestLaunchDistribution:
    def test_rss_only_at_launch(self):
        assert CFG.publishing.x_enabled is False
        assert CFG.youtube.enabled is False
        assert CFG.newsletter.enabled is False
        assert CFG.multilingual.enabled is False

    def test_future_youtube_enable_is_one_line(self):
        # image_provider pre-set to grok so flipping youtube.enabled doesn't
        # trip test_config.py::test_youtube_enabled_shows_use_grok_image_provider.
        assert CFG.youtube.image_provider == "grok"
        assert len(CFG.youtube.image_queries) >= 3


class TestSiteRegistration:
    def test_registered_with_thedppod_page(self):
        from generate_html import NETWORK_SHOWS

        assert "dp_pod" in NETWORK_SHOWS
        assert NETWORK_SHOWS["dp_pod"]["show_page"] == "thedppod.html"
        assert NETWORK_SHOWS["dp_pod"]["rss_file"] == "dp_pod_podcast.rss"

    def test_in_network_rss_feeds(self):
        src = (PROJECT_ROOT / "generate_network_rss.py").read_text(encoding="utf-8")
        assert '"dp_pod_podcast.rss"' in src

    def test_rss_link_points_at_thedppod_page(self):
        assert CFG.publishing.rss_link.endswith("/thedppod.html")


class TestChapterMarkers:
    def test_sign_off_listed_before_body_markers(self):
        titles = [m.title for m in CFG.chapters.section_markers]
        assert titles[0] == "Cold Open"
        assert titles[1] == "Sign-Off", (
            "Sign-Off must precede the body markers (EI June-11 ordering "
            "rule) so a merged final line is titled Sign-Off, not The Lever"
        )
        for expected in ("The Positive Papers", "Think Positive", "The Lever",
                         "Do Positive Dispatch"):
            assert expected in titles

    def test_positional_anchors(self):
        by_title = {m.title: m for m in CFG.chapters.section_markers}
        assert by_title["Cold Open"].where == "start"
        assert by_title["Sign-Off"].where == "end"


class TestClubPage:
    """July 2026 club redesign (docs/dp_pod_market_assessment_2026_07.md):
    the page is a membership pitch, not a media property — pledge-led join,
    constrained Dispatch grammar, seeded member wall, free-forever charter."""

    def test_registry_uses_club_template(self):
        from generate_html import NETWORK_SHOWS

        assert NETWORK_SHOWS["dp_pod"].get("show_page_template") == "show_page_dp_pod.html.j2"
        assert (PROJECT_ROOT / "templates" / "show_page_dp_pod.html.j2").exists()

    def test_club_page_renders_with_core_mechanics(self, tmp_path):
        import generate_html as gh

        html_path = gh.generate_show_page("dp_pod", dry_run=False)
        html = Path(html_path).read_text(encoding="utf-8")
        # Mechanic 1: pledge-led join via Buttondown with the show tag
        assert "buttondown.com/api/emails/embed-subscribe" in html
        assert 'value="DP Pod"' in html
        assert "Do Positive Pledge" in html
        # Mechanic 1b: seeded member wall (pledger-majority sequencing)
        assert "№ 001" in html and "Dan Perra" in html
        assert "№ 002" in html and "Patrick Novak" in html
        # Mechanic 2: constrained Dispatch grammar with a real submission path
        assert "mailto:" in html and "Do%20Positive%20Dispatch" in html
        assert "The honest numbers" in html
        # Mechanic 3/4: starter levers pre-launch; charter promises free
        # JOINING, never "free forever" (operator decision, July 2026 —
        # patron tiers fund Nerra; episodes stay un-paywalled)
        assert "Free to join" in html
        assert "Free forever" not in html
        assert "Do something about it" in html

    def test_patron_tiers_present_with_placeholder_until_url_set(self):
        import generate_html as gh

        html = (PROJECT_ROOT / "thedppod.html").read_text(encoding="utf-8")
        # Belonging-framed patronage (MaxFun/Defector/RtbC model): support,
        # not access — three tiers, nothing paywalled.
        assert "The club runs on patrons" in html
        assert "Become a Patron" in html or "Patron doors open" in html
        assert "Founding Patron" in html
        assert "paywall" in html  # the "never moves behind a paywall" promise
        # Registry carries the pluggable checkout URL field.
        assert "patron_url" in gh.NETWORK_SHOWS["dp_pod"]

    def test_lever_board_extracts_from_digest(self, tmp_path, monkeypatch):
        import generate_html as gh

        digest_dir = tmp_path / "digests" / "dp_pod"
        digest_dir.mkdir(parents=True)
        (digest_dir / "DP_Pod_Ep001_20260703.md").write_text(
            "# The DP Pod: The Do Positive Podcast\n"
            "**Date:** July 03, 2026\n\n"
            "**HOOK:** Heat pumps just crossed the payback line.\n\n"
            "### The Positive Papers\n1. **Solar: Source**\n   Text.\n\n"
            "### The Lever\n"
            "Get a free home heat-loss assessment and seal the top three leaks. "
            "Costs roughly forty dollars and two hours; saves in the range of "
            "one hundred fifty dollars a year.\n\n"
            "### Do Positive Dispatch\nNo dispatches in the bag today.\n",
            encoding="utf-8",
        )
        monkeypatch.setattr(gh, "ROOT", tmp_path)
        levers = gh._collect_dp_levers()
        assert len(levers) == 1
        assert levers[0]["episode_num"] == 1
        assert "heat-loss assessment" in levers[0]["lever_text"]
        assert "Dispatch" not in levers[0]["lever_text"]


class TestEp001Fixes:
    """Regression guards from the Episode 1 review (July 2 2026)."""

    def test_dialogue_disclosure_is_plural(self):
        # Ep001 spoke the single-host line ("my voice") on a two-voice
        # episode; dialogue mode now uses the plural variant.
        src = (PROJECT_ROOT / "run_show.py").read_text(encoding="utf-8")
        assert "_AI_DISCLOSURE_DIALOGUE" in src
        assert "our voices" in src

    def test_ep1_dialogue_branch_uses_personality_closing(self):
        # The generic single-host Ep1 closing fought the dialogue prompt
        # (Ep001 shipped "please subscribe..." truncated mid-sentence);
        # dialogue shows now debut with the personality's labeled closing.
        src = (PROJECT_ROOT / "run_show.py").read_text(encoding="utf-8")
        ep1_block = src.split("if episode_num == 1:", 1)[1][:2200]
        assert "config.tts.dialogue_mode" in ep1_block
        assert "build_closing_block" in ep1_block

    def test_dispatch_prompt_bans_invented_host_anecdotes(self):
        prompt = (PROJECT_ROOT / "shows" / "prompts" / "dp_pod_podcast.txt").read_text(
            encoding="utf-8")
        assert "NEVER invent specific past personal anecdotes" in prompt
        assert "forward commitment" in prompt


class TestDebutRework:
    """July 2 2026 Ep1 rework (operator verdict on the shipped debut:
    robotic, no founding story). Pins the designed-debut machinery."""

    def test_theme_song_is_the_music_bed(self):
        assert CFG.audio.music_file == "assets/music/dp_pod.mp3"
        assert (PROJECT_ROOT / "assets" / "music" / "dp_pod.mp3").exists()

    def test_full_song_outro_on_episode_one_only(self):
        assert CFG.audio.debut_song_file == "assets/music/dp_pod.mp3"
        assert CFG.audio.debut_song_episode == 1

    def test_debut_song_fields_default_noop(self):
        from engine.config import AudioConfig

        cfg = AudioConfig()
        assert cfg.debut_song_file is None
        assert cfg.debut_song_episode == 0

    def test_append_full_song_exists(self):
        from engine.audio import append_full_song  # noqa: F401

    def test_snappier_handoffs(self):
        # 300 -> 220 -> 180 across the two Ep001 listens.
        assert CFG.tts.dialogue_pause_ms == 180

    def test_energy_speed_multiplier(self):
        # Documented Grok speed param (0.7-1.5); subtle lift, dp_pod only.
        assert abs(CFG.tts.speed - 1.05) < 1e-9

    def test_hook_supplies_network_context(self):
        import importlib

        hook = importlib.import_module("shows.hooks.dp_pod")
        ctx = hook.pre_fetch(CFG, episode_num=2, today_str="July 3, 2026")
        assert "nerra_network_context" in ctx
        assert "First Principles Daily" in ctx["nerra_network_context"]

    def test_first_episode_overrides_are_dp_pod_specific(self):
        from engine.first_episode import (
            first_episode_digest_appendix,
            first_episode_podcast_appendix,
        )

        digest = first_episode_digest_appendix(1, CFG.name, show_slug="dp_pod")
        podcast = first_episode_podcast_appendix(1, CFG.name, show_slug="dp_pod")
        assert "FOUNDING BRIEF" in digest
        # July 3 2026: the debut anchor is the network's own build story
        # (pinned via shows/dp_pod_debut_anchor.md), not FP material.
        assert "BUILDING NERRA" in digest
        assert "Do Positive" in podcast and "song" in podcast.lower()
        assert "write NOTHING" in podcast
        # Other shows keep the generic debut guidance.
        generic = first_episode_podcast_appendix(1, "SpaceX Daily", show_slug="spacex")
        assert "FOUNDING" not in generic

    def test_podcast_prompt_has_energy_and_crosspromo_blocks(self):
        prompt = (PROJECT_ROOT / "shows" / "prompts" / "dp_pod_podcast.txt").read_text(
            encoding="utf-8")
        assert "WRITE THE ENERGY IN" in prompt
        assert "{nerra_network_context}" in prompt
        assert "CROSS-PROMO" in prompt

    def test_podcast_prompt_voice_direction_tags_budgeted(self):
        # Grok-docs-sanctioned inline tags with a hard budget; wrapping tags
        # beyond <emphasis> stay banned (the landmine-#17 leak class).
        prompt = (PROJECT_ROOT / "shows" / "prompts" / "dp_pod_podcast.txt").read_text(
            encoding="utf-8")
        assert "VOICE DIRECTION TAGS" in prompt
        assert "[laugh]" in prompt and "<emphasis>" in prompt
        assert "PUNCTUATION IS PROSODY" in prompt

    def test_analysis_is_the_show(self):
        prompt = (PROJECT_ROOT / "shows" / "prompts" / "dp_pod_podcast.txt").read_text(
            encoding="utf-8")
        assert "THE ANALYSIS IS THE SHOW" in prompt


class TestThinkPositiveSegment:
    """July 2026: the mindset segment — mental health via action-orientation,
    creativity, and individual accountability (Robbins/Sinek et al.), the
    first show to treat mental health alongside science and tech."""

    def test_digest_prompt_has_the_section_with_guardrails(self):
        prompt = (PROJECT_ROOT / "shows" / "prompts" / "dp_pod_digest.txt").read_text(
            encoding="utf-8")
        assert "### Think Positive" in prompt
        assert "Robbins" in prompt and "Sinek" in prompt
        # Editorial guardrails: attribution without fabrication, non-clinical.
        assert "never invent" in prompt
        assert "not therapy" in prompt or "never substitutes for professional" in prompt

    def test_podcast_prompt_has_the_spoken_segment(self):
        prompt = (PROJECT_ROOT / "shows" / "prompts" / "dp_pod_podcast.txt").read_text(
            encoding="utf-8")
        assert "[Think Positive]" in prompt
        assert "time to Think Positive" in prompt
        # The marker-theft guard: the phrase is banned before the announcement.
        assert "Do NOT speak the phrase" in prompt

    def test_chapter_marker_between_papers_and_lever(self):
        titles = [m.title for m in CFG.chapters.section_markers]
        assert titles.index("The Positive Papers") < titles.index("Think Positive") < titles.index("The Lever")

    def test_word_target_raised_for_the_extra_segment(self):
        assert CFG.llm.min_podcast_words == 1550

    def test_debut_includes_the_segment(self):
        from engine.first_episode import (
            first_episode_digest_appendix,
            first_episode_podcast_appendix,
        )

        assert "Think Positive" in first_episode_digest_appendix(1, CFG.name, show_slug="dp_pod")
        assert "[Think Positive" in first_episode_podcast_appendix(1, CFG.name, show_slug="dp_pod")

    def test_club_page_shows_the_mindset_step(self):
        html = (PROJECT_ROOT / "thedppod.html").read_text(encoding="utf-8")
        assert "Think Positive" in html
        assert "You get the mindset" in html

    def test_pipeline_ep1_block_is_dialogue_aware(self):
        # BOTH Ep001 renders aired pipeline.py's truncated generic closing —
        # run_show's pod_vars never reach run_generation_phase, so the
        # pipeline block is the live path and must handle dialogue shows.
        src = (PROJECT_ROOT / "engine" / "pipeline.py").read_text(encoding="utf-8")
        ep1_block = src.split("if episode_num == 1:", 1)[1][:2600]
        assert "dialogue_mode" in ep1_block
        assert "build_closing_block" in ep1_block
        assert "please subscribe... " not in src, (
            "the truncated Ep1 closing literal is back — it aired twice"
        )

    def test_debut_override_demands_founding_conversation_and_springboard(self):
        from engine.first_episode import (
            first_episode_digest_appendix,
            first_episode_podcast_appendix,
        )

        podcast = first_episode_podcast_appendix(1, CFG.name, show_slug="dp_pod")
        assert "500" in podcast  # the founding conversation length floor
        assert "SPRINGBOARD" in podcast
        # July 3 2026 (operator: too many personal details in the debut):
        # the anchor is the network's own build story, bios are capped at
        # one light detail per host, and the tour is woven in — no catalog.
        assert "how Nerra got built" in podcast
        assert "PERSONAL-DETAIL LIMIT" in podcast
        assert "NO separate tour" in podcast
        digest = first_episode_digest_appendix(1, CFG.name, show_slug="dp_pod")
        assert "SPRINGBOARD" in digest
        assert "BUILDING NERRA" in digest
        assert "PERSONAL-DETAIL LIMIT" in digest
        assert "BANNED" in digest  # editorial-boilerplate ban (the tour wall)


class TestDebutEnablers:
    """July 3 2026: the rehearse-listen-iterate loop + real founders'
    material — the levers for making the debut genuinely great."""

    def test_rehearse_flag_exists_and_stops_before_publish(self):
        src = (PROJECT_ROOT / "run_show.py").read_text(encoding="utf-8")
        assert '"--rehearse"' in src
        stop = src.index("Rehearsal stop (--rehearse)")
        publish = src.index("=== Publish & Distribution Phase ===")
        assert stop < publish, "the rehearsal stop must precede the publish phase"
        # Artifacts renamed so numbering/blog/lever gathers never see them.
        assert 'f"rehearsal_{_f.name}"' in src
        # Rehearsals never contaminate the content lake (same-day real run
        # would see its own stories as recently covered).
        assert "skipping content-lake write" in src

    def test_shipped_founders_notes_inject_real_material(self):
        import importlib

        hook = importlib.import_module("shows.hooks.dp_pod")
        # July 3 2026: the operator filled the notes with real material —
        # it must reach the prompts, with the guidance comments stripped.
        out = hook._founders_notes()
        assert "FOUNDERS' NOTES" in out
        assert "Yukon River Quest" in out      # Patrick's real grit story
        assert "WestJet" in out                # Dan's real world
        assert "operator-editable" not in out  # HTML comments stripped
        ctx = hook.pre_fetch(CFG, episode_num=1, today_str="July 3, 2026")
        assert "FOUNDERS' NOTES" in ctx["nerra_network_context"]

    def test_founders_notes_inject_when_real_content_added(self, tmp_path, monkeypatch):
        import importlib

        hook = importlib.import_module("shows.hooks.dp_pod")
        notes = tmp_path / "shows" / "dp_pod_founders_notes.md"
        notes.parent.mkdir(parents=True)
        notes.write_text(
            "<!-- guidance -->\nDan really did land in a crosswind at YVR "
            "last week and thought about checklists.", encoding="utf-8")
        monkeypatch.setattr(hook, "_ROOT", tmp_path)
        out = hook._founders_notes()
        assert "FOUNDERS' NOTES" in out
        assert "crosswind" in out
        assert "guidance" not in out  # comments stripped

    def test_shipped_debut_anchor_is_the_nerra_build_story(self):
        import importlib

        hook = importlib.import_module("shows.hooks.dp_pod")
        brief = hook._latest_first_principles_brief()
        assert "Pinned" in brief
        assert "BUILDING NERRA" in brief
        assert "OPEN QUESTIONS" in brief          # the 900-word cap keeps them
        assert "DEBUT ANCHOR" not in brief        # HTML guidance comment stripped

    def test_founders_notes_carry_the_pacing_rule(self):
        text = (PROJECT_ROOT / "shows" / "dp_pod_founders_notes.md").read_text(
            encoding="utf-8")
        assert "PACING RULE" in text
        assert "ONE light biographical detail" in text

    def test_debut_anchor_pin_wins_over_latest_fp(self, tmp_path, monkeypatch):
        import importlib

        hook = importlib.import_module("shows.hooks.dp_pod")
        (tmp_path / "shows").mkdir(parents=True)
        (tmp_path / "shows" / "dp_pod_debut_anchor.md").write_text(
            "The price of light fell ten thousandfold.", encoding="utf-8")
        fp_dir = tmp_path / "digests" / "first_principles"
        fp_dir.mkdir(parents=True)
        (fp_dir / "FP_Ep099.md").write_text(
            "**HOOK:** Something else entirely.\nbody", encoding="utf-8")
        monkeypatch.setattr(hook, "_ROOT", tmp_path)
        brief = hook._latest_first_principles_brief()
        assert "Pinned" in brief and "price of light" in brief
        assert "Something else" not in brief


class TestIntrosPersonality:
    def test_intro_is_dan_labeled_dialogue(self):
        from engine.intros import build_intro_line

        intro = build_intro_line(
            "dp_pod", episode_num=5, today_str="July 10, 2026",
            date=datetime.date(2026, 7, 10),
        )
        assert intro.startswith("DAN: ")
        assert "The DP Pod" in intro

    def test_every_closing_ends_with_sign_off_and_labels(self):
        from engine.intros import _SHOW_PERSONALITIES

        closings = _SHOW_PERSONALITIES["dp_pod"]["closings"]
        assert len(closings) >= 3
        for closing in closings:
            assert closing.rstrip().endswith("Do something about it."), (
                "every dp_pod closing must end with the exact sign-off — "
                "the Sign-Off chapter marker and brand promise key off it"
            )
            assert "PATRICK:" in closing, (
                "dp_pod closings are two-host dialogue — Patrick needs a turn"
            )

    def test_closing_parses_as_dialogue(self):
        from engine.intros import build_closing_block
        from engine.tts_dialogue import parse_dialogue_turns

        closing = build_closing_block(
            "dp_pod", episode_num=5, today_str="July 10, 2026",
            date=datetime.date(2026, 7, 10),
        )
        groups = parse_dialogue_turns(closing, CFG.tts.dialogue_voices)
        speakers = [g[0] for g in groups]
        assert speakers[0] == "DAN"
        assert "PATRICK" in speakers
