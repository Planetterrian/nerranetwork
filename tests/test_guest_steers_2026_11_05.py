"""What the first week of studio presses taught (Nov 3-4 2026, reviewed Nov 5).

Priyanka Sharma pressed Move on four times and typed "I'd like to talk about
the entrepreneurship in the industry"; every press was acked "applied" and
Mira stayed on the board-of-pharmacy question, re-asking it three ways, until
Priyanka SAID the subject aloud. A guest who presses is quiet (reading,
typing), so the request waited for the dead-air nudge, and that turn also
carried the note "put your last question to them again". The move-on also
named no subject to leave. Then "I'd like to wrap up the interview now" went
unheard, so the room cut her goodbye twice and she asked three more
questions. She asked twice, out loud, for a question to be repeated.

These guards hold: a press in a silence takes her turn at once; a queued
press replaces the nudge's note; a guest still talking keeps the floor; the
move-on and the repeat hand her her own last question in words; the studio's
new Repeat and Wrap-up buttons reach the room and the Worker keeps them; the
interview as the object of a stop is a stop.
"""
from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCENARIO_PATH = ROOT / "voximplant" / "scenarios" / "age_of_ai_interview.js"
SCENARIO = SCENARIO_PATH.read_text(encoding="utf-8")
SIM = ROOT / "tests" / "fixtures" / "room_sim.js"
STUDIO = (ROOT / "age-of-ai-studio.html").read_text(encoding="utf-8")
WORKER = (ROOT / "workers" / "voices" / "src" / "index.ts").read_text(encoding="utf-8")
NODE = shutil.which("node")
needs_node = pytest.mark.skipif(NODE is None, reason="node is not installed")

LAST_Q = "Has any board pushed back on what you're proposing?"


def sim(which: str) -> dict:
    out = subprocess.run([NODE, str(SIM), str(SCENARIO_PATH), which],
                         capture_output=True, text=True, timeout=60)
    assert out.returncode == 0, out.stderr[-2000:]
    return json.loads(out.stdout)


def _regex(name: str) -> re.Pattern:
    head = f"const {name} = /"
    rx = SCENARIO[SCENARIO.index(head) + len(head):]
    return re.compile(rx[:rx.index("/i;")].replace("\\u2014", "—"), re.I)


@needs_node
class TestAPressInASilenceTakesHerTurn:
    def test_move_on_while_quiet_goes_now_without_the_nudge(self):
        out = sim("steer_while_quiet")
        assert out["events"] == ["create"]
        assert out["notes"] == []          # no "ask it again" note beside it
        assert "leave this subject" in out["lastInstructions"]
        assert [a["status"] for a in out["acks"]] == ["queued", "applied"]
        assert any(t["d"] == "the floor is free; her turn now" for t in out["trace"])

    def test_a_queued_press_replaces_the_nudge_note(self):
        out = sim("steer_at_dead_air")
        assert out["notes"] == []
        assert "leave this subject" in out["lastInstructions"]
        assert not any("nudge 1" in t["d"] for t in out["trace"])

    def test_a_guest_still_talking_keeps_the_floor(self):
        out = sim("steer_waits_for_speech")
        assert out["eventsWhileSpeaking"] == []
        assert out["events"] == ["create"]
        assert "leave this subject" in out["lastInstructions"]
        assert not any(t["d"] == "the floor is free; her turn now" for t in out["trace"])

    def test_a_typed_topic_while_quiet_goes_now(self):
        out = sim("steer_topic_while_quiet")
        assert out["events"] == ["create"]
        assert "entrepreneurship in the industry" in out["lastInstructions"]
        # The typed words never reach the trace.
        assert "entrepreneurship" not in json.dumps(out["trace"])


@needs_node
class TestSheIsHandedHerOwnQuestion:
    def test_move_on_names_the_question_to_leave(self):
        ins = sim("steer_while_quiet")["lastInstructions"]
        assert "“" + LAST_Q + "”" in ins
        assert "not another angle on the same subject" in ins

    def test_repeat_hands_back_the_question(self):
        out = sim("steer_repeat")
        assert "“" + LAST_Q + "”" in out["lastInstructions"]
        assert "more simply" in out["lastInstructions"]
        assert out["feedback"][0]["kind"] == "repeat"


@needs_node
class TestTheWrapUpButton:
    def test_it_is_a_stop_and_the_closing_round_begins(self):
        out = sim("steer_wrap_up_button")
        assert out["askedToStop"] is True
        assert out["state"]["roundActive"] is True
        assert out["feedback"][0] == {"kind": "wrap_up", "by": "guest", "at_min": out["feedback"][0]["at_min"],
                                      "text": "", "applied": True, "held": False, "wrap_up": True}
        assert out["acks"][-1] == {"nn": 1, "ack": "wrap_up", "status": "applied"}


class TestTheInterviewAsTheObjectOfAStop:
    STOP = _regex("GUEST_STOP_RE")

    def test_her_words_are_a_stop(self):
        for text in ("I'd like to wrap up the interview now.",
                     "can we end the interview here",
                     "let's wrap up the conversation",
                     "let's stop the recording"):
            assert self.STOP.search(text), text

    def test_a_subject_or_a_later_intention_is_not(self):
        for text in ("I'd like to end the interview with a story about my dad",
                     "Let's try to talk about entrepreneurship in this space and then we can wrap up the interview.",
                     "how would we end the interview"):
            assert not self.STOP.search(text), text


class TestTheStudioAndTheWorker:
    def test_the_page_has_the_four_actions(self):
        for bid, label in (("fbMove", "New subject"), ("fbRepeat", "Repeat the question"),
                           ("fbGood", "Good question"), ("fbWrap", "Let's wrap up")):
            assert f'id="{bid}">{label}</button>' in STUDIO
        assert 'sendFeedback("repeat")' in STUDIO
        assert 'sendFeedback("wrap_up")' in STUDIO
        # Wrapping up cannot be taken back: it takes a second press.
        assert "Press again to wrap up" in STUDIO

    def test_the_room_and_the_worker_accept_the_new_kinds(self):
        assert "repeat: true, wrap_up: true" in SCENARIO
        assert '["good", "move_on", "topic", "repeat", "wrap_up"]' in WORKER


class TestTheTestRoomCarriesThePlan:
    """Nov 5 2026: the person's test room compiled Mira's prompt with no brief,
    so it carried no prepared questions and no interview plan."""

    def test_the_invite_room_gets_the_latest_brief_and_its_plan(self, monkeypatch, tmp_path):
        import sys
        sys.path.insert(0, str(ROOT / "pipelines" / "voices"))
        import rehearsal
        brief = {"likely_questions": [{"question": "What changed?", "section": "core"},
                                      {"question": "Where did it start?", "section": "opening"}]}
        monkeypatch.setattr(rehearsal, "_source_application",
                            lambda email: {"id": "a", "email": email, "name": "Some One"})
        monkeypatch.setattr(rehearsal, "ensure_invite_interview",
                            lambda src, m: {"interview": {"id": "iv", "show": "age_of_ai"}})
        monkeypatch.setattr(rehearsal, "_latest_brief", lambda src: brief)
        seen = {}
        monkeypatch.setattr(rehearsal, "invite_prompt",
                            lambda src, m, b=None: seen.setdefault("brief", b) and "PROMPT")
        monkeypatch.setattr(rehearsal, "build_run_row",
                            lambda **kw: seen.setdefault("row", kw) and {"grok_session_log": {"rehearsal": {}}})
        monkeypatch.setattr(rehearsal, "create_run", lambda row: {"id": "run-1", **row})
        monkeypatch.setattr(rehearsal, "wait_for_join", lambda run_id, m: {})
        rehearsal.invite_one(email="someone@example.com", minutes=15, scenario="deployed",
                             out_dir=tmp_path, wait_minutes=0, send=lambda *a: None)
        assert seen["brief"] is brief
        plan = seen["row"]["plan"]
        assert [q["question"] for q in plan] == ["Where did it start?", "What changed?"]



@needs_node
class TestAPressWhileSheSpeaks:
    """Nov 5 2026 (Patrick's test room): a press made while she talked waited
    for the guest's answer to the question being left."""

    def test_it_takes_her_turn_when_her_line_ends(self):
        out = sim("steer_while_she_speaks")
        assert out["eventsWhileSpeaking"] == []
        assert out["events"] == ["create"]
        assert "leave this subject" in out["lastInstructions"]
        assert out["steerQueued"] is False

    def test_the_guest_starting_to_talk_keeps_the_floor(self):
        out = sim("steer_she_speaks_then_guest")
        assert out["events"] == []
        assert out["steerQueued"] is True


class TestANoteIsQuiet:
    def test_the_note_line_never_announces_itself(self):
        start = SCENARIO.index("function topicSteer(text) {")
        body = SCENARIO[start:SCENARIO.index("\n}\n", start)]
        assert "wanted to get to" not in body
        assert "never say that they sent it" in body
        assert "follow-up" in body

    def test_no_round_note_after_the_closing_thanks(self):
        i = SCENARIO.index('trace("round", "asked again: "')
        assert "if (roundClosed || closingThanksQueued) return;" in SCENARIO[i - 400:i]


class TestThePageNeverLosesANote:
    PAGE = (ROOT / "age-of-ai-studio.html").read_text(encoding="utf-8")

    def test_a_note_is_never_refused_by_the_cooldown(self):
        fn = self.PAGE[self.PAGE.index("function sendFeedback(kind, text) {"):]
        fn = fn[:fn.index("function onRoomMessage")]
        assert 'kind !== "good" && kind !== "topic" && Date.now() < fbCooldown' in fn

    def test_the_box_keeps_its_words_when_nothing_was_sent(self):
        assert 'if (sendFeedback("topic", text)) input.value = "";' in self.PAGE


class TestAMoveIsABridgeNotACut:
    """Nov 6 2026 (Patrick's second test room): every press took her turn
    within seconds, but the change of subject landed as a cut, and a typed
    subject was named as the guest's."""

    def test_both_move_ons_carry_the_bridge(self):
        for name in ("MOVE_ON_STEER_TAIL", "PLAN_MOVE_ON_TAIL"):
            start = SCENARIO.index("const " + name + " =")
            body = SCENARIO[start:SCENARIO.index(";\n", start)]
            assert "STEER_BRIDGE" in body, name
        bridge = SCENARIO[SCENARIO.index("const STEER_BRIDGE ="):]
        bridge = bridge[:bridge.index(";\n")]
        assert "never as a cut" in bridge
        assert "one natural conversation" in bridge

    def test_a_typed_subject_is_never_attributed_to_the_guest(self):
        start = SCENARIO.index("function topicSteer(text) {")
        body = SCENARIO[start:SCENARIO.index("\n}\n", start)]
        assert "bridge to" in body
        assert "never say or hint that it came from them" in body
        assert "cannot tell it was asked for" in body


class TestBlurThatSafariCanDraw:
    """Nov 6 2026: Safari 27 has the canvas filter property but draws through
    it unchanged, so the page said "blurred" over a sharp background."""

    def test_the_filter_is_used_only_when_it_is_seen_to_blur(self):
        assert "function canvasFilterBlurs()" in STUDIO
        assert "var canFilter = canvasFilterBlurs();" in STUDIO
        assert 'var canFilter = typeof octx.filter === "string";' not in STUDIO
        fn = STUDIO[STUDIO.index("function canvasFilterBlurs()"):]
        fn = fn[:fn.index("\n  }\n")]
        assert "getImageData" in fn
