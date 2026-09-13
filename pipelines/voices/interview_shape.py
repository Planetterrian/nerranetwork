"""What the guest asked the interview to be.

Sept 13 2026. Three answers on the application — length, how deep on the
subject, how personal — used to go nowhere: length was a constant in the
Voximplant scenario, depth was whatever the research pass produced, and the
personal question was not asked at all. They now shape the number of
questions Mira prepares, the instructions in her system prompt, and the clock
the room paces to.

Every field is optional. A guest with no preference gets what the show did
before: 45 minutes, standard depth, a light touch on the personal.
"""

from __future__ import annotations

from typing import Any, Dict

DEFAULT_MINUTES = 45
DEFAULT_DEPTH = "standard"
DEFAULT_PERSONAL = "light"

# Question count is the one thing that must track length, because Mira works
# through her set and a twenty-minute conversation with eight prepared
# questions becomes a survey. Roughly four minutes per question, which is what
# the first two episodes actually ran.
_QUESTION_RANGE = ((20, "4-5"), (30, "5-6"), (45, "6-8"), (60, "8-10"), (90, "10-14"))

_DEPTH_NOTE = {
    "accessible": ("The guest asked for an accessible conversation. Assume a "
                   "listener who is smart but new to this field: ask for the "
                   "plain version, and when a term of art appears, ask them to "
                   "define it rather than defining it yourself."),
    "standard": ("The guest asked for a standard depth: an informed listener, "
                 "some technical detail, no jargon left unexplained."),
    "deep": ("The guest asked you to go deep. Assume expertise on both sides. "
             "Skip the definitional questions, go to the specifics, the "
             "numbers and the live disagreements in their field, and stay on "
             "one thread longer than feels comfortable."),
}

_PERSONAL_NOTE = {
    "none": ("The guest asked to keep this to the work. Do not ask about their "
             "upbringing, family, health, money or private life, and if they "
             "volunteer something personal, let it sit rather than following "
             "it. This is a boundary they set in writing; it is not a "
             "conversational hurdle to clear."),
    "light": ("The guest is open to a light personal thread: how they got "
              "here, what drew them to this work, what it costs them. One or "
              "two questions, early, then back to the work. Do not press."),
    "open": ("The guest said the personal side is part of the story. You may "
             "ask how this work has changed them, what they have given up for "
             "it, what they believe that their colleagues do not. Still one "
             "question at a time, and still stop at the first sign they would "
             "rather not."),
}


def planned_minutes(interview: Dict[str, Any], app: Dict[str, Any]) -> int:
    for value in (interview.get("duration_min"), app.get("desired_minutes")):
        try:
            minutes = int(value)
        except (TypeError, ValueError):
            continue
        if 15 <= minutes <= 90:
            return minutes
    return DEFAULT_MINUTES


def depth(app: Dict[str, Any]) -> str:
    return app.get("depth") if app.get("depth") in _DEPTH_NOTE else DEFAULT_DEPTH


def personal_depth(app: Dict[str, Any]) -> str:
    value = app.get("personal_depth")
    return value if value in _PERSONAL_NOTE else DEFAULT_PERSONAL


def question_count(minutes: int) -> str:
    for limit, spread in _QUESTION_RANGE:
        if minutes <= limit:
            return spread
    return _QUESTION_RANGE[-1][1]


def shape_block(interview: Dict[str, Any], app: Dict[str, Any]) -> str:
    """The guest's own answers, as instructions for Mira."""
    minutes = planned_minutes(interview, app)
    lines = [
        "WHAT THIS GUEST ASKED FOR (they answered these on the application):",
        f"- Length: about {minutes} minutes.",
        f"- Subject depth: {_DEPTH_NOTE[depth(app)]}",
        f"- Personal questions: {_PERSONAL_NOTE[personal_depth(app)]}",
    ]
    off = (app.get("off_limits") or "").strip()
    if off:
        lines.append("- Off limits, in their words: " + off
                     + ". Do not raise it. If they raise it themselves, follow "
                       "only as far as they take it.")
    return "\n".join(lines) + "\n"
