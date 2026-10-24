-- Oct 24 2026: one tick, two clocks (workers/voices/src/index.ts runTick).
--
-- The nerra-voices-api Worker's one cron trigger stopped firing at about
-- 17:15 UTC on Oct 23, during Cloudflare's cron incident, and stayed dead for
-- 23 hours. The tick now runs from whichever clock claims its five-minute
-- slot first: Cloudflare's cron, or Supabase's pg_cron posting
-- /voices/cron-tick one minute later (20261024_voices_backup_clock.sql). A
-- claim is an insert here; a duplicate slot means another clock already ran
-- it, which is what keeps gate-2's day-4 reminder from going out twice.
--
-- RLS on, no policies: only the Worker's service key reads or writes.

create table if not exists public.cron_ticks (
  slot       timestamptz primary key,
  source     text not null check (source in ('cloudflare', 'supabase', 'manual')),
  claimed_at timestamptz not null default now()
);
alter table public.cron_ticks enable row level security;
create index if not exists cron_ticks_source_slot on public.cron_ticks (source, slot desc);

-- The watchdog's state, kept here rather than in the Worker's memory: an
-- outage is open while outage_since is set. The Worker opens it with a PATCH
-- that only matches while it is closed, so exactly one tick sends the alert,
-- and a cloudflare claim closes it the same way.
create table if not exists public.cron_clock_state (
  name         text primary key,
  outage_since timestamptz,
  recovered_at timestamptz,
  updated_at   timestamptz not null default now()
);
alter table public.cron_clock_state enable row level security;
insert into public.cron_clock_state (name) values ('cloudflare') on conflict (name) do nothing;
