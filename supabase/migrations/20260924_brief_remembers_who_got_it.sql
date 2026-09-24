-- Sept 24 2026: Dr. Michael Brandt's prep brief went to his publicist's
-- address on an older booking row. When the booking was consolidated onto
-- his own application the brief was already "sent", so he never got one and
-- had to ask for it on the morning of the interview. The brief now records
-- the address it went to, and generate_briefs.py sends it again when the
-- guest's address has changed since.
alter table interview_briefs add column if not exists sent_to text;
