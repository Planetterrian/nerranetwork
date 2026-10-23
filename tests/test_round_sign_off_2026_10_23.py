"""Oct 23 2026 — rehearsal 39982637152 (the round fix's candidate room).

Three faults, each read from the room's own session log:

* Handed a description of each closing question ("whether they would be
  interviewed again"), she asked questions of her own on five of seven turns.
  Each fixed question now carries its line (tests/test_round_follow_up_*).
* Grok sends a transcript delta's words as a plain string in payload.delta;
  the room read delta.transcript, so every piece was empty and the
  mid-sentence sign-off cut had never fired. She said "That's the end of the
  recording. You can hang up now." whole, twice, mid-round.
* After a sign-off the correction went as a conversation note, which takes
  effect a turn late: she said she had spoken too soon, then asked a question
  of her own. The question in play is now handed again as that turn's
  instructions, with the correction in front of it.
"""
from __future__ import annotations

import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCENARIO_PATH = ROOT / "voximplant" / "scenarios" / "age_of_ai_interview.js"
SIM = ROOT / "tests" / "fixtures" / "room_sim.js"


def sim(which: str) -> dict:
    res = subprocess.run(["node", str(SIM), str(SCENARIO_PATH), which],
                         capture_output=True, text=True, check=True)
    return json.loads(res.stdout)


def round_lines(out: dict) -> list:
    return [x["d"] for x in out["trace"] if x.get("e") in ("round", "close")]


class TestTheDeltaIsRead:
    def test_a_string_delta_is_its_own_words(self):
        pieces = sim("delta_shapes")["pieces"]
        assert pieces == [" the end of the recording.", "That's", " older shape", ""]


class TestASignOffMidSentenceIsCut:
    def test_the_logged_deltas_cancel_the_line(self):
        out = sim("delta_cut_rehands_the_question")
        assert out["events"][:2] == ["cancel", "clear"]
        assert "cancelled mid-sentence: a sign-off with the closing round at 4/8" in round_lines(out)

    def test_the_question_in_play_goes_again_as_instructions(self):
        out = sim("delta_cut_rehands_the_question")
        assert out["notesAdded"] == 0
        assert len(out["handed"]) == 1
        handed = out["handed"][0]
        assert "[ROUND 4 of 8" in handed
        assert "What's the best piece of advice you were ever given?" in handed
        assert "Do not mention the sentence that was cut off." in handed

    def test_the_cut_line_arriving_late_moves_nothing(self):
        out = sim("delta_cut_rehands_the_question")
        assert out["afterCutLine"]["roundIndex"] == 3
        assert out["afterCutLine"]["roundAwaitingAnswer"] is True
        assert not any(line.startswith("her turn asked") for line in round_lines(out))
        # Her real question is answered and the round goes on to question 5.
        assert out["final"]["roundIndex"] == 4
        assert "answered 4/8" in round_lines(out)


class TestASignOffAfterTheFactIsCorrectedInTheSameTurn:
    def test_the_correction_and_the_question_ride_one_turn(self):
        out = sim("sign_off_after_the_fact_rehands")
        assert out["notesAdded"] == 0
        assert len(out["handed"]) == 1
        handed = out["handed"][0]
        assert "you spoke too soon" in handed
        assert "What's a book you would recommend, and in a sentence, why?" in handed
        assert out["state"]["roundIndex"] == 1 and out["state"]["roundAwaitingAnswer"] is True


class TestTheMetricsCountARehandOnce:
    def test_a_sign_off_rehand_is_not_a_second_question(self):
        import sys
        sys.path.insert(0, str(ROOT / "pipelines" / "voices"))
        import audio_metrics
        out = sim("delta_cut_rehands_the_question")
        summary = audio_metrics.closing_round(out["trace"])
        assert summary["round_repeats"] == 0
        assert summary["round_stacked"] == 0
        assert summary["round_rehanded"] == 1
        assert summary["round_asked"] == 5
