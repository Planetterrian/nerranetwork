"""Guards for the Oct 23 2026 slate review (docs/reviews/slate_review_2026_10_23.md)."""

import json
import re
import sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
COMPOSITE = (ROOT / ".github/actions/setup-python/action.yml").read_text(encoding="utf-8")
SETUP_FFMPEG = (ROOT / ".github/actions/setup-ffmpeg/action.yml").read_text(encoding="utf-8")
TEST_WF = (ROOT / ".github/workflows/test.yml").read_text(encoding="utf-8")


class TestTheMirrorIsTheLastResort:
    def test_system_packages_are_cached_per_runner_image(self):
        assert "actions/cache/restore@v6" in COMPOSITE
        assert "actions/cache/save@v6" in COMPOSITE
        assert "${ImageOS:-unknown}-${ImageVersion:-unknown}" in COMPOSITE
        # A hit installs the cached files with no download at all — through
        # dpkg since Oct 28 (apt's --no-download resolved against the image's
        # stale lists and fell back on every hit; tests/test_slate_2026_10_28.py).
        assert 'dpkg --force-confold -i "$APT_DEBS"/*.deb' in COMPOSITE
        assert "Dir::Cache::Archives=$APT_DEBS/" in COMPOSITE
        # Only a mirror install that downloaded something is saved.
        assert "steps.apt-install.outputs.source == 'mirror'" in COMPOSITE

    def test_a_stalled_mirror_falls_back_to_the_pinned_static_build(self):
        tag = re.search(r"BTBN_TAG: (autobuild-[\w-]+)", TEST_WF).group(1)
        asset = re.search(r"BTBN_ASSET: (\S+\.tar\.xz)", TEST_WF).group(1)
        for text in (COMPOSITE, SETUP_FFMPEG):
            assert tag in text and asset in text, "the fallback is the build CI tests on"
            assert "sha256sum -c -" in text
        assert '"${{ inputs.system-packages }}" != "ffmpeg"' in COMPOSITE, (
            "only ffmpeg has a static fallback; any other package still fails loudly")


class TestQueryStringsThatNameThePage:
    def test_identity_parameters_are_kept(self):
        from engine.content_tracker import _normalize_url_for_dedup as n
        a = n("https://journals.plos.org/plosone/article?id=10.1371/journal.pone.0049118")
        b = n("https://journals.plos.org/plosone/article?id=10.1371/journal.pone.0019069")
        assert a != b
        assert n("https://www.youtube.com/watch?v=AAA&feature=youtu.be") != n(
            "https://www.youtube.com/watch?v=BBB&feature=youtu.be")
        assert n("https://www.pib.gov.in/PressReleseDetailm.aspx?PRID=1592022") != n(
            "https://www.pib.gov.in/PressReleseDetailm.aspx?PRID=1575403")

    def test_tracking_parameters_still_merge(self):
        from engine.content_tracker import _normalize_url_for_dedup as n
        assert n("https://www.dw.com/en/x/a-79665338?maca=en-rss-1") == n(
            "https://www.dw.com/en/x/a-79665338?maca=en-rss-2") == "dw.com/en/x/a-79665338"
        assert n("https://example.com/story/?utm_source=x&utm_medium=y") == "example.com/story"


DIGEST = """# Show

> **The hook sentence about the first story here today**

### Top News

**1. First story headline about batteries: Outlet**
Body of the first story with enough words to count as an item.
Source: [ex](https://example.com/first-story)

**2. Second story headline about chips: Outlet**
Body of the second story with enough words to count as an item.
Source: [ex](https://example.com/second-story)
"""


class TestTheLakeKeepsItsStoryIds:
    def _lake(self, tmp_path):
        from engine import content_lake
        from engine.content_lake import EpisodeRecord, rebuild_story_ids, store_episode
        db = tmp_path / "lake.db"
        rec = EpisodeRecord(show_slug="demo", episode_num=7, date="2026-10-23", title="t",
                            hook="h", digest_md=DIGEST, podcast_script="", summary="",
                            headlines=[], source_urls=[], entities=[], topics=[],
                            word_count=10, show_name="Demo", language="en")
        store_episode(rec, db_path=db)
        rebuild_story_ids(db_path=db, since="2026-10-23")
        return content_lake, rec, db

    def test_a_restore_keeps_the_ids_it_did_not_change(self, tmp_path):
        content_lake, rec, db = self._lake(tmp_path)
        before = [i["story_id"] for i in content_lake.query_items("2026-10-23", "2026-10-23", db_path=db)]
        assert before and all(before)
        rec.podcast_script = "the script"
        content_lake.store_episode(rec, db_path=db)  # run_show's second write
        after = [i["story_id"] for i in content_lake.query_items("2026-10-23", "2026-10-23", db_path=db)]
        assert after == before

    def test_the_run_reassigns_ids_after_the_second_write(self):
        src = (ROOT / "run_show.py").read_text(encoding="utf-8")
        i = src.index("_lake_record.podcast_script = podcast_script")
        assert "_rebuild_ids(since=today.isoformat())" in src[i:i + 500]

    def test_an_article_aired_by_url_even_without_a_story_id(self, tmp_path):
        from engine import catalog
        content_lake, _rec, db = self._lake(tmp_path)
        conn = sqlite3.connect(db)
        conn.execute("UPDATE items SET story_id = NULL")
        conn.commit()
        conn.close()
        rows = catalog.article_rows(
            show_slug="demo", date="2026-10-23", db_path=db,
            fetched=[{"url": "https://www.example.com/first-story/", "title": "First story"},
                     {"url": "https://example.com/never-aired", "title": "Other"}],
            listed=[])
        aired = {r["url_key"]: r["aired"] for r in rows}
        assert aired == {"example.com/first-story": True, "example.com/never-aired": False}


class TestTheVideoSweepRetriesARunThatNeverRendered:
    def test_never_rendered(self):
        from scripts.video_job import RENDER_STEP, never_rendered
        died_in_setup = [{"steps": [{"name": "Checkout main", "conclusion": "success"},
                                    {"name": "Run ./.github/actions/setup-python", "conclusion": "failure"},
                                    {"name": RENDER_STEP, "conclusion": "skipped"}]}]
        assert never_rendered(died_in_setup)
        died_rendering = [{"steps": [{"name": RENDER_STEP, "conclusion": "failure"}]}]
        assert not never_rendered(died_rendering)

    def test_the_render_step_name_matches_the_workflow(self):
        from scripts.video_job import RENDER_STEP
        wf = (ROOT / ".github/workflows/render-video.yml").read_text(encoding="utf-8")
        assert f"- name: {RENDER_STEP}\n" in wf

    def test_plan_sweep_starts_a_retryable_handoff_once(self):
        from scripts.video_job import plan_sweep, run_title
        handoffs = [("first_principles", "2026-10-23", 300.0), ("uc", "2026-10-23", 300.0)]
        titles = {run_title("first_principles", "2026-10-23"), run_title("uc", "2026-10-23")}
        start, _ = plan_sweep(handoffs, titles,
                              retryable={run_title("first_principles", "2026-10-23")})
        assert start == [("first_principles", "2026-10-23")]

    def test_two_runs_or_a_live_run_are_never_retried(self):
        from scripts.video_job import retryable_titles

        class S:
            def get(self, *a, **k):
                class R:
                    def raise_for_status(self):
                        pass

                    def json(self):
                        return {"jobs": []}
                return R()
        runs = [{"id": 1, "display_title": "A", "status": "completed", "conclusion": "failure"},
                {"id": 2, "display_title": "A", "status": "completed", "conclusion": "failure"},
                {"id": 3, "display_title": "B", "status": "in_progress", "conclusion": None},
                {"id": 4, "display_title": "C", "status": "completed", "conclusion": "success"},
                {"id": 5, "display_title": "D", "status": "completed", "conclusion": "failure"}]
        assert retryable_titles(S(), "o/r", runs) == {"D"}


class TestMiraKnowsTheAccountIsEmpty:
    def _fire(self):
        import sys
        sys.path.insert(0, str(ROOT / "pipelines" / "voices"))
        import fire_interviews
        return fire_interviews

    def test_a_billing_stop_is_reported(self, monkeypatch):
        f = self._fire()
        monkeypatch.setenv("GROK_API_KEY", "k")

        class R:
            status_code = 403
            text = json.dumps({"error": "Your team x has either used all available credits "
                                        "or reached its monthly spending limit."})
        monkeypatch.setattr(f.requests, "post", lambda *a, **k: R())
        assert "spending limit" in f.xai_credit_stop()

    def test_any_other_failure_is_not(self, monkeypatch):
        f = self._fire()
        monkeypatch.setenv("GROK_API_KEY", "k")

        class R:
            status_code = 401
            text = "invalid api key"
        monkeypatch.setattr(f.requests, "post", lambda *a, **k: R())
        assert f.xai_credit_stop() == ""

    def test_the_t_minus_two_reminder_checks(self):
        src = (ROOT / "pipelines/voices/fire_interviews.py").read_text(encoding="utf-8")
        body = src[src.index("def send_reminders"):src.index("def fire_due_interviews")]
        assert "stop = xai_credit_stop()" in body and "credit_alert(" in body


class TestTheAccountIsOnWorkersPaid:
    def test_no_surface_says_the_account_is_on_workers_free(self):
        for rel in ("CLAUDE.md", "workers/scheduler/wrangler.toml", "workers/scheduler/README.md",
                    "workers/voices/wrangler.toml", "workers/voices/src/index.ts",
                    "docs/nerra_daily.md"):
            text = (ROOT / rel).read_text(encoding="utf-8")
            assert "account is on Workers Free" not in text, rel
            assert "account is on the Workers Free" not in text, rel
        assert "Workers Paid now" in (ROOT / "CLAUDE.md").read_text(encoding="utf-8")


class TestReRunsWait:
    """Ep064 (Oct 23) shipped 6 of 15 segments: the first re-run to land woke
    the gate after the hold and it built while nine re-runs were generating."""

    DAY = __import__("datetime").date(2026, 10, 23)

    def _hold(self):
        from engine.daily_edition import release_window
        return release_window(self.DAY)[1]

    def _run(self, show, *, created, wake="queued", status="in_progress"):
        steps = [{"name": "Run show pipeline", "status": "in_progress"},
                 {"name": "Wake the Nerra Daily gate", "status": wake}]
        return {"status": status, "created_at": created,
                "jobs": [{"name": "gate", "status": "completed", "steps": []},
                         {"name": f"run ({show})", "status": status, "steps": steps}]}

    def test_the_oct_23_replay_waits_for_the_running_shows(self):
        import datetime as dt
        from engine.daily_edition import rerunning_shows
        now = dt.datetime(2026, 10, 23, 14, 46, 30, tzinfo=dt.timezone.utc)
        missing = ["spacex", "tesla", "models_agents", "omni_view", "mag7",
                   "modern_investing", "omni_view_world", "prediction_markets"]
        runs = [self._run(s, created="2026-10-23T14:29:00Z")
                for s in missing if s != "prediction_markets"]
        # The run that woke the gate is at its own wake step: it is not waited for.
        runs.append(self._run("prediction_markets", created="2026-10-23T14:31:00Z",
                              wake="in_progress"))
        got = rerunning_shows(runs, missing, hold_until=self._hold(), now_utc=now)
        assert "prediction_markets" not in got
        assert set(got) == set(missing) - {"prediction_markets"}

    def test_what_is_never_waited_for(self):
        import datetime as dt
        from engine.daily_edition import rerunning_shows
        now = dt.datetime(2026, 10, 23, 14, 0, tzinfo=dt.timezone.utc)
        hold = self._hold()
        straggler = self._run("tesla", created="2026-10-23T10:10:00Z")   # before the hold
        landed = self._run("spacex", created="2026-10-23T13:00:00Z")     # not missing
        stale = self._run("mag7", created="2026-10-23T10:55:00Z")        # older than 3 h
        done = self._run("omni_view", created="2026-10-23T13:00:00Z", status="completed")
        no_job = {"status": "in_progress", "created_at": "2026-10-23T13:30:00Z",
                  "jobs": [{"name": "gate", "status": "in_progress"}]}
        got = rerunning_shows([straggler, landed, stale, done, no_job],
                              ["tesla", "mag7", "omni_view"], hold_until=hold, now_utc=now)
        assert got == []

    def test_the_rule_waits_only_past_the_hold_and_only_while_incomplete(self):
        import datetime as dt
        from engine.daily_edition import ready_decision
        hold = self._hold()
        after = hold + dt.timedelta(hours=4)
        kw = dict(target_date=self.DAY, expected=15, skipped=0, min_segments=4)
        assert ready_decision(now_utc=after, landed=6, rerunning=["spacex"], **kw)[0] == "wait"
        assert ready_decision(now_utc=after, landed=6, rerunning=[], **kw)[0] == "build"
        assert ready_decision(now_utc=after, landed=15, rerunning=["spacex"], **kw)[0] == "build"

    def test_the_gate_reads_runs_with_the_workflow_token_and_fails_open(self, monkeypatch):
        import datetime as dt
        import scripts.build_daily_edition as b
        monkeypatch.delenv("GH_TOKEN", raising=False)
        monkeypatch.delenv("GITHUB_TOKEN", raising=False)
        now = dt.datetime(2026, 10, 23, 14, 0, tzinfo=dt.timezone.utc)
        assert b._rerunning_after_hold(["spacex"], self.DAY, now) == []
        wf = (ROOT / ".github/workflows/nerra-daily.yml").read_text(encoding="utf-8")
        assert "actions: read" in wf and "GH_TOKEN: ${{ github.token }}" in wf

    def test_every_show_run_wakes_the_gate_from_the_step_the_gate_reads(self):
        from engine.daily_edition import RUN_SHOW_JOB_PREFIX, WAKE_STEP
        wf = (ROOT / ".github/workflows/run-show.yml").read_text(encoding="utf-8")
        i = wf.index(f"- name: {WAKE_STEP}\n")
        assert "if: always()" in wf[i:i + 900], "a failed re-run must still wake the gate"
        assert RUN_SHOW_JOB_PREFIX == "run (" and "\n  run:\n" in wf
