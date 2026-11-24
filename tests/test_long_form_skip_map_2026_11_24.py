"""The EN long-form opens on the story (Nov 24 2026).

Experiment ``long-form-skip-map-2026-11-24``: on odd episode numbers the
YouTube long-form is rendered from a copy of the mix with the map sentence
spliced out; captions, chapters and cards read that one timeline. The
episode, its feed audio and its podcast chapters are never touched.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parent.parent

LINES = [
    "A satellite dropped twelve kilometers and then climbed back on its own.",
    "This is Orbit Daily, episode one hundred seventy-three.",
    "A larger rocket is in design, a cargo flight was added, and a service "
    "limit is drawing questions, then the Counterpoint.",
    "The satellite used onboard propulsion to answer a burst of drag.",
    "The larger rocket takes lessons from recent flight tests.",
]


def _episode(tmp_path: Path, stem: str = "Orbit_Daily_Ep173_20261124"):
    """A script, a word-timed transcript that follows it, and chapters."""
    (tmp_path / f"{stem}_tts.txt").write_text("\n\n".join(LINES), encoding="utf-8")
    t, segments, starts = 0.0, [], []
    for line in LINES:
        starts.append(t)
        words = []
        for w in line.split():
            words.append({"word": " " + w, "start": round(t, 2), "end": round(t + 0.25, 2)})
            t += 0.3
        segments.append({"start": words[0]["start"], "end": words[-1]["end"],
                         "text": " " + line, "words": words})
        t += 0.6
    tj = tmp_path / f"{stem}_transcript.json"
    tj.write_text(json.dumps({"segments": segments}), encoding="utf-8")
    chapters = tmp_path / "chapters_ep173.json"
    chapters.write_text(json.dumps({"version": "1.2.0", "chapters": [
        {"startTime": 0.0, "title": "Introduction", "endTime": round(starts[3], 2)},
        {"startTime": round(starts[3], 2), "title": "Satellite", "endTime": round(starts[4], 2)},
        {"startTime": round(starts[4], 2), "title": "Rocket", "endTime": round(t, 2)},
    ]}), encoding="utf-8")
    return tj, chapters, starts, t


class TestTheArm:
    def test_ab_cuts_odd_episodes_and_keeps_even(self):
        from engine.short_furniture import long_form_map_arm

        assert long_form_map_arm("ab", 173) == "map_cut"
        assert long_form_map_arm("ab", 172) == "map_kept"
        assert long_form_map_arm("on", 172) == "map_cut"
        assert long_form_map_arm(True, 172) == "map_cut"  # YAML bare `on`

    def test_off_unknown_and_unreadable_are_no_arm(self):
        from engine.short_furniture import long_form_map_arm

        for mode in ("off", "", None, False, "sometimes"):
            assert long_form_map_arm(mode, 173) == ""
        assert long_form_map_arm("ab", None) == ""


class TestTheChapters:
    def test_later_chapters_move_earlier_and_zero_stays(self):
        from engine.short_furniture import shift_chapters

        data = {"chapters": [
            {"startTime": 0.0, "title": "Introduction", "endTime": 23.9},
            {"startTime": 23.9, "title": "A", "endTime": 32.5},
            {"startTime": 32.5, "title": "B"},
        ]}
        out = shift_chapters(data, 12.0, 22.0)
        assert [c["startTime"] for c in out["chapters"]] == [0.0, 13.9, 22.5]
        assert out["chapters"][0]["endTime"] == 13.9
        assert data["chapters"][1]["startTime"] == 23.9  # the input is not edited

    def test_a_start_inside_the_cut_lands_on_its_opening_once(self):
        from engine.short_furniture import shift_chapters

        out = shift_chapters({"chapters": [
            {"startTime": 0.0, "title": "Intro"},
            {"startTime": 14.0, "title": "Inside one"},
            {"startTime": 18.0, "title": "Inside two"},
            {"startTime": 30.0, "title": "After"},
        ]}, 12.0, 22.0)
        assert [(c["title"], c["startTime"]) for c in out["chapters"]] == [
            ("Intro", 0.0), ("Inside one", 12.0), ("After", 20.0)]


class TestTheSplice:
    def test_the_map_is_found_on_a_mapped_episode(self, tmp_path):
        from engine.short_furniture import episode_map_cut

        tj, _chapters, starts, _end = _episode(tmp_path)
        cut = episode_map_cut(tj)
        assert cut is not None
        assert starts[2] - 0.6 <= cut[0] <= starts[2]
        assert starts[3] - 0.6 <= cut[1] <= starts[3]

    def test_no_script_or_no_map_is_no_cut(self, tmp_path):
        from engine.short_furniture import episode_map_cut, spliced_long_source

        tj = tmp_path / "X_Ep001_20261124_transcript.json"
        tj.write_text("{}", encoding="utf-8")
        assert episode_map_cut(tj) is None
        assert spliced_long_source(tmp_path / "x.mp3", tj, None, tmp_path / "w") is None

    def test_one_timeline_for_audio_words_and_chapters(self, tmp_path):
        if not shutil.which("ffmpeg"):
            pytest.skip("ffmpeg not installed")
        from engine.short_furniture import episode_map_cut, spliced_long_source

        tj, chapters, starts, end = _episode(tmp_path)
        src = tmp_path / "Orbit_Daily_Ep173_20261124.wav"
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i",
                        f"sine=frequency=440:duration={end:.2f}", str(src)], check=True)
        cut = episode_map_cut(tj)
        gap = cut[1] - cut[0]
        out = spliced_long_source(src, tj, chapters, tmp_path / "w")
        assert out is not None
        audio, tx, ch, cut_s = out
        assert cut_s == pytest.approx(gap, abs=0.01)
        assert audio.name.endswith("_long_source.flac") and tx.name.endswith("_long_source.json")
        dur = float(subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0",
             str(audio)], capture_output=True, text=True, check=True).stdout)
        assert dur == pytest.approx(end - gap, abs=0.1)
        words = [w for s in json.loads(tx.read_text())["segments"] for w in s["words"]]
        text = " ".join(w["word"].strip() for w in words)
        assert "Counterpoint" not in text and "episode one hundred" in text
        # The first story's opening word now starts where the map did.
        first_story = next(w for w in words if w["word"].strip() == "The")
        assert first_story["start"] == pytest.approx(starts[3] - gap, abs=0.01)
        shifted = json.loads(ch.read_text())["chapters"]
        assert shifted[0]["startTime"] == 0.0
        assert shifted[1]["startTime"] == pytest.approx(starts[3] - gap, abs=0.01)
        # The episode's own chapters file is untouched.
        assert json.loads(chapters.read_text())["chapters"][1]["startTime"] == round(starts[3], 2)
        # The spliced transcript has no script beside it, so nothing downstream
        # (the hook Short, the "Coming up" card) finds a map to cut or show.
        assert episode_map_cut(tx) is None


class TestTheStageSource:
    def _config(self, mode):
        return SimpleNamespace(youtube=SimpleNamespace(long_form_skip_map=mode),
                               audio=SimpleNamespace(voice_intro_delay=0.0))

    def test_keep_arm_and_off_return_the_episode(self, tmp_path):
        import run_show

        tj, chapters, _s, _e = _episode(tmp_path, "Orbit_Daily_Ep172_20261124")
        mp3 = tmp_path / "Orbit_Daily_Ep172_20261124.mp3"
        result: dict = {}
        assert run_show._long_form_source(
            self._config("ab"), 172, mp3, tj, chapters, tmp_path / "w", result
        ) == (mp3, tj, chapters)
        assert result == {"long_form_map_arm": "map_kept"}
        result = {}
        assert run_show._long_form_source(
            self._config("off"), 173, mp3, tj, chapters, tmp_path / "w", result
        ) == (mp3, tj, chapters)
        assert result == {}

    def test_an_episode_without_a_map_is_in_no_arm(self, tmp_path):
        import run_show

        tj = tmp_path / "Tale_Ep011_20261124_transcript.json"
        tj.write_text(json.dumps({"segments": []}), encoding="utf-8")
        (tmp_path / "Tale_Ep011_20261124_tts.txt").write_text(
            "A story opens.\n\nThis is Tale, episode eleven.\n\nIt began in 1696.\n\nThen more.",
            encoding="utf-8")
        result: dict = {}
        mp3 = tmp_path / "Tale_Ep011_20261124.mp3"
        assert run_show._long_form_source(
            self._config("ab"), 11, mp3, tj, tmp_path / "none.json", tmp_path / "w", result
        ) == (mp3, tj, tmp_path / "none.json")
        assert result == {}

    def test_a_failed_splice_keeps_the_episode_and_records_no_arm(self, tmp_path):
        import run_show

        tj, chapters, _s, _e = _episode(tmp_path)
        missing = tmp_path / "Orbit_Daily_Ep173_20261124.mp3"  # no audio on disk
        result: dict = {}
        assert run_show._long_form_source(
            self._config("ab"), 173, missing, tj, chapters, tmp_path / "w", result
        ) == (missing, tj, chapters)
        assert result == {}


class TestTheOpeningPicture:
    """Evergreen b-roll never opens a long-form (the hook is spoken over the
    episode's own first scene); a generated clip still may."""

    def test_scheduled_stills_open_and_clips_follow(self):
        from engine.video import _interleave_broll_into_schedule

        schedule = [(Path(f"/s/{n}.png"), 30.0) for n in "abcdef"]
        clips = [Path("/c/x.mp4"), Path("/c/y.mp4"), Path("/c/z.mp4")]
        visuals = _interleave_broll_into_schedule(schedule, clips, [7.0, 7.0, 7.0])
        assert visuals[0][:2] == (Path("/s/a.png"), False)
        assert [v[0] for v in visuals if v[1]] == clips
        assert [v[0] for v in visuals if not v[1]] == [p for p, _ in schedule]
        assert sum(v[2] for v in visuals) == pytest.approx(180.0)

    def test_one_still_still_opens(self):
        from engine.video import _interleave_broll_into_schedule

        visuals = _interleave_broll_into_schedule(
            [(Path("/s/a.png"), 60.0)], [Path("/c/x.mp4")], [7.0])
        assert [v[1] for v in visuals] == [False, True]

    def test_uniform_path_opens_on_a_still_for_evergreen_clips_only(self):
        from engine.video import _build_hybrid_sequence

        stills = [Path(f"s{i}.jpg") for i in range(4)]
        clips = [Path("c0.mp4"), Path("c1.mp4")]
        evergreen = _build_hybrid_sequence(stills, clips, [5.0, 5.0],
                                           audio_duration_s=120.0, open_on_clip=False)
        assert evergreen[0][1] is False and len([v for v in evergreen if v[1]]) == 2
        generated = _build_hybrid_sequence(stills, clips, [5.0, 5.0], audio_duration_s=120.0)
        assert generated[0][1] is True


class TestWiring:
    def test_switch_metric_index_and_ignore(self):
        import yaml

        from engine.config import YouTubeConfig

        assert YouTubeConfig().long_form_skip_map == "off"
        defaults = yaml.safe_load((ROOT / "shows" / "_defaults.yaml").read_text(encoding="utf-8"))
        assert defaults["youtube"]["long_form_skip_map"] == "ab"
        pipeline = (ROOT / "engine" / "pipeline.py").read_text(encoding="utf-8")
        assert 'metrics.record("long_form_map_arm"' in pipeline
        assert 'metrics.record("long_form_map_cut_s"' in pipeline
        ignore = (ROOT / ".gitignore").read_text(encoding="utf-8")
        assert "digests/*/youtube_tmp/*_long_source.flac" in ignore
        assert "digests/*/youtube_tmp/*_long_source.json" in ignore

    def test_the_stage_reads_one_source_and_keeps_the_episodes_name(self):
        src = (ROOT / "run_show.py").read_text(encoding="utf-8")
        stage = src[src.index("def _publish_youtube("):]
        swap = stage.index("final_mp3, transcript_path, chapters_path = _long_form_source(")
        # Before the Shorts windows, the captions and the render read them.
        assert swap < stage.index("pick_top_n_engaging_windows")
        assert swap < stage.index("transcript_to_srt(")
        assert "base_name = _episode_stem" in stage
        assert 'variant=str(result.get("long_form_map_arm") or "")' in stage
        assert '_video_track["map_cut_s"]' in stage

    def test_a_cut_video_carries_no_audio_sidecars(self, tmp_path):
        from engine.video_feed import _sidecar_assets

        root = tmp_path / "digests" / "orbit"
        root.mkdir(parents=True)
        (root / "chapters_ep173.json").write_text("{}", encoding="utf-8")
        (root / "Orbit_Daily_Ep173_20261124_transcript.json").write_text("{}", encoding="utf-8")
        track = {"filename": "Orbit_Daily_Ep173_20261124.mp4", "url": "https://x/v.mp4"}
        kw = dict(num=173, base_url="https://nerranetwork.com",
                  audio_subdir="digests/orbit", assets_root=tmp_path)
        assert len(_sidecar_assets(track=track, **kw)) == 2
        assert _sidecar_assets(track={**track, "map_cut_s": 9.4}, **kw) == []

    def test_the_durable_index_remembers_the_cut(self, tmp_path):
        from engine import video_index

        config = SimpleNamespace(slug="orbit", episode=SimpleNamespace(
            output_dir="digests/orbit"))
        path = video_index.index_path(config, tmp_path)
        assert video_index.record_from_track(
            config, 173, {"url": "https://x/v.mp4", "bytes": 10, "map_cut_s": 9.42},
            project_root=tmp_path)
        assert video_index.record_from_track(
            config, 172, {"url": "https://x/u.mp4", "bytes": 10}, project_root=tmp_path)
        rows = video_index.indexed_episodes(path)
        assert rows[173]["map_cut_s"] == 9.42 and "map_cut_s" not in rows[172]

    def test_the_register_names_the_experiment(self):
        import yaml

        reg = yaml.safe_load((ROOT / "docs" / "experiments.yaml").read_text(encoding="utf-8"))
        ids = {e["id"] for e in reg["experiments"]}
        assert "long-form-skip-map-2026-11-24" in ids
