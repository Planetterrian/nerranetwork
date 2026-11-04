"""Mira's own recorder loses room time at every session change (Nov 4 2026).

Blaine Mathieu's tape: +17.06 s for 24 minutes, +36.96 s from the 30-minute
hand-over, +59.02 s from a rescue four and a half minutes later. The blind
search saw one jump, so the end of the hour had her 22 s off in the review
mix, the transcript and the cut. These pin the placement by the room's own
trace, the short-window check, and the wiring.
"""
import shutil
import sys
import wave
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "pipelines" / "voices"))

needs_ffmpeg = pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="ffmpeg")
SR = 8000


def _bursts(seconds: float, seed: int) -> np.ndarray:
    r = np.random.default_rng(seed)
    x = np.zeros(int(seconds * SR), np.float32)
    t = 0.0
    while t < seconds - 8:
        on = r.uniform(1, 6)
        a, n = int(t * SR), int(on * SR)
        x[a:a + n] = r.normal(0, r.uniform(.05, .3), n) * np.sin(np.linspace(0, np.pi, n))
        t += on + r.uniform(0.5, 4)
    return x


def _wav(path: Path, x: np.ndarray) -> Path:
    with wave.open(str(path), "wb") as f:
        f.setnchannels(1)
        f.setsampwidth(2)
        f.setframerate(SR)
        f.writeframes((np.clip(x, -1, 1) * 32767).astype("<i2").tobytes())
    return path


def _tape(tmp_path, segments):
    room = _bursts(900, 3)
    mira = np.concatenate([room[int(a * SR):int(b * SR)] for a, b in segments])
    return _wav(tmp_path / "room.wav", room), _wav(tmp_path / "mira.wav", mira)


@needs_ffmpeg
class TestSessionPieces:
    def test_two_changes_two_jumps(self, tmp_path):
        from audio.local_tracks import session_pieces
        # Starts 17 s in, loses 20 s after 400 s and 22 s after 650 s.
        room, mira = _tape(tmp_path, [(17, 400), (420, 650), (672, 900)])
        pieces = session_pieces(mira, room, tmp_path / "w", [401.5, 652.0], expected=0.0)
        assert [round(p["delay"]) for p in pieces] == [17, 37, 59]
        assert abs(pieces[1]["from"] - (400 - 17)) < 3
        assert abs(pieces[2]["from"] - (650 - 37)) < 3

    def test_a_change_that_lost_nothing_is_one_piece(self, tmp_path):
        from audio.local_tracks import session_pieces
        room, mira = _tape(tmp_path, [(17, 900)])
        pieces = session_pieces(mira, room, tmp_path / "w", [400.0], expected=0.0)
        assert len(pieces) == 1 and round(pieces[0]["delay"]) == 17

    def test_placed_and_verified_with_the_lost_seconds_filled(self, tmp_path):
        from audio.local_tracks import align_by_sessions, clock_residuals
        room, mira = _tape(tmp_path, [(17, 400), (420, 650), (672, 900)])
        got = align_by_sessions(mira, room, tmp_path / "w", [401.5, 652.0],
                                expected=0.0, fill_gaps=True)
        assert got is not None
        assert clock_residuals(got[0], room, tmp_path / "c") == []


@needs_ffmpeg
class TestShortWindowCheck:
    def test_sees_a_four_minute_stretch_off_the_clock(self, tmp_path):
        from audio.local_tracks import clock_residuals, place_pieces
        room, mira = _tape(tmp_path, [(17, 400), (420, 650), (672, 900)])
        # Placed as the blind search placed Blaine's: the last jump missed.
        wrong = place_pieces(mira, [{"from": 0, "to": 383, "delay": 17},
                                    {"from": 383, "to": 1000, "delay": 37}],
                             tmp_path / "p")
        off = clock_residuals(wrong, room, tmp_path / "c")
        assert off and all(o["at"] > 600 for o in off)
        assert {round(o["delay"]) for o in off} == {22}

    def test_a_repeat_is_not_an_offset(self, tmp_path):
        from audio.local_tracks import clock_residuals
        room = _bursts(300, 5)
        room[160 * SR:190 * SR] = room[100 * SR:130 * SR]   # she says it twice, a minute apart
        path = _wav(tmp_path / "room.wav", room)
        assert clock_residuals(path, path, tmp_path / "c") == []


class TestTheTraceNamesTheChanges:
    def test_hand_over_drop_and_a_trimmed_line(self):
        import post_interview as pi
        run = {"scenario_trace": [
            {"t": "2026-11-04T16:26:34.581Z", "e": "room", "d": "opened (webrtc)"},
            {"t": "2026-11-04T16:26:35.174Z", "e": "grok", "d": "session updated; agent<->room mix bridged"},
            {"t": "2026-11-04T16:51:07.240Z", "e": "grok", "d": "handing over to a fresh session after 1473s at a pause"},
            {"t": "2026-11-04T16:51:08.472Z", "e": "grok", "d": "session 2 bridged — resuming the interview"},
            {"t": "2026-11-04T16:55:49.194Z", "e": "grok", "d": "connection dropped code 1006"},
            {"t": "2026-11-04T16:55:51.836Z", "e": "grok", "d": "session 3 bridged — resuming the interview"},
            # The drop's own line fell out of the bounded trace:
            {"t": "2026-11-04T17:00:01.5Z", "e": "grok", "d": "session 4 bridged — resuming the interview"},
        ]}
        got = pi.mira_session_changes(run)
        assert got == [1472.66, 1754.61, 2005.42]


class TestWiring:
    SRC = (ROOT / "pipelines" / "voices" / "post_interview.py").read_text()

    def test_mira_is_placed_by_her_sessions_first(self):
        body = self.SRC[self.SRC.index("def build_tracks("):self.SRC.index("def place_local_take(")]
        assert "mira_session_changes(run)" in body
        assert body.index("align_by_sessions(") < body.index("align_to_room(track, guest_r")

    def test_the_blind_result_is_checked_in_short_windows(self):
        body = self.SRC[self.SRC.index("def build_tracks("):self.SRC.index("def place_local_take(")]
        assert "clock_residuals(shifted, guest_r" in body

    def test_the_lost_seconds_come_from_the_room_only_without_a_co_host(self):
        body = self.SRC[self.SRC.index("def build_tracks("):self.SRC.index("def place_local_take(")]
        assert "fill_gaps=host is None" in body
