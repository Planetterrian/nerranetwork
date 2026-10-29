"""Michael Kamins' room (Oct 28 2026, run 35cdf6f4): post-production hung.

Twice, right after both transcripts were written, the job went silent until
GitHub stopped it at its two-hour limit, and nothing reached the run row.
``tidy_lines`` (Oct 27, Glenn Broder) moves a stub of a few unfinished words
to the start of the same speaker's next line. Its loop used ``for ... else``:
a stub whose speaker did not come back within ``TIDY_REACH_SEC`` left by
``break``, which skips the ``else`` that moves on, so the same line was
looked at forever. Michael's transcript had such a stub. Every pass now
removes a line or moves on.
"""
from __future__ import annotations

import random
import signal
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "pipelines" / "voices"))
sys.path.insert(0, str(ROOT))


@pytest.fixture
def seconds_limit():
    """Fail instead of hanging the suite if the loop never ends."""
    def boom(*_a):
        raise TimeoutError("tidy_lines did not finish")
    old = signal.signal(signal.SIGALRM, boom)
    signal.alarm(10)
    yield
    signal.alarm(0)
    signal.signal(signal.SIGALRM, old)


def test_a_stub_whose_speaker_does_not_come_back_stays_put(seconds_limit):
    from post_interview import tidy_lines
    lines = [(0.0, "Michael", "And so the"), (30.0, "Mira", "Go on."),
             (60.0, "Michael", "Right.")]
    assert tidy_lines(lines) == lines


def test_a_stub_whose_speaker_comes_back_after_someone_else_is_out_of_reach(seconds_limit):
    from post_interview import TIDY_REACH_SEC, tidy_lines
    lines = [(0.0, "Michael", "But the"), (5.0, "Mira", "Mm."),
             (TIDY_REACH_SEC + 1.0, "Mira", "Say more."),
             (TIDY_REACH_SEC + 6.0, "Michael", "the point is this.")]
    assert tidy_lines(lines) == lines


def test_a_stub_still_joins_its_sentence_inside_the_reach(seconds_limit):
    from post_interview import tidy_lines
    assert tidy_lines([(0.0, "Michael", "And so the"), (5.0, "Mira", "Mm."),
                       (9.0, "Michael", "model forgets.")]) == [
        (5.0, "Mira", "Mm."), (9.0, "Michael", "And so the model forgets.")]


def test_any_hour_of_lines_finishes(seconds_limit):
    from post_interview import tidy_lines
    rng = random.Random(28)
    words = ["and", "so", "the", "model", "forgets", "right.", "but", "I", "think.", "yes?"]
    for _ in range(300):
        t, lines = 0.0, []
        for _ in range(rng.randint(1, 120)):
            t += rng.choice([0.5, 2.0, 4.0, 15.0, 25.0, 60.0])
            text = " ".join(rng.choice(words) for _ in range(rng.randint(1, 8)))
            lines.append((t, rng.choice(["Michael", "Mira", "Patrick"]), text))
        out = tidy_lines(lines)
        assert len(out) <= len(lines)
        # Nothing said is lost: every word is still there, in some line.
        assert sorted(" ".join(x[2] for x in out).split()) == sorted(
            " ".join(x[2] for x in lines).split())
