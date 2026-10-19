"""Oct 19 2026, Cory O'Daniel (Massdriver), who has been on many podcasts.

He got forty seconds of who-I-am and how-this-works before his first
question, then five minutes of biography and abstract questions ("did you see
that as a trap or a doorway?", "did that unease ever go away?"). He said "this
question sucks", then "it doesn't feel like a conversation... it feels so
mechanical"; Mira agreed it was mechanical, asked him what would make it feel
less so, offered to stop, and he left at six minutes. These tests hold the
prompt changes that answer each of those moments.
"""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PROMPT = (ROOT / "pipelines" / "voices" / "prompts" / "mira_system_prompt.txt").read_text(encoding="utf-8")
FLAT = " ".join(PROMPT.split())


def _section(start: str, end: str) -> str:
    return FLAT[FLAT.index(start):FLAT.index(end)]


class TestTheOpening:
    def test_two_beats_and_then_their_subject(self):
        opening = _section("HOW TO OPEN", "GET TO THEIR SUBJECT FAST")
        assert "Two short beats" in opening
        assert "ask your first real question, about the subject they came to discuss" in opening
        assert "Nothing else about the format" in opening

    def test_no_minutes_of_warm_up(self):
        assert "Three or four minutes about the person before the subject" not in FLAT
        assert "At most one warm-up question about the person" in FLAT
        assert "By the second minute you are on the subject they came to discuss" in FLAT


class TestTheQuestions:
    def test_concrete_not_literary(self):
        assert "ASK LIKE A PRACTITIONER, NOT A POET" in FLAT
        assert "trap or a doorway" in FLAT


class TestWhenAGuestSaysItIsntWorking:
    def test_change_course_and_hand_them_their_subject(self):
        block = _section("WHEN A GUEST SAYS IT ISN'T WORKING", "THE SUBJECT THEY CAME FOR IS THE SPINE")
        assert "Never agree that you are mechanical" in block
        assert "never ask them to diagnose the interview for you" in block
        assert "Let's go straight to what you came to talk about" in block
        assert "Only if they say they want to stop" in block


class TestPatrickAnswersHimHimself:
    def test_his_domains_are_never_auto_replied(self):
        import sys
        sys.path.insert(0, str(ROOT))
        from pipelines.producer.policy import load_policy
        from pipelines.producer.guest_reply import _never_auto
        policy = load_policy()
        assert _never_auto({"from_email": "cory@massdriver.cloud"}, policy)
        assert _never_auto({"from_email": "press@massdrivermedia.com"}, policy)
        assert not _never_auto({"from_email": "jon@genaipi.org"}, policy)

    def test_the_guest_reply_path_checks_it(self):
        src = (ROOT / "pipelines" / "producer" / "guest_reply.py").read_text(encoding="utf-8")
        assert "elif _never_auto(inbound, policy):" in src
