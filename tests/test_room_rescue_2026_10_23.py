"""A rescued session runs the dead-air clock (Oct 23 2026).

The three-rooms-per-arm rehearsal of the hold fixes (run 39879256504) lost
one proposed room at 3:42: Mira's socket dropped with code 1006 just after
one of her lines, the rescue bridged a fresh session, and neither side
spoke again until the fixture guest's timer ended the room eight minutes
later. The dead-air clock was armed only when one of her lines ended, so a
session that had not spoken yet never had one. Driven through the real
scenario by tests/fixtures/room_sim.js.
"""
from __future__ import annotations

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


class TestARescuedRoomIsNeverSilentForever:
    def test_twenty_seconds_of_silence_after_a_rescue_gets_her_question_again(self):
        out = sim("dead_air_after_rescue")
        assert out["before"] == []                 # nothing inside the twenty seconds
        assert out["after"] == ["create"]          # then one line from her
        assert "put your last question to them again" in out["nudgeNote"]

    def test_a_guest_who_spoke_before_the_drop_is_answered(self):
        assert sim("dead_air_after_rescue")["owed"] == ["create"]

    def test_both_hand_over_paths_resume_through_one_function(self):
        assert SCENARIO.count("resumeAfterHandover(agent);") == 1
        body = SCENARIO[SCENARIO.index("function resumeAfterHandover("):]
        body = body[:body.index("\n}\n")]
        assert "requestTurn(agent)" in body and "armDeadAir();" in body

    def test_the_rescue_clears_her_audio_with_the_socket(self):
        body = SCENARIO[SCENARIO.index("async function recoverAgent("):]
        body = body[:body.index("\n}\n")]
        assert "miraSilenced();" in body
