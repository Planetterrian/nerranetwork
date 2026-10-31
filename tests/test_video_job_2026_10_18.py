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
                     "_write_blog_post(\n            youtube_long_url, youtube_short_url, refresh=True,",
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
        # A real run's name is exactly run_title(); a rehearsal adds " (rehearsal)".
        assert ("format('Render video: {0} {1}{2}', inputs.show, inputs.date, "
                "inputs.rehearse && ' (rehearsal)' || '')") in VIDEO_WF
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
        assert render["name"] == "${{ inputs.rehearse && 'rehearse' || 'render' }} (${{ inputs.show }})"
        assert render["concurrency"]["group"] == "video-${{ inputs.show }}"
        checkout = render["steps"][0]
        # The branch tip at checkout time (production dispatches main).
        assert checkout["with"]["ref"] == "${{ github.ref_name }}"
        assert '"ref": "main"' in (ROOT / "scripts" / "video_job.py").read_text()
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
        # Oct 19 2026: the video job dispatches the sweep itself once the
        # scene manifest is on main (scripts/followup_dispatch.py); the
        # workflow_run fan-out is gone. The cron passes still wait on a
        # pending video, and the show run's dispatch defers to the video job.
        assert "workflow_run:" not in ML_WF
        assert ".video_pending_" in ML_WF and "Waiting for their video job" in ML_WF
        video_wf = (ROOT / ".github" / "workflows" / "render-video.yml").read_text(encoding="utf-8")
        assert "followup_dispatch.py multilingual" in video_wf and "--after-video" in video_wf
        script = (ROOT / "scripts" / "followup_dispatch.py").read_text(encoding="utf-8")
        assert "the video job is still rendering" in script


# --------------------------------------------------- the reel's preview loop --
class TestShortPreviewWiring:
    def test_the_index_row_carries_the_preview(self, tmp_path):
        from engine.youtube_index import record_video
        idx = tmp_path / "youtube_videos.json"
        assert record_video(video_id="abcdefghijk", show_slug="spacex", episode=1,
                            kind="short", preview_url="https://audio.example/p.mp4",
                            index_path=idx)
        assert record_video(video_id="bcdefghijkl", show_slug="spacex", episode=1,
                            kind="short", index_path=idx)
        rows = json.loads(idx.read_text())["videos"]
        assert rows[0]["preview_url"] == "https://audio.example/p.mp4"
        assert "preview_url" not in rows[1]

    def test_the_short_upload_cuts_and_records_it(self):
        assert "make_short_preview(this_short_video_path, _pv," in RUN_SHOW
        assert "start_s=SHORT_PREVIEW_START_S" in RUN_SHOW
        assert "preview_url=_preview_url," in RUN_SHOW
        from engine.pipeline import record_youtube_outcomes
        from engine.metrics import PipelineMetrics
        m = PipelineMetrics(show_slug="s", episode_num=1)
        from engine.config import load_config
        record_youtube_outcomes(m, {"short_preview_urls": ["a", "b"]}, 1.0,
                                config=load_config(ROOT / "shows" / "spacex.yaml"))
        assert m.counters["short_previews_uploaded"] == 2


# ------------------------------------------------------------- rehearsal --
class TestTheRehearsal:
    def test_it_removes_every_publishing_credential(self):
        from scripts.rehearse_video import scrub_environment
        env = {"GROK_API_KEY": "k", "PEXELS_API_KEY": "p", "R2_ACCESS_KEY_ID": "x",
               "YOUTUBE_REFRESH_TOKEN_EN": "x", "NERRANETWORK_X_ACCESS_TOKEN": "x",
               "X_QUEUE_SUPABASE_KEY": "x", "BUTTONDOWN_API_KEY": "x",
               "NOTIFICATION_WEBHOOK_URL": "x", "NERRA_VIDEO_JOB": "1",
               "PERSONAL_DEMAND_TOKEN": "x", "PIPELINE_TIMEOUT_SECONDS": "6600"}
        scrub_environment(env)
        assert set(env) == {"GROK_API_KEY", "PEXELS_API_KEY", "PIPELINE_TIMEOUT_SECONDS",
                            "R2_ACCESS_KEY_ID"}
        # Every credential the real video job is given is covered.
        video_env = set(_step_env(VIDEO_WF, "Render and publish the video"))
        keep = {"GROK_API_KEY", "ELEVENLABS_API_KEY", "GROK_CLONED_VOICE_ID",
                "PEXELS_API_KEY", "PIPELINE_TIMEOUT_SECONDS", "NERRA_LLM_TIMEOUT_SECONDS",
                "NERRA_SINGLE_PASS_RENDER", "NERRA_X264_PRESET",
                "R2_ENDPOINT_URL", "R2_ACCESS_KEY_ID", "R2_SECRET_ACCESS_KEY"}
        probe = {k: "x" for k in video_env}
        scrub_environment(probe)
        assert set(probe) <= keep, set(probe) - keep

    def test_every_youtube_write_is_faked(self, tmp_path):
        from scripts.rehearse_video import FakeYouTube
        mod = SimpleNamespace()
        FakeYouTube(tmp_path).install(mod)
        for name in ("get_channel_credentials_from_env", "upload_video",
                     "add_video_to_playlist", "update_video_title", "post_video_comment",
                     "video_has_comment", "upload_caption_track",
                     "upload_caption_track_detailed"):
            assert callable(getattr(mod, name)), name
        import engine.youtube as yt
        writes = {n for n in dir(yt) if n.startswith(("upload_", "post_", "add_", "update_"))
                  and callable(getattr(yt, n))}
        assert writes <= set(vars(mod)), writes - set(vars(mod))

    def test_the_upload_keeps_the_file(self, tmp_path):
        from scripts.rehearse_video import FakeYouTube
        src = tmp_path / "ep.mp4"
        src.write_bytes(b"\0" * 10)
        out = tmp_path / "out"
        out.mkdir()
        fake = FakeYouTube(out)
        res = fake.upload_video(src, title="T")
        assert (out / "01_ep.mp4").exists() and res.video_id == "REHEARSAL01"
        assert fake.uploads[0]["title"] == "T"

    def test_it_rebuilds_the_handoff_from_a_published_episode(self):
        from engine.config import load_config
        from scripts.rehearse_video import published_handoff
        cfg = load_config(ROOT / "shows" / "spacex.yaml")
        h = published_handoff(cfg, ROOT / cfg.episode.output_dir, dt.date(2026, 10, 18))
        assert h["episode_num"] == 134
        assert h["audio_url"].endswith("/SpaceX_Daily_Ep134_20261018.mp3")
        assert h["mp3"] == "SpaceX_Daily_Ep134_20261018.mp3"

    def test_the_workflow_publishes_nothing_on_a_rehearsal(self):
        doc = yaml.safe_load(VIDEO_WF)
        steps = {s.get("name"): s for s in doc["jobs"]["render"]["steps"]}
        for name in ("Regenerate show HTML pages", "Commit and push the video's artifacts"):
            assert "!inputs.rehearse" in steps[name]["if"]
        assert "scripts/rehearse_video.py" in steps["Render and publish the video"]["run"]
        assert steps["Attach the rehearsal's videos and report"]["uses"].startswith(
            "actions/upload-artifact@")

    def test_r2_is_read_only(self, monkeypatch):
        import boto3
        import botocore.client
        from botocore.exceptions import ClientError
        from scripts.rehearse_video import block_s3_writes
        monkeypatch.setattr(botocore.client.BaseClient, "_make_api_call",
                            botocore.client.BaseClient._make_api_call)
        blocked = block_s3_writes()
        s3 = boto3.client("s3", endpoint_url="http://127.0.0.1:9", region_name="auto",
                          aws_access_key_id="x", aws_secret_access_key="y")
        for call in (lambda: s3.put_object(Bucket="b", Key="k", Body=b"x"),
                     lambda: s3.delete_object(Bucket="b", Key="k"),
                     lambda: s3.create_multipart_upload(Bucket="b", Key="k")):
            with pytest.raises(ClientError) as exc:
                call()
            assert exc.value.response["Error"]["Code"] == "RehearsalReadOnly"
        assert blocked == ["PutObject", "DeleteObject", "CreateMultipartUpload"]

    def test_r2_uploads_are_refused_at_once(self, monkeypatch, tmp_path):
        import engine.storage as storage
        from scripts.rehearse_video import refuse_r2_uploads
        monkeypatch.setattr(storage, "upload_to_r2", storage.upload_to_r2)
        refused = refuse_r2_uploads()
        from engine.storage import upload_to_r2   # bound after: the refusal
        src = tmp_path / "a.mp4"
        src.write_bytes(b"x")
        assert upload_to_r2(src, "previews/s/ep1-short1.mp4", bucket="b",
                            endpoint_url="e", access_key="a", secret_key="s") == ""
        assert refused == ["previews/s/ep1-short1.mp4"]
