-- Oct 16 2026 (Patrick, after Meridan Zerner never opened her studio and
-- nobody knew until the no-show email forty minutes later). The fire job
-- (pipelines/voices/fire_interviews.py) now texts and emails the guest five
-- minutes before the start, and texts and emails Patrick five minutes after
-- it when the guest still hasn't opened the studio. Each is claimed with a
-- conditional write on its column, so two ticks never both send.

alter table public.interviews
  add column if not exists start_notice_at timestamptz,
  add column if not exists late_alert_at timestamptz;
