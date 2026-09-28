-- Sept 29 2026 (Chad Law): the subject a guest came for and the points they
-- asked Mira to reach. Read into her interview prompt as destinations, not a
-- script (pipelines/voices/common.py guest_agenda_block).
alter table public.guest_applications add column if not exists guest_agenda jsonb;
comment on column public.guest_applications.guest_agenda is 'The subject the guest came for and the points they asked Mira to cover (Sept 29 2026, Chad Law): {topic, points[], updated_at, source}. Read into Mira''s interview prompt as destinations, not a script.';
