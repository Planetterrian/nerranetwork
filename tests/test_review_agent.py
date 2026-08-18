"""Drift guards for the scheduled Show Review Agent.

Pins the contract between the three moving parts:
  - .claude/commands/review-show.md   (the review playbook)
  - scripts/pick_review_target.py     (deterministic rotation)
  - docs/reviews/review_state.yaml    (rotation state)
  - .github/workflows/show-review.yml (the scheduler)

If a show is added (scripts/scaffold_show.py) without a rotation entry, or
the playbook loses one of its operator-safety guardrails, these tests fail.
"""

import importlib.util
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
STATE_PATH = ROOT / "docs" / "reviews" / "review_state.yaml"
PLAYBOOK_PATH = ROOT / ".claude" / "commands" / "review-show.md"
WORKFLOW_PATH = ROOT / ".github" / "workflows" / "show-review.yml"

# shows/*.yaml files that are not show configs.
NON_SHOW_YAMLS = {"network_meta", "pronunciation_map", "scaffold_pending",
                  "translation_overrides"}


def _load_picker():
    spec = importlib.util.spec_from_file_location(
        "pick_review_target", ROOT / "scripts" / "pick_review_target.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _show_slugs():
    return {
        p.stem
        for p in (ROOT / "shows").glob("*.yaml")
        if not p.stem.startswith("_") and p.stem not in NON_SHOW_YAMLS
    }


class TestRotationState:
    def test_state_covers_every_show_plus_network(self):
        data = yaml.safe_load(STATE_PATH.read_text(encoding="utf-8"))
        targets = set(data["targets"])
        expected = _show_slugs() | {"network"}
        missing = expected - targets
        stale = targets - expected
        assert not missing, f"shows missing from review rotation: {sorted(missing)}"
        assert not stale, f"rotation entries with no shows/<slug>.yaml: {sorted(stale)}"

    def test_every_entry_is_a_date(self):
        data = yaml.safe_load(STATE_PATH.read_text(encoding="utf-8"))
        for slug, value in data["targets"].items():
            assert str(value).count("-") == 2, f"{slug}: expected YYYY-MM-DD, got {value!r}"


class TestPicker:
    def test_picks_least_recently_reviewed(self, tmp_path):
        picker = _load_picker()
        state = tmp_path / "state.yaml"
        state.write_text(
            "targets:\n  alpha: 2026-06-10\n  beta: 2026-06-01\n  gamma: 2026-06-05\n"
        )
        assert picker.pick_target(state, set()) == "beta"

    def test_alphabetical_tie_break_is_deterministic(self, tmp_path):
        picker = _load_picker()
        state = tmp_path / "state.yaml"
        state.write_text("targets:\n  zeta: 2026-06-01\n  alpha: 2026-06-01\n")
        assert picker.pick_target(state, set()) == "alpha"

    def test_excludes_in_flight_targets(self, tmp_path):
        picker = _load_picker()
        state = tmp_path / "state.yaml"
        state.write_text("targets:\n  alpha: 2026-06-01\n  beta: 2026-06-05\n")
        assert picker.pick_target(state, {"alpha"}) == "beta"

    def test_returns_none_when_everything_excluded(self, tmp_path):
        picker = _load_picker()
        state = tmp_path / "state.yaml"
        state.write_text("targets:\n  alpha: 2026-06-01\n")
        assert picker.pick_target(state, {"alpha"}) is None

    def test_picks_from_real_state_file(self):
        picker = _load_picker()
        slug = picker.pick_target(STATE_PATH, set())
        assert slug in _show_slugs() | {"network"}


class TestPlaybookGuardrails:
    """The playbook must keep the operator-safety language that makes
    autonomous review PRs safe to receive."""

    def test_playbook_exists_and_takes_argument(self):
        text = PLAYBOOK_PATH.read_text(encoding="utf-8")
        assert "$ARGUMENTS" in text

    def test_ab_listen_guardrail_present(self):
        text = PLAYBOOK_PATH.read_text(encoding="utf-8")
        assert "A/B-listen" in text
        assert "landmine #17" in text

    def test_draft_pr_only(self):
        text = PLAYBOOK_PATH.read_text(encoding="utf-8")
        assert "--draft" in text
        assert "Never merge your own PR" in text

    def test_rotation_update_instruction_present(self):
        text = PLAYBOOK_PATH.read_text(encoding="utf-8")
        assert "review_state.yaml" in text
        assert "docs/reviews/" in text

    def test_branch_prefix_matches_workflow_exclusion_regex(self):
        # The workflow detects in-flight reviews by this exact branch shape.
        playbook = PLAYBOOK_PATH.read_text(encoding="utf-8")
        workflow = WORKFLOW_PATH.read_text(encoding="utf-8")
        assert "agent/review-<slug>-<YYYYMMDD>" in playbook
        assert "agent/review-" in workflow


class TestWorkflowWiring:
    def test_workflow_runs_grok_review_via_picker(self):
        text = WORKFLOW_PATH.read_text(encoding="utf-8")
        # Runs the Grok-powered review script, not the (retired, costly) Claude
        # Opus claude-code-action.
        assert "scripts/run_show_review.py" in text
        assert "anthropics/claude-code-action" not in text
        assert "pick_review_target.py" in text

    def test_workflow_is_scheduled_and_dispatchable(self):
        data = yaml.safe_load(WORKFLOW_PATH.read_text(encoding="utf-8"))
        triggers = data.get("on") or data.get(True)  # yaml parses bare `on:` as True
        assert "schedule" in triggers
        assert "workflow_dispatch" in triggers

    def test_workflow_supports_prompt_validation_and_notify(self):
        text = WORKFLOW_PATH.read_text(encoding="utf-8")
        # GROK_API_KEY enables the show-the-output prompt validation path.
        assert "GROK_API_KEY" in text
        # Operator heartbeat when a review PR opens (no-op when unset).
        assert "NOTIFICATION_WEBHOOK_URL" in text

    def test_forced_target_respects_in_flight_reviews(self):
        # A forced dispatch (operator or daily-audit) must not double up on
        # a show that already has an open review PR.
        text = WORKFLOW_PATH.read_text(encoding="utf-8")
        assert "already has an open review PR" in text

    def test_bot_dispatch_needs_no_actor_allowlist(self):
        # The daily audit dispatches this workflow as the github-actions bot.
        # The review now runs as a plain `python scripts/run_show_review.py`
        # step authorized by GITHUB_TOKEN, which works for bot-initiated runs —
        # so the old claude-code-action `allowed_bots` allowlist is gone.
        text = WORKFLOW_PATH.read_text(encoding="utf-8")
        assert "allowed_bots" not in text
        assert "GH_TOKEN: ${{ secrets.GITHUB_TOKEN }}" in text

    def test_pick_step_excludes_pushed_review_branches(self):
        # gh pr create is org-blocked in some configs, so review runs land as
        # orphan agent/review-* branches with no PR. The pick-target exclusion
        # must treat a pushed branch as an in-flight review — the open-PR-only
        # dedupe kept re-reviewing the same show (FF 4x, Jun-Jul 2026).
        text = WORKFLOW_PATH.read_text(encoding="utf-8")
        assert "git ls-remote --heads origin 'refs/heads/agent/review-*'" in text

    def test_review_step_carries_notification_webhook(self):
        # run_show_review.py alerts this webhook when gh pr create fails, so
        # a review stranded on its branch is never silent.
        data = yaml.safe_load(WORKFLOW_PATH.read_text(encoding="utf-8"))
        steps = data["jobs"]["review"]["steps"]
        run_step = next(s for s in steps if s.get("name") == "Run review agent (Grok)")
        assert "NOTIFICATION_WEBHOOK_URL" in run_step.get("env", {})


def _load_script(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class TestReviewSnapshot:
    """The deterministic quality-snapshot script the playbook runs first."""

    def test_tic_detector_finds_and_stitches_cross_episode_phrase(self):
        snap = _load_script("review_snapshot")
        boiler = "that truly wraps today's case file for the network everyone stay curious"
        texts = [f"Story about topic{chr(97 + i)} today. {boiler}." for i in range(10)]
        phrases = [p for p, _ in snap.find_repeated_ngrams(texts)]
        # Stitching must reassemble the >8-word phrase into ONE entry, not
        # report each overlapping 8-gram window separately.
        assert any(
            "wraps today's case file for the network everyone stay" in p for p in phrases
        )
        assert len([p for p in phrases if "case file" in p]) == 1

    def test_tic_detector_ignores_unique_text(self):
        snap = _load_script("review_snapshot")
        letters = "abcdefghijklmnopqrstuvwxyz"
        texts = [
            " ".join(f"q{letters[i]}{letters[j]}word" for j in range(20))
            for i in range(10)
        ]  # tokens are unique per text — no shared n-grams at all
        assert snap.find_repeated_ngrams(texts) == []

    def test_chapter_issue_detection(self):
        snap = _load_script("review_snapshot")
        chapters = [
            {"title": "Introduction"},
            {"title": "Story one"},
            {"title": "Introduction"},
        ]
        issues = " ".join(snap.chapter_issues(chapters))
        assert "Introduction" in issues

    def test_snapshot_runs_on_a_real_show(self):
        snap = _load_script("review_snapshot")
        report = snap.build_snapshot("tesla", episodes=3)
        assert "Review snapshot: tesla" in report
        assert "Script length" in report


class TestQualityReviewDispatch:
    """daily-audit's event-driven review trigger (scripts/dispatch_quality_reviews.py)."""

    def test_picks_show_with_most_editorial_criticals(self):
        mod = _load_script("dispatch_quality_reviews")
        data = {
            "remediation": {"auto_retry_shows": []},
            "episodes": [
                {"show": "tesla", "critical": 1},
                {"show": "omni_view", "critical": 3},
                {"show": "env_intel", "critical": 0},
            ],
        }
        assert mod.pick_review_candidate(data) == "omni_view"

    def test_missed_shows_are_retried_not_reviewed(self):
        mod = _load_script("dispatch_quality_reviews")
        data = {
            "remediation": {"auto_retry_shows": ["tesla"]},
            "episodes": [{"show": "tesla", "critical": 2}],
        }
        assert mod.pick_review_candidate(data) is None

    def test_no_criticals_means_no_dispatch(self):
        mod = _load_script("dispatch_quality_reviews")
        data = {"episodes": [{"show": "tesla", "critical": 0, "warnings": 4}]}
        assert mod.pick_review_candidate(data) is None

    def test_daily_audit_wires_the_dispatcher(self):
        audit = (ROOT / ".github" / "workflows" / "daily-audit.yml").read_text(encoding="utf-8")
        assert "dispatch_quality_reviews.py" in audit
        assert "actions: write" in audit

    def test_pushed_review_branch_counts_as_in_flight(self, monkeypatch):
        # PR-only dedupe re-dispatched FF 4x while its review sat on orphan
        # branches (gh pr create org-blocked). A pushed agent/review-<slug>-*
        # branch must dedupe too.
        mod = _load_script("dispatch_quality_reviews")
        calls = []

        class Proc:
            stdout = "abc123\trefs/heads/agent/review-fascinating_frontiers-20260626\n"
            stderr = ""

        def fake_run(cmd, **kwargs):
            calls.append(cmd)
            return Proc()

        monkeypatch.setattr(mod.subprocess, "run", fake_run)
        assert mod._remote_review_branch_exists("fascinating_frontiers") is True
        assert calls and "ls-remote" in calls[0]

    def test_no_remote_branch_means_not_in_flight(self, monkeypatch):
        mod = _load_script("dispatch_quality_reviews")

        class Proc:
            stdout = ""
            stderr = ""

        monkeypatch.setattr(mod.subprocess, "run", lambda cmd, **kw: Proc())
        assert mod._remote_review_branch_exists("tesla") is False


class TestGrokReviewScript:
    """The Grok-powered review runner that replaced the Claude Opus agent."""

    SCRIPT = ROOT / "scripts" / "run_show_review.py"

    def test_script_exists_and_uses_grok(self):
        """The scheduled reviewer stays on a Grok model (cost contract:
        this job replaced a $6-9/run Claude agent). Upgraded grok-4.3 ->
        grok-4.5 on 2026-07-31 (analysis-only task, operator-gated
        output, ~$0.75/run); env-overridable for rollback."""
        text = self.SCRIPT.read_text(encoding="utf-8")
        assert 'REVIEW_MODEL = os.environ.get("REVIEW_MODEL", "grok-4.6")' \
            in text

    def test_script_opens_draft_pr_with_review_branch_prefix(self):
        text = self.SCRIPT.read_text(encoding="utf-8")
        assert "--draft" in text
        assert "agent/review-" in text

    def test_script_does_not_auto_edit_prompts_or_audio(self):
        # The safety contract: Grok PROPOSES prompt/audio changes in the PR
        # body (A/B-listen gate, landmine #17) and never auto-applies them.
        text = self.SCRIPT.read_text(encoding="utf-8")
        assert "A/B-listen required" in text
        assert "ab_listen_required" in text

    def test_script_loads_without_ci_only_deps(self):
        # Importing the module must not require the heavy engine.generator
        # stack (tenacity/openai) — those are deferred to the Grok call so the
        # gather/parse/write logic stays unit-testable.
        mod = _load_script("run_show_review")
        assert hasattr(mod, "build_pr_body")
        assert hasattr(mod, "update_ledger")

    def test_pr_body_committed_to_branch_and_gh_failure_alerts(self, tmp_path, monkeypatch):
        # The PR body carries the ONLY copy of the proposed A/B prompt edits.
        # It must be committed into the review branch BEFORE `gh pr create`
        # (org-blocked in some configs) so proposals survive a failed PR open,
        # and the failure must alert the operator webhook with the branch name.
        import datetime as dt

        mod = _load_script("run_show_review")
        monkeypatch.setattr(mod, "ROOT", tmp_path)
        git_calls = []
        monkeypatch.setattr(mod, "_git", lambda *args: git_calls.append(args))

        class FailedProc:
            returncode = 1
            stdout = ""
            stderr = "GraphQL: GitHub Actions is not permitted to create or approve pull requests"

        monkeypatch.setattr(mod.subprocess, "run", lambda *a, **kw: FailedProc())
        alerts = []
        monkeypatch.setattr(mod, "_post_webhook", lambda text: alerts.append(text))

        today = dt.date(2026, 7, 1)
        doc = tmp_path / "docs" / "reviews" / "tesla_review_2026_07_01.md"
        doc.parent.mkdir(parents=True)
        doc.write_text("review", encoding="utf-8")

        mod.open_draft_pr("tesla", [doc], "PR BODY with A/B proposals", today)

        pending = tmp_path / "docs" / "reviews" / "pending" / "tesla_2026_07_01_pr_body.md"
        assert pending.exists()
        assert "A/B proposals" in pending.read_text(encoding="utf-8")
        add_call = next(c for c in git_calls if c[0] == "add")
        assert any("pending" in arg for arg in add_call), \
            "pending PR body must be part of the review-branch commit"
        assert alerts and "agent/review-tesla-20260701" in alerts[0]


class TestLedger:
    """The review ledger is the recursive-memory mechanism."""

    def test_schema_doc_exists(self):
        readme = (ROOT / "docs" / "reviews" / "ledger" / "README.md").read_text(encoding="utf-8")
        for key in ("predictions", "verdict", "do_not_retry", "deferred"):
            assert key in readme

    def test_seed_ledger_parses_with_expected_shape(self):
        data = yaml.safe_load(
            (ROOT / "docs" / "reviews" / "ledger" / "tesla.yaml").read_text(encoding="utf-8")
        )
        assert data["reviews"], "seed ledger must contain at least one review"
        review = data["reviews"][0]
        for key in ("date", "shipped", "deferred", "predictions"):
            assert key in review
        assert all("metric" in p and "verdict" in p for p in review["predictions"])
        assert data["do_not_retry"], "seed must carry the landmine-17 do_not_retry entry"

    def test_playbook_closes_the_loop(self):
        text = PLAYBOOK_PATH.read_text(encoding="utf-8")
        for needle in (
            "docs/reviews/ledger/",
            "do_not_retry",
            "review_snapshot.py",
            "predictions",
            "meta-review",
        ):
            assert needle in text, f"playbook lost its recursive-loop step: {needle}"


class TestSnapshotFetchFilterLeakage:
    """July 18 2026 meta-review: fetch-filter predictions sat pending for
    weeks because nothing counted them — the snapshot now scans recent
    digests for lines whose (bold-title) text matches the show's own
    exclude_title_patterns."""

    def test_leakage_section_present_for_filter_shows(self):
        import subprocess
        import sys
        out = subprocess.run(
            [sys.executable, str(ROOT / "scripts" / "review_snapshot.py"), "planetterrian"],
            capture_output=True, text=True, timeout=120,
        ).stdout
        assert "## Fetch-filter leakage" in out

    def test_date_suffix_does_not_false_match(self):
        # SpaceX digest titles end "(YYYY-MM-DD)" which false-matched the
        # id-shaped junk-title pattern until the probe stripped it.
        import subprocess
        import sys
        out = subprocess.run(
            [sys.executable, str(ROOT / "scripts" / "review_snapshot.py"), "spacex"],
            capture_output=True, text=True, timeout=120,
        ).stdout
        section = out.split("## Fetch-filter leakage", 1)[1].split("##", 1)[0]
        assert "(2026-" not in section, (
            "date suffixes must not register as junk-title filter hits"
        )


class TestDashboardVoiceBaseline:
    def test_ru_baseline_is_the_grok_olya_voice(self):
        # The stale ElevenLabs RU baseline flagged FP/PR/age_of_ai as voice
        # drift on every dashboard build (false positives train the
        # operator to ignore warnings).
        text = (ROOT / "scripts" / "generate_dashboard.py").read_text(
            encoding="utf-8")
        assert '_VOICE_ID_RU = "0b875ae2"' in text
        assert '"ara"' in text.split("_SANCTIONED_EXTRA_VOICES", 1)[1][:80]


class TestLedgerDrivenRotation:
    """July 21 2026: review PRs no longer edit review_state.yaml (any two
    concurrently-open review PRs conflicted on it every time — PRs
    #845/#856). The effective last-reviewed date is max(state seed date,
    latest ledger entry date), so merging a review PR advances the
    rotation via the ledger entry it already carries."""

    def test_newer_ledger_date_wins_over_state_seed(self, tmp_path):
        picker = _load_picker()
        state = tmp_path / "state.yaml"
        state.write_text(
            "targets:\n  alpha: 2026-06-01\n  beta: 2026-06-10\n"
        )
        ledger = tmp_path / "ledger"
        ledger.mkdir()
        # alpha was reviewed on 06-20 per its ledger — beta becomes oldest.
        (ledger / "alpha.yaml").write_text(
            "reviews:\n  - date: '2026-06-20'\n    summary: pass\n"
        )
        assert picker.pick_target(state, set(), ledger_dir=ledger) == "beta"

    def test_missing_ledger_falls_back_to_state_date(self, tmp_path):
        picker = _load_picker()
        state = tmp_path / "state.yaml"
        state.write_text("targets:\n  alpha: 2026-06-01\n  beta: 2026-06-10\n")
        assert picker.pick_target(state, set()) == "alpha"

    def test_ledger_dates_read_by_regex_not_yaml(self, tmp_path):
        # Three committed ledgers contain unquoted ": " inside list items
        # and cannot be safe_load-ed — the date extraction must survive that.
        picker = _load_picker()
        state = tmp_path / "state.yaml"
        state.write_text("targets:\n  alpha: 2026-06-01\n  beta: 2026-06-05\n")
        ledger = tmp_path / "ledger"
        ledger.mkdir()
        (ledger / "alpha.yaml").write_text(
            "reviews:\n"
            "  - date: '2026-06-30'\n"
            "    summary: broken: unquoted: colons: everywhere\n"
        )
        assert picker.pick_target(state, set(), ledger_dir=ledger) == "beta"

    def test_real_ledgers_yield_parseable_dates(self):
        picker = _load_picker()
        ledger_dir = ROOT / "docs" / "reviews" / "ledger"
        found = 0
        for path in ledger_dir.glob("*.yaml"):
            d = picker._latest_ledger_date(ledger_dir, path.stem)
            if d:
                assert len(d) == 10 and d[4] == "-", (path.name, d)
                found += 1
        assert found >= 5  # the rotation's ledgers are being read

    def test_review_runner_no_longer_writes_review_state(self):
        text = (ROOT / "scripts" / "run_show_review.py").read_text(encoding="utf-8")
        assert "advance_rotation" not in text.replace(
            "rotation is no longer advanced here", ""
        ).replace("advances the\n# rotation", "")
        assert 'review_state.yaml"' not in text
