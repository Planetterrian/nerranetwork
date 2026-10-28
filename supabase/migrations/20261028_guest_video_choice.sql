-- Oct 28 2026 (Patrick): guests' cameras are recorded in the browser for a
-- video version of the episode. The guest review page asks a guest whose
-- camera was recorded whether the video may be published; this is their
-- answer. NULL = never asked (no video, or an older review page); FALSE =
-- audio only, and publish_episode sends no video anywhere.
alter table public.editorial_packages
  add column if not exists guest_video_ok boolean;

comment on column public.editorial_packages.guest_video_ok is
  'Guest''s video choice on the review page: true = video version welcome, false = audio only, null = not asked';
