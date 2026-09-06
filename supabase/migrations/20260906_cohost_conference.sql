-- Phase 2 (September 2026): Patrick in the room as co-host, three clean
-- tracks per interview, local high-quality browser recordings.
-- Idempotent; apply via the Supabase SQL editor on project nerra-voices.

alter table interviews
  add column if not exists host_mode boolean not null default true;

alter table interview_runs
  add column if not exists host_mode boolean not null default true;
alter table interview_runs
  add column if not exists recording_host_url text;
alter table interview_runs
  add column if not exists recording_mira_url text;
alter table interview_runs
  add column if not exists local_guest_url text;
alter table interview_runs
  add column if not exists local_host_url text;
alter table interview_runs
  add column if not exists guest_joined_at timestamptz;
alter table interview_runs
  add column if not exists host_joined_at timestamptz;
alter table interview_runs
  add column if not exists host_left_at timestamptz;
alter table interview_runs
  add column if not exists host_attempts int not null default 0;
-- Voximplant user the scenario dials as the co-host leg (fire_interviews.py
-- writes it from env VOX_HOST_USER; the scenario falls back to 'host').
alter table interview_runs
  add column if not exists host_user text not null default 'host';
