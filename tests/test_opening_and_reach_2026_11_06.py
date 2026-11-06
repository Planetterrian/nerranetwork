"""Patrick's test room, Nov 6 2026: the opening, and the last closing question.

1. At the start Mira introduces herself, asks the guest to be patient with her
   because she is still learning, says she leaves time for them to finish a
   thought, says how they can steer and change the subject, and says the hour
   ends with closing questions, a chance to say where to reach them and room
   for anything not covered. It is a turn of its own, between the hello and
   the first question, ending on a check (Oct 19 2026, Cory O'Daniel: forty
   seconds of format with the first question stacked on it).
2. A closing question: "How can listeners reach you or follow you if they
   want to know more?" It is the eighth and last, before the guest's last
   word. The scenario, fire_interviews.CLOSING_ROUND and the report change
   together.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VOICES = ROOT / "pipelines" / "voices"
SCENARIO_PATH = ROOT / "voximplant" / "scenarios" / "age_of_ai_interview.js"
SCENARIO = SCENARIO_PATH.read_text(encoding="utf-8")
PROMPT = (VOICES / "prompts" / "mira_system_prompt.txt").read_text(encoding="utf-8")
FLAT = " ".join(PROMPT.split())
REACH = "How can listeners reach you or follow you if they want to know more?"

sys.path.insert(0, str(VOICES))


def _opening() -> str:
    return FLAT[FLAT.index("HOW TO OPEN"):FLAT.index("THEIR SUBJECT, FAST")]


class TestTheOpeningSaysHowTheHourWorks:
    def test_every_point_patrick_asked_for_is_in_the_turn(self):
        turn = _opening()
        turn = turn[turn.index("2. How the hour works"):turn.index("3. Welcome them")]
        for needle in ("you are Mira", "still learning, and ask their patience",
                       "you pause after they finish, so nothing gets cut off",
                       "this is their hour: they can steer any time, aloud or with the studio's buttons and notes",
                       "any question can be skipped, anything can come out afterwards",
                       "they will see the transcript before anything goes out",
                       "closing questions, where to reach them, and anything not covered",
                       "Then ask if that sounds good."):
            assert needle in turn, needle

    def test_it_is_a_turn_of_its_own_and_the_question_comes_after(self):
        turn = _opening()
        assert "Three short turns, each one ending so that you can listen" in turn
        assert turn.index("2. How the hour works") < turn.index("3. Welcome them")
        assert "ask your first real question, about the subject they came to discuss" in turn

    def test_no_quoted_specimen_line(self):
        turn = _opening()
        assert "“" not in turn and '"' not in turn

    def test_the_room_tells_her_the_same_when_she_has_already_said_hello(self):
        assert ("beat 2 of HOW TO OPEN: how the hour works, in a few short sentences,\" +\n"
                "            \" then ask if that sounds good and listen.") in SCENARIO
        assert "one sentence on how this works" not in SCENARIO

    def test_the_co_host_is_introduced_in_the_welcome(self):
        import fire_interviews as fi
        assert fi.COHOST_INTRO_STEP.startswith("   In the welcome, introduce {{cohost_name}}")

    def test_the_brief_stays_inside_its_budget(self):
        assert len(PROMPT.split()) < 1600


def _round_block() -> str:
    block = SCENARIO[SCENARIO.index("const ROUND_QUESTIONS = ["):]
    return block[:block.index("];")]


class TestTheLastClosingQuestionIsWhereToReachThem:
    def test_the_room_asks_it_last_in_patricks_words(self):
        rows = [line for line in _round_block().splitlines()[1:] if line.strip().startswith("[")]
        assert len(rows) == 8
        assert rows[-1].startswith('  ["how listeners can reach or follow them"')
        assert REACH in rows[-1]
        assert "whether they would like a follow-up interview" in rows[-2]

    def test_the_topic_list_names_it(self):
        topics = SCENARIO[SCENARIO.index("const ROUND_TOPICS = {"):]
        topics = topics[:topics.index("};")]
        assert '"how listeners can reach or follow them":' in topics

    def test_fire_interviews_closing_round_matches(self):
        import fire_interviews as fi
        assert len(fi.CLOSING_ROUND) == 7   # the room's eight, without the show's own
        label, rx = fi.CLOSING_ROUND[-1]
        assert label.startswith("How listeners can reach or follow them")
        for said in (REACH, "Where can people find you online?", "And how can people follow you?"):
            assert rx.search(said), said
        for said in ("When did that idea first reach you?", "I follow you, go on.",
                     "Would you do this again?"):
            assert not rx.search(said), said

    def test_the_report_reads_eight(self):
        import rehearsal
        import audio_metrics
        qs = rehearsal.round_questions(SCENARIO_PATH)
        assert [label for label, _ in qs][-1] == "how listeners can reach or follow them"
        assert len(qs) == 8 == audio_metrics.ROUND_QUESTIONS_DEFAULT
        assert qs[-1][1].search(REACH)
        # Each room pattern is widened with the CLOSING_ROUND one in the same place.
        assert qs[-2][1].search("Would you do this again?")

    def test_the_round_has_its_minute(self):
        assert "function closingRoundMin() { return Math.min(10, closingWindowMin()); }" in SCENARIO
        assert re.search(r"where to\n// reach them \+ last word: about ten minutes", SCENARIO)
