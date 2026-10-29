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


# ---------------------------------------------------------------------------
# The same episode, reviewed (Oct 29 2026)
# ---------------------------------------------------------------------------

def test_a_split_line_keeps_its_spaces():
    """The transcript JSON stores words stripped; a split line had come out
    "That'sareallysolidquestion.Ithinkovermycareer" (47 lines of his)."""
    from post_interview import split_on_pauses
    words = [("Great.", 15.1), ("I'm", 22.2), ("great,", 22.4), ("Mira.", 22.6),
             ("That's", 59.2), ("a", 59.5), ("really", 59.6), ("solid", 59.9),
             ("question.", 60.2), ("Self", 60.7), ("-rated", 61.0), ("P", 61.3),
             ("&L", 61.5), ("of", 61.7), ("0", 61.8), (".3%.", 62.0)]
    seg = {"start": 15.1,
           "text": " Great. I'm great, Mira. That's a really solid question. Self-rated P&L of 0.3%.",
           "words": [{"start": t, "end": t + 0.2, "word": w} for w, t in words]}
    assert split_on_pauses(seg) == [
        (15.1, "Great."), (22.2, "I'm great, Mira."),
        (59.2, "That's a really solid question. Self-rated P&L of 0.3%.")]
    # Words the text does not hold are joined with spaces, never with nothing.
    seg["text"] = "something else"
    assert split_on_pauses(seg)[2] == (59.2, "That's a really solid question. Self -rated P &L of 0 .3%.")


def test_the_post_prints_the_transcript_of_the_edit():
    src = (ROOT / "pipelines" / "voices" / "publish_episode.py").read_text(encoding="utf-8")
    body = src.split("def write_episode_digest")[1].split("\ndef ")[0]
    assert 'pkg.get("edit_transcript") or pkg.get("transcript_cleaned")' in body


def test_the_shared_moment_points_into_the_published_file():
    import publish_episode as pe

    class Show:
        audio_subdir = "digests/age_of_ai_test_nowhere"

        @staticmethod
        def post_url(n):
            return f"https://nerranetwork.com/blog/age_of_ai/ep{n:03d}.html"
    pkg = {"clip_suggestions": [{"start": 1146, "end": 1218, "title": "Gen Z"}]}
    run = {"grok_session_log": {"tracks": {"edit": {"clock": [[45.6, 2601.0, 65.2, 0.9]]}}}}
    url, title = pe.clip_link(pkg, Show, 12, run=run)
    assert url.endswith("#t=1055") and title == "Gen Z"   # 65.2 + (1146 - 45.6) * 0.9
    url, _ = pe.clip_link(pkg, Show, 12)
    assert url.endswith("#t=1146")


def test_his_own_short_question_is_not_taken_for_her_echo():
    from post_interview import strip_echo_lines
    out, dropped = strip_echo_lines(
        "[27:22] Michael: I hope that answers your question.\n"
        "[27:24] Michael: Does that make sense?\n"
        "[27:29] Mira: It does. Does early work done under that old resume system count against someone, "
        "or does it start clean?\n"
        "[28:45] Mira: What does that ask of someone already sending out 40 applications a week?\n"
        "[28:50] Michael: What does what part?\n", "Mira")
    assert dropped == 0 and "Does that make sense?" in out and "What does what part?" in out


def test_a_muted_speaker_is_not_in_the_transcript_of_the_edit():
    from edit_transcript import transcript_of_the_edit
    room = ("[24:07] Michael: And just the scoring mechanism attached to them.\n"
            "[24:17] Michael: You cut out for a second. Can you ask that question again?\n"
            "[24:18] Mira: Keyword filters deciding who gets seen.\n")
    cuts = [{"from": "mix:clean", "start": 1440.0, "end": 1470.0,
             "mute": [{"role": "guest", "from": 1456.95, "to": 1459.2}]}]
    out = transcript_of_the_edit(room, cuts, [30.0])
    assert "You cut out" not in out
    assert "Keyword filters" in out and "scoring mechanism" in out
