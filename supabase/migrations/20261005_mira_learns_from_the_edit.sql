-- Oct 5 2026. Mira's learning loop, widened.
-- editor_cuts: lines of Mira's that the edit removed (false starts, fillers,
-- apologies over the guest). The next grading pass is shown them, and the
-- short ones join her retired phrases.
create table if not exists editor_cuts (
  id uuid primary key default gen_random_uuid(),
  interview_id uuid references interviews(id) on delete cascade,
  show text not null,
  line text not null,
  at_sec numeric,
  created_at timestamptz not null default now()
);
create index if not exists editor_cuts_show_created on editor_cuts (show, created_at desc);
alter table editor_cuts enable row level security;
-- What the guest said about being interviewed by Mira, after listening back.
alter table editorial_packages add column if not exists guest_experience text;
alter table editorial_packages add column if not exists guest_experience_at timestamptz;
-- show_lessons.show = 'network' marks a standing lesson every show carries.
