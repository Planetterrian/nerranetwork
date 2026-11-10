# Purging the guest material (and the old MP3s) from git history

Operator decision, Nov 10 2026 (project audit, item 1a). PR #1678 removed
`Claude outputs/`, `_claude/` and `quota_screenshots/` from HEAD; every byte
of them is still readable in old commits of this public repo. This is the
runbook for removing them from history. It is destructive and runs once, in a
quiet window, with the operator present.

## What a rewrite does and does not reach

- **Reaches:** every branch and tag. All commit SHAs change.
- **Does not reach:** pull-request refs (`refs/pull/*`) and GitHub's cached
  views. The diffs of the PRs that added or removed those files (including
  #1678) keep serving them until **GitHub Support** removes them. Without
  that request the rewrite only hides the files from `git clone`.
- **Breaks:** every existing clone (re-clone, or `git fetch && git reset
  --hard origin/main` on a clean one), and commit SHAs quoted in `docs/`.
- **Optional, same window:** `--include-mp3` also drops the 2.2 GB of episode
  MP3s from history (CLAUDE.md Active Issue #1). One disruption instead of
  two. `assets/music/` is never touched; R2 enclosure URLs are unaffected.

## The window

Shows run between about 03:00 and 06:30 Eastern, Nerra Daily releases at
07:00, and the video jobs and multilingual sweep follow through the morning.
The quietest stretch is late evening Eastern (21:00–01:00). The script
disables every active workflow, waits for running ones to finish, rewrites
again to catch anything pushed meanwhile, force-pushes, and re-enables the
same workflows on exit (even on failure). Cloudflare scheduler dispatches
that land on a disabled workflow fail harmlessly and the GitHub fallback
crons cover the next slot.

## Steps

1. **Dry run** (anytime, changes nothing remote):
   `scripts/purge_history.sh` (add `--include-mp3` to size the MP3 purge).
   It prints the pack size before and after and the guest paths it found.
2. **In the window:** `scripts/purge_history.sh --push [--include-mp3]`,
   from a machine where `gh` is logged in as a repo admin (a pushed rewrite
   touches workflow files, which the Actions token may not push). If `main`
   has a rule that blocks force-pushes, allow it for the window.
3. **GitHub Support:** open a request at
   <https://support.github.com/contact> ("Remove sensitive data") asking them
   to remove cached views and the pull-request references that still contain
   `Claude outputs/`, `_claude/` and `quota_screenshots/`, naming the PRs
   that touched them (#1678 and the PRs that added the files; `git log --all
   -- "Claude outputs" _claude` in a pre-purge clone lists them).
4. **Every clone re-clones**, including the Mac's working copy and the
   Cowork handoff folder (copy local-only files out first; both folders are
   gitignored now).

Guards: none in CI by design; the script refuses to push while any guest
path is left in the rewritten history.
