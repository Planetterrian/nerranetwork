-- Oct 24 2026: the Supabase clock for the nerra-voices-api Worker.
--
-- pg_cron posts POST /voices/cron-tick one minute after each of Cloudflare's
-- five-minute slots (1-59/5). When Cloudflare is healthy it has already
-- claimed the slot in cron_ticks and this call does nothing; when Cloudflare's
-- timer has stopped, this call runs the tick (and the Worker's watchdog tells
-- Patrick). The GitHub schedule on nerra_voices_fire_interview.yml stays the
-- third clock.
--
-- The bearer secret lives only in Supabase Vault (voices_cron_tick_secret) and
-- in the Worker's secrets (CRON_TICK_SECRET), never in git. Until both are
-- set the Worker answers 401 and nothing runs from this clock.
--
-- Apply after 20261024_cron_ticks.sql and after the Worker with
-- /voices/cron-tick is deployed.

create extension if not exists pg_cron;
create extension if not exists pg_net;

-- Re-runnable: drop the jobs by name before scheduling them again.
select cron.unschedule(jobid) from cron.job
 where jobname in ('voices-backup-tick', 'voices-backup-clock-cleanup');

select cron.schedule(
  'voices-backup-tick',
  '1-59/5 * * * *',
  $$
  select net.http_post(
    url := 'https://api.nerranetwork.com/voices/cron-tick',
    headers := jsonb_build_object(
      'Content-Type', 'application/json',
      'Authorization', 'Bearer ' || coalesce(
        (select decrypted_secret from vault.decrypted_secrets where name = 'voices_cron_tick_secret'), '')),
    body := '{"source":"supabase-pg-cron"}'::jsonb,
    timeout_milliseconds := 25000
  )
  $$
);

-- Daily: claimed slots are kept 14 days (health and the watchdog read the last
-- 20 minutes), pg_cron's own run log 7.
select cron.schedule(
  'voices-backup-clock-cleanup',
  '17 4 * * *',
  $$
  delete from public.cron_ticks where slot < now() - interval '14 days';
  delete from cron.job_run_details where end_time < now() - interval '7 days';
  $$
);
