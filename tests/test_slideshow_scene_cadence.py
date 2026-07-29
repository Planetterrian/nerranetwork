"""Drift guard for the May 8 2026 slideshow scene-cadence fix.

Operator caught the long-form video using a fixed 12 s/scene cadence:
8 scenes × 12 s = 96 s slideshow, then ``-stream_loop -1`` cycled
that 96-second clip across the full 5-10 minute audio. Result:
listeners saw the same eight photos on repeat 3-6 times per episode.

Fix: ``build_long_form_video`` now computes
``scene_duration = max(8.0, audio_duration / len(scene_paths))`` so
the slideshow naturally spans the full audio without visible loops.
A 6-minute episode → 8 scenes × ~45 s each. A 30 s teaser →
8 scenes × ~8 s (floor). A 30-minute deep-dive → 8 scenes × ~225 s
(Ken Burns zoom keeps long holds watchable).

These tests pin the math directly by mocking the slideshow render
and audio-duration probe.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest


@pytest.fixture
def stub_paths(tmp_path):
    audio = tmp_path / "ep.mp3"
    audio.write_bytes(b"\x00" * 1024)
    cover = tmp_path / "cover.jpg"
    cover.write_bytes(b"\x00" * 1024)
    out = tmp_path / "ep.mp4"
    scenes = []
    for i in range(8):
        p = tmp_path / f"scene_{i}.jpg"
        p.write_bytes(b"\x00")
        scenes.append(p)
    return {"audio": audio, "cover": cover, "out": out, "scenes": scenes}


def _capture(stub_paths, audio_duration_s, num_scenes=8, *, single_pass=False):
    """Run build_long_form_video with mocks and return what cadence the
    render was asked for: ``{"scene_duration", "n_scenes"}``.

    Both render paths are covered. The two-stage path is read from the
    ``_render_slideshow`` call; the fused single-pass path (default since
    July 29 2026) is read from ``_single_pass_long_form_cmd``. They share
    ``_uniform_slideshow_plan``, and these tests exist to keep it that
    way — a cost or speed change to the render must never quietly alter
    how long a viewer stares at one image.
    """
    from engine import video

    captured = {}

    def _fake_render_slideshow(scene_paths, output, *,
                               scene_duration=None, **kwargs):
        captured["scene_duration"] = scene_duration
        captured["n_scenes"] = len(scene_paths)
        # Pretend the render produced an output the caller can chain on.
        Path(output).write_bytes(b"\x00")
        return Path(output)

    def _fake_single_pass_cmd(scenes, *args, scene_duration=None,
                              scene_durations=None, **kwargs):
        captured["scene_duration"] = scene_duration
        captured["n_scenes"] = len(scenes)
        captured["scene_durations"] = scene_durations
        return ["true"]

    def _fake_subprocess_run(cmd, **kwargs):
        class _R:
            returncode = 0
            stderr = b""
        return _R()

    with patch.object(video, "_render_slideshow", _fake_render_slideshow), \
         patch.object(video, "_long_form_cmd", lambda *a, **k: ["true"]), \
         patch.object(video, "_single_pass_long_form_cmd", _fake_single_pass_cmd), \
         patch.object(video, "_single_pass_enabled", lambda: single_pass), \
         patch("subprocess.run", _fake_subprocess_run), \
         patch("engine.audio.get_audio_duration", return_value=audio_duration_s):
        scenes = stub_paths["scenes"][:num_scenes]
        video.build_long_form_video(
            stub_paths["audio"], stub_paths["cover"], stub_paths["out"],
            scene_paths=scenes,
        )
    return captured


def _capture_scene_duration(stub_paths, audio_duration_s, num_scenes=8,
                            *, single_pass=False):
    return _capture(stub_paths, audio_duration_s, num_scenes,
                    single_pass=single_pass).get("scene_duration")


@pytest.fixture(params=[False, True], ids=["two_stage", "single_pass"])
def render_path(request):
    """Every cadence assertion runs against BOTH render paths."""
    return request.param


class TestSceneCadenceMatchesAudio:

    def test_six_minute_episode_cycles_to_15s_cap(self, stub_paths, render_path):
        """June 2026 motion pass: scenes CYCLE so no image holds longer than
        ~15 s (was 25 s; 360 s/8 = 45 s/scene used to ship — visually static;
        the scene list now repeats in rotation at zero added image cost).
        360/15 = 24 slots — exactly the render-safe slot cap, so the 15 s
        preference still wins."""
        dur = _capture_scene_duration(stub_paths, audio_duration_s=360.0,
                                      single_pass=render_path)
        assert dur is not None and 8.0 <= dur <= 15.0, (
            f"Expected ≤15 s/scene after cycling for 360 s/8, got {dur}"
        )

    def test_ten_minute_episode_respects_slot_cap(self, stub_paths, render_path):
        """600 s @ 15 s would be 40 slots; the render-safe cap (24) binds
        and holds stretch to 600/24 = 25 s. Still far below the pre-motion
        75 s/scene static look."""
        from engine.scene_scheduler import _MAX_SLIDESHOW_SLOTS
        dur = _capture_scene_duration(stub_paths, audio_duration_s=600.0,
                                      single_pass=render_path)
        assert dur is not None
        assert 8.0 <= dur <= (600.0 / _MAX_SLIDESHOW_SLOTS) + 0.01
        # Cap must have fired — uncapped would be ≤15 s.
        assert dur > 15.0

    def test_seventeen_minute_episode_stays_under_slot_cap(
            self, stub_paths, render_path):
        """Ep537-class (1044 s): prove the uniform cycling path never asks
        ffmpeg for more than _MAX_SLIDESHOW_SLOTS inputs."""
        from engine.scene_scheduler import _MAX_SLIDESHOW_SLOTS

        got = _capture(stub_paths, 1044.0, num_scenes=4,
                       single_pass=render_path)
        assert got["n_scenes"] == _MAX_SLIDESHOW_SLOTS
        assert got["scene_duration"] == pytest.approx(
            1044.0 / _MAX_SLIDESHOW_SLOTS, rel=0.01,
        )

    def test_thirty_second_teaser_clamps_to_floor(self, stub_paths, render_path):
        """Very short audio gets clamped to the 8 s floor so scenes
        don't whip past faster than the eye can register."""
        dur = _capture_scene_duration(stub_paths, audio_duration_s=30.0,
                                      single_pass=render_path)
        assert dur == 8.0, f"Floor should clamp short episodes; got {dur}"

    def test_zero_or_unknown_audio_falls_back_to_legacy_12s(self, stub_paths, render_path):
        """If ``get_audio_duration`` can't read the file (returns 0),
        keep the legacy 12 s default rather than producing a 0-second
        slideshow that would crash the slideshow render."""
        from engine.video import _SCENE_DURATION_SECONDS
        dur = _capture_scene_duration(stub_paths, audio_duration_s=0.0,
                                      single_pass=render_path)
        assert dur == _SCENE_DURATION_SECONDS

    def test_three_scenes_for_short_episode_still_floors(self, stub_paths, render_path):
        """Short audio + small scene count: 30 s / 3 = 10 s per scene
        (above floor); floor doesn't kick in here, no clamping needed."""
        dur = _capture_scene_duration(
            stub_paths, audio_duration_s=30.0, num_scenes=3,
            single_pass=render_path,
        )
        assert dur == pytest.approx(10.0, rel=0.01)
