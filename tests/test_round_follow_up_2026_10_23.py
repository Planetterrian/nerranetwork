"""Oct 23 2026 (rehearsal 0dd50fbe) — a round turn that asks a follow-up.

Handed "who you should interview next", Mira reacted to the guest's book and
asked a follow-up about it. The guest's reply was counted as the answer and the
question was never put to them. A round turn that asks something, but not the
question in play, now hands that question again, once per question, so a
rewording the room cannot recognise never loops.
"""
from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path

from pipelines.voices import audio_metrics, rehearsal

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


class TestAFollowUpIsNotTheQuestion:
    def test_the_question_in_play_goes_again(self):
        out = sim("round_turn_asks_a_follow_up")
        lines = round_lines(out)
        assert ("her turn asked something else; who you should interview next "
                "goes again when they finish") in lines
        assert "they finished their thought; handing 3/7 again" in lines
        assert out["handedAgain"] == 2

    def test_a_second_miss_moves_on_and_never_loops(self):
        out = sim("round_turn_asks_a_follow_up")
        lines = round_lines(out)
        assert sum(1 for line in lines if line.startswith("her turn asked")) == 1
        assert "asked 4/7: the best advice they were ever given" in lines
        assert out["state"]["roundIndex"] == 3


class TestTheQuestionIsRecognised:
    def _pattern(self) -> re.Pattern:
        for label, pat in rehearsal.round_questions():
            if label == "who you should interview next":
                return pat
        raise AssertionError("no pattern for the interview-next question")

    def test_common_wordings_read_as_asked(self):
        pat = self._pattern()
        for line in ("Who should I interview next?",
                     "Who else should I have on the show?",
                     "Who should we have on next?",
                     "Is there someone I should talk to next?"):
            assert pat.search(line), line

    def test_the_report_counts_the_new_line_as_a_rehand(self):
        assert audio_metrics._ROUND_REHAND.search(
            "her turn asked something else; who you should interview next goes again")


class TestAQuestionOnTheSubjectIsNeverHandedBack:
    def test_her_own_wording_of_the_handed_question_counts(self):
        # The four 2026-10-22 hold rooms ask "the one bet you are making",
        # which the exact pattern misses: the subject check keeps the room
        # from handing it back and making her ask a guest twice.
        for which in ("feedback_in_round", "server_turns_advance_the_round"):
            out = sim(which)
            assert not any(line.startswith("her turn asked")
                           for line in round_lines(out)), which

    def test_every_round_question_has_a_subject(self):
        labels = [label for label, _ in rehearsal.round_questions()]
        i = SCENARIO.index("const ROUND_TOPICS")
        topics = SCENARIO[i:SCENARIO.index("};", i)]
        for label in labels[:8]:
            assert f'"{label}"' in topics, label


class TestSheIsGivenTheWords:
    """Rehearsal 39982637152: handed a description ("whether they would be
    interviewed again"), she asked questions of her own ("What did you expect
    this to be like?") on five of seven turns. Each fixed question now carries
    the line she says, and the room's own pattern must hear that line."""

    def _entries(self):
        i = SCENARIO.index("const ROUND_QUESTIONS = [")
        block = SCENARIO[i:SCENARIO.index("];", i)]
        return re.findall(r'\["([^"]+)", /(.+?)/i(?:, "([^"]*)")?\]', block)

    def test_every_fixed_question_has_its_line_and_the_room_hears_it(self):
        entries = self._entries()
        assert len(entries) == 7
        for label, pattern, line in entries:
            if label == "the show's own question":
                continue    # the show supplies its own wording
            assert line.endswith("?"), label
            assert re.search(pattern, line, re.I), label

    def test_the_instruction_carries_the_line_not_the_label(self):
        i = SCENARIO.index("function roundQuestionText")
        body = SCENARIO[i:SCENARIO.index("\n}\n", i)]
        # Oct 24 2026: never the label; with no words to hand, nothing.
        assert 'return entry[2] || "";' in body
        assert "return showQuestionText();" in body
