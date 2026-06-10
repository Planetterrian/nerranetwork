# nerra-scheduler — exact-time show dispatcher

GitHub Actions delivers `schedule` events best-effort (observed 1–6 h late,
May–June 2026; Tesla's 11:00 UTC cron started at 13:54 on June 9). Cloudflare
Cron Triggers fire to the minute. This Worker dispatches each show's
`Run Podcast Show` run via `workflow_dispatch` at its intended slot.

The GitHub crons in `run-show.yml` stay enabled as the delayed fallback;
the gate's same-day duplicate guard (it checks for today's
`Auto-generated: <show> <date>` commit) ensures the two drivers never
double-publish. If this Worker is down, episodes still ship — just late,
exactly as today.

## One-time setup (operator)

1. Create a **fine-grained PAT**: repo `Planetterrian/nerranetwork`,
   permission **Actions: Read and write** only. 1-year expiry; calendar
   reminder to rotate.
2. `cd workers/scheduler`
3. `wrangler secret put GITHUB_DISPATCH_TOKEN` (paste the PAT)
4. `wrangler deploy`
5. Verify next slot in the Cloudflare dashboard (Workers → nerra-scheduler
   → Logs) and confirm the corresponding workflow run starts within ~1 min
   of :07/:37.

## Keeping it in sync

`SLOTS` in `src/index.ts` mirrors `CRON_MAP` in
`.github/workflows/run-show.yml`. `tests/test_scheduling_punctuality.py`
parses both and fails CI on drift. When changing the schedule, update both
+ redeploy the Worker.
