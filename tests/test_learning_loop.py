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
        # Interruptions are estimated from line spans, and say so.
        assert m["notes"]["interruption_basis"] == "estimated line spans"

    def test_an_interruption_count_is_never_invented_without_a_guest(self):
        from learning import measure

        m = measure({"id": "r"}, "[00:00] Mira: Nobody else is here.\n")
        assert m["interruptions"] is None, (
            "with no guest there is nothing to interrupt; a number would be a guess")


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

    def test_a_short_line_is_only_required_to_exist(self):
        import importlib

        narrate = importlib.import_module("narrate")
        # Seven words in 1.7s is a real read, not a truncation (Sept 12 2026).
        narrate._duration = lambda p: 1.7
        narrate._check_not_truncated(Path("/dev/null"), "That is where we will leave it.")
        narrate._duration = lambda p: 0.05
        with pytest.raises(RuntimeError, match="empty"):
            narrate._check_not_truncated(Path("/dev/null"), "That is where we will leave it.")

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


class TestNoDeadAirBetweenParagraphs:
    """Sept 12 2026: the recorder runs for as long as the paragraph should
    take to say, so a take Mira finishes early ends in silence. Stitched raw,
    that left four to ten second holes between paragraphs — 57 seconds of dead
    air in a two-minute introduction."""

    def test_each_take_is_trimmed_before_stitching(self):
        src = (ROOT / "pipelines" / "voices" / "narrate.py").read_text(encoding="utf-8")
        assert "def _trim(" in src
        assert "silenceremove=start_periods=1" in src
        assert "silenceremove=stop_periods=-1" in src
        assert "parts.append(trimmed)" in src

    def test_the_length_check_runs_on_the_trimmed_take(self):
        src = (ROOT / "pipelines" / "voices" / "narrate.py").read_text(encoding="utf-8")
        i_trim = src.index("trimmed = _trim(part)")
        i_check = src.index("_check_not_truncated(trimmed, para)")
        assert i_trim < i_check, (
            "trailing silence would make a cut-off read look complete")

    def test_the_gap_between_paragraphs_is_the_one_we_choose(self):
        from narrate import BREATH_SEC, KEEP_SILENCE_SEC

        assert 0.2 <= BREATH_SEC <= 0.8
        assert KEEP_SILENCE_SEC < BREATH_SEC


class TestEveryoneOnOneClock:
    """Sept 12 2026 (Hogan Shrum): per-speaker recordings start when that
    person's leg connects, not when the room opened. Merged on their own
    clocks, a guest who joined five minutes late appeared five minutes early
    — Mira looked like she asked her opening question long after he had
    answered it, and the dead-air metric came back as 2035 seconds."""

    def test_offsets_come_from_the_session_trace(self):
        import importlib

        post = importlib.import_module("post_interview")
        run = {"scenario_trace": [
            {"t": "2026-09-12T00:26:57.7Z", "e": "room", "d": "opened (webrtc); mixer"},
            {"t": "2026-09-12T00:26:57.8Z", "e": "leg", "d": "host #1 joined (1 in room)"},
            {"t": "2026-09-12T00:26:58.4Z", "e": "grok", "d": "session updated; agent<->room mix bridged"},
            {"t": "2026-09-12T00:32:11.2Z", "e": "leg", "d": "guest #2 joined (2 in room)"},
            {"t": "2026-09-12T01:07:00.0Z", "e": "leg", "d": "host #3 joined (1 in room)"},
        ]}
        off = post.room_offsets(run)
        assert abs(off["guest"] - 313.5) < 1.0
        assert off["host"] < 1.0
        # A late rejoin must not replace the first join's offset.
        assert off["host"] < 60

    def test_a_run_without_a_trace_degrades_to_zero(self):
        import importlib

        post = importlib.import_module("post_interview")
        assert post.room_offsets({}) == {"guest": 0.0, "host": 0.0, "mira": 0.0}

    def test_the_merge_applies_the_shift(self):
        src = (ROOT / "pipelines" / "voices" / "post_interview.py").read_text(encoding="utf-8")
        assert 'float(seg.get("start", 0.0)) + shift' in src
        assert "offsets=offsets" in src

    def test_both_clean_paths_pass_offsets(self):
        src = (ROOT / "pipelines" / "voices" / "post_interview.py").read_text(encoding="utf-8")
        assert src.count("room_offsets(") >= 3   # definition + three-track + two-track


class TestMetricsMeasureTheRightPerson:
    def test_guest_share_survives_a_label_mismatch(self):
        import importlib

        learning = importlib.import_module("learning")
        transcript = ("[00:00] Mira: One short question for you.\n"
                      "[00:10] GUEST: " + " ".join(["answer"] * 40) + "\n")
        m = learning.measure({"id": "r"}, transcript, host_label="Mira",
                             guest_label="Hogan")   # name the transcript never uses
        assert m["guest_talk_share"] > 0.8, "must still find the guest"

    def test_interruptions_are_counted_now_that_clocks_agree(self):
        import importlib

        learning = importlib.import_module("learning")
        rows = [(0.0, "Hogan", " ".join(["word"] * 40)),   # ~17 s from 0
                (5.0, "Mira", "Sorry, before we move on"),  # lands inside it
                (40.0, "Mira", "And what about the artists?")]
        assert learning.count_interruptions(rows, "Mira", "Hogan") == 1

    def test_no_guest_means_no_number_rather_than_a_wrong_one(self):
        import importlib

        learning = importlib.import_module("learning")
        assert learning.count_interruptions([(0.0, "Mira", "hello")], "Mira", "") is None


class TestHostLegIsNotOverwritten:
    def test_first_host_leg_wins_and_later_ones_are_kept(self):
        body = WORKER[WORKER.index("async function handleLegEvent("):]
        body = body[:body.index("\n}\n") + 3]
        assert "extra_host_record_urls" in body
        assert "if (!run.recording_host_url)" in body


class TestMiraDoesNotRepeatHerself:
    """Sept 12 2026: Mira reaches for one acknowledgment shape — "That's a
    crisp way to put it", "That's a bold direction", "That's a meaningful
    backstop". Three in an episode and she sounds like a form. Each episode
    now retires the reflexes it used, and later interviews are told not to
    reach for them again."""

    def test_formulas_are_collected_and_questions_are_not(self):
        from learning import host_formulas

        rows = [
            (0.0, "Mira", "That's a crisp way to put it. What pulled you in?"),
            (30.0, "Mira", "Good answer."),
            (60.0, "Mira", "What does that look like in practice?"),
            (90.0, "Hogan", "That's a fair question from my side."),
            (120.0, "Mira", "The royalty pays on every generation, including the "
                            "test renders, which is a real cost to carry."),
        ]
        got = [p.lower() for p in host_formulas(rows, "Mira")]
        assert "that's a crisp way to put it" in got
        assert "good answer" in got
        assert not any("what does that look like" in p for p in got), "a question is not a reflex"
        assert not any("royalty" in p for p in got), "substance is not a reflex"
        assert not any("fair question from my side" in p for p in got), "the guest is not the host"

    def test_duplicates_collapse(self):
        from learning import host_formulas

        rows = [(0.0, "Mira", "That's a crisp way to put it."),
                (10.0, "Mira", "that's a crisp way to put it")]
        assert len(host_formulas(rows, "Mira")) == 1

    def test_a_show_with_no_history_reads_exactly_as_before(self):
        import learning

        learning.sb_select = lambda *a, **k: []
        assert learning.variety_block("age_of_ai") == ""

    def test_retired_phrases_reach_the_prompt(self):
        import learning

        learning.sb_select = lambda *a, **k: [{"phrase": "That's a crisp way to put it"}]
        block = learning.variety_block("age_of_ai")
        assert "ALREADY USED ON THIS SHOW" in block
        assert "crisp way to put it" in block
        assert "near-variant" in block

    def test_a_lookup_failure_never_blocks_an_interview(self):
        import learning

        def boom(*a, **k):
            raise RuntimeError("supabase down")

        learning.sb_select = boom
        assert learning.variety_block("age_of_ai") == ""

    def test_both_blocks_are_appended_to_miras_prompt(self):
        assert "lessons_block(show.slug) + variety_block(show.slug)" in FIRE

    def test_post_interview_retires_this_episodes_tics(self):
        assert "save_host_phrases(" in POST
        assert "host_formulas(" in POST

    def test_the_prompt_tells_her_to_vary_her_language(self):
        text = (ROOT / "pipelines" / "voices" / "prompts"
                / "mira_system_prompt.txt").read_text(encoding="utf-8")
        assert "SAY IT A DIFFERENT WAY EVERY TIME" in text
        assert "ALREADY USED ON THIS SHOW" in text
        assert "LET THEM FINISH" in text
        assert "Never read a source aloud" in text
        assert "the interview is over" in text


class TestTheShowDoesNotOpenToAnEmptyChair:
    def test_the_timeout_greets_the_co_host_instead_of_opening(self):
        body = SCENARIO[SCENARIO.index("function maybeOpen()"):]
        body = body[:body.index("\n}\n") + 3]
        assert "greetHostAndWait()" in body
        assert "host only, wait timed out" not in body

    def test_the_greeting_is_not_the_show_opening(self):
        body = SCENARIO[SCENARIO.index("function greetHostAndWait()"):]
        body = body[:body.index("\n}\n") + 3]
        assert "Do NOT open the show" in body
        assert "do not ask any interview questions" in body
        assert "stay silent until" in body

    def test_the_guest_arriving_is_what_opens_the_show(self):
        assert 'if (role === "guest" && !openingFired) maybeOpen();' in SCENARIO


class TestTheEditIsData:
    """Sept 12 2026: both of the first two episodes needed a real edit, and
    both were cut by hand outside the pipeline — unreproducible, unreviewable,
    impossible to undo. The edit now lives in the repo as an EDL."""

    def test_every_edl_names_its_run_and_has_cuts(self):
        import json

        d = ROOT / "pipelines" / "voices" / "edl"
        specs = list(d.glob("*.json"))
        assert specs, "no EDLs on disk"
        for p in specs:
            spec = json.loads(p.read_text(encoding="utf-8"))
            assert spec.get("run_id"), p.name
            assert spec.get("interview_id"), p.name
            assert spec.get("cuts"), p.name
            for cut in spec["cuts"]:
                assert ("from" in cut) ^ ("gap" in cut), f"{p.name}: {cut}"
            # A narration reference requires the slug that resolves it.
            if any(str(c.get("from", "")).startswith("narration:") for c in spec["cuts"]):
                assert spec.get("narration"), p.name

    def test_sources_resolve_from_the_run_row(self):
        import importlib

        mod = importlib.import_module("assemble_edit")
        run = {"recording_guest_url": "https://example/guest.mp3",
               "grok_session_log": {"voximplant_mix_record_url": "https://example/mix.mp3",
                                    "extra_guest_record_urls": ["https://example/g2.mp3"]}}
        show = importlib.import_module("shows").get_show("age_of_ai")
        assert mod._resolve("run:guest", run, show, "") == "https://example/guest.mp3"
        assert mod._resolve("run:mix", run, show, "") == "https://example/mix.mp3"
        assert mod._resolve("run:extra_guest:0", run, show, "") == "https://example/g2.mp3"
        assert mod._resolve("https://example/x.mp3", run, show, "") == "https://example/x.mp3"

    def test_a_missing_source_fails_loudly(self):
        import importlib

        mod = importlib.import_module("assemble_edit")
        show = importlib.import_module("shows").get_show("age_of_ai")
        with pytest.raises(SystemExit, match="not on the run row"):
            mod._resolve("run:host", {"grok_session_log": {}}, show, "")
        with pytest.raises(SystemExit, match="needs a top-level"):
            mod._resolve("narration:intro", {}, show, "")
        with pytest.raises(SystemExit, match="unrecognised source"):
            mod._resolve("guest.mp3", {}, show, "")

    def test_channels_are_named_not_guessed(self):
        import importlib

        mod = importlib.import_module("assemble_edit")
        assert set(mod.CHANNEL_FILTERS) == {"left", "right", "mono"}
        # L is that person's microphone on a Voximplant per-person recording.
        assert mod.CHANNEL_FILTERS["left"] == "pan=mono|c0=c0"

    def test_the_review_pages_are_pointed_at_the_edit(self):
        src = (ROOT / "pipelines" / "voices" / "assemble_edit.py").read_text(encoding="utf-8")
        assert 'tracks["preview"] = url' in src
        assert 'tracks["edit"]' in src

    def test_the_workflow_can_read_and_write_r2(self):
        wf = (ROOT / ".github" / "workflows"
              / "nerra_voices_assemble_edit.yml").read_text(encoding="utf-8")
        assert "R2_ACCESS_KEY_ID: ${{ secrets.R2_ACCESS_KEY_ID }}" in wf
        assert "SUPABASE_SERVICE_KEY: ${{ secrets.VOICES_SUPABASE_SERVICE_KEY }}" in wf
        assert "setup-ffmpeg" in wf
        assert "EDL_SLUG: ${{ inputs.slug }}" in wf
