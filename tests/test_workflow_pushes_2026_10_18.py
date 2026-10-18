"""Oct 18 2026 workflow review: pushes that fail visibly, guards that see
the whole day, and wake-ups that survive a cancelled finalize.

1. produce-special.yml: a rebase conflict left .git/rebase-merge behind and
   the step exited 0 — on the release path that lost the released catalog
   commit and the X/Short "posted" markers after X and YouTube had posted.
2. safe-commit-push: a failed `git pull --rebase` was never aborted, so every
   later attempt was dead (the class push_show_artifacts.sh fixed in #1472).
3. A cancelled pending finalize makes the whole Run Podcast Show run conclude
   `cancelled`; Nerra Daily and the multilingual sweep never woke for it.
5. The duplicate guard read one unfiltered page of 100 commits.
6. A members-only desk that skipped with no_member_demand re-ran on every
   fallback cron.
"""
from __future__ import annotations

import re
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
WF = ROOT / ".github" / "workflows"


def _wf(name: str) -> str:
    return (WF / name).read_text(encoding="utf-8")


def _step(text: str, name: str) -> str:
    start = text.index(f"- name: {name}")
    nxt = text.find("- name:", start + 10)
    return text[start:nxt if nxt != -1 else len(text)]


class TestProduceSpecialPushes:
    def test_parses(self):
        yaml.safe_load(_wf("produce-special.yml"))

    def test_no_bare_retry_loop_is_left(self):
        text = _wf("produce-special.yml")
        assert "git push -q origin HEAD:main && break" not in text

    def test_push_helper_aborts_a_failed_rebase_and_returns_failure(self):
        text = _wf("produce-special.yml")
        for step in ("Produce", "Release"):
            body = _step(text, step)
            helper = body[body.index("push_main() {"):body.index("return 1")]
            assert "git rebase --abort" in helper
            assert "rebase-merge" in helper
            assert "return 0" in helper

    def test_produce_fails_when_a_commit_never_reached_main(self):
        body = _step(_wf("produce-special.yml"), "Produce")
        assert "if push_main; then unpushed=0; else unpushed=1; fi" in body
        tail = body[body.index('if [ "$unpushed" -ne 0 ]'):]
        assert "create_recovery_pr.sh" in tail
        assert "exit 1" in tail[:tail.index("exit $status")]

    def test_release_fails_visibly_when_its_commit_cannot_land(self):
        body = _step(_wf("produce-special.yml"), "Release")
        tail = body[body.index("if ! push_main; then"):]
        assert "::error::" in tail and "exit 1" in tail
        assert "create_recovery_pr.sh" in tail

    def test_release_never_commits_finalize_owned_pages(self):
        body = _step(_wf("produce-special.yml"), "Release")
        assert "--homepage" not in body
        assert "--sitemap" not in body
        add = [ln for ln in body.splitlines() if "git add" in ln]
        assert add and all("sitemap.xml" not in ln for ln in add)
        assert "git reset -q -- login.html index.html sitemap.xml" in body

    def test_recovery_pr_has_its_token_and_permission(self):
        text = _wf("produce-special.yml")
        doc = yaml.safe_load(text)
        assert doc["permissions"].get("pull-requests") == "write"
        for step in doc["jobs"]["special"]["steps"]:
            if step.get("name") in ("Produce", "Release"):
                assert "GH_TOKEN" in step["env"], step["name"]


class TestSafeCommitPushAbortsRebase:
    def _action(self) -> str:
        return (ROOT / ".github" / "actions" / "safe-commit-push" / "action.yml").read_text(
            encoding="utf-8")

    def test_no_swallowed_rebase_failure(self):
        assert "git pull --rebase --autostash origin main || true" not in self._action()

    def test_pull_and_push_steps_abort_a_stale_rebase(self):
        text = self._action()
        for step in ("Pull latest (best effort)", "Push to main (with retry)"):
            body = _step(text, step)
            assert "abort_stale_rebase() {" in body, step
            assert "git rebase --abort" in body, step
            assert "|| abort_stale_rebase" in body, step

    def test_rebase_is_cleared_before_the_recovery_branch(self):
        body = _step(self._action(), "Push to main (with retry)")
        after_loop = body[body.index("done"):]
        assert after_loop.index("abort_stale_rebase") < after_loop.index("create_recovery_pr.sh")


class TestCancelledRunsStillWake:
    def test_nerra_daily_wakes_on_a_cancelled_run(self):
        doc = yaml.safe_load(_wf("nerra-daily.yml"))
        cond = doc["jobs"]["build"]["if"]
        for c in ("success", "failure", "cancelled"):
            assert f'"{c}"' in cond, c

    def test_multilingual_wakes_on_a_cancelled_run(self):
        doc = yaml.safe_load(_wf("multilingual.yml"))
        cond = doc["jobs"]["resolve"]["if"]
        assert '"success"' in cond and '"cancelled"' in cond

    def test_multilingual_translates_only_successful_show_jobs(self):
        text = _wf("multilingual.yml")
        assert 'job.get("conclusion") == "success"' in text
        # Oct 18 2026: the video job's "render (<show>)" jobs count too.
        assert r're.fullmatch(r"(?:run|render) \((\S+)\)"' in text


class TestDuplicateGuard:
    def _gate(self) -> str:
        return _step(_wf("run-show.yml"), "Determine shows to run")

    def test_listing_is_per_show_and_paginated(self):
        gate = self._gate()
        assert "commits?path={_output_dir(slug)}" in gate
        assert "&page={page}" in gate
        assert re.search(r"for page in range\(1, \d+\)", gate)
        assert "commits?since={since}&per_page=100\"" not in gate

    def test_audio_checkpoint_commit_still_counts(self):
        gate = self._gate()
        assert 'marker = f"Auto-generated: {slug} {today_str}"' in gate
        assert "m.startswith(marker)" in gate

    def test_no_member_demand_skip_is_done_but_unknown_demand_is_not(self):
        gate = self._gate()
        assert 'DONE_SKIP_REASONS = {"no_member_demand"}' in gate
        assert "member_demand_unknown" not in gate.split("DONE_SKIP_REASONS")[1].split("\n")[0]

    def test_recheck_honours_no_member_demand_only(self):
        body = _step(_wf("run-show.yml"), "Run show pipeline")
        recheck = body[body.index('if [ "$RECHECK" = "true" ]'):body.index('EXTRA_FLAGS=""')]
        assert ".skip_${TODAY}.json" in recheck
        assert "== 'no_member_demand'" in recheck
        assert "'member_demand_unknown'" not in recheck

    def test_reason_is_what_run_show_writes(self):
        src = (ROOT / "run_show.py").read_text(encoding="utf-8")
        assert '"no_member_demand",' in src
        assert 'marker_path = digests_dir / f".skip_{today.strftime(\'%Y%m%d\')}.json"' in src
