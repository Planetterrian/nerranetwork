"""The separate video job (Oct 18 2026).

The audio job stops at the audio-first checkpoint and leaves a handoff marker;
.github/workflows/render-video.yml renders, uploads, links and posts to X from
it in its own job, with its own time limit (run_show.py --video-phase).
"""

from __future__ import annotations

import datetime as dt
import json
import re
import subprocess
from pathlib import Path
from types import SimpleNamespace

import pytest
import yaml

ROOT = Path(__file__).resolve().parent.parent
RUN_SHOW = (ROOT / "run_show.py").read_text(encoding="utf-8")
RUN_WF = (ROOT / ".github" / "workflows" / "run-show.yml").read_text(encoding="utf-8")
VIDEO_WF_PATH = ROOT / ".github" / "workflows" / "render-video.yml"
VIDEO_WF = VIDEO_WF_PATH.read_text(encoding="utf-8")
ML_WF = (ROOT / ".github" / "workflows" / "multilingual.yml").read_text(encoding="utf-8")


def _run_body() -> str:
    start = RUN_SHOW.index("def run(args: argparse.Namespace) -> None:")
    return RUN_SHOW[start:RUN_SHOW.index("\ndef ", start + 10)]


def _args(**kw):
    base = dict(show="spacex", test=False, dry_run=False, rehearse=False,
                skip_youtube=False, resume_publish=False, resume_youtube=False,
                video_phase=False, skip_x=False, skip_newsletter=False,
                skip_podcast=False, date=None, force_video=False)
    base.update(kw)
    return SimpleNamespace(**base)


def _config(youtube=True, video_podcast=False):
    return SimpleNamespace(youtube=SimpleNamespace(enabled=youtube),
                           video_podcast=SimpleNamespace(enabled=video_podcast))


# ------------------------------------------------------------ the switch --
class TestWhenTheVideoIsHandedOver:
    def test_needs_the_workflow_switch(self, monkeypatch):
        import run_show
        monkeypatch.delenv(run_show.VIDEO_JOB_ENV, raising=False)
        assert run_show._video_job_wanted(_config(), _args()) is False
        monkeypatch.setenv(run_show.VIDEO_JOB_ENV, "1")
        assert run_show._video_job_wanted(_config(), _args()) is True

    @pytest.mark.parametrize("flag", ["test", "dry_run", "rehearse", "skip_youtube",
                                      "resume_publish", "resume_youtube", "video_phase"])
    def test_never_from_a_run_that_is_not_a_daily_episode(self, monkeypatch, flag):
        import run_show
        monkeypatch.setenv(run_show.VIDEO_JOB_ENV, "1")
        assert run_show._video_job_wanted(_config(), _args(**{flag: True})) is False

    def test_a_show_with_no_video_keeps_its_x_post_in_the_audio_job(self, monkeypatch):
        import run_show
        monkeypatch.setenv(run_show.VIDEO_JOB_ENV, "1")
        assert run_show._video_job_wanted(_config(youtube=False), _args()) is False
        assert run_show._video_job_wanted(
            _config(youtube=False, video_podcast=True), _args()) is True


# -------------------------------------------------------- inline == before --
class TestTheInlineRunIsUnchanged:
    def test_run_builds_both_writers_from_the_factories(self):
        body = _run_body()
        assert "_write_rss_feed = _make_feed_writer(" in body
        assert "_write_blog_post = _make_blog_writer(" in body
        assert "def _write_rss_feed(" not in body
        assert "def _write_blog_post(" not in body

    def test_the_handoff_rides_the_audio_commit(self):
        body = _run_body()
        handoff = body.index("_write_video_handoff(")
        checkpoint = body.index("_checkpoint_publish(args, metrics)")
        video = body.index("_run_video_stage(")
        assert handoff < checkpoint < video
        assert "if not _video_deferred:\n        _run_video_stage(" in body

    def test_the_newsletter_stays_with_the_audio_and_x_goes_with_the_video(self):
        body = _run_body()
        newsletter = body.index("# 12b. Send newsletter")
        x_stage = body.index("_run_x_stage(")
        assert body.index("_run_video_stage(") < newsletter < x_stage
        assert "if not _video_deferred:\n        _run_x_stage(" in body

    def test_the_moved_code_kept_its_steps(self):
        video = RUN_SHOW[RUN_SHOW.index("def _run_video_stage("):RUN_SHOW.index("def _run_x_stage(")]
        for step in ("_publish_youtube(", "record_youtube_outcomes(",
                     "_write_rss_feed(youtube_long_url, refresh=True",
                     "_write_blog_post(\"\" if youtube_long_scheduled else youtube_long_url",
                     "build_video_feed_for_show("):
            assert step in video
        x_stage = RUN_SHOW[RUN_SHOW.index("def _run_x_stage("):]
        assert "x_queue.enqueue_reply(" in x_stage and "post_to_x(" in x_stage


# --------------------------------------------------------------- handoff --
class TestTheHandoff:
    def test_it_carries_what_is_not_committed(self, tmp_path):
        import run_show
        mp3 = tmp_path / "SpaceX_Ep140_20261018.mp3"
        path = run_show._write_video_handoff(
            tmp_path, show_slug="spacex", episode_num=140, today=dt.date(2026, 10, 18),
            final_mp3=mp3, r2_audio_url="https://audio.nerranetwork.com/spacex/x.mp3",
            rss_audio_url="https://op3.dev/e/audio.nerranetwork.com/spacex/x.mp3",
            hook="Starship flies", title_hook="Starship", audio_duration=601.234,
            digest_md=tmp_path / "SpaceX_Ep140_20261018.md",
            extra_context={"price": "141.50", "hook": "Starship flies",
                           "big": "x" * 5000, "articles": [{"a": 1}], "n": 3})
        assert path.name == ".video_pending_20261018.json"
        data = json.loads(path.read_text())
        assert data["episode_num"] == 140 and data["date"] == "2026-10-18"
        assert data["mp3"] == mp3.name and data["digest_md"] == "SpaceX_Ep140_20261018.md"
        assert data["audio_url"].startswith("https://audio.") and data["audio_duration"] == 601.23
        # Short scalars only: the teaser's fields, never a prompt-sized block.
        assert data["extra_context"] == {"price": "141.50", "hook": "Starship flies", "n": 3}

    def test_the_marker_is_committed(self):
        out = subprocess.run(
            ["git", "check-ignore", "-q", "digests/spacex/.video_pending_20261018.json"],
            cwd=ROOT)
        assert out.returncode == 1, "the handoff marker must not be gitignored"
        staging = (ROOT / "scripts" / "stage_show_artifacts.sh").read_text()
        assert "git add -A digests/" in staging


# ----------------------------------------------------------- video phase --
@pytest.fixture
def phase(tmp_path, monkeypatch):
    import run_show
    from engine.config import load_config

    real = load_config(ROOT / "shows" / "spacex.yaml")
    monkeypatch.setattr(run_show, "PROJECT_ROOT", tmp_path)
    monkeypatch.setattr("engine.config.load_config", lambda _p: real)
    out = tmp_path / real.episode.output_dir
    out.mkdir(parents=True)
    today = dt.date(2026, 10, 18)
    (out / "SpaceX_Ep140_20261018.md").write_text("# Digest\n\nBody.\n")
    (out / "metrics_ep140.json").write_text(json.dumps({
        "show_slug": "spacex", "episode_num": 140,
        "stages": [{"name": "digest", "duration_s": 12.0, "success": True}],
        "counters": {"tts_duration_s": 90.0}}))
    run_show._write_video_handoff(
        out, show_slug="spacex", episode_num=140, today=today,
        final_mp3=out / "SpaceX_Ep140_20261018.mp3",
        r2_audio_url="https://audio.example/spacex/SpaceX_Ep140_20261018.mp3",
        rss_audio_url="", hook="Hook", title_hook="Hook", audio_duration=600.0,
        digest_md=out / "SpaceX_Ep140_20261018.md", extra_context={"price": "1"})
    calls = {}

    def fake_fetch(url, dest, attempts=3):
        calls["fetched"] = url
        dest.write_bytes(b"ID3")

    def fake_video(**kw):
        calls["video"] = kw
        kw["metrics"].record("youtube_long_form_uploaded", True)

    monkeypatch.setattr(run_show, "_fetch_episode_mp3", fake_fetch)
    monkeypatch.setattr(run_show, "_run_video_stage", fake_video)
    monkeypatch.setattr(run_show, "_run_x_stage", lambda **kw: calls.setdefault("x", kw))
    monkeypatch.setattr("engine.tracking.save_usage", lambda tracker, d: calls.setdefault("usage", tracker))
    return SimpleNamespace(run_show=run_show, out=out, calls=calls, today=today)


class TestTheVideoPhase:
    def test_renders_posts_and_marks_it_done(self, phase):
        phase.run_show.run_video_phase(_args(video_phase=True, date="2026-10-18"))
        c = phase.calls
        assert c["fetched"] == "https://audio.example/spacex/SpaceX_Ep140_20261018.mp3"
        assert c["video"]["episode_num"] == 140 and c["video"]["x_thread"].startswith("# Digest")
        assert c["video"]["extra_context"] == {"price": "1"}
        assert c["x"]["episode_published"] is True
        assert not (phase.out / ".video_pending_20261018.json").exists()
        done = json.loads((phase.out / ".video_done_20261018.json").read_text())
        assert done["long_form_uploaded"] is True and done["episode_num"] == 140
        # The audio job's metrics are kept and the video's added to them.
        m = json.loads((phase.out / "metrics_ep140.json").read_text())
        assert m["counters"]["tts_duration_s"] == 90.0
        assert m["counters"]["video_job"] == "rendered"
        assert [s["name"] for s in m["stages"]] == ["digest"]
        # The MP3 it fetched is not left on the runner.
        assert not (phase.out / "SpaceX_Ep140_20261018.mp3").exists()

    def test_a_done_video_is_not_rendered_twice(self, phase):
        (phase.out / ".video_done_20261018.json").write_text("{}")
        phase.run_show.run_video_phase(_args(video_phase=True, date="2026-10-18"))
        assert "video" not in phase.calls

    def test_no_handoff_is_a_loud_failure(self, phase):
        (phase.out / ".video_pending_20261018.json").unlink()
        with pytest.raises(SystemExit) as exc:
            phase.run_show.run_video_phase(_args(video_phase=True, date="2026-10-18"))
        assert exc.value.code == 1

    def test_main_routes_the_flag(self):
        assert "if args.video_phase:\n            run_video_phase(args)" in RUN_SHOW


def test_metrics_round_trip(tmp_path):
    from engine.metrics import PipelineMetrics
    m = PipelineMetrics(show_slug="s", episode_num=3)
    m.record_stage("digest", 4.5)
    m.record("youtube_publish_duration_s", 10.0)
    path = m.save(tmp_path)
    back = PipelineMetrics.load(path)
    assert back.to_dict() == m.to_dict()


# ----------------------------------------------------------------- sweep --
class TestTheSweep:
    def test_run_title_matches_the_workflow_run_name(self):
        from scripts.video_job import run_title
        assert "format('Render video: {0} {1}', inputs.show, inputs.date)" in VIDEO_WF
        assert run_title("spacex", "2026-10-18") == "Render video: spacex 2026-10-18"

    def test_starts_only_lost_dispatches(self):
        from scripts.video_job import plan_sweep, run_title
        handoffs = [("a", "2026-10-18", 45.0),   # lost: starts
                    ("b", "2026-10-18", 5.0),    # its own dispatch is in flight
                    ("c", "2026-10-18", 90.0),   # already has a run (any outcome)
                    ("d", "2026-10-16", 3000.0)]  # too old: reported, never started
        start, stale = plan_sweep(handoffs, {run_title("c", "2026-10-18")})
        assert start == [("a", "2026-10-18")]
        assert stale == [("d", "2026-10-16")]

    def test_a_done_video_is_not_due(self, tmp_path, monkeypatch):
        import scripts.video_job as vj
        monkeypatch.setattr(vj, "ROOT", tmp_path)
        d = tmp_path / "digests" / "spacex"
        d.mkdir(parents=True)
        stamp = {"show": "spacex", "date": "2026-10-18",
                 "created_at": "2026-10-18T10:00:00+00:00"}
        (d / ".video_pending_20261018.json").write_text(json.dumps(stamp))
        now = dt.datetime(2026, 10, 18, 11, 0, tzinfo=dt.timezone.utc)
        assert [h[:2] for h in vj.due_handoffs(now)] == [("spacex", "2026-10-18")]
        (d / ".video_done_20261018.json").write_text("{}")
        assert vj.due_handoffs(now) == []


# ------------------------------------------------------------- workflows --
def _step_env(wf_text: str, step_name: str) -> dict:
    doc = yaml.safe_load(wf_text)
    for job in doc["jobs"].values():
        for step in job.get("steps", []):
            if step.get("name") == step_name:
                return step.get("env") or {}
    raise AssertionError(step_name)


class TestTheWorkflows:
    def test_the_video_job_has_every_credential_the_show_run_has(self):
        show = set(_step_env(RUN_WF, "Run show pipeline"))
        video = set(_step_env(VIDEO_WF, "Render and publish the video"))
        assert show - {"NERRA_AUDIO_FIRST_PUSH", "NERRA_VIDEO_JOB"} == video

    def test_its_own_time_limit_sits_above_its_watchdog(self):
        doc = yaml.safe_load(VIDEO_WF)
        step = next(s for s in doc["jobs"]["render"]["steps"]
                    if s.get("name") == "Render and publish the video")
        watchdog = int(step["env"]["PIPELINE_TIMEOUT_SECONDS"])
        assert step["timeout-minutes"] * 60 - watchdog >= 300
        assert watchdog > 4200, "longer than the show run's own budget, or there is no point"

    def test_it_runs_on_main_and_one_show_at_a_time(self):
        doc = yaml.safe_load(VIDEO_WF)
        render = doc["jobs"]["render"]
        assert render["name"] == "render (${{ inputs.show }})"
        assert render["concurrency"]["group"] == "video-${{ inputs.show }}"
        checkout = render["steps"][0]
        assert checkout["with"]["ref"] == "main"
        # Never the finalize group: a short job would supersede a pending finalize.
        assert doc["jobs"]["homepage"]["concurrency"]["group"] != "finalize-shared-pages"

    def test_its_commit_counts_as_the_shows_and_names_the_video(self):
        assert 'git commit -m "Auto-generated: ${{ inputs.show }} ${{ inputs.date }} (video)"' in VIDEO_WF
        assert "scripts/create_recovery_pr.sh" in VIDEO_WF

    def test_the_show_run_switches_it_on_and_starts_it(self):
        assert ("NERRA_VIDEO_JOB: ${{ github.event.inputs.test_mode == 'true' && '0' "
                "|| vars.NERRA_VIDEO_JOB || '1' }}") in RUN_WF
        assert "actions: write" in RUN_WF
        commit = RUN_WF.index("- name: Commit and push output")
        start = RUN_WF.index("- name: Start the video job")
        assert commit < start
        assert 'python scripts/video_job.py dispatch --show "${{ matrix.show }}"' in RUN_WF

    def test_multilingual_follows_the_video(self):
        assert 'workflows: ["Run Podcast Show", "Render Episode Video"]' in ML_WF
        assert re.search(r"\(\?:run\|render\)", ML_WF)
        assert ".video_pending_" in ML_WF and "Waiting for their video job" in ML_WF
