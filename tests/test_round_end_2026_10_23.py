"""Oct 23 2026 — the end of the closing round (rehearsal 39991520039), and the
seven questions Patrick set the same day.

The rehearsal asked the first six questions in their words and lost the last
two. Handed "How was the experience of being interviewed by an AI?", she
asked a question of her own; handed it again, she went into her goodbye (the
thanks, the network, "that's the end of the recording") three times, each cut
mid-sentence. The guest said "sounds like you trailed off there" and the room
counted that as the answer, to both questions. After her closing thanks the
room went on giving her turns: "Bye, Roddy.", "Silence.", "Nothing.", "Yeah.",
and, to an empty room, "I'm here. Take your time."

Patrick's round: the two questions about the interview are one, sixth; the
last asks for a follow-up interview in six months to a year.
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCENARIO_PATH = ROOT / "voximplant" / "scenarios" / "age_of_ai_interview.js"
SCENARIO = SCENARIO_PATH.read_text(encoding="utf-8")
SIM = ROOT / "tests" / "fixtures" / "room_sim.js"
PROMPTS = ROOT / "pipelines" / "voices" / "prompts"
sys.path.insert(0, str(ROOT / "pipelines" / "voices"))


def sim(which: str) -> dict:
    res = subprocess.run(["node", str(SIM), str(SCENARIO_PATH), which],
                         capture_output=True, text=True, check=True)
    return json.loads(res.stdout)


def round_lines(out: dict) -> list:
    return [x["d"] for x in out["trace"] if x.get("e") in ("round", "close", "turn")]


def entries() -> list:
    i = SCENARIO.index("const ROUND_QUESTIONS = [")
    block = SCENARIO[i:SCENARIO.index("];", i)]
    return re.findall(r'\["([^"]+)", /(.+?)/i(?:, "([^"]*)")?\]', block)


class TestPatricksSevenQuestions:
    def test_the_order(self):
        assert [label for label, _, _ in entries()] == [
            "the show's own question",
            "a book they would recommend",
            "who you should interview next",
            "the best advice they were ever given",
            "who has inspired them most",
            "how being interviewed by an AI was, and one improvement",
            "whether they would like a follow-up interview",
        ]

    def test_the_words(self):
        lines = {label: line for label, _, line in entries()}
        assert lines["how being interviewed by an AI was, and one improvement"] == (
            "How was the experience of being interviewed by an AI, and what's one specific"
            " thing we could improve?")
        follow_up = lines["whether they would like a follow-up interview"]
        assert "follow-up interview" in follow_up
        assert "six months to a year" in follow_up
        assert "projects" in follow_up and "how much I've improved" in follow_up

    def test_no_question_hears_another_ones_words(self):
        rows = entries()
        for label, pattern, _ in rows:
            for other, _, line in rows:
                if other != label and line:
                    assert not re.search(pattern, line, re.I), (label, other)

    def test_the_closing_session_list_matches_the_room(self):
        from fire_interviews import CLOSING_ROUND
        rows = entries()[1:]
        assert len(CLOSING_ROUND) == len(rows)
        for (_, rx), (label, _, line) in zip(CLOSING_ROUND, rows):
            assert rx.search(line), label

    def test_the_briefs_name_the_round(self):
        flat = " ".join((PROMPTS / "mira_system_prompt.txt").read_text(encoding="utf-8").split())
        assert ("four short closing questions, one about the interview itself, and whether"
                " they would like a follow-up interview") in flat
        closing = " ".join((PROMPTS / "mira_closing_session.txt").read_text(encoding="utf-8").split())
        assert "whether they would like a follow-up interview in six months to a year" in closing
        assert "two about the interview itself" not in flat + closing

    def test_the_feedback_reader_and_the_closing_cut_still_hear_it(self):
        import auto_edit
        import learning
        line = entries()[5][2]
        assert learning._FEEDBACK_CUE.search(line)
        assert auto_edit.CLOSING_ENDS.search(line)


class TestAQuestionNeverHeardIsNotAnswered:
    def test_the_guest_saying_she_trailed_off_hands_it_again(self):
        out = sim("round_end_as_rehearsed")
        lines = round_lines(out)
        assert ("they spoke, but how being interviewed by an AI was, and one improvement"
                " never reached them; handing 6/7 again") in lines
        assert out["afterTrailedOff"]["roundIndex"] == 5
        assert out["afterTrailedOff"]["roundAwaitingAnswer"] is True
        # Asked in its words at last, its answer moves the round on.
        assert "answered 6/7" in lines and "answered 7/7" in lines
        assert lines.index("answered 6/7") > lines.index(
            "they spoke, but how being interviewed by an AI was, and one improvement"
            " never reached them; handing 6/7 again")

    def test_it_is_handed_again_at_most_twice(self):
        fn = SCENARIO[SCENARIO.index("function roundAnswered()"):]
        fn = fn[:fn.index("\nfunction ", 10)]
        assert "ROUND_UNHEARD_REHANDS_MAX" in fn
        assert "const ROUND_UNHEARD_REHANDS_MAX = 2;" in SCENARIO
        # A question she asked twice in words the room cannot recognise is
        # taken as asked, never handed again for being unheard.
        assert "!roundAskedUnrecognised[" in fn

    def test_the_metric_counts_it_once(self):
        import audio_metrics
        out = sim("round_end_as_rehearsed")
        summary = audio_metrics.closing_round(out["trace"])
        assert summary["round_asked"] == 7
        assert summary["round_stacked"] == 0
        assert summary["closing_round_complete"] is True


class TestSheKnowsTheRoundIsNotOver:
    def test_each_question_says_what_is_still_to_come(self):
        out = sim("round_end_as_rehearsed")
        sixth = [h for h in out["handed"] if h.startswith("[ROUND 6 of 7")]
        seventh = [h for h in out["handed"] if h.startswith("[ROUND 7 of 7")]
        assert sixth and seventh
        assert all("hands you 1 more closing question, then their last word" in h for h in sixth)
        assert "This is the last closing question" in seventh[0]
        for h in sixth + seventh:
            assert "no thanks, no goodbye, nothing about the recording ending" in h


class TestNothingAfterTheGoodbye:
    def test_one_goodbye_then_silence(self):
        out = sim("round_end_as_rehearsed")
        assert out["createsAfterThanks"] == 1
        assert out["lastInstructions"].endswith("Say goodbye in a few words. Nothing else.")
        assert round_lines(out).count("the interview is over; no turn after her goodbye") == 2

    def test_no_time_notes_after_the_round(self):
        tick = SCENARIO[SCENARIO.index("function startTimeChecks()"):]
        tick = tick[:tick.index("const elapsed")]
        assert "if (roundClosed) return;" in tick
