-- Oct 21 2026 — Age of AI review, §7.4 "A loop that can hear" and §7.6.
--
-- The craft metrics were estimated from a transcript whose lines carry a
-- start but no end; the three faults guests name (pace, overlap, no
-- reaction) are timing phenomena. These columns hold the measures
-- pipelines/voices/audio_metrics.py takes from each speaker's own recording.
-- The old estimates (interruptions, dead_air_sec, repeated_questions) stay
-- and are still written for a month of comparison; metrics_basis says
-- which kind a row carries ('audio' | 'transcript').
alter table episode_metrics
  add column if not exists overlap_sec numeric,
  add column if not exists overlap_events integer,
  add column if not exists turn_gap_ms_median numeric,
  add column if not exists turn_gap_ms_p10 numeric,
  add column if not exists turn_gap_ms_p90 numeric,
  add column if not exists mira_turn_sec_median numeric,
  add column if not exists mira_turn_sec_p90 numeric,
  add column if not exists guest_words_per_answer_median numeric,
  add column if not exists guest_words_trend numeric,
  add column if not exists self_answered_turns integer,
  add column if not exists echo_open_rate numeric,
  add column if not exists closing_round_complete boolean,
  add column if not exists seams integer,
  add column if not exists metrics_basis text;
comment on column episode_metrics.overlap_sec is
  'Seconds where Mira''s track and the guest''s track both carried speech (audio).';
comment on column episode_metrics.turn_gap_ms_median is
  'Guest''s last word to Mira''s first, per turn: 400-900 is conversation, under 300 an interruption, over 3000 dead air she caused.';
comment on column episode_metrics.mira_turn_sec_median is
  'Her turn length from her own track; 7.6 s is clipped, 50 s a monologue.';
comment on column episode_metrics.guest_words_trend is
  'Median guest words per answer in the last third of the hour over the first third; above 1 means answers grew.';
comment on column episode_metrics.self_answered_turns is
  'Mira turns with no guest speech since her previous turn: she asked and answered.';
comment on column episode_metrics.echo_open_rate is
  'Share of her turns whose first four words sat in the guest''s previous thirty.';
comment on column episode_metrics.closing_round_complete is
  'From the room trace: every closing-round question asked, one per turn, each followed by the guest.';
comment on column episode_metrics.seams is
  'Session rotations and drops with guest speech within two seconds either side.';
comment on column episode_metrics.metrics_basis is
  '''audio'' when the overlap/gap/turn columns were measured from per-speaker tracks; ''transcript'' when only the older estimates exist.';

-- The guest is asked every time (§7.4): a three-question email 24 h after
-- the room, from Mira, whether or not they open the approval page.
-- The edit keeps its promises (§7.6): a redaction carries a time window
-- the assembly applies, the guest approves the transcript of the EDIT,
-- and the thank-you / publish-day emails are stamped so they go once.
alter table editorial_packages
  add column if not exists survey_token text,
  add column if not exists survey_sent_at timestamptz,
  add column if not exists survey_rating integer,
  add column if not exists survey_change text,
  add column if not exists survey_recommend text,
  add column if not exists survey_answered_at timestamptz,
  add column if not exists guest_redaction_windows jsonb not null default '[]'::jsonb,
  add column if not exists edit_transcript text,
  add column if not exists thanks_sent_at timestamptz,
  add column if not exists publish_package_sent_at timestamptz;
comment on column editorial_packages.survey_rating is
  'The guest''s 1-5 answer to "how did the hour compare with a human host" — the headline figure for an interview show.';
comment on column editorial_packages.guest_redaction_windows is
  'List of {start_sec, end_sec, line}: cuts the guest asked for, applied to the shipped edit by code.';
comment on column editorial_packages.edit_transcript is
  'Transcript of the edit the guest approves — never the room''s, which carries lines the edit removed.';
create unique index if not exists editorial_packages_survey_token_idx
  on editorial_packages (survey_token) where survey_token is not null;

-- A lesson names the measure that will show it worked, and is retired when
-- that measure has been green for three rooms — never by age.
alter table show_lessons
  add column if not exists metric text;
comment on column show_lessons.metric is
  'The audio_metrics key the weekly pass reads to decide the lesson has done its job (null: retired only by a person).';
comment on column show_lessons.status is
  'proposed (the grading pass), active (the weekly pass or Patrick), retired, dropped, merged.';

-- The live interview''s reasoning effort, per run (§7.2: trial low on the
-- rehearsal harness before a guest hears it). Null keeps the scenario''s
-- pinned default.
alter table interview_runs
  add column if not exists reasoning_effort text;
