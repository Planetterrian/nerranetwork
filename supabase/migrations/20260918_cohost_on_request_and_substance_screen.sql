-- Sept 18 2026. Two things the first eight episodes taught the intake.
--
-- 1. Patrick is the network's creator and an occasional co-host, not a
--    fixture of every episode. Mira carries the room on her own; a guest
--    who would like him there says so on the application, and only then is
--    the interview a three-hander.
--
-- 2. A guest with nothing behind the pitch (Rhett Mikols, via a publicist,
--    Sept 17) cost an hour of Mira's and Patrick's time and produced nothing
--    publishable. Applications are screened for substance before triage:
--    named, checkable work versus abstractions with no instance. The screen
--    is advice for the person who approves, never the decision.

alter table guest_applications
  add column if not exists wants_cohost boolean not null default false,
  add column if not exists screen jsonb,
  add column if not exists screened_at timestamptz;

comment on column guest_applications.wants_cohost is
  'Guest asked for Patrick Novak (creator, occasional co-host) in the room. Sets interviews.host_mode.';
comment on column guest_applications.screen is
  '{"verdict": strong|thin|unclear, "summary", "specifics": [], "concerns": []} from screen_applications.py';
