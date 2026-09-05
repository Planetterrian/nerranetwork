# Voices API Worker (The Age of AI + Nerra Voices)

Webhook + tool-endpoint layer for the live-interview pipeline
([`docs/age_of_ai_plan.md`](../../docs/age_of_ai_plan.md)). Thin by design:
handlers update Supabase, send the occasional transactional email, and fire
`repository_dispatch` events that the `nerra_voices_*` GitHub Actions
workflows consume.

## Shows (September 2026)

One Worker, one set of tables, two shows. `guest_applications.show` and
`interviews.show` (migration `20260905_voices_show_routing.sql`, default
`age_of_ai`) say which show a row belongs to, and every Slack prefix, email
subject/sign-off, page title, brand colour and studio URL is looked up from
the `SHOWS` map in `src/index.ts`:

| slug | name | short label | colour | apply page | studio page |
|---|---|---|---|---|---|
| `age_of_ai` | The Age of AI | Age of AI | `#7C3AED` | `age-of-ai-apply.html` | `age-of-ai-studio.html?show=age_of_ai` |
| `nerra_voices` | Nerra Voices | Nerra Voices | `#0F766E` | `nerra-voices-apply.html` | `age-of-ai-studio.html?show=nerra_voices` |

The map mirrors `pipelines/voices/shows.py` (which reads `shows/<slug>.yaml`
`voices:` blocks) — change a value in the yaml and here together. Helpers:
`showFor(row, ...fallbacks)` (row.show → default `age_of_ai`), `isShow(slug)`,
`studioUrl(show, interviewId)`, `bookingUrl(env, show)`.

How the show is decided at each step:

- **Apply** — the form posts `show` (each apply page hardcodes its own slug);
  unknown/missing → `age_of_ai`. If the Nerra Producer inbox job already
  created an `invited` row for the same email, the form completes that row
  (status → `pending`, form fields merged over the stub, `source`/
  `pitched_show`/`email_thread_id`/`publicist_*` kept) instead of inserting
  a duplicate.
- **Triage** — `/voices/admin/triage` groups pending rows by show, shows
  the Producer's provenance fields, and has a per-row "Reassign" control →
  `POST /voices/triage-reassign {application_id, show}`. Approval emails the
  show's booking link (`CALCOM_BOOKING_URL_NERRA_VOICES` for Nerra Voices,
  else `CALCOM_BOOKING_URL`).
- **Cal.com booking** — the event type in the payload (`eventType.slug`,
  `eventTypeId`, `eventTypeSlug`) is matched against
  `CALCOM_EVENT_SLUG_AGE_OF_AI` / `CALCOM_EVENT_SLUG_NERRA_VOICES` when set;
  otherwise a slug containing `voices` → `nerra_voices`, else `age_of_ai`.
  The approved application is looked up with `show=eq.<slug>` first, then
  (logged) any approved application for that email. The interview row is
  written with the application's show and the confirmation links the studio
  with `&show=<slug>`.
- **Everything downstream** (editorial/guest review, gate-2 housekeeping,
  studio-state) resolves the show from the interview row, falling back to
  its application.

**Documented deviation from the pipeline spec §5.6:** the spec sketched
these as Vercel/Next.js routes beside Bill Saved. This repo's API surface
is Cloudflare Workers on `api.nerranetwork.com` (gallery worker precedent),
so they live here — the handler logic ports 1:1 to Next.js route files if
the operator later prefers Vercel. Routing: the gallery worker owns
`api.nerranetwork.com` as a custom domain; this worker claims only
`api.nerranetwork.com/voices/*` via a zone route (more-specific routes win).

## Endpoints

| Route | Purpose |
|---|---|
| `POST /voices/apply` | Public guest application form (both apply pages post here with their `show`) |
| `POST /voices/interview-complete` | Voximplant scenario hangup webhook → `repository_dispatch: interview-complete` |
| `POST /voices/cal-com-booked` | Cal.com booking webhook → schedules the interview + confirmation email |
| `GET/POST /voices/review/<token>` | Guest transcript review (gate 2): approve → `repository_dispatch: interview-approved-by-guest`; removal requests → back to Patrick |
| `GET /voices/admin/triage?token=…` | Patrick's application triage UI (~30 s/app), grouped by show |
| `GET /voices/admin/review/<pkg-id>?token=…` | Patrick's editorial review UI (gate 1): audio + transcript + drafts, approve/kill |
| `POST /voices/triage-decision` · `POST /voices/triage-reassign` · `POST /voices/editorial-decision` | The admin actions (token-gated); `triage-reassign` moves an application to the other show |
| `GET /voices/studio-state?interview=…` | Studio page poll: run readiness plus `show` / `show_name` for branding |
| `GET /voices/episode-lookup` · `GET /voices/guest-brief` · `POST /voices/fact-check` | Mira's three in-call tools (spec §3.2) |
| `scheduled` (daily 17:00 UTC) | Gate-2 housekeeping: day-4 guest reminder, day-7 auto-approve |
| `scheduled` (every 5 min) | Punctual fire-tick → `repository_dispatch: fire-tick` (GitHub's own 5-minute cron arrives hours late under load) |
| `GET /voices/health` | Deploy verification: which secrets are set (never values), cron config, and a live read-only GitHub auth probe — `github_status: 401` means the stored token is bad (expired, or pasted with a trailing newline); `repository_dispatch` needs **Contents: Read and write** |

## Deploy

```bash
cd workers/voices
wrangler secret put SUPABASE_URL
wrangler secret put SUPABASE_SERVICE_KEY
wrangler secret put GITHUB_DISPATCH_TOKEN   # fine-grained PAT, Contents: Read and write (repository_dispatch); verify with GET /voices/health
wrangler secret put ADMIN_TOKEN             # long random string; gates /voices/admin/*
wrangler secret put RESEND_API_KEY
wrangler secret put VOICES_FROM_EMAIL
wrangler secret put CALCOM_BOOKING_URL
wrangler secret put SLACK_WEBHOOK           # optional
# Nerra Voices (all optional — everything falls back to the Age of AI values):
wrangler secret put CALCOM_BOOKING_URL_NERRA_VOICES   # second Cal.com event; else CALCOM_BOOKING_URL is reused
wrangler secret put CALCOM_EVENT_SLUG_AGE_OF_AI       # Cal.com event-type slug (or numeric id) → routes the booking webhook
wrangler secret put CALCOM_EVENT_SLUG_NERRA_VOICES    # ditto; unset = slug containing "voices" → nerra_voices
wrangler deploy
```

Then point the external services at it:

- Voximplant scenario `WEBHOOK_URL` → `https://api.nerranetwork.com/voices/interview-complete` (already set in `voximplant/scenarios/age_of_ai_interview.js`).
- Cal.com event webhook → `https://api.nerranetwork.com/voices/cal-com-booked` (subscribe both event types to the same webhook).
- The public forms (`age-of-ai-apply.html` and `nerra-voices-apply.html` on the main site) post to `/voices/apply` with their `show`.

## Notes

- `fact_check_claim` deliberately returns an instruction that makes the
  agent use its own Grok web-search grounding — the named tool exists so
  fact checks are deliberate and auditable in the session log (spec §3.2),
  without duplicating a search stack in the Worker.
- `episode-lookup` reads the public site search index; if the index shape
  changes, the tool degrades to an empty result (never an error mid-call).
- No R2 binding needed: recordings move via the GitHub Actions pipelines,
  which have retry-friendly runtimes for multi-hundred-MB files.
