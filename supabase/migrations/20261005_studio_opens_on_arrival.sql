-- Oct 5 2026 (Jon Cheney): runs are staged ahead and the Worker opens the
-- studio when the guest arrives. These record the Worker's one-time alert
-- and its throttled request for a run when none was staged.
alter table interviews add column if not exists studio_kick_at timestamptz;
alter table interviews add column if not exists studio_alert_at timestamptz;
