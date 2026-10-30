"""Oct 30 2026 — the hook Short skips the episode's map.

Since Oct 20 every English opening runs hook, identity line, then a map of
the stories that follow; the hook Short is a clip of that opening, so for
~9 s of a ~32 s Short it read a list of other stories. At age 5 days the
Shorts published after Oct 20 held viewers for less (EN 16.0 -> 13.5 s,
FR 16 -> 13, RU 19 -> 17) and EN flagship reach at day 3 fell about 3x.
engine/short_furniture.py cuts the map out of the Short's SOURCE (mix and
transcript); the episode is untouched.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
TST = ROOT / "digests" / "tesla_shorts_time"
EP650 = TST / "Tesla_Shorts_Time_Pod_Ep650_20261030"
EP637 = TST / "Tesla_Shorts_Time_Pod_Ep637_20261017"


def _script(stem: Path) -> str:
    from engine.utils import strip_speech_tags

    return strip_speech_tags((stem.parent / (stem.name + "_tts.txt")).read_text(encoding="utf-8"))


def _tx(stem: Path) -> dict:
    return json.loads((stem.parent / (stem.name + "_transcript.json")).read_text(encoding="utf-8"))


class TestFindingTheMap:
    def test_a_map_after_the_identity_line(self):
        from engine import story_breaks as sb
        from engine.short_furniture import map_line_range

        rng = map_line_range(_script(EP650))
        assert rng is not None
        line = sb.script_lines(_script(EP650))[rng[0]]
        assert line.startswith("Quiet Mode on Model Y")

    def test_a_lead_sentence_is_never_a_map(self):
        """Ep637 was written before maps: its second line continues the lead
        ("Those packs hold ..., according to ...")."""
        from engine.short_furniture import map_cut, map_line_range

        assert map_line_range(_script(EP637)) is None
        assert map_cut(_script(EP637), _tx(EP637)) is None

    def test_no_false_positive_before_maps_existed(self):
        """Every committed English episode of Oct 1-19: no map, no cut."""
        from engine.short_furniture import map_cut
        from engine.utils import strip_speech_tags

        checked = 0
        for tj in sorted((ROOT / "digests").glob("*/*_202610[01][0-9]_transcript.json")):
            if tj.name[-24:-16] > "20261019":
                continue
            tts = tj.with_name(tj.name.replace("_transcript.json", "_tts.txt"))
            if not tts.exists():
                continue
            checked += 1
            script = strip_speech_tags(tts.read_text(encoding="utf-8"))
            assert map_cut(script, json.loads(tj.read_text(encoding="utf-8"))) is None, tj.name
        assert checked > 100

    @pytest.mark.parametrize("line,expected", [
        ("Colonial Hills home offers, a Cursor marketplace backdoor, and a Ukraine "
         "Starlink throttle come next, then The Counterpoint.", True),
        ("Massey's gets a Ship 42 firing, Telesat books Falcon 9s, then the Air Force flies.", True),
        ("Those packs hold the array's output for night and for overcast days, "
         "according to my broadband.", False),
        ("The new name is the U K Mission, Jerusalem. A Foreign Secretary statement "
         "says the change follows.", False),
    ])
    def test_the_map_test(self, line, expected):
        from engine.short_furniture import is_map_line

        assert is_map_line(line) is expected


class TestTheCut:
    def test_ep650_cut_lands_between_identity_and_story(self):
        from engine.short_furniture import map_cut, splice_transcript

        cut = map_cut(_script(EP650), _tx(EP650))
        assert cut is not None
        a, b = cut
        assert 8.0 < a < 11.0 and 5.0 < b - a < 12.0
        spliced = splice_transcript(_tx(EP650), a, b)
        # The Short's window: the first 35 s of the spliced source.
        text = "".join(w["word"].strip() for s in spliced["segments"]
                       for w in s["words"] if w["start"] < 35)
        assert "episode650.Houston'sRobotaxipromotion" in text
        assert "QuietMode" not in text and "Quietmode" not in text
        # Every word keeps its order and later words move earlier by the cut.
        starts = [w["start"] for s in spliced["segments"] for w in s["words"]]
        assert starts == sorted(starts)

    def test_most_mapped_episodes_get_a_cut(self):
        from engine.short_furniture import map_cut
        from engine.utils import strip_speech_tags

        found = total = 0
        for tj in sorted((ROOT / "digests").glob("*/*_20261030_transcript.json")):
            tts = tj.with_name(tj.name.replace("_transcript.json", "_tts.txt"))
            if not tts.exists():
                continue
            total += 1
            cut = map_cut(strip_speech_tags(tts.read_text(encoding="utf-8")),
                          json.loads(tj.read_text(encoding="utf-8")))
            if cut:
                found += 1
                assert 1.0 <= cut[1] - cut[0] <= 20.0
        assert total and found >= total // 2

    def test_the_splice_command_fades_both_sides(self):
        from engine.short_furniture import splice_audio_cmd

        cmd = splice_audio_cmd(Path("in.mp3"), Path("out.flac"), 9.5, 18.0)
        graph = cmd[cmd.index("-filter_complex") + 1]
        assert "atrim=0:9.500" in graph and "atrim=start=18.000" in graph
        assert graph.count("afade") == 2 and "concat=n=2:v=0:a=1" in graph
        assert cmd[-2:] == ["flac", "out.flac"]

    def test_a_real_splice_is_shorter_by_the_cut(self, tmp_path):
        ffmpeg = shutil.which("ffmpeg")
        if not ffmpeg:
            pytest.skip("ffmpeg not installed")
        from engine.short_furniture import splice_audio_cmd

        src = tmp_path / "tone.wav"
        subprocess.run([ffmpeg, "-y", "-loglevel", "error", "-f", "lavfi", "-i",
                        "sine=frequency=440:duration=6", str(src)], check=True)
        out = tmp_path / "out.flac"
        subprocess.run(splice_audio_cmd(src, out, 2.0, 4.5), check=True)
        dur = float(subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(out)],
            capture_output=True, text=True, check=True).stdout)
        assert dur == pytest.approx(3.5, abs=0.05)

    def test_no_script_beside_the_transcript_is_no_cut(self, tmp_path):
        from engine.short_furniture import spliced_short_source

        tj = tmp_path / "X_Ep001_20261030_transcript.json"
        tj.write_text("{}", encoding="utf-8")
        assert spliced_short_source(tmp_path / "x.mp3", tj, tmp_path / "w") is None


class TestWiring:
    def test_switch_and_metric(self):
        import yaml

        from engine.config import YouTubeConfig

        assert YouTubeConfig().shorts_skip_map is False
        defaults = yaml.safe_load((ROOT / "shows" / "_defaults.yaml").read_text(encoding="utf-8"))
        assert defaults["youtube"]["shorts_skip_map"] is True
        assert 'metrics.record("shorts_map_cut_s"' in (ROOT / "engine" / "pipeline.py").read_text(encoding="utf-8")

    def test_the_hook_short_renders_from_the_spliced_source(self):
        src = (ROOT / "run_show.py").read_text(encoding="utf-8")
        helper = src[src.index("def _short_source("):src.index("def _publish_youtube(")]
        assert 'short_idx == 0 and fill_mode == "hook_open"' in helper
        assert "spliced_short_source(" in helper
        assert 'result["shorts_map_cut_s"]' in helper
        loop = src[src.index("for short_idx, (this_offset, this_hook, _fill_mode) in enumerate(shorts_plan):"):
                   src.index("# ---- Aggregate results onto ``result`` ----")]
        assert "_short_source(" in loop
        # Inside the loop every Short reads its own source, never the episode's.
        after_setup = loop[loop.index("_short_source("):]
        after_setup = after_setup[after_setup.index(")") + 1:]
        for name in ("final_mp3", "transcript_path", "_transcript_words"):
            assert name not in after_setup, name
        assert "_src_audio, cover_path, this_short_video_path" in loop

    def test_the_helper_returns_the_episode_for_every_other_short(self, tmp_path):
        import importlib

        rs = importlib.import_module("run_show")

        class YT:
            shorts_skip_map = True

        out = rs._short_source(YT(), 1, "qualified", Path("a.mp3"), Path("t.json"),
                               [{"word": "x"}], tmp_path, 0.0, {})
        assert out == (Path("a.mp3"), Path("t.json"), [{"word": "x"}])
        YT.shorts_skip_map = False
        out = rs._short_source(YT(), 0, "hook_open", Path("a.mp3"), Path("t.json"),
                               [], tmp_path, 0.0, {})
        assert out == (Path("a.mp3"), Path("t.json"), [])
