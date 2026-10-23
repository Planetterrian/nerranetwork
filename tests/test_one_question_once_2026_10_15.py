"""Oct 15 2026, Patrick: Mira must never ask the same question twice.

Piper Martz was asked the show's question ("What's the one bet you're making
for the next twelve months that you cannot prove yet?") at the end of her
first session and again, word for word, in her closing session. The closing
session's half is fixed in fire_interviews.already_answered (tested in
test_closing_sessions_2026_10_14.py). This is the room's half, for any
interview: it records each closing question Mira asks, tells her after each
one what is done, carries the list through a reconnect, and tells her at once
if she asks one again.
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCENARIO = (ROOT / "voximplant" / "scenarios" / "age_of_ai_interview.js").read_text(encoding="utf-8")


def _fn(name: str) -> str:
    i = SCENARIO.index("function " + name + "(")
    return SCENARIO[i:SCENARIO.index("\n}\n", i)]


def _questions() -> list:
    i = SCENARIO.index("const ROUND_QUESTIONS = [")
    block = SCENARIO[i:SCENARIO.index("];", i)]
    out = []
    for label, pattern, flags in re.findall(r'\["([^"]+)", /(.+?)/(i?)(?:, "[^"]*")?\]', block):
        out.append((label, re.compile(pattern, re.I if flags else 0)))
    return out


class TestTheRoomKnowsWhatSheAsked:
    def test_every_line_of_hers_is_checked(self):
        assert "noteRoundQuestion(text);" in _fn("remember")

    def test_the_closing_questions_are_recognised_as_she_says_them(self):
        qs = dict(_questions())
        assert len(qs) == 7
        said = {
            "the show's own question":
                "What's the one bet you're making for the next 12 months that you cannot prove yet?",
            "a book they would recommend": "A book you would recommend and in a sentence why?",
            "who you should interview next": "What's one person you think I should interview next?",
            "the best advice they were ever given": "What's the best piece of advice you were ever given?",
            "who has inspired them most": "Who's the person who's inspired you most?",
            "how being interviewed by an AI was, and one improvement":
                "How was the experience of being interviewed by an AI, and what's one thing we could improve?",
            "whether they would like a follow-up interview":
                "Would you like to come back for a follow-up interview in six months to a year?",
        }
        for label, line in said.items():
            assert qs[label].search(line), label

    def test_her_reaction_to_an_answer_is_not_mistaken_for_the_question(self):
        for label, rx in _questions():
            for line in ("That's the bet that matters most.", "That's the bet.",
                         "I like that you gave me a little community to choose from."):
                assert not rx.search(line), (label, line)

    def test_she_is_told_what_is_done_after_each_one(self):
        body = _fn("noteRoundQuestion")
        assert "roundAsked[label] = elapsedMin();" in body
        assert "Never ask\" +\n        \" any of these again, in any wording." in body

    def test_a_repeat_is_caught_and_not_nagged(self):
        body = _fn("noteRoundQuestion")
        assert "a second time" in body and "do not ask it a third time" in body
        assert "roundRepeats > 3" in body

    def test_the_list_survives_a_reconnect(self):
        body = _fn("handoverNote")
        assert "Object.keys(roundAsked).join(\"; \")" in body
        assert "never" in body and "to be asked again" in body
