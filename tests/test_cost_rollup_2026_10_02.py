"""Cost-measurement pass, 2026-10-02 — the four lines that never reached
``api/dashboard.json`` ``cost_rollup``.

The rollup reported ~$192/30d while four real lines were missing:

1. multilingual dub tracks (~$58/30d) — the sidecar credit file carries
   only ``services.multilingual.estimated_cost_usd`` and no file-level
   total, so ``aggregate_costs`` summed it as $0 AND counted it as an
   episode;
2. hook-Short motion clips (~$0.28/episode) — a METRIC, never a tracker
   line, so no credit file carried the spend;
3. the scene-brief and YouTube-title LLM calls — ``_call_grok`` returned a
   usage meta that both callers discarded;
4. the daily-audit reviewer — up to 16 Grok calls a day recorded nowhere.

Rule these guards pin (CLAUDE.md): a result key or a metric is not a cost
until a credit file carries it and the rollup reads it.
"""

from __future__ import annotations

import datetime as _dt
import importlib.util
import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from engine import tracking  # noqa: E402


def _load_dashboard_module():
    spec = importlib.util.spec_from_file_location(
        "gen_dash_cost_pass", REPO_ROOT / "scripts" / "generate_dashboard.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules["gen_dash_cost_pass"] = mod
    try:
        spec.loader.exec_module(mod)
    finally:
        sys.modules.pop("gen_dash_cost_pass", None)
    return mod


def _load_review_module():
    spec = importlib.util.spec_from_file_location(
        "review_episodes_cost_pass", REPO_ROOT / "review_episodes.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules["review_episodes_cost_pass"] = mod
    try:
        spec.loader.exec_module(mod)
    finally:
        sys.modules.pop("review_episodes_cost_pass", None)
    return mod


# ---------------------------------------------------------------------------
# D. aggregate_costs — the two new buckets, episode counting, _review dir
# ---------------------------------------------------------------------------

class TestAggregateCostsBuckets:

    def _write(self, ddir: Path, name: str, payload: dict) -> None:
        ddir.mkdir(parents=True, exist_ok=True)
        (ddir / name).write_text(json.dumps(payload), encoding="utf-8")

    @pytest.fixture
    def tree(self, tmp_path):
        today = _dt.date.today().isoformat()
        tesla = tmp_path / "digests" / "tesla_shorts_time"
        # An episode file with every per-episode service line, including
        # the new motion_api block, and a total that includes it.
        self._write(tesla, f"credit_usage_{today}_ep700.json", {
            "date": today,
            "services": {
                "grok_api": {"total_cost_usd": 0.20},
                "tts_api": {"estimated_cost_usd": 0.30},
                "image_api": {"estimated_cost_usd": 0.16},
                "search_api": {"estimated_cost_usd": 0.03},
                "motion_api": {"clips_generated": 1, "estimated_cost_usd": 0.28},
            },
            "total_estimated_cost_usd": 0.97,
        })
        # The multilingual sidecar, exactly as engine/multilingual.py
        # writes it: ONE service key, no file-level total.
        self._write(tesla, f"credit_usage_{today}_ep700_multilingual.json", {
            "date": today,
            "show": "Tesla Shorts Time",
            "episode_number": 700,
            "services": {
                "multilingual": {
                    "estimated_cost_usd": 0.42,
                    "languages": ["fr", "ru", "zh"],
                    "tracks": 3,
                    "tts_chars": 24986,
                },
            },
        })
        # The reviewer's file under the virtual slug.
        self._write(tmp_path / "digests" / "_review",
                    f"credit_usage_{today}_review.json", {
            "date": today,
            "show": "Episode Review",
            "episode_number": 0,
            "services": {
                "grok_api": {
                    "total_cost_usd": 0.05,
                    "episode_review": {"estimated_cost_usd": 0.05},
                },
                "tts_api": {"estimated_cost_usd": 0.0},
            },
            "review": {"runs": 1, "calls": 12},
            "total_estimated_cost_usd": 0.05,
        })
        return tmp_path

    def test_multilingual_and_motion_reach_total(self, tree):
        gd = _load_dashboard_module()
        out = gd.aggregate_costs(tree, [{"slug": "tesla", "name": "Tesla Shorts Time"}])
        net30 = out["network_last_30_days"]
        assert net30["multilingual"] == pytest.approx(0.42)
        assert net30["motion"] == pytest.approx(0.28)
        assert net30["review"] == pytest.approx(0.05)
        # 0.97 (episode, motion inside its total) + 0.42 (sidecar) + 0.05
        assert net30["total"] == pytest.approx(1.44)
        # The pre-existing buckets are untouched.
        assert net30["grok"] == pytest.approx(0.25)   # episode 0.20 + review 0.05
        assert net30["tts"] == pytest.approx(0.30)
        assert net30["images"] == pytest.approx(0.16)
        assert net30["search"] == pytest.approx(0.03)

    def test_sidecar_and_review_files_are_not_episodes(self, tree):
        gd = _load_dashboard_module()
        out = gd.aggregate_costs(tree, [{"slug": "tesla", "name": "Tesla Shorts Time"}])
        net7 = out["network_last_7_days"]
        assert net7["episodes"] == 1
        assert net7["files"] == 3
        tesla = out["per_show"]["tesla"]["last_7_days"]
        assert tesla["episodes"] == 1 and tesla["files"] == 2
        assert out["projections"]["episodes_7d"] == 1
        assert out["projections"]["files_7d"] == 3
        # avg is per EPISODE and carries the sidecar + reviewer spend.
        assert out["projections"]["avg_cost_per_episode_usd"] == pytest.approx(1.44)

    def test_review_dir_is_read_and_labelled(self, tree):
        gd = _load_dashboard_module()
        assert "_review" in gd._VIRTUAL_COST_SLUGS
        out = gd.aggregate_costs(tree, [{"slug": "tesla", "name": "Tesla Shorts Time"}])
        assert out["per_show"]["_review"]["label"] == "review"
        assert out["per_show"]["_review"]["last_30_days"]["review"] == pytest.approx(0.05)
        assert out["per_show"]["_review"]["last_30_days"]["episodes"] == 0

    def test_old_file_without_new_keys_is_unchanged(self, tmp_path):
        """A pre-pass credit file (no motion_api, no sidecar) sums as before."""
        gd = _load_dashboard_module()
        today = _dt.date.today().isoformat()
        ddir = tmp_path / "digests" / "spacex"
        self._write(ddir, f"credit_usage_{today}_ep100.json", {
            "date": today,
            "services": {
                "grok_api": {"total_cost_usd": 0.02},
                "tts_api": {"estimated_cost_usd": 0.10},
            },
            "total_estimated_cost_usd": 0.12,
        })
        out = gd.aggregate_costs(tmp_path, [{"slug": "spacex", "name": "SpaceX Daily"}])
        net = out["network_last_30_days"]
        assert net["total"] == pytest.approx(0.12)
        assert net["multilingual"] == 0.0 and net["motion"] == 0.0 and net["review"] == 0.0
        assert net["episodes"] == 1 and net["files"] == 1

    def test_projection_note_names_every_bucket(self, tree):
        gd = _load_dashboard_module()
        out = gd.aggregate_costs(tree, [{"slug": "tesla", "name": "Tesla Shorts Time"}])
        note = out["projections"]["note"]
        for word in ("multilingual", "motion", "reviewer", "images", "search"):
            assert word in note


class TestManagementCostCard:
    """The card renders the new lines, and never fabricates a $0.00."""

    def test_card_reads_multilingual_motion_and_review(self):
        src = (REPO_ROOT / "management.html").read_text(encoding="utf-8")
        assert "n7.multilingual" in src
        assert "n7.motion" in src
        assert "n7.review" in src
        assert "moneyOrDash" in src


# ---------------------------------------------------------------------------
# A. record_motion_clip_usage + save_usage total
# ---------------------------------------------------------------------------

class TestMotionClipUsage:

    def test_shape_matches_image_api_and_is_additive(self):
        tracker = tracking.create_tracker("Tesla Shorts Time", 700)
        tracking.record_motion_clip_usage(tracker, 1, 0.28)
        tracking.record_motion_clip_usage(tracker, 0, 0.10)   # billed, no clip
        motion = tracker["services"]["motion_api"]
        assert motion["provider"] == "grok-imagine-video"
        assert motion["clips_generated"] == 1
        assert motion["estimated_cost_usd"] == pytest.approx(0.38)
        assert set(motion) >= {"provider", "model", "clips_generated", "estimated_cost_usd"}

    def test_save_usage_total_includes_motion(self, tmp_path):
        tracker = tracking.create_tracker("Tesla Shorts Time", 700)
        tracking.record_tts_usage(tracker, 10_000, provider="grok")
        tracking.record_image_usage(tracker, 4, 0.16)
        tracking.record_motion_clip_usage(tracker, 1, 0.28)
        path = tracking.save_usage(tracker, tmp_path)
        assert path is not None and path.name == f"credit_usage_{tracker['date']}_ep700.json"
        data = json.loads(path.read_text(encoding="utf-8"))
        expected = 10_000 / 1000 * tracking.GROK_TTS_COST_PER_1K_CHARS + 0.16 + 0.28
        assert data["total_estimated_cost_usd"] == pytest.approx(expected)

    def test_old_tracker_without_motion_block_saves(self, tmp_path):
        tracker = tracking.create_tracker("SpaceX Daily", 1)
        tracker["services"].pop("motion_api", None)
        assert tracking.save_usage(tracker, tmp_path) is not None

    def test_run_show_wires_motion_cost_into_the_tracker(self):
        src = (REPO_ROOT / "run_show.py").read_text(encoding="utf-8")
        assert "record_motion_clip_usage(" in src
        assert 'youtube_urls.get("hook_short_motion_cost_usd"' in src
        # The metric stays — engine/pipeline.py is untouched.
        pipe = (REPO_ROOT / "engine" / "pipeline.py").read_text(encoding="utf-8")
        assert 'metrics.record("hook_short_motion_cost_usd"' in pipe


class TestTtsRate:
    def test_grok_tts_constant_is_the_verified_list_price(self):
        # $15.00 / 1M chars at https://docs.x.ai/docs/models (2026-10-02).
        assert tracking.GROK_TTS_COST_PER_1K_CHARS == pytest.approx(0.015)
        src = (REPO_ROOT / "engine" / "tracking.py").read_text(encoding="utf-8")
        assert "docs.x.ai/docs/models" in src
        assert "2026-10-02" in src


# ---------------------------------------------------------------------------
# B. scene briefs + title bundle record usage when a tracker is passed
# ---------------------------------------------------------------------------

_META = {
    "provider": "openai_compat",
    "model": "grok-4.3",
    "usage": {"prompt_tokens": 900, "completion_tokens": 120,
              "total_tokens": 1020, "cached_tokens": 100},
}


class TestYouTubeStageLlmUsage:

    def test_record_llm_usage_from_meta(self):
        tracker = tracking.create_tracker("X", 1)
        assert tracking.record_llm_usage_from_meta(tracker, "scene_briefs", _META)
        step = tracker["services"]["grok_api"]["scene_briefs"]
        assert step["prompt_tokens"] == 900
        assert step["completion_tokens"] == 120
        assert step["cached_tokens"] == 100
        assert step["model"] == "grok-4.3"
        assert step["estimated_cost_usd"] > 0
        # None tracker / no usage are no-ops.
        assert tracking.record_llm_usage_from_meta(None, "scene_briefs", _META) is False
        assert tracking.record_llm_usage_from_meta(tracker, "x", {"model": "grok-4.3"}) is False

    def test_scene_briefs_record_when_tracker_given(self, monkeypatch):
        from engine import generator, scene_briefs

        briefs = json.dumps([
            "A red Cybercab parked under sodium lights at a Texas depot, low angle, dusk.",
            "A Starship booster on the launch mount at Boca Chica, wide shot, dawn mist.",
        ])
        monkeypatch.setattr(generator, "_call_grok", lambda *a, **k: (briefs, dict(_META)))
        tracker = tracking.create_tracker("Tesla Shorts Time", 1)
        out = scene_briefs.generate_scene_briefs(
            ["Tesla Cybercab fleet grows", "SpaceX stacks Starship"],
            hook="Two launches", show_name="Tesla Shorts Time",
            show_descriptor="photo", tracker=tracker,
        )
        assert len(out) == 2
        step = tracker["services"]["grok_api"]["scene_briefs"]
        assert step["prompt_tokens"] == 900 and step["completion_tokens"] == 120

    def test_scene_briefs_record_nothing_without_tracker(self, monkeypatch):
        from engine import generator, scene_briefs

        calls = []
        monkeypatch.setattr(tracking, "record_llm_usage",
                            lambda *a, **k: calls.append((a, k)))
        briefs = json.dumps(["A red car under lights at a depot, low angle, dusk.",
                             "A booster on the mount at dawn, wide shot."])
        monkeypatch.setattr(generator, "_call_grok", lambda *a, **k: (briefs, dict(_META)))
        scene_briefs.generate_scene_briefs(
            ["Tesla Cybercab fleet grows", "SpaceX stacks Starship"],
            hook="Two launches", show_name="Tesla Shorts Time", show_descriptor="photo",
        )
        assert calls == []

    def test_title_bundle_records_when_tracker_given(self, monkeypatch):
        from engine import generator, youtube_titles

        text = "TITLE: Tesla Cybercab fleet doubles\nPUNCH: FLEET DOUBLES\nSHORT1: Cybercab doubles"
        monkeypatch.setattr(generator, "_call_grok", lambda *a, **k: (text, dict(_META)))
        tracker = tracking.create_tracker("Tesla Shorts Time", 1)
        bundle = youtube_titles.generate_title_bundle(
            hook="Tesla doubles the Cybercab fleet", digest_text="…",
            show_name="Tesla Shorts Time", episode_num=1,
            short_window_texts=["Cybercab doubles"], tracker=tracker,
        )
        assert bundle["titles"]
        step = tracker["services"]["grok_api"]["youtube_titles"]
        assert step["total_tokens"] == 1020
        assert step["model"] == "grok-4.3"

    def test_title_bundle_records_nothing_without_tracker(self, monkeypatch):
        from engine import generator, youtube_titles

        calls = []
        monkeypatch.setattr(tracking, "record_llm_usage",
                            lambda *a, **k: calls.append((a, k)))
        text = "TITLE: Tesla Cybercab fleet doubles\nPUNCH: FLEET DOUBLES"
        monkeypatch.setattr(generator, "_call_grok", lambda *a, **k: (text, dict(_META)))
        youtube_titles.generate_title_bundle(
            hook="h", digest_text="d", show_name="s", episode_num=1)
        assert calls == []

    def test_run_show_threads_the_tracker(self):
        src = (REPO_ROOT / "run_show.py").read_text(encoding="utf-8")
        sig_start = src.index("def _publish_youtube(")
        sig_end = src.index(") -> dict:", sig_start)
        assert "tracker:" in src[sig_start:sig_end]
        call = src.index("youtube_urls = _publish_youtube(")
        call_end = src.index("    )\n", call)
        assert "tracker=tracker" in src[call:call_end]
        for fn in ("generate_title_bundle(", "generate_scene_briefs("):
            at = src.index("_bundle = " + fn if fn.startswith("generate_title") else "_scene_briefs = " + fn)
            end = src.index(")\n", at + 200)
            assert "tracker=tracker" in src[at:end + 1], fn

    def test_step_labels_name_the_new_steps(self):
        for step in ("scene_briefs", "youtube_titles", "episode_review"):
            assert step in tracking._STEP_LABELS


# ---------------------------------------------------------------------------
# C. the reviewer writes ONE dated credit file per run day
# ---------------------------------------------------------------------------

class _Usage:
    def __init__(self, p, c, cached=0):
        self.prompt_tokens = p
        self.completion_tokens = c
        self.total_tokens = p + c
        self.prompt_tokens_details = type("D", (), {"cached_tokens": cached})()


class _Resp:
    def __init__(self, text, usage):
        self.usage = usage
        self.choices = [type("C", (), {"message": type("M", (), {"content": text})()})()]


class TestReviewerCreditFile:

    def test_write_review_credit_file_merges_same_day_runs(self, tmp_path):
        rv = _load_review_module()
        day = _dt.date(2026, 10, 2)
        calls = [{"model": "grok-4.3", "prompt_tokens": 4000, "completion_tokens": 300,
                  "cached_tokens": 0}] * 3
        p1 = rv.write_review_credit_file(day, calls=calls, out_dir=tmp_path, run_day=day)
        assert p1 is not None and p1.name == "credit_usage_2026-10-02_review.json"
        d1 = json.loads(p1.read_text(encoding="utf-8"))
        assert d1["review"] == {"runs": 1, "calls": 3, "last_target_date": "2026-10-02"}
        step = d1["services"]["grok_api"]["episode_review"]
        assert step["prompt_tokens"] == 12_000 and step["model"] == "grok-4.3"
        assert d1["total_estimated_cost_usd"] == pytest.approx(
            tracking._estimate_grok_cost("grok-4.3", 12_000, 900))
        assert d1["episode_number"] == 0 and d1["date"] == "2026-10-02"

        # Second run the same day: merged, not overwritten, not doubled.
        p2 = rv.write_review_credit_file(day, calls=calls[:2], out_dir=tmp_path, run_day=day)
        assert p2 == p1
        d2 = json.loads(p2.read_text(encoding="utf-8"))
        assert d2["review"]["runs"] == 2 and d2["review"]["calls"] == 5
        assert d2["services"]["grok_api"]["episode_review"]["prompt_tokens"] == 20_000
        assert len(list(tmp_path.glob("credit_usage_*"))) == 1

    def test_no_calls_writes_nothing(self, tmp_path):
        rv = _load_review_module()
        assert rv.write_review_credit_file(_dt.date.today(), calls=[], out_dir=tmp_path) is None
        assert list(tmp_path.iterdir()) == []

    def test_ai_review_episode_accumulates_usage(self, monkeypatch):
        rv = _load_review_module()
        import openai

        class _Client:
            def __init__(self, **kw):
                self.chat = type("Chat", (), {})()
                self.chat.completions = type("Comp", (), {})()
                self.chat.completions.create = lambda **kw: _Resp(
                    "FACTUAL_ERRORS: NO\nQUALITY_SCORE: 8\nSUMMARY: fine", _Usage(5000, 200, 1000))

        monkeypatch.setattr(openai, "OpenAI", _Client)
        monkeypatch.setenv("GROK_API_KEY", "test-key")
        monkeypatch.setattr(rv, "_load_reviewer_settings", lambda slug: ("grok-4.3", 1500, 0.3))
        rv._REVIEW_USAGE.clear()
        ep = rv.EpisodeReview(show_slug="tesla", show_name="Tesla Shorts Time",
                              episode_num=700, date="2026-10-02",
                              digest_text="word " * 400, tts_text="word " * 400)
        rv.ai_review_episode(ep)
        assert rv._REVIEW_USAGE == [{
            "model": "grok-4.3", "prompt_tokens": 5000,
            "completion_tokens": 200, "cached_tokens": 1000}]

    def test_run_review_writes_the_file(self):
        src = (REPO_ROOT / "review_episodes.py").read_text(encoding="utf-8")
        at = src.index("def run_review(")
        body = src[at:src.index("def write_review_json(")]
        assert "write_review_credit_file(target_date)" in body
        assert "_record_review_call(resp, reviewer_model)" in src

    def test_daily_audit_commits_the_review_dir(self):
        wf = (REPO_ROOT / ".github" / "workflows" / "daily-audit.yml").read_text(encoding="utf-8")
        at = wf.index("add-paths:")
        block = wf[at:wf.index("commit-message:", at)]
        assert "digests/_review/*.json" in block
