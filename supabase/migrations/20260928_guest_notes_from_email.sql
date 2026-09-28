-- Sept 28 2026 (Elliot Justin): what a guest writes to Mira between booking
-- and the call is filed here by the Producer and read into her interview
-- prompt, instead of being answered as if it were a publicist's pitch.
alter table public.guest_applications add column if not exists guest_notes jsonb;
comment on column public.guest_applications.guest_notes is 'What the guest wrote to Mira between booking and the call (Sept 28 2026): [{at, text, thread_id, source}]. Read into Mira''s interview prompt.';
