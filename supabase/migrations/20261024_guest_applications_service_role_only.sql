-- Oct 24 2026 security pass: guest_applications becomes service-role only.
--
-- The 20260704 schema gave anon an INSERT policy with WITH CHECK (true)
-- ("anon can submit applications"), and Supabase's default grants gave anon
-- and authenticated every privilege on every column. Anyone holding the
-- publishable key could POST /rest/v1/guest_applications with status,
-- fit_score, screen, producer_* or publicist_email already set, and the
-- Producer would act on that forged row (email the guest, book the call).
--
-- Nothing legitimate uses that path. Both apply pages (age-of-ai-apply.html,
-- nerra-voices-apply.html) POST to the Voices Worker at /voices/apply;
-- handleApply builds the row from a fixed list of applicant fields and
-- writes it with the service key. The Producer, the voices pipelines, the
-- Cal.com stub and the Voximplant scenario all use the service key as well.
-- So anon and authenticated get nothing on this table, the same model as
-- the sibling tables (RLS on, no policies, service role only).
--
-- service_role bypasses RLS and keeps its own grants, so no writer changes.
-- Idempotent: safe to run twice.
--
-- FLAG FOR OPERATOR: apply with the Supabase MCP / SQL editor on the Nerra
-- Voices project (mosbymmshvagdgcajkwr). Do NOT auto-apply from CI.

-- A table-level REVOKE also removes every column-level privilege. PUBLIC
-- holds nothing today; it is listed so a grant to PUBLIC cannot reopen this.
revoke all on table public.guest_applications from public, anon, authenticated;

drop policy if exists "anon can submit applications" on public.guest_applications;

alter table public.guest_applications enable row level security;

-- Stop here rather than leave the fix half applied.
do $$
declare
  r text;
begin
  foreach r in array array['anon', 'authenticated'] loop
    if has_table_privilege(r, 'public.guest_applications',
         'SELECT, INSERT, UPDATE, DELETE, TRUNCATE, REFERENCES, TRIGGER')
       or has_any_column_privilege(r, 'public.guest_applications',
         'SELECT, INSERT, UPDATE, REFERENCES') then
      raise exception 'guest_applications: % still holds a privilege', r;
    end if;
  end loop;

  if exists (select 1 from pg_policies
             where schemaname = 'public' and tablename = 'guest_applications'
               and roles && array['anon', 'authenticated', 'public']::name[]) then
    raise exception 'guest_applications: a policy for anon/authenticated/public remains';
  end if;

  if not (has_table_privilege('service_role', 'public.guest_applications', 'SELECT')
          and has_table_privilege('service_role', 'public.guest_applications', 'INSERT')
          and has_table_privilege('service_role', 'public.guest_applications', 'UPDATE')) then
    raise exception 'guest_applications: service_role lost access';
  end if;
end $$;
