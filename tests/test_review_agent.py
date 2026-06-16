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
    def test_workflow_invokes_playbook_via_picker(self):
        text = WORKFLOW_PATH.read_text(encoding="utf-8")
        assert "anthropics/claude-code-action@v1" in text
        assert "/review-show" in text
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

    def test_bot_dispatch_is_allowed(self):
        # The daily audit dispatches this workflow as the github-actions
        # bot; claude-code-action refuses bot-initiated runs unless the
        # actor is allowlisted (broke the event-driven path 2026-06-10).
        text = WORKFLOW_PATH.read_text(encoding="utf-8")
        assert 'allowed_bots: "github-actions"' in text


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
