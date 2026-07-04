"""Drift guards for The Age of AI — the Nerra Voices live-interview pipeline.

The Age of AI is the network's AI-hosted interview show: Mira (an AI
documentarian persona, Grok voice ``ara``) phones real guests via a
Voximplant scenario bridged to a Grok Voice Agent, and the episode is
produced from the real recording through two human gates (Patrick's
editorial review, guest transcript approval). Spec + runbook:
docs/age_of_ai_plan.md.

These tests pin:
* the show-registry shape (run_show is a guard-railed no-op; production
  belongs to pipelines/voices/);
* the presence + coherence of the spec artifacts (schema, scenario,
  workflows, prompts, Worker) so a partial revert fails CI;
* the editorial-pass validators (the LLM-output schema gates);
* the fire-window compilation logic that runs before any credits are spent.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parent.parent
SHOW_YAML = ROOT / "shows" / "age_of_ai.yaml"
TOPIC_QUEUE = ROOT / "shows" / "topic_queues" / "age_of_ai.yaml"
PIPELINES = ROOT / "pipelines" / "voices"
WORKER_TS = ROOT / "workers" / "voices" / "src" / "index.ts"
SCENARIO = ROOT / "voximplant" / "scenarios" / "age_of_ai_interview.js"
MIGRATION = ROOT / "supabase" / "migrations" / "20260704_nerra_voices_schema.sql"

sys.path.insert(0, str(PIPELINES))


# ---------------------------------------------------------------------------
# Show registry shape (run_show side)
# ---------------------------------------------------------------------------

class TestShowRegistryShape:
    def test_config_loads_with_mira_voice(self):
        from engine.config import load_config
        cfg = load_config(SHOW_YAML)
        assert cfg.slug == "age_of_ai"
        assert cfg.tts.provider == "grok"
        assert cfg.tts.voice_id == "ara", (
            "Mira's narration voice is the Grok built-in `ara` (spec §3.1)"
        )
        assert cfg.tts.voice_id != "kdif6sqjcyiq", (
            "the AI host must not reuse the Patrick voice clone"
        )
        assert getattr(cfg.tts, "dialogue_mode", False) is False, (
            "guest audio is REAL recorded phone audio — dialogue TTS is not "
            "part of this show"
        )
        assert cfg.publishing.host_name == "Mira"

    def test_run_show_guard_rail(self):
        """An accidental `run_show.py age_of_ai` must be a clean skip:
        narrative mode + a permanently-empty topic queue."""
        raw = yaml.safe_load(SHOW_YAML.read_text(encoding="utf-8"))
        assert raw.get("narrative_mode") is True
        assert raw.get("min_articles_skip") == 0
        queue = yaml.safe_load(TOPIC_QUEUE.read_text(encoding="utf-8"))
        assert queue == {"queue": []}, (
            "the run_show topic queue must stay empty — production goes "
            "through pipelines/voices/ (see the comment in the queue file)"
        )

    def test_distribution_off_at_launch(self):
        raw = yaml.safe_load(SHOW_YAML.read_text(encoding="utf-8"))
        assert raw["publishing"]["x_enabled"] is False
        assert raw["youtube"]["enabled"] is False
        assert raw["youtube"]["image_provider"] == "grok"
        assert raw["newsletter"]["enabled"] is False
        assert raw["multilingual"]["enabled"] is False
        assert raw.get("weekly_recap_on_sunday") is False

    def test_intro_personality_is_mira(self):
        import datetime as dt
        from engine.intros import build_closing_block, build_intro_line
        intro = build_intro_line("age_of_ai", episode_num=2,
                                 today_str="July 4, 2026",
                                 date=dt.date(2026, 7, 4))
        assert "Mira" in intro and "Age of AI" in intro
        closing = build_closing_block("age_of_ai", episode_num=2,
                                      today_str="July 4, 2026",
                                      date=dt.date(2026, 7, 4))
        assert closing.rstrip().endswith("keep being human.")
        assert "Mira" in closing


# ---------------------------------------------------------------------------
# Spec artifacts present + coherent
# ---------------------------------------------------------------------------

class TestSpecArtifacts:
    def test_supabase_migration_covers_all_tables(self):
        sql = MIGRATION.read_text(encoding="utf-8")
        for table in ("guest_applications", "interviews", "interview_briefs",
                      "interview_runs", "editorial_packages",
                      "cross_show_callouts"):
            assert f"create table if not exists {table}" in sql, table
            assert f"alter table {table} enable row level security" in sql, (
                f"{table} missing RLS"
            )
        assert "anon can submit applications" in sql

    def test_scenario_core_contracts(self):
        js = SCENARIO.read_text(encoding="utf-8")
        assert "Modules.GrokVoiceAgent" in js
        assert "stereo: true" in js, "dual-track recording is the diarization"
        assert "50 * 60 * 1000" in js, "50-minute hard cap (spec §11.8)"
        assert "api.nerranetwork.com/voices/interview-complete" in js
        assert "CallEvents.Failed" in js, "no-answer path must fire the webhook"
        assert "webhookFired" in js, "webhook must be exactly-once"

    def test_workflows_exist_and_parse(self):
        wf_dir = ROOT / ".github" / "workflows"
        expected = {
            "nerra_voices_prep_briefs.yml",
            "nerra_voices_fire_interview.yml",
            "nerra_voices_post_interview.yml",
            "nerra_voices_produce_episode.yml",
            "nerra_voices_publish.yml",
        }
        for name in expected:
            data = yaml.safe_load((wf_dir / name).read_text(encoding="utf-8"))
            assert data, f"{name} failed to parse"

    def test_dispatch_event_types_match_worker(self):
        """The Worker's repository_dispatch event names must match the
        workflows' `repository_dispatch: types:` — a rename on one side
        silently orphans the other."""
        worker = WORKER_TS.read_text(encoding="utf-8")
        post = yaml.safe_load(
            (ROOT / ".github/workflows/nerra_voices_post_interview.yml")
            .read_text(encoding="utf-8"))
        produce = yaml.safe_load(
            (ROOT / ".github/workflows/nerra_voices_produce_episode.yml")
            .read_text(encoding="utf-8"))
        post_types = post[True]["repository_dispatch"]["types"] \
            if True in post else post["on"]["repository_dispatch"]["types"]
        produce_types = produce[True]["repository_dispatch"]["types"] \
            if True in produce else produce["on"]["repository_dispatch"]["types"]
        assert "interview-complete" in post_types
        assert "interview-approved-by-guest" in produce_types
        assert 'dispatch(env, "interview-complete"' in worker
        assert 'dispatch(env, "interview-approved-by-guest"' in worker

    def test_editorial_pass_prompts_match_pipeline_list(self):
        from post_interview import EDITORIAL_PASSES
        prompt_dir = PIPELINES / "prompts" / "editorial_passes"
        on_disk = {p.name for p in prompt_dir.glob("*.txt")}
        listed = {name for name, _ in EDITORIAL_PASSES}
        assert listed == on_disk, (
            f"editorial pass list and prompt files diverged: "
            f"listed-only={listed - on_disk}, disk-only={on_disk - listed}"
        )
        assert len(EDITORIAL_PASSES) == 8, "spec §5.3: exactly 8 passes"

    def test_mira_system_prompt_contracts(self):
        text = (PIPELINES / "prompts" / "mira_system_prompt.txt").read_text(
            encoding="utf-8")
        assert "You are Mira" in text
        assert "Lightning round" in text
        assert "the one bet you're making" in text, "closing question (spec §3.3)"
        assert "Hard time cap: 45 minutes" in text
        for token in ("{{guest_name}}", "{{episode_thesis}}", "{{guest_brief}}"):
            assert token in text, f"missing template token {token}"

    def test_worker_routes_cover_spec_endpoints(self):
        worker = WORKER_TS.read_text(encoding="utf-8")
        for route in ("/voices/apply", "/voices/interview-complete",
                      "/voices/cal-com-booked", "/voices/triage-decision",
                      "/voices/episode-lookup", "/voices/guest-brief",
                      "/voices/fact-check", "/voices/admin/triage"):
            assert route in worker, f"Worker missing route {route}"
        assert "gate2Housekeeping" in worker, "day-7 auto-approve cron missing"

    def test_email_templates_exist(self):
        email_dir = ROOT / "templates" / "email"
        for name in ("voices_application_received.j2",
                     "voices_triage_approved_booking_link.j2",
                     "voices_booking_confirmation.j2",
                     "voices_prep_brief.j2",
                     "voices_interview_reminder.j2",
                     "voices_transcript_for_approval.j2",
                     "voices_publish_notification.j2",
                     "voices_weekly_digest.j2"):
            assert (email_dir / name).exists(), name

    def test_apply_form_posts_to_worker(self):
        page = (ROOT / "age-of-ai-apply.html").read_text(encoding="utf-8")
        assert "api.nerranetwork.com/voices/apply" in page
        assert "recorded" in page and "approve the transcript" in page.lower() \
            or "approved the transcript" in page.lower() \
            or "approve" in page.lower()


# ---------------------------------------------------------------------------
# Fire logic (runs before any credits are spent)
# ---------------------------------------------------------------------------

class TestFireLogic:
    def test_mira_tools_shape(self):
        from fire_interviews import MIRA_TOOLS
        names = {t["name"] for t in MIRA_TOOLS}
        assert names == {"nerra_episode_lookup", "guest_brief_lookup",
                         "fact_check_claim"}, "spec §3.2: exactly these 3 tools"
        for tool in MIRA_TOOLS:
            assert tool["type"] == "function"
            assert tool["parameters"]["type"] == "object"

    def test_compile_mira_prompt_substitutes_everything(self):
        from fire_interviews import compile_mira_prompt
        prompt = compile_mira_prompt(
            {"episode_thesis": "THESIS-X"},
            {"name": "Jane Doe", "title": "Teacher", "organization": "PS 42"},
            {"bio_research": "BRIEF-X",
             "likely_questions": [{"question": "Q-ONE?"}, "Q-TWO?"]},
        )
        for needle in ("Jane Doe", "Teacher", "PS 42", "THESIS-X", "BRIEF-X",
                       "Q-ONE?", "Q-TWO?"):
            assert needle in prompt, needle
        assert "{{" not in prompt, "unsubstituted template tokens remain"

    def test_fire_window_tolerates_cron_drift(self):
        import fire_interviews as fi
        assert fi.FIRE_GRACE_BEHIND_MIN >= 5, (
            "GitHub cron is best-effort — a delayed tick must still fire "
            "what it missed (spec §5.2 note)"
        )


# ---------------------------------------------------------------------------
# Editorial-pass validators (the LLM-output schema gates, spec §7)
# ---------------------------------------------------------------------------

class TestValidators:
    def test_chapter_markers_good_and_bad(self):
        from validators.schema_validators import validate_pass_output
        good = [{"start": 0, "end": 300, "title": "The studio ban"},
                {"start": 300, "end": 900, "title": "What apprentices lose"}]
        validate_pass_output("chapter_markers", good)
        with pytest.raises(ValueError):
            validate_pass_output("chapter_markers", [])
        with pytest.raises(ValueError, match="starts before"):
            validate_pass_output("chapter_markers", [
                {"start": 300, "end": 400, "title": "b"},
                {"start": 0, "end": 200, "title": "a"},
            ])

    def test_social_copy_twitter_length(self):
        from validators.schema_validators import validate_pass_output
        base = {"twitter": "x" * 200, "linkedin": "y", "instagram": "z"}
        validate_pass_output("social_copy", base)
        with pytest.raises(ValueError, match="280"):
            validate_pass_output("social_copy", {**base, "twitter": "x" * 300})

    def test_show_fits_rejects_unknown_slugs(self):
        from validators.schema_validators import validate_pass_output
        validate_pass_output("topical_show_fits", ["models_agents"])
        with pytest.raises(ValueError, match="unknown"):
            validate_pass_output("topical_show_fits", ["not_a_show"])

    def test_clip_bounds(self):
        from validators.schema_validators import validate_pass_output
        validate_pass_output("clip_suggestions", [
            {"start": 10, "end": 55, "title": "t", "why": "w"}])
        with pytest.raises(ValueError):
            validate_pass_output("clip_suggestions", [
                {"start": 10, "end": 11, "title": "too short", "why": "w"}])

    def test_cleaned_transcript_keeps_labels(self):
        from validators.schema_validators import validate_pass_output
        ok = "\n".join(f"[00:{i:02d}] {'MIRA' if i % 2 else 'GUEST'}: " +
                       "word " * 30 for i in range(20))
        validate_pass_output("transcript_cleaned", ok)
        with pytest.raises(ValueError, match="labels"):
            validate_pass_output("transcript_cleaned", "word " * 300)

    def test_callouts_reject_unknown_show(self):
        from validators.schema_validators import validate_pass_output
        validate_pass_output("cross_show_callouts",
                             {"tesla": "Mira interviewed a battery engineer "
                                       "about the cell supply chain."})
        with pytest.raises(ValueError):
            validate_pass_output("cross_show_callouts", {"nope": "x" * 30})


# ---------------------------------------------------------------------------
# The two human gates stay wired (spec §6)
# ---------------------------------------------------------------------------

class TestHumanGates:
    def test_gate1_no_auto_publish_language(self):
        """Patrick's gate has no timeout-to-publish: the Worker only
        auto-approves GATE 2 (guest, day 7). A gate-1 auto-publish would
        contradict spec §6/§7 ('the package waits indefinitely')."""
        worker = WORKER_TS.read_text(encoding="utf-8")
        assert "approved_by_patrick" in worker
        housekeeping = worker.split("async function gate2Housekeeping")[1]
        assert "status=eq.approved_by_patrick" in housekeeping, (
            "housekeeping must only act on packages Patrick ALREADY approved"
        )

    def test_publish_requires_approved_status(self):
        src = (PIPELINES / "publish_episode.py").read_text(encoding="utf-8")
        assert "'approved'" in src and "publish requires status" in src
