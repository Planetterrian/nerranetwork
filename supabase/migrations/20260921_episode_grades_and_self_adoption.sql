-- Sept 21 2026. The learning loop closes itself.
--
-- Until today a retrospective pass proposed lessons and Patrick promoted them
-- at gate 1. Eight proposals were still sitting unread while the same faults
-- recurred across Meridan Zerner's and Sameer Ranjan's episodes, which means
-- the queue was the bottleneck, not the judgement. The grading pass now adopts
-- what it decides and retires what the show has outgrown, and Patrick reads
-- what it did rather than gating it.
--
-- Two things make that safe rather than reckless: the grader is shown the
-- instructions Mira already carries and told not to restate them, and every
-- adoption stays reversible from the triage page. So this migration only has
-- to make the decision auditable — who decided, when, why, and what the
-- episode actually scored.

alter table show_lessons
  add column if not exists decided_by text,
  add column if not exists decision_note text;

comment on column show_lessons.decided_by is
  'Who moved this lesson to its current status: ''mira'' (the grading pass, automatic) or ''patrick''.';
comment on column show_lessons.decision_note is
  'Why, in one line — confidence at adoption, or the reason for retiring.';

-- 'retired' joins proposed/active/dropped/merged: a lesson that did its job or
-- was crowded out by a sharper one. Kept, never deleted; the record of what
-- the show used to need is the only evidence that it improved.

create table if not exists episode_grades (
  interview_id  uuid primary key references interviews(id) on delete cascade,
  show          text not null,
  overall       numeric(3,1),
  listening     numeric(3,1),
  questions     numeric(3,1),
  pacing        numeric(3,1),
  turn_taking   numeric(3,1),
  warmth        numeric(3,1),
  why           text,
  worked        jsonb default '[]'::jsonb,
  lessons_adopted int not null default 0,
  lessons_retired int not null default 0,
  ask_the_guest text,
  created_at    timestamptz not null default now()
);

comment on table episode_grades is
  'One scorecard per interview from the grading pass. Scores are out of ten and '
  'are meant to be comparable between episodes, so "Mira is improving" can be '
  'checked rather than felt.';
comment on column episode_grades.ask_the_guest is
  'A question worth putting to this guest in the follow-up about how the hour felt.';

create index if not exists episode_grades_show_created_idx
  on episode_grades (show, created_at desc);
