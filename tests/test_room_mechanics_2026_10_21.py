"""The room stops interrupting (Oct 21 2026, review §7.1).

Twenty-three rooms since Sept 10 and the loop could not move the three
faults guests named: she spoke over them, she answered her own questions,
and the session relay cut an answer in half. All three were the ROOM's
mechanics, not the prompt's: the voice API's silence timer started her
turn, a response was generated on an empty turn, the hand-over fired on a
timer, and four paths started her over the guest. These guards pin the
replacements in voximplant/scenarios/age_of_ai_interview.js.
"""
from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCENARIO_PATH = ROOT / "voximplant" / "scenarios" / "age_of_ai_interview.js"
SCENARIO = SCENARIO_PATH.read_text(encoding="utf-8")
CLIENT = (ROOT / "voximplant" / "api_clients" / "voximplant_client.py").read_text(encoding="utf-8")
DEPLOY = (ROOT / ".github" / "workflows" / "nerra_voices_deploy_scenario.yml").read_text(encoding="utf-8")


def _fn(name: str) -> str:
    i = SCENARIO.index(name)
    j = SCENARIO.index("\n}\n", i)
    return SCENARIO[i:j]


class TestEndOfTurnIsADecision:
    def test_the_server_finds_the_pause_and_starts_nothing(self):
        td = _fn("function turnDetection()")
        assert "create_response: tuned.create_response === true" in td
        # The silence timer is not raised again: it was 1,100 -> 1,300 ->
        # 1,800 ms and the Oct 20 room still logged 14 interruptions.
        assert "silence_duration_ms: Number(tuned.silence_duration_ms) || 1100" in td

    def test_the_room_decides_on_the_guests_words(self):
        body = _fn("function decideTurn()")
        assert "if (!spoke && !owed) {" in body, "nobody spoke: she holds"
        assert "guestDelta()" in body
        assert "looksFinished(delta)" in body
        assert "TURN_TRANSCRIPT_WAIT_MS" in body and "TURN_THINK_EXTRA_MS" in body
        assert body.index("if (rotationDue) {") < body.index("requestTurn(grokAgent);")
        assert "const TURN_DECIDE_MS = 500;" in SCENARIO

    def test_an_unfinished_clause_waits_once_more(self):
        fn = _fn("function looksFinished(text)")
        assert "UNFINISHED_TAIL_RE" in fn
        assert "const UNFINISHED_TAIL_RE = /(?:^|\\s)(and|but|so|or|because" in SCENARIO
        assert "if (/[,;:\\-–—]$/.test(t)) return false;" in fn

    def test_speech_stopped_schedules_the_decision(self):
        i = SCENARIO.index("InputAudioBufferSpeechStopped, function () {")
        stopped = SCENARIO[i:i + 700]
        assert "scheduleTurnDecision(TURN_DECIDE_MS);" in stopped
        assert "speechSinceMiraMs += Math.max(0, ms);" in stopped

    def test_a_turn_nobody_asked_for_is_cancelled(self):
        body = _fn("function markTurnStarted(agent)")
        assert "serverTurns += 1;" in body
        assert "if (!spoke && openingFired) {" in body
        assert "selfAnswersBlocked += 1;" in body
        assert "responseCancel" in body and 'type: "response.cancel"' in body
        assert "cancelled a turn nobody had asked for" in body
        # The flags that say "they spoke since her last line" reset per turn.
        assert "guestSpokeSinceMira = false;" in body and "speechSinceMiraMs = 0;" in body


class TestEveryTurnGoesThroughRequestTurn:
    def test_request_turn_never_starts_over_the_guest(self):
        body = _fn("function requestTurn(agent)")
        assert "if (miraSpeaking) { pendingTurn = true; return; }" in body
        assert "if (inboundSpeaking) { pendingTurn = true; return; }" in body
        assert "turnRequested = true;" in body

    def test_the_only_direct_response_create_is_hers(self):
        # requestTurn, and the narration take (a session with no guest in it).
        assert SCENARIO.count("responseCreate({})") == 2
        for fn in ("function openWhenReady(reason)", "function resumeForGuest()",
                   "function silentMicNudge(attempt)", "function greetGuestAndWait()",
                   "function greetHostAndWait()", "async function onToolCall(event)"):
            body = _fn(fn)
            assert "requestTurn(" in body, fn
            assert "responseCreate" not in body, fn

    def test_the_new_session_owes_no_first_line(self):
        i = SCENARIO.index("session \" + generation + \" bridged — resuming the interview")
        bridged = SCENARIO[i:i + 600]
        assert "if (handoverTurnOwed) {" in bridged
        assert "responseCreate" not in bridged


class TestSheNeverSpeaksFirstOnJoin:
    def test_three_seconds_or_their_first_words(self):
        assert "const GUEST_SETTLE_MS = 3 * 1000;" in SCENARIO
        body = _fn("function maybeOpen()")
        # The co-host hold no longer greets the guest the instant they join.
        assert "openingTimer = setTimeout(function () { openingTimer = null; greetGuestAndWait(); }, GUEST_SETTLE_MS);" in body
        assert body.index("if (waitingForCohost())") < body.index("greetGuestAndWait()")

    def test_their_first_words_open_her_mouth_in_every_mode(self):
        body = _fn("function openAfterGuestSpoke()")
        assert "if (waitingForCohost()) { greetGuestAndWait(); return; }" in body
        assert 'openWhenReady("guest spoke first");' in body
        i = SCENARIO.index("InputAudioBufferSpeechStopped, function () {")
        assert "if (!openingFired) { setTimeout(openAfterGuestSpoke, TURN_DECIDE_MS); return; }" in SCENARIO[i:i + 700]


class TestTheHandoverHappensAtAPause:
    def test_due_then_performed_at_a_pause(self):
        armed = _fn("function armRotation()")
        assert "rotationDue = true;" in armed
        assert "ROTATE_FORCE_MS" in armed
        assert "handoverTurnOwed = miraSpeaking;" in armed, "a forced hand-over mid-sentence owes the thought"
        assert "const ROTATE_AFTER_MS_DEFAULT = Math.max(2, GROK_SESSION_MAX_MIN - 6) * 60 * 1000;" in SCENARIO
        assert "const ROTATE_FORCE_MS = Math.max(3, GROK_SESSION_MAX_MIN - 1.5) * 60 * 1000;" in SCENARIO

    def test_the_whole_transcript_rides_along(self):
        assert "const HANDOVER_TURNS = 200;" in SCENARIO
        assert "if (transcript.length > 200)" in _fn("function remember(who, text)")
        note = _fn("function handoverNote()")
        assert "sorry, go on" not in note, "no quoted specimen line in a note she reads"

    def test_a_recovery_replies_only_if_they_spoke(self):
        body = _fn("async function recoverAgent(reason)")
        assert "handoverTurnOwed = guestSpokeSinceMira || hostSpokeSinceMira;" in body
        assert body.index("handoverTurnOwed = ") < body.index("await createAgent(note)")


class TestTheCoHostIsNotTheGuest:
    def test_per_leg_mic_state_is_read(self):
        body = _fn("function admitLeg(call, role)")
        assert "call.handleMicStatus(true);" in body
        assert "CallEvents.MicStatusChange" in body
        assert "guestMicActive = legs.filter" in body and "hostMicActive = legs.filter" in body

    def test_a_host_only_voice_is_not_a_barge_in(self):
        start = _fn("function noteInboundStart()")
        assert "const hostOnly = micStatusSeen && guestMicActive === 0 && hostMicActive > 0;" in start
        assert "if (hostOnly) hostSpokeSinceMira = true; else guestSpokeSinceMira = true;" in start
        i = SCENARIO.index("InputAudioBufferSpeechStarted, function () {")
        started = SCENARIO[i:i + 1400]
        assert "const hostOnly = noteInboundStart();" in started
        assert started.index("if (hostOnly) {") < started.index("agent.clearMediaBuffer();")


class TestTheSignOffIsCaughtBeforeItIsSaid:
    def test_the_deltas_are_read(self):
        assert 'raw.indexOf("audio_transcript.delta") >= 0' in SCENARIO
        assert "ResponseOutputAudioTranscriptDelta" in SCENARIO
        assert SCENARIO.count("catchEarlyCloseOnDelta(currentResponseText)") == 2

    def test_a_close_before_the_window_is_cancelled_mid_sentence(self):
        body = _fn("function catchEarlyCloseOnDelta(textSoFar)")
        assert "SIGN_OFF_RE.test(t) && closingOnAnUnansweredQuestion()" in body
        assert "elapsedMin() < closingOpensAtMin() - 1" in body
        assert "responseCancelledEarly = true;" in body
        assert "responseCancel" in body
        assert 'trace("close", "cancelled mid-sentence: " + why);' in body
        # The after-the-fact catchers do not fire a second rescue on the same sentence.
        assert "if (responseCancelledEarly) return;" in _fn("function catchEarlySignOff(text)")
        assert "if (responseCancelledEarly) return;" in _fn("function catchEarlyClosingRound(text)")


class TestTheClosingRoundIsAStateMachine:
    def test_the_room_hands_her_one_question_at_a_time(self):
        ask = _fn("function askNextRoundQuestion()")
        assert "roundAsked[ROUND_QUESTIONS[next][0]] !== undefined" in ask, "a question she asked herself is skipped"
        assert "roundAwaitingAnswer = true;" in ask
        assert 'trace("round", "asked " + (next + 1) + "/" + ROUND_QUESTIONS.length + ": " + entry[0]);' in ask
        assert "ask ONLY this, in your own words" in ask
        assert "requestTurn(grokAgent);" in ask

    def test_the_guests_finished_answer_advances_it(self):
        decide = _fn("function decideTurn()")
        assert "if (roundActive && roundAwaitingAnswer && spoke) {" in decide
        assert "roundAnswered();" in decide
        answered = _fn("function roundAnswered()")
        assert 'trace("round", "answered " + (roundIndex + 1) + "/" + ROUND_QUESTIONS.length);' in answered
        assert "askNextRoundQuestion();" in answered

    def test_the_round_begins_when_required_and_ends_on_the_last_word(self):
        checks = _fn("function startTimeChecks()")
        assert "roundPendingStart = !roundActive && !roundClosed;" in checks
        assert "room will hand you each closing question" in checks
        assert "if (roundPendingStart && spoke) {" in _fn("function decideTurn()")
        last = _fn("function askRoundLastWord()")
        assert "hand them the last word" in last
        close = _fn("function closeRound()")
        assert "roundClosed = true;" in close and "lastWordAnswered = true;" in close
        assert "that's the end of the recording" in close

    def test_a_question_she_asks_herself_once_permitted_hands_the_round_to_the_room(self):
        body = _fn("function noteRoundQuestion(text)")
        assert "startRound(\"she began it with \" + label, ROUND_QUESTIONS.indexOf(q));" in body
        start = _fn("function startRound(why, askedIndex)")
        assert "if (askedIndex >= 0) {" in start and "roundAwaitingAnswer = true;" in start

    def test_a_closing_session_runs_the_round_from_its_first_answer(self):
        assert "if (isClosingSession()) roundPendingStart = true;" in _fn("function openWhenReady(reason)")

    def test_the_end_of_room_report_carries_the_rooms_own_numbers(self):
        body = _fn("async function endRoom(reason)")
        for key in ("barge_ins: bargeIns", "server_turns: serverTurns",
                    "self_answers_blocked: selfAnswersBlocked",
                    "closing_round_complete: roundClosed",
                    "closing_questions_asked: Object.keys(roundAsked).length"):
            assert key in body, key
        assert "turnDecisionTimer" in body and "roundRepromptTimer" in body and "rotateForceTimer" in body


class TestReasoningEffortComesFromTheRunRow:
    def test_default_high_and_four_values(self):
        fn = _fn("function reasoningEffort()")
        assert "config.reasoning_effort" in fn
        assert '(raw === "none" || raw === "low" || raw === "medium" || raw === "high") ? raw : "high"' in fn
        assert "reasoning: { effort: reasoningEffort() }" in SCENARIO


class TestRequestsToTheWorkerAreSigned:
    def test_every_room_request_carries_the_header(self):
        assert 'const WEBHOOK_SECRET = "__VOICES_WEBHOOK_SECRET__";' in SCENARIO
        for fn in ("function postLegEvent(role, event)", "function postSilenceAlert(seconds)",
                   "async function fireWebhook(payload)"):
            assert "signedHeaders(" in _fn(fn), fn
        assert "headers: signedHeaders(takeBody)" in SCENARIO
        sh = _fn("function signedHeaders(body)")
        assert 'if (WEBHOOK_SECRET && WEBHOOK_SECRET.indexOf("__") !== 0)' in sh
        assert '"X-Voices-Signature: " + hmacSha256Hex(WEBHOOK_SECRET, body)' in sh

    def test_the_hmac_matches_the_standard_vectors(self):
        """RFC 4231-style check of the hand-written SHA-256 under node."""
        src = SCENARIO
        start = src.index("function utf8Bytes")
        end = src.index("function getSecret(name)")
        script = (
            "const Logger={write(){}}; let runId='t'; const WEBHOOK_SECRET='x';\n"
            + src[start:end]
            + "\nconst out = {"
            "fox: hmacSha256Hex('key', 'The quick brown fox jumps over the lazy dog'),"
            "abc: sha256Bytes(utf8Bytes('abc')).map(b=>(b<16?'0':'')+b.toString(16)).join(''),"
            "empty: hmacSha256Hex('', ''),"
            "longkey: hmacSha256Hex('k'.repeat(100), 'body'),"
            "utf8: sha256Bytes(utf8Bytes('Мира')).length};"
            "console.log(JSON.stringify(out));"
        )
        res = subprocess.run(["node", "-e", script], capture_output=True, text=True, check=True)
        out = json.loads(res.stdout.strip())
        assert out["fox"] == "f7bc83f430538424b13298e6aa6fb143ef4d59a14946175997479dbc2d1a3cd8"
        assert out["abc"] == "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad"
        assert out["empty"] == "b613679a0814d9ec772f95d778c35fc5ff1697c493715653c6c712144292c5ad"
        import hashlib, hmac
        assert out["longkey"] == hmac.new(b"k" * 100, b"body", hashlib.sha256).hexdigest()
        assert out["utf8"] == 32

    def test_the_deploy_substitutes_the_secret_when_set(self):
        assert '"__VOICES_WEBHOOK_SECRET__"' in CLIENT
        assert 'os.environ.get("VOICES_WEBHOOK_SECRET", "")' in CLIENT
        assert "VOICES_WEBHOOK_SECRET: ${{ secrets.VOICES_WEBHOOK_SECRET }}" in DEPLOY

    def test_the_scenario_parses(self):
        subprocess.run(["node", "--check", str(SCENARIO_PATH)], check=True)
