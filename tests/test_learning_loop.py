"""The show improves on purpose (Sept 10 2026).

After the Matt Davis interview: every episode now leaves behind measurable
craft metrics and a set of PROPOSED standing instructions for Mira. Proposals
reach Mira only when a human promotes them at gate 1 — a host that edits its
own instructions unsupervised drifts, and the drift is invisible until an
episode is bad.

Also pins the two failures that split that interview in half: a dropped Grok
socket now rescues in place instead of ending the room, and a rejoin no longer
overwrites the first half's browser recording.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "pipelines" / "voices"))

WORKER = (ROOT / "workers" / "voices" / "src" / "index.ts").read_text(encoding="utf-8")
SCENARIO = (ROOT / "voximplant" / "scenarios" / "age_of_ai_interview.js").read_text(encoding="utf-8")
STUDIO = (ROOT / "age-of-ai-studio.html").read_text(encoding="utf-8")
FIRE = (ROOT / "pipelines" / "voices" / "fire_interviews.py").read_text(encoding="utf-8")
POST = (ROOT / "pipelines" / "voices" / "post_interview.py").read_text(encoding="utf-8")
RETRO = (ROOT / "pipelines" / "voices" / "prompts" / "editorial_passes"
         / "09_interview_retro.txt").read_text(encoding="utf-8")

TRANSCRIPT = """\
[00:00] Mira: Welcome. Where are you calling from today, and what brought you to this work?
[00:20] Matt: Dallas. I run a delivery firm that replaced offshore teams with agents.
[01:30] Mira: How does your five day workshop actually run?
[01:40] Matt: We ingest their artifacts, interview stakeholders, and build a prototype.
[09:00] Mira: Where are you calling from today, and what brought you to this work?
[09:10] Matt: I mentioned Dallas earlier.
"""


class TestMetrics:
    def test_parses_labelled_lines(self):
        from learning import parse_transcript

        rows = parse_transcript(TRANSCRIPT)
        assert len(rows) == 6
        assert rows[0][0] == 0 and rows[0][1] == "Mira"
        assert rows[2][0] == 90

    def test_catches_a_question_asked_twice(self):
        from learning import count_repeated_questions

        host = [t for _, s, t in __import__("learning").parse_transcript(TRANSCRIPT)
                if s == "Mira"]
        assert count_repeated_questions(host) == 1

    def test_a_clean_interview_scores_zero_repeats(self):
        from learning import count_repeated_questions

        assert count_repeated_questions([
            "What does the workshop look like?",
            "Who reviews the agents' output before it ships?",
        ]) == 0

    def test_measure_reports_talk_share_and_session_history(self):
        from learning import measure

        run = {"id": "r1", "duration_sec": 600, "scenario_trace": [
            {"e": "grok", "d": "session 2 bridged — resuming the interview"},
            {"e": "grok", "d": "connection dropped code 1006"},
        ]}
        m = measure(run, TRANSCRIPT, host_label="Mira", guest_label="Matt")
        assert 0 < m["guest_talk_share"] < 1
        assert m["mira_turns"] == 3
        assert m["repeated_questions"] == 1
        assert m["agent_sessions"] == 2 and m["drops"] == 1
        # Talk share is words, and says so rather than pretending to be seconds.
        assert m["notes"]["talk_share_basis"] == "words"
        assert m["interruptions"] is None

    def test_metrics_never_invent_an_interruption_count(self):
        from learning import measure

        m = measure({"id": "r"}, TRANSCRIPT)
        assert m["interruptions"] is None, (
            "the transcript has no segment end times; a number here would be a guess")


class TestLessonsReachMiraOnlyViaAHuman:
    def test_proposals_are_stored_as_proposed(self):
        import learning

        seen = []
        learning.sb_insert = lambda table, row: seen.append((table, row)) or row
        n = learning.save_proposed_lessons("age_of_ai", "iv1", [
            {"category": "questions", "lesson": "Ask one question at a time and stop talking.",
             "evidence": "[09:00] repeated the opener"},
            {"category": "nonsense", "lesson": "Keep the close under a minute."},
            {"category": "pacing", "lesson": "   "},          # dropped
            "not a dict",                                      # dropped
        ])
        assert n == 2
        assert all(r["status"] == "proposed" for _, r in seen)
        assert seen[1][1]["category"] == "other"

    def test_block_is_empty_until_something_is_promoted(self):
        import learning

        learning.sb_select = lambda *a, **k: []
        assert learning.lessons_block("age_of_ai") == ""

    def test_block_carries_active_lessons_into_the_prompt(self):
        import learning

        learning.sb_select = lambda *a, **k: [
            {"lesson": "Ask one question at a time and stop talking."}]
        block = learning.lessons_block("age_of_ai")
        assert "Ask one question at a time" in block
        assert "EARLIER INTERVIEWS" in block

    def test_a_lookup_failure_never_blocks_an_interview(self):
        import learning

        def boom(*a, **k):
            raise RuntimeError("supabase down")

        learning.sb_select = boom
        assert learning.lessons_block("age_of_ai") == ""

    def test_fire_appends_the_block_to_miras_prompt(self):
        assert "+ lessons_block(show.slug)" in FIRE

    def test_post_interview_measures_and_proposes_without_blocking(self):
        assert "09_interview_retro.txt" in POST
        assert "save_proposed_lessons(" in POST and "save_metrics(" in POST
        block = POST[POST.index("# Learning loop"):]
        block = block[:block.index('if package.get("topical_show_fits")')]
        assert "except Exception:" in block

    def test_retro_prompt_judges_the_host_not_the_guest(self):
        assert "Judge the HOST, not the guest" in RETRO
        assert "Ignore anything caused by infrastructure" in RETRO
        assert "An empty array is a correct answer" in RETRO

    def test_worker_gates_promotion_on_the_package_token(self):
        body = WORKER[WORKER.index("async function handleLessonDecision("):]
        body = body[:body.index("\n// -- Gate 2")]
        assert "requirePackageAccess(req, env, String(body?.package_id ?? \"\"))" in body
        assert '["active", "retired"].includes(status)' in body
        assert '"/voices/lesson-decision"' in WORKER


class TestDroppedSocketDoesNotEndTheInterview:
    def test_a_drop_is_rescued_before_the_room_is_ended(self):
        drop = SCENARIO[SCENARIO.index("function onGrokDropped("):]
        drop = drop[:drop.index("\n}\n") + 3]
        assert "recoverAgent(" in drop
        assert drop.index("recoverAgent(") < drop.index('endRoom("grok_dropped")')

    def test_the_rescue_carries_the_conversation_and_rearms_rotation(self):
        body = SCENARIO[SCENARIO.index("async function recoverAgent("):]
        body = body[:body.index("\n}\n") + 3]
        assert "handoverNote()" in body
        assert "createAgent(note)" in body
        assert "armRotation()" in body

    def test_rescues_are_bounded(self):
        assert "GROK_MAX_RECOVERIES" in SCENARIO
        assert "grokRecoveries < GROK_MAX_RECOVERIES" in SCENARIO
        assert "gave up after" in SCENARIO


class TestARejoinNeverOverwritesTheFirstHalf:
    def test_studio_mints_a_take_id_per_join(self):
        assert "rec.sid = (Date.now().toString(36)" in STUDIO
        assert '"&sid=" + encodeURIComponent(rec.sid)' in STUDIO
        assert "sid: rec.sid || null," in STUDIO

    def test_worker_keys_chunks_and_manifest_under_the_take(self):
        key = WORKER[WORKER.index("function localKey("):]
        key = key[:key.index("\n}\n") + 3]
        assert "const take = sid ? `${sid}/` : \"\";" in key
        assert '`${String(seq).padStart(5, "0")}.webm`, sid)' in WORKER
        assert '"manifest.json", sid)' in WORKER

    def test_every_take_is_recorded_not_just_the_last(self):
        assert "local_takes" in WORKER
        # The single-manifest column stays, so the pipeline keeps working.
        assert "[`local_${gate.role}_url`]: manifestKey" in WORKER

    def test_old_clients_without_a_take_id_keep_the_flat_layout(self):
        key = WORKER[WORKER.index("function localKey("):]
        key = key[:key.index("\n}\n") + 3]
        assert 'sid ? `${sid}/` : ""' in key


class TestMiraReadsHerOwnPickups:
    """Sept 11 2026: narration used xAI's text-to-speech while the interview
    is the Speech-to-Speech agent. Two engines, two voices, one show — so a
    pickup is now read by the same agent that hosts the interview."""

    def test_scenario_has_a_narration_mode_that_records_the_agent(self):
        assert "if (custom.narrate) return narrationSession(custom);" in SCENARIO
        body = SCENARIO[SCENARIO.index("async function narrationSession("):]
        body = body[:body.index("\n}\n") + 3]
        assert "createVoiceAgentAPIClient" in body
        assert "agent.sendMediaTo(recorder)" in body
        assert "voice: preset," in body
        assert "turn_detection: null" in body

    def test_the_read_is_verbatim_and_unhosted(self):
        body = SCENARIO[SCENARIO.index("async function narrationSession("):]
        body = body[:body.index("\n}\n") + 3]
        assert "word for word" in body
        assert "Do not greet" in body

    def test_a_take_cannot_outlive_the_session_limit(self):
        body = SCENARIO[SCENARIO.index("async function narrationSession("):]
        body = body[:body.index("\n}\n") + 3]
        assert "52 * 1000" in body, "must report before Voximplant's 60 s cut-off"

    def test_paragraphs_are_split_to_fit_one_session(self):
        from narrate import PARAGRAPH_MAX_CHARS, paragraphs

        text = "One short opener.\n\n" + ("A sentence that keeps going. " * 60)
        parts = paragraphs(text)
        assert parts[0] == "One short opener."
        assert len(parts) > 2
        assert all(len(p) <= PARAGRAPH_MAX_CHARS for p in parts)

    def test_empty_and_whitespace_blocks_are_dropped(self):
        from narrate import paragraphs

        assert paragraphs("\n\n   \n\nHello.\n\n\n") == ["Hello."]

    def test_agent_is_the_default_engine(self):
        src = (ROOT / "pipelines" / "voices" / "narrate.py").read_text(encoding="utf-8")
        assert 'os.environ.get("NARRATION_ENGINE", "agent")' in src
        assert "will NOT match the" in src, "the tts fallback must warn"

    def test_worker_attaches_a_take_recording(self):
        body = WORKER[WORKER.index("async function handleNarrationTake("):]
        body = body[:body.index("\n// -- Gate 2")]
        assert "narration_takes?take_id=eq." in body
        assert '"take not found" }, 404' in body
        assert '"/voices/narration-take"' in WORKER


class TestNarrationPickup:
    """Hand-written narration (Sept 11 2026): an episode sometimes needs a
    proper introduction or a clean close, written and reviewed as words
    rather than produced as a side effect of a production run."""

    def test_spec_files_are_well_formed(self):
        import json

        d = ROOT / "pipelines" / "voices" / "narration"
        specs = list(d.glob("*.json"))
        assert specs, "no narration specs on disk"
        for p in specs:
            spec = json.loads(p.read_text(encoding="utf-8"))
            assert spec.get("segments"), p.name
            for seg in spec["segments"]:
                assert seg.get("id") and seg.get("text", "").strip(), p.name

    def test_narrate_uploads_one_file_per_segment(self):
        src = (ROOT / "pipelines" / "voices" / "narrate.py").read_text(encoding="utf-8")
        assert 'show.r2_key("narration", slug, f"{seg_id}.mp3")' in src
        assert "_stitch(parts," in src

    def test_workflow_supplies_the_voice_key_and_bucket(self):
        wf = (ROOT / ".github" / "workflows"
              / "nerra_voices_narrate.yml").read_text(encoding="utf-8")
        assert "GROK_API_KEY: ${{ secrets.GROK_API_KEY }}" in wf
        assert "R2_ACCESS_KEY_ID: ${{ secrets.R2_ACCESS_KEY_ID }}" in wf
        assert "NARRATION_SLUG: ${{ inputs.slug }}" in wf
        # The agent path starts Voximplant sessions and polls Supabase.
        assert "VOXIMPLANT_API_KEY: ${{ secrets.VOXIMPLANT_API_KEY }}" in wf
        assert "SUPABASE_SERVICE_KEY: ${{ secrets.VOICES_SUPABASE_SERVICE_KEY }}" in wf


class TestVoiceRoster:
    """xAI's Speech-to-Speech and Text-to-Speech APIs share one voice roster
    and both take the LOWERCASE voice id. Title-casing it (Sept 2026) meant
    "Ara" matched nothing and every interview fell back to the default voice,
    so the live host and the narration were two different people."""

    def test_scenario_sends_a_lowercase_voice_id(self):
        assert 'voice: preset,' in SCENARIO
        assert "toUpperCase() + preset.slice(1)" not in SCENARIO
        assert '.trim().toLowerCase()' in SCENARIO

    def test_a_spec_can_pin_its_own_voice(self):
        src = (ROOT / "pipelines" / "voices" / "narrate.py").read_text(encoding="utf-8")
        assert 'spec.get("voice")' in src
        assert '.strip().lower()' in src
        assert "voice=voice" in src, "the pinned voice must reach the take"


class TestNarrationEntryOrdering:
    def test_a_take_is_recognised_before_the_run_id_guard(self):
        entry = SCENARIO[SCENARIO.index("VoxEngine.addEventListener(AppEvents.Started"):]
        entry = entry[:entry.index("});")]
        narrate = entry.index("custom.narrate")
        guard = entry.index("if (!custom.run_id) return;")
        assert narrate < guard, (
            "a narration take has no interview and therefore no run_id; if the "
            "guard runs first the session silently does nothing")


class TestATakeIsNotCutOff:
    """Sept 11 2026: ResponseDone fires while Mira is still speaking, so the
    recorder stopped after roughly the first sentence of every paragraph and
    the episode shipped a mangled introduction."""

    def test_the_recorder_runs_for_the_length_of_the_script(self):
        body = SCENARIO[SCENARIO.index("async function narrationSession("):]
        body = body[:body.index("\n}\n") + 3]
        assert "expectedMs" in body
        assert "setTimeout(function () { report(\"ok\"" in body

    def test_response_done_is_not_a_stop_signal(self):
        body = SCENARIO[SCENARIO.index("async function narrationSession("):]
        body = body[:body.index("\n}\n") + 3]
        rd = body[body.index("ResponseDone, function"):]
        assert "report(" not in rd[:400], "ResponseDone must not end the take"
        assert "still recording" in rd[:400]

    def test_the_read_stops_before_the_session_does(self):
        body = SCENARIO[SCENARIO.index("async function narrationSession("):]
        body = body[:body.index("\n}\n") + 3]
        assert "Math.min(44000" in body
        assert "52 * 1000" in body

    def test_a_short_take_fails_instead_of_shipping(self):
        import importlib

        narrate = importlib.import_module("narrate")
        text = " ".join(["word"] * 60)          # ~25 s of speech
        narrate._duration = lambda p: 4.0        # what a cut-off take looks like
        with pytest.raises(RuntimeError, match="cut off"):
            narrate._check_not_truncated(Path("/dev/null"), text)

    def test_a_full_take_passes(self):
        import importlib

        narrate = importlib.import_module("narrate")
        text = " ".join(["word"] * 60)
        narrate._duration = lambda p: 24.0
        narrate._check_not_truncated(Path("/dev/null"), text)

    def test_paragraphs_are_short_enough_to_say_in_one_session(self):
        from narrate import PARAGRAPH_MAX_CHARS, WORDS_PER_SEC

        worst_case_sec = (PARAGRAPH_MAX_CHARS / 5) / WORDS_PER_SEC
        assert worst_case_sec < 45, "a paragraph must be SAID inside the session limit"
