# Active issue 23 — GitHub push transients

Moved verbatim from CLAUDE.md "Active Issues" on 2026-11-24.

23. **GitHub push transients on large text commits ("fatal error in commit_refs")** —
    Successful episode generation (run_show.py) can produce 8k–10k+ line commits
    (full Whisper transcripts JSON+txt, _tts.txt, metrics, chapters, digests, blog
    HTML, RSS updates). GitHub's ref-update service occasionally returns a server
    error during `git push origin main` even after the pack is accepted. The
    4-attempt rebase/merge loop in `.github/workflows/run-show.yml` handles
    normal concurrency races between matrix jobs. On final exhaustion the step
    now calls `scripts/create_recovery_pr.sh` which creates a `recovery/<show>-<run_id>-<ts>`
    branch, pushes it, and opens a **draft PR** with the complete artifacts plus
    operator instructions. The job exits 0 (data preserved). The PR appears in
    the repo for the operator to merge. This is the hardened path for the
    "Commit and push output" step (the finalize shared-pages push has a 5-attempt
    loop + warning but no recovery PR because those pages are fully regenerable).
    The `safe-commit-push` composite now has an opt-in `recovery-on-failure`
    input wired for the two callers whose commits are expensive to regenerate
    (nightly maintenance, topic-queue restock); the other composite callers
    deliberately stay fail-visible because their artifacts are regenerable
    (stale note corrected 2026-08-15). The multilingual
    sweep's commit step (`.github/workflows/multilingual.yml`) also uses the
    recovery-PR escape hatch now, since it commits large translation-track +
    per-language-feed diffs on the same push-contended `main`. Drift guard:
    the recovery script + the warning annotation in the Actions log.
