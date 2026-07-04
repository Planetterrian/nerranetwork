# Nerra Voices API Worker (The Age of AI)

Webhook + tool-endpoint layer for the live-interview pipeline
([`docs/age_of_ai_plan.md`](../../docs/age_of_ai_plan.md)). Thin by design:
handlers update Supabase, send the occasional transactional email, and fire
`repository_dispatch` events that the `nerra_voices_*` GitHub Actions
workflows consume.

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
| `POST /voices/apply` | Public guest application form (static page posts here) |
| `POST /voices/interview-complete` | Voximplant scenario hangup webhook → `repository_dispatch: interview-complete` |
| `POST /voices/cal-com-booked` | Cal.com booking webhook → schedules the interview + confirmation email |
| `GET/POST /voices/review/<token>` | Guest transcript review (gate 2): approve → `repository_dispatch: interview-approved-by-guest`; removal requests → back to Patrick |
| `GET /voices/admin/triage?token=…` | Patrick's application triage UI (~30 s/app) |
| `GET /voices/admin/review/<pkg-id>?token=…` | Patrick's editorial review UI (gate 1): audio + transcript + drafts, approve/kill |
| `POST /voices/triage-decision` · `POST /voices/editorial-decision` | The two admin actions (token-gated) |
| `GET /voices/episode-lookup` · `GET /voices/guest-brief` · `POST /voices/fact-check` | Mira's three in-call tools (spec §3.2) |
| `scheduled` (daily 17:00 UTC) | Gate-2 housekeeping: day-4 guest reminder, day-7 auto-approve |

## Deploy

```bash
cd workers/voices
wrangler secret put SUPABASE_URL
wrangler secret put SUPABASE_SERVICE_KEY
wrangler secret put GITHUB_DISPATCH_TOKEN   # fine-grained PAT, contents:write
wrangler secret put ADMIN_TOKEN             # long random string; gates /voices/admin/*
wrangler secret put RESEND_API_KEY
wrangler secret put VOICES_FROM_EMAIL
wrangler secret put CALCOM_BOOKING_URL
wrangler secret put SLACK_WEBHOOK           # optional
wrangler deploy
```

Then point the external services at it:

- Voximplant scenario `WEBHOOK_URL` → `https://api.nerranetwork.com/voices/interview-complete` (already set in `voximplant/scenarios/age_of_ai_interview.js`).
- Cal.com event webhook → `https://api.nerranetwork.com/voices/cal-com-booked`.
- The public form (`age-of-ai-apply.html` on the main site) posts to `/voices/apply`.

## Notes

- `fact_check_claim` deliberately returns an instruction that makes the
  agent use its own Grok web-search grounding — the named tool exists so
  fact checks are deliberate and auditable in the session log (spec §3.2),
  without duplicating a search stack in the Worker.
- `episode-lookup` reads the public site search index; if the index shape
  changes, the tool degrades to an empty result (never an error mid-call).
- No R2 binding needed: recordings move via the GitHub Actions pipelines,
  which have retry-friendly runtimes for multi-hundred-MB files.
