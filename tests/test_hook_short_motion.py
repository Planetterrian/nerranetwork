"""Hook-Short motion retry (Sep 22 2026) — engine/hook_short_motion.py.

One ~4 s Grok video clip opens the HOOK Short on the three flagships.
The contract, like the Shorts A/B it learns from: the cost gate bites
BEFORE any request, a shortfall ships stills and RECORDS stills (its own
label, never the A/B's), and disabled never imports the generator.
"""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from engine import hook_short_motion as hm  # noqa: E402
from engine import shorts_ab  # noqa: E402
from engine.config import YouTubeConfig, load_config  # noqa: E402


@pytest.fixture()
def tesla():
    return load_config(ROOT / "shows" / "tesla.yaml")


@pytest.fixture()
def off():
    return load_config(ROOT / "shows" / "omni_view.yaml")


class _ClipSet:
    def __init__(self, paths=(), cost=0.0, failures=()):
        self.paths = list(paths)
        self.total_cost_usd = cost
        self.failures = list(failures)


class TestGates:
    def test_disabled_never_imports_the_generator(self, off, tmp_path, monkeypatch):
        def _boom(**_k):
            raise AssertionError("disabled must not request clips")
        monkeypatch.setattr("engine.grok_video_clips.generate_short_clips", _boom)
        r = hm.plan_hook_motion(off, work_dir=tmp_path, episode_num=1,
                                scene_brief="a car", hook="h")
        assert r.variant == hm.VARIANT_HOOK_STILLS
        assert r.clip_path is None and r.requested is False
        assert r.fallback_reason == "disabled"

    def test_cost_ceiling_blocks_before_any_api_call(self, tesla, tmp_path, monkeypatch):
        def _boom(**_k):
            raise AssertionError("must not request clips over the ceiling")
        monkeypatch.setattr("engine.grok_video_clips.generate_short_clips", _boom)
        r = hm.plan_hook_motion(
            tesla, work_dir=tmp_path, episode_num=1, scene_brief="a car",
            hook="h", spent_usd=tesla.youtube.hook_short_motion_max_cost_usd)
        assert r.variant == hm.VARIANT_HOOK_STILLS
        assert "cost ceiling" in r.fallback_reason
        assert r.requested is False

    def test_default_cost_passes_the_ceiling(self):
        from engine.grok_video import VIDEO_COST_USD
        cfg = YouTubeConfig()
        assert (VIDEO_COST_USD["720p"] * cfg.hook_short_motion_seconds
                <= cfg.hook_short_motion_max_cost_usd)
        assert VIDEO_COST_USD["720p"] * 4 == pytest.approx(0.28)

    def test_pipeline_budget_floor(self, tesla, tmp_path, monkeypatch):
        def _boom(**_k):
            raise AssertionError("must not request clips with no pipeline time")
        monkeypatch.setattr("engine.grok_video_clips.generate_short_clips", _boom)
        r = hm.plan_hook_motion(tesla, work_dir=tmp_path, episode_num=1,
                                scene_brief="a car", hook="h",
                                pipeline_budget_left_s=299.0)
        assert r.variant == hm.VARIANT_HOOK_STILLS
        assert "floor" in r.fallback_reason

    def test_nothing_to_film_is_stills(self, tesla, tmp_path, monkeypatch):
        monkeypatch.setattr("engine.grok_video_clips.generate_short_clips",
                            lambda **_k: (_ for _ in ()).throw(AssertionError()))
        r = hm.plan_hook_motion(tesla, work_dir=tmp_path, episode_num=1)
        assert r.variant == hm.VARIANT_HOOK_STILLS


class TestOutcomes:
    def test_generator_failure_records_stills_with_the_reason(self, tesla, tmp_path, monkeypatch):
        monkeypatch.setattr("engine.grok_video_clips.generate_short_clips",
                            lambda **_k: _ClipSet(failures=["submit clip 0: 503"]))
        r = hm.plan_hook_motion(tesla, work_dir=tmp_path, episode_num=1,
                                scene_brief="a car", hook="h",
                                pipeline_budget_left_s=1000.0)
        assert r.variant == hm.VARIANT_HOOK_STILLS
        assert r.clip_path is None and r.requested is True
        assert "503" in r.fallback_reason

    def test_a_raising_generator_never_breaks_the_publish(self, tesla, tmp_path, monkeypatch):
        def _raise(**_k):
            raise RuntimeError("boom")
        monkeypatch.setattr("engine.grok_video_clips.generate_short_clips", _raise)
        r = hm.plan_hook_motion(tesla, work_dir=tmp_path, episode_num=1,
                                scene_brief="a car", hook="h")
        assert r.variant == hm.VARIANT_HOOK_STILLS and "raised" in r.fallback_reason

    def test_success_ships_motion_open_with_cost(self, tesla, tmp_path, monkeypatch):
        clip = tmp_path / "hook_motion" / "clip_0.mp4"
        clip.parent.mkdir()
        clip.write_bytes(b"x" * 64)
        seen = {}

        def _gen(**k):
            seen.update(k)
            return _ClipSet([clip], cost=0.28)
        monkeypatch.setattr("engine.grok_video_clips.generate_short_clips", _gen)
        r = hm.plan_hook_motion(tesla, work_dir=tmp_path, episode_num=7,
                                scene_brief="A red Cybertruck at dawn on a desert road.",
                                hook="h", pipeline_budget_left_s=1000.0)
        assert r.variant == hm.VARIANT_MOTION_OPEN
        assert r.clip_path == clip and r.cost_usd == pytest.approx(0.28)
        assert r.seconds == 4
        # One vertical 720p clip under its own budget, in its own dir.
        assert seen["count"] == 1 and seen["aspect"] == "9:16"
        assert seen["resolution"] == "720p" and seen["seconds"] == 4
        assert seen["budget_s"] == pytest.approx(150.0)
        assert seen["work_dir"] == tmp_path / "hook_motion"
        assert seen["prompt_override"].startswith("A red Cybertruck at dawn")
        assert "gentle camera motion" in seen["prompt_override"]
        assert "no text" in seen["prompt_override"]
        assert r.as_metric() == {
            "hook_short_motion": "motion_open",
            "hook_short_motion_cost_usd": 0.28,
            "hook_short_motion_reason": "",
        }

    def test_an_empty_clip_file_is_a_shortfall(self, tesla, tmp_path, monkeypatch):
        clip = tmp_path / "clip_0.mp4"
        clip.write_bytes(b"")
        monkeypatch.setattr("engine.grok_video_clips.generate_short_clips",
                            lambda **_k: _ClipSet([clip], cost=0.28))
        r = hm.plan_hook_motion(tesla, work_dir=tmp_path, episode_num=1,
                                scene_brief="a car", hook="h")
        assert r.variant == hm.VARIANT_HOOK_STILLS and r.cost_usd == pytest.approx(0.28)

    def test_labels_never_collide_with_the_ab(self):
        assert hm.VARIANT_HOOK_STILLS != shorts_ab.VARIANT_STILLS
        assert hm.VARIANT_MOTION_OPEN != shorts_ab.VARIANT_GROK_VIDEO
        assert not (set(hm.VARIANTS) & set(shorts_ab.VARIANTS))

    def test_prompt_override_reaches_the_request(self, monkeypatch, tmp_path):
        from engine import grok_video_clips as gvc
        monkeypatch.setattr(gvc, "_api_key", lambda: "k")
        seen = {}

        def _req(prompt, **k):
            seen["prompt"] = prompt
            raise RuntimeError("stop here")
        monkeypatch.setattr("engine.grok_video._request_one_video", _req)
        gvc.generate_short_clips(work_dir=tmp_path, episode_num=1, count=1,
                                 prompt_override="my exact prompt")
        assert seen["prompt"] == "my exact prompt"


class TestSingleClipHybrid:
    @pytest.fixture(autouse=True)
    def _stub_probe(self, monkeypatch):
        monkeypatch.setattr("engine.video._probe_video_duration",
                            lambda _p, fallback: 4.0)

    def _paths(self, tmp_path, n, prefix):
        out = []
        for i in range(n):
            p = tmp_path / f"{prefix}{i}.bin"
            p.write_bytes(b"x")
            out.append(p)
        return out

    def test_one_clip_opens_and_the_stills_keep_cycling(self, tmp_path):
        from engine.video import _build_short_hybrid_sequence
        seq = _build_short_hybrid_sequence(
            self._paths(tmp_path, 3, "still"), self._paths(tmp_path, 1, "clip"),
            duration=35.0, nominal_clip_seconds=4.0, max_still_hold_s=7.0)
        assert seq[0][1] is True and seq[0][2] == pytest.approx(4.0)
        stills = [s for s in seq[1:]]
        assert all(v is False for _p, v, _d in stills)
        assert len(stills) == 5                       # 31 s / 7 s → 5 holds
        assert all(d <= 7.0 + 1e-6 for _p, _v, d in stills)
        assert len({p for p, _v, _d in stills}) == 3   # cycles the pool
        assert sum(d for _p, _v, d in seq) == pytest.approx(35.0, abs=1e-6)

    def test_legacy_layout_is_unchanged_without_the_cap(self, tmp_path):
        from engine.video import _build_short_hybrid_sequence
        stills = self._paths(tmp_path, 3, "still")
        clips = self._paths(tmp_path, 3, "clip")
        a = _build_short_hybrid_sequence(stills, clips, duration=35.0)
        b = _build_short_hybrid_sequence(stills, clips, duration=35.0,
                                         max_still_hold_s=None)
        assert a == b
        one = _build_short_hybrid_sequence(stills, clips[:1], duration=35.0)
        assert len(one) == 2 and one[1][2] == pytest.approx(31.0)

    def test_build_short_video_min_clips_default_is_two(self):
        import inspect
        from engine.video import build_short_video
        sig = inspect.signature(build_short_video)
        assert sig.parameters["min_clips"].default == 2
        assert sig.parameters["still_max_hold_s"].default is None

    def test_one_clip_renders_the_hybrid_only_with_min_clips_one(self, tmp_path, monkeypatch):
        from engine import video
        calls = []
        monkeypatch.setattr(video, "_render_hybrid_slideshow",
                            lambda *a, **k: calls.append("hybrid"))
        monkeypatch.setattr(video, "_run_ffmpeg", lambda c, **k: None)
        audio = tmp_path / "a.mp3"; audio.write_bytes(b"x")
        cover = tmp_path / "c.jpg"; cover.write_bytes(b"x")
        clip = tmp_path / "clip.mp4"; clip.write_bytes(b"x")
        video.build_short_video(audio, cover, tmp_path / "s.mp4", duration=35.0,
                                clip_paths=[clip], clip_seconds=4.0)
        assert calls == []
        video.build_short_video(audio, cover, tmp_path / "s2.mp4", duration=35.0,
                                clip_paths=[clip], clip_seconds=4.0, min_clips=1,
                                still_max_hold_s=7.0)
        assert calls == ["hybrid"]


class TestRecords:
    def test_index_row_carries_the_arm(self, tmp_path):
        from engine.youtube_index import record_video
        p = tmp_path / "youtube_videos.json"
        record_video(video_id="v1", show_slug="tesla", episode=1, kind="short",
                     variant=hm.VARIANT_BROLL_OPEN, window="hook_open", index_path=p)
        rows = json.loads(p.read_text())["videos"]
        assert rows[0]["variant"] == "broll_open"

    def test_early_reach_rows_carry_the_arm(self):
        spec = importlib.util.spec_from_file_location(
            "ter_motion", ROOT / "scripts" / "track_early_reach.py")
        tr = importlib.util.module_from_spec(spec)
        sys.modules["ter_motion"] = tr
        spec.loader.exec_module(tr)
        reach = tr.load_reach(Path("/nonexistent/x.json"))
        snap = {"generated": "2026-09-25T19:00:00+00:00", "shows": {"x": {"videos": [
            {"video_id": "a", "published": "2026-09-22", "views": 40, "channel": "en",
             "kind": "short", "show_slug": "tesla", "window": "hook_open",
             "variant": "motion_open", "subscribers_gained": 0}]}}}
        assert tr.merge_snapshot(reach, snap) == 1
        assert reach["videos"]["a"]["variant"] == "motion_open"

    def test_metrics_on_the_allowlist(self):
        src = (ROOT / "engine" / "pipeline.py").read_text(encoding="utf-8")
        assert 'metrics.record("hook_short_motion"' in src
        assert 'metrics.record("hook_short_motion_cost_usd"' in src

    def test_dashboard_metric_is_computable_and_honest_null(self, tmp_path):
        import importlib
        gd = importlib.import_module("scripts.generate_dashboard")
        (tmp_path / "api").mkdir()
        rows = [{"video_id": f"v{i}", "kind": "short", "channel": "en",
                 "published": "2026-09-22", "show_slug": "tesla", "window": "hook_open",
                 "variant": "motion_open" if i % 2 else "hook_stills",
                 "views": 20, "average_view_percentage": 50.0}
                for i in range(12)]
        (tmp_path / "api" / "youtube_stats.json").write_text(json.dumps({
            "generated": "2026-09-23T14:00:00Z", "channels": {},
            "shows": {"tesla_shorts_time": {"videos": rows}}}))
        m = gd._experiment_live_metrics(tmp_path)
        assert m["hook_short_motion_share_14d"] == pytest.approx(0.5)
        assert m["short_avp_en_14d"] == pytest.approx(50.0)
        (tmp_path / "api" / "youtube_stats.json").write_text(json.dumps({
            "generated": "2026-09-23T14:00:00Z", "channels": {},
            "shows": {"tesla_shorts_time": {"videos": rows[:6]}}}))
        m = gd._experiment_live_metrics(tmp_path)
        assert m["hook_short_motion_share_14d"] is None
        assert m["short_avp_en_14d"] is None


class TestWiring:
    def test_run_show_gates_the_retry_to_the_en_hook_short_outside_the_ab(self):
        src = (ROOT / "run_show.py").read_text(encoding="utf-8")
        block = src[src.index("Hook-Short motion retry (Sep 22 2026)"):
                    src.index("_short_broll: list = []")]
        assert "short_idx == 0" in block and "not _ab_on" in block
        assert '_yt_channel == "en"' in block and '_fill_mode == "hook_open"' in block
        assert "_hook_motion_mod.is_enabled(config)" in block
        assert "pipeline_budget_left_s=_pipeline_budget_remaining()" in block
        # The pool is skipped when the clip landed; the clip wins the
        # clip_paths chain over the pool and loses to the A/B's.
        assert "and _hook_motion_clip is None" in src
        assert "min_clips=1 if _hook_motion_clip else 2" in src
        assert "_hook_motion_mod.STILL_MAX_HOLD_S" in src
        # A shortfall on a show with a pool records broll_open.
        assert "_hook_motion_mod.VARIANT_BROLL_OPEN if _short_broll" in src
        # The index carries the arm outside the A/B.
        assert "else (_hook_motion.variant" in src

    def test_knobs_default_off_and_arm_shows_on(self):
        cfg = YouTubeConfig()
        assert cfg.hook_short_motion is False
        defaults = yaml.safe_load((ROOT / "shows" / "_defaults.yaml").read_text(encoding="utf-8"))
        assert defaults["youtube"]["hook_short_motion"] is False
        for slug in ("tesla", "spacex", "fascinating_frontiers"):
            data = yaml.safe_load((ROOT / "shows" / f"{slug}.yaml").read_text(encoding="utf-8"))
            assert data["youtube"]["hook_short_motion"] is True, slug
        for slug in ("models_agents", "omni_view", "modern_investing"):
            data = yaml.safe_load((ROOT / "shows" / f"{slug}.yaml").read_text(encoding="utf-8"))
            assert "hook_short_motion" not in (data.get("youtube") or {}), slug

    def test_dub_paths_are_untouched(self):
        for mod in ("ru_dub", "lang_dub"):
            src = (ROOT / "engine" / f"{mod}.py").read_text(encoding="utf-8")
            assert "hook_short_motion" not in src
