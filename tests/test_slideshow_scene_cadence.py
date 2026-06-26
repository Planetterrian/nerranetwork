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


def _capture_scene_duration(stub_paths, audio_duration_s, num_scenes=8):
    """Run build_long_form_video with mocks and return the
    scene_duration argument that was passed to _render_slideshow.

    Mocks bypass the actual ffmpeg invocation so the test is fast
    and deterministic.
    """
    from engine import video

    captured = {}

    def _fake_render_slideshow(scene_paths, output, *,
                               scene_duration=None, **kwargs):
        captured["scene_duration"] = scene_duration
        # Pretend the render produced an output the caller can chain on.
        Path(output).write_bytes(b"\x00")
        return Path(output)

    def _fake_long_form_cmd(*args, **kwargs):
        return ["true"]  # noop

    def _fake_subprocess_run(cmd, **kwargs):
        class _R:
            returncode = 0
            stderr = b""
        # Touch the expected output so the caller doesn't 404 it.
        if "out" in kwargs:
            pass
        return _R()

    with patch.object(video, "_render_slideshow", _fake_render_slideshow), \
         patch.object(video, "_long_form_cmd", _fake_long_form_cmd), \
         patch("subprocess.run", _fake_subprocess_run), \
         patch("engine.audio.get_audio_duration", return_value=audio_duration_s):
        scenes = stub_paths["scenes"][:num_scenes]
        video.build_long_form_video(
            stub_paths["audio"], stub_paths["cover"], stub_paths["out"],
            scene_paths=scenes,
        )
    return captured.get("scene_duration")


class TestSceneCadenceMatchesAudio:

    def test_six_minute_episode_cycles_to_15s_cap(self, stub_paths):
        """June 2026 motion pass: scenes CYCLE so no image holds longer than
        ~15 s (was 25 s; 360 s/8 = 45 s/scene used to ship — visually static;
        the scene list now repeats in rotation at zero added image cost)."""
        dur = _capture_scene_duration(stub_paths, audio_duration_s=360.0)
        assert dur is not None and 8.0 <= dur <= 15.0, (
            f"Expected ≤15 s/scene after cycling for 360 s/8, got {dur}"
        )

    def test_ten_minute_episode_cycles_to_15s_cap(self, stub_paths):
        """600 s/8 = 75 s/scene pre-fix; cycling caps the hold at ≤15 s."""
        dur = _capture_scene_duration(stub_paths, audio_duration_s=600.0)
        assert dur is not None and 8.0 <= dur <= 15.0

    def test_thirty_second_teaser_clamps_to_floor(self, stub_paths):
        """Very short audio gets clamped to the 8 s floor so scenes
        don't whip past faster than the eye can register."""
        dur = _capture_scene_duration(stub_paths, audio_duration_s=30.0)
        assert dur == 8.0, f"Floor should clamp short episodes; got {dur}"

    def test_zero_or_unknown_audio_falls_back_to_legacy_12s(self, stub_paths):
        """If ``get_audio_duration`` can't read the file (returns 0),
        keep the legacy 12 s default rather than producing a 0-second
        slideshow that would crash the slideshow render."""
        from engine.video import _SCENE_DURATION_SECONDS
        dur = _capture_scene_duration(stub_paths, audio_duration_s=0.0)
        assert dur == _SCENE_DURATION_SECONDS

    def test_three_scenes_for_short_episode_still_floors(self, stub_paths):
        """Short audio + small scene count: 30 s / 3 = 10 s per scene
        (above floor); floor doesn't kick in here, no clamping needed."""
        dur = _capture_scene_duration(
            stub_paths, audio_duration_s=30.0, num_scenes=3,
        )
        assert dur == pytest.approx(10.0, rel=0.01)
