# nerra-scheduler — exact-time show dispatcher

GitHub Actions delivers `schedule` events best-effort (observed 1–6 h late,
May–June 2026; Tesla's 11:00 UTC cron started at 13:54 on June 9). Cloudflare
Cron Triggers fire to the minute. This Worker dispatches each show's
`Run Podcast Show` run via `workflow_dispatch` at its intended slot.

**Every slot is EASTERN wall time** (Oct 17 2026, operator-directed:
Nerra Daily is out by 7:00 AM New York). `SLOTS` rows are
`[etHour, etMinute, show, dayFilter]` on `SLOT_TZ = "America/New_York"`;
the handler converts each firing to Eastern time and the day filters read
the Eastern date, so the 1 November and March clock changes move nothing.
The Nerra Daily edition (`EDITION_DISPATCH`, 06:35 / 06:50 ET) and the
@nerranetwork X queue (`X_QUEUE_DISPATCH`, :05 / :35 from 7:05 AM to
10:05 PM ET) read the same clock. The Worker's ONE cron trigger is
`*/5 * * * *` (Workers Free: five triggers per account, Voices holds three);
every Eastern minute it needs is a multiple of five, which is a multiple of
five in UTC under both offsets.

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
   of its Eastern slot (`GET /` shows `next_slot.et`).

## Verifying a deploy (do this instead of waiting for a slot)

The Worker answers HTTP on its workers.dev URL (Cloudflare dashboard →
Workers & Pages → nerra-scheduler → the `*.workers.dev` link, or
`wrangler deployments list`):

- `GET /` — config, the slot table (each row `{"at": "05:45", "tz":
  "America/New_York", "show": ..., "filter": ...}`), and `next_slot` (what
  should fire next, in UTC and Eastern).
- `GET /health` — the same plus a **live, read-only GitHub probe** with
  the stored token. `ok: true` means the token authenticates AND has the
  Actions permission `workflow_dispatch` needs. It never dispatches.

| `/health` result | Meaning | Fix |
|---|---|---|
| `github_status: 200`, `ok: true` | Deployed and able to dispatch | — (watch the next slot) |
| `github_status: 401` | Stored token rejected | Expired PAT, or a **trailing newline pasted into `wrangler secret put`** — re-put the secret (the Worker now trims whitespace, but re-put anyway if it predates that) |
| `github_status: 403` / `404` | Token lacks **Actions: Read and write** on the repo | A Contents-only PAT (the voices Worker's scope) lands here — edit the PAT's repository permissions |
| `token_present: false` | Secret never set on this Worker | `wrangler secret put GITHUB_DISPATCH_TOKEN` |

Live tail during a slot: `wrangler tail nerra-scheduler --format pretty`.
The dashboard's **Cron Triggers → past events** list also shows whether
each slot fired and whether the handler threw.

PAT permissions, for the record: this Worker calls `workflow_dispatch`
(needs **Actions: Read and write**); `workers/voices` calls
`repository_dispatch` (needs **Contents: Read and write**). One
fine-grained PAT carrying both is fine for both Workers.

## Keeping it in sync

**What fires is what was last deployed, not what is committed.** On
2026-09-24 a redeploy from a checkout that predated the launch-cohort PR
left nine new shows off the live slot table; the cron string already
covered their hours, so the deploy output looked right and only the
dispatch pattern gave it away (every old slot fired on the minute, no
new one did). Always `git pull` on `main` before `npx wrangler deploy`,
then open `GET /` and count the `slots`. The daily audit runs
`scripts/check_scheduler_deploy.py`, which diffs the live table against
`src/index.ts` once the repo variable `SCHEDULER_STATUS_URL` holds the
Worker's `*.workers.dev` URL (Settings → Secrets and variables → Actions →
Variables). Until it is set the check is a one-line no-op.

The dispatcher honours `FIRST_RUN` (a show's first scheduled date) the same
way `next_slot` does; before 2026-09-24 only the status page did, and a
`workflow_dispatch` bypasses the workflow's own launch-date gate by design.


`SLOTS` in `src/index.ts` mirrors `CRON_MAP` in
`.github/workflows/run-show.yml`. The GitHub fallback crons are UTC and
cannot follow daylight saving, so each is the slot's EST equivalent
(ET + 5 h) — in summer it fires an hour after the Worker and the gate's
duplicate guard drops it. `tests/test_scheduling_punctuality.py` parses
both and compares them at the EST offset, failing CI on drift. When
changing the schedule, update both + redeploy the Worker. A Worker still
deployed from before Oct 17 2026 answers UTC rows (`"09:16Z"`); the deploy
check names that clock and asks for a redeploy.
