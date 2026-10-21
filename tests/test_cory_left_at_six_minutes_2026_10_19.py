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
        opening = _section("HOW TO OPEN", "THEIR SUBJECT, FAST")
        assert "Two short turns" in opening
        assert "ask your first real question, about the subject they came to discuss" in opening
        assert "The tagline ({{opening_line}}) belongs to the produced episode" in opening

    def test_no_minutes_of_warm_up(self):
        assert "Three or four minutes about the person before the subject" not in FLAT
        assert "At most one warm-up question about the person" in FLAT
        assert "By the second minute you are on the subject they came for" in FLAT


class TestTheQuestions:
    def test_concrete_not_literary(self):
        assert "Ask like a practitioner, in their terms" in FLAT
        # Oct 21 2026: the bad question is in docs/mira_craft_notes.md, not
        # in the prompt (de-seed by shape, never with a quotable example).
        assert "trap or a doorway" not in FLAT


class TestWhenAGuestSaysItIsntWorking:
    def test_change_course_and_hand_them_their_subject(self):
        block = _section("IT IS THEIR HOUR, AND YOU TOLD THEM SO", "THE PERSON, IN SERVICE OF THE SUBJECT")
        assert "one plain acknowledgment, then their subject, in their words" in block
        assert "If they want to stop, thank them warmly and tell them they can simply leave" in block
        assert "Let's go straight to what you came to talk about" not in block


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
