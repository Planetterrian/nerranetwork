"""Drift guards for the July 2026 alerting + push-reliability wiring pass.

Pins the fixes for the silent failure modes found after the June 28 mass-
stranding incident:
  - run-show.yml passes NOTIFICATION_WEBHOOK_URL to the pipeline step
    (run_show.py:_alert_webhook) and the commit step
    (scripts/create_recovery_pr.sh stranded-episode alert) — both alerts read
    the var but the steps never supplied it.
  - The commit step's aggregate-exclusion restore is per-file (a multi-path
    `git checkout HEAD -- a b c` is all-or-nothing and silently no-ops when
    any one path is missing from HEAD).
  - nightly-maintenance commits api/daily-show-health.json (it was
    regenerated + discarded every night) and wires the health-check
    escalation webhook.
  - daily-audit persists api/daily-review.json via the safe-commit-push
    composite (the bare push from a job-start checkout never landed once).
  - dispatch_audit_retries skips shows stranded on same-day recovery/*
    branches (a re-run duplicates already-uploaded YouTube/R2 assets).
  - scripts/grok_show_check.py: garble pattern matches the garble (not the
    correct spelling), the severe word-count branch is reachable, and
    escalations post to the operator webhook.
"""

from __future__ import annotations

import datetime
import importlib.util
import sys
import types
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
WF = ROOT / ".github" / "workflows"


def _load_workflow(name: str) -> dict:
    return yaml.safe_load((WF / name).read_text(encoding="utf-8"))


def _step(workflow: dict, job: str, step_name: str) -> dict:
    steps = workflow["jobs"][job]["steps"]
    return next(s for s in steps if s.get("name") == step_name)


def _load_script(name: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


# ---------------------------------------------------------------------------
# run-show.yml
# ---------------------------------------------------------------------------


class TestRunShowAlertWiring:
    def test_commit_step_env_carries_webhook(self):
        """create_recovery_pr.sh reads NOTIFICATION_WEBHOOK_URL for its
        stranded-episode alert; without this env entry every stranded episode
        was silent (P0)."""
        step = _step(_load_workflow("run-show.yml"), "run", "Commit and push output")
        env = step.get("env") or {}
        assert env.get("NOTIFICATION_WEBHOOK_URL") == "${{ secrets.NOTIFICATION_WEBHOOK_URL }}"

    def test_pipeline_step_env_carries_webhook(self):
        """run_show.py:_alert_webhook (e.g. newsletter-failure alert) reads
        this from the process env."""
        step = _step(_load_workflow("run-show.yml"), "run", "Run show pipeline")
        env = step.get("env") or {}
        assert env.get("NOTIFICATION_WEBHOOK_URL") == "${{ secrets.NOTIFICATION_WEBHOOK_URL }}"

    def test_aggregate_exclusion_restore_is_per_file(self):
        """One `git checkout HEAD -- <file>` per aggregate: the multi-path
        form silently no-ops when any one path is absent from HEAD, leaving
        the tree dirty → the June 28 mass-stranding mode."""
        wf = (WF / "run-show.yml").read_text(encoding="utf-8")
        assert "for aggregate in blog.rss network.rss blog/index.html" in wf
        assert 'git checkout HEAD -- "$aggregate" 2>/dev/null || true' in wf
        assert "git checkout HEAD -- blog.rss network.rss blog/index.html" not in wf


# ---------------------------------------------------------------------------
# nightly-maintenance.yml
# ---------------------------------------------------------------------------


class TestNightlyHealthCheckWiring:
    def test_health_json_in_safe_commit_add_paths(self):
        """api/daily-show-health.json was regenerated nightly but never
        committed (last landed June 24) because add-paths omitted it (P0)."""
        wf = _load_workflow("nightly-maintenance.yml")
        steps = wf["jobs"]["generate-artifacts"]["steps"]
        composite = next(s for s in steps
                         if "safe-commit-push" in str(s.get("uses", "")))
        assert "api/daily-show-health.json" in composite["with"]["add-paths"]

    def test_health_check_step_carries_webhook(self):
        """The escalation POST in grok_show_check.py needs the webhook env."""
        step = _step(_load_workflow("nightly-maintenance.yml"),
                     "generate-artifacts", "Daily Show Health Check (Grok Tier 1)")
        env = step.get("env") or {}
        assert env.get("NOTIFICATION_WEBHOOK_URL") == "${{ secrets.NOTIFICATION_WEBHOOK_URL }}"


# ---------------------------------------------------------------------------
# daily-audit.yml
# ---------------------------------------------------------------------------


class TestDailyAuditPersist:
    def test_persist_uses_safe_commit_push_composite(self):
        """The bare `git push origin main || echo non-blocking` from a
        job-start checkout was always non-fast-forward on this push-busy
        repo — api/daily-review.json had ZERO commits ever (P2)."""
        wf = _load_workflow("daily-audit.yml")
        steps = wf["jobs"]["audit"]["steps"]
        composite = next(s for s in steps
                         if "safe-commit-push" in str(s.get("uses", "")))
        assert "api/daily-review.json" in composite["with"]["add-paths"]
        text = (WF / "daily-audit.yml").read_text(encoding="utf-8")
        assert "git push origin main || echo" not in text

    def test_contents_write_permission_for_persist(self):
        wf = _load_workflow("daily-audit.yml")
        assert wf["permissions"]["contents"] == "write"

    def test_remediation_step_carries_webhook(self):
        """dispatch_audit_retries.py alerts (instead of re-running) when a
        'missed' show is stranded on a same-day recovery branch."""
        step = _step(_load_workflow("daily-audit.yml"), "audit",
                     "Automated Remediation (retry missed shows using daily-review.json)")
        env = step.get("env") or {}
        assert env.get("NOTIFICATION_WEBHOOK_URL") == "${{ secrets.NOTIFICATION_WEBHOOK_URL }}"


# ---------------------------------------------------------------------------
# scripts/grok_show_check.py
# ---------------------------------------------------------------------------


class TestGrokShowCheck:
    def test_correct_hassabis_spelling_not_flagged(self):
        mod = _load_script("grok_show_check")
        result = mod.check_phonetic_garbles(
            "Demis Hassabis announced a new model today.", "")
        assert result["status"] == "ok", \
            "the CORRECT spelling 'Hassabis' must not be flagged as a garble"

    def test_hassabis_garble_form_is_flagged(self):
        mod = _load_script("grok_show_check")
        result = mod.check_phonetic_garbles(
            "Demis Hah-sah-biss announced a new model today.", "")
        assert result["status"] == "flagged"
        assert any(f["correct_form"] == "Hassabis" for f in result["findings"])

    def test_word_count_severe_branch_is_reachable(self):
        """< 0.9*floor must yield the significantly_short finding — the old
        (if < floor, elif < 0.9*floor) ordering made it dead code."""
        mod = _load_script("grok_show_check")
        result = mod.check_word_count("word " * 1000, "tesla")  # floor 2000
        types_found = [f["type"] for f in result["findings"]]
        assert types_found == ["significantly_short"]

    def test_word_count_mild_shortfall_still_flagged(self):
        mod = _load_script("grok_show_check")
        result = mod.check_word_count("word " * 1950, "tesla")  # 90-100% of floor
        types_found = [f["type"] for f in result["findings"]]
        assert types_found == ["below_target_length"]

    def test_escalation_webhook_no_op_when_unset(self, monkeypatch):
        mod = _load_script("grok_show_check")
        monkeypatch.delenv("NOTIFICATION_WEBHOOK_URL", raising=False)
        # Must not raise (and must not try to import/POST anything).
        mod._post_escalation_webhook(
            [{"slug": "tesla", "escalation_score": 0.8, "flagged_checks": ["chapters"]}],
            "20260701",
        )

    def test_escalation_webhook_posts_when_set(self, monkeypatch):
        mod = _load_script("grok_show_check")
        monkeypatch.setenv("NOTIFICATION_WEBHOOK_URL", "https://hooks.example/x")
        posted = {}

        def fake_post(url, json=None, timeout=None):
            posted.update(url=url, json=json, timeout=timeout)
            return types.SimpleNamespace(status_code=200)

        monkeypatch.setitem(sys.modules, "requests",
                            types.SimpleNamespace(post=fake_post))
        mod._post_escalation_webhook(
            [{"slug": "tesla", "escalation_score": 0.8, "flagged_checks": ["chapters"]}],
            "20260701",
        )
        assert posted["url"] == "https://hooks.example/x"
        assert "tesla" in posted["json"]["text"]
        assert posted["timeout"] == 15

    def test_escalation_threshold_matches_promised_value(self):
        # Commit 8ef49eef promised "score >0.6 triggers weekly Claude deep-dive".
        mod = _load_script("grok_show_check")
        assert mod.ESCALATION_THRESHOLD == 0.60


# ---------------------------------------------------------------------------
# scripts/dispatch_audit_retries.py
# ---------------------------------------------------------------------------


class TestAuditRetrySkipsStrandedEpisodes:
    NOW = datetime.datetime(2026, 7, 1, 17, 0, tzinfo=datetime.timezone.utc)

    def _mod_with_refs(self, monkeypatch, stdout: str):
        mod = _load_script("dispatch_audit_retries")

        class Proc:
            pass

        proc = Proc()
        proc.stdout = stdout
        proc.stderr = ""
        monkeypatch.setattr(mod.subprocess, "run", lambda cmd, **kw: proc)
        return mod

    def test_same_day_recovery_branch_detected(self, monkeypatch):
        today_epoch = int(datetime.datetime(
            2026, 7, 1, 9, 30, tzinfo=datetime.timezone.utc).timestamp())
        mod = self._mod_with_refs(
            monkeypatch,
            f"abc123\trefs/heads/recovery/tesla-12345-{today_epoch}\n",
        )
        branch = mod._same_day_recovery_branch("tesla", now=self.NOW)
        assert branch == f"recovery/tesla-12345-{today_epoch}"

    def test_old_recovery_branch_does_not_block_retry(self, monkeypatch):
        old_epoch = int(datetime.datetime(
            2026, 6, 25, 9, 30, tzinfo=datetime.timezone.utc).timestamp())
        mod = self._mod_with_refs(
            monkeypatch,
            f"abc123\trefs/heads/recovery/tesla-11111-{old_epoch}\n",
        )
        assert mod._same_day_recovery_branch("tesla", now=self.NOW) is None

    def test_unparseable_branch_suffix_is_ignored(self, monkeypatch):
        mod = self._mod_with_refs(
            monkeypatch, "abc123\trefs/heads/recovery/tesla-manual-rescue\n")
        assert mod._same_day_recovery_branch("tesla", now=self.NOW) is None

    def test_no_recovery_branches_means_no_skip(self, monkeypatch):
        mod = self._mod_with_refs(monkeypatch, "")
        assert mod._same_day_recovery_branch("tesla", now=self.NOW) is None

    def test_dispatch_loop_warns_and_skips_stranded_show(self, capsys, tmp_path, monkeypatch):
        import json as _json

        mod = _load_script("dispatch_audit_retries")
        (tmp_path / "api").mkdir()
        # date must be TODAY: the 2026-08-21 stale-report guard refuses to
        # dispatch from any other day's report before the stranded check runs.
        _today = datetime.datetime.now(datetime.timezone.utc).date().isoformat()
        (tmp_path / "api" / "daily-review.json").write_text(
            _json.dumps({"date": _today,
                         "remediation": {"auto_retry_shows": ["tesla"]}}),
            encoding="utf-8",
        )
        monkeypatch.chdir(tmp_path)  # main() reads api/daily-review.json from cwd
        monkeypatch.setenv("GH_TOKEN", "x")
        dispatched = []
        monkeypatch.setattr(
            mod, "_same_day_recovery_branch",
            lambda show, now=None: "recovery/tesla-12345-1751360000")
        monkeypatch.setattr(mod.subprocess, "run",
                            lambda cmd, **kw: dispatched.append(cmd))
        alerts = []
        monkeypatch.setattr(mod, "_post_webhook", lambda text: alerts.append(text))
        mod.main()
        out = capsys.readouterr().out
        assert "::warning::" in out and "STRANDED" in out
        assert not dispatched, "a stranded show must not be re-dispatched"
        assert alerts and "merge" in alerts[0]


# ---------------------------------------------------------------------------
# scripts/create_recovery_pr.sh
# ---------------------------------------------------------------------------


class TestRecoveryScript:
    SCRIPT = (ROOT / "scripts" / "create_recovery_pr.sh").read_text(encoding="utf-8")

    def test_no_duplicated_opening_echo(self):
        assert self.SCRIPT.count('echo "Opening draft recovery PR..."') == 1

    def test_reads_notification_webhook(self):
        # Sanity: the alert the run-show env wiring exists to feed.
        assert "NOTIFICATION_WEBHOOK_URL" in self.SCRIPT
