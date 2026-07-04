# The Age of AI — Automated Interview Pipeline (implementation notes)

**Show:** The Age of AI · **Host:** Mira (AI documentarian persona, Grok voice `ara`)
**Status:** Repo-side implementation landed July 2026 (PR #771). External
provisioning (Voximplant, Supabase, Cal.com, phone number) is the operator
bootstrap below.

This document tracks the operator's full pipeline spec ("The Age of AI —
Automated Interview Pipeline Spec") as implemented in this repo. The spec's
architecture is unchanged: everything between the guest form and publish is
automated, with exactly two intentional manual gates — **Patrick's
editorial review** (gate 1) and the **guest's transcript approval** (gate 2,
auto-approve at day 7 with a day-4 reminder). Gate 1 never times out into a
publish; Patrick is the bottleneck by design.

## What lives where

| Spec § | Piece | In this repo |
|---|---|---|
| §3 | Voximplant scenario (the central glue) | `voximplant/scenarios/age_of_ai_interview.js` + `voximplant/api_clients/voximplant_client.py` (StartScenarios, scenario deploy, secrets, SMS) |
| §3.2 | Mira's 3 in-call tools | Tool definitions in `pipelines/voices/fire_interviews.py` (`MIRA_TOOLS`); endpoints in the voices Worker |
| §3.3 | Mira's system prompt (templated per interview) | `pipelines/voices/prompts/mira_system_prompt.txt`, compiled at fire time |
| §4 | Supabase schema (6 tables + RLS) | `supabase/migrations/20260704_nerra_voices_schema.sql` (separate instance from Bill Saved, per §11.4) |
| §5.1 | Daily prep briefs (9am PT) | `.github/workflows/nerra_voices_prep_briefs.yml` → `pipelines/voices/generate_briefs.py` |
| §5.2 | Fire interviews (every 5 min) + T-2h SMS | `nerra_voices_fire_interview.yml` → `fire_interviews.py` (drift-tolerant window, idempotent via `interview_runs`) |
| §5.3 | Post-interview processing | `nerra_voices_post_interview.yml` (repository_dispatch `interview-complete`) → `post_interview.py`: R2 copies, ffmpeg mix, **per-channel Whisper STT (the stereo tracks are the diarization)**, 8 validated editorial passes, Slack ping |
| §5.4 | Produce final episode | `nerra_voices_produce_episode.yml` (dispatch `interview-approved-by-guest`) → `produce_episode.py`: narration LLM pass → Mira TTS → assembly with **redaction cuts first** → waveform video → R2 |
| §5.5 | Publish | `nerra_voices_publish.yml` → `publish_episode.py` (reuses `engine.publisher` RSS + summaries + site regen; commits like run-show) |
| §5.6 | Webhook/API layer | **`workers/voices/`** — see deviation note below |
| §10 | Editorial pass prompts + validators | `pipelines/voices/prompts/editorial_passes/01..08` + `pipelines/voices/validators/schema_validators.py` (schema check → one strict retry → surface to Patrick) |
| §10 | Guest form | `age-of-ai-apply.html` (static, posts to the Worker) |
| §10 | Email templates | `templates/email/voices_*.j2` (8) |
| — | Show registry (RSS/site/dashboards) | `shows/age_of_ai.yaml` — **run_show is a guard-railed no-op** (narrative mode + permanently-empty `shows/topic_queues/age_of_ai.yaml` → clean `narrative_queue_empty` skip). Production never goes through run_show. |

**Documented deviation (spec §5.6):** the spec sketched the webhook handlers
as Vercel/Next.js routes beside Bill Saved. That app isn't in this repo, and
the network's API surface is Cloudflare Workers on `api.nerranetwork.com`
(gallery worker precedent) — so the handlers live in `workers/voices/`
(route `api.nerranetwork.com/voices/*`; more-specific routes win over the
gallery worker's custom domain). The handlers are deliberately thin and port
1:1 to Next.js if the operator prefers Vercel later. The Worker also hosts
the three UIs (Patrick's triage + editorial review, the guest's signed-link
transcript review) and a daily cron for gate-2 housekeeping.

Two small mechanical deviations inside the scenario: recordings reach R2 via
the post-interview workflow (scenario `Net.httpRequest` can't stream
multi-hundred-MB audio reliably; GitHub Actions retries are cheap — the
§7 upload-failure row is handled there), and scenario secrets come from
Voximplant application custom data set once via
`voximplant_client.set_application_secrets()`.

## The state machine (single source of truth: Supabase)

```
guest_applications.status : pending → approved|declined … lapsed (2 no-shows)
interviews.status         : scheduled → briefed → in_progress → recorded/
                            editorial_review → guest_review → approved →
                            published   (or cancelled/failed/missed)
editorial_packages.status : draft → in_review → approved_by_patrick →
                            approved_by_guest → published   (or killed)
interview_runs.status     : pending → fired → in_progress → completed|failed
```

Edge-case handling follows spec §7: no-answer → missed + reschedule email
(2nd no-show lapses the application); Grok drop → 10 s grace, Mira apology
clip, hangup; short call / low STT confidence → flags on the editorial
package for Patrick; LLM pass garbage → schema validator + one strict
retry, then manual-draft escalation; double cron tick → `interview_runs`
idempotency check.

## Operator bootstrap (one-time, in order)

1. **Supabase**: create the Nerra Voices project (separate from Bill
   Saved), apply `supabase/migrations/20260704_nerra_voices_schema.sql`.
2. **Voximplant** (phase 1 smoke test): enable the Grok Voice Agent
   connector, create app `nerra-voices` + rule `age-of-ai-interview`, buy
   Mira's dedicated Vancouver-area number (§11.1, ~$1/mo), then
   `voximplant_client.upload_scenario()` +
   `set_application_secrets(supabase_key, xai_key)`. Record the consent
   disclosure + Grok-drop apology clips (Mira `ara` voice) to R2 and put
   their URLs on the run rows' config (columns exist).
   **Smoke test:** point a hand-inserted `interview_runs` row at your own
   cell, `StartScenarios`, talk to Mira for 5 minutes, listen back.
3. **Worker**: `cd workers/voices && wrangler secret put …` (see its
   README) `&& wrangler deploy`.
4. **Cal.com**: event type (Tue/Wed/Thu 9-15 PT + overnight slots for
   EU/Asia guests, §11.6), webhook → `/voices/cal-com-booked`.
5. **GitHub secrets**: `VOICES_SUPABASE_URL`, `VOICES_SUPABASE_SERVICE_KEY`,
   `VOXIMPLANT_ACCOUNT_ID`, `VOXIMPLANT_API_KEY`, `VOXIMPLANT_CALLER_ID`,
   `RESEND_API_KEY` (or `POSTMARK_TOKEN`), `CALCOM_BOOKING_URL`,
   `SLACK_WEBHOOK` (R2_* and GROK_API_KEY already exist).
6. **Dry runs** (phase 4): three end-to-end test interviews with Patrick /
   Trystan as guests; tune Mira's prompt from the recordings.
7. **Soft launch** (phase 7): first real guest from the inbound queue; no
   network announcement until 2-3 real interviews land (phase 8 flips on
   cross-promo via the `cross_show_callouts` table + X/YouTube/newsletter
   in `shows/age_of_ai.yaml`).

Open decisions §11 stay with Patrick (caller ID bought vs shared, consent
wording, Cal.com self-host vs cloud, Postmark vs Resend, slot windows,
first three guests). Defaults implemented: dedicated caller ID assumed,
soft-cap-45 + hard-cap-50, auto-reschedule once then lapse.

## Cost (spec §8, verified there)

~$4.50–7.00 per 45-min interview end-to-end (PSTN + Grok Voice + STT +
editorial passes + TTS + storage); ~$120–180/yr at biweekly cadence. Same
order as one daily show's API spend.

## Quality gates philosophy (spec §6 — keep both manual)

Real humans on tape ≠ AI news scripts. Gate 1 protects Patrick's editorial
reputation (~20-30 min/episode); gate 2 protects guest relationships and
consent (auto-approve day 7, never removed). Revisit relaxing gate 1 only
after 25 episodes if editorial veto rate < 5% and redaction rate < 10% —
and never remove gate 2.
