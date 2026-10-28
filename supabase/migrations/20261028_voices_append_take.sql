-- Oct 28 2026: append one local recording take to an interview run, atomically.
--
-- The studio page finishes its audio take and its camera take at the same
-- moment. Each /voices/upload-done read grok_session_log, added its take and
-- wrote the whole object back, so the later write erased the earlier one's
-- listing: the second test room's camera take (42 chunks on R2) was listed
-- nowhere. The Worker now appends inside the database; the UPDATE holds the
-- row lock, so two appends can only follow one another.

create or replace function public.voices_append_take(
  p_run uuid, p_field text, p_role text, p_take jsonb
) returns jsonb
language plpgsql
security definer
set search_path = public
as $$
declare
  listed jsonb;
begin
  if p_field not in ('local_takes', 'local_video_takes') then
    raise exception 'voices_append_take: field % not allowed', p_field;
  end if;
  if p_role not in ('guest', 'host') then
    raise exception 'voices_append_take: role % not allowed', p_role;
  end if;
  if coalesce(p_take ->> 'manifest', '') = '' then
    raise exception 'voices_append_take: a take needs its manifest key';
  end if;
  update interview_runs r
     set grok_session_log = jsonb_set(
           coalesce(r.grok_session_log, '{}'::jsonb),
           array[p_field],
           coalesce(r.grok_session_log -> p_field, '{}'::jsonb) || jsonb_build_object(
             p_role,
             case
               when exists (
                 select 1
                   from jsonb_array_elements(coalesce(r.grok_session_log -> p_field -> p_role, '[]'::jsonb)) t
                  where t ->> 'manifest' = p_take ->> 'manifest')
               then coalesce(r.grok_session_log -> p_field -> p_role, '[]'::jsonb)
               else coalesce(r.grok_session_log -> p_field -> p_role, '[]'::jsonb) || jsonb_build_array(p_take)
             end))
   where r.id = p_run
  returning r.grok_session_log -> p_field -> p_role into listed;
  return listed;
end;
$$;

revoke all on function public.voices_append_take(uuid, text, text, jsonb) from public;
revoke all on function public.voices_append_take(uuid, text, text, jsonb) from anon, authenticated;
grant execute on function public.voices_append_take(uuid, text, text, jsonb) to service_role;

comment on function public.voices_append_take(uuid, text, text, jsonb) is
  'Oct 28 2026: append a studio recording take to interview_runs.grok_session_log.<field>.<role> without a read-and-write race (Worker /voices/upload-done).';
