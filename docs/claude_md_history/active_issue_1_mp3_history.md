# Active issue 1 — MP3s in git history

Moved verbatim from CLAUDE.md "Active Issues" on 2026-11-24.

1. **2.2 GB of MP3s in git HISTORY (HEAD is clean)** — measured June 10
   2026: zero episode MP3s are tracked at HEAD (guards in `.gitignore` +
   the commit step's `git reset -- '*.mp3'`; only the 43 MB of
   `assets/music` themes + two voice-reference WAVs remain, which the
   pipeline needs). All enclosure URLs serve from R2. CI clones are
   shallow since the June 2026 workflow pass (~115 MB packed vs ~2.5 GB
   full), so the day-to-day clone cost is FIXED and growth is now
   text-only (~50 MB/month → years of headroom under GitHub's 10 GB
   limit). The history weight itself can only be removed by a
   `git filter-repo` rewrite + force-push of main — DESTRUCTIVE:
   requires a paused-cron window (12 daily workflows push to main and
   could race the force-push and resurrect old history), invalidates
   every existing clone, and dangles the commit SHAs referenced across
   docs/. Playbook in
   [`docs/workflow_review_2026_06_10.md`](docs/workflow_review_2026_06_10.md);
   operator-scheduled, not urgent. For full local clones meanwhile:
   `git clone --filter=blob:none` skips historical blobs.
