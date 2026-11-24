"""Pipeline hardening pass, Nov 24 2026.

Each class pins one defect read out of the Nov 14-24 workflow runs:

* the Daily Audit's retry dispatcher called a FRESH report stale whenever
  GitHub delivered the audit's cron after 00:00 UTC (Nov 10, 17 and 24);
* the PyAV requirement guard pinned an exact floor, so the weekly grouped
  Dependabot PR (#1739) went red on a patch bump inside the ceiling;
* a topic restock whose every candidate repeated the queue failed the night
  (Nov 14 and Nov 20) without trying once more.
"""
import datetime
import importlib.util
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
UTC = datetime.timezone.utc


def _load(name: str):
    spec = importlib.util.spec_from_file_location(f"_hardening_{name}", ROOT / "scripts" / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    # Registered before exec: a module that declares dataclasses under
    # ``from __future__ import annotations`` is looked up by name.
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class TestLateAuditIsNotAStaleReport:
    """``review_episodes`` dates its report by the Eastern day; a show run
    stamps its episode with the UTC date. The dispatcher needs both."""

    #: The Nov 24 run: started 02:52 UTC, wrote a report dated Nov 23.
    LATE = datetime.datetime(2026, 11, 24, 3, 7, tzinfo=UTC)

    def _run(self, tmp_path, monkeypatch, review, now):
        mod = _load("dispatch_audit_retries")
        path = tmp_path / "api" / "daily-review.json"
        path.parent.mkdir(parents=True)
        path.write_text(json.dumps(review))
        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("GH_TOKEN", "test-token")
        monkeypatch.delenv("NOTIFICATION_WEBHOOK_URL", raising=False)
        calls = []

        class _Result:
            stdout = ""
            stderr = ""

        def _fake_run(cmd, **kwargs):
            calls.append(list(cmd))
            return _Result()

        monkeypatch.setattr(mod.subprocess, "run", _fake_run)
        pages = []
        monkeypatch.setattr(mod, "_post_webhook", pages.append)
        mod.main(now=now)
        return [c for c in calls if c[:3] == ["gh", "workflow", "run"]], pages

    def test_verdicts(self):
        mod = _load("dispatch_audit_retries")
        assert mod.report_verdict("2026-11-24", self.LATE) == "fresh"
        assert mod.report_verdict("2026-11-23", self.LATE) == "late"
        assert mod.report_verdict("2026-11-22", self.LATE) == "stale"
        assert mod.report_verdict("", self.LATE) == "stale"
        # Mid-afternoon UTC the two calendars agree: yesterday is stale.
        noon = datetime.datetime(2026, 11, 24, 16, 15, tzinfo=UTC)
        assert mod.report_verdict("2026-11-24", noon) == "fresh"
        assert mod.report_verdict("2026-11-23", noon) == "stale"

    def test_the_audit_day_follows_the_audits_own_zone(self):
        """One zone, two files: a drift would reopen the false alarm."""
        mod = _load("dispatch_audit_retries")
        src = (ROOT / "review_episodes.py").read_text(encoding="utf-8")
        m = re.search(r'^NETWORK_TZ = ZoneInfo\("([^"]+)"\)', src, re.M)
        assert m and mod.NETWORK_TZ.key == m.group(1)

    def test_late_audit_with_nothing_to_retry_is_quiet(self, tmp_path, monkeypatch, capsys):
        dispatched, pages = self._run(
            tmp_path, monkeypatch,
            {"date": "2026-11-23", "remediation": {"auto_retry_shows": []}},
            self.LATE)
        out = capsys.readouterr().out
        assert dispatched == [] and pages == []
        assert "::warning::" not in out and "stale" not in out

    def test_late_audit_names_the_shows_it_could_not_retry(self, tmp_path, monkeypatch, capsys):
        dispatched, pages = self._run(
            tmp_path, monkeypatch,
            {"date": "2026-11-23",
             "remediation": {"auto_retry_shows": ["tesla", "spacex"]}},
            self.LATE)
        out = capsys.readouterr().out
        # Never dispatched: the run would be stamped Nov 24 and take that
        # day's slot through the same-day duplicate guard.
        assert dispatched == []
        assert "tesla, spacex" in out and "::warning::" in out
        assert "stale" not in out and "did not ship" not in out
        assert len(pages) == 1 and "tesla, spacex" in pages[0]

    def test_a_truly_stale_report_still_dispatches_nothing(self, tmp_path, monkeypatch, capsys):
        dispatched, pages = self._run(
            tmp_path, monkeypatch,
            {"date": "2026-11-21",
             "remediation": {"auto_retry_shows": ["tesla"]}},
            self.LATE)
        assert dispatched == [] and len(pages) == 1
        assert "stale" in capsys.readouterr().out

    def test_a_same_utc_day_report_still_dispatches(self, tmp_path, monkeypatch):
        now = datetime.datetime(2026, 11, 23, 21, 40, tzinfo=UTC)
        dispatched, _ = self._run(
            tmp_path, monkeypatch,
            {"date": "2026-11-23",
             "remediation": {"auto_retry_shows": ["tesla"]}},
            now)
        assert len(dispatched) == 1

    def test_a_show_run_still_stamps_the_utc_date(self):
        """The reason a late retry is refused. If the duplicate guard ever
        moves to the network's day, ``late`` can dispatch and this fails to
        say so."""
        wf = (ROOT / ".github/workflows/run-show.yml").read_text(encoding="utf-8")
        assert "TODAY=$(date -u +%Y%m%d)" in wf


class TestRequirementGuardsPinNoExactFloor:
    def test_the_pyav_guard_accepts_a_patch_bump_inside_the_ceiling(self):
        src = (ROOT / "tests/test_runner_upgrade_2026_10_09.py").read_text(encoding="utf-8")
        assert r"^av>=18\.1\.0,<19" not in src

    PINNED = re.compile(
        r'''["']\^[a-z][a-z0-9_-]*>=\d+(?:\\\.\d+)+(?:,<\d+)?(?:\\s\*)?\$["']''')

    def test_the_pattern_reads_the_line_that_failed(self):
        assert self.PINNED.search('re.search(r"^av>=18\\.1\\.0,<19\\s*$", req, re.M)')
        assert not self.PINNED.search('re.search(r"^av>=([\\d.]+),<19\\s*$", req, re.M)')

    def test_no_guard_pins_an_exact_requirement_line(self):
        """A guard on requirements.txt states a floor or a ceiling. One that
        spells a whole ``name>=x.y.z`` line with ``$`` after it turns the
        weekly Dependabot bump red (Oct 16: openai; Nov 24: av)."""
        found = {}
        for path in sorted((ROOT / "tests").glob("test_*.py")):
            if path.name == Path(__file__).name:
                continue
            src = path.read_text(encoding="utf-8")
            if "requirements.txt" in src and self.PINNED.search(src):
                found[path.name] = self.PINNED.findall(src)
        assert not found, found


class TestRestockTriesOnceMoreAfterAnAllRepeatsAnswer:
    """Nov 14 and Nov 20: 30 and 29 candidates, every one already queued."""

    QUEUE = [{"id": "cobra-effect", "title": "The Cobra Effect",
              "brief": "x" * 100, "category": "classic", "produced": False}]
    REPEAT = {"title": "The Cobra Effect", "brief": "b" * 120, "category": "classic"}
    NOVEL = {"title": "The Bridge That Moved the Traffic", "brief": "b" * 120,
             "category": "infrastructure"}

    def _run(self, tmp_path, monkeypatch, answers):
        import dataclasses

        import yaml
        rq = _load("restock_topic_queues")
        qf = tmp_path / "q.yaml"
        qf.write_text(yaml.safe_dump({"queue": list(self.QUEUE)}), encoding="utf-8")
        cfg = dataclasses.replace(rq.RESTOCK_CONFIGS["unintended_consequences"],
                                  queue_file=str(qf))
        prompts = []

        def fake_generate(prompt):
            prompts.append(prompt)
            return list(answers[len(prompts) - 1]), "stub"

        monkeypatch.setattr(rq, "ROOT", Path("/"))
        monkeypatch.setattr(rq, "build_prompt", lambda c, q, n, arm=None: "PROMPT")
        monkeypatch.setattr(rq, "generate_candidates", fake_generate)
        monkeypatch.setattr(rq, "ground_candidates", lambda entries, needed: entries[:needed])
        return rq, rq.restock_show(cfg, dry_run=True, force=False), prompts

    def test_an_all_repeats_answer_is_asked_again_once(self, tmp_path, monkeypatch):
        rq, result, prompts = self._run(
            tmp_path, monkeypatch, [[self.REPEAT], [self.NOVEL]])
        assert len(prompts) == 2
        assert prompts[0] == "PROMPT"
        assert prompts[1] == "PROMPT" + rq.REPEAT_RETRY_NOTE
        assert result["added"] == 1 and result["repeat_retry"] is True

    def test_it_never_asks_a_third_time(self, tmp_path, monkeypatch):
        _, result, prompts = self._run(
            tmp_path, monkeypatch, [[self.REPEAT], [self.REPEAT], [self.NOVEL]])
        assert len(prompts) == 2 and result["added"] == 0

    def test_a_usable_answer_costs_one_call(self, tmp_path, monkeypatch):
        _, result, prompts = self._run(tmp_path, monkeypatch, [[self.NOVEL]])
        assert len(prompts) == 1 and "repeat_retry" not in result

    def test_an_empty_answer_is_not_retried(self, tmp_path, monkeypatch):
        """No candidates at all is the model-fallback path's business."""
        _, result, prompts = self._run(tmp_path, monkeypatch, [[]])
        assert len(prompts) == 1 and result["added"] == 0

    def test_the_note_names_no_topic(self):
        rq = _load("restock_topic_queues")
        assert '"' not in rq.REPEAT_RETRY_NOTE and "\u201c" not in rq.REPEAT_RETRY_NOTE

    def test_one_shows_empty_night_does_not_discard_the_others_topics(self):
        import yaml
        wf = yaml.safe_load((ROOT / ".github/workflows/restock-topic-queues.yml")
                            .read_text(encoding="utf-8"))
        steps = wf["jobs"]["restock"]["steps"]
        by_id = {s.get("id"): s for s in steps if s.get("id")}
        assert "restock" in by_id and "continue-on-error" not in by_id["restock"]
        assert by_id["verify"]["if"] == "always() && steps.restock.outcome != 'skipped'"
        commit = next(s for s in steps if "safe-commit-push" in str(s.get("uses", "")))
        assert commit["if"] == "always() && steps.verify.outcome == 'success'"
        assert steps.index(by_id["verify"]) < steps.index(commit)


class TestTheAuditHasAnExactClockAndRunsOnce:
    """GitHub delivered the audit's 16:15 UTC cron at 20:40-02:52 UTC on
    every day from Nov 14 to Nov 24. The Worker dispatches it now; the gate
    keeps the late cron from auditing the day a second time."""

    TS = (ROOT / "workers/scheduler/src/index.ts").read_text(encoding="utf-8")
    NOON = datetime.datetime(2026, 11, 24, 16, 15, tzinfo=UTC)

    def _decide(self, **over):
        gate = _load("audit_gate")
        kw = dict(input_date="", input_show="", force=False,
                  report_date="2026-11-23", now=self.NOON)
        kw.update(over)
        return gate.decide(**kw)

    def test_the_worker_dispatches_the_audit_on_eastern_time(self):
        m = re.search(
            r'const AUDIT_DISPATCH = \{\s*tz: "([^"]+)",\s*time: \[(\d+), (\d+)\] as '
            r'\[number, number\],\s*workflow: "([\w.-]+)",', self.TS)
        assert m, "AUDIT_DISPATCH missing or reshaped"
        assert m.group(1) == "America/New_York" and m.group(4) == "daily-audit.yml"
        hour, minute = int(m.group(2)), int(m.group(3))
        # The one cron trigger is */5; and the audit reads a finished slate:
        # at least two hours after the last show slot.
        assert minute % 5 == 0
        slots = re.findall(r'^\s*\[(\d+),\s*(\d+),\s*"[a-z0-9_]+"', self.TS, re.M)
        assert slots
        last = max(int(h) * 60 + int(mi) for h, mi in slots)
        assert hour * 60 + minute >= last + 120
        assert (hour, minute) not in {(int(h), int(mi)) for h, mi in slots}

    def test_the_handler_fires_it_and_a_failure_skips_nothing_else(self):
        handler = self.TS[self.TS.index("async scheduled("):]
        at = handler.index('dispatchWorkflow(env, AUDIT_DISPATCH.workflow, {}, "daily-audit")')
        # Before the show-slot lookup, whose miss returns from the handler.
        assert at < handler.index("const slot = SLOTS.find(")
        block = handler[handler.rindex("try {", 0, at):handler.index("}", handler.index("catch", at))]
        assert "catch (e)" in block
        assert "audit_dispatch: AUDIT_DISPATCH" in self.TS

    def test_a_second_untargeted_run_on_the_same_network_day_is_skipped(self):
        run, reason = self._decide(report_date="2026-11-24")
        assert run is False and "already dated 2026-11-24" in reason

    def test_the_first_run_of_the_day_runs(self):
        assert self._decide(report_date="2026-11-23")[0] is True

    def test_the_day_is_the_networks_not_utc(self):
        """The late cron of Nov 24: 02:52 UTC is still Nov 23 in New York."""
        late = datetime.datetime(2026, 11, 24, 2, 52, tzinfo=UTC)
        assert self._decide(report_date="2026-11-23", now=late)[0] is False
        assert self._decide(report_date="2026-11-22", now=late)[0] is True

    def test_a_targeted_or_forced_run_always_runs(self):
        assert self._decide(report_date="2026-11-24", force=True)[0] is True
        assert self._decide(report_date="2026-11-24", input_show="tesla")[0] is True
        assert self._decide(report_date="2026-11-24", input_date="20261120")[0] is True

    def test_an_unreadable_report_means_run(self):
        assert self._decide(report_date=None)[0] is True

    def test_a_failed_read_is_none_never_a_date(self, monkeypatch):
        gate = _load("audit_gate")

        def boom(*a, **k):
            raise OSError("gh not found")
        monkeypatch.setattr(gate.subprocess, "run", boom)
        assert gate.read_report_date("o/r") is None

    def test_the_gate_and_the_audit_share_one_zone(self):
        gate = _load("audit_gate")
        src = (ROOT / "review_episodes.py").read_text(encoding="utf-8")
        m = re.search(r'^NETWORK_TZ = ZoneInfo\("([^"]+)"\)', src, re.M)
        assert m and gate.NETWORK_TZ.key == m.group(1)

    def test_the_workflow_runs_the_gate_first_and_fails_open(self):
        import yaml
        wf = yaml.safe_load((ROOT / ".github/workflows/daily-audit.yml")
                            .read_text(encoding="utf-8"))
        jobs = wf["jobs"]
        assert jobs["audit"]["needs"] == "once"
        assert jobs["audit"]["if"] == "always() && needs.once.outputs.run != 'false'"
        assert jobs["once"]["outputs"]["run"] == "${{ steps.gate.outputs.run }}"
        gate = next(s for s in jobs["once"]["steps"] if s.get("id") == "gate")
        assert gate["run"] == "python3 scripts/audit_gate.py"
        # The second run must WAIT for the first, or both read an old report.
        assert wf["concurrency"] == {"group": "daily-audit", "cancel-in-progress": False}
        on = wf.get("on") or wf.get(True)
        assert "force" in on["workflow_dispatch"]["inputs"]
        assert on["schedule"], "GitHub's cron stays as the fallback"

    def test_an_undeployed_audit_dispatch_is_named(self):
        from scripts.check_scheduler_deploy import missing_extra_dispatches
        assert missing_extra_dispatches({"slots": []}) == ["AUDIT_DISPATCH"]
        assert missing_extra_dispatches(
            {"audit_dispatch": {"workflow": "daily-audit.yml"}}) == []
        assert missing_extra_dispatches({}, source="const SLOTS = [];") == []


class TestTheSearchWindowFollowsTheShowsFetchLadder:
    """Offshore North skipped Nov 16 and Nov 23 as too thin. Its web search,
    the only route to half its sources, asked for "the last 24 hours" on a
    weekly show."""

    def test_run_show_passes_the_ladders_widest_window(self):
        src = (ROOT / "run_show.py").read_text(encoding="utf-8")
        call = src[src.index("web_articles = fetch_web_search_articles("):]
        call = call[:call.index(")\n") + 1]
        assert "window_hours=_search_window" in call
        assert 'getattr(config, "fetch_expansion_hours", None)' in src

    def test_only_a_show_with_its_own_ladder_is_asked_differently(self):
        """Every other show sends the request it sent before."""
        import yaml
        wide = {}
        for path in sorted((ROOT / "shows").glob("*.yaml")):
            if path.name.startswith("_"):
                continue
            data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
            ladder = data.get("fetch_expansion_hours") or []
            if ladder and max(ladder) > 24 and data.get("web_search_queries"):
                wide[path.stem] = max(ladder)
        assert wide == {"offshore_north": 168}, wide

    def test_the_default_request_is_unchanged_and_a_week_asks_for_seven_days(self, monkeypatch):
        import sys as _sys
        import types

        from engine import fetcher
        prompts = []
        fake = types.ModuleType("digests.xai_grok")

        def grok_generate_text(prompt=None, *a, **k):
            prompts.append(prompt if prompt is not None else k.get("prompt"))
            return "NO_RECENT_ARTICLES", {}
        fake.grok_generate_text = grok_generate_text
        monkeypatch.setitem(_sys.modules, "digests.xai_grok", fake)
        monkeypatch.setenv("GROK_API_KEY", "test")
        assert fetcher.fetch_web_search_articles(["imoca"]) == []
        assert fetcher.fetch_web_search_articles(["imoca"], window_hours=168) == []
        assert len(prompts) == 2 and all(isinstance(p, str) for p in prompts)
        assert "(last 24 hours)" in prompts[0] and "last 7 days" not in prompts[0]
        assert "(last 7 days)" in prompts[1] and "last 24 hours" not in prompts[1]
