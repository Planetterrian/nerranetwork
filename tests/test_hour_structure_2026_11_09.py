"""More structure for Mira's hour (Nov 9 2026, Patrick: "give more structure").

1. The opening's how-the-hour-works turn names two or three parts ahead,
   taken from the prepared questions, a phrase each, so the guest and the
   listener hear the shape before the first real question.
2. When the room moves her to the next prepared question, she names the
   part of the hour she is turning to, the way a host opens a segment.
3. The rehearsal report says WHERE the two gating counts happened: each
   self-answered turn with the silence before it (a second or two is a
   pause inside one turn of hers, not a question she answered) and each
   stretch of talking over. Times only, never words.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VOICES = ROOT / "pipelines" / "voices"
SCENARIO = (ROOT / "voximplant" / "scenarios" / "age_of_ai_interview.js").read_text(encoding="utf-8")
PROMPT = (VOICES / "prompts" / "mira_system_prompt.txt").read_text(encoding="utf-8")
FLAT = " ".join(PROMPT.split())

sys.path.insert(0, str(VOICES))


def _beat_two() -> str:
    turn = FLAT[FLAT.index("HOW TO OPEN"):FLAT.index("THEIR SUBJECT, FAST")]
    return turn[turn.index("2. How the hour works"):turn.index("3. Welcome them")]


class TestTheOpeningNamesThePartsAhead:
    def test_the_parts_come_from_the_prepared_questions_a_phrase_each(self):
        beat = _beat_two()
        assert "two or three parts ahead, from the prepared questions, a phrase each" in beat
        # After how she listens, before the guest's controls: the map, then the rights.
        assert beat.index("nothing gets cut off") < beat.index("parts ahead") < beat.index("this is their hour")

    def test_still_one_turn_that_ends_on_a_check(self):
        beat = _beat_two()
        assert beat.rstrip().endswith("Then ask if that sounds good.")
        assert "“" not in beat and '"' not in beat

    def test_the_brief_stays_inside_its_budget(self):
        assert len(PROMPT.split()) < 1600


class TestTheMoveNamesThePart:
    def test_the_room_asks_her_to_open_the_next_part_like_a_segment(self):
        head = SCENARIO[SCENARIO.index("const PLAN_MOVE_HEAD ="):]
        head = head[:head.index(";\n")]
        flat = " ".join(head.replace('" +', "").replace('"', "").split())
        assert "name the part of the hour you are turning to, in a phrase" in flat
        assert "the way a host opens a new segment" in flat
        assert "differently each time" in flat
        assert "never a summary of their answer" in flat


class TestTheReportSaysWhereToListen:
    def _turn(self, start, end, words="a b c"):
        return {"start": start, "end": end, "words": words.split()}

    def test_spans_carry_the_silence_before_each_self_answered_turn(self):
        import audio_metrics as am
        mira = [self._turn(0, 5), self._turn(6.2, 9), self._turn(30, 33)]
        guest = [self._turn(12, 25)]
        assert am.self_answered_spans(guest, mira) == [[5, 6.2]]
        assert am.self_answered(guest, mira) == 1

    def test_the_count_and_the_spans_agree_in_measure_audio(self):
        import audio_metrics as am
        words = {
            "mira": [{"start": 0.0, "end": 1.0, "word": "Hello"},
                     {"start": 2.5, "end": 3.0, "word": "there?"},
                     {"start": 20.0, "end": 21.0, "word": "Good."}],
            "guest": [{"start": 10.0, "end": 15.0, "word": "Fine"}],
        }
        m = am.measure_audio(words, trace=None)
        assert m["self_answered_turns"] == len(m["self_answered_spans"]) == 1
        assert m["self_answered_spans"] == [[1.0, 2.5]]
        assert "self_answered_spans" not in am.COLUMNS

    def test_the_room_log_prints_times_never_words(self):
        import rehearsal
        line = rehearsal.where_to_listen({
            "self_answered_spans": [[61.0, 62.4], [300.0, 309.0]],
            "overlap_spans": [[125.0, 126.5]],
        })
        assert line == ("her turn again with no guest speech between at 01:02 (1.4 s after her "
                        "last word), 05:09 (9.0 s after her last word); talking over at 02:05 (1.5 s)")
        assert rehearsal.where_to_listen({}) == ""
        md = rehearsal.room_markdown({"arm": "proposed", "fixture": "adrian", "run_id": "x",
                                      "metrics": {"self_answered_spans": [[1.0, 2.5]]}})
        assert "- where to listen: her turn again with no guest speech between at 00:02" in md
