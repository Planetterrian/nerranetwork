"""Oct 13 2026, Piper Martz: one episode from two sessions.

The room's 45-minute cap cut her first session off seconds into her answer to
the lightning round's first question, and she came back on Oct 12 to finish.
The automatic splice put the closing session on the end as it was recorded,
which left in four things a listener should not hear: Mira picking up "where
we left off" on a book recommendation the edit had already cut, Piper making
the same bet with the same IKEA story a second time, her feedback on the
process, which she said she would not include in the interview, and a sign-off
that said "You can hang up now" three times.

The edit in the repo fixes all four. These tests pin it, so a re-run of the
splice or a later hand edit cannot quietly put any of it back. Times are on
each session's own room clock, measured from the processed tracks.
"""

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EDL = json.loads((ROOT / "pipelines" / "voices" / "edl" / "piper_martz_2026_10_05.json")
                 .read_text(encoding="utf-8"))
FIRST = EDL["run_id"]
CLOSING = "c13f5d10-c0c0-4f74-9470-784627ea561e"


def _pieces(run: str) -> list:
    return [c for c in EDL["cuts"]
            if c.get("from") == "mix:clean" and (c.get("run_id") or FIRST) == run]


class TestPiperIsOneEpisode:
    def test_the_first_session_runs_on_through_the_book_question(self):
        (first,) = _pieces(FIRST)
        # "A book you would recommend, and in a sentence, why?" ends at
        # 2995.7; her answer, which the cap cut off, starts at 2998.0.
        assert 2995.7 < first["end"] < 2998.0

    def test_the_first_session_starts_on_mira_s_first_word(self):
        (first,) = _pieces(FIRST)
        # "Welcome" begins at 20.4; 20.6 took its first syllable off.
        assert first["start"] <= 20.4

    def test_her_answer_comes_from_the_closing_session_from_the_top(self):
        closing = _pieces(CLOSING)
        # Mira's "Go ahead and finish that thought" ends at 66.4; Piper's
        # "Yeah, one of my favorite books" starts at 68.4.
        assert 66.4 < closing[0]["start"] < 68.4

    def test_nothing_refers_to_a_break_the_listener_never_hears(self):
        # "That's a beautiful thread to pick back up", 172.8 to 174.9.
        for c in _pieces(CLOSING):
            assert c["end"] <= 172.8 or c["start"] >= 174.9

    def test_the_repeated_bet_is_out(self):
        # Mira asks the bet a second time at 548.1, and her "That's the bet
        # that matters most" after the answer ends at 674.1.
        for c in _pieces(CLOSING):
            assert c["end"] <= 548.1 or c["start"] >= 674.1

    def test_her_feedback_and_the_sign_off_are_out(self):
        # Mira's "The absence of body language..." starts at 737.1, and
        # "Candidly, and I wouldn't include this in the formal interview"
        # follows it.
        assert max(c["end"] for c in _pieces(CLOSING)) < 737.1

    def test_mira_s_mispronounced_line_is_muted(self):
        # "Success as the habit of keeping your enthusiasm through the
        # stumbles", 443.5 to 447.1, where her voice says "keking".
        (piece,) = [c for c in _pieces(CLOSING) if c["start"] < 443.5 and c["end"] > 447.1]
        assert any(m["role"] == "mira" and m["from"] <= 443.5 and m["to"] >= 447.1
                   for m in piece.get("mute") or [])

    def test_mira_s_produced_close_still_ends_the_episode(self):
        froms = [c.get("from") for c in EDL["cuts"] if "from" in c]
        assert froms[-1] == "narration:outro"
        last_closing = max(i for i, c in enumerate(EDL["cuts"]) if c.get("run_id") == CLOSING)
        assert last_closing < len(EDL["cuts"]) - 1
