-- Oct 5 2026: the Cal.com booking an interview came from, so a reschedule or
-- cancellation in Cal.com finds its interview directly.
alter table interviews add column if not exists cal_booking_uid text;
create index if not exists interviews_cal_booking_uid on interviews (cal_booking_uid);
