-- Oct 5 2026 (Piper Martz): a short follow-up session that records only the
-- closing round of an interview the time cap cut off. Applied by Claude via
-- the Supabase connector the same day.
alter table interviews add column if not exists session_kind text not null default 'interview';
alter table interviews add column if not exists continues_interview_id uuid references interviews(id);
alter table interview_runs add column if not exists session_kind text not null default 'interview';
