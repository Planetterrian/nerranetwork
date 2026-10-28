-- Oct 27 2026: phone interviews are no longer offered (the sound is too poor
-- for the show); every interview is the browser studio. Two columns for the
-- studio's own bookkeeping:
--   studio_seen_at             the newest poll from the guest's studio page
--                              (stamped at most once a minute), so the late
--                              alert can tell an open page from a closed tab
--   studio_reschedule_sent_at  when the studio's "Pick another time" button
--                              last emailed the guest their move link
alter table public.interviews
  add column if not exists studio_seen_at timestamptz,
  add column if not exists studio_reschedule_sent_at timestamptz;

-- No interview still to happen is a phone interview.
update public.interviews set call_mode = 'webrtc'
 where call_mode is distinct from 'webrtc'
   and status in ('scheduled', 'briefed', 'in_progress');
