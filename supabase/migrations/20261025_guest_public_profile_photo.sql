-- Oct 25 2026: every guest application names at least one public profile
-- (an X account, a LinkedIn profile, or the guest's page on their company's
-- site). The profiles live in guest_applications.links under the keys x,
-- linkedin and company_profile (the Worker's publicProfiles writes them).
-- The photo from those profiles goes on the episode page beside the guest's
-- name; pipelines/voices/profile_photo.py finds it, keeps a square copy on
-- R2 and records it here. A photo set by hand is never replaced.
alter table public.guest_applications
  add column if not exists profile_photo_url text,
  add column if not exists profile_photo_source text,
  add column if not exists profile_photo_at timestamptz;

comment on column public.guest_applications.profile_photo_url is
  'Square JPEG of the guest''s public profile photo on R2, shown on their episode page.';
comment on column public.guest_applications.profile_photo_source is
  'The profile page the photo came from, or "set by hand".';
