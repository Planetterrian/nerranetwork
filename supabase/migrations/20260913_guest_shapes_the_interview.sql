-- What the guest wants the conversation to be (Sept 13 2026).
--
-- Until now length was a constant in the Voximplant scenario — 45 minutes for
-- everyone, whatever they had asked for — depth was whatever the research pass
-- happened to produce, and how personal Mira could get was not asked at all.
-- The application asks all three now, and the answers reach the question set,
-- Mira's system prompt and the room's clock.

alter table guest_applications
  add column if not exists desired_minutes int,
  add column if not exists depth text,
  add column if not exists personal_depth text,
  add column if not exists off_limits text;

alter table guest_applications
  drop constraint if exists guest_applications_depth_check,
  add constraint guest_applications_depth_check
    check (depth is null or depth in ('accessible','standard','deep'));

alter table guest_applications
  drop constraint if exists guest_applications_personal_depth_check,
  add constraint guest_applications_personal_depth_check
    check (personal_depth is null or personal_depth in ('none','light','open'));

alter table guest_applications
  drop constraint if exists guest_applications_desired_minutes_check,
  add constraint guest_applications_desired_minutes_check
    check (desired_minutes is null or desired_minutes between 15 and 90);

comment on column guest_applications.desired_minutes is
  'Interview length the guest asked for. Copied to interviews.duration_min at booking; drives Mira''s time checks and the room hard cap.';
comment on column guest_applications.personal_depth is
  'How far Mira may go into the guest personally: none | light | open. She does not push past it.';

-- interviews.duration_min has existed since the first migration and nothing
-- ever wrote it. The booking endpoint writes it now.
alter table interview_runs
  add column if not exists planned_minutes int;

comment on column interview_runs.planned_minutes is
  'Interview length this room paces to, from the guest''s application. The scenario reads it for its [TIME CHECK] notes and hard cap; null means 45.';
