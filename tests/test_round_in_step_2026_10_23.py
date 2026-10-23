"""The closing round stays in step with what Mira actually asks (Oct 23 2026).

The first 22-minute rehearsal on the deployed room (run 4729e7b6) got all
eight closing questions, the last word and the thanks, but the room's count
ran one turn ahead of her from the start. The round began in a pause in the
middle of the guest's sentence; her turn only reacted and asked nothing; the
guest finished the sentence and the room took that for the answer to
question one. She then asked each question a turn late, and the room told
her three times that she had asked something twice. It also called any
question the room had handed her a repeat when she said it, on time or not,
because the room marks a question asked when it hands it over. Driven
through the real scenario by tests/fixtures/room_sim.js.
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


def round_lines(out: dict) -> list[str]:
    return [t["d"] for t in out["trace"] if t["e"] == "round"]


class TestATurnThatAsksNothingDidNotAsk:
    def test_the_question_goes_again_when_they_finish_their_thought(self):
        out = sim("round_turn_without_question")
        lines = round_lines(out)
        assert any(l.startswith("her turn asked nothing; the show's own question") for l in lines)
        assert any("handing 1/8 again" in l for l in lines)
        assert out["roundNotesAfterThought"] == 2          # handed twice, asked once
        assert not any(l.startswith("answered 1/8") for l in lines[:3])

    def test_the_round_then_runs_in_step(self):
        out = sim("round_turn_without_question")
        lines = round_lines(out)
        assert "answered 1/8" in lines
        assert "asked 2/8: a book they would recommend" in lines
        assert out["state"]["roundIndex"] == 1             # the book, the question in play
        assert out["state"]["roundAwaitingAnswer"] is True

    def test_a_question_the_room_handed_her_is_never_called_a_repeat(self):
        out = sim("round_turn_without_question")
        assert out["secondTimeNotes"] == 0
        assert not any(l.startswith("asked again") for l in round_lines(out))

    def test_a_reaction_and_their_silence_gets_the_question_now(self):
        out = sim("round_reaction_then_silence")
        assert out["events"] == ["create"]
        assert out["lastNote"].startswith("[ROUND 1 of 8")


class TestTheRuleIsNarrow:
    def test_only_a_line_with_no_question_counts(self):
        body = SCENARIO[SCENARIO.index("function noteRoundTurnWithoutQuestion("):]
        body = body[:body.index("\n}\n")]
        assert 'text.indexOf("?") >= 0' in body
        # Never the last word, never while the guest is away, never a question
        # her own words already carried.
        for guard in ("roundLastWordAsked", "holdMode", "roundSpoken[label]"):
            assert guard in body

    def test_it_runs_on_every_line_of_hers(self):
        remember = SCENARIO[SCENARIO.index("function remember(who, text)"):]
        remember = remember[:remember.index("\n}\n")]
        assert "noteRoundTurnWithoutQuestion(text);" in remember
        assert remember.index("noteRoundQuestion(text);") < remember.index("noteRoundTurnWithoutQuestion(text);")
