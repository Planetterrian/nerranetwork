"""The craft is measured from the audio, not estimated from a transcript
(Oct 21 2026 review, §7.4).

Synthetic per-speaker word lists stand in for the Whisper word timestamps
the post-interview step collects. The §7.7 baseline shapes are here as the
calibration: a room that interrupts, a room where Mira answers herself, a
room that opens every turn on an echo, and a clean room.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "pipelines" / "voices"))

import audio_metrics as am  # noqa: E402


def _words(text: str, start: float, wps: float = 2.5) -> list[dict]:
    """Evenly spaced words from ``start``, ``wps`` words a second."""
    out = []
    t = start
    for w in text.split():
        out.append({"start": round(t, 3), "end": round(t + 1.0 / wps * 0.8, 3), "word": w})
        t += 1.0 / wps
    return out


def _turn(words: list[dict], text: str, start: float) -> float:
    ws = _words(text, start)
    words.extend(ws)
    return ws[-1]["end"]


class TestTurns:
    def test_words_under_a_second_apart_are_one_turn(self):
        ws = _words("one two three four five", 0.0)
        assert len(am.turns(ws)) == 1

    def test_a_pause_over_a_second_splits_a_turn(self):
        ws = _words("one two", 0.0) + _words("three four", 5.0)
        assert len(am.turns(ws)) == 2

    def test_bad_words_are_dropped_not_fatal(self):
        ws = [{"start": "x"}, {"word": "hi"}, {"start": 1.0, "end": 1.2, "word": "ok"}]
        assert len(am.turns(ws)) == 1


class TestACleanRoom:
    """Guest speaks, Mira waits ~600 ms, speaks for fifteen seconds, waits."""

    def setup_method(self):
        self.mira, self.guest = [], []
        t = 0.0
        for i in range(6):
            t = _turn(self.mira, "so tell me about the part of the work that surprised you most " * 3, t)
            t = _turn(self.guest, ("well the surprising thing was the database stall and the queue "
                                   "that fixed it " * (3 + i)), t + 0.6)
            t += 0.6

    def test_no_overlap_no_self_answers(self):
        m = am.measure_audio({"mira": self.mira, "guest": self.guest})
        assert m["metrics_basis"] == "audio"
        assert m["overlap_events"] == 0 and m["overlap_sec"] == 0
        assert m["self_answered_turns"] == 0
        assert m["echo_open_rate"] == 0.0

    def test_turn_gap_is_a_conversation(self):
        m = am.measure_audio({"mira": self.mira, "guest": self.guest})
        assert 400 <= m["turn_gap_ms_median"] <= 900
        assert m["interruptions_audio"] == 0

    def test_mira_turn_length_is_a_host_not_a_clip(self):
        m = am.measure_audio({"mira": self.mira, "guest": self.guest})
        assert 12 <= m["mira_turn_sec_median"] <= 20

    def test_answers_grow_through_the_hour(self):
        m = am.measure_audio({"mira": self.mira, "guest": self.guest})
        assert m["guest_words_trend"] is not None and m["guest_words_trend"] > 1.0


class TestTheOct19Room:
    """What the Oct 19 and 20 rooms sounded like: Mira starts while the
    guest is still talking, turns of eight seconds, every opener an echo."""

    def setup_method(self):
        self.mira, self.guest = [], []
        t = 0.0
        for i in range(5):
            t = _turn(self.mira, "how big is the team now and who runs it " * 2, t)
            end = _turn(self.guest, "we are talking to staff about twelve people across two offices", t + 0.5)
            # She starts 200 ms BEFORE the guest's last word ends.
            t = _turn(self.mira, "talking to staff about twelve. and the second office is where", end - 0.2)
            t += 2.0

    def test_overlap_and_interruptions_are_counted(self):
        m = am.measure_audio({"mira": self.mira, "guest": self.guest})
        assert m["overlap_events"] >= 5
        assert m["overlap_sec"] > 0
        assert m["interruptions_audio"] >= 5
        assert m["turn_gap_ms_p10"] < am.INTERRUPTION_MS

    def test_the_echo_opener_is_measured_without_a_phrase_list(self):
        m = am.measure_audio({"mira": self.mira, "guest": self.guest})
        assert m["echo_open_rate"] >= 0.5

    def test_short_turns_read_as_clipped(self):
        m = am.measure_audio({"mira": self.mira, "guest": self.guest})
        assert m["mira_turn_sec_median"] < 12


class TestSelfAnswered:
    def test_a_turn_with_no_guest_speech_between_is_self_answered(self):
        mira, guest = [], []
        t = _turn(mira, "what would you tell a founder starting today", 0.0)
        t = _turn(mira, "i suppose you would say start small and measure", t + 2.5)
        _turn(guest, "yes exactly start small", t + 1.0)
        m = am.measure_audio({"mira": mira, "guest": guest})
        assert m["self_answered_turns"] == 1

    def test_a_guest_answer_between_is_not(self):
        mira, guest = [], []
        t = _turn(mira, "what would you tell a founder starting today", 0.0)
        t = _turn(guest, "start small", t + 0.6)
        _turn(mira, "and measure what exactly", t + 0.6)
        m = am.measure_audio({"mira": mira, "guest": guest})
        assert m["self_answered_turns"] == 0


class TestUnmeasurable:
    def test_a_missing_track_is_none_never_zero(self):
        m = am.measure_audio({"mira": _words("hello there", 0.0)})
        assert m["metrics_basis"] == "none"
        assert m["overlap_events"] is None and m["self_answered_turns"] is None
        assert m["mira_turn_sec_median"] is not None

    def test_columns_and_notes_split_the_result(self):
        m = am.measure_audio({"mira": _words("a b", 0.0), "guest": _words("c d", 3.0)})
        cols = am.columns(m)
        assert set(cols) <= set(am.COLUMNS)
        assert "turn_gaps_ms" in am.notes(m) and "turn_gaps_ms" not in cols


class TestTheTrace:
    def _trace(self, lines):
        return [{"t": f"2026-10-21T00:00:{i:02d}Z", "e": e, "d": d}
                for i, (e, d) in enumerate(lines)]

    def test_eight_asks_each_answered_is_complete(self):
        lines = [("room", "opened")]
        for n in range(1, 9):
            lines += [("round", f"asked {n}/8: q{n}"), ("round", f"answered {n}/8")]
        out = am.closing_round(self._trace(lines))
        assert out["closing_round_complete"] is True and out["round_asked"] == 8

    def test_two_asks_in_one_turn_are_not_complete(self):
        lines = [("round", "asked 1/8: a"), ("round", "answered 1/8"),
                 ("round", "asked 2/8: b"), ("round", "asked 3/8: c"), ("round", "answered 3/8")]
        out = am.closing_round(self._trace(lines))
        assert out["round_stacked"] == 1 and out["closing_round_complete"] is False

    def test_the_oct_19_shape_counts_asks_without_answered_lines(self):
        lines = [("round", "asked: the show's own question"), ("grok", "response done"),
                 ("round", "asked: who you should interview next"), ("grok", "response done")]
        out = am.closing_round(self._trace(lines), expected=2)
        assert out["round_asked"] == 2 and out["closing_round_complete"] is True

    def test_a_handover_inside_guest_speech_is_a_seam(self):
        guest = _words("a long answer that was still going when the session rotated", 3.0)
        trace = self._trace([("room", "opened"), ("grok", "response done"),
                             ("grok", "handing over to a fresh session after 1560s"),
                             ("grok", "session 2 bridged — resuming the interview")])
        # The handover is at t=2s of the room clock; the guest speaks 3.0-7.6.
        out = am.seams(trace, am.turns(guest))
        assert out["seams"] >= 1

    def test_a_handover_in_silence_is_not(self):
        guest = _words("a short answer", 30.0)
        trace = self._trace([("room", "opened"),
                             ("grok", "handing over to a fresh session after 1560s")])
        assert am.seams(trace, am.turns(guest))["seams"] == 0


class TestTargets:
    def test_green_reads_the_review_targets(self):
        row = {"overlap_events": 2, "duration_sec": 2700, "self_answered_turns": 0,
               "mira_turn_sec_median": 15.0, "echo_open_rate": 0.05,
               "guest_words_trend": 1.3, "closing_round_complete": True, "seams": 0}
        for metric in ("overlap_events_per_10min", "self_answered_turns", "mira_turn_sec_median",
                       "echo_open_rate", "guest_words_trend", "closing_round_complete", "seams"):
            assert am.is_green(metric, row) is True, metric

    def test_an_unmeasured_room_is_never_green(self):
        assert am.is_green("self_answered_turns", {}) is None
        assert am.is_green("overlap_events_per_10min", {"overlap_events": 1}) is None

    def test_the_oct_20_room_is_red(self):
        row = {"overlap_events": 14, "duration_sec": 2207, "self_answered_turns": 3,
               "mira_turn_sec_median": 8.7, "echo_open_rate": 0.6}
        assert am.is_green("overlap_events_per_10min", row) is False
        assert am.is_green("mira_turn_sec_median", row) is False
        assert am.is_green("echo_open_rate", row) is False
