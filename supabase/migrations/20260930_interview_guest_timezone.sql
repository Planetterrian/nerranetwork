-- Sept 30 2026: every time in Mira's mail is Pacific (the network's zone),
-- with the guest's own clock alongside. The booking records their zone here.
alter table public.interviews add column if not exists guest_timezone text;
comment on column public.interviews.guest_timezone is 'IANA zone the guest booked in (Cal.com attendee timeZone), Sept 30 2026. Emails show Pacific Time with the guest''s own clock alongside.';
