#!/usr/bin/env bash
# Push one show's generated artifacts to main, surviving concurrent jobs.
#
# Incident, 28 July 2026 (SpaceX Ep47, run 30354757421): the rebase hit a
# content conflict in spacex_podcast.video.rss, the merge fallback failed
# four times with "fatal: refusing to merge unrelated histories", and the
# episode ended up stranded in recovery PR #892.
#
# Two separate defects, and the second is the one that mattered:
#
# 1. Ownership. The show job commits *.video.rss via `git add '*.rss'`,
#    and the nightly runs build_video_feeds.py --all, which rewrites
#    every video feed. Two writers, one file. The workflow already
#    documents this exact failure class for network.rss and blog.rss and
#    excludes them; *.video.rss behaves identically and was never added.
#
# 2. The merge fallback could never work. Checkout is fetch-depth: 1, so
#    a shallow clone has no common ancestor with the fetched tip and git
#    refuses outright. That branch has been dead since it was written —
#    every conflict, of any kind, went straight to a recovery branch
#    after four guaranteed-doomed attempts and 30s of sleeps.
#
# The fix here is to resolve rather than merge. The conflicting feeds are
# DETERMINISTIC: they rebuild exactly from digests/<slug>/video_assets.json
# and the summaries JSON, both of which merge cleanly because concurrent
# shows touch different files. So on conflict we take our side and
# regenerate, which is correct by construction rather than by luck.
#
# `-X theirs` is deliberately NOT used anywhere below. On a real conflict
# it silently discards one side, and "silently discards an episode" is
# strictly worse than "opens a recovery PR".
#
# Environment:
#   SHOW           show slug, used to regenerate its feed after a resolve
#   PUSH_ATTEMPTS  optional, default 4
#
# Exit status: 0 when the push landed, 1 when the caller should fall back
# to the recovery-branch path.

set -uo pipefail

SHOW="${SHOW:-}"
ATTEMPTS="${PUSH_ATTEMPTS:-4}"

# Files git cannot three-way merge but this repo can rebuild from
# committed state. Keep this list tight: anything listed here has its
# conflicting content REPLACED, so a file that is not truly regenerable
# would lose data silently.
is_regenerable() {
  case "$1" in
    *.video.rss) return 0 ;;
    *) return 1 ;;
  esac
}

# Rebuild the feeds we resolved by fiat, so the committed bytes match
# what a clean run would produce rather than whichever side won.
regenerate_feeds() {
  [ -n "$SHOW" ] || return 0
  if [ -f scripts/build_video_feeds.py ]; then
    python scripts/build_video_feeds.py "$SHOW" >/dev/null 2>&1 || true
    git add -- '*.video.rss' 2>/dev/null || true
  fi
}

# Returns 0 only when EVERY conflicted path was regenerable. A single
# unknown conflict means we must not continue — a wrong auto-resolution
# is worse than a recovery PR, because nobody reviews a green run.
resolve_conflicts() {
  local conflicted
  conflicted="$(git diff --name-only --diff-filter=U)"
  [ -n "$conflicted" ] || return 1

  local unresolved=0 f
  while IFS= read -r f; do
    [ -n "$f" ] || continue
    if is_regenerable "$f"; then
      # During a rebase, --theirs is the commit being replayed (ours),
      # and --ours is upstream. The naming is inverted from intuition;
      # we want the version carrying this run's new episode.
      git checkout --theirs -- "$f" 2>/dev/null \
        || git checkout --ours -- "$f" 2>/dev/null || true
      git add -- "$f" 2>/dev/null || true
      echo "  resolved regenerable conflict: $f"
    else
      echo "  UNRESOLVABLE conflict: $f"
      unresolved=1
    fi
  done <<< "$conflicted"

  [ "$unresolved" -eq 0 ]
}

for attempt in $(seq 1 "$ATTEMPTS"); do
  if git pull --rebase origin main; then
    if git push origin main; then
      echo "Push succeeded on attempt $attempt (rebase)"
      exit 0
    fi
  else
    echo "Rebase hit a conflict on attempt $attempt — inspecting..."
    if resolve_conflicts; then
      regenerate_feeds
      if GIT_EDITOR=true git rebase --continue; then
        if git push origin main; then
          echo "Push succeeded on attempt $attempt (rebase + regenerated feeds)"
          exit 0
        fi
      else
        echo "rebase --continue failed — aborting to a clean tree"
        git rebase --abort 2>/dev/null || true
      fi
    else
      echo "Conflict is not auto-resolvable — aborting rebase"
      git rebase --abort 2>/dev/null || true
    fi
  fi

  if [ "$attempt" -lt "$ATTEMPTS" ]; then
    echo "Push failed on attempt $attempt, retrying in $((attempt * 5))s..."
    sleep $((attempt * 5))
  fi
done

echo "All direct push attempts to main exhausted."
exit 1
