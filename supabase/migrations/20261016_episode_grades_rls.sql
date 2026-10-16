-- Oct 16 2026 security pass: episode_grades was created without RLS
-- (20260921_episode_grades_and_self_adoption.sql). Sibling tables in this
-- project enable RLS with no anon policies (service-role only). Match that
-- so a leaked anon key cannot read scorecards.
--
-- FLAG FOR OPERATOR: apply with the Supabase MCP / SQL editor on the Nerra
-- Voices project. Do NOT auto-apply from CI. File-only in this PR.

alter table episode_grades enable row level security;

-- No policies for anon/authenticated — service role bypasses RLS. Defence
-- in depth if the publishable key ever reaches a client with this table
-- exposed via PostgREST.

comment on table episode_grades is
  'One scorecard per interview from the grading pass. Scores are out of ten and '
  'are meant to be comparable between episodes, so "Mira is improving" can be '
  'checked rather than felt. RLS on (Oct 16 2026); service-role only.';
