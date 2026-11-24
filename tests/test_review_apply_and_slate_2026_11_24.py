"""Nov 24 2026, items 3 and 6 of the review-loop automation: the review agent
applies its own show's changes and rehearses them, and one weekly slate
merges records-only PRs and lists the rest by merge tier.

Register ``review-loop-automation-2026-11-24``; rules in
``docs/REVIEW_AGENT.md`` ("Applied changes", "Merge tiers").
"""

from __future__ import annotations

import datetime as dt
import importlib.util
import json
import shutil
import sys
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))


def _load(name: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


rc = _load("review_changes")
slate = _load("review_slate")
review = _load("run_show_review")


# ---------------------------------------------------------------- tiers


class TestTiers:
    @pytest.mark.parametrize("path,tier", [
        ("docs/reviews/spacex_review_2026_11_24.md", "A"),
        ("docs/reviews/ledger/spacex.yaml", "A"),
        ("docs/reviews/pending/spacex_2026_11_24_pr_body.md", "A"),
        ("shows/prompts/spacex_digest.txt", "B"),
        ("shows/prompts/_shared/hook_shape.txt", "B"),
        ("shows/spacex.yaml", "B"),
        ("shows/_defaults.yaml", "B"),
        ("engine/audio.py", "B"),
        ("engine/tts_dialogue.py", "B"),
        ("assets/pronunciation.py", "B"),
        ("engine/blog.py", "C"),
        (".github/workflows/run-show.yml", "C"),
        ("docs/experiments.yaml", "C"),
        ("shows/contracts/must_haves.yaml", "C"),
    ])
    def test_path_tier(self, path, tier):
        assert rc.tier_for_path(path) == tier

    def test_pr_tier_is_the_highest_file_tier(self):
        assert rc.tier_for_paths(["docs/reviews/a.md"]) == "A"
        assert rc.tier_for_paths(["docs/reviews/a.md", "shows/spacex.yaml"]) == "B"
        assert rc.tier_for_paths(["shows/spacex.yaml", "engine/blog.py"]) == "C"

    def test_an_empty_diff_is_never_a_record(self):
        assert rc.tier_for_paths([]) == "C"


# ---------------------------------------------------------------- apply


class TestAllowlist:
    @pytest.mark.parametrize("path,ok", [
        ("shows/prompts/spacex_digest.txt", True),
        ("shows/prompts/spacex/extra.txt", True),
        ("shows/spacex.yaml", True),
        ("shows/prompts/tesla_digest.txt", False),
        ("shows/prompts/spacexy_digest.txt", False),
        ("shows/prompts/_shared/hook_shape.txt", False),
        ("shows/_defaults.yaml", False),
        ("shows/tesla.yaml", False),
        ("engine/audio.py", False),
        ("shows/prompts/spacex_../../engine/x.txt", False),
    ])
    def test_only_the_shows_own_prompts_and_yaml(self, path, ok):
        assert rc.may_apply("spacex", path) is ok

    def test_network_target_applies_nothing(self):
        assert not rc.may_apply("network", "shows/network.yaml")


@pytest.fixture()
def tree(tmp_path):
    (tmp_path / "shows" / "prompts" / "_shared").mkdir(parents=True)
    shutil.copy(ROOT / "shows" / "_defaults.yaml", tmp_path / "shows" / "_defaults.yaml")
    shutil.copy(ROOT / "shows" / "spacex.yaml", tmp_path / "shows" / "spacex.yaml")
    prompt = tmp_path / "shows" / "prompts" / "spacex_digest.txt"
    prompt.write_text("Line one about {show_name}.\nKeep the hook short.\nRepeat.\nRepeat.\n",
                      encoding="utf-8")
    return tmp_path


class TestApply:
    P = "shows/prompts/spacex_digest.txt"

    def test_applies_exact_once(self, tree):
        out = rc.apply_change("spacex", {"file": self.P, "old": "Keep the hook short.",
                                         "new": "Keep the hook under twenty words."}, tree)
        assert out["status"] == rc.APPLIED
        assert "under twenty words" in (tree / self.P).read_text()

    def test_missing_old_text_is_left_as_a_proposal(self, tree):
        before = (tree / self.P).read_text()
        out = rc.apply_change("spacex", {"file": self.P, "old": "Not there.", "new": "x"}, tree)
        assert out["status"] == rc.OLD_NOT_FOUND
        assert (tree / self.P).read_text() == before

    def test_repeated_old_text_is_refused(self, tree):
        out = rc.apply_change("spacex", {"file": self.P, "old": "Repeat.", "new": "Once."}, tree)
        assert out["status"] == rc.OLD_NOT_UNIQUE

    def test_a_prompt_that_no_longer_renders_is_refused(self, tree):
        before = (tree / self.P).read_text()
        out = rc.apply_change("spacex", {"file": self.P, "old": "Keep the hook short.",
                                         "new": "Keep {the hook short."}, tree)
        assert out["status"] == rc.INVALID
        assert (tree / self.P).read_text() == before

    def test_a_missing_include_is_refused(self, tree):
        out = rc.apply_change("spacex", {"file": self.P, "old": "Keep the hook short.",
                                         "new": "<<include: nope.txt>>"}, tree)
        assert out["status"] == rc.INVALID

    def test_broken_yaml_is_refused_and_the_file_untouched(self, tree):
        path = tree / "shows" / "spacex.yaml"
        before = path.read_text()
        first = next(ln for ln in before.splitlines() if ln.startswith("name:"))
        out = rc.apply_change("spacex", {"file": "shows/spacex.yaml", "old": first,
                                         "new": first + "\n  bad: [1"}, tree)
        assert out["status"] == rc.INVALID
        assert path.read_text() == before

    def test_outside_the_allowlist_never_touches_the_file(self, tree):
        path = tree / "shows" / "_defaults.yaml"
        before = path.read_text()
        out = rc.apply_change("spacex", {"file": "shows/_defaults.yaml",
                                         "old": before[:20], "new": "x"}, tree)
        assert out["status"] == rc.NOT_ALLOWED
        assert path.read_text() == before

    def test_apply_proposals_keeps_order_and_chains_edits(self, tree):
        out = rc.apply_proposals("spacex", [
            {"file": self.P, "old": "Keep the hook short.", "new": "Short hook."},
            {"file": self.P, "old": "Short hook.", "new": "Shorter hook."},
            {"file": "engine/blog.py", "old": "a", "new": "b"},
        ], tree)
        assert [o["status"] for o in out] == [rc.APPLIED, rc.APPLIED, rc.NOT_ALLOWED]
        assert "Shorter hook." in (tree / self.P).read_text()


# ---------------------------------------------------------------- the agent


RESULT = {
    "summary": "s", "review_markdown": "body",
    "proposed_changes": [
        {"file": "shows/prompts/spacex_digest.txt", "kind": "prompt",
         "ab_listen_required": True, "old": "a", "new": "b", "rationale": "applied one"},
        {"file": "engine/blog.py", "kind": "code", "ab_listen_required": True,
         "old": "c", "new": "d", "rationale": "not applied one"},
    ],
}
APPLIED = [
    {"file": "shows/prompts/spacex_digest.txt", "status": "applied", "reason": ""},
    {"file": "engine/blog.py", "status": "not_allowed", "reason": "outside the allowlist"},
]


class TestAgent:
    def test_pr_body_separates_applied_from_proposed(self):
        body = review.build_pr_body("spacex", RESULT, 0.5, {}, None, APPLIED, "B", True)
        assert "Merge tier: B (listen)" in body
        applied_sec = body.split("## Applied in this branch")[1].split("## ⚠️")[0]
        assert "applied one" in applied_sec and "not applied one" not in applied_sec
        assert "rehearsal of the episode was dispatched" in applied_sec
        assert "Not applied: not_allowed" in body

    def test_ledger_records_each_changes_status(self, tmp_path, monkeypatch):
        monkeypatch.setattr(review, "ROOT", tmp_path)
        (tmp_path / "docs" / "reviews" / "ledger").mkdir(parents=True)
        doc = tmp_path / "docs" / "reviews" / "x.md"
        doc.write_text("x")
        path = review.update_ledger("spacex", RESULT, doc, 0.1, dt.date(2026, 11, 24), APPLIED)
        entry = yaml.safe_load(path.read_text())["reviews"][-1]
        assert [c["status"] for c in entry["proposed_changes_in_pr"]] == \
            ["applied", "not_allowed"]
        assert entry["shipped"] == []  # applied is not shipped until merged

    def test_result_file_drives_the_rehearsal(self, tmp_path, monkeypatch):
        out = tmp_path / "r.json"
        monkeypatch.setenv("REVIEW_RESULT_FILE", str(out))
        review.write_result("spacex", "agent/review-spacex-20261124", "B", APPLIED, True)
        data = json.loads(out.read_text())
        assert data["rehearse"] is True and data["tier"] == "B"
        assert [a["file"] for a in data["applied"]] == ["shows/prompts/spacex_digest.txt"]

    def test_rehearsable_shows_exclude_the_interview_show(self):
        slugs = review.rehearsable_slugs()
        assert "spacex" in slugs and "age_of_ai" not in slugs and "network" not in slugs

    def test_script_offers_the_old_behaviour(self):
        text = (ROOT / "scripts" / "run_show_review.py").read_text()
        assert "--no-apply" in text and "apply_proposals" in text

    def test_contract_tells_grok_to_copy_old_text_exactly(self):
        assert "EXACTLY" in review._OUTPUT_CONTRACT
        assert "quotable example" in review._OUTPUT_CONTRACT


class TestReviewWorkflow:
    TEXT = (ROOT / ".github" / "workflows" / "show-review.yml").read_text()

    def test_token_makes_review_prs_real_events(self):
        assert "token: ${{ secrets.REVIEW_PR_TOKEN || github.token }}" in self.TEXT
        assert "GH_TOKEN: ${{ secrets.REVIEW_PR_TOKEN || secrets.GITHUB_TOKEN }}" in self.TEXT

    def test_rehearsal_is_dispatched_on_the_review_branch(self):
        assert "actions: write" in self.TEXT
        assert 'gh workflow run run-show.yml --ref "$BRANCH"' in self.TEXT
        assert "rehearse=true" in self.TEXT
        assert "REVIEW_RESULT_FILE" in self.TEXT


# ---------------------------------------------------------------- the slate


def _pr(n, paths, branch=None, checks=None, created="2026-11-20"):
    return {"number": n, "title": f"pr {n}", "url": f"u/{n}",
            "headRefName": branch or f"agent/review-show{n}-20261120",
            "isDraft": True, "createdAt": created + "T07:00:00Z",
            "files": [{"path": p} for p in paths],
            "statusCheckRollup": checks or []}


GREEN = [{"status": "COMPLETED", "conclusion": "SUCCESS"}]
RED = [{"status": "COMPLETED", "conclusion": "FAILURE"}]
GOOD_LEDGER = "reviews:\n- date: '2026-11-20'\n"


class FakeGh:
    def __init__(self, prs, runs=None):
        self.prs, self.runs, self.calls = prs, runs or {}, []

    def __call__(self, args):
        self.calls.append(args)
        if args[:2] == ["pr", "list"]:
            return json.dumps(self.prs)
        if args[:2] == ["run", "list"]:
            branch = args[args.index("--branch") + 1]
            return json.dumps(self.runs.get(branch, []))
        return ""

    def merged(self):
        return [a[2] for a in self.calls if a[:2] == ["pr", "merge"]]


def _reader(text=GOOD_LEDGER):
    return lambda _branch: (lambda _path: text)


TODAY = dt.date(2026, 11, 27)


class TestSlate:
    def test_checks_state(self):
        assert slate.checks_state([]) == "none"
        assert slate.checks_state(GREEN) == "green"
        assert slate.checks_state(GREEN + RED) == "red"
        assert slate.checks_state([{"status": "IN_PROGRESS"}]) == "pending"
        assert slate.checks_state([{"state": "SUCCESS"}]) == "green"

    def test_records_merge_on_apply_and_nothing_else_does(self, tmp_path):
        gh = FakeGh([
            _pr(1, ["docs/reviews/a.md", "docs/reviews/ledger/a.yaml"], checks=GREEN),
            _pr(2, ["docs/reviews/b.md", "shows/prompts/show2_digest.txt"], checks=GREEN),
            _pr(3, ["docs/reviews/c.md", "engine/blog.py"], checks=GREEN),
            _pr(4, ["shows/x.yaml"], branch="claude/other"),
        ], runs={"agent/review-show2-20261120": [{"url": "r", "conclusion": "success"}]})
        doc = slate.build(gh, apply=True, today=TODAY, root=tmp_path, read_at=_reader())
        assert gh.merged() == ["1"]
        buckets = {i["number"]: i["bucket"] for i in doc["items"]}
        assert buckets == {1: "records", 2: "listen", 3: "operator"}
        assert "Ready for your listen" in doc["body"] and "#2" in doc["body"]

    def test_dry_run_merges_nothing(self, tmp_path):
        gh = FakeGh([_pr(1, ["docs/reviews/a.md"], checks=GREEN)])
        doc = slate.build(gh, apply=False, today=TODAY, root=tmp_path, read_at=_reader())
        assert gh.merged() == [] and doc["held"][0]["held"] == "dry run"

    def test_red_checks_hold_a_records_pr(self, tmp_path):
        gh = FakeGh([_pr(1, ["docs/reviews/a.md"], checks=RED)])
        doc = slate.build(gh, apply=True, today=TODAY, root=tmp_path, read_at=_reader())
        assert gh.merged() == [] and "checks red" in doc["held"][0]["held"]

    def test_a_broken_ledger_holds_a_records_pr(self, tmp_path):
        gh = FakeGh([_pr(1, ["docs/reviews/ledger/a.yaml"], checks=GREEN)])
        doc = slate.build(gh, apply=True, today=TODAY, root=tmp_path,
                          read_at=_reader("reviews:\n- date: [\n"))
        assert gh.merged() == [] and "ledger does not parse" in doc["held"][0]["held"]

    def test_listen_tier_without_a_rehearsal_waits(self, tmp_path):
        gh = FakeGh([_pr(2, ["shows/prompts/show2_digest.txt"])])
        doc = slate.build(gh, apply=True, today=TODAY, root=tmp_path, read_at=_reader())
        assert doc["items"][0]["bucket"] == "rehearsal" and gh.merged() == []

    def test_stale_is_flagged_never_closed(self, tmp_path):
        gh = FakeGh([_pr(3, ["engine/blog.py"], created="2026-10-01")])
        doc = slate.build(gh, apply=True, today=TODAY, root=tmp_path, read_at=_reader())
        assert doc["items"][0]["stale"] and "**stale**" in doc["body"]
        assert not any(a[:2] == ["pr", "close"] for a in gh.calls)

    def test_slate_reads_readout_misses_and_must_haves(self, tmp_path):
        (tmp_path / "api").mkdir()
        (tmp_path / "api" / "register_readouts.json").write_text(
            json.dumps({"misses": ["structural-regen-2026-10-09"]}))
        (tmp_path / "api" / "show_contracts.json").write_text(
            json.dumps({"page": ["spacex Ep170: missing"], "warn": []}))
        doc = slate.build(FakeGh([]), today=TODAY, root=tmp_path, read_at=_reader())
        assert "structural-regen-2026-10-09" in doc["body"]
        assert "spacex Ep170: missing" in doc["body"]

    def test_workflow_is_weekly_and_merges_only_through_the_script(self):
        text = (ROOT / ".github" / "workflows" / "review-slate.yml").read_text()
        assert "cron: '0 15 * * 5'" in text
        assert "python scripts/review_slate.py --apply" in text
        assert "gh pr merge" not in text
        assert "runs-on: ubuntu-26.04" in text


def test_claude_md_names_the_pass():
    text = (ROOT / "CLAUDE.md").read_text(encoding="utf-8")
    assert "scripts/review_changes.py" in text and "scripts/review_slate.py" in text
