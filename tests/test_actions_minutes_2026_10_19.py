"""Actions minutes (Oct 19 2026): the "is there work" decision leaves the runner.

Measured Oct 16-18: ~1,790 runner-minutes a day, of which ~460 were jobs
starting Python to decide there was nothing to do — the multilingual sweep
and the Nerra Daily gate woke on EVERY Run Podcast Show completion, the
producer tick dispatched a Gmail read every half hour, and the full test
suite ran on every pipeline push to main. What binds now:

* multilingual.yml and nerra-daily.yml have no ``workflow_run`` trigger;
  ``scripts/followup_dispatch.py`` decides from the show run (and the video
  job) and dispatches for ONE show; its decisions are pure and tested here;
* a single-show multilingual dispatch answers without a checkout;
* the Voices Worker's producer tick asks Gmail before it dispatches,
  fail-open, with the live-interview tick untouched;
* test.yml / e2e.yml skip a push that changes only generated output, and
  never filter pull requests.
"""
from __future__ import annotations

import datetime as dt
import json
import sys
import types
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

import followup_dispatch as fd  # noqa: E402
from engine import daily_edition as D  # noqa: E402

UTC = dt.timezone.utc


def _cfg(enabled=True, auto=True, mode="public"):
    return types.SimpleNamespace(
        multilingual=types.SimpleNamespace(enabled=enabled, auto=auto),
        access=types.SimpleNamespace(mode=mode),
    )


class TestMultilingualDecision:
    TODAY = dt.date(2026, 10, 19)

    def _published(self, tmp_path):
        (tmp_path / f"show_{self.TODAY:%Y%m%d}.md").write_text("# ep")
        return tmp_path

    def test_published_auto_show_dispatches(self, tmp_path):
        go, why = fd.multilingual_decision(_cfg(), self._published(tmp_path), self.TODAY)
        assert go, why

    def test_no_episode_today_skips(self, tmp_path):
        go, why = fd.multilingual_decision(_cfg(), tmp_path, self.TODAY)
        assert not go and "no episode" in why

    def test_not_automatic_skips(self, tmp_path):
        out = self._published(tmp_path)
        assert not fd.multilingual_decision(_cfg(auto=False), out, self.TODAY)[0]
        assert not fd.multilingual_decision(_cfg(enabled=False), out, self.TODAY)[0]

    def test_members_only_skips(self, tmp_path):
        go, why = fd.multilingual_decision(_cfg(mode="members_only"),
                                           self._published(tmp_path), self.TODAY)
        assert not go and "members-only" in why

    def test_video_pending_waits_for_the_video_job(self, tmp_path):
        out = self._published(tmp_path)
        (out / f".video_pending_{self.TODAY:%Y%m%d}.json").write_text("{}")
        go, why = fd.multilingual_decision(_cfg(), out, self.TODAY)
        assert not go and "video job" in why
        # The video job's own dispatch, and a finished video, both go.
        assert fd.multilingual_decision(_cfg(), out, self.TODAY, after_video=True)[0]
        (out / f".video_done_{self.TODAY:%Y%m%d}.json").write_text("{}")
        assert fd.multilingual_decision(_cfg(), out, self.TODAY)[0]


class TestEditionDecision:
    SPEC = D.EDITIONS["en"]
    MONDAY = dt.date(2026, 10, 19)

    def _root(self, tmp_path, published=False):
        d = tmp_path / self.SPEC.digest_dir
        d.mkdir(parents=True, exist_ok=True)
        rows = [{"date": self.MONDAY.isoformat()}] if published else []
        (d / f"summaries_{self.SPEC.slug}.json").write_text(json.dumps({"summaries": rows}))
        return tmp_path

    def test_before_the_release_nothing_wakes_the_gate(self, tmp_path):
        release, _ = D.release_window(self.MONDAY)
        go, why = fd.edition_decision(self.SPEC, self._root(tmp_path), "tesla",
                                      release - dt.timedelta(minutes=30))
        assert not go and "Worker" in why

    def test_a_straggler_after_the_release_wakes_it(self, tmp_path):
        release, hold = D.release_window(self.MONDAY)
        assert fd.edition_decision(self.SPEC, self._root(tmp_path), "tesla",
                                   release + dt.timedelta(minutes=5))[0]
        # And a re-run after a failed morning, past the hold, too.
        assert fd.edition_decision(self.SPEC, self._root(tmp_path), "tesla",
                                   hold + dt.timedelta(hours=2))[0]

    def test_a_published_edition_is_never_rebuilt(self, tmp_path):
        release, _ = D.release_window(self.MONDAY)
        go, why = fd.edition_decision(self.SPEC, self._root(tmp_path, published=True),
                                      "tesla", release + dt.timedelta(minutes=5))
        assert not go and "already published" in why

    def test_a_show_off_the_roster_never_wakes_it(self, tmp_path):
        release, _ = D.release_window(self.MONDAY)
        go, why = fd.edition_decision(self.SPEC, self._root(tmp_path), "vancouver",
                                      release + dt.timedelta(minutes=5))
        assert not go and "roster" in why
        # A Monday-only show on a Tuesday is off the roster too.
        tuesday = self.MONDAY + dt.timedelta(days=1)
        rel_tue, _ = D.release_window(tuesday)
        assert not fd.edition_decision(self.SPEC, self._root(tmp_path), "dp_pod",
                                       rel_tue + dt.timedelta(minutes=5), tuesday)[0]

    def test_the_summaries_path_is_the_real_one(self):
        assert (ROOT / self.SPEC.digest_dir / f"summaries_{self.SPEC.slug}.json").is_file()


class TestWorkflowWiring:
    def _wf(self, name):
        return (ROOT / ".github" / "workflows" / name).read_text(encoding="utf-8")

    def test_run_show_dispatches_both_followups(self):
        text = self._wf("run-show.yml")
        assert "name: Start the multilingual sweep" in text
        assert "name: Wake the Nerra Daily gate" in text
        # The edition wake-up runs after success, failure AND skip.
        i = text.index("name: Wake the Nerra Daily gate")
        block = text[i:i + 1200]
        assert "if: always() && github.event.inputs.test_mode != 'true'" in block
        assert "actions: write" in text

    def test_video_job_dispatches_after_the_manifest_push(self):
        text = self._wf("render-video.yml")
        i = text.index("bash scripts/push_regenerable.sh")
        assert "followup_dispatch.py multilingual" in text[i:]

    def test_no_workflow_run_fanout_remains(self):
        for name in ("multilingual.yml", "nerra-daily.yml"):
            wf = yaml.safe_load(self._wf(name))
            on = wf.get("on") or wf.get(True)
            assert "workflow_run" not in on, name
            assert "schedule" in on and "workflow_dispatch" in on, name

    def test_nerra_daily_job_has_no_trigger_conclusion_gate(self):
        wf = yaml.safe_load(self._wf("nerra-daily.yml"))
        assert "if" not in wf["jobs"]["build"]

    def test_multilingual_single_show_path_validates_the_slug(self):
        text = self._wf("multilingual.yml")
        assert '[[ ! "$SHOW" =~ ^[a-z0-9_]+$ ]]' in text


class TestTestWorkflowsSkipGeneratedPushes:
    GENERATED = ["digests/**", "blog/**", "api/**", "site/data/**", "*.rss", "*.html",
                 "claims/**", "topics/**", "ru/**", "fr/**", "sitemap.xml", "specials/**"]

    def _on(self, name):
        wf = yaml.safe_load((ROOT / ".github" / "workflows" / name).read_text(encoding="utf-8"))
        return wf.get("on") or wf.get(True)

    def test_push_ignores_generated_output_only(self):
        for name in ("test.yml", "e2e.yml"):
            on = self._on(name)
            ignore = on["push"]["paths-ignore"]
            for pattern in self.GENERATED:
                assert pattern in ignore, (name, pattern)
            # Code, prompts, show config, templates, workflows and the tests
            # themselves are never ignored.
            for code in ("engine/**", "scripts/**", "shows/**", "templates/**",
                         "tests/**", ".github/**", "run_show.py", "generate_html.py",
                         "workers/**", "pipelines/**"):
                assert code not in ignore, (name, code)
            assert "paths-ignore" not in on["pull_request"], name
            assert "paths" not in on["pull_request"], name


class TestProducerTickGate:
    TS = (ROOT / "workers" / "voices" / "src" / "index.ts").read_text(encoding="utf-8")

    def test_the_half_hour_tick_asks_gmail_first(self):
        i = self.TS.index("if (halfHour) {")
        block = self.TS[i:i + 700]
        assert "if (await producerTickDue(env))" in block
        assert 'dispatch(env, "producer-tick", { source: "voices-worker-cron" })' in block

    def test_the_gate_runs_the_inbox_jobs_own_query(self):
        from pipelines.producer import gmail_client as gc
        from pipelines.producer.policy import _DEFAULTS
        assert gc.PROCESSED_LABEL == "Producer/Processed"
        expected = f"-label:{gc.PROCESSED_LABEL} {_DEFAULTS['inbox_query']}"
        assert f'const PRODUCER_INBOX_QUERY = "{expected}";' in self.TS
        # The scope the delegation already grants, never a new one.
        assert f'const GMAIL_SCOPE = "{gc.SCOPES[0]}"' in self.TS

    def test_fail_open_everywhere(self):
        i = self.TS.index("async function producerTickDue(")
        body = self.TS[i:i + 900]
        assert "return true;  // not configured" in body
        assert 'console.error("producer-tick gate failed (dispatching anyway):"' in body

    def test_the_live_interview_tick_is_not_gated(self):
        assert ('if (await interviewIsLive(env)) await dispatch(env, "producer-tick", '
                '{ source: "live-interview" });') in self.TS

    def test_secrets_are_documented_as_optional(self):
        readme = (ROOT / "workers" / "voices" / "README.md").read_text(encoding="utf-8")
        assert "wrangler secret put GMAIL_SERVICE_ACCOUNT_JSON" in readme
        assert "wrangler secret put GMAIL_DELEGATED_USER" in readme
