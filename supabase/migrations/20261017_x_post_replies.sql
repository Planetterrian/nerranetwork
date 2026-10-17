-- Oct 17 2026: the full episode as a reply under a show's X post
-- (engine/x_queue.py enqueue_reply / post_due_replies). A reply waits until
-- its parent post in x_post_queue is up, then posts the long-form video as a
-- reply to it. A separate table on purpose: the parent queue is untouched,
-- so posting keeps working before this migration is applied. Service-role
-- only: RLS on, no policies.
create table if not exists public.x_post_replies (
  id uuid primary key default gen_random_uuid(),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  show_slug text not null,
  episode_num integer not null,
  kind text not null default 'long',
  env_prefix text not null default 'NERRANETWORK_X_',
  text text not null,
  media_url text not null,
  subtitles_url text,
  status text not null default 'queued'
    check (status in ('queued', 'posting', 'posted', 'failed', 'cancelled')),
  attempts integer not null default 0,
  tweet_url text,
  error text,
  posted_at timestamptz,
  unique (show_slug, episode_num, kind)
);
create index if not exists x_post_replies_status on public.x_post_replies (status, created_at);
alter table public.x_post_replies enable row level security;
