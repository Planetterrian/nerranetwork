"""The shape of the hour (Nov 5 2026).

Patrick, after Blaine Mathieu's room: Mira lacks structure. She asks a
question, says a short summary of the answer and carries on down the same
thread, where a good interviewer knows when to move on, change the subject,
and have a real conversation with the guest when it fits. The record agreed:
across the nine rooms before it she reached 9 of 63 prepared questions, and
her brief told her to ask "the next question one step down" after every
answer and to go down from there again when the list ran out.

These guards hold: the prepared questions travel to the room in running
order; the room hands her the next one in words when a thread has had its
turns, never before a thread has had two of her questions; a thread of five
moves whatever the clock says; nothing is skipped or asked twice; the guest
and the close outrank the plan; a room with no plan behaves as before; the
trace carries indices, never words; and the brief describes the shape (two
or three steps, then move on out loud, one conversational turn of her own
in each part) without a quoted line.
"""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCENARIO_PATH = ROOT / "voximplant" / "scenarios" / "age_of_ai_interview.js"
SCENARIO = SCENARIO_PATH.read_text(encoding="utf-8")
SIM = ROOT / "tests" / "fixtures" / "room_sim.js"
PROMPT = (ROOT / "pipelines" / "voices" / "prompts" / "mira_system_prompt.txt").read_text(encoding="utf-8")
QUESTIONS = (ROOT / "pipelines" / "voices" / "prompts" / "question_generation.txt").read_text(encoding="utf-8")
NODE = shutil.which("node")
needs_node = pytest.mark.skipif(NODE is None, reason="node is not installed")

sys.path.insert(0, str(ROOT / "pipelines" / "voices"))


def sim(which: str) -> dict:
    out = subprocess.run([NODE, str(SIM), str(SCENARIO_PATH), which],
                         capture_output=True, text=True, timeout=60)
    assert out.returncode == 0, out.stderr[-2000:]
    return json.loads(out.stdout)


def plan_trace(out: dict) -> list:
    return [x["d"] for x in out["trace"] if x["e"] == "plan"]


def _flat(text: str) -> str:
    return " ".join(text.split())


HULL = "How do you decide which hull design is worth testing at sea?"


# 1. The plan travels to the room in running order ------------------------------

class TestThePlanTravels:
    BRIEF = {"likely_questions": [
        {"question": "Where does the field go next?", "section": "forward", "curious": "c4"},
        {"question": "What did the first boat teach you?", "section": "core", "curious": "c2"},
        {"question": "How did you start?", "section": "opening", "curious": "c1"},
        {"question": "Who disagrees with you, and why?", "section": "tension"},
        {"question": "What does a hull cost to test?", "section": "core"},
        "A plain string question?",
        {"question": "  ", "section": "core"},
    ]}

    def test_running_order_is_opening_core_tension_forward(self):
        import fire_interviews as fi
        plan = fi.interview_plan(self.BRIEF)
        assert [q["question"] for q in plan] == [
            "How did you start?", "What did the first boat teach you?",
            "What does a hull cost to test?", "A plain string question?",
            "Who disagrees with you, and why?", "Where does the field go next?"]
        assert plan[0] == {"question": "How did you start?", "curious": "c1", "section": "opening"}
        assert plan[3]["section"] == "core"   # no section sits with the core

    def test_the_plan_rides_the_run_row(self):
        import fire_interviews as fi

        class Show:
            local_video = False
        seed = fi.room_log_seed(Show, {}, self.BRIEF)
        assert len(seed["interview_plan"]) == 6
        assert fi.room_log_seed(Show, {}) == {}   # no brief, no plan, as before
        assert fi.room_log_seed(Show, {}, {"likely_questions": [{"question": "One?"}]}) == {}
        fire = (ROOT / "pipelines" / "voices" / "fire_interviews.py").read_text(encoding="utf-8")
        assert "is_hello_session(interview) or is_closing_session(interview) else brief" in fire

    def test_the_prompt_lists_them_numbered_in_the_same_order(self):
        import fire_interviews as fi
        plan = fi.interview_plan(self.BRIEF)
        listed = "\n".join(f"{n}. {q['question']}" for n, q in enumerate(plan, 1))
        src = (ROOT / "pipelines" / "voices" / "fire_interviews.py").read_text(encoding="utf-8")
        assert 'f"{n}. {q[\'question\']}"' in src and "enumerate(interview_plan(brief), 1)" in src
        assert listed.splitlines()[0] == "1. How did you start?"

    def test_the_rehearsal_s_proposed_arm_carries_it(self):
        import rehearsal
        row = rehearsal.build_run_row(
            interview={"id": "i", "show": "age_of_ai"}, arm="proposed",
            fixture={"id": "adrian", "name": "Adrian"}, prompt="P", minutes=30,
            turn_silence_ms=None, reasoning_effort="", tools=[],
            plan=[{"question": "A?"}, {"question": "B?"}])
        assert row["grok_session_log"]["interview_plan"] == [{"question": "A?"}, {"question": "B?"}]
        bare = rehearsal.build_run_row(
            interview={"id": "i", "show": "age_of_ai"}, arm="current",
            fixture={"id": "adrian", "name": "Adrian"}, prompt="P", minutes=30,
            turn_silence_ms=None, reasoning_effort="", tools=[])
        assert "interview_plan" not in bare["grok_session_log"]

    def test_the_rehearsal_report_shows_the_shape(self):
        import rehearsal
        trace = [{"t": "2026-11-05T16:00:00Z", "e": "plan", "d": "handed 2/4 at 9 min (the room)"},
                 {"t": "2026-11-05T16:30:00Z", "e": "plan",
                  "d": "reached 4/4; room moves 3, hers 0; longest thread 4 questions"}]
        log = rehearsal.room_log(trace)
        assert log["plan_summary"].startswith("reached 4/4")
        md = rehearsal.room_markdown({"arm": "proposed", "fixture": "adrian", "run_id": "x",
                                      "room_log": log, "planned_minutes": 30})
        assert "prepared questions: reached 4/4" in md
        assert "the shape of the hour, as the room traced it" in md


# 2. The room moves a thread that has had its turns ------------------------------

@needs_node
class TestTheRoomMovesOn:
    def test_not_before_the_thread_has_had_its_turns_and_the_clock(self):
        out = sim("plan_moves_on")
        assert out["first"]["instructions"] == "" and out["second"]["instructions"] == ""
        third = out["third"]
        assert HULL in third["instructions"]
        assert third["instructions"].startswith("BRIEF: the guest builds boats.")
        assert "for this turn only" in third["instructions"]
        assert third["plan"]["planIndex"] == 1 and third["plan"]["planThreadTurns"] == 0
        assert plan_trace(out) == ["move to 2/4 queued (due at 9 min)",
                                   "handed 2/4 at 9 min (the room)"]
        # The next turn is hers again: one move, then the new thread.
        assert out["after"]["instructions"] == ""
        assert out["after"]["plan"]["planThreadTurns"] == 1

    def test_the_move_says_close_turn_ask_and_never_summarise(self):
        line = _flat(sim("plan_moves_on")["third"]["instructions"])
        assert "if they just asked you something, answer it first" in line
        assert "close this thread in one sentence that carries something it gave you" in line
        assert "never a summary of their answer" in line
        assert "differently each time" in line
        assert "in these words or very close to them" in line

    def test_five_questions_on_one_thread_move_whatever_the_clock(self):
        turns = sim("plan_max_thread")["turns"]
        assert [bool(t["instructions"]) for t in turns] == [False, False, False, False, True, False]
        assert HULL in turns[4]["instructions"]

    def test_a_question_she_reaches_herself_counts_and_nothing_is_skipped(self):
        out = sim("plan_own_ask")
        assert out["own"]["plan"]["planOwnMoves"] == 1 and out["own"]["instructions"] == ""
        # The room's next hand is the first one not yet reached, never the next index.
        assert HULL in out["next"]["instructions"]
        assert plan_trace(out)[0] == "she reached 3/4 herself at 3 min"
        assert "numbers 1, 2, 3 have been asked" in out["handover"]

    def test_the_handover_carries_where_the_plan_stands(self):
        out = sim("plan_moves_on")
        assert "you are on number 2 of 4, and numbers 1, 2 have been asked" in out["handover"]


# 3. The guest and the close outrank the plan -------------------------------------

@needs_node
class TestTheGuestComesFirst:
    def test_no_move_once_the_close_is_permitted(self):
        out = sim("plan_yields")
        assert out["closing"]["instructions"] == ""
        assert not any(d.startswith("move") for d in plan_trace(out))

    def test_a_topic_press_wins_and_starts_a_new_thread(self):
        steer = sim("plan_yields")["steer"]
        assert "the sailing club" in steer["instructions"]
        assert HULL not in steer["instructions"]
        assert steer["plan"]["planThreadTurns"] == 0

    def test_move_on_hands_the_next_prepared_subject_in_words(self):
        out = sim("plan_move_on_press")
        assert HULL in out["press"]["instructions"]
        assert "never say that they asked to move on" in out["press"]["instructions"]
        assert out["press"]["plan"]["planIndex"] == 1
        assert plan_trace(out) == ["handed 2/4 at 3 min (the guest moved on)"]

    def test_the_plan_pauses_for_every_guest_and_close_state(self):
        body = SCENARIO[SCENARIO.index("function planPaused()"):]
        body = body[:body.index("\n}\n")]
        for state in ("holdMode", "roundActive", "roundPendingStart", "roundClosed",
                      "closingPermitted", "closingThanksQueued", "stopWithoutRound()", "guestSteer"):
            assert state in body, state
        on = SCENARIO[SCENARIO.index("function planOn()"):]
        assert "!isHelloSession() && !isClosingSession()" in on[:on.index("\n}\n")]

    def test_a_move_never_overwrites_another_turn_s_instructions(self):
        body = SCENARIO[SCENARIO.index("function queuePlanMove("):]
        assert "if (k < 0 || nextTurnInstructions) return false;" in body[:body.index("\n}\n")]


# 4. A room with no plan is the room it was ---------------------------------------

@needs_node
class TestNoPlanNoChange:
    def test_no_plan_no_moves_no_lines(self):
        out = sim("plan_none")
        for k in ("first", "second", "third", "after"):
            assert out[k]["instructions"] == "", k
        assert plan_trace(out) == []
        assert "prepared questions one subject at a time" not in out["handover"]

    def test_the_old_time_note_stays_for_a_room_without_a_plan(self):
        assert "next question down from it" in SCENARIO
        assert "The room hands you your next prepared question when this thread" in SCENARIO


# 5. The trace carries indices, never words ---------------------------------------

class TestTheTraceCarriesNoWords:
    def test_every_plan_trace_is_numbers_and_reasons(self):
        lines = [line for line in SCENARIO.splitlines() if 'trace("plan"' in line]
        assert lines
        for line in lines:
            assert ".question)" not in line and ".question +" not in line and "curious" not in line, line

    @needs_node
    def test_the_sim_trace_has_no_question_words(self):
        for which in ("plan_moves_on", "plan_own_ask", "plan_move_on_press"):
            for d in plan_trace(sim(which)):
                assert "hull" not in d.lower() and "insurer" not in d.lower(), d


# 6. The brief describes the shape, by shape ---------------------------------------

class TestTheBriefHasAShape:
    LISTEN = _flat(PROMPT[PROMPT.index("HOW TO LISTEN"):PROMPT.index("IT IS THEIR HOUR")])
    REACT = _flat(PROMPT[PROMPT.index("HOW TO REACT"):PROMPT.index("RESEARCH IS QUIET")])

    def test_the_prepared_questions_are_the_running_order(self):
        assert "follow the conversation, not the list" not in PROMPT
        assert "Prepared questions, one part of the hour each, in order:" in PROMPT

    def test_two_or_three_steps_then_the_next_question_out_loud(self):
        assert "Two or three steps down is a thread; then the next prepared question," \
            " out loud." in self.LISTEN
        assert "go down from there" not in self.LISTEN
        assert "Then the next question one step down" not in self.LISTEN
        assert "go back to the best thing they said and open it from a new side" in self.LISTEN

    def test_one_conversational_turn_of_her_own_in_each_part(self):
        assert "Once in each part, offer a view of your own and hand it back as a" \
            " question; answer their questions first." in self.REACT
        assert "once or twice an hour" not in self.REACT

    def test_the_brief_stays_within_its_budget(self):
        # tests/test_second_test_room_2026_10_28.py holds the brief under 1,600
        # words; the structure is the room's job, so the brief only names it.
        assert len(PROMPT.split()) < 1600

    def test_the_move_s_craft_is_in_the_room_not_the_brief(self):
        flat = SCENARIO.replace('" +\n  "', "")
        assert "close this thread in one sentence that carries something it gave you" in flat
        assert "never a summary of their answer" in flat

    def test_no_quoted_line_and_no_guest_in_the_new_text(self):
        for chunk in (self.LISTEN, self.REACT):
            assert '"' not in chunk
        for word in ("Blaine", "Mathieu", "Nov 5", "63"):
            assert word not in PROMPT, word

    def test_the_question_set_is_written_as_a_running_order(self):
        flat = _flat(QUESTIONS)
        assert "every prepared question she does not need is one she can drop" not in flat
        assert "The set is the running order of the hour" in flat
