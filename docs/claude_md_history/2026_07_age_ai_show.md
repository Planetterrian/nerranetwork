# The Age of AI — show notes (Jul 2026 – Oct 15 2026)

Moved verbatim from CLAUDE.md on 2026-11-03; the rules that still bind are summarised there.

- **AOAI** (The Age of AI) — the network's **AI-hosted LIVE interview show**
  (July 2026): Mira, an AI documentarian persona (Grok voice `ara`,
  deliberately NOT the Patrick clone), interviews REAL guests live through a
  Voximplant scenario bridged to a Grok Voice Agent, dual-track records the
  conversation, and the episode is produced from the real recording.
  **Since 2026-09-09 every interview is a ROOM** — the guest (and an optional
  co-host) joins from `age-of-ai-studio.html`, picks a mic and presses Join.
  **Since 2026-10-27 there are NO phone-call interviews at all** (Patrick:
  the sound is too poor for the show). A guest whose computer won't
  cooperate opens the same link in their phone's browser, or presses "Pick
  another time" (`/voices/studio-reschedule`); `/voices/studio-phone` and
  `/voices/admin/call-guest` answer 410, the scenario refuses a PSTN start,
  and nothing in `fire_interviews.py` dials. Never reintroduce a phone call,
  in code or in copy. An
  earlier version of this paragraph said Mira "phones" guests, and that claim
  had also reached `engine/brand.py` as the BASIS of the network's
  first-of-its-kind claim; corrected 2026-09-20. Do not describe the show as
  a phone-call show on any surface. **Production does NOT go
  through run_show** — `shows/age_of_ai.yaml` exists for registry/publish
  surfaces only, and its narrative mode + permanently-empty topic queue make
  an accidental `run_show.py age_of_ai` a clean `narrative_queue_empty` skip.
  The real pipeline is **Nerra Voices**: `pipelines/voices/` + the five
  `nerra_voices_*.yml` workflows + `workers/voices/` (webhooks, Mira's 3
  in-call tools, triage/review UIs — Cloudflare Worker at
  `api.nerranetwork.com/voices/*`, a documented deviation from the spec's
  Vercel sketch) + `supabase/migrations/20260704_nerra_voices_schema.sql`
  (separate Supabase instance; 6 tables are the state machine) +
  `voximplant/scenarios/age_of_ai_interview.js` (the central glue: browser
  room → Grok Voice bridge → stereo recorder → hangup webhook; 50-min hard
  cap). Flow: apply form → Patrick triage (~30 s) → Cal.com booking → T-1d
  LLM prep brief emailed to guest → T-2h SMS → fire (5-min cron,
  drift-tolerant window, idempotent) → live call → post-processing (R2, mix,
  per-channel Whisper STT — the stereo tracks ARE the diarization, 8
  schema-validated editorial passes) → **gate 1: Patrick editorial review
  (never times out into publish)** → **gate 2: guest transcript approval
  (day-4 reminder, day-7 auto-approve; redactions cut from audio FIRST at
  assembly)** → Mira narration TTS + ffmpeg assembly + waveform video →
  publish via the standard `engine.publisher` surface. Guest words are
  verbatim; every episode discloses the AI host. Spec-as-implemented +
  operator bootstrap (Voximplant/Supabase/Cal.com/Worker provisioning +
  phase-1 smoke test): [`docs/age_of_ai_plan.md`](docs/age_of_ai_plan.md);
  drift guards: `tests/test_age_of_ai_show.py` (registry no-op shape, spec
  artifacts, dispatch-event coherence, validators, the two human gates).
  **Distribution (2026-09-20, operator-directed): newsletter + YouTube ON,
  X still posted by hand from @nerranetwork, multilingual off** (a dub of a
  guest's own recorded voice is a different consent question, not a config
  flip). Those two flags had been read by NOTHING until this date — the
  interview shows bypass `run_show.py`, where every other show's newsletter
  send and YouTube upload live, so flipping them looked like enabling
  distribution and did nothing, the same class as the OP3-prefix hole.
  `pipelines/voices/publish_episode.py` now reads them:
  `maybe_send_newsletter` reuses `engine.newsletter.send_show_newsletter`
  (so the sanitizer, the contrast check and the 20-hour double-send guard all
  apply) and `maybe_publish_youtube` uploads the waveform MP4 the produce
  step already renders — long-form only, no Shorts/thumbnails/dubs/policy
  tier, recorded in `digests/age_of_ai/youtube_videos.json` so the analytics
  fetcher and the adaptive policy see it. Both run AFTER the rows flip to
  `published` and swallow their own failures: the audio in the feed is the
  product. The video URL is DERIVED from the audio URL
  (`waveform_video_url` — `<prefix>/video/<name>.mp4`) and HEAD-checked,
  because the produce step only ever put it in an email. Any new show that
  bypasses run_show inherits this hole; wire its distribution explicitly.
  **Oct 15 2026 — Grok Voice 3.0 (register `grok-voice-3-2026-10-15`;
  guards `tests/test_grok_voice_3_2026_10_15.py`).** 3.0 is the
  speech-to-speech model behind the Voice Agent API — Mira's live room — and
  NOT the `/v1/tts` endpoint the shows synthesise through, which has no model
  id (the shows are untouched). The `grok-voice-latest` alias moved to 3.0 on
  Oct 14 and 2.0 is deprecated, so Mira was upgraded by the alias before any
  change here; **the model is PINNED now** (`grok-voice-3.0` in
  `voximplant_client.DEFAULT_GROK_VOICE_MODEL` and the scenario fallback;
  `GROK_VOICE_MODEL` overrides) — xAI's production guidance and the network's
  floating-alias rule; the next version is adopted after a rehearsal. From the
  3.0 docs: the scripted narration read runs `reasoning.effort: "none"`, the
  live interview pins `"high"`; the fire step writes `interview_runs.keyterms`
  (guest, organisation, title, show, network, hosts; migration
  `20261015_interview_runs_keyterms.sql`, applied Oct 15) and the scenario
  sends them as `audio.input.transcription.keyterms` — an insert on a database
  without the column retries without it; Mira's prompt is reorganised under
  xAI's recommended H2 order (Role & Persona / Objective / Conversation Flow /
  Guardrails & Escalation / Voice & Communication Style / CRITICAL
  INSTRUCTIONS) with every earlier paragraph kept verbatim (⚠️ AUDIO — the
  first interview is the listen; the guide's trim to a shorter prompt is the
  next A/B, not this one). `idle_timeout_ms` and `resumption` were read and
  NOT adopted: the first conflicts with the hold-the-silence rule, the second
  needs the Voximplant connector to pass `conversation_id`. Operator: run the
  scenario deploy workflow so the pin and the session settings go live.
