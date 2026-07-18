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
import re
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
        # Operator decision: fresh episode every day including Sunday, and no
        # weekly-summary segment (dp_pod has its own fixed daily shape).
        assert CFG.weekly_summary_segment is False


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
    """July 2026 club redesign + July 9 de-gimmick pass
    (docs/reviews/dp_pod_review_2026_07_09.md): membership pitch without
    oath-heavy pledge language; constrained Dispatch grammar; seeded wall."""

    def test_registry_uses_club_template(self):
        from generate_html import NETWORK_SHOWS

        assert NETWORK_SHOWS["dp_pod"].get("show_page_template") == "show_page_dp_pod.html.j2"
        assert (PROJECT_ROOT / "templates" / "show_page_dp_pod.html.j2").exists()

    def test_club_page_renders_with_core_mechanics(self, tmp_path):
        import generate_html as gh

        html_path = gh.generate_show_page("dp_pod", dry_run=False)
        html = Path(html_path).read_text(encoding="utf-8")
        # Join via Buttondown with the show tag (de-gimmicked: invitation,
        # not an oath-style "Sign the pledge")
        assert "buttondown.com/api/emails/embed-subscribe" in html
        assert 'value="DP Pod"' in html
        assert "Join the club" in html
        assert "Join free — get the daily briefing" in html
        assert "Sign the pledge" not in html
        assert "once a week, I'll do one positive thing" not in html
        # Seeded member wall (pledger-majority sequencing)
        assert "№ 001" in html and "Dan Perra" in html
        assert "№ 002" in html and "Patrick Novak" in html
        # Constrained Dispatch grammar with a real submission path
        assert "mailto:" in html and "Do%20Positive%20Dispatch" in html
        assert "The honest numbers" in html
        # Charter: free JOINING, never "free forever"
        assert "Free to join" in html
        assert "Free forever" not in html
        assert "Do something about it" in html
        # Lever framed as invitation, not homework assignment
        assert "This week's levers" in html
        assert "This week's assignments" not in html
        assert "You get one invitation" in html

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

    def test_hook_injects_previous_lever_for_dispatch_continuity(self):
        """Ep2/Ep4 invented a heat-pump callback that never aired — the hook
        must surface the real prior Lever so Dispatch can't invent one."""
        import importlib

        hook = importlib.import_module("shows.hooks.dp_pod")
        # Live digests exist through Ep4 — previous lever should be Ep4's
        # solar assessment (newest) or at least some real aired action.
        prev = hook._previous_lever_for_dispatch()
        assert prev.startswith("PREVIOUS LEVER")
        # The quoted lever body (after the colon) must be a real aired action —
        # not a phantom heat-pump callback. The instruction preamble may still
        # mention heat pumps as a forbidden example.
        quoted = prev.split("):", 1)[-1]
        assert "heat-pump" not in quoted.lower()
        assert "heat pump" not in quoted.lower()
        # Data-independent reality check (the old hard-coded token list broke
        # the suite whenever a new episode's lever used different words): the
        # quoted text must come verbatim from the cited episode's committed
        # digest, proving it is an aired action rather than an invention.
        ep_match = re.search(r"\[Ep(\d+)\]\s*(.+)", quoted, re.DOTALL)
        assert ep_match, f"no [EpNNN] citation in: {quoted[:120]}"
        digest_glob = f"DP_Pod_Ep{int(ep_match.group(1)):03d}_*.md"
        sources = list((PROJECT_ROOT / "digests" / "dp_pod").glob(digest_glob))
        assert sources, f"cited digest {digest_glob} not found"
        digest_text = re.sub(r"\s+", " ", sources[0].read_text(encoding="utf-8"))
        lever_snippet = re.sub(r"\s+", " ", ep_match.group(2)).rstrip("…").strip()
        assert lever_snippet[:120] in digest_text, (
            f"quoted lever not found in {sources[0].name}: {lever_snippet[:120]}"
        )
        ctx = hook.pre_fetch(CFG, episode_num=5, today_str="July 9, 2026")
        assert "PREVIOUS LEVER" in ctx["nerra_network_context"]

    def test_digest_prompt_forbids_phantom_prior_levers(self):
        digest = (PROJECT_ROOT / "shows" / "prompts" / "dp_pod_digest.txt").read_text(
            encoding="utf-8")
        assert "PREVIOUS LEVER" in digest
        assert "never invent a different past lever" in digest.lower() or (
            "NEVER invent a prior Lever" in digest
        )

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

    def test_podcast_prompt_has_energy_and_network_blocks(self):
        prompt = (PROJECT_ROOT / "shows" / "prompts" / "dp_pod_podcast.txt").read_text(
            encoding="utf-8")
        assert "WRITE THE ENERGY IN" in prompt
        assert "{nerra_network_context}" in prompt
        # July 2026 follow-up pass: the occasional CROSS-PROMO became the
        # regular FROM THE NETWORK beat — one grounded pointer per episode.
        assert "FROM THE NETWORK" in prompt

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

    def test_debut_anchor_retired_after_ship(self, tmp_path):
        # Episode 1 shipped (operator-approved July 4 2026) — the pinned
        # debut anchor is deleted and the hook falls back to the latest
        # First Principles brief. The pin mechanism itself stays: dropping
        # content into shows/dp_pod_debut_anchor.md re-engages it.
        import importlib

        hook = importlib.import_module("shows.hooks.dp_pod")
        assert not (PROJECT_ROOT / "shows" / "dp_pod_debut_anchor.md").exists()
        brief = hook._latest_first_principles_brief()
        assert "Pinned" not in brief
        assert "First Principles Daily" in brief

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


class TestEp001V4Fixes:
    """Regression guards from the third Episode 1 review (July 4 2026, v4
    render): digest expansion paraphrase-duplication, spoken markdown header
    from a missing HOOK, and the Lever chapter stolen by a cold-open mention."""

    def test_digest_expansion_retry_dedups(self):
        # The v4 digest's expand-retry re-told every beat as a near-verbatim
        # duplicate wall; the retry output now runs the same near-duplicate
        # sentence strip the podcast-side retry got in the July net-pass.
        src = (PROJECT_ROOT / "engine" / "generator.py").read_text(encoding="utf-8")
        digest_retry = src.split("firing one-shot ", 1)[1]
        assert "_dedup_expansion_sentences(expanded)" in digest_retry[:3000], (
            "the digest expansion retry must strip near-duplicate sentences "
            "(Ep001 v4 shipped a paraphrase-duplicated founding brief)"
        )

    def test_pipeline_hook_fallback_skips_markdown(self):
        # v4 spoke "# The DP Pod — The Founding Brief" on air: the hook
        # fallback grabbed the digest's first line, a raw markdown header.
        src = (PROJECT_ROOT / "engine" / "pipeline.py").read_text(encoding="utf-8")
        assert 'startswith(("#", "━", "---", "==="))' in src, (
            "the effective_hook fallback must skip markdown/rule lines"
        )

    def test_debut_digest_requires_hook_line(self):
        from engine.first_episode import first_episode_digest_appendix

        appendix = first_episode_digest_appendix(1, "The DP Pod", "dp_pod")
        assert "**HOOK:**" in appendix, (
            "the debut brief must lead with a HOOK line — v4 omitted it and "
            "the spoken hook fell back to a raw markdown header"
        )

    def test_lever_marker_is_announce_anchored(self):
        by_title = {m.title: m for m in CFG.chapters.section_markers}
        lever = by_title["The Lever"]
        assert "brings us to" in lever.pattern, (
            "the Lever marker must be announce-anchored (v4's cold-open "
            "mention of 'The Lever' stole the chapter at 74s)"
        )
        # The bare segment name must NOT be a standalone alternative.
        import re
        for alt in lever.pattern.split("|"):
            assert re.sub(r"\[.\w\]", "", alt).strip().lower() not in (
                "the lever", "he lever"
            ), f"bare-name alternative reintroduces the theft: {alt!r}"

    def test_prompt_has_segment_name_discipline(self):
        prompt = (PROJECT_ROOT / "shows" / "prompts" / "dp_pod_podcast.txt").read_text(
            encoding="utf-8")
        assert "SEGMENT-NAME DISCIPLINE" in prompt
        assert "brings us to The" in prompt


class TestCommunityLayer:
    """The club page's learn-and-encourage layer (July 4 2026): the Mindset
    Shelf (Think Positive principles from digests) and the Dispatch Wall
    (operator-curated REAL listener dispatches — never generated)."""

    def test_mindset_collector_extracts_think_positive(self, tmp_path, monkeypatch):
        import generate_html as gh

        digest_dir = tmp_path / "digests" / "dp_pod"
        digest_dir.mkdir(parents=True)
        (digest_dir / "DP_Pod_Ep003_20260706.md").write_text(
            "# The DP Pod\n\n**HOOK:** Test hook\n\n"
            "### The Positive Papers\nStuff.\n\n"
            "### Think Positive\nCarol Dweck's **growth mindset**: add "
            "\"yet\" out loud. [src](https://x.com)\n\n"
            "### The Lever\nDo the thing.\n\n### Sources\n- x\n",
            encoding="utf-8",
        )
        monkeypatch.setattr(gh, "ROOT", tmp_path)
        mindsets = gh._collect_dp_mindsets()
        assert len(mindsets) == 1
        text = mindsets[0]["mindset_text"]
        assert "yet" in text and "**" not in text and "https" not in text
        assert mindsets[0]["episode_num"] == 3
        assert mindsets[0]["blog_url"] == "blog/dp_pod/ep003.html"

    def test_dispatch_collector_reads_curated_json(self, tmp_path, monkeypatch):
        import json as _json

        import generate_html as gh

        dp_dir = tmp_path / "digests" / "dp_pod"
        dp_dir.mkdir(parents=True)
        (dp_dir / "dispatches.json").write_text(_json.dumps({"dispatches": [
            {"name": "Sarah, Calgary", "date": "2026-07-10",
             "did": "Sealed three drafts.", "numbers": "$14, 2h",
             "shoutout": "Dad held the ladder."},
            {"did": ""},  # invalid: skipped
            {"date": "2026-07-12", "did": "Recruited a doomscroller."},
        ]}), encoding="utf-8")
        monkeypatch.setattr(gh, "ROOT", tmp_path)
        dispatches = gh._collect_dp_dispatches()
        assert len(dispatches) == 2
        assert dispatches[0]["date"] == "2026-07-12"  # newest first
        assert dispatches[0]["name"] == "A club member"  # default
        assert dispatches[1]["numbers"] == "$14, 2h"

    def test_dispatch_collector_empty_when_file_missing(self, tmp_path, monkeypatch):
        import generate_html as gh

        monkeypatch.setattr(gh, "ROOT", tmp_path)
        assert gh._collect_dp_dispatches() == []

    def test_curated_dispatches_file_exists_and_is_empty_at_launch(self):
        import json as _json

        path = PROJECT_ROOT / "digests" / "dp_pod" / "dispatches.json"
        assert path.exists(), "the operator-curated Dispatch Wall seed file"
        data = _json.loads(path.read_text(encoding="utf-8"))
        assert isinstance(data.get("dispatches"), list)

    def test_page_renders_community_sections(self):
        import generate_html as gh

        html_path = gh.generate_show_page("dp_pod", dry_run=False)
        html = Path(html_path).read_text(encoding="utf-8")
        assert 'id="mindset"' in html and "The Mindset Shelf" in html
        assert 'id="dispatch"' in html
        # Charter promise stays on the page: real dispatches only.
        assert "never invent listener mail" in html

    def test_template_has_honest_empty_states(self):
        # Pre-launch the wall must NOT render fabricated dispatches and the
        # shelf must show its opens-with-episode-1 state, not fake principles.
        tpl = (PROJECT_ROOT / "templates" / "show_page_dp_pod.html.j2").read_text(
            encoding="utf-8")
        assert "{% if dp_dispatches %}" in tpl
        assert "{% if dp_mindsets %}" in tpl
        assert "The shelf opens with Episode 1" in tpl

    def test_operator_dispatch_cli_round_trips(self, tmp_path, monkeypatch):
        # scripts/add_dp_dispatch.py writes entries the page collector reads —
        # pin the round-trip so the two never drift apart.
        import importlib.util
        import json as _json

        spec = importlib.util.spec_from_file_location(
            "add_dp_dispatch", PROJECT_ROOT / "scripts" / "add_dp_dispatch.py")
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)

        wall = tmp_path / "digests" / "dp_pod" / "dispatches.json"
        wall.parent.mkdir(parents=True)
        wall.write_text(_json.dumps({"dispatches": []}), encoding="utf-8")
        monkeypatch.setattr(mod, "DISPATCHES_PATH", wall)
        monkeypatch.setattr(
            sys, "argv",
            ["add_dp_dispatch.py", "--name", "Sarah, Calgary",
             "--did", "Sealed three drafts.", "--numbers", "$14, 2h",
             "--date", "2026-07-10", "--episode", "3"],
        )
        mod.main()

        import generate_html as gh
        monkeypatch.setattr(gh, "ROOT", tmp_path)
        dispatches = gh._collect_dp_dispatches()
        assert len(dispatches) == 1
        assert dispatches[0]["name"] == "Sarah, Calgary"
        assert dispatches[0]["numbers"] == "$14, 2h"
        assert dispatches[0]["episode_num"] == 3


class TestShowAnthem:
    """The "Do Positive" lyrics are canon (operator-supplied, July 2026):
    on-air quotes must match assets/music/dp_pod_lyrics.md exactly, and the
    anthem must not become a per-episode tic (seeded-template class)."""

    def test_lyrics_file_is_canon(self):
        lyrics = (PROJECT_ROOT / "assets" / "music" / "dp_pod_lyrics.md").read_text(
            encoding="utf-8")
        for line in ("Turn the worry down", "One real thing, one good thing",
                     "Let it spread around", "We can build from this",
                     "Now pass it on around"):
            assert line in lyrics

    def test_prompt_anthem_block_is_anti_tic(self):
        prompt = (PROJECT_ROOT / "shows" / "prompts" / "dp_pod_podcast.txt").read_text(
            encoding="utf-8")
        assert "THE SHOW ANTHEM" in prompt
        # The anti-convergence guard: default is NO anthem reference.
        assert "ZERO TIMES" in prompt
        assert "EXACTLY" in prompt  # quotes must match the lyrics verbatim

    def test_prompt_lyric_quotes_match_canon(self):
        # Any lyric line the prompt seeds must exist verbatim in the lyrics
        # file — a drifted quote would put wrong words in the hosts' mouths.
        lyrics = (PROJECT_ROOT / "assets" / "music" / "dp_pod_lyrics.md").read_text(
            encoding="utf-8").replace("'", "'")
        prompt = (PROJECT_ROOT / "shows" / "prompts" / "dp_pod_podcast.txt").read_text(
            encoding="utf-8")
        anthem_block = prompt.split("THE SHOW ANTHEM", 1)[1].split("\n\n", 1)[0]
        import re
        lyrics = re.sub(r"\s+", " ", lyrics)
        for quoted in re.findall(r'"([^"]+)"', anthem_block):
            for fragment in re.split(r"\s*/\s*|\.\.\.", quoted):
                fragment = re.sub(r"\s+", " ", fragment).strip().rstrip(".")
                if len(fragment.split()) >= 3 and "Do Positive" not in fragment:
                    assert fragment in lyrics, f"prompt quote drifted from canon: {fragment!r}"

    def test_club_page_has_anthem_section(self):
        import generate_html as gh

        html_path = gh.generate_show_page("dp_pod", dry_run=False)
        html = Path(html_path).read_text(encoding="utf-8")
        assert 'id="anthem"' in html
        assert "Turn the worry down" in html
        assert "Now pass it on around" in html


class TestFollowUpEpisodes:
    """July 4 2026 follow-up pass (operator approved Ep1 and asked for great
    regular episodes that regularly point at real network shows/episodes):
    the FRESH ON THE NETWORK block, the daily Network pick, Think Positive
    thinker rotation memory, and the digest-depth floor raise."""

    def test_fresh_network_block_reads_real_episodes(self, tmp_path, monkeypatch):
        import datetime
        import json as _json

        import shows.hooks.dp_pod as hook

        monkeypatch.setattr(hook, "_ROOT", tmp_path)
        d = tmp_path / "digests" / "spacex"
        d.mkdir(parents=True)
        (d / "summaries_spacex.json").write_text(_json.dumps({
            "podcast": "spacex",
            "summaries": [  # newest-first, as the pipeline writes it
                {"date": "2026-07-03", "episode_num": "20",
                 "episode_title": "Ep 20: Starship's six-engine static fire validates the full cluster"},
                {"date": "2026-07-02", "episode_num": "19",
                 "episode_title": "Ep 19: older"},
            ],
        }), encoding="utf-8")
        # A stale show (outside the window) must not appear.
        d2 = tmp_path / "digests" / "tesla_shorts_time"
        d2.mkdir(parents=True)
        (d2 / "summaries_tesla.json").write_text(_json.dumps({
            "summaries": [{"date": "2026-06-01", "episode_title": "Ep 1: old"}],
        }), encoding="utf-8")
        block = hook._fresh_network_episodes(today=datetime.date(2026, 7, 4))
        assert "FRESH ON THE NETWORK" in block
        assert "SpaceX Daily (yesterday)" in block
        assert "six-engine static fire" in block
        assert "Ep 20:" not in block  # episode-number prefix stripped
        assert "Tesla" not in block   # stale show excluded

    def test_fresh_network_block_empty_when_nothing_fresh(self, tmp_path, monkeypatch):
        import datetime

        import shows.hooks.dp_pod as hook

        monkeypatch.setattr(hook, "_ROOT", tmp_path)
        assert hook._fresh_network_episodes(today=datetime.date(2026, 7, 4)) == ""

    def test_thinker_rotation_memory_mines_digests(self, tmp_path, monkeypatch):
        import shows.hooks.dp_pod as hook

        monkeypatch.setattr(hook, "_ROOT", tmp_path)
        d = tmp_path / "digests" / "dp_pod"
        d.mkdir(parents=True)
        (d / "DP_Pod_Ep001_20260704.md").write_text(
            "### Think Positive\nViktor Frankl's chosen response...\n\n### The Lever\nx\n",
            encoding="utf-8")
        (d / "DP_Pod_Ep002_20260705.md").write_text(
            "### Think Positive\nCarol Dweck's growth mindset...\n\n### The Lever\nx\n",
            encoding="utf-8")
        out = hook._recent_think_positive_thinkers()
        assert "RECENTLY FEATURED THINKERS" in out
        # Newest digest first: Dweck before Frankl.
        assert out.index("Carol Dweck") < out.index("Viktor Frankl")

    def test_prompts_carry_the_network_pick_contract(self):
        digest = (PROJECT_ROOT / "shows" / "prompts" / "dp_pod_digest.txt").read_text(
            encoding="utf-8")
        assert "**Network pick:**" in digest
        assert "RECENTLY FEATURED THINKERS" in digest
        podcast = (PROJECT_ROOT / "shows" / "prompts" / "dp_pod_podcast.txt").read_text(
            encoding="utf-8")
        assert "FROM THE NETWORK" in podcast
        assert "GROUNDED ONLY" in podcast
        # Anti-tic: the pointer must move around, never become a fixed slot.
        assert "never a fixed segment" in podcast

    def test_digest_depth_floor_raised(self):
        # Ep1 scripts capped ~1,200w against the 1,550 target because the
        # brief was the ceiling — the digest floor is the length lever.
        assert CFG.llm.min_digest_words == 1100
        assert CFG.llm.digest_expand_below_target is True


class TestNetworkPickRotationMemory:
    """July 18 2026 network review: the daily Network pick converged on
    Fascinating Frontiers (5/10, consecutive days, same host + frame).
    The hook now mines recent Network pick lines into a vary-away list."""

    def test_pick_memory_mines_digests_newest_first(self, tmp_path, monkeypatch):
        import shows.hooks.dp_pod as hook

        monkeypatch.setattr(hook, "_ROOT", tmp_path)
        d = tmp_path / "digests" / "dp_pod"
        d.mkdir(parents=True)
        (d / "DP_Pod_Ep010_20260714.md").write_text(
            "**Network pick:** Planetterrian Daily — quantum heat engines.\n",
            encoding="utf-8")
        (d / "DP_Pod_Ep011_20260715.md").write_text(
            "**Network pick:** Fascinating Frontiers — booster recovery.\n",
            encoding="utf-8")
        out = hook._recent_network_picks()
        assert "RECENT NETWORK PICKS" in out
        assert out.index("Fascinating Frontiers") < out.index("Planetterrian Daily")

    def test_pick_memory_in_context(self, tmp_path, monkeypatch):
        import shows.hooks.dp_pod as hook

        monkeypatch.setattr(hook, "_ROOT", tmp_path)
        (tmp_path / "digests" / "dp_pod").mkdir(parents=True)
        ctx = hook.pre_fetch(None)["nerra_network_context"]
        # No history → no section, and the hook never crashes.
        assert "THE NERRA NETWORK" in ctx
