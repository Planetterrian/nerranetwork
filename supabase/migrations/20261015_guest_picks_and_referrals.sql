-- Oct 15 2026 (Patrick): every interview ends with a lightning round, and
-- the answers (a book, the best advice they were given, who inspires them,
-- their bet, who Mira should interview next) are worth keeping. The picks
-- live on the episode's record; the people guests recommend become leads
-- that Mira researches and invites, crediting the guest who named them.

alter table public.episode_records
  add column if not exists picks jsonb,
  add column if not exists picks_at timestamptz;

create table if not exists public.guest_referrals (
  id uuid primary key default gen_random_uuid(),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  show text not null,
  recommender_interview_id uuid not null references public.interviews(id),
  recommender_name text not null,
  name text not null,
  organization text,
  role text,
  why text,                      -- the recommending guest's own words
  note text,                     -- e.g. the name was hard to make out in the recording
  status text not null default 'new' check (status in (
    'new',                 -- extracted, not looked at yet
    'held',                -- waiting for Patrick (first batch, or a manual pause)
    'invited',             -- Mira emailed them
    'asked_recommender',   -- no public address: Mira asked the guest for an introduction
    'no_contact',          -- nothing found and the guest was already asked
    'known',               -- already a guest or applicant: nothing to send
    'booked', 'interviewed', 'declined', 'skipped', 'failed')),
  contact_email text,
  contact_via text,              -- e.g. "University of Toronto Media Relations" when the address is an office
  contact_source text,           -- the public page the address was read from
  contact_route text,            -- a form or profile URL when there is no address
  topic text,                    -- what an interview with them would be about, from their public work
  searched_at timestamptz,       -- when Mira looked for an address (once)
  application_id uuid references public.guest_applications(id),
  invited_at timestamptz,
  asked_recommender_at timestamptz,
  attempts integer not null default 0,
  error text,
  unique (recommender_interview_id, name)
);

create index if not exists guest_referrals_status_idx on public.guest_referrals (status);
alter table public.guest_referrals enable row level security;

-- Applied separately once the table existed.
alter table public.guest_referrals add column if not exists note text;
alter table public.guest_referrals add column if not exists topic text,
  add column if not exists searched_at timestamptz;
