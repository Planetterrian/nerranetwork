"""Nov 25 2026: the room times the wait before Mira's reply (measuring only).

Hold-and-release (rehearsed Nov 25) could not work: the server's own reply
streams audio within milliseconds of starting, so a muted hold loses it. And
reasoning effort "low" made the gap longer, not shorter. Before another room
change, the room records where the wait goes: VAD stop -> guest transcript ->
the room's request -> her first words, as medians in
grok_session_log.turn_timing.
"""
from pathlib import Path

SCENARIO = Path("voximplant/scenarios/age_of_ai_interview.js").read_text(encoding="utf-8")


def _fn(name):
    body = SCENARIO[SCENARIO.index("function " + name + "("):]
    return body[:body.index("\n}\n")]


def test_the_clock_starts_at_the_vad_stop():
    i = SCENARIO.index("InputAudioBufferSpeechStopped, function () {")
    handler = SCENARIO[i:i + 600]
    assert "turnClock = { stopped: Date.now(), transcript: 0, requested: 0, path: [] };" in handler


def test_each_leg_is_stamped_where_it_happens():
    assert "if (turnClock.stopped && !turnClock.transcript) turnClock.transcript = Date.now();" in _fn("noteGuestTranscript")
    req = _fn("requestTurn")
    assert "if (turnClock.stopped && !turnClock.requested) turnClock.requested = Date.now();\n  agent.responseCreate(body);" in req
    assert "if (!currentResponseText) clockTurnFirstWords();" in _fn("noteMiraDelta")


def test_only_a_requested_turn_is_timed_and_it_is_bounded():
    body = _fn("clockTurnFirstWords")
    assert "if (!turnClock.requested || !turnClock.stopped) return;" in body
    assert "turnTimings.length < TURN_TIMINGS_MAX" in body


def test_the_summary_reaches_the_session_log_and_changes_no_turn():
    assert "turn_timing: turnTimingSummary()," in SCENARIO
    for name in ("clockTurnFirstWords", "turnTimingSummary", "medianOf"):
        body = _fn(name)
        for call in ("responseCreate", "responseCancel", "requestTurn(", "scheduleTurnDecision"):
            assert call not in body


def test_the_summary_also_rides_the_stored_trace():
    # The Voices Worker keeps only its own counters (roomCountersOf), so the
    # end of the room writes the timing as one trace line too.
    end = SCENARIO[SCENARIO.index("async function endRoom("):]
    end = end[:end.index("await fireWebhook(")]
    assert 'trace("turn", "timing: "' in end


class TestTheWordsEndTheWait:
    """Timed in rehearsal (Nov 25): the guest transcript landed a median 597 ms
    after the VAD stop, just past TURN_DECIDE_MS (500), so about half her
    replies waited the whole TURN_TRANSCRIPT_WAIT_MS. The wait for words now
    ends when they land; the 1,500 ms timer stays the ceiling."""

    def test_the_wait_is_marked_only_while_its_timer_is_pending(self):
        decide = _fn("decideTurn")
        assert decide.index("turnWaitingForWords = false;") < decide.index("const owed = pendingTurn;")
        assert ("scheduleTurnDecision(TURN_TRANSCRIPT_WAIT_MS);\n    turnWaitingForWords = true;") in decide
        assert "turnWaitingForWords = false;" in _fn("cancelTurnDecision")

    def test_landed_words_bring_the_decision_forward_never_over_the_guest(self):
        body = _fn("noteGuestTranscript")
        assert "if (turnWaitingForWords && turnDecisionTimer && !inboundSpeaking) {" in body
        assert "scheduleTurnDecision(TURN_WORDS_LANDED_MS);" in body
        assert "const TURN_WORDS_LANDED_MS = 100;" in SCENARIO
        assert "const TURN_TRANSCRIPT_WAIT_MS = 1500;" in SCENARIO

    def test_the_count_rides_the_timing_line(self):
        assert '" decided when the words landed"' in SCENARIO


def test_each_reply_traces_the_waits_it_went_through():
    """Nov 25 2026: the words-landed change moved the request median by ~0-120 ms,
    so each reply's waits are traced (bounded) to find where the rest goes."""
    assert "turnClock.path.push(" in _fn("scheduleTurnDecision")
    assert 'trace("turn", "path: request "' in _fn("clockTurnFirstWords")
    assert "TURN_PATH_TRACES_MAX = 40" in SCENARIO
