# The Voices Worker has a backup clock (Oct 24 2026)

Moved verbatim from CLAUDE.md on 2026-11-03; the rules that still bind are summarised there.

### The Voices Worker has a backup clock (Oct 24 2026)

`nerra-voices-api`'s one Cloudflare cron stopped at 17:15 UTC on Oct 23 and
stayed dead 23 hours (Cloudflare's fourth cron incident in ten days; not
revived by a redeploy or a same-expression re-add — re-registered as
`0-59/5 * * * *`, which stays). A guest's T-2h reminder never went out. Doc
[`docs/voices_backup_clock.md`](docs/voices_backup_clock.md); guards
`tests/test_voices_backup_clock_2026_10_24.py`,
`workers/voices/test/backup_clock.test.ts`. Rules that bind: **`scheduled()`
is only `runTick(env, scheduledTime, "cloudflare")`**; Supabase pg_cron posts
`POST /voices/cron-tick` (`Bearer CRON_TICK_SECRET`, never ADMIN_TOKEN) at
`1-59/5` and runs `runTick(..., "supabase")`. **A tick claims its five-minute
slot in `cron_ticks` first** (ignore-duplicates insert; empty = another clock
ran it; Supabase unreachable = run anyway), and **every minute decision reads
the slot, never the arrival time** — the backup at 17:01 runs the 17:00 gate-2
job, and the claim is what stops its day-4 reminder going out twice. A new
timed job goes inside `runTick` and keys on `slot`. The watchdog
(`cron_clock_state`, never memory) alerts once per outage when a supabase
claim finds no cloudflare claim in 20 minutes, and once when Cloudflare is
back. The secret lives only in Supabase Vault (`voices_cron_tick_secret`) and
the Worker's secrets. GitHub's schedule on `nerra_voices_fire_interview.yml`
stays the third clock. Operator: apply `20261024_cron_ticks.sql`, deploy the
Worker, set the secret in both places, apply `20261024_voices_backup_clock.sql`.
