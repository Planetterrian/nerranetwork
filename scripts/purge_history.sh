#!/usr/bin/env bash
# Remove paths from the WHOLE git history of the public repo and force-push.
#
# Nov 10 2026 audit, operator decision 1a: guest interview material
# (`Claude outputs/`, `_claude/`) and `quota_screenshots/` were tracked in this
# public repo until PR #1678; removing them from HEAD left every byte readable
# in old commits. With --include-mp3 the same rewrite also drops the 2.2 GB of
# episode MP3s in history (CLAUDE.md Active Issue #1; the playbook in
# docs/workflow_review_2026_06_10.md). `assets/music/` is never touched.
#
# DESTRUCTIVE when run with --push: every commit SHA changes, every clone must
# re-clone, and a show run that pushes during the window resurrects the old
# history. Full runbook: docs/history_purge_2026_11.md. Dry run by default.
#
# Needs: git, git-filter-repo (pip install git-filter-repo), gh (logged in as
# a repo admin), ~6 GB free disk.
set -euo pipefail

REPO="Planetterrian/nerranetwork"
PUSH=0
INCLUDE_MP3=0
WORK="${TMPDIR:-/tmp}/nerranetwork-purge"
for arg in "$@"; do
  case "$arg" in
    --push) PUSH=1 ;;
    --include-mp3) INCLUDE_MP3=1 ;;
    *) echo "unknown argument: $arg" >&2; exit 2 ;;
  esac
done

command -v git-filter-repo >/dev/null || { echo "install git-filter-repo first" >&2; exit 1; }
command -v gh >/dev/null || { echo "install and log in to gh first" >&2; exit 1; }

PATHS=(--path "Claude outputs/" --path "_claude/" --path "quota_screenshots/")
if [ "$INCLUDE_MP3" = 1 ]; then
  PATHS+=(--path-glob 'digests/*.mp3' --path-glob 'digests/**/*.mp3')
fi

echo "== Fresh mirror clone into $WORK"
rm -rf "$WORK"
git clone --mirror "https://github.com/$REPO.git" "$WORK"
cd "$WORK"
# Pull-request refs are read-only on GitHub and cannot be rewritten from here;
# drop them locally so filter-repo and the push only see branches and tags.
git for-each-ref --format='delete %(refname)' refs/pull | git update-ref --stdin || true

echo "== Before"
git count-objects -vH | grep size-pack
git log --all --format= --name-only -- "Claude outputs" _claude quota_screenshots | sort -u | sed 's/^/  /' | head -50

git filter-repo --force --invert-paths "${PATHS[@]}"

echo "== After"
git gc --prune=now --aggressive >/dev/null 2>&1 || git gc --prune=now
git count-objects -vH | grep size-pack
left=$(git log --all --format= --name-only -- "Claude outputs" _claude quota_screenshots | sort -u | wc -l)
echo "  guest paths left in history: $left"
[ "$left" = 0 ] || { echo "paths remain; not pushing" >&2; exit 1; }

if [ "$PUSH" != 1 ]; then
  echo "Dry run: nothing pushed. Re-run with --push inside the quiet window."
  exit 0
fi

echo "== Pausing every active workflow"
gh workflow list --repo "$REPO" --json id,state --jq '.[] | select(.state=="active") | .id' > paused_workflows.txt
while read -r id; do gh workflow disable "$id" --repo "$REPO"; done < paused_workflows.txt
trap 'echo "== Re-enabling workflows"; while read -r id; do gh workflow enable "$id" --repo "$REPO" || true; done < "$WORK/paused_workflows.txt"' EXIT

echo "== Waiting for running workflow runs to finish (max 40 min)"
for _ in $(seq 1 80); do
  n=$(gh run list --repo "$REPO" --status in_progress --json databaseId --jq length)
  q=$(gh run list --repo "$REPO" --status queued --json databaseId --jq length)
  [ "$n" = 0 ] && [ "$q" = 0 ] && break
  echo "  $n running, $q queued"; sleep 30
done

echo "== Re-applying the rewrite to anything pushed since the clone"
git fetch "https://github.com/$REPO.git" '+refs/heads/*:refs/heads/*' '+refs/tags/*:refs/tags/*'
git filter-repo --force --invert-paths "${PATHS[@]}"

echo "== Force-pushing branches and tags"
git remote add purge-origin "https://github.com/$REPO.git" 2>/dev/null || true
git push --force purge-origin 'refs/heads/*:refs/heads/*' 'refs/tags/*:refs/tags/*'
echo "Done. Next: the GitHub Support request in docs/history_purge_2026_11.md."
