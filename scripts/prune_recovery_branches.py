#!/usr/bin/env python3
"""Delete merged ``recovery/*`` branches, and alarm on stranded ones.

Where these come from
---------------------
When a show's artifact push exhausts its retry loop (landmine #23 —
GitHub's ref-update service intermittently fails on the 8k-10k line
commits a successful episode produces), ``scripts/create_recovery_pr.sh``
parks the episode on a ``recovery/<show>-<run_id>-<ts>`` branch and opens
a draft PR so no work is lost. The job then exits 0.

The gap this closes
-------------------
Nothing ever cleaned those branches up, so merged ones accumulate
indefinitely, and — much worse — an UNMERGED one is a **stranded
episode**: audio, transcript and feed updates that were generated, paid
for, and never published. Nobody was watching for that.

So:
  * a recovery branch whose tip is already an ancestor of the default
    branch has served its purpose and is deleted;
  * one that is NOT merged and is older than the grace period is
    reported as a ``::warning::`` naming the show, because that is an
    episode sitting in limbo.

Deletion is deliberately narrow: only branches matching ``recovery/``
whose commits are provably already on the default branch. An unmerged
branch is never deleted by this script under any circumstance — losing a
stranded episode is the exact failure it exists to prevent.

Usage::

    python scripts/prune_recovery_branches.py             # report only
    python scripts/prune_recovery_branches.py --apply     # delete merged
"""

from __future__ import annotations

import argparse
import datetime as dt
import re
import subprocess
import sys

BRANCH_PREFIX = "recovery/"
DEFAULT_STRANDED_HOURS = 24

# recovery/<show>-<run_id>-<unix_ts>
_BRANCH_RE = re.compile(r"^recovery/(?P<show>.+)-(?P<run>\d+)-(?P<ts>\d+)$")


def _git(*args: str) -> str:
    return subprocess.run(
        ["git", *args], capture_output=True, text=True, check=True,
    ).stdout.strip()


def remote_recovery_branches() -> list[str]:
    out = _git("ls-remote", "--heads", "origin", f"{BRANCH_PREFIX}*")
    branches = []
    for line in out.split("\n"):
        if not line.strip():
            continue
        parts = line.split("\t")
        if len(parts) == 2 and parts[1].startswith("refs/heads/"):
            branches.append(parts[1][len("refs/heads/"):])
    return sorted(branches)


def is_merged(branch: str, base: str) -> bool:
    """True when *branch*'s tip is already an ancestor of *base*.

    ``merge-base --is-ancestor`` is the authoritative check: it is true
    for a fast-forward, a merge commit, AND a squash-merge that kept the
    original commit reachable. When the ref cannot be resolved we return
    False — refusing to delete on uncertainty is the safe direction.
    """
    try:
        tip = _git("rev-parse", f"refs/remotes/origin/{branch}")
    except subprocess.CalledProcessError:
        return False
    try:
        subprocess.run(
            ["git", "merge-base", "--is-ancestor", tip, base],
            capture_output=True, check=True,
        )
        return True
    except subprocess.CalledProcessError:
        return False


def branch_age_hours(branch: str, now: dt.datetime) -> float | None:
    """Age from the timestamp the branch name carries, else from its tip."""
    match = _BRANCH_RE.match(branch)
    if match:
        try:
            created = dt.datetime.fromtimestamp(
                int(match.group("ts")), dt.timezone.utc)
            return (now - created).total_seconds() / 3600
        except (ValueError, OSError, OverflowError):
            pass
    try:
        when = int(_git("log", "-1", "--format=%ct",
                        f"refs/remotes/origin/{branch}"))
        created = dt.datetime.fromtimestamp(when, dt.timezone.utc)
        return (now - created).total_seconds() / 3600
    except (subprocess.CalledProcessError, ValueError):
        return None


def show_of(branch: str) -> str:
    match = _BRANCH_RE.match(branch)
    return match.group("show") if match else branch[len(BRANCH_PREFIX):]


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--apply", action="store_true",
                    help="Delete merged branches (default: report only)")
    ap.add_argument("--base", default="origin/main",
                    help="Branch the recovery work must have reached")
    ap.add_argument("--stranded-hours", type=float,
                    default=DEFAULT_STRANDED_HOURS,
                    help="Warn about unmerged branches older than this")
    args = ap.parse_args(argv)

    branches = remote_recovery_branches()
    if not branches:
        print("No recovery/* branches on origin — nothing to do.")
        return 0

    print(f"{len(branches)} recovery branch(es) on origin\n")
    now = dt.datetime.now(dt.timezone.utc)

    merged, stranded, young = [], [], []
    for branch in branches:
        if is_merged(branch, args.base):
            merged.append(branch)
            continue
        age = branch_age_hours(branch, now)
        if age is not None and age >= args.stranded_hours:
            stranded.append((branch, age))
        else:
            young.append((branch, age))

    for branch in merged:
        print(f"  merged     {branch}")
    for branch, age in young:
        age_txt = f"{age:.1f}h" if age is not None else "age unknown"
        print(f"  in flight  {branch}  ({age_txt})")
    for branch, age in stranded:
        print(f"  STRANDED   {branch}  ({age:.1f}h)")

    # A stranded recovery branch means a generated, paid-for episode was
    # never published. That is worth an annotation someone will see.
    for branch, age in stranded:
        print(
            f"::warning::Stranded recovery branch {branch} "
            f"({show_of(branch)}) is {age:.0f}h old and not merged into "
            f"{args.base}. Its episode artifacts were generated but never "
            f"published — merge or close the recovery PR.",
            flush=True,
        )

    if not merged:
        print("\nNo merged recovery branches to delete.")
        return 0

    if not args.apply:
        print(f"\nDry run — would delete {len(merged)} merged branch(es). "
              "Pass --apply to delete.")
        return 0

    failures = 0
    for branch in merged:
        try:
            _git("push", "origin", "--delete", branch)
            print(f"deleted {branch}")
        except subprocess.CalledProcessError as exc:
            failures += 1
            print(f"could not delete {branch}: {exc}", file=sys.stderr)

    print(f"\nDeleted {len(merged) - failures} of {len(merged)} merged branch(es).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
