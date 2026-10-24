# The Voices Worker's backup clock (Oct 24 2026)

The `nerra-voices-api` Worker runs a five-minute tick that:

- fires interviews;
- sends guest reminders (including the T-2h one);
- runs Mira's inbox (:00/:30);
- does gate-2 housekeeping (17:00 UTC).

Until Oct 24 that tick had one clock: Cloudflare's cron. Its `*/5 * * * *` trigger stopped firing at about 17:15 UTC on Oct 23, during Cloudflare's cron incident, and stayed dead for 23 hours. Nothing brought it back:

- the incident being resolved;
- a redeploy;
- deleting and re-adding the schedule with the same expression.

What it cost: Stuart Berkowitz's T-2h reminder never went out, the producer inbox ran every few hours instead of every half hour, and the late alerts stopped. `nerra-scheduler`'s own `*/5`, in the same account, fired the whole time. Re-registering the trigger as `0-59/5 * * * *` brought it back at the next slot. It was Cloudflare's fourth cron incident in ten days (Oct 13, 14, 16, 23).

## How it works

There is one tick and there are three clocks.

| clock | when | how |
|---|---|---|
| Cloudflare cron | `0-59/5 * * * *` (:00, :05, …) | `scheduled()` → `runTick(env, scheduledTime, "cloudflare")` |
| Supabase pg_cron | `1-59/5 * * * *` (:01, :06, …) | `POST /voices/cron-tick` with `Bearer CRON_TICK_SECRET` → `runTick(env, now, "supabase")` |
| GitHub Actions | the schedule on `nerra_voices_fire_interview.yml` | unchanged; fires the interviews only, late under load |

**`runTick` first claims its five-minute slot.**

- The slot is the firing time floored to five minutes UTC.
- Claiming means an insert into `cron_ticks` (primary key `slot`). When the result is empty, another clock already ran that slot, and nothing runs.
- When Cloudflare is healthy it claims each slot first, so the backup a minute later does nothing.
- Every minute-based decision reads the slot, never the arrival time: the :00/:30 inbox and the 17:00 gate-2 job. A backup call at 17:01 therefore runs the 17:00 jobs, and the claim keeps gate-2's day-4 reminder from being emailed twice.
- If Supabase cannot be reached to make the claim, the tick runs anyway.

**The watchdog.**

- Trigger: a supabase tick claims a slot, and no cloudflare tick has claimed one in the last 20 minutes.
- It then opens the outage in `cron_clock_state` and alerts Patrick once, on Slack and by email from Mira: "Cloudflare's timer has stopped; the backup clock is carrying reminders."
- When a cloudflare tick claims a slot again, it closes the outage and sends "Cloudflare's timer is back." once.
- The state lives in Supabase, not in the Worker's memory.

**`/voices/health`** shows:

- `configured.cron_tick_secret`;
- the last slot each clock claimed (`clocks.cloudflare`, `clocks.supabase`);
- the outage state (`clocks.cloudflare_outage`).

## Deploying it (Patrick)

Order matters a little. If the Worker is deployed before the tables exist, its claim fails and every tick runs as it did before: nothing is lost, but nothing is deduplicated yet.

1. **Apply the tables.** Run `supabase/migrations/20261024_cron_ticks.sql`, in the SQL editor or by `supabase db push`.
2. **Deploy the Worker.** Push the branch, merge, then run `npx wrangler deploy` in `workers/voices`. Keep `crons = ["0-59/5 * * * *"]` in `wrangler.toml`.
3. **Set the secret in both places.** The value was generated with `openssl rand -hex 32` and handed over outside git. It is never committed.
   - `npx wrangler secret put CRON_TICK_SECRET` in `workers/voices`, then paste the value.
   - In the Supabase SQL editor: `select vault.create_secret('<value>', 'voices_cron_tick_secret');`
4. **Start the Supabase clock.** Run `supabase/migrations/20261024_voices_backup_clock.sql`. It creates `pg_cron` and `pg_net`, the `voices-backup-tick` job and the daily `voices-backup-clock-cleanup` job. The cleanup keeps `cron_ticks` for 14 days and `cron.job_run_details` for 7.

## Checks after deploying

**1. A wrong token is refused.** Expect `401` from both of these:

```sh
curl -s -o /dev/null -w '%{http_code}\n' -X POST https://api.nerranetwork.com/voices/cron-tick \
     -H 'Authorization: Bearer wrong'
curl -s -o /dev/null -w '%{http_code}\n' -X POST https://api.nerranetwork.com/voices/cron-tick
```

**2. The health page.** Run `curl -s https://api.nerranetwork.com/voices/health`. Expect `configured.cron_tick_secret: true`, and once ticks have run, a recent `clocks.cloudflare.slot`.

**3. After 30 minutes, in the Supabase SQL editor:**

```sql
-- pg_cron ran the job every five minutes, and it succeeded
select start_time, status, return_message
  from cron.job_run_details
 where jobid = (select jobid from cron.job where jobname = 'voices-backup-tick')
 order by start_time desc limit 6;

-- the Worker answered 200: {"slot": ..., "ran": false} while Cloudflare is healthy
select created, status_code, left(content, 120) as body
  from net._http_response order by created desc limit 6;

-- each slot claimed once; with Cloudflare healthy every row reads cloudflare
select slot, source, claimed_at from public.cron_ticks order by slot desc limit 12;
```

A healthy result:

- six `succeeded` runs;
- `status_code` 200 with `"ran":false`;
- `cron_ticks` holding one row per five minutes, all from `cloudflare`.

To test the backup itself, insert nothing. Instead, wait for a slot that Cloudflare misses, or test it deliberately in a quiet hour:

1. Pause the Cloudflare trigger in the dashboard for 25 minutes.
2. Watch `supabase` rows appear, and one "Cloudflare's timer has stopped" alert.
3. Resume the trigger, and watch for one "Cloudflare's timer is back".

**Deadline.** Have this live before Elliot Justin's interview on Monday Oct 26 at 20:00 UTC. His T-2h reminder is due around 18:00 UTC.
