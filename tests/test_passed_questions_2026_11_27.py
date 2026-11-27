"""A question the guest passes on never reaches the episode (Nov 27 2026).

Gary Amaral passed on eight questions in his Nov 13 room and the produced
episode carried all eight, each followed by Mira's "Sure." The edit already
had a rule for a decline, but his one-word "pass" never reached the
transcript: Whisper drops a lone word in a long silence, or glues it onto
the end of the previous answer. What the transcript DOES carry every time is
the shape: Mira's question, nobody answering, then her acknowledgment and a
different question. Patrick's rule: any question a guest passes on or
declines comes out of the produced episode before it goes out for review.

The transcript below is synthetic and keeps the shapes of that room.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "pipelines" / "voices"))
sys.path.insert(0, str(ROOT))

import assemble_edit as asm  # noqa: E402
import auto_edit as ae  # noqa: E402
import edit_transcript as et  # noqa: E402

AUTO = (ROOT / "pipelines" / "voices" / "auto_edit.py").read_text(encoding="utf-8")
ASSEMBLE = (ROOT / "pipelines" / "voices" / "assemble_edit.py").read_text(encoding="utf-8")
PROMPT = (ROOT / "pipelines" / "voices" / "prompts" / "auto_edit.txt").read_text(encoding="utf-8")

ROOM = """[01:00] Mira: Welcome. What did the first launch teach you?
[01:05] Guest: That the infrastructure was not ready for the volume we sent it.
[01:40] Mira: The volume was the variable.
[01:42] Mira: What did that week of manual work look like?
[01:55] Mira: Sure.
[01:57] Mira: You stopped taking lead targets. How do you set goals instead?
[02:03] Guest: We align with the sales leader's number.
[02:30] Mira: Opportunity it is.
[02:31] Mira: Self-sourcing is something no agent can replicate.
[02:35] Mira: Have you seen that muscle come back?
[02:40] Guest: It is definitely coming back.
[03:00] Mira: The art and science framing is older than the tools. Was there one campaign where it clicked?
[03:14] Mira: Of course, a different one. What changed in the first thirty days?
[03:20] Guest: Not much else changed, to be honest.
[04:00] Mira: Two checklists still name the steps.
[04:03] Mira: Which one do your reps reach for first?
[04:13] Mira: Understood.
[04:16] Mira: You mentioned behaviour takes time to change.
[04:18] Mira: What is the messiest part of that transition?
[04:27] Mira: Taking those.
[04:29] Mira: Where do you see this in five years?
[04:33] Guest: The form as we know it is likely gone.
[05:00] Mira: Is that handoff the moment you would rather delay?
[05:05] Guest: Can you restate the question?
[05:10] Mira: Would you rather that moment came later?
[05:14] Guest: Sooner, always.
[05:40] Mira: What do you say to a buyer who is not ready yet?
[05:52] Mira: Because lead scores still sell, and that gap is where it gets costly.
[06:00] Guest: I challenge the premise.
[06:30] Mira: What about hiring?
[06:34] Guest: Pass.
[06:36] Mira: Fine.
[06:38] Mira: Where did pricing go next?
[06:42] Guest: Pricing went to usage.
"""


def _spans(text: str, kind: str | None = None):
    rows = ae.guest_requests(text)
    return [(r["from_sec"], r["to_sec"]) for r in rows if kind is None or r["kind"] == kind]


class TestAPassIsFoundFromTheShapeItLeaves:
    def test_question_silence_then_sure_is_a_pass(self):
        assert (100.0, pytest.approx(116.75)) in _spans(ROOM, "pass")

    def test_the_span_starts_with_her_reaction_before_the_question(self):
        # "The volume was the variable." was the run-up to a question that is
        # no longer there; the guest's previous answer stays whole.
        (row,) = [r for r in ae.guest_requests(ROOM)
                  if r["kind"] == "pass" and "manual work" in r["why"]]
        assert row["from_sec"] == 100.0
        assert row["guest_request"] is True
        assert "Sure." in row["why"]

    def test_an_answered_question_is_never_a_pass(self):
        found = _spans(ROOM)
        # "Have you seen that muscle come back?" was answered at 02:40.
        assert not any(a <= 155.0 < b for a, b in found)
        # Nor does a reaction before an answered question come out.
        assert not any(a <= 150.0 < b for a, b in found)

    def test_a_restate_request_is_not_a_pass(self):
        found = _spans(ROOM)
        assert not any(a <= 300.0 < b for a, b in found)
        assert not any(a <= 310.0 < b for a, b in found)

    def test_her_own_elaboration_after_a_silence_is_not_a_pass(self):
        # "Because lead scores still sell..." elaborates the question; the
        # guest answers it. Not an acknowledgment, so nothing comes out.
        found = _spans(ROOM)
        assert not any(a <= 340.0 < b for a, b in found)

    def test_a_short_line_that_is_not_in_the_list_still_acknowledges(self):
        # "Taking those." between an unanswered question and the next one.
        (row,) = [r for r in ae.guest_requests(ROOM) if "Taking those" in r["why"]]
        assert row["kind"] == "pass" and row["to_sec"] == pytest.approx(268.75)

    def test_two_passes_in_a_row_are_two_spans_that_do_not_overlap(self):
        spans = sorted(_spans(ROOM, "pass"))
        first = (240.0, pytest.approx(255.75))
        assert first in spans
        assert (256.0, pytest.approx(268.75)) in spans
        for (a1, b1), (a2, b2) in zip(spans, spans[1:]):
            assert b1 <= a2

    def test_a_quick_ack_in_her_own_turn_is_not_a_pass(self):
        text = ("[00:10] Mira: Is that right? \n[00:12] Mira: Sure. Next, what about pricing?\n"
                "[00:15] Guest: Pricing went to usage.\n")
        assert _spans(text, "pass") == []


class TestASpokenPassIsADecline:
    @pytest.mark.parametrize("said", [
        "Pass.", "pass", "Um, pass.", "Next question.", "Skip it.",
        "Yeah, I'll pass.", "I'm not going to answer that.",
        "That's a fair question, but I'm going to pass on it.",
        "Can we skip that one?", "I'd rather not get into hiring.",
    ])
    def test_the_words_of_a_pass(self, said):
        assert ae.DECLINE_RE.search(said) or ae.DECLINE_ANYWHERE_RE.search(said)

    @pytest.mark.parametrize("said", [
        "Passion is what drives the team.", "Next we launched in Europe.",
        "We let that pass and moved on to pricing, which grew.",
    ])
    def test_an_answer_is_never_a_decline(self, said):
        assert not (ae.DECLINE_RE.search(said) or ae.DECLINE_ANYWHERE_RE.search(said))

    def test_a_bare_pass_takes_the_question_the_pass_and_her_ack(self):
        (row,) = [r for r in ae.guest_requests(ROOM) if r["kind"] == "decline"]
        assert row["from_sec"] == 390.0                     # "What about hiring?"
        assert row["to_sec"] == pytest.approx(397.75)       # through "Fine."
        # Found once, not again as a pass.
        assert not any(a <= 390.0 < b for a, b in _spans(ROOM, "pass"))


class TestAnAckThatSharesItsLineWithTheNextQuestion:
    def test_the_span_stops_before_the_line_and_carries_the_ack(self):
        (row,) = [r for r in ae.guest_requests(ROOM) if r.get("skip_ack")]
        assert (row["from_sec"], row["to_sec"]) == (180.0, pytest.approx(193.75))
        assert row["skip_ack"]["ack"] == "Of course, a different one."
        assert row["skip_ack"]["line_at"] == 194.0
        assert row["skip_ack"]["until_sec"] == pytest.approx(194.0 + 5 * ae.WORD_SEC)

    def test_a_one_sentence_line_never_loses_its_front(self):
        assert ae._inline_ack((10.0, "Mira", "Sure, what about hiring?")) is None
        assert ae._inline_ack((10.0, "Mira", "Sure.")) is None

    def test_the_assembler_starts_after_the_pause_that_ends_the_ack(self):
        import numpy as np
        # 10 ms frames from the line's start: 2.0 s of ack, 0.3 s pause, then
        # the next question; one short catch inside the ack is not a pause.
        loud = np.array([True] * 90 + [False] * 5 + [True] * 105
                        + [False] * 30 + [True] * 200)
        at = asm.ack_pause(loud, 194.0, 194.0 + 5 * ae.WORD_SEC)
        assert at == pytest.approx(194.0 + 2.3 - 0.08)

    def test_no_pause_keeps_the_ack_rather_than_guessing(self):
        import numpy as np
        assert asm.ack_pause(np.array([True] * 400), 194.0, 196.25) is None
        cut = {"from": "mix:clean", "start": 193.75, "end": 300.0,
               "skip_ack": {"line_at": 194.0, "until_sec": 196.25, "ack": "Sure."}}
        asm._loud_frames, saved = (lambda *a, **k: None), asm._loud_frames
        try:
            asm._start_after_the_ack(cut, "x.wav")
        finally:
            asm._loud_frames = saved
        assert cut["start"] == 193.75 and not cut.get("_ack_skipped")

    def test_the_guest_sees_the_line_without_the_ack(self):
        transcript = ("[03:00] Mira: Was there one campaign?\n"
                      "[03:14] Mira: Of course, a different one. What changed?\n"
                      "[03:20] Guest: Not much.\n")
        cuts = [{"from": "mix:clean", "start": 196.2, "end": 230.0, "_ack_skipped": True,
                 "skip_ack": {"line_at": 194.0, "until_sec": 196.25,
                              "ack": "Of course, a different one."}}]
        text = et.transcript_of_the_edit(transcript, cuts, [33.8])
        assert "Mira: What changed?" in text
        assert "a different one" not in text
        assert "Guest: Not much." in text

    def test_the_assembler_runs_it_on_both_beds(self):
        assert ASSEMBLE.count("_start_after_the_ack(cut, ") == 2


class TestBuildCarriesItThrough:
    def test_passes_ride_the_guest_request_path_with_no_floor(self):
        body = AUTO[AUTO.index("def guest_requests("):AUTO.index("def _inline_ack(")]
        assert "found += passed_questions(lines, host, already=found)" in body

    def test_drops_a_breath_apart_are_joined(self):
        body = AUTO[AUTO.index("def build("):AUTO.index("def _cold_open(")]
        assert 'd["from"] - joined[-1]["to"] < MERGE_GAP_SEC' in body
        assert '"skip_ack": ack' in body
        assert "question(s) the guest passed on are out" in body

    def test_the_prompt_names_the_shape(self):
        assert "the guest passed" in PROMPT
