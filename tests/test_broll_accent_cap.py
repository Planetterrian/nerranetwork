"""Drift guards: a pool b-roll clip is an ACCENT, never a takeover.

The evergreen b-roll pool was designed around the recovered Grok Video
clips (~5 s each), so nothing ever bounded a clip's LENGTH — the
interleaver used each file's full duration verbatim. The first
real-footage pool (2026-08-01: NASA "Isolated Launch Views", 229 s to
2442 s per file) would have asked for ~72 minutes of b-roll inside a
~10 minute episode: ``_interleave_broll_into_schedule``'s
``factor = (total - clip_total)/total`` goes to 0, every still collapses
to its 1 s floor, and ffmpeg decodes 40-minute inputs in a pipeline that
already runs near a 40-minute timeout.

Caught before the first render that would have used it.
"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
_SCRIPTS = PROJECT_ROOT / "scripts"
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

import pytest  # noqa: E402

from engine import video as V  # noqa: E402


class TestAccentCap:
    def test_cap_is_short_enough_to_be_an_accent(self):
        assert 0 < V._MAX_BROLL_SEGMENT_S <= 15.0

    def test_runner_clamps_long_clips(self):
        """The clamp lives in the long-form runner where clip_durs is
        built; pin it so a refactor cannot drop it silently."""
        src = (PROJECT_ROOT / "engine" / "video.py").read_text(
            encoding="utf-8")
        assert "_MAX_BROLL_SEGMENT_S" in src
        assert "raw_dur = _MAX_BROLL_SEGMENT_S" in src

    def test_real_nasa_durations_would_have_swamped_an_episode(self):
        """The concrete regression, with the real numbers."""
        episode_s = 600.0
        nasa = [506.4, 1396.7, 2442.0]  # DART, IMAP, GOES-U as uploaded
        assert sum(nasa) > 7 * episode_s           # the bug (~72 min)
        clamped = [min(d, V._MAX_BROLL_SEGMENT_S) for d in nasa]
        assert sum(clamped) < 0.1 * episode_s      # the fix

    def test_stills_keep_real_holds_after_clamping(self):
        """With the clamp, the interleaver leaves stills their time."""
        schedule = [(Path(f"s{i}.jpg"), 60.0) for i in range(10)]  # 600 s
        clips = [Path("a.mp4"), Path("b.mp4"), Path("c.mp4")]
        durs = [V._MAX_BROLL_SEGMENT_S] * 3
        visuals = V._interleave_broll_into_schedule(schedule, clips, durs)
        still_holds = [d for _p, is_v, d in visuals if not is_v]
        # Every still keeps a real hold, not the 1.0 s collapse floor.
        assert min(still_holds) > 30.0
        total = sum(d for _p, _v, d in visuals)
        assert 590.0 <= total <= 610.0

    def test_unclamped_long_clips_would_collapse_stills(self):
        """Guard the guard: prove the failure mode is real, so this
        test fails loudly if the clamp is ever removed upstream."""
        schedule = [(Path(f"s{i}.jpg"), 60.0) for i in range(10)]
        visuals = V._interleave_broll_into_schedule(
            schedule, [Path("a.mp4")], [2442.0])
        still_holds = [d for _p, is_v, d in visuals if not is_v]
        assert max(still_holds) == 1.0  # the collapse


class TestHybridInputTrim:
    def test_video_inputs_carry_input_level_t(self):
        """Without ``-t`` before ``-i`` ffmpeg decodes the whole source;
        free on a 5 s generated clip, ruinous on a 40-minute master."""
        visuals = [
            (Path("clip.mp4"), True, 8.0),
            (Path("still.jpg"), False, 30.0),
        ]
        cmd = V._hybrid_slideshow_cmd(visuals, Path("/tmp/out.mp4"))
        i_clip = cmd.index("clip.mp4")
        assert cmd[i_clip - 1] == "-i"
        assert cmd[i_clip - 2] == "8.00"
        assert cmd[i_clip - 3] == "-t"

    def test_graph_still_trims_video_segments(self):
        graph = V._hybrid_filter_graph([(Path("c.mp4"), True, 8.0)])
        assert "trim=duration=8.00" in graph


class TestPoolTrimOption:
    def _mod(self):
        import build_broll_pool
        return build_broll_pool

    def test_parses_common_forms(self):
        m = self._mod()
        assert m.parse_trim("1:24-1:32") == (84.0, 92.0)
        assert m.parse_trim("0:10-0:18") == (10.0, 18.0)
        assert m.parse_trim("1:02:10-1:02:18") == (3730.0, 3738.0)

    def test_rejects_garbage_and_inverted_ranges(self):
        m = self._mod()
        for bad in ("liftoff", "1:24", "", "1:32-1:24", "1:24-1:24"):
            with pytest.raises(ValueError):
                m.parse_trim(bad)

    def test_trim_command_reencodes_for_frame_accuracy(self, monkeypatch,
                                                       tmp_path):
        """A keyframe-aligned stream copy can drift by seconds, which at
        accent length is the entire clip."""
        m = self._mod()
        captured = {}

        def _run(cmd, **kwargs):
            captured["cmd"] = cmd

            class _P:
                returncode = 0
            return _P()

        monkeypatch.setattr(m.subprocess, "run", _run)
        src = tmp_path / "src.mp4"
        src.write_bytes(b"x")
        m.trim_clip(src, "1:24-1:32", tmp_path)
        cmd = captured["cmd"]
        assert "-ss" in cmd and "84.000" in cmd
        assert "-to" in cmd and "92.000" in cmd
        assert "libx264" in cmd
        assert "copy" not in cmd

    def test_long_clip_warning_threshold_exceeds_accent_length(self):
        m = self._mod()
        assert m.ACCENT_SECONDS < m.LONG_CLIP_WARN_SECONDS
        assert m.ACCENT_SECONDS == V._MAX_BROLL_SEGMENT_S
