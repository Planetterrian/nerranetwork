-- Oct 11 2026: daytime posting for @nerranetwork (engine/x_queue.py).
-- run_show queues a show's X post into a half-hour slot between 6:30 AM and
-- 7:00 PM Pacific; scripts/post_x_queue.py posts what is due. Service-role
-- only: RLS on, no policies.
create table if not exists public.x_post_queue (
  id uuid primary key default gen_random_uuid(),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  show_slug text not null,
  episode_num integer not null,
  env_prefix text not null default 'NERRANETWORK_X_',
  text text not null,
  media_url text,
  media_kind text,
  due_at timestamptz not null,
  status text not null default 'queued'
    check (status in ('queued', 'posting', 'posted', 'failed', 'cancelled')),
  attempts integer not null default 0,
  tweet_url text,
  error text,
  posted_at timestamptz,
  unique (show_slug, episode_num)
);
create index if not exists x_post_queue_status_due on public.x_post_queue (status, due_at);
alter table public.x_post_queue enable row level security;
