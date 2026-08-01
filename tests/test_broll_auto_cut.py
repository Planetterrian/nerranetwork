"""Drift guards for automatic b-roll segmentation + per-episode variety.

Two halves of one goal — daily long-forms that don't look like each
other:

* ``scripts/cut_broll_segments.py`` mines many short accents out of long
  source masters, so the pool is deep enough for variety to be possible
  without the operator scrubbing hours of tape.
* ``gallery_library.rotate_for_episode`` makes the render actually USE
  that depth. Before it, the pool was consumed in fixed committed order,
  so every episode of a show shipped the same first three clips no
  matter how large the pool grew.
"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
_SCRIPTS = PROJECT_ROOT / "scripts"
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

import cut_broll_segments as C  # noqa: E402
from engine import gallery_library as gl  # noqa: E402


# ---------------------------------------------------------------------------
# Motion probe parsing
# ---------------------------------------------------------------------------


class TestParseMotionOutput:
    def test_parses_ffmpeg_metadata_pairs(self):
        text = (
            "frame:0    pts:0      pts_time:0\n"
            "lavfi.scene_score=0.000000\n"
            "frame:1    pts:1024   pts_time:0.5\n"
            "lavfi.scene_score=0.123456\n"
            "frame:2    pts:2048   pts_time:1\n"
            "lavfi.scene_score=0.400000\n"
        )
        assert C.parse_motion_output(text) == [
            (0.0, 0.0), (0.5, 0.123456), (1.0, 0.4),
        ]

    def test_ignores_ffmpeg_log_noise(self):
        text = (
            "ffmpeg version 7.1 Copyright (c) 2000-2024\n"
            "  Stream #0:0: Video: h264, yuv420p, 1920x1080\n"
            "frame:1    pts:1024   pts_time:2.5\n"
            "lavfi.scene_score=0.050000\n"
        )
        assert C.parse_motion_output(text) == [(2.5, 0.05)]

    def test_empty_input_is_empty(self):
        assert C.parse_motion_output("") == []
        assert C.parse_motion_output(None) == []


# ---------------------------------------------------------------------------
# Segment selection (pure)
# ---------------------------------------------------------------------------


def _samples(spec):
    """[(start, end, score)] → 2 fps samples covering the range."""
    out = []
    for start, end, score in spec:
        t = start
        while t < end:
            out.append((round(t, 2), score))
            t += 0.5
    return out


class TestPickSegments:
    def test_prefers_sustained_motion_over_static_holds(self):
        samples = _samples([
            (0, 60, 0.001),     # long locked-off hold
            (60, 120, 0.05),    # something moving
        ])
        picks = C.pick_segments(samples, segment_s=7.0, max_segments=1,
                                min_gap_s=10.0, skip_head_s=8.0)
        assert len(picks) == 1
        assert picks[0][0] >= 60.0

    def test_never_spans_a_hard_cut(self):
        # A cut sits at t=40; no chosen window may contain it.
        samples = _samples([(0, 40, 0.05)]) + [(40.0, 0.9)] + _samples(
            [(40.5, 120, 0.05)])
        picks = C.pick_segments(samples, segment_s=7.0, max_segments=5,
                                min_gap_s=5.0, skip_head_s=0.0)
        assert picks
        for start, end, _score in picks:
            assert not (start < 40.0 < end), f"window {start}-{end} spans cut"

    def test_skips_the_head_where_slates_live(self):
        samples = _samples([(0, 120, 0.05)])
        picks = C.pick_segments(samples, segment_s=7.0, max_segments=3,
                                min_gap_s=10.0, skip_head_s=30.0)
        assert picks
        assert all(start >= 30.0 for start, _e, _s in picks)

    def test_spreads_picks_across_the_source(self):
        samples = _samples([(0, 600, 0.05)])
        picks = C.pick_segments(samples, segment_s=7.0, max_segments=5,
                                min_gap_s=60.0, skip_head_s=8.0)
        starts = sorted(p[0] for p in picks)
        assert len(starts) >= 2
        for a, b in zip(starts, starts[1:]):
            assert b - a >= 60.0

    def test_rejects_a_wholly_static_source(self):
        """Better three good clips than five padded with dead holds."""
        samples = _samples([(0, 300, 0.0001)])
        assert C.pick_segments(samples, segment_s=7.0, max_segments=5,
                               min_gap_s=10.0, skip_head_s=8.0) == []

    def test_never_runs_past_the_end_of_the_source(self):
        samples = _samples([(0, 60, 0.05)])
        picks = C.pick_segments(samples, segment_s=7.0, max_segments=9,
                                min_gap_s=1.0, skip_head_s=0.0)
        assert picks
        assert all(end <= 60.0 for _s, end, _sc in picks)

    def test_respects_max_segments(self):
        samples = _samples([(0, 600, 0.05)])
        picks = C.pick_segments(samples, segment_s=7.0, max_segments=3,
                                min_gap_s=10.0, skip_head_s=0.0)
        assert len(picks) == 3

    def test_degenerate_inputs_are_empty(self):
        assert C.pick_segments([], segment_s=7.0) == []
        assert C.pick_segments(_samples([(0, 60, 0.05)]), segment_s=0) == []
        assert C.pick_segments(_samples([(0, 60, 0.05)]),
                               max_segments=0) == []

    def test_returns_best_first(self):
        samples = (_samples([(0, 100, 0.02)])
                   + _samples([(100, 200, 0.09)])
                   + _samples([(200, 300, 0.05)]))
        picks = C.pick_segments(samples, segment_s=7.0, max_segments=3,
                                min_gap_s=30.0, skip_head_s=8.0)
        scores = [p[2] for p in picks]
        assert scores == sorted(scores, reverse=True)


class TestCutSegmentCommand:
    def test_reencodes_rather_than_stream_copies(self, monkeypatch, tmp_path):
        captured = {}
        monkeypatch.setattr(C.subprocess, "run",
                            lambda cmd, **k: captured.setdefault("cmd", cmd))
        C.cut_segment(tmp_path / "src.mp4", 84.0, 92.0, tmp_path / "o.mp4")
        cmd = captured["cmd"]
        assert "-ss" in cmd and "84.000" in cmd
        assert "-to" in cmd and "92.000" in cmd
        assert "libx264" in cmd and "copy" not in cmd

    def test_attribution_rides_from_source_provenance(self, tmp_path):
        (tmp_path / "_provenance.json").write_text(
            '[{"file": "src.mp4", "attribution": "NASA (public domain)"}]',
            encoding="utf-8")
        assert C._source_attribution(tmp_path / "src.mp4") == \
            "NASA (public domain)"

    def test_missing_provenance_is_blank_not_an_error(self, tmp_path):
        assert C._source_attribution(tmp_path / "src.mp4") == ""


# ---------------------------------------------------------------------------
# Per-episode rotation
# ---------------------------------------------------------------------------


class TestRotateForEpisode:
    def _pool(self, n):
        return [{"url": f"https://r2/c{i}.mp4"} for i in range(n)]

    def test_consecutive_episodes_share_no_clips(self):
        """The strong property: back-to-back episodes are disjoint, so a
        daily viewer never sees the same accent two days running."""
        pool = self._pool(12)
        slices = [
            set(c["url"] for c in gl.rotate_for_episode(
                pool, f"spacex:ep{n:03d}", 3))
            for n in range(1, 11)
        ]
        for day, (a, b) in enumerate(zip(slices, slices[1:]), start=1):
            assert not (a & b), f"ep{day} and ep{day + 1} overlap: {a & b}"

    def test_every_episode_gets_a_distinct_set(self):
        pool = self._pool(12)
        slices = [
            tuple(c["url"] for c in gl.rotate_for_episode(
                pool, f"spacex:ep{n:03d}", 3))
            for n in range(1, 5)
        ]
        assert len(set(slices)) == 4, slices

    def test_is_deterministic_for_the_same_episode(self):
        pool = self._pool(12)
        a = gl.rotate_for_episode(pool, "spacex:ep053", 3)
        b = gl.rotate_for_episode(pool, "spacex:ep053", 3)
        assert a == b

    def test_no_seed_preserves_legacy_committed_order(self):
        pool = self._pool(5)
        assert gl.rotate_for_episode(pool, None, 3) == pool[:3]
        assert gl.rotate_for_episode(pool, "", 3) == pool[:3]

    def test_shows_diverge_on_the_same_episode_number(self):
        pool = self._pool(12)
        a = gl.rotate_for_episode(pool, "spacex:ep010", 3)
        b = gl.rotate_for_episode(pool, "tesla:ep010", 3)
        assert a != b

    def test_pool_smaller_than_limit_is_safe(self):
        pool = self._pool(2)
        got = gl.rotate_for_episode(pool, "spacex:ep001", 5)
        assert len(got) == 2

    def test_empty_pool_is_empty(self):
        assert gl.rotate_for_episode([], "spacex:ep001", 3) == []

    def test_rotation_walks_the_whole_pool_over_time(self):
        """Every clip should get screen time across a month of episodes,
        not just the first three forever."""
        pool = self._pool(10)
        seen = set()
        for n in range(1, 31):
            for c in gl.rotate_for_episode(pool, f"spacex:ep{n:03d}", 3):
                seen.add(c["url"])
        assert len(seen) == 10


class TestWiring:
    def test_visual_reuse_passes_an_episode_seed(self):
        src = (PROJECT_ROOT / "engine" / "visual_reuse.py").read_text(
            encoding="utf-8")
        assert "episode_seed=" in src
        assert "broll_clips_per_episode" in src

    def test_config_exposes_the_width_knob(self):
        from engine.config import load_config
        cfg = load_config("shows/spacex.yaml")
        assert getattr(cfg.youtube, "broll_clips_per_episode", None) == 3
