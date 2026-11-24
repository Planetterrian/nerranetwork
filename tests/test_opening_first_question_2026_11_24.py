"""Nov 24 2026 (Patrick): Mira's opening is two turns, and her first real
question comes inside the first minute.

Since Oct 1, six of about 24 joined rooms ended inside seven minutes, three of
them during or just after the opening; every room opened on a ~45 s speech
about how the hour works, then a "does that sound good" check, and only then
the first question. The format now lives on the studio page and in the
reminder (``engine.brand.MIRA_HOUR_PARTS``); the spoken opening is a hello,
then who she is in two short sentences and the first question. The parts of
the hour are named as the room reaches them (the interview plan's move).

This is a brief and room change: it ships to a booked guest only after a
two-arm rehearsal PASS and one listen by Patrick.
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PROMPT = (ROOT / "pipelines" / "voices" / "prompts" / "mira_system_prompt.txt").read_text(encoding="utf-8")
SCENARIO = (ROOT / "voximplant" / "scenarios" / "age_of_ai_interview.js").read_text(encoding="utf-8")
FLAT = re.sub(r"\s+", " ", PROMPT)
OPENING = FLAT[FLAT.index("HOW TO OPEN"):FLAT.index("THEIR SUBJECT, FAST")]


def test_two_turns_and_the_first_minute():
    assert "Two short turns" in OPENING
    assert "first real question comes inside the first minute" in OPENING
    assert "3. " not in OPENING.split("{{cohost_intro_step}}")[0]


def test_no_format_recital_or_check_question():
    for gone in ("How the hour works", "sounds good", "two or three parts ahead",
                 "any question can be skipped", "ask their patience"):
        assert gone not in OPENING, gone


def test_she_never_guesses_their_time_of_day():
    assert "never guess their time of day" in OPENING


def test_the_scenario_notes_match_the_brief():
    assert "who you are in two short sentences, then\" +" in SCENARIO
    assert "Who you are and your first real question come on your" in SCENARIO
    assert "How the hour works comes on your next turn" not in SCENARIO


def test_the_brief_stays_under_its_budget():
    assert len(PROMPT.split()) < 1600
