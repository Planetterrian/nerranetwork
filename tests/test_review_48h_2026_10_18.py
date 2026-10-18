"""The 48-hour review of Oct 17-18 2026, checked and acted on.

Three reviewers read everything merged in the window against the day's
committed episodes and runs. What they found that was true, and is fixed
here:

* the homepage's "Also in this episode" headlines and the interview cards'
  guest name / identifier / co-host / dek rendered RAW under
  ``autoescape=False`` — model- and web-form-written text;
* ``workers/gallery/wrangler.toml`` carried a placeholder KV namespace id,
  which wrangler refuses at upload, so every pending deploy of that Worker
  was blocked;
* the homepage render re-parsed 145 show YAMLs (15 of its 18 seconds) and
  is rebuilt ~26 times a day;
* ``pick_videos`` judged "still scheduled" by the wall clock, not the
  build's ``now``;
* the summaries record's ``datetime`` was a naive local stamp read as UTC;
* the structural digest retry replaced the module stashes (claims ledger,
  combined script) before the caller decided whether the retry shipped, and
  its deadline thread kept writing them after the caller gave up;
* the two chapter passes disagreed by ``intro_duration``;
* the video job's commit step ran only on a successful video step, so a
  job that died AFTER uploading lost its YouTube index and the failure
  alert invited the duplicate upload;
* the multilingual cron passes ignored a running video job;
* ``x_queue.enqueue`` hosted the clip before the duplicate check;
* ``_schedule_refused`` treated any HTTP 400 as a publishAt refusal;
* the Show Review Agent swallowed git's stderr (a $0.13 review was lost to
  a push rejection nobody could read);
* the UC restock added a duplicate topic and a brief that contradicted its
  own first source.
"""

from __future__ import annotations

import datetime as dt
import json
import re
import subprocess
import sys
import threading
import time
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

UTC = dt.timezone.utc
NOW = dt.datetime(2026, 10, 17, 13, 30, tzinfo=UTC)

TEMPLATE = (ROOT / "templates" / "network_page.html.j2").read_text(encoding="utf-8")
RUN_SHOW = (ROOT / "run_show.py").read_text(encoding="utf-8")
GEN_HTML = (ROOT / "generate_html.py").read_text(encoding="utf-8")
VIDEO_WF = (ROOT / ".github" / "workflows" / "render-video.yml").read_text(encoding="utf-8")
ML_WF = (ROOT / ".github" / "workflows" / "multilingual.yml").read_text(encoding="utf-8")
WRANGLER = (ROOT / "workers" / "gallery" / "wrangler.toml").read_text(encoding="utf-8")

XSS = '<img src=x onerror=alert(1)>'
XSS_ESCAPED = "&lt;img src=x onerror=alert(1)&gt;"


# ------------------------------------------------------------- homepage --
class TestHomepageEscapesEveryModelAndFormString:
    def test_more_headlines_and_guest_fields_use_the_escape_filter(self):
        assert "{{ h | e }}" in TEMPLATE
        for raw in ("{{ h }}", "{{ c.guest }}", "{{ c.identifier }}", "{{ c.cohost }}",
                    "{{ x.guest }}", "{{ x.identifier }}", "{{ ep.dek }}"):
            assert raw not in TEMPLATE, f"{raw} renders raw"
        assert 'with {{ c.guest | e }}"' in TEMPLATE, "the aria-label interpolation"

    def test_a_poisoned_also_in_this_episode_headline_is_escaped(self, tmp_path, monkeypatch):
        import generate_html as G
        from engine import landing_test as LT

        real_assemble = LT.assemble

        def poisoned(*args, **kwargs):
            page = real_assemble(*args, **kwargs)
            buckets = [page.get("lead")] + list(page.get("top") or []) + \
                list(page.get("latest") or []) + list(page.get("flagships") or [])
            for sec in page.get("sections") or []:
                buckets.extend(sec.get("stories") or [])
            seen = False
            for story in buckets:
                if story and story.get("post_url"):
                    story["more"] = [XSS]
                    seen = True
            if not seen:
                pytest.skip("no story with a post at the fixed clock")
            return page

        monkeypatch.setattr(LT, "assemble", poisoned)
        html = G.generate_network_page(output_dir=tmp_path, now=NOW).read_text(encoding="utf-8")
        assert XSS not in html
        assert XSS_ESCAPED in html


class TestHomepageRenderCost:
    def test_the_show_yaml_loaders_are_cached_for_the_process(self):
        import generate_html as G
        assert hasattr(G._registry_show_config, "cache_info")
        assert hasattr(G._listening_languages, "cache_info")

    def test_pick_videos_reads_the_builds_clock(self):
        assert "markets=None, now=None):" in GEN_HTML
        assert GEN_HTML.count("audience_order=order, now=now)") == 2
        assert "markets=markets, now=now)" in GEN_HTML


class TestRecordTimestampsAreAware:
    def test_publisher_and_edition_stamp_utc(self):
        pub = (ROOT / "engine" / "publisher.py").read_text(encoding="utf-8")
        assert "now = datetime.datetime.now(datetime.timezone.utc)" in pub
        ed = (ROOT / "scripts" / "build_daily_edition.py").read_text(encoding="utf-8")
        assert '"datetime": dt.datetime.now(dt.timezone.utc).isoformat()' in ed

    def test_newsroom_reads_an_aware_stamp(self):
        from engine import newsroom as N
        when = N._parse_iso(dt.datetime(2026, 10, 18, 12, 0, tzinfo=UTC).isoformat())
        assert when == dt.datetime(2026, 10, 18, 12, 0, tzinfo=UTC)


# --------------------------------------------------------------- worker --
class TestGalleryWorkerDeploys:
    def test_no_live_kv_binding_carries_a_placeholder_id(self):
        live = "\n".join(l for l in WRANGLER.splitlines() if not l.lstrip().startswith("#"))
        assert "PLACEHOLDER" not in live
        assert 'binding = "SUB_COUNTS"' not in live, "un-comment only with a real id"
        # The Worker tolerates the unbound namespace.
        ts = (ROOT / "workers" / "gallery" / "src" / "types.ts").read_text(encoding="utf-8")
        assert "SUB_COUNTS?: KVNamespace" in ts


# ------------------------------------------------------ retry stashes --
class TestStructuralRetryKeepsTheShippingDigestsStashes:
    def test_an_abandoned_thread_cannot_write_the_claims_stash(self):
        from engine import claims
        claims.restore_stashed_claims([{"id": "orig"}])
        box = {}

        def worker():
            setattr(threading.current_thread(), claims.ABANDONED_THREAD_ATTR, True)
            box["clean"] = claims.extract_and_stash(
                "Body.\n\n```claims\n[{\"id\": \"retry\", \"claim\": \"x\", \"url\": \"https://a\", \"supporting_quote\": \"x\"}]\n```\n")

        t = threading.Thread(target=worker)
        t.start(); t.join()
        assert "```claims" not in box["clean"]
        assert claims.drain_stashed_claims() == [{"id": "orig"}]

    def test_a_live_thread_still_writes_it(self):
        from engine import claims
        claims.restore_stashed_claims(None)
        claims.extract_and_stash(
            "Body.\n\n```claims\n[{\"id\": \"c1\", \"claim\": \"x\", \"url\": \"https://a\", \"supporting_quote\": \"x\"}]\n```\n")
        got = claims.drain_stashed_claims()
        assert got and got[0]["id"] == "c1"

    def test_the_deadline_marks_the_thread_it_abandons(self):
        import run_show
        from engine.claims import ABANDONED_THREAD_ATTR
        started = threading.Event()

        def slow():
            started.set()
            time.sleep(1.5)

        with pytest.raises(TimeoutError):
            run_show._call_with_deadline(slow, 0.2)
        started.wait(1)
        marked = [t for t in threading.enumerate()
                  if t.name == "deadline-call" and getattr(t, ABANDONED_THREAD_ATTR, False)]
        assert marked

    def test_combined_script_from_an_abandoned_thread_is_discarded(self):
        from engine import generator
        generator.restore_combined_script({"script": "orig", "digest": "d"})

        def worker():
            from engine.claims import ABANDONED_THREAD_ATTR
            setattr(threading.current_thread(), ABANDONED_THREAD_ATTR, True)
            generator._finish_combined_script("retry " * 400, "digest", object())

        t = threading.Thread(target=worker)
        t.start(); t.join()
        assert generator.take_combined_script() == {"script": "orig", "digest": "d"}

    def test_run_show_snapshots_before_and_restores_unless_accepted(self):
        i = RUN_SHOW.index("_pre_retry_claims = _stash_claims_mod.peek_stashed_claims()")
        block = RUN_SHOW[i:RUN_SHOW.index("# Blocking lints (Sep 24 2026)", i)]
        assert "_pre_retry_combined = _stash_gen_mod.snapshot_combined_script()" in block
        assert block.count("_retry_accepted = True") == 1
        assert "if not _retry_accepted:" in block
        assert "restore_stashed_claims(_pre_retry_claims)" in block
        assert "restore_combined_script(_pre_retry_combined)" in block
        # The accept path is the one that assigns the candidate.
        assert block.index("x_thread = _candidate") < block.index("_retry_accepted = True")


# --------------------------------------------------------------- chapters --
class TestChapterPassesShareOneFrame:
    def test_calculate_timestamps_gets_voice_intro_delay_only(self):
        i = RUN_SHOW.index("# 10a. Generate chapter data")
        block = RUN_SHOW[i:i + 2500]
        assert "music_intro_offset = float(config.audio.voice_intro_delay or 0.0)" in block
        assert "voice_intro_delay + config.audio.intro_duration" not in block


# -------------------------------------------------------------- video job --
class TestTheVideoJobSurvivesItsOwnFailures:
    def test_the_commit_step_runs_whatever_the_video_step_did(self):
        wf = yaml.safe_load(VIDEO_WF)
        steps = wf["jobs"]["render"]["steps"]
        commit = next(s for s in steps if s.get("id") == "commit")
        assert commit["if"].replace(" ", "") == "always()&&!inputs.rehearse"
        alert = next(s for s in steps if s.get("name") == "Alert on failure")
        assert "YouTube Studio" in alert["run"]

    def test_the_done_marker_is_written_before_the_x_stage(self):
        i = RUN_SHOW.index("def run_video_phase(")
        body = RUN_SHOW[i:RUN_SHOW.index("\ndef ", i + 10)]
        assert body.index("done.write_text(") < body.index("_run_x_stage(")
        assert "video_job_x_error" in body

    def test_an_x_failure_after_the_uploads_still_marks_the_video_done(self, tmp_path, monkeypatch):
        import run_show
        from engine.config import load_config
        from tests.test_video_job_2026_10_18 import _args

        real = load_config(ROOT / "shows" / "spacex.yaml")
        monkeypatch.setattr(run_show, "PROJECT_ROOT", tmp_path)
        monkeypatch.setattr("engine.config.load_config", lambda _p: real)
        out = tmp_path / real.episode.output_dir
        out.mkdir(parents=True)
        today = dt.date(2026, 10, 18)
        (out / "SpaceX_Ep140_20261018.md").write_text("# Digest\n\nBody.\n")
        (out / "SpaceX_Ep140_20261018.mp3").write_bytes(b"ID3")
        run_show._write_video_handoff(
            out, show_slug="spacex", episode_num=140, today=today,
            final_mp3=out / "SpaceX_Ep140_20261018.mp3",
            r2_audio_url="https://audio.example/x.mp3", rss_audio_url="", hook="Hook",
            title_hook="Hook", audio_duration=600.0,
            digest_md=out / "SpaceX_Ep140_20261018.md", extra_context={})

        def fake_video(**kw):
            kw["metrics"].record("youtube_short_uploaded", True)

        def failing_x(**kw):
            raise RuntimeError("X refused")

        monkeypatch.setattr(run_show, "_run_video_stage", fake_video)
        monkeypatch.setattr(run_show, "_run_x_stage", failing_x)
        monkeypatch.setattr("engine.tracking.save_usage", lambda tracker, d: None)
        run_show.run_video_phase(_args(video_phase=True, date="2026-10-18"))
        done = json.loads((out / ".video_done_20261018.json").read_text())
        assert done["short_uploaded"] is True
        assert not (out / ".video_pending_20261018.json").exists()
        m = json.loads((out / "metrics_ep140.json").read_text())
        assert m["counters"]["x_post_skipped"] == "video_job_x_error"
        assert m["counters"]["video_job"] == "rendered"

    def test_the_multilingual_cron_waits_for_a_running_video_job(self):
        assert "def video_pending_today(slug):" in ML_WF
        sched = ML_WF[ML_WF.index('# Scheduled / "all"'):]
        assert "video_pending_today(s)" in sched[:600]

    def test_a_refused_publish_at_is_named_never_any_400(self):
        i = RUN_SHOW.index("def _schedule_refused(")
        body = RUN_SHOW[i:i + 900]
        assert '"400"' not in body
        assert '"publishing time"' in body and '"publishat"' in body


class TestXQueueDuplicateLeavesNoOrphanMedia:
    def test_a_duplicate_row_forgets_the_copy_this_call_hosted(self, monkeypatch, tmp_path):
        from engine import x_queue
        clip = tmp_path / "clip.mp4"
        clip.write_bytes(b"0")
        forgotten = []
        monkeypatch.setattr(x_queue, "configured", lambda: True)
        monkeypatch.setattr(x_queue, "_host", lambda p, s: "https://x.example/x/clip.mp4")
        monkeypatch.setattr(x_queue, "_taken", lambda now: [])
        monkeypatch.setattr(x_queue, "slot_for", lambda *a, **k: dt.datetime(2026, 10, 19, 12, tzinfo=UTC))
        monkeypatch.setattr(x_queue, "_rest", lambda *a, **k: [])
        monkeypatch.setattr(x_queue, "_forget_media", lambda url: forgotten.append(url))
        ok, why = x_queue.enqueue(show_slug="tesla", episode_num=1, env_prefix="X_",
                                  text="t", media_path=str(clip), media_kind="clip")
        assert (ok, why) == (True, "already_queued")
        assert forgotten == ["https://x.example/x/clip.mp4"]

    def test_a_copy_the_caller_hosted_is_left_alone(self, monkeypatch):
        from engine import x_queue
        forgotten = []
        monkeypatch.setattr(x_queue, "configured", lambda: True)
        monkeypatch.setattr(x_queue, "_taken", lambda now: [])
        monkeypatch.setattr(x_queue, "slot_for", lambda *a, **k: dt.datetime(2026, 10, 19, 12, tzinfo=UTC))
        monkeypatch.setattr(x_queue, "_rest", lambda *a, **k: [])
        monkeypatch.setattr(x_queue, "_forget_media", lambda url: forgotten.append(url))
        x_queue.enqueue(show_slug="tesla", episode_num=1, env_prefix="X_", text="t",
                        media_url="https://x.example/x/pre.mp4")
        assert forgotten == []


# ---------------------------------------------------------- review agent --
class TestReviewAgentGitErrorsAreReadable:
    def test_a_failed_git_command_prints_its_stderr(self, capsys):
        sys.path.insert(0, str(ROOT / "scripts"))
        import run_show_review as R
        with pytest.raises(subprocess.CalledProcessError):
            R._git("rev-parse", "--verify", "refs/heads/no-such-branch-48h-review")
        out = capsys.readouterr().out
        assert "::warning::git rev-parse" in out and "fatal" in out

    def test_the_push_retries(self):
        src = (ROOT / "scripts" / "run_show_review.py").read_text(encoding="utf-8")
        i = src.index("def open_draft_pr(")
        body = src[i:src.index("\ndef ", i + 10)]
        assert "for _attempt in range(3):" in body
        assert '_git("push", "-u", "origin", branch)' in body


# ------------------------------------------------------------ topic queue --
class TestUCQueueAfterTheRestock:
    def test_the_duplicate_autopilot_topic_is_gone(self):
        q = yaml.safe_load((ROOT / "shows" / "topic_queues" / "unintended_consequences.yaml")
                           .read_text(encoding="utf-8"))["queue"]
        ids = [e["id"] for e in q]
        assert "the-autopilot-skills-fade-in" not in ids
        assert "aviation-automation-complacency" in ids

    def test_the_starling_brief_names_the_shakespeare_story_as_a_myth(self):
        q = yaml.safe_load((ROOT / "shows" / "topic_queues" / "unintended_consequences.yaml")
                           .read_text(encoding="utf-8"))["queue"]
        e = next(e for e in q if e["id"] == "the-european-starling-release-and")
        assert e.get("source_audit") == "fix"
        assert "SOURCE AUDIT (2026-10-18)" in e["brief"]
        assert "myth" in e["brief"]
        assert "to complete a Shakespearean aviary collection" not in e["brief"]


# ----------------------------------------------------- weekly segment --
class TestWeeklySegmentNamesPeopleAsTheCoverageDid:
    def test_the_instruction_carries_the_naming_rule(self):
        src = (ROOT / "engine" / "weekly_recap.py").read_text(encoding="utf-8")
        assert "a surname alone is" in src and "not a name" in src


# ------------------------------------------------------------ corrections --
class TestTheTwoCorrectionsFiled:
    @pytest.mark.parametrize("show_dir,episode,needle", [
        ("unintended_consequences", 146, "30 percent"),
        ("first_principles", 134, "battleship"),
    ])
    def test_filed_and_applied(self, show_dir, episode, needle):
        from engine.corrections import load_corrections
        rows = load_corrections(ROOT / "digests" / show_dir)
        row = next(r for r in rows if int(r.get("episode", 0)) == episode)
        assert row.get("date") == "2026-10-18" and row.get("where") == "both"
        md = next((ROOT / "digests" / show_dir).glob(f"*Ep{episode}_*.md"))
        text = md.read_text(encoding="utf-8")
        for rep in row.get("replacements") or []:
            assert rep["find"] not in text
        assert re.search(r"\b" + needle + r"\b", text) is None or needle == "30 percent" and "rose roughly 30 percent" not in text
