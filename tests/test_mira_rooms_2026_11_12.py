"""What the rooms of Nov 11 and 12 2026 taught (reviewed Nov 12).

The first real guests since Nov 4. John's room graded 4 and Rania Esmael's 5,
and the graders' notes named the same things: every turn of hers opened by
folding the answer into a phrase, and the gaps were long. Rania's trace and
transcript showed four faults no instrument had counted:

- she asked to hear the question again about eight times, aloud; the room
  acted only on the studio button, the prepared questions ran to 33 words in
  one sentence, and Mira said each again at full length;
- in the closing round "the one what?" was counted as the answer to the
  show's question, and the round lost its place from there;
- handed the book question, Mira reacted, asked nothing, and the question
  was never put;
- "I'll be here", said to a guest who had promised an email, put the room on
  hold for 64 seconds with the guest present.

These guards hold: a spoken request to hear a question again is that request,
on an ordinary turn and in the round, and is counted; a closing turn of hers
that asked nothing is followed by its question at once; "I'll be here" is a
wait only when it says so; the room rotates the shape of her ordinary turns;
a long prepared question is handed for the ear; prepared questions are
checked for length in code; and the repeat requests are a number the grader
and the rehearsal read.
"""
from __future__ import annotations

import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
V = ROOT / "pipelines" / "voices"
if str(V) not in sys.path:
    sys.path.insert(0, str(V))

SCENARIO_PATH = ROOT / "voximplant" / "scenarios" / "age_of_ai_interview.js"
SCENARIO = SCENARIO_PATH.read_text(encoding="utf-8")
SIM = ROOT / "tests" / "fixtures" / "room_sim.js"
PROMPT = (V / "prompts" / "mira_system_prompt.txt").read_text(encoding="utf-8")
QUESTIONS_PROMPT = (V / "prompts" / "question_generation.txt").read_text(encoding="utf-8")
NODE = shutil.which("node")
needs_node = pytest.mark.skipif(NODE is None, reason="node is not installed")

#: What a guest says when the question did not land. One list, read by the
#: room's pattern and by the metric's.
REPEAT_ASKS = [
    "Sorry, can you repeat the question?",
    "Could you say that again?",
    "Can you rephrase that, please?",
    "Please repeat the question.",
    "I didn't catch that.",
    "I did not understand the question.",
    "I don't understand your question.",
    "Sorry, what?",
    "Come again?",
    "What was the question?",
    "One more time, please.",
    "What do you mean?",
    "Can you ask me again?",
    "I couldn’t hear you.",
]
#: Answers that carry some of the same words.
NOT_REPEAT_ASKS = [
    "We repeat the test every quarter and it holds.",
    "I caught that problem early, in the first cohort.",
    "The question we kept coming back to was price.",
    "Yes. That is exactly what I mean.",
    "I understand the question, and the honest answer is no.",
]


def sim(which: str) -> dict:
    out = subprocess.run([NODE, str(SIM), str(SCENARIO_PATH), which],
                         capture_output=True, text=True, timeout=60)
    assert out.returncode == 0, out.stderr[-2000:]
    return json.loads(out.stdout)


def _regex(name: str) -> re.Pattern:
    head = f"const {name} = /"
    rx = SCENARIO[SCENARIO.index(head) + len(head):]
    return re.compile(rx[:rx.index("/i;")], re.I)


def _flat(text: str) -> str:
    return " ".join(str(text).split())


def _const(name: str) -> str:
    """The string a scenario constant concatenates to."""
    head = f"const {name} ="
    body = SCENARIO[SCENARIO.index(head) + len(head):]
    body = body[:body.index(";\n")]
    return "".join(re.findall(r'"((?:[^"\\]|\\.)*)"', body))


class TestASpokenRepeatIsTheRepeatButton:
    @pytest.mark.parametrize("text", REPEAT_ASKS)
    def test_the_room_hears_it(self, text):
        assert _regex("GUEST_REPEAT_RE").search(text.replace("’", "'")), text

    @pytest.mark.parametrize("text", NOT_REPEAT_ASKS)
    def test_an_answer_is_not_a_request(self, text):
        assert not _regex("GUEST_REPEAT_RE").search(text), text

    @needs_node
    def test_her_next_turn_is_the_question_again_plainer_and_nothing_else(self):
        out = sim("spoken_repeat")
        first = _flat(out["first"])
        assert first.startswith("BRIEF: the guest builds boats.")          # the brief rides with it
        assert "which of them do you build for?" in first                   # her own question, in words
        assert "one short sentence in plain, everyday words" in first
        assert "Do not say it again as it was" in first
        assert "never remark that they asked" in first

    @needs_node
    def test_asked_twice_she_asks_a_simpler_question_instead(self):
        out = sim("spoken_repeat")
        second = _flat(out["second"])
        assert "Do not ask it a third time" in second
        assert "much simpler question about the same thing" in second
        # An answer between two requests starts the count again.
        assert "Do not say it again as it was" in _flat(out["third"])

    @needs_node
    def test_the_same_words_inside_a_long_answer_are_the_answer(self):
        out = sim("spoken_repeat")
        assert out["inAnAnswer"] == ""
        assert out["count"] == 3

    @needs_node
    def test_it_is_counted_and_the_trace_never_carries_their_words(self):
        out = sim("spoken_repeat")
        lines = [t["d"] for t in out["trace"] if t["e"] == "repeat"]
        assert len(lines) == 3
        assert all(d.startswith("the guest asked to hear the question again") for d in lines)
        assert not any("understand" in d or "Sorry" in d or "what?" in d for d in lines)
        assert "guest_repeat_asks: guestRepeatAsks," in SCENARIO

    def test_the_lines_carry_no_specimen_she_could_say(self):
        for name in ("SPOKEN_REPEAT_HEAD", "SPOKEN_REPEAT_TAIL", "SPOKEN_REPEAT_AGAIN_TAIL",
                     "PLAIN_AGAIN_LEAD_IN"):
            line = _const(name)
            assert line and "“" not in line and "lightning" not in line.lower(), name


@needs_node
class TestTheClosingRoundKeepsItsPlace:
    def test_asking_to_hear_it_again_is_not_an_answer(self):
        out = sim("round_repeat_is_not_an_answer")
        after = out["afterRepeat"]
        assert after["state"]["roundIndex"] == 0 and after["state"]["roundAwaitingAnswer"]
        assert after["handed"].startswith("What's the one bet")
        assert "shorter, plainer words that keep its meaning" in _flat(after["instructions"])
        assert "in these words (their name may go in)" not in _flat(after["instructions"])
        # The allowance for a question that never reached them is not spent on it.
        assert after["rehands"] == "{}"

    def test_the_round_goes_on_from_the_real_answer(self):
        out = sim("round_repeat_is_not_an_answer")
        assert out["afterAnswer"]["state"]["roundIndex"] == 1
        assert out["afterAnswer"]["handed"].startswith("What's a book")
        assert out["asked"] == [1, 1, 2]

    def test_a_question_goes_again_in_plainer_words_at_most_twice(self):
        assert "const ROUND_PLAIN_ASKS_MAX = 2;" in SCENARIO
        assert "(roundPlainAsks[label] || 0) < ROUND_PLAIN_ASKS_MAX" in SCENARIO

    def test_a_turn_of_hers_that_asked_nothing_is_followed_by_the_question(self):
        out = sim("round_asked_nothing_follows_now")
        assert out["early"] == []                    # her line is heard out first
        assert out["events"] == ["create"]           # then the question, not a 35-second wait
        assert out["handed"].startswith("What's a book")
        assert "Say nothing before it" in _flat(out["instructions"])
        assert out["state"]["roundIndex"] == 1
        assert any("the floor is free; the question follows now" in t["d"] for t in out["trace"])

    def test_a_guest_who_adds_something_keeps_the_floor(self):
        # The Oct 23 case still holds: they finish the thought, then it is handed.
        out = sim("round_turn_without_question")
        assert out["roundNotesAfterThought"] == 2
        assert "if (guestSpokeSinceMira || inboundSpeaking) {" in SCENARIO[
            SCENARIO.index("function continueRoundTurn()"):SCENARIO.index("function roundTurnDone()")]


@needs_node
class TestIllBeHereIsNotAHold:
    def phrases(self, lines):
        import os
        out = subprocess.run([NODE, str(SIM), str(SCENARIO_PATH), "phrases"], capture_output=True,
                             text=True, timeout=60, env={**os.environ, "ROOM_SIM_PHRASES": json.dumps(lines)})
        assert out.returncode == 0, out.stderr[-2000:]
        return [p["mira_wait"] for p in json.loads(out.stdout)["phrases"]]

    def test_said_to_a_guest_who_is_staying_it_is_not_a_wait(self):
        assert self.phrases(["Deal. I'll be here.", "Send it when you can. I will be here.",
                             "I'll be here for the follow-up."]) == [False, False, False]

    def test_the_waiting_senses_still_hold(self):
        assert self.phrases(["I'll be right here.", "Take your time, I'll be here.",
                             "I'll be here when you're back.", "Of course, I'll wait."]) == [True] * 4


@needs_node
class TestTheRoomRotatesTheShapeOfHerTurn:
    def test_every_second_ordinary_turn_is_shaped_and_never_the_same_twice(self):
        out = sim("turn_shapes")
        assert [bool(t) for t in out["turns"]] == [True, False, True, False, True, False]
        assert out["shapes"] == ["join (1)", "weigh (2)", "instance (3)"]
        shaped = [_flat(t) for t in out["turns"] if t]
        assert len(set(shaped)) == 3
        for line in shaped:
            assert line.startswith("BRIEF: the guest builds boats.")
            assert "directions, not words to say" in line
            assert "none of their phrases" in line
            assert "full sentence" in line

    def test_a_short_answer_and_a_question_to_her_are_left_alone(self):
        out = sim("turn_shapes")
        assert out["short"] == "" and out["asksHer"] == ""

    def test_one_room_can_switch_it_off(self):
        out = sim("turn_shapes_off")
        assert out["handed"] == 0 and not any(out["turns"])

    def test_never_in_the_opening_the_round_a_hold_or_on_a_turn_that_carries_something(self):
        fn = SCENARIO[SCENARIO.index("function noteOrdinaryTurn(delta)"):SCENARIO.index("function takeTurnShape()")]
        assert "nextTurnInstructions || guestSteer || researchAsk" in fn
        assert "roundActive || roundPendingStart || closingThanksQueued || holdMode" in fn
        assert "minutesIn() < PLAN_OPEN_MIN" in fn
        on = SCENARIO[SCENARIO.index("function turnShapesOn()"):SCENARIO.index("function noteOrdinaryTurn(delta)")]
        assert "isHelloSession() || isClosingSession()" in on
        # The shape is the last thing a turn may carry, after every other hand.
        assert "nextTurnInstructions || takeGuestSteer() || takeResearchAsk() || takeTurnShape();" in SCENARIO

    def test_the_shapes_are_directions_with_no_line_to_say(self):
        body = SCENARIO[SCENARIO.index("const TURN_SHAPES = ["):SCENARIO.index("const TURN_SHAPE_MIN_WORDS")]
        assert "“" not in body and "'" not in body.replace("their", "")
        assert "lightning" not in body.lower()

    def test_the_brief_did_not_grow_a_prohibition_for_it(self):
        # The room enforces the variety; the brief keeps its one line of shape.
        assert PROMPT.count("never the same shape twice") == 1
        assert len(PROMPT.split()) < 1600


class TestQuestionsAreWrittenForTheEar:
    def test_a_long_prepared_question_is_handed_for_the_ear(self):
        if NODE is None:
            pytest.skip("node is not installed")
        out = sim("question_lines_for_the_ear")
        assert "in these words or very close to them" in out["short"]
        assert "in these words" not in out["long"]
        assert "understood on first hearing" in out["long"]
        assert "its own short sentence before it" in out["long"]

    def test_the_brief_asks_for_one_idea_in_plain_words(self):
        flat = _flat(PROMPT)
        assert "One short question per turn, one idea in everyday words, asked once, then silence" in flat
        assert "asked to hear it again, say it shorter and plainer" in flat
        assert "- One question per turn: one idea, plain words, asked once." in PROMPT

    def test_the_question_writer_is_told_the_shape_and_the_numbers(self):
        flat = _flat(QUESTIONS_PROMPT)
        assert "written for the ear" in flat
        assert "{{spoken_question_words}}" in QUESTIONS_PROMPT and "{{spoken_setup_words}}" in QUESTIONS_PROMPT
        ear = (V / "prompts" / "question_for_the_ear.txt").read_text(encoding="utf-8")
        assert "{{questions}}" in ear and "{{spoken_question_words}}" in ear

    def test_the_length_is_checked_in_code(self):
        import generate_briefs as gb
        ok = "You built the yard in a garage. What did the first boat teach you about cost?"
        assert gb.spoken_question_faults(ok) == []
        assert gb.spoken_question_faults("What did the first boat teach you?") == []
        long_one = ("Other yards use the same autonomous navigation tools to sell boats that later turn out"
                    " to need a crew; how do you keep the difference between those offers and your own"
                    " safety-first teaching visible to buyers?")
        faults = gb.spoken_question_faults(long_one)
        assert any("runs past" in f for f in faults) and any("semicolon" in f for f in faults)
        assert gb.spoken_question_faults("Where did it start? And what did it cost?")
        assert gb.spoken_question_faults("Tell me about the first boat.")
        assert gb.spoken_question_faults("")

    def test_a_rewrite_is_kept_only_when_it_passes(self, monkeypatch):
        import generate_briefs as gb
        long_a = " ".join(["word"] * 30) + "?"
        long_b = " ".join(["other"] * 30) + "?"
        questions = [{"question": "What did the first boat teach you?", "why": "w", "section": "opening"},
                     {"question": long_a, "why": "a", "curious": "c", "section": "core"},
                     {"question": long_b, "why": "b", "section": "tension"}]
        calls = []
        monkeypatch.setattr(gb, "load_prompt", lambda *a, **k: calls.append(k) or "")
        monkeypatch.setattr(gb, "llm", lambda *a, **k: json.dumps(
            ["What did the second hull cost you?", " ".join(["still"] * 30) + "?"]))
        out = gb.questions_for_the_ear(questions)
        assert json.loads(calls[0]["questions"]) == [long_a, long_b]         # only the failing ones are sent
        assert out[0] == questions[0]
        assert out[1] == {"question": "What did the second hull cost you?", "why": "a", "curious": "c", "section": "core"}
        assert out[2]["question"] == long_b                                   # a rewrite that fails is not kept
        assert questions[1]["question"] == long_a                             # the input is not edited in place

    def test_a_failed_rewrite_never_costs_the_brief(self, monkeypatch):
        import generate_briefs as gb
        questions = [{"question": " ".join(["word"] * 30) + "?"}]
        monkeypatch.setattr(gb, "load_prompt", lambda *a, **k: "")

        def boom(*a, **k):
            raise RuntimeError("no model")
        monkeypatch.setattr(gb, "llm", boom)
        assert gb.questions_for_the_ear(questions) == questions
        monkeypatch.setattr(gb, "llm", lambda *a, **k: "[]")                  # wrong length
        assert gb.questions_for_the_ear(questions) == questions
        calls = []
        monkeypatch.setattr(gb, "llm", lambda *a, **k: calls.append(1) or "[]")
        fine = [{"question": "What did the first boat teach you?"}]
        assert gb.questions_for_the_ear(fine) == fine and calls == []         # nothing to rewrite: no call


class TestRepeatRequestsAreANumber:
    @pytest.mark.parametrize("text", REPEAT_ASKS)
    def test_the_metric_reads_the_same_phrases_as_the_room(self, text):
        import audio_metrics
        assert audio_metrics.is_repeat_request(text), text

    @pytest.mark.parametrize("text", NOT_REPEAT_ASKS)
    def test_and_the_same_answers(self, text):
        import audio_metrics
        assert not audio_metrics.is_repeat_request(text), text

    def test_counted_per_room_and_none_without_a_guest_track(self):
        import audio_metrics

        def words(text, at):
            return [{"start": at + i * 0.3, "end": at + i * 0.3 + 0.25, "word": w}
                    for i, w in enumerate(text.split())]
        guest = (words("Sorry, can you repeat the question?", 10.0)
                 + words("We tried it on the lake first and it mostly worked.", 40.0)
                 + words("I didn't understand the question.", 80.0))
        mira = words("What did the first boat teach you about cost?", 2.0) + \
            words("What did the first boat teach you?", 20.0) + words("And after the lake?", 60.0)
        measured = audio_metrics.measure_audio({"mira": mira, "guest": guest})
        assert measured["guest_repeat_requests"] == 2
        assert audio_metrics.notes(measured)["guest_repeat_requests"] == 2
        assert audio_metrics.guest_repeat_requests([]) is None
        long_answer = " ".join(["word"] * 40) + " what do you mean by that"
        assert not audio_metrics.is_repeat_request(long_answer)

    def test_the_grader_the_retro_and_the_rehearsal_read_it(self):
        import rehearsal
        assert "guest_repeat_requests" in rehearsal.READ_BESIDE
        post = (V / "post_interview.py").read_text(encoding="utf-8")
        assert '"guest_repeat_requests": ((metrics.get("notes") or {}).get("audio") or {}).get("guest_repeat_requests")' in post
        assert '("asked to hear the question again", "guest_repeat_requests", "")' in (
            V / "learning.py").read_text(encoding="utf-8")


class TestTheRecord:
    def test_the_review_and_the_register_entry_exist(self):
        review = (ROOT / "docs" / "reviews" / "mira_rooms_2026_11_12.md").read_text(encoding="utf-8")
        for needle in ("a6a46957", "turn_shapes", "guest_repeat_requests"):
            assert needle in review
        register = (ROOT / "docs" / "experiments.yaml").read_text(encoding="utf-8")
        assert "mira-rooms-2026-11-12" in register
