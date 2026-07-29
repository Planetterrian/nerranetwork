"""Drift guards for the single-pass long-form render (P1-2, July 28 2026).

The two-stage path renders the Ken Burns slideshow to an intermediate
MP4, then feeds that file back in as ``[0:v]`` of the composite — a full
extra encode AND decode of a 1080p file that exists only to be consumed
seconds later, plus a second lossy generation on every delivered pixel.

Fusing them shifts every ffmpeg input index: two-stage numbering is fixed
at bg(0)/audio(1)/brand(2)/pill(3), but with the scene stills as inputs
the extras move to ``n``, ``n+1``, ``n+2``. Getting that wrong is
**silent** — ffmpeg will happily overlay the wrong stream — so most of
these tests are about index arithmetic.

Measured on a real 24 s / 4-scene render in this repo (intermediates
cleared between runs, since ``_render_slideshow`` is idempotent and a
warm intermediate makes the two-stage path look artificially fast):

    two-stage    31.3 s, 32.2 s
    single-pass  22.2 s, 22.2 s        (~30% faster)

    ffprobe resolution / fps / codec / pix_fmt / audio / duration:
        identical
    PSNR single vs two-stage: 54.4 dB average, 37.7 dB min
    overlay regions: RMS 0.06 (brand) and 0.00 (URL pill)

The path ships **opt-in** because none of that was measured against a
real episode with real imagery, captions and chapter metadata yet.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import engine.video as video  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parent.parent
SCENES = [Path(f"/tmp/scene{i}.png") for i in range(4)]


class TestDefaultIsOnWithAnEscapeHatch:
    """Default flipped ON (July 29 2026) after an A/B on both production
    render shapes — uniform stills and chapter-schedule-plus-captions —
    which came out equivalent (same duration/frames/geometry, mean pixel
    diff < 0.3/255, identical scene timeline) and 23-34% faster.

    The env var is now an escape hatch rather than an opt-in, so the
    values that must keep working are the DISABLING ones. The two-stage
    fallback on ffmpeg failure is pinned separately below — that is what
    makes the flip safe in the first place."""

    def test_enabled_without_the_env_var(self, monkeypatch):
        monkeypatch.delenv("NERRA_SINGLE_PASS_RENDER", raising=False)
        assert video._single_pass_enabled() is True

    @pytest.mark.parametrize("value", ["", "1", "true", "TRUE", "yes", "on"])
    def test_absent_or_affirmative_values_stay_enabled(self, monkeypatch, value):
        monkeypatch.setenv("NERRA_SINGLE_PASS_RENDER", value)
        assert video._single_pass_enabled() is True

    @pytest.mark.parametrize("value", ["0", "false", "FALSE", "off", "no"])
    def test_escape_hatch_forces_the_legacy_path(self, monkeypatch, value):
        monkeypatch.setenv("NERRA_SINGLE_PASS_RENDER", value)
        assert video._single_pass_enabled() is False

    def test_dub_workflow_carries_the_escape_hatch(self):
        """The dubs render long-form too. Before this, one switch could
        not turn the fused path off everywhere."""
        wf = (REPO_ROOT / ".github" / "workflows"
              / "multilingual.yml").read_text(encoding="utf-8")
        wired = [ln for ln in wf.splitlines()
                 if ln.strip().startswith("NERRA_SINGLE_PASS_RENDER:")]
        assert len(wired) == 2, (
            "both the RU and FR dub publish steps must carry the hatch; "
            f"found {len(wired)}"
        )


class TestInputIndexArithmetic:
    """The silent failure mode: overlaying the wrong stream."""

    @pytest.mark.parametrize("n", [1, 2, 4, 9, 30])
    def test_brand_and_pill_indices_follow_scene_count(self, n):
        graph = video._single_pass_long_form_filter_graph(
            n, with_url_pill=True)
        assert f"[{n + 1}:v]format=rgba[brand]" in graph
        assert f"[{n + 2}:v]format=rgba[urlpill]" in graph

    @pytest.mark.parametrize("n", [1, 2, 4, 9])
    def test_no_index_collides_with_a_scene(self, n):
        """A scene index reused for an overlay would silently corrupt it."""
        graph = video._single_pass_long_form_filter_graph(
            n, with_url_pill=True)
        overlay_indices = {
            int(m) for m in re.findall(r"\[(\d+):v\]format=rgba", graph)
        }
        assert overlay_indices.isdisjoint(range(n))

    def test_audio_is_mapped_from_the_scene_count_index(self):
        cmd = video._single_pass_long_form_cmd(
            SCENES, "a.m4a", "brand.png", "out.mp4")
        assert "-map" in cmd
        assert f"{len(SCENES)}:a" in cmd

    def test_metadata_index_accounts_for_the_pill(self):
        n = len(SCENES)
        without = video._single_pass_long_form_cmd(
            SCENES, "a.m4a", "brand.png", "out.mp4", chapter_metadata_in="m.txt")
        assert without[without.index("-map_metadata") + 1] == str(n + 2)

        with_pill = video._single_pass_long_form_cmd(
            SCENES, "a.m4a", "brand.png", "out.mp4",
            url_pill_in="url.png", chapter_metadata_in="m.txt")
        assert with_pill[with_pill.index("-map_metadata") + 1] == str(n + 3)

    def test_input_order_matches_the_graph(self):
        """Inputs must appear scenes → audio → brand → pill."""
        cmd = video._single_pass_long_form_cmd(
            SCENES, "audio.m4a", "brand.png", "out.mp4", url_pill_in="url.png")
        inputs = [cmd[i + 1] for i, tok in enumerate(cmd) if tok == "-i"]
        assert inputs[:len(SCENES)] == [str(p) for p in SCENES]
        assert inputs[len(SCENES):] == ["audio.m4a", "brand.png", "url.png"]


class TestGraphShape:
    def test_slideshow_half_is_reused_verbatim(self):
        """Forking the xfade offset arithmetic would be a latent bug."""
        slideshow = video._slideshow_filter_graph(4)
        fused = video._single_pass_long_form_filter_graph(4)
        assert fused.startswith(slideshow[: -len("[v]")])

    def test_slideshow_output_is_relabelled_to_bg(self):
        fused = video._single_pass_long_form_filter_graph(4)
        assert "[bg]" in fused
        assert fused.endswith("[v]")

    def test_terminates_in_v_for_every_branch(self):
        for kwargs in ({}, {"with_url_pill": True},
                       {"subtitles_path": "/tmp/x.ass"},
                       {"with_url_pill": True, "subtitles_path": "/tmp/x.ass"}):
            assert video._single_pass_long_form_filter_graph(
                4, **kwargs).endswith("[v]")

    def test_subtitles_applied_after_overlays(self):
        """Captions must sit on top of the pills, as in the two-stage graph."""
        graph = video._single_pass_long_form_filter_graph(
            4, with_url_pill=True, subtitles_path="/tmp/x.ass")
        assert graph.index("[stamped]subtitles=") > graph.index("[urlpill]")

    def test_per_scene_durations_are_honoured(self):
        graph = video._single_pass_long_form_filter_graph(
            3, scene_durations=[5.0, 9.0, 4.0])
        # xfade offsets are cumulative visible time: 5.0, then 14.0.
        assert "offset=5.00" in graph
        assert "offset=14.00" in graph

    def test_mismatched_durations_raise(self):
        with pytest.raises(ValueError):
            video._single_pass_long_form_filter_graph(
                3, scene_durations=[5.0, 9.0])

    def test_uses_the_delivery_encode_profile(self):
        """It produces the delivered file, not an intermediate."""
        cmd = video._single_pass_long_form_cmd(
            SCENES, "a.m4a", "brand.png", "out.mp4")
        assert "-crf" in cmd
        assert cmd[cmd.index("-crf") + 1] == "22"
        assert "+faststart" in cmd


class TestScenePlanIsShared:
    """Both renderers must compute the same plan from one implementation."""

    def test_uniform_plan_cycles_long_episodes(self):
        """Reusing images in rotation restores motion at zero image cost."""
        scenes = [Path(f"s{i}.png") for i in range(4)]
        planned, hold = video._uniform_slideshow_plan(scenes, 600.0)
        assert len(planned) > len(scenes)
        # 4 scenes over 600 s would be 150 s/image (Ep505's static-render
        # bug); cycling cuts that hard. The 24-slot input cap deliberately
        # wins over the 15 s target on long episodes, so this asserts the
        # improvement, not the target.
        assert hold < 600.0 / len(scenes)

    def test_uniform_plan_respects_the_input_cap(self):
        from engine.scene_scheduler import _MAX_SLIDESHOW_SLOTS
        scenes = [Path(f"s{i}.png") for i in range(4)]
        planned, _ = video._uniform_slideshow_plan(scenes, 100000.0)
        assert len(planned) <= _MAX_SLIDESHOW_SLOTS

    def test_zero_duration_falls_back_to_the_legacy_hold(self):
        scenes = [Path("s0.png")]
        planned, hold = video._uniform_slideshow_plan(scenes, 0.0)
        assert planned == scenes
        assert hold == video._SCENE_DURATION_SECONDS

    def test_schedule_supplies_its_own_durations(self):
        schedule = [(Path("a.png"), 7.0), (Path("b.png"), 11.0)]
        scenes, durations, _ = video._single_pass_scene_plan(schedule, None, 100.0)
        assert scenes == [Path("a.png"), Path("b.png")]
        assert durations == [7.0, 11.0]

    def test_no_schedule_yields_uniform_and_no_per_scene_list(self):
        scenes_in = [Path(f"s{i}.png") for i in range(3)]
        scenes, durations, hold = video._single_pass_scene_plan(
            None, scenes_in, 30.0)
        assert durations is None       # reproduces the legacy graph exactly
        assert hold > 0
        assert scenes == scenes_in

    def test_no_scenes_is_empty(self):
        assert video._single_pass_scene_plan(None, [], 30.0)[0] == []

    def test_two_stage_uses_the_shared_planner(self):
        """Guards against the two paths drifting apart."""
        source = (REPO_ROOT / "engine" / "video.py").read_text(encoding="utf-8")
        assert source.count("def _uniform_slideshow_plan") == 1
        # def + the two-stage call site + the single-pass call site.
        assert source.count("_uniform_slideshow_plan(") >= 3
        # And the two-stage branch must no longer inline its own copy of
        # the cycling arithmetic.
        two_stage = source.split("slideshow_scenes, scene_duration_s =")[1][:600]
        assert "i % len(" not in two_stage


class TestFallbackIsPreserved:
    def test_hybrid_broll_path_is_untouched(self):
        """The clips path already produces a video background."""
        source = (REPO_ROOT / "engine" / "video.py").read_text(encoding="utf-8")
        # The single-pass branch must sit AFTER the hybrid early-return.
        assert source.index("_render_hybrid_slideshow(visuals") < source.index(
            "if _single_pass_enabled():")

    def test_failure_falls_back_to_two_stage(self):
        source = (REPO_ROOT / "engine" / "video.py").read_text(encoding="utf-8")
        block = source.split("if _single_pass_enabled():")[1][:2200]
        assert "except (subprocess.CalledProcessError, RuntimeError)" in block
        assert "falling back to" in block
        # It must NOT return on failure — control has to reach the old path.
        assert block.index("falling back to") > block.index("_run_ffmpeg(")

    def test_two_stage_command_builder_still_exists(self):
        assert callable(video._long_form_cmd)
        assert callable(video._render_slideshow)
