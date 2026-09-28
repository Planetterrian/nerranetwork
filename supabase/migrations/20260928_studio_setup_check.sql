-- Sept 28 2026 (Elliot): the studio's microphone check and the day-before
-- setup test report here, so a guest whose microphone Mira cannot hear is
-- known about before the interview, not from the cancellation.
alter table public.interviews add column if not exists setup_check jsonb;
comment on column public.interviews.setup_check is 'Latest studio setup test / pre-join microphone check (Sept 28 2026): {mic, mic_db, echo, signin, test, device, at, history}.';
