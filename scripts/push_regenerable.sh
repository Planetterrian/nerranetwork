#!/usr/bin/env bash
# Push a commit of REGENERABLE pages (the homepage, gallery indexes) to main.
#
# Same rule as run-show.yml's finalize push: on a rebase conflict keep
# origin's copy (in a rebase, --ours is the upstream side, which may carry a
# newer regeneration from another job) — ours comes back on the next
# regeneration. A commit emptied by that resolution is skipped. Exits 1 after
# five failed attempts; the pages regenerate on the next finalize or nightly.
set -u

for attempt in 1 2 3 4 5; do
  if ! git pull --rebase origin main; then
    CONFLICTS=$(git diff --name-only --diff-filter=U || true)
    if [ -n "$CONFLICTS" ]; then
      echo "$CONFLICTS" | while IFS= read -r f; do
        git checkout --ours -- "$f" 2>/dev/null || true
        git add -- "$f" 2>/dev/null || true
      done
      GIT_EDITOR=true git rebase --continue \
        || GIT_EDITOR=true git rebase --skip \
        || git rebase --abort || true
    else
      git rebase --abort 2>/dev/null || true
    fi
  fi
  if git push origin main; then
    echo "Push succeeded on attempt $attempt"
    exit 0
  fi
  if [ "$attempt" -lt 5 ]; then
    sleep $((attempt * 3))
  fi
done
echo "::warning::Regenerated pages could not be pushed after 5 attempts; the next finalize or nightly regenerates them."
exit 1
