"""A beat between stories (Oct 13 2026, operator listen: stories ran
straight into each other with no processing time).

Pins ``engine/story_breaks.py`` — story starts found from the digest on a
real committed episode, cuts placed only in the voice track's own silence,
the splice lossless and the transcript shifted with it — the wiring in
run_show (before the mix, never on a dialogue show, off at 0), and the
prompt rule that replaced "move between stories with the next story's
first fact".
"""
from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from engine import story_breaks as S

ROOT = Path(__file__).resolve().parent.parent
EP = ROOT / "digests" / "spacex" / "SpaceX_Daily_Ep128_20261012"


def _real():
    return (Path(f"{EP}.md").read_text(encoding="utf-8"),
            Path(f"{EP}_tts.txt").read_text(encoding="utf-8"),
            json.loads(Path(f"{EP}_transcript.json").read_text(encoding="utf-8")))


@pytest.mark.skipif(not Path(f"{EP}_tts.txt").exists(), reason="fixture episode pruned")
class TestStoryStartsOnARealEpisode:
    def test_every_story_change_and_nothing_else(self):
        md, script, _ = _real()
        lines = S.script_lines(script)
        starts = [lines[i][:20] for i in S.story_boundary_lines(script, md)]
        # SpaceX Ep128: the FCC licence, India pricing, the Crew Dragon
        # splashdown, Grok in Cybercab, the Cybertruck photo, Ship 40, the
        # Vandenberg launches (one beat for the pair), the Columbia clip,
        # the Counterpoint, AI & Compute, the engineering essay, and (Oct 17
        # 2026, once the sign-off stopped the scan) the "Before we go"
        # teaser, which is a story change like any other.
        assert starts == [
            "The Federal Communic", "Elon Musk said Space",
            "Crew Dragon Freedom ", "Grok is now availabl",
            "Musk also posted a p", "Ship Forty, the Star",
            "KSBY has a Falcon Ni", "Musk shared a two-fo",
            "One thing worth watc", "On the A I front, Mu",
            "Pull the engineering", "Before we go — weath",
        ]

    def test_the_hook_and_identity_line_never_break(self):
        md, script, _ = _real()
        assert all(i > 2 for i in S.story_boundary_lines(script, md))

    def test_an_essay_is_one_unit(self):
        md, _, _ = _real()
        labels = [u.label for u in S.story_units(md)]
        assert labels.count("essay") >= 1
        # The 17-sentence engineering deep dive is one unit, not 17.
        assert max(u.sentences for u in S.story_units(md) if u.label == "essay") >= 10

    def test_starts_are_located_in_whisper_words(self):
        md, script, transcript = _real()
        anchors, unmatched = S.boundary_anchors(
            script, S.story_boundary_lines(script, md), transcript)
        assert len(anchors) >= 9 and unmatched <= 2
        assert all(a <= b for a, b in anchors)
        assert [b for _, b in anchors] == sorted(b for _, b in anchors)


class TestRules:
    def test_a_one_line_detour_is_not_a_story(self):
        units = [S.StoryUnit("item", frozenset({"rocket", "booster", "landing", "pad", "falcon", "barge"}), 5),
                 S.StoryUnit("item", frozenset({"court", "ruling", "judge", "appeal", "filing", "lawsuit"}), 5)]
        md = ("## News\n\n1. **A**\nrocket booster landing pad falcon barge\n\n"
              "2. **B**\ncourt ruling judge appeal filing lawsuit\n")
        script = ("The rocket booster made its landing on the barge pad.\n"
                  "The falcon booster rocket used the barge landing pad again.\n"
                  "A court ruling from the judge on the appeal filing came.\n"
                  "The falcon rocket booster barge landing pad is reusable.\n"
                  "The rocket booster landing barge pad falcon was quick.\n")
        assert S.story_boundary_lines(script, md) == []
        assert len(units) == 2

    def test_numbers_are_matched_as_spoken(self):
        transcript = {"segments": [{"words": [
            {"word": "Earlier", "start": 0.0, "end": 0.4},
            {"word": "Falcon", "start": 1.0, "end": 1.3}, {"word": "9", "start": 1.3, "end": 1.5},
            {"word": "launches", "start": 1.5, "end": 1.9}, {"word": "from", "start": 1.9, "end": 2.0},
            {"word": "Vandenberg", "start": 2.0, "end": 2.6}]}]}
        anchors, unmatched = S.boundary_anchors(
            "Earlier.\nFalcon Nine launches from Vandenberg.", [1], transcript)
        assert anchors == [(0.4, 1.0)] and unmatched == 0

    def test_no_silence_no_cut(self):
        assert S.choose_cuts([(10.0, 10.0)], []) == ([], 1)
        assert S.choose_cuts([(10.0, 10.0)], [(30.0, 31.0)]) == ([], 1)
        assert S.choose_cuts([(10.0, 10.1)], [(9.9, 10.5)]) == ([10.2], 0)

    def test_silencedetect_parse(self):
        log = ("[silencedetect @ 0x1] silence_start: 1.99\n"
               "[silencedetect @ 0x1] silence_end: 2.51 | silence_duration: 0.52\n")
        assert S.parse_silencedetect(log) == [(1.99, 2.51)]

    def test_transcript_shift(self):
        t = {"duration": 10.0, "segments": [
            {"start": 1.0, "end": 3.0, "words": [{"start": 1.0, "end": 1.5}, {"start": 2.5, "end": 3.0}]},
            {"start": 5.0, "end": 6.0, "words": [{"start": 5.0, "end": 6.0}]}]}
        out = S.shift_transcript(t, [2.0, 4.0], 1.2)
        assert out["segments"][0]["words"][0]["start"] == 1.0
        assert out["segments"][0]["words"][1]["start"] == 3.7
        assert out["segments"][1]["start"] == 7.4
        assert out["duration"] == 12.4
        assert t["segments"][1]["start"] == 5.0  # the input is untouched


class TestTheSplice:
    def test_silence_lands_at_the_cut_and_nothing_else_moves(self, tmp_path):
        src = tmp_path / "voice.mp3"
        subprocess.run(
            ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
             "-f", "lavfi", "-i", "sine=f=300:d=2",
             "-f", "lavfi", "-i", "anullsrc=r=48000:cl=mono:d=0.5",
             "-f", "lavfi", "-i", "sine=f=500:d=2",
             "-filter_complex", "[0][1][2]concat=n=3:v=0:a=1,aresample=48000",
             "-c:a", "libmp3lame", "-q:a", "2", str(src)], check=True)
        silences = S.detect_silences(src)
        cuts, unplaced = S.choose_cuts([(2.0, 2.5)], silences)
        assert unplaced == 0 and len(cuts) == 1
        out = tmp_path / "out.wav"
        cmd = S.insert_silences_cmd(src, out, cuts, 1.2)
        assert "pcm_s16le" in cmd  # lossless: the mix encodes once
        subprocess.run(cmd, check=True)
        gap = [s for s in S.detect_silences(out) if s[1] - s[0] > 1.0]
        assert gap and 1.6 <= gap[0][1] - gap[0][0] <= 1.8


class TestWiring:
    SRC = (ROOT / "run_show.py").read_text(encoding="utf-8")

    def test_breaks_go_in_after_the_gate_and_before_the_mix(self):
        breaks = self.SRC.index("# 9a-breaks.")
        assert self.SRC.index('metrics.record("spoken_text_gate", _gate_outcome)') < breaks
        assert breaks < self.SRC.index("mix_with_music(\n                            voice_for_mix")
        block = self.SRC[breaks:self.SRC.index("# 9b. Post-TTS")]
        assert "not config.tts.dialogue_mode" in block
        assert "rewrite_transcript_files" in block and "voice_for_mix = raw_mp3" in block

    def test_off_by_default_on_for_the_network(self):
        from engine.config import AudioConfig, load_config

        assert AudioConfig().story_break_seconds == 0.0
        # Oct 14 2026: the value is now the TOTAL pause (was 1.2 s added).
        assert load_config(ROOT / "shows" / "spacex.yaml").audio.story_break_seconds == 1.0


class TestThePromptRule:
    def test_the_shared_rule_orients_the_listener(self):
        text = (ROOT / "shows" / "prompts" / "_shared" / "content_discipline.txt").read_text(encoding="utf-8")
        assert "The listener hears every story change" in text
        assert "next story's first fact" not in text

    def test_no_prompt_still_says_jump_straight_in(self):
        for p in (ROOT / "shows" / "prompts").rglob("*.txt"):
            text = p.read_text(encoding="utf-8")
            for stale in ("next story's first fact", "connective of six words or fewer",
                          "connective of a few words", 'simply "Next up..."'):
                assert stale not in text, f"{p.name}: {stale}"
