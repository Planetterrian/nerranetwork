"""Drift guards for P3 operational hygiene (July 28 2026).

Three scheduled-maintenance gaps, plus two plan items that turned out to
be already done:

  * ``scripts/prune_video_r2.py`` existed but was scheduled nowhere, so
    the video keyspace grew ~318 GB/year unchecked.
  * ``recovery/*`` branches were never cleaned up — and an UNMERGED one
    is a stranded episode (generated, paid for, never published) that
    nothing was watching for.
  * The Apple Reporter token expires after 180 days and its failure mode
    is silent by design, so a dead token produced a green nightly job.

Already resolved, verified rather than assumed: the repo-root strays
(``_to_delete/``, ``recovered_ep519/``, ``recovered_spacex_ep12/``) are
gone, and the ruff gate is green.
"""

from __future__ import annotations

import datetime as dt
import json
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

REPO_ROOT = Path(__file__).resolve().parent.parent

from check_apple_reporter_freshness import check as reporter_check  # noqa: E402
import prune_recovery_branches as prb  # noqa: E402


class TestRepoRootIsClean:
    @pytest.mark.parametrize(
        "stray", ["_to_delete", "recovered_ep519", "recovered_spacex_ep12"])
    def test_stray_directories_are_gone(self, stray):
        assert not (REPO_ROOT / stray).exists()

    @pytest.mark.parametrize(
        "stray", ["_to_delete", "recovered_ep519", "recovered_spacex_ep12"])
    def test_strays_are_not_tracked(self, stray):
        tracked = subprocess.run(
            ["git", "ls-files", stray], cwd=REPO_ROOT,
            capture_output=True, text=True,
        ).stdout.strip()
        assert tracked == ""


class TestStoragePruneScheduled:
    @pytest.fixture()
    def workflow(self):
        path = REPO_ROOT / ".github" / "workflows" / "storage-prune.yml"
        assert path.exists(), "the monthly prune workflow must exist"
        return yaml.safe_load(path.read_text(encoding="utf-8"))

    def test_runs_on_a_monthly_cron(self, workflow):
        # PyYAML parses a bare `on:` key as the boolean True.
        triggers = workflow.get("on") or workflow.get(True)
        crons = [s["cron"] for s in triggers["schedule"]]
        assert crons, "no schedule configured"
        # day-of-month set, month wildcard => monthly.
        day_of_month = crons[0].split()[2]
        assert day_of_month != "*", f"not monthly: {crons[0]}"

    def test_manual_runs_default_to_a_dry_run(self, workflow):
        """Irreversible deletion must not be the default for a human."""
        triggers = workflow.get("on") or workflow.get(True)
        assert triggers["workflow_dispatch"]["inputs"]["apply"]["default"] is False

    def test_scheduled_run_actually_applies(self):
        """A prune that never deletes would leave the growth unfixed."""
        raw = (REPO_ROOT / ".github" / "workflows" / "storage-prune.yml").read_text(
            encoding="utf-8")
        assert "github.event_name == 'schedule' && 'true'" in raw
        assert "--apply" in raw

    def test_missing_credentials_skip_rather_than_fail(self):
        raw = (REPO_ROOT / ".github" / "workflows" / "storage-prune.yml").read_text(
            encoding="utf-8")
        assert "R2 credentials not configured" in raw

    def test_report_reaches_the_job_summary(self):
        """A destructive job with no audit trail is how bad prunes hide."""
        raw = (REPO_ROOT / ".github" / "workflows" / "storage-prune.yml").read_text(
            encoding="utf-8")
        assert "GITHUB_STEP_SUMMARY" in raw

    def test_does_not_race_the_daily_slate(self, workflow):
        """Shows finish as late as ~16:00; nightly runs 16:45."""
        triggers = workflow.get("on") or workflow.get(True)
        hour = int(triggers["schedule"][0]["cron"].split()[1])
        assert hour < 4 or 4 <= hour <= 6, f"hour {hour} risks overlapping a publish"


class TestRecoveryBranchJanitor:
    def test_unmerged_branches_are_never_deleted(self):
        """Deleting a stranded episode is the failure this prevents."""
        source = (REPO_ROOT / "scripts" / "prune_recovery_branches.py").read_text(
            encoding="utf-8")
        delete_block = source.split("if not args.apply:")[1]
        # The only iteration that deletes is over `merged`.
        assert "for branch in merged:" in delete_block
        assert "for branch in stranded:" not in delete_block

    def test_unresolvable_ref_is_treated_as_unmerged(self, monkeypatch):
        def _boom(*args, **kwargs):
            raise subprocess.CalledProcessError(1, "git")
        monkeypatch.setattr(prb, "_git", _boom)
        assert prb.is_merged("recovery/tesla-1-2", "origin/main") is False

    def test_age_read_from_the_branch_name(self):
        now = dt.datetime(2026, 7, 28, 12, 0, tzinfo=dt.timezone.utc)
        created = now - dt.timedelta(hours=30)
        branch = f"recovery/tesla-30353150739-{int(created.timestamp())}"
        age = prb.branch_age_hours(branch, now)
        assert age == pytest.approx(30.0, abs=0.1)

    def test_show_name_recovered_from_the_branch(self):
        assert prb.show_of("recovery/spacex-30354757421-1785247730") == "spacex"
        # Multi-part slugs survive the split.
        assert prb.show_of("recovery/models_agents-1-2") == "models_agents"

    def test_stranded_branch_emits_a_warning(self, monkeypatch, capsys):
        now = dt.datetime.now(dt.timezone.utc)
        created = int((now - dt.timedelta(hours=48)).timestamp())
        branch = f"recovery/tesla-999-{created}"
        monkeypatch.setattr(prb, "remote_recovery_branches", lambda: [branch])
        monkeypatch.setattr(prb, "is_merged", lambda b, base: False)

        prb.main([])
        out = capsys.readouterr().out
        assert "::warning::" in out
        assert "Stranded recovery branch" in out
        assert "tesla" in out

    def test_young_unmerged_branch_is_not_alarmed(self, monkeypatch, capsys):
        """An in-flight recovery PR is normal, not an incident."""
        now = dt.datetime.now(dt.timezone.utc)
        created = int((now - dt.timedelta(hours=2)).timestamp())
        monkeypatch.setattr(
            prb, "remote_recovery_branches",
            lambda: [f"recovery/tesla-999-{created}"])
        monkeypatch.setattr(prb, "is_merged", lambda b, base: False)

        prb.main([])
        out = capsys.readouterr().out
        assert "::warning::" not in out
        assert "in flight" in out

    def test_no_branches_is_a_clean_noop(self, monkeypatch, capsys):
        monkeypatch.setattr(prb, "remote_recovery_branches", lambda: [])
        assert prb.main([]) == 0
        assert "nothing to do" in capsys.readouterr().out

    def test_wired_into_nightly(self):
        raw = (REPO_ROOT / ".github" / "workflows"
               / "nightly-maintenance.yml").read_text(encoding="utf-8")
        assert "prune_recovery_branches.py" in raw
        assert "--apply" in raw

    def test_merged_branch_is_decidable_in_a_shallow_clone(
            self, tmp_path, monkeypatch):
        """Nightly runs the janitor in a fetch-depth:1 checkout. With
        only main's tip local, ``merge-base --is-ancestor`` is false for
        every branch merged before that tip — every merged branch would
        be misclassified unmerged and eventually announced as a stranded
        episode. ``ensure_ancestry_provable`` deepens main (bounded by
        the branch-name timestamp) so the check becomes decidable."""
        def git(*args, cwd):
            return subprocess.run(
                ["git", *args], cwd=str(cwd), check=True,
                capture_output=True, text=True).stdout.strip()

        seed = tmp_path / "seed"
        seed.mkdir()
        git("init", "--initial-branch=main", cwd=seed)
        git("config", "user.email", "t@example.com", cwd=seed)
        git("config", "user.name", "T", cwd=seed)
        (seed / "a.txt").write_text("base\n")
        git("add", "-A", cwd=seed)
        git("commit", "-m", "base", cwd=seed)

        now = dt.datetime.now(dt.timezone.utc)
        branch = f"recovery/tesla-999-{int(now.timestamp())}"
        git("checkout", "-b", branch, cwd=seed)
        (seed / "ep.txt").write_text("episode\n")
        git("add", "-A", cwd=seed)
        git("commit", "-m", "recovered episode", cwd=seed)
        git("checkout", "main", cwd=seed)
        git("merge", "--no-ff", "-m", "merge recovery", branch, cwd=seed)
        (seed / "later.txt").write_text("later\n")
        git("add", "-A", cwd=seed)
        git("commit", "-m", "later main commit", cwd=seed)

        origin = tmp_path / "origin.git"
        subprocess.run(
            ["git", "init", "--bare", "--initial-branch=main", str(origin)],
            check=True, capture_output=True)
        git("remote", "add", "origin", str(origin), cwd=seed)
        git("push", "origin", "main", branch, cwd=seed)

        # file:// forces the wire protocol so --depth is honoured.
        clone = tmp_path / "shallow"
        subprocess.run(
            ["git", "clone", "--depth", "1", f"file://{origin}",
             str(clone)], check=True, capture_output=True)
        git("fetch", "--depth=1", "origin",
            f"refs/heads/{branch}:refs/remotes/origin/{branch}", cwd=clone)

        monkeypatch.chdir(clone)
        # The bug: undecidable before deepening.
        assert prb.is_merged(branch, "origin/main") is False
        prb.ensure_ancestry_provable([branch], now)
        assert prb.is_merged(branch, "origin/main") is True

    def test_a_failed_deepen_does_not_alarm_on_its_own(
            self, monkeypatch, capsys):
        """CI checks out shallow, so the deepen runs — and when it cannot
        succeed there, a standalone ``::warning::`` turned every quiet run
        into a red one. The caveat belongs on the stranded alarm, not on
        its own line: an internal git optimisation failing is not an
        operator action."""
        now = dt.datetime.now(dt.timezone.utc)
        created = int((now - dt.timedelta(hours=2)).timestamp())
        monkeypatch.setattr(
            prb, "remote_recovery_branches",
            lambda: [f"recovery/tesla-999-{created}"])
        monkeypatch.setattr(prb, "is_merged", lambda b, base: False)
        monkeypatch.setattr(prb, "ensure_ancestry_provable",
                            lambda branches, now: False)

        prb.main([])
        out = capsys.readouterr().out
        assert "::warning::" not in out
        assert "in flight" in out

    def test_an_undecidable_ancestry_caveats_the_stranded_alarm(
            self, monkeypatch, capsys):
        """When a branch IS alarmed and ancestry could not be proven, say
        so — otherwise the operator chases an episode that shipped."""
        now = dt.datetime.now(dt.timezone.utc)
        created = int((now - dt.timedelta(hours=48)).timestamp())
        monkeypatch.setattr(
            prb, "remote_recovery_branches",
            lambda: [f"recovery/tesla-999-{created}"])
        monkeypatch.setattr(prb, "is_merged", lambda b, base: False)
        monkeypatch.setattr(prb, "ensure_ancestry_provable",
                            lambda branches, now: False)

        prb.main([])
        out = capsys.readouterr().out
        assert "::warning::Stranded recovery branch" in out
        assert "could not be deepened" in out

    def test_full_clone_is_left_untouched(self, monkeypatch):
        """On a non-shallow repo the deepen must be a no-op — a stray
        --shallow-since fetch here could shallowify a full clone."""
        calls = []

        def fake_git(*args):
            calls.append(args)
            if args == ("rev-parse", "--is-shallow-repository"):
                return "false"
            raise AssertionError(f"unexpected git call: {args}")

        monkeypatch.setattr(prb, "_git", fake_git)
        prb.ensure_ancestry_provable(
            ["recovery/tesla-999-1785247730"],
            dt.datetime.now(dt.timezone.utc))
        assert calls == [("rev-parse", "--is-shallow-repository")]


class TestAppleReporterFreshness:
    def _rollup(self, tmp_path, *, fetched_at, shows=1, last_date=None):
        if last_date is None:
            last_date = (dt.datetime.now(dt.timezone.utc)
                         - dt.timedelta(days=1)).date().isoformat()
        path = tmp_path / "apple_reporter.json"
        path.write_text(json.dumps({
            "fetched_at": fetched_at, "last_date": last_date,
            "shows": {str(i): {} for i in range(shows)},
        }), encoding="utf-8")
        return path

    def test_fresh_fetch_but_stalled_report_date_is_an_alarm(self, tmp_path):
        """A wrong APPLE_REPORTER_VENDOR answers 'no report' for every
        date — fetched_at keeps advancing while last_date freezes, and
        every silent day is unrecoverable history."""
        now = dt.datetime.now(dt.timezone.utc)
        path = self._rollup(
            tmp_path,
            fetched_at=(now - dt.timedelta(hours=6)).isoformat(),
            last_date=(now - dt.timedelta(days=9)).date().isoformat())
        ok, message = reporter_check(path, 3, now)
        assert not ok
        assert "APPLE_REPORTER_VENDOR" in message

    def test_next_day_publishing_lag_is_not_an_alarm(self, tmp_path):
        now = dt.datetime.now(dt.timezone.utc)
        path = self._rollup(
            tmp_path,
            fetched_at=(now - dt.timedelta(hours=6)).isoformat(),
            last_date=(now - dt.timedelta(days=2)).date().isoformat())
        ok, _ = reporter_check(path, 3, now)
        assert ok

    def test_fresh_rollup_is_ok(self, tmp_path):
        now = dt.datetime.now(dt.timezone.utc)
        path = self._rollup(
            tmp_path, fetched_at=(now - dt.timedelta(days=1)).isoformat())
        ok, message = reporter_check(path, 3, now)
        assert ok
        assert "fresh" in message

    def test_stale_rollup_names_the_token(self, tmp_path):
        now = dt.datetime.now(dt.timezone.utc)
        path = self._rollup(
            tmp_path, fetched_at=(now - dt.timedelta(days=9)).isoformat())
        ok, message = reporter_check(path, 3, now)
        assert not ok
        assert "180 days" in message
        assert "token" in message.lower()

    def test_absent_file_is_not_an_alarm(self, tmp_path):
        """Reporter is opt-in — "not set up" is not "broken"."""
        ok, message = reporter_check(
            tmp_path / "nope.json", 3, dt.datetime.now(dt.timezone.utc))
        assert ok
        assert "not configured" in message

    def test_corrupt_file_is_an_alarm(self, tmp_path):
        path = tmp_path / "apple_reporter.json"
        path.write_text("{broken", encoding="utf-8")
        ok, _ = reporter_check(path, 3, dt.datetime.now(dt.timezone.utc))
        assert not ok

    def test_missing_timestamp_is_an_alarm(self, tmp_path):
        path = tmp_path / "apple_reporter.json"
        path.write_text(json.dumps({"shows": {}}), encoding="utf-8")
        ok, _ = reporter_check(path, 3, dt.datetime.now(dt.timezone.utc))
        assert not ok

    def test_naive_timestamps_do_not_crash(self, tmp_path):
        now = dt.datetime.now(dt.timezone.utc)
        path = self._rollup(
            tmp_path,
            fetched_at=(now - dt.timedelta(days=1)).replace(tzinfo=None).isoformat())
        ok, _ = reporter_check(path, 3, now)
        assert ok

    def test_never_fails_the_nightly_by_default(self, tmp_path):
        """It rides along with nightly — an alarm must not become a gate."""
        now = dt.datetime.now(dt.timezone.utc)
        path = self._rollup(
            tmp_path, fetched_at=(now - dt.timedelta(days=30)).isoformat())
        result = subprocess.run(
            [sys.executable,
             str(REPO_ROOT / "scripts" / "check_apple_reporter_freshness.py"),
             "--path", str(path)],
            capture_output=True, text=True,
        )
        assert result.returncode == 0
        assert "::warning::" in result.stdout

    def test_strict_mode_exits_non_zero(self, tmp_path):
        now = dt.datetime.now(dt.timezone.utc)
        path = self._rollup(
            tmp_path, fetched_at=(now - dt.timedelta(days=30)).isoformat())
        result = subprocess.run(
            [sys.executable,
             str(REPO_ROOT / "scripts" / "check_apple_reporter_freshness.py"),
             "--path", str(path), "--strict"],
            capture_output=True, text=True,
        )
        assert result.returncode == 1

    def test_expiry_is_documented(self):
        doc = (REPO_ROOT / "docs" / "analytics.md").read_text(encoding="utf-8")
        assert "180 days" in doc
        assert "January 2027" in doc
        # And names the real secret, not an invented one.
        assert "APPLE_REPORTER_TOKEN" in doc

    def test_wired_into_nightly(self):
        raw = (REPO_ROOT / ".github" / "workflows"
               / "nightly-maintenance.yml").read_text(encoding="utf-8")
        assert "check_apple_reporter_freshness.py" in raw


class TestRuffGateRunsLocally:
    """``pytest`` must fail on what the CI lint step fails on.

    July 30 2026: the full local suite passed (5,023 tests) while CI went
    red, because the lint step in ``.github/workflows/test.yml`` was the
    only thing running ruff and nothing in the suite did. The retention
    pass stopped using ``build_intro_line``'s greeting/framing selections
    but left them assigned, which is an F841 — invisible locally, a red
    check on the PR.

    Skips when ruff isn't installed rather than failing: CI installs it
    and runs the explicit step regardless, so the value here is catching
    it in a dev environment before the push, not gating one without ruff.
    """

    # Mirrors the CI invocation's targets. CI adds --fix
    # --exit-non-zero-on-fix (fail even when auto-fixable); a plain check
    # fails on the same findings without mutating the working tree.
    _TARGETS = ["engine/", "run_show.py", "scripts/"]

    def test_ruff_is_clean(self):
        pytest.importorskip("ruff", reason="ruff not installed in this env")
        result = subprocess.run(
            [sys.executable, "-m", "ruff", "check", *self._TARGETS],
            cwd=REPO_ROOT, capture_output=True, text=True,
        )
        assert result.returncode == 0, (
            "ruff would fail CI:\n" + (result.stdout or result.stderr)
        )

    def test_targets_match_the_ci_step(self):
        """A target added to CI but not here would go unchecked locally."""
        raw = (REPO_ROOT / ".github" / "workflows"
               / "test.yml").read_text(encoding="utf-8")
        line = next(ln for ln in raw.splitlines() if "ruff check" in ln)
        for target in self._TARGETS:
            assert target in line, f"CI no longer lints {target}"
        # And nothing in CI's list is missing from ours.
        ci_targets = [tok for tok in line.split()
                      if not tok.startswith("-") and tok not in
                      ("run:", "ruff", "check")]
        assert sorted(ci_targets) == sorted(self._TARGETS), ci_targets
