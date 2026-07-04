-- Nerra Voices — The Age of AI interview pipeline schema (spec §4).
--
-- Provision on a SEPARATE Supabase instance from Bill Saved (spec §11.4):
-- data segregation, RLS clarity, and isolation from Bill Saved schema
-- changes. Apply via `supabase db push` or the Supabase MCP
-- apply_migration tool.
--
-- Access model (RLS below):
--   guest_applications : INSERT from anon (public form); read service-role only
--   editorial_packages : service role + signed-link guest access (the guest
--                        review page runs server-side in the Worker with the
--                        service key after verifying the signed token, so no
--                        anon policy is required here)
--   everything else    : service-role only

-- ---------------------------------------------------------------------------
-- Public application form submissions
-- ---------------------------------------------------------------------------
create table if not exists guest_applications (
  id uuid primary key default gen_random_uuid(),
  created_at timestamptz default now(),
  name text not null,
  email text not null,
  phone text,
  organization text,
  title text,
  bio text,
  topics text[],                          -- e.g. ['AI in journalism', 'tutoring']
  links jsonb,                            -- {website, twitter, linkedin, scholar}
  preferred_window text,
  referrer text,
  status text default 'pending',          -- pending, approved, declined, queued, lapsed
  fit_score numeric,                      -- 0-10, LLM-assigned at triage time
  notes text                              -- Patrick's notes
);

-- ---------------------------------------------------------------------------
-- Approved guests, awaiting or completed interview
-- ---------------------------------------------------------------------------
create table if not exists interviews (
  id uuid primary key default gen_random_uuid(),
  application_id uuid references guest_applications(id),
  scheduled_at timestamptz,               -- set by Cal.com webhook
  duration_min int default 45,
  topical_show_fits text[],               -- ['models_agents', 'modern_investing']
  episode_thesis text,                    -- the angle for this episode
  episode_number int,                     -- sequential, assigned at publish
  status text default 'scheduled',
  -- statuses: scheduled, briefed, in_progress, recorded, editorial_review,
  --           guest_review, approved, published, cancelled, failed, missed
  caller_id text,                         -- Mira's outbound phone number
  no_show_count int default 0,            -- spec §11.7: lapse after 2 no-shows
  reminder_sent_at timestamptz,           -- T-2h SMS reminder (once per booking)
  created_at timestamptz default now(),
  updated_at timestamptz default now()
);

-- ---------------------------------------------------------------------------
-- Pre-interview research brief (one per interview)
-- ---------------------------------------------------------------------------
create table if not exists interview_briefs (
  id uuid primary key default gen_random_uuid(),
  interview_id uuid references interviews(id) on delete cascade,
  generated_at timestamptz default now(),
  bio_research text,                      -- LLM-generated research summary
  past_work_summary text,                 -- summary of guest's published work
  likely_questions jsonb,                 -- array of 6-8 question objects
  episode_thesis_draft text,
  sent_to_guest_at timestamptz
);

-- ---------------------------------------------------------------------------
-- A specific interview run (the scheduled call)
-- ---------------------------------------------------------------------------
create table if not exists interview_runs (
  id uuid primary key default gen_random_uuid(),
  interview_id uuid references interviews(id) on delete cascade,
  mira_system_prompt text not null,       -- compiled at fire time
  voice_preset text default 'ara',
  tools jsonb,
  guest_phone text not null,
  caller_id text not null,
  scheduled_for timestamptz not null,
  fired_at timestamptz,
  voximplant_session_id text,
  recording_guest_url text,               -- R2 URL after upload
  recording_mira_url text,
  recording_mixed_url text,               -- ffmpeg-mixed final
  grok_session_log jsonb,
  duration_sec int,
  disconnect_reason text,
  status text default 'pending',
  -- pending, fired, in_progress, completed, failed
  created_at timestamptz default now()
);

create index if not exists idx_runs_pending_by_time
  on interview_runs (scheduled_for)
  where status = 'pending';

-- ---------------------------------------------------------------------------
-- Post-call editorial package
-- ---------------------------------------------------------------------------
create table if not exists editorial_packages (
  id uuid primary key default gen_random_uuid(),
  interview_id uuid references interviews(id) on delete cascade,
  interview_run_id uuid references interview_runs(id),
  transcript_raw text,
  transcript_cleaned text,
  chapter_markers jsonb,                  -- [{start, end, title}, ...]
  episode_notes text,
  social_copy jsonb,                      -- {twitter, linkedin, instagram}
  clip_suggestions jsonb,                 -- [{start, end, title, why}]
  cross_show_callouts jsonb,              -- {tesla: "...", mit: "...", ...}
  newsletter_draft text,
  status text default 'draft',
  -- draft, in_review, approved_by_patrick, approved_by_guest, published, killed
  patrick_reviewed_at timestamptz,
  patrick_notes text,
  guest_reviewed_at timestamptz,
  guest_review_token text,                -- signed-link access for gate 2
  guest_review_deadline timestamptz,      -- +7 days; auto-approve after (spec §7)
  guest_redactions jsonb,                 -- [{start, end, reason}]
  audio_quality_flag text,                -- e.g. 'low_stt_confidence', 'short_call'
  created_at timestamptz default now()
);

-- ---------------------------------------------------------------------------
-- Cross-show callout queue (consumed by sister-show pipelines)
-- ---------------------------------------------------------------------------
create table if not exists cross_show_callouts (
  id uuid primary key default gen_random_uuid(),
  source_show text default 'age_of_ai',
  source_episode_id uuid references interviews(id),
  target_show text not null,              -- 'tesla', 'modern_investing', etc.
  callout_text text not null,
  callout_url text not null,              -- link to episode
  expires_at timestamptz,                 -- 14 days post-publish typical
  consumed_at timestamptz,                -- when target show used it
  created_at timestamptz default now()
);

create index if not exists idx_callouts_target_active
  on cross_show_callouts (target_show, expires_at)
  where consumed_at is null;

-- ---------------------------------------------------------------------------
-- Row-Level Security
-- ---------------------------------------------------------------------------
alter table guest_applications enable row level security;
alter table interviews enable row level security;
alter table interview_briefs enable row level security;
alter table interview_runs enable row level security;
alter table editorial_packages enable row level security;
alter table cross_show_callouts enable row level security;

-- Public form: anon may INSERT only (never read back).
create policy "anon can submit applications"
  on guest_applications for insert
  to anon
  with check (true);

-- No other anon/authenticated policies: with RLS enabled and no policy,
-- all access is denied except the service role (which bypasses RLS). The
-- Worker/API layer and GitHub Actions pipelines use the service key; the
-- guest review page verifies the signed guest_review_token server-side
-- before touching editorial_packages with the service key.
