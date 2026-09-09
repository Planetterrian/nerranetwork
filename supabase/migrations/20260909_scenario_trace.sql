-- Sept 9 2026: the VoxEngine scenario keeps its own timeline on the run
-- row (conference attach, agent bridge, opening, first speech heard,
-- host dial results, audio-path fallback) because the Voximplant session
-- log is size-capped and the panel session expires. Idempotent.
alter table interview_runs
  add column if not exists scenario_trace jsonb;
