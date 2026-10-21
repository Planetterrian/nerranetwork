-- Oct 21 2026: a five-minute hello two days before the interview, so the
-- guest's agenda is set out loud rather than in a reply nobody sends. Same
-- shape as the closing session (20261005_interview_closing_session.sql):
-- its own interviews row, session_kind = 'hello'.
alter table interviews add column if not exists hello_for_interview_id uuid references interviews(id);
alter table interviews add column if not exists hello_invited_at timestamptz;
alter table interviews add column if not exists hello_skipped_reason text;
alter table interviews add column if not exists hello_agenda jsonb;
comment on column interviews.hello_for_interview_id is
  'On a session_kind = ''hello'' row: the interview this five-minute hello precedes.';
comment on column interviews.hello_invited_at is
  'When the guest was invited to book a hello (once per interview; null = not yet).';
comment on column interviews.hello_agenda is
  'On a hello row: the agenda extracted from its transcript, also written to guest_applications.guest_agenda.';
