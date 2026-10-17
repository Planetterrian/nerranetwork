#!/usr/bin/env bash
# Audio-first checkpoint: push a show's episode before its video renders.
#
# Oct 17 2026. A run used to commit once, at the very end, so an episode
# reached main ~35 minutes after its run started even though the audio, the
# feed, the summaries and the blog post were done in ~15 — the long-form
# render and the uploads were the other twenty. run_show.py calls this
# between the two halves when NERRA_AUDIO_FIRST_PUSH=1.
#
# The commit message carries the same "Auto-generated: <show> <date>" prefix
# the workflow's final commit uses, so the same-day duplicate guard sees the
# episode as published from this moment. The final commit step still runs and
# pushes whatever the video half adds.
#
# Environment:
#   SHOW  show slug (the workflow's matrix.show)
#
# Exit status: 0 when the checkpoint landed or there was nothing to push,
# non-zero when the push failed (the caller logs it; nothing is lost).

set -uo pipefail

SHOW="${SHOW:?SHOW is required}"

git config --local user.name "github-actions[bot]"
git config --local user.email "github-actions[bot]@users.noreply.github.com"

bash scripts/stage_show_artifacts.sh

if git diff --cached --quiet; then
  echo "Nothing to checkpoint."
  exit 0
fi

git commit -q -m "Auto-generated: ${SHOW} $(date -u +%Y-%m-%d) (audio)"

# The run is still writing files (metrics, the video half's outputs), so the
# tree is not clean the way it is at the final commit. Autostash for this one
# pull, scoped to this process, so the rebase can replay the checkpoint onto
# the latest main and hand the working files back untouched.
export GIT_CONFIG_COUNT=1
export GIT_CONFIG_KEY_0=rebase.autoStash
export GIT_CONFIG_VALUE_0=true
if SHOW="$SHOW" PUSH_ATTEMPTS="${PUSH_ATTEMPTS:-3}" bash scripts/push_show_artifacts.sh; then
  exit 0
fi

# Un-commit, keep everything staged: the final commit step commits only when
# something is staged, so an unpushed checkpoint commit left here would never
# be pushed at all.
git rebase --abort 2>/dev/null || true
git reset -q --soft HEAD~1
echo "Checkpoint push failed; left staged for the final commit."
exit 1
