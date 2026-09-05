-- Nerra Voices: second Mira-hosted interview show + Nerra Producer inbox
-- (September 2026). Threads a `show` discriminator through the guest
-- pipeline so The Age of AI and Nerra Voices share one set of tables,
-- one Worker and one set of workflows.
--
-- Apply via the Supabase MCP `apply_migration` (project `nerra-voices`,
-- ref mosbymmshvagdgcajkwr). Idempotent: every statement is IF NOT EXISTS
-- / add column if not exists, so re-running is safe.
--
-- NOTE: production already carries columns the July migration never
-- declared (interviews.call_mode, interview_runs.recording_video_url,
-- extra status values). This file does not touch those.

-- ---------------------------------------------------------------------
-- Show routing
-- ---------------------------------------------------------------------
alter table guest_applications
  add column if not exists show text not null default 'age_of_ai';
alter table interviews
  add column if not exists show text not null default 'age_of_ai';

-- Which show slug is allowed (mirrors pipelines/voices/shows.py).
alter table guest_applications
  drop constraint if exists guest_applications_show_check;
alter table guest_applications
  add constraint guest_applications_show_check
  check (show in ('age_of_ai', 'nerra_voices'));
alter table interviews
  drop constraint if exists interviews_show_check;
alter table interviews
  add constraint interviews_show_check
  check (show in ('age_of_ai', 'nerra_voices'));

create index if not exists idx_applications_show_status
  on guest_applications (show, status);
create index if not exists idx_interviews_show_status
  on interviews (show, status);

-- ---------------------------------------------------------------------
-- Nerra Producer (inbox job) provenance
-- ---------------------------------------------------------------------
-- source: 'form' (the apply page) | 'email' (Producer inbox job)
alter table guest_applications
  add column if not exists source text not null default 'form';
-- The daily show the publicist actually pitched (e.g. 'planetterrian',
-- 'models_agents', 'modern_investing') — feeds cross_show_callouts so the
-- finished interview gets plugged on the channel they had in mind.
alter table guest_applications
  add column if not exists pitched_show text;
-- Gmail thread the pitch arrived in; unique so the inbox job is idempotent.
alter table guest_applications
  add column if not exists email_thread_id text;
create unique index if not exists idx_applications_email_thread
  on guest_applications (email_thread_id)
  where email_thread_id is not null;
-- Publicist / booker (often not the guest) and the Producer's own notes.
alter table guest_applications
  add column if not exists publicist_name text;
alter table guest_applications
  add column if not exists publicist_email text;
alter table guest_applications
  add column if not exists pitch_summary text;
-- Producer decision audit: what the classifier said and what we did.
alter table guest_applications
  add column if not exists producer_classification jsonb;
alter table guest_applications
  add column if not exists producer_action text;   -- 'sent' | 'drafted' | 'skipped'
alter table guest_applications
  add column if not exists producer_acted_at timestamptz;

-- status values now also include 'invited' (Producer replied with the
-- apply link; the guest has not filled the form yet). When the form
-- arrives from the same email the application flips to 'pending'.

-- ---------------------------------------------------------------------
-- Producer run log (one row per inbox tick; cheap observability)
-- ---------------------------------------------------------------------
create table if not exists producer_runs (
  id uuid primary key default gen_random_uuid(),
  job text not null,                       -- 'inbox' | 'chase' | 'review'
  started_at timestamptz not null default now(),
  finished_at timestamptz,
  messages_seen int not null default 0,
  messages_acted int not null default 0,
  drafts_created int not null default 0,
  sent int not null default 0,
  errors jsonb,
  cost_usd numeric,
  notes text
);
alter table producer_runs enable row level security;
