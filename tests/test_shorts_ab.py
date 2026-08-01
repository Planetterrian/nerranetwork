"""Drift guards for the Shorts motion A/B (July 2026, SpaceX pilot).

Three ways this experiment could quietly produce a wrong answer, and the
tests that stop each one:

  1. **No control.** If the plan ever put every Short in the treatment
     arm there would be nothing to compare against. Index 0 is reserved.
  2. **A disguised treatment arm.** If a Short that fell back to stills
     were still recorded as ``grok_video``, the treatment arm would
     contain control episodes and the comparison would regress toward
     "no difference" no matter what the truth is.
  3. **A verdict called early.** One viral Short can move a mean by
     hundreds of percent, so the report must refuse to compare small
     samples and must widen, not narrow, when the arms overlap.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from engine import shorts_ab  # noqa: E402
from engine.config import load_config  # noqa: E402


@pytest.fixture()
def spacex():
    return load_config(ROOT / "shows" / "spacex.yaml")


# ---------------------------------------------------------------------------
# Assignment
# ---------------------------------------------------------------------------

class TestPlanVariants:
    def test_spacex_enrollment_ended_by_operator_verdict(self, spacex):
        """2026-08-01: the operator reviewed the spacex videos and chose
        real NASA b-roll over paid generated motion — the experiment
        ended with ZERO analytics-rated episodes in either arm. The
        machinery stays (config retained for a one-line re-enable), but
        no show is enrolled and spacex ships all-stills plans."""
        assert shorts_ab.is_enabled(spacex) is False
        assert shorts_ab.plan_variants(spacex, 2) == [
            shorts_ab.VARIANT_STILLS, shorts_ab.VARIANT_STILLS,
        ]

    def test_index_zero_is_always_the_control(self, spacex):
        # Even if someone configures index 0, keeping a control is the
        # point of the experiment.
        spacex.youtube.shorts_ab_video_indexes = [0, 1]
        plan = shorts_ab.plan_variants(spacex, 2)
        assert plan[0] == shorts_ab.VARIANT_STILLS

    def test_a_single_short_day_ships_the_control(self, spacex):
        # The adaptive policy can drop a show to one Short; there is no
        # room for both arms that day, so the control wins.
        assert shorts_ab.plan_variants(spacex, 1) == [shorts_ab.VARIANT_STILLS]

    def test_out_of_range_indexes_are_ignored(self, spacex):
        spacex.youtube.shorts_ab_video_indexes = [5]
        assert shorts_ab.plan_variants(spacex, 2) == \
            [shorts_ab.VARIANT_STILLS] * 2

    def test_junk_indexes_do_not_crash_a_publish(self, spacex):
        spacex.youtube.shorts_ab_enabled = True  # machinery test
        spacex.youtube.shorts_ab_video_indexes = ["x", None, 1]
        assert shorts_ab.plan_variants(spacex, 2)[1] == \
            shorts_ab.VARIANT_GROK_VIDEO

    def test_unenrolled_shows_are_byte_for_byte_unchanged(self):
        for slug in ("tesla", "fascinating_frontiers", "modern_investing"):
            cfg = load_config(ROOT / "shows" / f"{slug}.yaml")
            assert shorts_ab.is_enabled(cfg) is False
            assert shorts_ab.plan_variants(cfg, 2) == \
                [shorts_ab.VARIANT_STILLS] * 2

    def test_no_show_is_enrolled(self):
        """The experiment ended 2026-08-01 (operator verdict: real
        footage over generated motion). If it ever restarts: one show at
        a time — two enrolled shows would double the spend and still not
        answer the question faster; the comparison is within-show."""
        from engine.config import discover_show_slugs

        enrolled = [
            slug for slug in discover_show_slugs()
            if shorts_ab.is_enabled(load_config(ROOT / "shows" / f"{slug}.yaml"))
        ]
        assert enrolled == []


# ---------------------------------------------------------------------------
# Building the treatment — every failure path lands on stills
# ---------------------------------------------------------------------------

class TestBuildVariantFallsBackHonestly:
    def test_control_never_calls_the_clip_generator(self, spacex, tmp_path,
                                                    monkeypatch):
        def _boom(**_kwargs):
            raise AssertionError("the control arm must not generate clips")

        monkeypatch.setattr("engine.grok_video_clips.generate_short_clips",
                            _boom)
        result = shorts_ab.build_variant(
            spacex, index=0, intended=shorts_ab.VARIANT_STILLS,
            work_dir=tmp_path, episode_num=1)
        assert result.variant == shorts_ab.VARIANT_STILLS
        assert result.is_fallback is False

    def test_cost_ceiling_blocks_before_any_api_call(self, spacex, tmp_path,
                                                     monkeypatch):
        # The retired June 2026 pilot's failure was cost. The ceiling has
        # to bite BEFORE money is spent, not after.
        def _boom(**_kwargs):
            raise AssertionError("must not request clips over the ceiling")

        monkeypatch.setattr("engine.grok_video_clips.generate_short_clips",
                            _boom)
        result = shorts_ab.build_variant(
            spacex, index=1, intended=shorts_ab.VARIANT_GROK_VIDEO,
            work_dir=tmp_path, episode_num=1,
            spent_usd=spacex.youtube.shorts_ab_max_cost_usd)
        assert result.variant == shorts_ab.VARIANT_STILLS
        assert "cost ceiling" in result.fallback_reason

    def test_too_few_clips_ships_stills_and_says_so(self, spacex, tmp_path,
                                                    monkeypatch):
        clip = tmp_path / "clip_0.mp4"
        clip.write_bytes(b"x" * 64)

        class _Set:
            paths = [clip]
            total_cost_usd = 0.35

        monkeypatch.setattr("engine.grok_video_clips.generate_short_clips",
                            lambda **_k: _Set())
        result = shorts_ab.build_variant(
            spacex, index=1, intended=shorts_ab.VARIANT_GROK_VIDEO,
            work_dir=tmp_path, episode_num=1)
        # A one-clip loop is not the treatment being tested; recording it
        # as one would put a control episode in the treatment arm.
        assert result.variant == shorts_ab.VARIANT_STILLS
        assert result.intended == shorts_ab.VARIANT_GROK_VIDEO
        assert result.is_fallback
        assert "usable" in result.fallback_reason

    def test_a_raising_generator_never_breaks_the_publish(self, spacex,
                                                          tmp_path, monkeypatch):
        monkeypatch.setattr(
            "engine.grok_video_clips.generate_short_clips",
            lambda **_k: (_ for _ in ()).throw(RuntimeError("xAI 500")))
        result = shorts_ab.build_variant(
            spacex, index=1, intended=shorts_ab.VARIANT_GROK_VIDEO,
            work_dir=tmp_path, episode_num=1)
        assert result.variant == shorts_ab.VARIANT_STILLS
        assert "raised" in result.fallback_reason

    def test_enough_clips_ships_the_treatment(self, spacex, tmp_path,
                                              monkeypatch):
        clips = []
        for i in range(3):
            p = tmp_path / f"clip_{i}.mp4"
            p.write_bytes(b"x" * 64)
            clips.append(p)

        class _Set:
            paths = clips
            total_cost_usd = 1.05

        monkeypatch.setattr("engine.grok_video_clips.generate_short_clips",
                            lambda **_k: _Set())
        result = shorts_ab.build_variant(
            spacex, index=1, intended=shorts_ab.VARIANT_GROK_VIDEO,
            work_dir=tmp_path, episode_num=1)
        assert result.variant == shorts_ab.VARIANT_GROK_VIDEO
        assert len(result.clip_paths) == 3
        assert result.cost_usd == pytest.approx(1.05)

    def test_clip_subjects_are_scenes_not_headlines(self, spacex):
        """A video model needs something depictable.

        The first cut fed the episode's extracted headlines to the clip
        prompt, and the operator's verdict on the resulting Short was
        "pretty bad video content and pretty nonsensical" — a $8bn
        spectrum acquisition has no physical form to render. The show's
        curated ``image_queries`` are concrete scenes and are what the
        still pipeline already uses.
        """
        from engine.shorts_ab import _clip_contexts

        headline = "Rocket Lab's purchase of Aridium for $8 billion"
        got = _clip_contexts(spacex, "an episode hook", [headline], 3)
        assert got, "no clip subjects produced"
        assert headline not in got, "raw news headlines are back in the prompt"
        assert set(got) <= set(spacex.youtube.image_queries)

    def test_clip_subjects_fall_back_when_a_show_curates_none(self, spacex):
        from engine.shorts_ab import _clip_contexts

        spacex.youtube.image_queries = []
        got = _clip_contexts(spacex, "the hook", ["a scene prompt"], 2)
        assert got == ["a scene prompt", "a scene prompt"]
        spacex.youtube.image_queries = []
        assert _clip_contexts(spacex, "the hook", [], 1) == ["the hook"]

    def test_clips_are_requested_vertical(self, spacex, tmp_path, monkeypatch):
        seen = {}

        def _capture(**kwargs):
            seen.update(kwargs)

            class _Set:
                paths = []
                total_cost_usd = 0.0
            return _Set()

        monkeypatch.setattr("engine.grok_video_clips.generate_short_clips",
                            _capture)
        shorts_ab.build_variant(
            spacex, index=1, intended=shorts_ab.VARIANT_GROK_VIDEO,
            work_dir=tmp_path, episode_num=1)
        # A 16:9 clip letterboxed into a Short would measure the crop,
        # not the motion.
        assert seen["aspect"] == "9:16"


# ---------------------------------------------------------------------------
# The render
# ---------------------------------------------------------------------------

class TestHybridShortBackground:
    def _paths(self, tmp_path, n, prefix):
        out = []
        for i in range(n):
            p = tmp_path / f"{prefix}{i}.bin"
            p.write_bytes(b"x")
            out.append(p)
        return out

    @pytest.fixture(autouse=True)
    def _stub_probe(self, monkeypatch):
        monkeypatch.setattr("engine.video._probe_video_duration",
                            lambda _p, fallback: 5.0)

    def test_segments_sum_to_the_clip_length_exactly(self, tmp_path):
        from engine.video import _build_short_hybrid_sequence

        seq = _build_short_hybrid_sequence(
            self._paths(tmp_path, 4, "still"),
            self._paths(tmp_path, 3, "clip"),
            duration=35.0)
        # A background that is short by even a few frames leaves black at
        # the end of the Short.
        assert sum(d for _p, _v, d in seq) == pytest.approx(35.0, abs=1e-6)

    def test_it_opens_on_motion(self, tmp_path):
        from engine.video import _build_short_hybrid_sequence

        seq = _build_short_hybrid_sequence(
            self._paths(tmp_path, 4, "still"),
            self._paths(tmp_path, 3, "clip"),
            duration=35.0)
        assert seq[0][1] is True, "the first second decides whether a Short is watched"

    def test_clips_and_stills_alternate(self, tmp_path):
        from engine.video import _build_short_hybrid_sequence

        seq = _build_short_hybrid_sequence(
            self._paths(tmp_path, 4, "still"),
            self._paths(tmp_path, 3, "clip"),
            duration=35.0)
        kinds = [is_video for _p, is_video, _d in seq]
        assert kinds == [True, False, True, False, True, False]

    def test_more_clips_than_fit_are_trimmed_not_overrun(self, tmp_path):
        from engine.video import _build_short_hybrid_sequence

        seq = _build_short_hybrid_sequence(
            self._paths(tmp_path, 2, "still"),
            self._paths(tmp_path, 12, "clip"),
            duration=20.0)
        assert sum(d for _p, _v, d in seq) == pytest.approx(20.0, abs=1e-6)
        assert all(d > 0 for _p, _v, d in seq)

    def test_no_stills_still_produces_a_full_length_background(self, tmp_path):
        from engine.video import _build_short_hybrid_sequence

        seq = _build_short_hybrid_sequence(
            [], self._paths(tmp_path, 2, "clip"), duration=35.0)
        assert sum(d for _p, _v, d in seq) == pytest.approx(35.0, abs=1e-6)

    def test_no_clips_raises_so_the_caller_falls_back_to_stills(self, tmp_path):
        from engine.video import _build_short_hybrid_sequence

        with pytest.raises(ValueError):
            _build_short_hybrid_sequence(
                self._paths(tmp_path, 2, "still"), [], duration=35.0)


class TestBuildShortVideoSignature:
    def test_clip_paths_defaults_to_none_so_legacy_renders_are_unchanged(self):
        import inspect

        from engine.video import build_short_video

        params = inspect.signature(build_short_video).parameters
        assert params["clip_paths"].default is None


class TestHybridCommandShape:
    """Command-structure guards (the repo's convention for ffmpeg code —
    CI has no ffmpeg, so the command is asserted rather than run)."""

    def test_vertical_geometry_and_per_segment_trims(self, tmp_path):
        from engine.video import _hybrid_slideshow_cmd

        clip = tmp_path / "c.mp4"
        clip.write_bytes(b"x")
        still = tmp_path / "s.jpg"
        still.write_bytes(b"x")
        cmd = _hybrid_slideshow_cmd(
            [(clip, True, 5.0), (still, False, 6.5)],
            tmp_path / "out.mp4", width=1080, height=1920, fps=30)
        graph = cmd[cmd.index("-filter_complex") + 1]
        # Shorts geometry, not the long-form default.
        assert "scale=1080:1920" in graph
        assert "concat=n=2" in graph
        # Each segment is trimmed to its planned duration, which is what
        # makes the background sum to the clip length exactly.
        assert "trim=duration=5.00" in graph
        assert "trim=duration=6.50" in graph
        # The video segment plays its own frames; the still gets Ken Burns.
        assert "zoompan" in graph

    def test_a_video_input_is_not_looped_like_a_still(self, tmp_path):
        from engine.video import _hybrid_slideshow_cmd

        clip = tmp_path / "c.mp4"
        clip.write_bytes(b"x")
        cmd = _hybrid_slideshow_cmd([(clip, True, 5.0)],
                                    tmp_path / "out.mp4",
                                    width=1080, height=1920)
        assert "-loop" not in cmd


# ---------------------------------------------------------------------------
# Recording the arm
# ---------------------------------------------------------------------------

class TestVideoIndexCarriesTheVariant:
    def test_variant_is_written_when_set(self, tmp_path):
        from engine.youtube_index import record_video

        path = tmp_path / "youtube_videos.json"
        record_video(video_id="abc", show_slug="spacex", episode=45,
                     kind="short", variant="grok_video", index_path=path)
        row = json.loads(path.read_text())["videos"][0]
        assert row["variant"] == "grok_video"

    def test_the_key_is_absent_for_unenrolled_shows(self, tmp_path):
        from engine.youtube_index import record_video

        path = tmp_path / "youtube_videos.json"
        record_video(video_id="abc", show_slug="tesla", episode=45,
                     kind="short", index_path=path)
        # Every historical row and every non-enrolled show keeps its
        # exact existing shape.
        assert "variant" not in json.loads(path.read_text())["videos"][0]


# ---------------------------------------------------------------------------
# The report
# ---------------------------------------------------------------------------

class TestReport:
    def _write_stats(self, tmp_path, videos, extra_shows=None):
        api = tmp_path / "api"
        api.mkdir(parents=True, exist_ok=True)
        shows = {"spacex": {"videos": videos}}
        shows.update(extra_shows or {})
        (api / "youtube_stats.json").write_text(json.dumps({"shows": shows}))
        # Enrollment registry: only spacex runs the experiment. Without
        # this the report cannot tell participants from bystanders — the
        # 2026-07-30/31 window stamped variant="stills" on every network
        # Short, and an unfiltered report drew its control arm from the
        # whole network.
        shows_dir = tmp_path / "shows"
        shows_dir.mkdir(parents=True, exist_ok=True)
        (shows_dir / "spacex.yaml").write_text(
            "slug: spacex\nyoutube:\n  shorts_ab_enabled: true\n")
        return api

    def _build(self, tmp_path, videos, extra_shows=None):
        import importlib

        api = self._write_stats(tmp_path, videos, extra_shows=extra_shows)
        module = importlib.import_module("scripts.build_shorts_ab_report")
        original = module._ROOT
        module._ROOT = tmp_path
        try:
            return module.build()
        finally:
            module._ROOT = original

    @staticmethod
    def _video(variant, views=100, retention=40.0, subs=0):
        return {"show_slug": "spacex", "kind": "short", "variant": variant,
                "views": views, "average_view_percentage": retention,
                "subscribers_gained": subs}

    def test_no_comparison_before_both_arms_are_full(self, tmp_path):
        from scripts.build_shorts_ab_report import MIN_PER_ARM

        data = self._build(tmp_path, [
            *[self._video("grok_video") for _ in range(MIN_PER_ARM)],
            *[self._video("stills") for _ in range(MIN_PER_ARM - 1)],
        ])
        assert data["status"] == "collecting"
        assert data["comparisons"] == {}

    def test_videos_without_a_variant_are_excluded(self, tmp_path):
        data = self._build(tmp_path, [
            {"show_slug": "spacex", "kind": "short", "views": 900},
            self._video("stills"),
        ])
        # A Short published before the experiment was never eligible for
        # the treatment; counting it as control would bias the control
        # arm with a different production era.
        assert data["arms"]["stills"]["n"] == 1
        assert data["arms"]["grok_video"]["n"] == 0

    def test_non_participating_shows_never_enter_the_control_arm(
            self, tmp_path):
        """Between 2026-07-30 and 07-31 run_show recorded variant="stills"
        on every network Short (plan_variants doubles as the render plan
        and its output was recorded verbatim). Those rows must not become
        control data: a control arm drawn from other shows/channels
        measures the network, not the motion."""
        tesla_short = {"show_slug": "tesla", "kind": "short",
                       "variant": "stills", "views": 5000,
                       "average_view_percentage": 55.0,
                       "subscribers_gained": 3}
        data = self._build(
            tmp_path,
            [self._video("stills"), self._video("grok_video")],
            extra_shows={"tesla": {"videos": [tesla_short, tesla_short]}},
        )
        assert data["arms"]["stills"]["n"] == 1
        assert data["arms"]["grok_video"]["n"] == 1

    def test_overlapping_arms_report_no_measurable_difference(self, tmp_path):
        from scripts.build_shorts_ab_report import MIN_PER_ARM

        videos = []
        for i in range(MIN_PER_ARM + 6):
            videos.append(self._video("grok_video", retention=40 + (i % 7)))
            videos.append(self._video("stills", retention=39 + (i % 7)))
        data = self._build(tmp_path, videos)
        assert data["status"] == "ready"
        verdict = data["comparisons"]["average_view_percentage"]["verdict"]
        assert verdict == "no_measurable_difference"

    def test_a_large_consistent_effect_is_called(self, tmp_path):
        from scripts.build_shorts_ab_report import MIN_PER_ARM

        videos = []
        for i in range(MIN_PER_ARM + 6):
            videos.append(self._video("grok_video", retention=70 + (i % 3)))
            videos.append(self._video("stills", retention=40 + (i % 3)))
        data = self._build(tmp_path, videos)
        assert data["comparisons"]["average_view_percentage"]["verdict"] == \
            "treatment_better"

    def test_the_confidence_interval_brackets_the_difference(self, tmp_path):
        from scripts.build_shorts_ab_report import welch_difference

        result = welch_difference([50, 55, 60, 45, 52], [40, 44, 38, 41, 43])
        lo, hi = result["ci95"]
        assert lo <= result["difference"] <= hi

    def test_empty_input_is_a_clean_not_started(self, tmp_path):
        data = self._build(tmp_path, [])
        assert data["status"] == "not_started"
        assert data["arms"]["grok_video"]["n"] == 0


class TestWindowParityDeconfound:
    """July 31 2026: treatment was pinned to Short index 1 = always the
    SECOND-best smart window, so the experiment measured motion + weaker
    window combined. run_show now alternates the top-two window
    assignment by episode parity for enrolled shows — each arm sees
    ~equal window quality over time, deterministically."""

    def test_run_show_swaps_windows_on_odd_episodes_for_enrolled_shows(self):
        src = (ROOT / "run_show.py").read_text(encoding="utf-8")
        assert "episode_num % 2 == 1" in src
        assert "shorts_ab_windows_swapped" in src
        # The swap is gated on enrollment — non-enrolled shows must keep
        # their plan order untouched.
        swap_block = src.split("Window-parity de-confound")[1][:800]
        assert "_shorts_ab.is_enabled(config)" in swap_block
