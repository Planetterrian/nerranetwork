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
NON_SHOW_YAMLS = {"network_meta", "pronunciation_map", "scaffold_pending"}


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
