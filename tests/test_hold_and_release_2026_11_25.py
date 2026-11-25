"""Nov 25 2026: hold and release of Mira's turn.

The server starts a reply of its own at nearly every pause (create_response
is ignored: 13 of 13 turns in the Nov 24 Vincent rehearsal), and the room
cancelled every one and asked again once it had decided, so each reply was
generated twice and the guest waited for the second (turn_gap_ms_median
3,720-3,830 in all four Nov 24 rehearsal rooms). Now the server's turn is
held (muted to the room and her recorder) while the room decides, and an
ordinary turn with nothing to hand her is released instead of regenerated.
Anything else drops it exactly as the room always did.
"""
import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCENARIO_PATH = ROOT / "voximplant" / "scenarios" / "age_of_ai_interview.js"
SCENARIO = SCENARIO_PATH.read_text(encoding="utf-8")
SIM = ROOT / "tests" / "fixtures" / "room_sim.js"


def sim(which: str) -> dict:
    res = subprocess.run(["node", str(SIM), str(SCENARIO_PATH), which],
                         capture_output=True, text=True, check=True)
    return json.loads(res.stdout)


def _fn(name: str) -> str:
    i = SCENARIO.index(name)
    return SCENARIO[i:SCENARIO.index("\n}\n", i)]


class TestAPlainTurnIsReleased:
    def test_the_held_generation_is_the_one_heard(self):
        out = sim("held_plain")
        held = out["whileHeld"]
        assert held["media"] == ["mute"] and held["events"] == []
        assert held["state"]["held"] and not held["state"]["miraSpeaking"]
        decided = out["decided"]
        # Nothing cancelled, nothing generated again: the held reply plays.
        assert decided["events"] == []
        assert decided["media"] == ["mute", "unmute"]
        assert decided["state"]["heldReleased"] == 1 and decided["state"]["miraSpeaking"]
        assert out["doneSwallowed"] is False, "a released turn's done is hers"
        assert any("held turn released (#1)" in t["d"] for t in out["trace"])


class TestAnythingElseIsDroppedAsBefore:
    def test_a_turn_that_carries_a_shape_is_regenerated_with_it(self):
        out = sim("held_shape")
        decided = out["decided"]
        assert decided["events"] == ["cancel", "clear", "create"]
        assert decided["instructions"], "the shape rides on the room's own turn"
        assert decided["state"]["reasons"] == {"the turn carries something for her": 1}

    def test_audio_before_the_decision_drops_it(self):
        out = sim("held_audio_first")
        assert out["decided"]["events"] == ["cancel", "clear", "create"]
        assert out["decided"]["state"]["reasons"] == {"her audio began before the decision": 1}

    def test_the_guest_talking_drops_it_with_no_barge_in_note(self):
        out = sim("held_talked_over")
        assert out["decided"]["events"][:2] == ["cancel", "clear"]
        assert out["decided"]["state"]["reasons"] == {"they kept talking": 1}

    def test_a_dropped_turns_done_is_not_hers(self):
        out = sim("held_shape")
        assert out["doneSwallowed"] is True and out["nextDoneSwallowed"] is False

    def test_off_for_one_room_is_the_old_reroute(self):
        out = sim("held_off")
        assert out["whileHeld"]["events"] == ["cancel", "clear"]
        assert out["whileHeld"]["media"] == []
        assert out["decided"]["state"]["serverTurnsRerouted"] == 1


class TestTheSourceKeepsItsPromises:
    def test_round_hold_goodbye_and_handover_are_never_held(self):
        body = _fn("function markTurnStarted(agent)")
        gate = body[body.index("holdReleaseOn() && !heldTurn"):body.index("holdServerTurn(agent);")]
        for cond in ("!inboundSpeaking", "!holdMode", "!roundActive", "!roundPendingStart",
                     "!closingThanksQueued", "!rotationDue"):
            assert cond in gate, cond

    def test_release_needs_nothing_to_hand_her(self):
        body = _fn("function heldReleasable()")
        for cond in ("nextTurnInstructions", "guestSteer", "researchAsk", "turnShapeOwed",
                     "HOLD_RELEASE_MAX_MS", "guestInRoom()"):
            assert cond in body, cond

    def test_every_path_that_starts_another_turn_drops_the_held_one(self):
        assert 'dropHeld("the room asked for its own turn");' in _fn("function requestTurn(agent)")
        assert 'dropHeld("her audio began before the decision")' in _fn("function noteMiraDelta(event)")
        assert 'dropHeld("session hand-over");' in SCENARIO
        assert 'dropHeld("they kept talking");' in SCENARIO

    def test_the_room_reports_it(self):
        for key in ("server_turns_held: serverTurnsHeld", "held_turns_released: heldReleased",
                    "held_turns_dropped: heldDropped", "held_drop_reasons: heldDropReasons"):
            assert key in SCENARIO, key

    def test_one_switch_per_room(self):
        assert "grok_session_log.hold_release === false" in _fn("function holdReleaseOn()")
