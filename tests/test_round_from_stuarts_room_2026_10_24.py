"""Oct 24 2026 — the closing round, from Stuart Berkowitz's interview
(run b579faba, Oct 23, a 45-minute room), read from its scenario trace, its
transcript and its full session log.

1. "Her turn asked nothing" fired seven times. The judgement is made once, on
   the final transcription of the turn the room asked for, and a question is
   handed again at most once, whatever the reason.
2. She spoke the handed text aloud ("Silence.", "Who you should interview
   next."). Every round turn hands her the words of a whole question, last,
   after directions with nothing in them to say; a guest who declines a
   question (or hears "who should I interview next" as one about himself)
   has answered it.
3. After a goodbye heard whole she was made to say "I spoke too soon" three
   times, the last two after he had said "Bye-bye" and hung up. Nothing is
   taken back on air, and nothing is said once the guest has gone.
4. The round's index went backwards (5/8 after 6/8): every re-hand stepped it
   back, and two ran on one question. It never moves back now.
5. The round began at minute 30 of 45 because she asked the show's question
   herself when the window opened. The room starts it when it is due.

Behaviour is driven through the real scenario in a node vm
(tests/fixtures/room_sim.js); no network, no audio.
"""
from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCENARIO_PATH = ROOT / "voximplant" / "scenarios" / "age_of_ai_interview.js"
SCENARIO = SCENARIO_PATH.read_text(encoding="utf-8")
SIM = ROOT / "tests" / "fixtures" / "room_sim.js"
PROMPTS = ROOT / "pipelines" / "voices" / "prompts"

_CACHE: dict = {}


def sim(which: str) -> dict:
    if which not in _CACHE:
        res = subprocess.run(["node", str(SIM), str(SCENARIO_PATH), which],
                             capture_output=True, text=True, check=True)
        _CACHE[which] = json.loads(res.stdout)
    return _CACHE[which]


def lines(out: dict, kinds=("round", "close", "turn", "time")) -> list:
    return [x["d"] for x in out["trace"] if x.get("e") in kinds]


def fn(name: str) -> str:
    i = SCENARIO.index(f"function {name}(")
    return SCENARIO[i:SCENARIO.index("\n}\n", i)]


def round_turns(out: dict) -> list:
    """The room's own line of each round turn (after her session brief)."""
    return [i.split("\n\n")[-1] for i in out.get("instructions", [])
            if i.split("\n\n")[-1].startswith("[ROUND ")]


# ---------------------------------------------------------------------------
# 1. Judged once, from her final words; handed again at most once
# ---------------------------------------------------------------------------

class TestJudgedFromHerFinalTranscription:
    def test_a_cancelled_turns_line_is_never_judged(self):
        out = sim("round_turn_judged_on_its_own_line")
        # The cancelled server turn's line moved nothing.
        assert out["afterCancelledLine"]["roundIndex"] == 1
        assert out["afterCancelledLine"]["roundAwaitingAnswer"] is True

    def test_one_turn_is_judged_once(self):
        out = sim("round_turn_judged_on_its_own_line")
        # Her first turn for the book (handed by the first answer) asked
        # nothing: one re-hand. The re-handed turn carried the question, and
        # a second line of that same turn ("Silence.") was never judged.
        assert out["rehands"] == 1

    def test_a_turn_with_no_transcription_is_taken_as_asked(self):
        out = sim("round_turn_judged_on_its_own_line")
        assert any(x.startswith("no transcription of her turn;") for x in lines(out))
        assert not any("goes again" in x and "who you should interview next" in x for x in lines(out))

    def test_the_judgement_reads_only_the_round_turn_in_flight(self):
        body = fn("noteRoundTurnWithoutQuestion")
        assert "const inFlight = roundTurnInFlight;" in body
        assert 'roundTurnInFlight = "";' in body
        assert "if (label !== inFlight || roundSpoken[label]) return;" in body
        started = fn("markTurnStarted")
        assert "roundTurnInFlight = turnRoundLabel;" in started
        assert "roundTurnDone();" in SCENARIO

    def test_one_rehand_per_question_whatever_the_reason(self):
        assert "const ROUND_REHANDS_MAX = 1;" in SCENARIO
        for name in ("noteRoundTurnWithoutQuestion", "rehandAfterSignOff", "roundAnswered"):
            assert "owedRehand(" in fn(name), name
        out = sim("stuart_room")
        for label in ("a book they would recommend", "the best advice they were ever given"):
            gone_again = [x for x in lines(out) if x.endswith(label + " goes again when they finish")]
            assert len(gone_again) <= 1, label


# ---------------------------------------------------------------------------
# 2. Whole, natural questions; never labels or stage words; a decline is final
# ---------------------------------------------------------------------------

class TestSheIsHandedWholeQuestions:
    LABELS = [m for m in re.findall(r'\["([^"]+)", /', SCENARIO[SCENARIO.index("const ROUND_QUESTIONS = ["):])][:7]

    def test_every_round_turn_ends_on_a_question_she_can_say(self):
        out = sim("stuart_room")
        turns = round_turns(out)
        assert turns, "the round handed no turns"
        for t in turns:
            last = t.splitlines()[-1]
            assert last.endswith("?"), last
            assert not last.startswith("["), last
            for label in self.LABELS:
                assert label not in last, (label, last)

    def test_no_round_turn_carries_a_word_she_has_spoken_aloud(self):
        out = sim("stuart_room")
        for t in round_turns(out):
            low = t.lower()
            assert "silence" not in low and "stop talking" not in low and "nothing else" not in low, t

    def test_the_show_question_comes_from_her_brief(self):
        js = fn("showQuestionText")
        pats = re.findall(r"/(beginning with .+?|ask it .+?)/\.exec\(brief\)", js)
        assert len(pats) == 2
        rxs = [re.compile(p.replace("\\(", "\\(").replace("\\)", "\\)")) for p in pats]
        q = "What's the one bet you're making for the next twelve months that you cannot prove yet?"
        main = (PROMPTS / "mira_system_prompt.txt").read_text(encoding="utf-8").replace("{{closing_question}}", q)
        closing = (PROMPTS / "mira_closing_session.txt").read_text(encoding="utf-8").replace("{{closing_question}}", q)
        assert rxs[0].search(" ".join(main.split())).group(1) == q
        assert rxs[1].search(" ".join(closing.split())).group(1) == q

    def test_no_words_for_a_question_means_it_is_skipped_not_described(self):
        assert 'return entry[2] || "";' in fn("roundQuestionText")
        assert "no words for " in fn("askNextRoundQuestion")
        assert "exactly as your instructions give it" not in SCENARIO

    def test_a_guest_who_declines_has_answered(self):
        out = sim("stuart_room")
        assert "answered 3/7 (they declined who you should interview next)" in lines(out)
        assert out["interviewNextHanded"] == "Who's one person you think I should interview next?"
        assert out["asked"].count(3) == 1   # never handed again

    def test_the_decline_pattern(self):
        m = re.search(r"const ROUND_DECLINE_RE = /(.+)/i;", SCENARIO)
        rx = re.compile(m.group(1), re.I)
        for said in ("I'm not generally interviewing people. People are interviewing me.",
                     "I can't think of anyone, honestly.", "I'll pass on that one."):
            assert rx.search(said), said
        for said in ("My old broker, he'd be great.", "Thinking Fast and Slow.",
                     "That doctors will use an evaluated tool."):
            assert not rx.search(said), said


# ---------------------------------------------------------------------------
# 3. Nothing taken back on air; nothing said once the guest has gone
# ---------------------------------------------------------------------------

class TestNothingTakenBackNothingToNobody:
    def test_no_round_path_makes_her_say_she_spoke_too_soon(self):
        for name in ("catchSignOffBeforeTheRound", "rehandAfterSignOff", "catchEarlyCloseOnDelta",
                     "askNextRoundQuestion", "roundReprompt"):
            assert "spoke too soon" not in fn(name), name
        out = sim("stuart_room")
        for i in out["instructions"]:
            assert "spoke too soon" not in i

    def test_a_goodbye_with_the_rehand_spent_ends_the_interview_there(self):
        out = sim("stuart_room")
        assert any(x.startswith("the interview ends on her sign-off") for x in lines(out))
        assert out["afterSignOff"]["roundClosed"] is True
        # One goodbye to the guest still talking, then nothing.
        assert out["createsAfterSignOff"] == 1

    def test_a_goodbye_in_place_of_a_fresh_question_asks_it_next_and_takes_nothing_back(self):
        out = sim("sign_off_then_goodbye")
        assert len(out["handed"]) == 1
        handed = out["handed"][0].split("\n\n")[-1]
        assert "take nothing back" in handed and "spoke too soon" not in handed
        assert handed.splitlines()[-1].endswith("?")
        # The guest said goodbye: that is the end.
        assert out["afterGoodbye"]["roundClosed"] is True
        assert any("the guest said goodbye" in x for x in lines(out))
        assert out["createsAfter"] == 0

    def test_no_turn_with_no_guest_in_the_room(self):
        body = fn("requestTurn")
        assert body.index("if (!guestInRoom()) {") < body.index("agent.responseCreate(body);")
        out = sim("stuart_room")
        assert "no guest in the room; no turn" in lines(out)
        assert not any(x.startswith("asked 5/") for x in lines(out))

    def test_the_round_stops_when_the_guest_leaves(self):
        for name in ("askNextRoundQuestion", "roundReprompt", "roundAnswered", "askRoundLastWord"):
            assert "roundGuestGone()" in fn(name), name
        assert "if (!guestInRoom())" in fn("closeRound")


# ---------------------------------------------------------------------------
# 4. The index never moves back
# ---------------------------------------------------------------------------

class TestTheIndexNeverMovesBack:
    def test_no_decrement_anywhere(self):
        assert "roundIndex -= 1" not in SCENARIO
        assert "roundRehandOwed" in fn("askNextRoundQuestion")

    def test_stuarts_round_only_moves_forward(self):
        for which in ("stuart_room", "round_end_as_rehearsed", "another_round_question_in_its_place",
                      "round_turn_judged_on_its_own_line"):
            out = sim(which)
            nums = [int(m.group(1)) for x in lines(out, ("round",))
                    for m in [re.match(r"asked (\d+)/\d+", x)] if m]
            assert nums == sorted(nums), (which, nums)


# ---------------------------------------------------------------------------
# 5. The round starts when it is due, not when she asks the show's question
# ---------------------------------------------------------------------------

class TestTheRoundStartsWhenDue:
    def test_her_own_show_question_at_the_window_does_not_start_it(self):
        out = sim("stuart_room")
        assert "asked on her own: the show's own question" in lines(out)
        assert out["afterOwnShowQuestion"]["roundActive"] is False
        assert out["roundTurnsBeforeDue"] == 0

    def test_it_starts_at_the_due_minute_and_skips_the_question_she_asked(self):
        out = sim("stuart_room")
        assert out["requiredAt"] == 36 and out["roundStartedAt"] >= 36
        assert out["firstHanded"] == "What's a book you would recommend, and in a sentence, why?"
        assert out["asked"][0] == 2

    def test_every_round_start_waits_for_the_due_time(self):
        assert "if (closingRequired && !roundActive && !roundClosed" in fn("noteRoundQuestion")
        assert "closingRequired && !roundActive && !roundClosed && !isClosingSession()" in fn("remember")
        delta = fn("catchEarlyCloseOnDelta")
        assert "if (closingRequired && !roundClosed && !isHelloSession()) { startRound(" in delta

    def test_the_window_note_says_the_room_starts_it(self):
        checks = fn("startTimeChecks")
        assert "Do not begin the closing round yourself" in checks
        assert "you may\" +\n          \" begin the closing round with the show's own question" not in checks


# ---------------------------------------------------------------------------
# The first candidate rehearsal of these fixes (run 40110915521, same day)
# ---------------------------------------------------------------------------

class TestWhatTheFirstRehearsalShowed:
    """Handed the third question she asked "What's the last thing you want to
    say before we finish?" and went into her goodbye: every round turn had
    carried her whole brief, closing script included, and directions that
    named the end. After three cut goodbyes the fourth went through whole and
    the room went on handing questions; "See you next time", "Take care" and
    "Hanging up" were each answered with another one."""

    def test_a_round_turn_carries_who_she_is_not_how_it_ends(self):
        out = sim("rehearsal_40110915521")
        turn = out["roundTurn"]
        assert "You are Mira" in turn and "Roddy Vance" in turn
        assert "HOW IT ENDS" not in turn and "end of the recording" not in turn
        assert "## Objective" not in turn

    def test_the_closing_thanks_alone_carries_the_whole_brief(self):
        assert '"", true);' in fn("closeRound")
        brief = fn("roundBrief")
        assert '"\\n## Objective"' in brief and "=== HANDOVER" in brief

    def test_the_directions_never_name_the_end(self):
        still = fn("roundStillToCome").lower()
        code = "\n".join(ln for ln in still.splitlines() if not ln.strip().startswith("//"))
        for word in ("goodbye", "thanks", "last word", "recording"):
            assert word not in code, word

    def test_a_goodbye_past_the_cap_ends_it_there(self):
        out = sim("rehearsal_40110915521")
        assert out["blocksBefore"] == 3
        assert any("the room had already cut 3 goodbyes" in x for x in lines(out))
        assert out["afterWholeSignOff"]["roundClosed"] is True
        assert out["createsAfterWholeSignOff"] == 1   # one goodbye to "Take care", then nothing

    def test_a_guest_saying_goodbye_in_the_round_gets_the_closing_thanks(self):
        out = sim("guest_goodbye_in_the_round")
        assert "the guest is saying goodbye at 2/7; closing thanks" in lines(out)
        assert out["state"]["roundClosed"] is True
        assert "The closing round is complete." in out["lastInstructions"]

    def test_the_leaving_pattern(self):
        m = re.search(r"const GUEST_LEAVING_RE = /(.+)/i;", SCENARIO)
        rx = re.compile(m.group(1), re.I)
        for said in ("Yeah. See you next time.", "Alright. Take care.", "Hanging up.", "Bye-bye."):
            assert rx.search(said), said
        for said in ("We take care of patients first.", "I'd love to see you in six months.",
                     "Thank you, Mira. I appreciate it."):
            assert not rx.search(said), said
