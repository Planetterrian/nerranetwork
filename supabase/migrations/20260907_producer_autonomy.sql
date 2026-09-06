-- Nerra Producer autonomy (September 2026): follow-up replies, chase
-- nudges and the daily digest. Idempotent; apply via the Supabase SQL
-- editor on project nerra-voices.

-- Follow-up bookkeeping on email-sourced applications.
alter table guest_applications
  add column if not exists producer_followup_count int not null default 0;
alter table guest_applications
  add column if not exists producer_last_inbound_at timestamptz;
alter table guest_applications
  add column if not exists producer_last_outbound_at timestamptz;
-- Chase job: how many nudges went out and when the last one did.
alter table guest_applications
  add column if not exists chase_count int not null default 0;
alter table guest_applications
  add column if not exists chased_at timestamptz;
-- Why the Producer closed a thread ('no_reply', 'declined', 'auto_reply_only').
alter table guest_applications
  add column if not exists producer_closed_reason text;
-- Bio / topics / links the Producer extracted from the pitch so a guest who
-- never fills the form still gets a proper prep brief (bio/topics/links
-- columns already exist from the July schema).

create index if not exists idx_applications_producer_chase
  on guest_applications (status, source, chase_count)
  where source = 'email';
