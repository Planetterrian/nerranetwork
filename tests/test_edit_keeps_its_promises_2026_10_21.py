"""Oct 21 2026: the edit keeps the promises Mira makes in the room.

Three promises, three mechanisms, all pure functions of the EDL so they are
tested without audio:

1. A restart, a cut request or a declined question comes out whatever its
   length (``auto_edit.guest_requests`` + the floor exemption in ``build``).
2. The guest approves the transcript of the EDIT, re-stamped on the
   published file's clock (``edit_transcript.transcript_of_the_edit``).
3. The passages the guest marks on the review page are cut from the file
   that publishes (``edit_transcript.apply_windows``), and
   ``publish_episode`` refuses a file built without them.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "pipelines" / "voices"))
sys.path.insert(0, str(ROOT))

import auto_edit as ae  # noqa: E402
import edit_transcript as et  # noqa: E402

AUTO = (ROOT / "pipelines" / "voices" / "auto_edit.py").read_text(encoding="utf-8")
ASSEMBLE = (ROOT / "pipelines" / "voices" / "assemble_edit.py").read_text(encoding="utf-8")
PUBLISH = (ROOT / "pipelines" / "voices" / "publish_episode.py").read_text(encoding="utf-8")

TRANSCRIPT = """[00:10] Mira: Hello, how are you?
[00:14] Guest: Good. Thanks.
[00:20] Mira: What did the first year teach you?
[00:25] Guest: So the first year we had, um, no wait, let me start over.
[00:31] Guest: The first year taught us that pricing is a story.
[00:50] Mira: Say more about that.
[00:55] Guest: Our biggest client left in March, which I probably should not say. Can we cut that?
[01:02] Mira: Done, that stays out.
[01:05] Mira: What about hiring?
[01:08] Guest: I'd rather not get into hiring.
[01:11] Mira: Of course. Where did pricing go next?
[01:20] Guest: Pricing went to usage, and that is where the next three years are.
[02:00] Mira: Thank you. That's the end of the recording.
"""


class TestAGuestsRequestComesOut:
    def test_a_restart_drops_the_aborted_attempt_and_keeps_the_retake(self):
        (restart,) = [r for r in ae.guest_requests(TRANSCRIPT) if r["kind"] == "restart"]
        assert restart["from_sec"] == 25.0
        assert restart["to_sec"] == pytest.approx(30.75)   # the retake at 00:31 stays
        assert restart["guest_request"] is True
        assert "let me start over" in restart["why"]

    def test_a_cut_request_takes_the_question_the_passage_and_the_acknowledgment(self):
        (cut,) = [r for r in ae.guest_requests(TRANSCRIPT) if r["kind"] == "cut"]
        assert cut["from_sec"] == 50.0                      # Mira's "Say more about that."
        assert cut["to_sec"] == pytest.approx(64.75)        # through "Done, that stays out."

    def test_a_decline_never_swallows_the_next_question(self):
        (decline,) = [r for r in ae.guest_requests(TRANSCRIPT) if r["kind"] == "decline"]
        assert decline["from_sec"] == 65.0                  # "What about hiring?"
        # "Of course. Where did pricing go next?" carries the next question,
        # so the span stops before it.
        assert decline["to_sec"] == pytest.approx(70.75)

    def test_mira_never_triggers_a_request(self):
        text = "[00:10] Mira: Let me start over. Can we cut that?\n[00:20] Guest: Sure.\n"
        assert ae.guest_requests(text) == []

    def test_the_span_is_exempt_from_the_floor_in_build(self):
        body = AUTO[AUTO.index("def build("):AUTO.index("def _cold_open(")]
        assert "requests = guest_requests(transcript_of(ctx))" in body
        assert "for d in merge_drops(decided.get(\"drop\") or [], requests):" in body
        assert 'if d.get("guest_request"):\n            floor = 0.0' in body
        # The twenty-five-second floor still exists for the model's own drops.
        assert "floor = EARLY_DROP_MIN_SEC if a < start + EARLY_WINDOW_SEC else MIN_DROP_SEC" in body

    def test_a_request_the_model_also_found_is_one_drop(self):
        merged = ae.merge_drops([{"from_sec": 24, "to_sec": 60, "why": "model"}],
                                ae.guest_requests(TRANSCRIPT))
        assert merged[0]["from_sec"] == 24 and merged[0]["to_sec"] == pytest.approx(64.75)
        assert merged[0]["guest_request"] is True
        assert [m["kind"] for m in merged[1:]] == ["decline"]

    def test_the_edl_carries_the_offset_the_assembler_needs(self):
        assert '"room_offset_sec": round(offset, 3)' in AUTO
        assert '"guest_request_drops": kept_requests' in AUTO


CUTS = [{"from": "narration:intro"}, {"gap": 0.7},
        {"from": "mix:clean", "start": 20.0, "end": 60.0, "note": "a"},
        {"gap": 0.4},
        {"from": "mix:clean", "start": 70.0, "end": 130.0, "note": "b",
         "mute": [{"role": "mira", "from": 100.0, "to": 101.0}]},
        {"gap": 1.4}, {"from": "narration:outro"}]


class TestTheGuestsWindowsReachTheShippedFile:
    def test_a_window_splits_the_cut_it_falls_in(self):
        cuts, applied = et.apply_windows(CUTS, [{"start_sec": 80, "end_sec": 90, "line": "x"}])
        assert applied == 1
        spans = [(c["start"], c["end"]) for c in cuts if c.get("start") is not None]
        assert spans == [(20.0, 60.0), (70.0, pytest.approx(80 - et.WINDOW_PAD_SEC)),
                         (pytest.approx(90 + et.WINDOW_PAD_SEC), 130.0)]
        # A gap breathes at the seam, and the mute outside the window survives.
        idx = [i for i, c in enumerate(cuts) if c.get("start") == 70.0][0]
        assert cuts[idx + 1] == {"gap": 0.4}
        assert cuts[idx + 2]["mute"] == [{"role": "mira", "from": 100.0, "to": 101.0}]

    def test_a_window_on_the_room_clock_is_moved_to_the_legs(self):
        cuts, _ = et.apply_windows(CUTS, [{"start_sec": 480, "end_sec": 490}],
                                   room_offset_sec=400.0)
        spans = [(c["start"], c["end"]) for c in cuts if c.get("start") is not None]
        assert spans[1] == (70.0, pytest.approx(80 - et.WINDOW_PAD_SEC))

    def test_a_window_covering_a_whole_cut_removes_it(self):
        cuts, applied = et.apply_windows(CUTS, [{"start_sec": 10, "end_sec": 65}])
        assert applied == 1
        spans = [(c["start"], c["end"]) for c in cuts if c.get("start") is not None]
        assert spans == [(70.0, 130.0)]
        gaps = [c for c in cuts if c.get("gap") is not None]
        assert len(gaps) == 2                                 # two gaps never run together

    def test_a_note_without_numbers_is_not_a_window(self):
        assert et.normalise_windows([{"note": "please remove the bit about March"}]) == []
        assert et.windows_hash([{"note": "x"}]) == ""

    def test_the_hash_moves_when_a_window_does(self):
        a = et.windows_hash([{"start_sec": 1, "end_sec": 2}])
        b = et.windows_hash([{"start_sec": 1, "end_sec": 3}])
        assert a and b and a != b
        assert et.windows_hash([{"start_sec": 1.001, "end_sec": 2.004}]) == a

    def test_the_assembler_applies_them_before_building_and_records_the_hash(self):
        body = ASSEMBLE[ASSEMBLE.index("def assemble("):ASSEMBLE.index("def _live_package(")]
        assert "cuts, applied = apply_windows(cuts, windows, room_offset)" in body
        assert body.index("apply_windows(") < body.index("for i, cut in enumerate(cuts):")
        assert '"windows_hash": windows_hash(windows)' in body


class TestPublishRefusesAnUnappliedCut:
    def _run(self, h):
        return {"grok_session_log": {"tracks": {"edit": {"url": "u", "windows_hash": h}}}}

    def test_it_ships_when_the_file_was_built_against_the_windows(self, monkeypatch):
        import publish_episode as pe
        windows = [{"start_sec": 10, "end_sec": 20}]
        pe.assert_windows_applied({"guest_redaction_windows": windows},
                                  self._run(et.windows_hash(windows)))

    def test_it_refuses_when_the_guest_marked_a_cut_after_the_edit(self, monkeypatch):
        import publish_episode as pe
        told = []
        monkeypatch.setattr(pe, "notify_operator", lambda text, **kw: told.append(text))
        windows = [{"start_sec": 10, "end_sec": 20}]
        with pytest.raises(RuntimeError, match="refusing to publish"):
            pe.assert_windows_applied({"guest_redaction_windows": windows}, self._run(""))
        assert told and "assemble workflow" in told[0]
        with pytest.raises(RuntimeError):
            pe.assert_windows_applied({"guest_redaction_windows": windows}, self._run("deadbeef"))

    def test_no_windows_is_not_a_refusal(self):
        import publish_episode as pe
        pe.assert_windows_applied({"guest_redaction_windows": None}, self._run(""))
        pe.assert_windows_applied({"guest_redactions": [{"note": "free text"}]}, self._run(""))

    def test_publish_one_asks_before_it_resolves_the_audio(self):
        body = PUBLISH[PUBLISH.index("def publish_one("):PUBLISH.index("def _show_config(")]
        assert body.index("assert_windows_applied(pkg, run)") < body.index("audio_url = episode_audio(run)")
        assert "THE GUEST'S CUTS SHIP OR NOTHING DOES" in PUBLISH


class TestTheGuestApprovesTheEdit:
    def test_lines_are_restamped_on_the_edits_clock(self):
        cuts = [{"from": "narration:intro"}, {"gap": 0.7},
                {"from": "mix:clean", "start": 20.0, "end": 60.0},
                {"gap": 0.4},
                {"from": "mix:clean", "start": 70.0, "end": 130.0},
                {"gap": 1.4}, {"from": "narration:outro"}]
        durations = [12.0, 0.7, 40.0, 0.4, 60.0, 1.4, 8.0]
        text = et.transcript_of_the_edit(TRANSCRIPT, cuts, durations,
                                         narration={"intro": "My guest today.",
                                                    "outro": "Until next time."})
        lines = text.splitlines()
        assert lines[0] == "[00:00] Mira (narration): My guest today."
        # [00:25] in the room is 5 s into the first kept span, which starts at
        # 12.0 + 0.7 on the edit's clock.
        assert "[00:18] Guest: So the first year we had, um, no wait, let me start over." in lines
        # [00:50] "Say more about that." is in the first span; [01:05] falls in
        # the dropped stretch 60-70 and is gone.
        assert any(line.endswith("Mira: Say more about that.") for line in lines)
        assert not any("What about hiring?" in line for line in lines)
        # [01:20] = 80 s room -> 10 s into the second span, which starts at 53.1.
        assert "[01:03] Guest: Pricing went to usage, and that is where the next three years are." in lines
        # 12 + 0.7 + 40 + 0.4 + 60 + 1.4 = 114.5 s before the outro.
        assert lines[-1].startswith("[01:54] Mira (narration): Until next time.")

    def test_a_span_the_gap_trim_shortened_never_runs_backwards(self):
        # Oct 23 2026: 60 s of room came out at 30 s once its long pauses
        # were closed; the next span's lines must still come after it.
        cuts = [{"from": "mix:clean", "start": 0.0, "end": 60.0},
                {"from": "mix:clean", "start": 70.0, "end": 130.0}]
        text = et.transcript_of_the_edit(TRANSCRIPT, cuts, [30.0, 60.0])
        stamps = [line[1:6] for line in text.splitlines()]
        secs = [int(t[:2]) * 60 + int(t[3:]) for t in stamps]
        assert secs == sorted(secs)
        assert max(s for s, line in zip(secs, text.splitlines())
                   if "Say more about that." in line) < 30
        # The second span starts at 30 s, where the first one actually ended.
        assert "[00:40] Guest: Pricing went to usage, and that is where the next three years are." in text.splitlines()

    def test_the_offset_moves_the_room_lines_too(self):
        cuts = [{"from": "mix:clean", "start": 0.0, "end": 60.0}]
        text = et.transcript_of_the_edit(TRANSCRIPT, cuts, [60.0], room_offset_sec=20.0)
        # Leg 0-60 is room 20-80: the 00:20 question is first, at 00:00.
        assert text.splitlines()[0] == "[00:00] Mira: What did the first year teach you?"

    def test_the_assembler_writes_it_to_the_live_package(self):
        assert '{"edit_transcript": edit_text}' in ASSEMBLE
        assert "transcript_of_the_edit(" in ASSEMBLE
        # The measured pieces, never an estimate, are the clock.
        assert "piece_durations = [_duration(piece) for piece in pieces]" in ASSEMBLE

    def test_a_duration_count_mismatch_is_an_error_not_a_wrong_clock(self):
        with pytest.raises(ValueError):
            et.transcript_of_the_edit(TRANSCRIPT, CUTS, [1.0, 2.0])
