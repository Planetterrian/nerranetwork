"""Room fixes after Stan Lewis's interview (run c868dac8, Oct 22 2026).

Three faults in one room, all the room's:

1. The closing round began at 34 minutes and never advanced past its first
   question, though he answered and she replied over a hundred times.
   decideTurn() is the only path to roundAnswered(), and a turn the SERVER
   started bypassed it (markTurnStarted resets the flags decideTurn reads).
   Now a server turn after the guest spoke is cancelled and the room decides
   it like any other pause.
2. He took a phone call; she spoke to him and the caller about forty times
   over fifteen minutes, about his personal details, and once said the
   sign-off. Now the room holds: no turns, no time checks, no round prompts,
   nothing counted as an answer, until he turns back to her or three minutes
   pass, when she may say one short line that she is still there.
3. At 46:05 she said "that's the end of the recording" with the round at
   question 1. A sign-off is now cut mid-sentence while the round is
   unfinished, unless the guest asked to stop or the hard cap fired.

Plus the grading rubric (replying to someone else's conversation is a
turn-taking fault) and a way to rehearse a CANDIDATE room before it is
deployed. The behavioural guards drive the real scenario in a node vm
(tests/fixtures/room_sim.js); the rest pin the source.
"""
from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCENARIO_PATH = ROOT / "voximplant" / "scenarios" / "age_of_ai_interview.js"
FIXTURE_PATH = ROOT / "voximplant" / "scenarios" / "age_of_ai_fixture_guest.js"
SCENARIO = SCENARIO_PATH.read_text(encoding="utf-8")
FIXTURE = FIXTURE_PATH.read_text(encoding="utf-8")
SIM = ROOT / "tests" / "fixtures" / "room_sim.js"
RETRO = (ROOT / "pipelines" / "voices" / "prompts" / "editorial_passes"
         / "09_interview_retro.txt").read_text(encoding="utf-8")
WORKER = (ROOT / "workers" / "voices" / "src" / "index.ts").read_text(encoding="utf-8")
REHEARSAL_WF = (ROOT / ".github" / "workflows" / "nerra_voices_rehearsal.yml").read_text(encoding="utf-8")


def _fn(name: str) -> str:
    i = SCENARIO.index(name)
    j = SCENARIO.index("\n}\n", i)
    return SCENARIO[i:j]


def sim(which: str, phrases=None) -> dict:
    env = dict(os.environ)
    if phrases is not None:
        env["ROOM_SIM_PHRASES"] = json.dumps(phrases)
    res = subprocess.run(["node", str(SIM), str(SCENARIO_PATH), which],
                         capture_output=True, text=True, check=True, env=env)
    return json.loads(res.stdout)


def lines(out: dict) -> list:
    return [t["e"] + ": " + t["d"] for t in out["trace"]]


class TestAServerTurnGoesThroughTheDecision:
    def test_the_round_advances_when_the_server_starts_her_reply(self):
        out = sim("server_turns_advance_the_round")
        after = out["afterServerTurn"]
        # The server's turn is cancelled, not spoken.
        assert after["events"][-2:] == ["cancel", "clear"]
        assert after["state"]["serverTurnsRerouted"] == 1
        assert after["state"]["roundIndex"] == 0
        decided = out["afterDecision"]
        # The room's decision counted his answer and handed her question two.
        assert decided["state"]["roundIndex"] == 1
        assert decided["events"][-1] == "create"
        t = lines(out)
        assert "round: answered 1/8" in t
        assert "round: asked 2/8: a book they would recommend" in t
        assert any("the room decides it (#1)" in x for x in t)

    def test_the_source_routes_it(self):
        body = _fn("function markTurnStarted(agent)")
        i = body.index("if (openingFired) {")
        rerouted = body[i:i + 900]
        assert "serverTurnsRerouted += 1;" in rerouted
        assert "scheduleTurnDecision(TURN_DECIDE_MS);" in rerouted
        assert "responseCancel" in rerouted
        # The self-answer rule still runs first: no words, no turn at all.
        assert body.index("if (!spoke && openingFired) {") < i
        # A cancelled turn's words do not move the start of the guest's delta.
        assert "if (who === \"Mira\" && cancelledLinePending) { cancelledLinePending = false; return; }" in SCENARIO

    def test_the_room_reports_it(self):
        body = _fn("async function endRoom(reason)")
        assert "server_turns_rerouted: serverTurnsRerouted" in body
        assert "holds: holdsEntered" in body
        assert '"server_turns_rerouted", "holds", "dead_air_nudges"' in WORKER


class TestHoldMode:
    def test_a_phone_call_holds_her(self):
        out = sim("hold_mode")
        assert out["entered"]["holdMode"] is True
        away = out["whileAway"]
        # A server turn while he was away was cancelled; the room asked for none.
        assert "create" not in away["events"]
        # What he said to the caller never answered the closing question.
        assert away["state"]["roundIndex"] == 0 and away["state"]["roundAwaitingAnswer"]

    def test_one_short_line_after_three_minutes(self):
        out = sim("hold_mode")
        assert out["checkIn"]["events"][-1] == "create"
        # The check-in is that one response's instructions, not a note in her
        # context: as a note (third rehearsal) it came out as "welcome back"
        # and the question again, into a guest still away, and on their
        # return her first line was the check-in again.
        said = out["checkIn"]["instructions"]
        assert "still here whenever they are ready" in said
        assert "no question, no welcome back" in said and "no goodbye" in said
        assert not any("still here" in n for n in out["checkIn"]["notes"])
        # The second rehearsal's note came out as the one word "Silence."
        assert "Nothing else" not in said and "one short, warm sentence" in said
        assert "const HOLD_CHECK_IN_MS = 3 * 60 * 1000;" in SCENARIO

    def test_the_check_in_leaves_nothing_behind(self):
        out = sim("hold_mode")
        # Their return gets an ordinary turn under her own prompt.
        assert out["afterBack"]["instructions"] == ""
        exit_hold = SCENARIO.split("function exitHold(why) {", 1)[1].split("\n}\n", 1)[0]
        assert 'nextTurnInstructions = "";' in exit_hold
        create = SCENARIO.split("turnRequested = true;", 1)[1].split("\n}\n", 1)[0]
        # Oct 23 2026: a guest's feedback steer is the only other source of a
        # turn's instructions, and only when no room turn is parked.
        assert "const instructions = nextTurnInstructions || takeGuestSteer();" in create
        assert "{ response: { instructions: instructions } }" in create
        assert 'nextTurnInstructions = "";' in create

    def test_back_means_the_question_in_play_again(self):
        out = sim("hold_mode")
        assert out["back"]["holdMode"] is False and out["back"]["holdResumeOwed"] is True
        after = out["afterBack"]
        assert after["events"] == ["create"]
        assert after["state"]["roundIndex"] == 0, "the call was never the answer"
        assert any("ask again, in one short line, the closing question" in n for n in after["notes"])
        # The time note that fell inside the hold is delivered after it.
        assert any(n.startswith("[TIME CHECK") for n in after["notes"])

    def test_the_trace_carries_no_guest_words(self):
        out = sim("hold_mode")
        holds = [x for x in lines(out) if x.startswith("hold: ")]
        assert holds[0] == "hold: entered: the guest stepped away"
        assert any(x.startswith("hold: check-in 1 after") for x in holds)
        # Words or speech: in this scenario the guest's return falls in the
        # reply window, and the room hears the speech before the words.
        assert any(x.startswith("hold: left: they") for x in holds)
        joined = " ".join(lines(out)).lower()
        for private in ("delivery", "thursday", "take this call"):
            assert private not in joined

    @pytest.mark.parametrize("text", [
        "Sorry, I have to take this call.",
        "Hang on a second, my phone's ringing.",
        "Give me just a moment.",
        "Bear with me.",
        "I'll be right back.",
        "Excuse me for one second.",
    ])
    def test_stepping_away_is_heard(self, text):
        assert sim("phrases", [text])["phrases"][0]["enter"], text

    @pytest.mark.parametrize("text", [
        "Let me think about that for a second.",
        "Hold on to that thought, because the second part matters.",
        "I'd take that call every time if it came from a customer.",
        "We have to take a moment to look at the numbers.",
    ])
    def test_a_pause_inside_an_answer_is_not_a_hold(self, text):
        assert not sim("phrases", [text])["phrases"][0]["enter"], text

    @pytest.mark.parametrize("text", [
        "Sorry about that. Where were we?",
        "Okay, I'm back.",
        "Mira, thanks for waiting.",
        "Thanks for your patience.",
        # The fourth rehearsal's guest came back on these and was held two
        # and a half minutes more.
        "Back. That was my plumber. Anyway, you were asking what it looked like.",
        "Okay, back. Sorry.",
        "Anyway, as I was saying, the team changed.",
        "Right, your question about the team.",
    ])
    def test_turning_back_is_heard(self, text):
        assert sim("phrases", [text])["phrases"][0]["exit"], text

    @pytest.mark.parametrize("text", [
        "Hey, yeah, I'm here.",
        "No, that's fine. Two o'clock works.",
        "I'll call you back.",
        "Can you do three instead? Text me the address.",
        "Thanks, appreciate it. Talk soon, bye.",
        "He'd come back from the office late.",
    ])
    def test_a_phone_call_does_not_end_the_hold(self, text):
        assert not sim("phrases", [text])["phrases"][0]["exit"], text

    def test_her_saying_she_will_wait_is_a_hold(self):
        out = sim("phrases", ["Of course, I'll wait.", "Take your time with that answer."])
        assert out["phrases"][0]["mira_wait"] and not out["phrases"][1]["mira_wait"]

    def test_everything_that_could_speak_or_prompt_holds(self):
        assert "if (holdMode && !holdCheckInRequested) return;" in _fn("function requestTurn(agent)")
        assert "if (holdMode) { holdPausesSkipped += 1; return; }" in _fn("function decideTurn()")
        assert "if (holdMode) return;" in _fn("function startTimeChecks()")
        assert "if (holdMode) { heldTimeNote = note; return; }" in _fn("function startTimeChecks()")
        assert "if (holdMode) return;" in _fn("function roundReprompt()")
        assert "if (!lastWordAskedAt || lastWordAnswered || holdMode) return;" in _fn("function noteGuestSpoke(ms)")
        assert "if (!holdMode) lastWordAnswered = true;" in _fn("function guestWordsChecks(text)")
        assert "guestWordsChecks(text);" in _fn("function remember(who, text)")
        assert "roundAwaitingAnswer && !holdMode" in _fn("function askRoundLastWord()")
        # The hard cap always ends a hold, and endRoom clears its timer.
        assert 'if (holdMode) exitHold("the hard cap");' in SCENARIO
        assert "roundRepromptTimer, holdTimer].forEach" in _fn("async function endRoom(reason)")


class TestTheHoldEndsWithoutWords:
    """The first candidate rehearsal (Oct 22): the hold began on her line,
    she checked in three times, the guest came back and spoke, and nothing
    left the hold, because the room receives no transcription of the guest
    and every exit read words. It then said nothing more, so the closing
    round never ran. The live path is speech, not text."""

    def test_speech_after_her_check_in_brings_them_back(self):
        out = sim("hold_ends_on_speech")
        assert out["entered"]["holdMode"] is True
        assert out["whileAway"]["events"] == [], "talking to the caller is never a turn"
        assert out["stillHeld"] is True, "speech outside a reply window is not a return"
        assert out["back"]["holdMode"] is False and out["back"]["holdResumeOwed"] is True
        assert out["afterBack"]["events"] == ["create"]
        assert any("ask again, in one short line, the closing question" in n
                   for n in out["afterBack"]["notes"])
        holds = [x["d"] for x in out["trace"] if x["e"] == "hold"]
        assert any(d.startswith("left: they spoke after her check-in") for d in holds)

    def test_the_round_moves_on_after_the_return(self):
        out = sim("hold_ends_on_speech")
        rounds = [x["d"] for x in out["trace"] if x["e"] == "round"]
        # Oct 23 2026: "I'll wait" asked nothing, so the book question is the
        # one in play when they come back; her asking it then is question 2.
        assert any(d.startswith("her turn asked nothing; a book") for d in rounds)
        assert "asked 2/8: a book they would recommend (her own words)" in rounds
        assert "answered 2/8" in rounds and out["afterAnswer"]["roundIndex"] == 2

    def test_she_keeps_checking_in_for_as_long_as_they_are_away(self):
        out = sim("hold_ends_on_speech")
        assert out["checkIns"] == 4
        assert "no more check-ins" not in SCENARIO
        assert "HOLD_MAX_CHECK_INS" not in SCENARIO

    def test_a_cough_or_a_late_word_to_the_caller_is_not_a_return(self):
        out = sim("hold_ignores_a_cough")
        assert out["afterCough"] is True and out["afterLateSpeech"] is True

    def test_the_vad_paths_share_one_speech_handler(self):
        assert SCENARIO.count("noteSpeechEnded(") >= 3   # definition + both VAD paths
        assert "noteHoldSpeech(len)" in _fn("function noteSpeechEnded")
        # The window runs from the end of her check-in line.
        assert "if (holdMode && holdCheckInAt) holdCheckInAt = Date.now();" in SCENARIO


class TestTheRoomHearsTheGuestsWords:
    """The Voximplant session log of the first candidate room: Mira's agent
    received 29 ConversationItemInputAudioTranscriptionCompleted events
    carrying the guest's words, each item re-sent about every second as it
    grew, and the room listened only for an Unknown event. No guest word ever
    reached it, so every rule that reads one had never run live."""

    def test_the_named_event_is_heard(self):
        assert ("agent.addEventListener(Grok.VoiceAgentAPIEvents."
                "ConversationItemInputAudioTranscriptionCompleted") in SCENARIO
        assert "noteGuestTranscript(itemIdOf(ev), textOf(ev));" in SCENARIO

    def test_one_line_per_item_however_many_copies(self):
        out = sim("live_transcription")
        assert out["lines"] == 1
        assert out["lastLine"].startswith("Guest: It taught me")

    def test_the_words_drive_the_hold_and_the_stop(self):
        out = sim("live_transcription")
        assert out["held"] is True and out["stillHeld"] is True
        assert out["back"] is False, "sorry about that, where were we"
        assert out["stop"] is True

    def test_no_guest_words_reach_the_trace(self):
        assert sim("live_transcription")["traceHasNoWords"] is True


class TestDeadAirIsBroken:
    """The second candidate rehearsal (Oct 22): two minutes in, after her
    line, nobody spoke again for twelve minutes. With every unrequested
    server turn cancelled, a silence nobody breaks has no end."""

    def test_she_puts_the_question_again_after_twenty_seconds_twice(self):
        out = sim("dead_air")
        assert out["before"] == [] and out["first"] == ["create"]
        assert out["afterMax"] == [], "two nudges a silence, then the room waits"
        turns = [x["d"] for x in out["trace"] if x["e"] == "turn"]
        assert "dead air continues; no more nudges until someone speaks" in turns
        assert "const DEAD_AIR_MS = 20 * 1000;" in SCENARIO
        assert "const DEAD_AIR_MAX_NUDGES = 2;" in SCENARIO

    def test_speech_resets_the_count(self):
        out = sim("dead_air")
        assert out["afterReset"] == ["create"] and out["nudges"] == 3

    def test_an_empty_room_is_never_nudged(self):
        # Oct 22 candidate rehearsal: after the guest's leg dropped she
        # nudged the empty room twice inside the rejoin grace.
        out = sim("dead_air_empty_room")
        assert "create" not in out["events"]
        assert out["nudges"] == 0

    def test_a_guest_who_starts_talking_is_never_nudged(self):
        out = sim("dead_air_waits_for_a_thinker")
        assert out["nudges"] == 0

    def test_never_in_a_hold_or_the_closing_round(self):
        body = _fn("function deadAirCheck()")
        assert "holdMode" in body and "roundActive" in body and "roundClosed" in body
        assert "cancelDeadAir();" in _fn("function enterHold(why)")
        assert "cancelDeadAir();" in _fn("function noteInboundStart()")

    def test_it_fires_from_the_end_of_her_turn_and_is_reported(self):
        i = SCENARIO.index("agent.addEventListener(Grok.VoiceAgentAPIEvents.ResponseDone, function () {\n        miraSpeaking = false;")
        assert "armDeadAir();" in SCENARIO[i:i + 400]
        assert "dead_air_nudges: deadAirNudgesTotal" in _fn("async function endRoom(reason)")


class TestTheFixtureSurvivesADroppedSocket:
    """The second candidate rehearsal lost its fixture guest to a 1006 two
    minutes in (Voximplant session log) and measured twelve silent minutes."""

    def test_a_closed_socket_reconnects_and_the_beats_run_once(self):
        assert "reconnectFixture();" in FIXTURE
        assert "const FIXTURE_RECONNECTS_MAX = 3;" in FIXTURE
        i = FIXTURE.index("function bridge()")
        body = FIXTURE[i:FIXTURE.index("\n}\n", i)]
        assert "if (beatsScheduled) return;" in body
        assert body.index("if (beatsScheduled) return;") < body.index("scheduleBeats();")
        assert body.index("if (beatsScheduled) return;") < body.index("maxTimer = setTimeout")


class TestNeverCloseBeforeTheRound:
    def test_a_sign_off_is_cut_while_the_round_is_open(self):
        out = sim("sign_off_waits_for_the_round")
        assert out["inRound"]["events"] == ["cancel", "clear"]
        assert "close: cancelled mid-sentence: a sign-off with the closing round at 1/8" in lines(out)

    def test_unless_the_guest_asked_to_stop_or_the_round_closed(self):
        out = sim("sign_off_waits_for_the_round")
        assert out["afterGuestAsked"]["events"] == []
        assert out["afterRoundClosed"]["events"] == []

    def test_the_guest_asking_to_stop_is_heard(self):
        out = sim("guest_stop_is_heard")
        assert out["state"]["guestAskedToStop"] is True
        assert "close: the guest asked to stop" in lines(out)

    def test_the_hard_cap_closes_the_round_and_a_guest_is_never_trapped(self):
        i = SCENARIO.index("hardCapTimer = setTimeout(function () {")
        assert "roundClosed = true;" in SCENARIO[i:i + 900]
        blocked = _fn("function signOffBlockedByRound()")
        assert "if (roundClosed || guestAskedToStop || isHelloSession()) return false;" in blocked
        assert "roundCloseBlocks >= ROUND_CLOSE_BLOCKS_MAX" in blocked
        assert "const ROUND_CLOSE_BLOCKS_MAX = 3;" in SCENARIO

    def test_a_sign_off_the_deltas_missed_is_caught_after(self):
        assert "if (closingPermitted) { catchSignOffBeforeTheRound(text); return; }" in _fn("function catchEarlySignOff(text)")
        body = _fn("function catchSignOffBeforeTheRound(text)")
        assert "signOffBlockedByRound()" in body and "rescueAllowed()" in body
        assert 'startRound("a sign-off came before it");' in body


class TestTheGraderKnowsTheDifference:
    def test_replying_to_someone_elses_conversation_is_a_turn_taking_fault(self):
        assert "A CONVERSATION THAT IS NOT WITH HER." in RETRO
        assert "is a turn-taking fault" in RETRO
        assert "however patient or friendly it" in RETRO
        assert "replying to, or acting on, a conversation the guest is having with someone" in RETRO
        # The rubric names no guest and quotes no line of hers (de-seed by shape).
        block = RETRO[RETRO.index("A CONVERSATION THAT IS NOT WITH HER."):RETRO.index("Transcript (speaker-labelled")]
        assert "Stan" not in block and '"' not in block.replace('"hold"', "")


class TestACandidateRoomIsRehearsedBeforeItShips:
    def test_the_candidate_answers_only_its_own_prefix(self):
        from voximplant.api_clients.voximplant_client import (
            CANDIDATE_ROOM_PREFIX, VoximplantError, candidate_source)
        out = candidate_source(SCENARIO)
        assert f'const ROOM_PREFIX = "{CANDIDATE_ROOM_PREFIX}";' in out
        assert 'const ROOM_PREFIX = "room-";' not in out
        with pytest.raises(VoximplantError):
            candidate_source("no prefix line here")
        with pytest.raises(VoximplantError):
            candidate_source(SCENARIO, "room-")

    def test_it_never_writes_the_live_scenario_or_rule(self):
        from voximplant.api_clients import voximplant_client as vc
        assert vc.CANDIDATE_SCENARIO_NAME != vc.SCENARIO_NAME
        assert vc.CANDIDATE_ROOM_RULE_NAME != vc.ROOM_RULE_NAME
        assert vc.CANDIDATE_ROOM_RULE_PATTERN == r"^candroom-.*"
        i = REHEARSAL_WF.index("Upload this ref's interview scenario as the candidate")
        step = REHEARSAL_WF[i:REHEARSAL_WF.index("- name: Rehearse the current configuration")]
        assert "upload_candidate_scenario()" in step and "ensure_candidate_room_rule()" in step
        assert "upload_scenario(" not in step.replace("upload_candidate_scenario(", "")
        assert "ensure_room_rule(" not in step

    def test_the_fixture_dials_the_candidate_only_when_asked(self):
        assert 'const ROOM_PREFIXES = ["room-", "candroom-"];' in FIXTURE
        assert "if (ROOM_PREFIXES.indexOf(custom.room_prefix) >= 0) ROOM_PREFIX = custom.room_prefix;" in FIXTURE
        from voximplant.api_clients import voximplant_client as vc
        with pytest.raises(vc.VoximplantError):
            vc.start_fixture_guest("r", persona="p", room_prefix="elsewhere-")

    def test_the_harness_can_rehearse_a_call(self, monkeypatch):
        import sys
        sys.path.insert(0, str(ROOT / "pipelines" / "voices"))
        import rehearsal
        kinds = [b["kind"] for b in rehearsal.HOLD_BEATS]
        assert kinds.index("take_call") < kinds.index("end_call")
        assert rehearsal.SCENARIOS == {"deployed": "room-", "candidate": "candroom-"}
        seen = {}
        import voximplant.api_clients.voximplant_client as vc
        monkeypatch.setattr(vc, "start_fixture_guest", lambda run_id, **kw: seen.update(kw) or {})
        rehearsal.start_fixture("run", {"id": "roddy", "name": "Roddy"}, "persona", 10,
                                scenario="candidate", with_hold=True)
        assert seen["room_prefix"] == "candroom-" and seen["beats"] == rehearsal.HOLD_BEATS
        assert "take_call" in FIXTURE and "end_call" in FIXTURE
        assert "candidate_scenario:" in REHEARSAL_WF and "with_hold:" in REHEARSAL_WF


class TestTheScenariosParse:
    @pytest.mark.parametrize("path", [SCENARIO_PATH, FIXTURE_PATH, SIM])
    def test_node_check(self, path):
        subprocess.run(["node", "--check", str(path)], check=True)


class TestTheFixtureFollowsTheRef:
    def test_a_candidate_or_hold_rehearsal_uploads_this_refs_fixture(self):
        # The deployed fixture predates the candidate prefix; without this the
        # proposed arm would quietly dial the live room.
        i = REHEARSAL_WF.index("Upload this ref's fixture guest")
        step = REHEARSAL_WF[i:REHEARSAL_WF.index("- name: Rehearse the current configuration")]
        assert "inputs.candidate_scenario || inputs.with_hold" in step
        assert "upload_fixture_scenario()" in step
        assert REHEARSAL_WF.index("Upload this ref's fixture guest") < REHEARSAL_WF.index("- name: Rehearse the current configuration")


class TestTheRehearsalInstallsFfmpegWithoutApt:
    def test_static_ffmpeg_not_the_apt_mirror(self):
        # Oct 22 2026: three rehearsals died at exit 124 in the apt install
        # before any room ran; test.yml's pinned static build is used instead.
        assert "./.github/actions/setup-ffmpeg" not in REHEARSAL_WF
        assert "BTBN_TAG: autobuild-" in REHEARSAL_WF
        assert "sha256sum -c -" in REHEARSAL_WF
        assert REHEARSAL_WF.index("Add ffmpeg to PATH") < REHEARSAL_WF.index("- name: Rehearse the current configuration")


class TestHerLineEndsWhenItIsHeard:
    """The candidate rehearsal (run 1ca8839a): response.done marks the end of
    GENERATION, and a forty-second line is generated in a few seconds. The
    room read it as the end of her line, gave her another turn and started the
    dead-air clock while she was still talking: the guest heard the welcome
    twice in one 58-second monologue, and the dead-air re-ask counted as her
    answering herself."""

    def test_the_silence_starts_when_her_audio_ends(self):
        out = sim("long_line_dead_air")
        assert "create" not in out["during"]   # 30 s in: still talking + 6 s
        assert "create" in out["after"]
        assert out["nudges"] == 1

    def test_a_turn_waits_for_her_audio(self):
        out = sim("turn_waits_for_her_audio")
        assert "create" not in out["immediately"]
        assert out["pending"] is True
        assert "create" in out["after"]

    def test_a_pause_inside_her_line_gives_no_turn(self):
        out = sim("pause_inside_her_line")
        assert "create" not in out["immediately"]

    def test_cleared_audio_is_silent(self):
        out = sim("cleared_audio_is_silent")
        assert (out["before"], out["after"]) == (True, False)

    def test_every_clear_of_her_audio_marks_her_silent(self):
        assert SCENARIO.count("clearMediaBuffer();") == SCENARIO.count("clearMediaBuffer(); miraSilenced();")

    def test_the_estimate_comes_from_her_spoken_line(self):
        body = SCENARIO[SCENARIO.index("ResponseOutputAudioTranscriptDone,"):]
        body = body[:body.index("});")]
        assert "noteMiraLineSpoken(textOf(ev))" in body
