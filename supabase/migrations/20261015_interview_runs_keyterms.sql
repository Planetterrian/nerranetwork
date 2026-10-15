-- Oct 15 2026 (Grok Voice 3.0): the proper nouns the live transcription
-- should spell right — the guest's name, organisation and title, the show,
-- the network, the host and the co-host. Written by the fire step
-- (fire_interviews.keyterms_for), read by the Voximplant scenario into the
-- Voice Agent session's audio.input.transcription.keyterms (max 100 terms of
-- up to 50 characters). Idempotent; the fire step falls back to a row
-- without the column until this is applied.
alter table interview_runs add column if not exists keyterms jsonb not null default '[]'::jsonb;
comment on column interview_runs.keyterms is
  'Grok Voice 3.0 transcription key terms for this run (guest name, organisation, show, network, hosts).';
