"""The push-retry path, exercised against real temporary git repos.

Reproduces the 28 July 2026 incident (SpaceX Ep47, run 30354757421): a
content conflict in ``spacex_podcast.video.rss`` sent the episode to
recovery PR #892 after four attempts, because

* the show job and the nightly's ``build_video_feeds.py --all`` both
  write the video feeds, and
* the merge fallback could never succeed — checkout is ``fetch-depth: 1``
  and a shallow clone has no common ancestor, so git answers "refusing
  to merge unrelated histories" every single time.

These tests use real ``git`` rather than mocks, because the failure was
entirely in git's actual behaviour: which side ``--ours`` refers to
during a rebase (inverted from intuition), and what a shallow clone
refuses to do. A mock would have happily passed while production
stranded episodes.
"""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "scripts" / "push_show_artifacts.sh"

pytestmark = pytest.mark.skipif(shutil.which("git") is None,
                                reason="git not available")


def _git(*args, cwd, check=True, **kw):
    return subprocess.run(["git", *args], cwd=str(cwd), check=check,
                          capture_output=True, text=True, **kw)


@pytest.fixture()
def remote_and_clone(tmp_path):
    """A bare 'origin' with one commit, plus a working clone."""
    origin = tmp_path / "origin.git"
    origin.mkdir()
    _git("init", "--bare", "--initial-branch=main", cwd=origin)

    seed = tmp_path / "seed"
    seed.mkdir()
    _git("init", "--initial-branch=main", cwd=seed)
    _git("config", "user.email", "t@example.com", cwd=seed)
    _git("config", "user.name", "T", cwd=seed)
    (seed / "spacex_podcast.video.rss").write_text("<rss>base</rss>\n")
    (seed / "other.txt").write_text("base\n")
    _git("add", "-A", cwd=seed)
    _git("commit", "-m", "seed", cwd=seed)
    _git("remote", "add", "origin", str(origin), cwd=seed)
    _git("push", "-u", "origin", "main", cwd=seed)

    work = tmp_path / "work"
    _git("clone", str(origin), str(work), cwd=tmp_path)
    _git("config", "user.email", "t@example.com", cwd=work)
    _git("config", "user.name", "T", cwd=work)
    return origin, seed, work


def _run_script(work: Path, show: str = "spacex", attempts: str = "2"):
    env = dict(os.environ, SHOW=show, PUSH_ATTEMPTS=attempts)
    return subprocess.run(["bash", str(SCRIPT)], cwd=str(work), env=env,
                          capture_output=True, text=True)


def _advance_origin(seed: Path, path: str, content: str, message: str):
    """Simulate the concurrent writer (another job) landing first."""
    _git("pull", "--rebase", "origin", "main", cwd=seed)
    (seed / path).write_text(content)
    _git("add", "-A", cwd=seed)
    _git("commit", "-m", message, cwd=seed)
    _git("push", "origin", "main", cwd=seed)


class TestCleanPush:
    def test_pushes_when_nothing_else_moved(self, remote_and_clone):
        _, _, work = remote_and_clone
        (work / "digest.md").write_text("ep47\n")
        _git("add", "-A", cwd=work)
        _git("commit", "-m", "spacex ep47", cwd=work)

        result = _run_script(work)
        assert result.returncode == 0, result.stdout + result.stderr
        assert "Push succeeded" in result.stdout

    def test_rebases_over_an_unrelated_concurrent_commit(self, remote_and_clone):
        """The common case: another show pushed first, different files."""
        _, seed, work = remote_and_clone
        (work / "digest.md").write_text("ep47\n")
        _git("add", "-A", cwd=work)
        _git("commit", "-m", "spacex ep47", cwd=work)

        _advance_origin(seed, "other.txt", "tesla moved\n", "tesla ep519")

        result = _run_script(work)
        assert result.returncode == 0, result.stdout + result.stderr
        log = _git("log", "--oneline", "origin/main", cwd=work).stdout
        assert "spacex ep47" in log and "tesla ep519" in log


class TestTheIncident:
    """A conflicting *.video.rss — exactly what stranded Ep47."""

    def test_regenerable_conflict_resolves_instead_of_stranding(
            self, remote_and_clone):
        _, seed, work = remote_and_clone
        (work / "spacex_podcast.video.rss").write_text(
            "<rss>ours: ep47 added</rss>\n")
        _git("add", "-A", cwd=work)
        _git("commit", "-m", "spacex ep47", cwd=work)

        # The nightly's build_video_feeds.py --all rewrote the same file.
        _advance_origin(seed, "spacex_podcast.video.rss",
                        "<rss>nightly rebuild</rss>\n", "nightly feeds")

        result = _run_script(work)
        assert result.returncode == 0, (
            "the exact Ep47 conflict must no longer strand the episode\n"
            + result.stdout + result.stderr)
        assert "resolved regenerable conflict" in result.stdout

    def test_our_episode_survives_the_resolution(self, remote_and_clone):
        """Taking the wrong side of a rebase conflict is the subtle bug
        here: during a rebase --ours is UPSTREAM and --theirs is the
        commit being replayed. Getting it backwards would silently drop
        the new episode and still exit 0."""
        _, seed, work = remote_and_clone
        (work / "spacex_podcast.video.rss").write_text(
            "<rss>ours: ep47 added</rss>\n")
        _git("add", "-A", cwd=work)
        _git("commit", "-m", "spacex ep47", cwd=work)

        _advance_origin(seed, "spacex_podcast.video.rss",
                        "<rss>nightly rebuild</rss>\n", "nightly feeds")

        assert _run_script(work).returncode == 0
        _git("fetch", "origin", cwd=work)
        landed = _git("show", "origin/main:spacex_podcast.video.rss",
                      cwd=work).stdout
        assert "ep47" in landed, f"our episode was discarded: {landed!r}"


class TestRefusesToGuess:
    def test_unknown_conflict_is_not_auto_resolved(self, remote_and_clone):
        """A wrong auto-resolution is worse than a recovery PR, because
        nobody reviews a green run. Anything outside the regenerable
        list must fail out to the caller's recovery path."""
        _, seed, work = remote_and_clone
        (work / "other.txt").write_text("ours\n")
        _git("add", "-A", cwd=work)
        _git("commit", "-m", "spacex ep47", cwd=work)

        _advance_origin(seed, "other.txt", "theirs\n", "concurrent edit")

        result = _run_script(work)
        assert result.returncode == 1
        assert "UNRESOLVABLE conflict" in result.stdout
        assert "other.txt" in result.stdout

    def test_leaves_a_clean_tree_for_the_recovery_branch(self, remote_and_clone):
        """create_recovery_pr.sh checks out a new branch; a tree left
        mid-rebase would break it. The June 2026 mass-stranding came from
        exactly this — a dirty tree after a failed resolution."""
        _, seed, work = remote_and_clone
        (work / "other.txt").write_text("ours\n")
        _git("add", "-A", cwd=work)
        _git("commit", "-m", "spacex ep47", cwd=work)
        _advance_origin(seed, "other.txt", "theirs\n", "concurrent edit")

        _run_script(work)
        assert not (work / ".git" / "rebase-merge").exists()
        assert not (work / ".git" / "rebase-apply").exists()
        status = _git("status", "--porcelain", cwd=work).stdout
        assert "UU " not in status, f"unmerged paths remain: {status!r}"


class TestNoSilentDataLoss:
    def test_script_never_uses_dash_x_theirs(self):
        """``-X theirs`` silently discards one side of a real conflict.
        The old inline loop used it; on a shallow clone it never ran, so
        the danger was masked rather than absent.

        Checks executable lines only — the script's header explains why
        the flag is avoided, and a naive substring search flags that
        explanation as the very thing it warns against."""
        code = [ln for ln in SCRIPT.read_text().splitlines()
                if ln.strip() and not ln.strip().startswith("#")]
        assert not any("-X theirs" in ln for ln in code), [
            ln for ln in code if "-X theirs" in ln]

    def test_regenerable_list_stays_narrow(self):
        """Every pattern here has its conflicting content REPLACED. A
        file that is not genuinely rebuildable from committed state would
        lose data without a trace."""
        body = SCRIPT.read_text()
        start = body.index("is_regenerable()")
        block = body[start:body.index("}", start)]
        patterns = [ln.strip() for ln in block.splitlines()
                    if ln.strip().startswith("*") and "return 0" in ln]
        assert patterns == ["*.video.rss) return 0 ;;"], patterns


class TestWorkflowWiring:
    def test_workflow_calls_the_script(self):
        wf = (ROOT / ".github" / "workflows" / "run-show.yml").read_text()
        assert "scripts/push_show_artifacts.sh" in wf

    def test_the_dead_merge_fallback_is_gone(self):
        """It could never succeed under fetch-depth: 1 and cost four
        attempts plus 30s of sleeps on every conflict."""
        wf = (ROOT / ".github" / "workflows" / "run-show.yml").read_text()
        assert "refusing to merge unrelated histories" not in wf
        assert "git pull --no-rebase origin main -X theirs" not in wf

    def test_recovery_path_is_still_reachable(self):
        wf = (ROOT / ".github" / "workflows" / "run-show.yml").read_text()
        assert "create_recovery_pr.sh" in wf
        assert 'PUSH_SUCCEEDED' in wf
