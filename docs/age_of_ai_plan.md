# The Age of AI — AI-hosted interview show (design + runbook)

**Status:** Phase 1 shipped (July 2026). Distribution OFF at launch (RSS + site
only, no cron — episodes are produced via `workflow_dispatch` when an
interview packet is ready).

## Concept

The Age of AI is the Nerra Network's interview show with a twist that *is* the
premise: the host is an AI. **Nerra** — the network's resident AI — sets up
and conducts interviews with real people about living and working through the
AI transition: founders, teachers, artists, tradespeople, researchers,
skeptics. The guest is always a real human; their words are always their own.

The show inverts the usual arrangement of every other Nerra show (AI produces,
human curates): here the machine asks the questions and the human provides the
substance. That inversion is stated on air, every episode.

## Non-negotiable ethics rules (enforced in code + prompts)

1. **Never fabricate guest words.** The guest's answers enter the pipeline
   verbatim and both prompts require verbatim fidelity (light spoken-flow
   edits only — fillers, false starts). The digest stage may *select and
   order* answers, never rewrite their meaning.
2. **Consent gates publication.** `engine.interview.compile_packet` refuses
   to build an episode packet unless the guest record has
   `consent_to_publish: true`.
3. **AI voicing needs separate consent.** Guest turns are synthesised with a
   synthetic voice ONLY when `consent_ai_voice: true`
   (`voice_mode: ai_voiced`). Otherwise the episode runs in `quoted` mode:
   Nerra narrates and quotes the guest — one voice, clearly attributed.
4. **Disclosure on air.** Every episode says the host is an AI; `ai_voiced`
   episodes additionally say the guest's answers are their own written words
   performed by a synthetic voice with their permission.

## Pipeline (two stages, one file each)

### Stage A — Guest pipeline (operator-in-the-loop CRM)

`shows/guest_queues/age_of_ai.yaml` holds guest records with a `stage` field:

```
prospect → invited → accepted → questions_sent → answers_received
        → compiled → published          (or → declined at any point)
```

Operator CLI — `scripts/age_of_ai_guests.py`:

| Command | What it does |
|---|---|
| `list` | Pipeline overview + next action per guest |
| `add <id> --name … --angle …` | Add a prospect |
| `invite <id>` | Draft a personalized invitation email (Grok if `GROK_API_KEY` is set, deterministic template otherwise) → `digests/age_of_ai/outreach/<id>_invite.md` |
| `questions <id>` | Draft a tailored question set → stored on the record + `outreach/<id>_questions.md` |
| `ingest <id> --answers <file>` | Record the guest's written answers (`Q:` / `A:` markdown) |
| `compile <id>` | Consent-checked: build the interview packet and append it to the topic queue |

The AI drafts the outreach; **the operator sends it** (from their own inbox)
and pastes the replies back. Nothing emails anyone automatically in Phase 1.

### Stage B — Episode production (standard narrative pipeline)

`shows/age_of_ai.yaml` is a `narrative_mode: true` show whose
`topic_queue_file` (`shows/topic_queues/age_of_ai.yaml`) contains **compiled
interview packets** in the standard queue schema (`id`/`title`/`brief`/
`produced` + interview extras: `guest_id`, `voice_mode`, `guest_voice_id`).
An empty queue is a clean skip (`narrative_queue_empty`) — the show simply
doesn't publish until an interview is ready.

- **Digest stage** → an *interview edit plan*: episode arc, which answers to
  feature in what order, framing notes. Guest answers stay verbatim.
- **Podcast stage** → the spoken script. Two modes, chosen per episode by the
  hook (`shows/hooks/age_of_ai.py` reads the upcoming packet):
  - `ai_voiced` — two-voice dialogue script (`NERRA:` / `GUEST:` labels) on
    the existing `engine/tts_dialogue.py` path (DP Pod infrastructure).
    Voices: Nerra = Grok built-in `eve`, guest default = Grok built-in `ara`,
    per-guest override via the packet's `guest_voice_id`.
  - `quoted` — the hook flips `config.tts.dialogue_mode = False` for the run;
    Nerra narrates single-voice and quotes the guest with attribution.
- **post_generate hook** marks the guest `published` (honours
  `NERRA_HOOKS_READONLY`, so `--test`/`--rehearse` runs never advance CRM
  state).

## Launch shape

- No cron entry (CRON_MAP and the scheduler Worker are untouched — the
  punctuality drift guard stays at 14 slots). Produce episodes with
  `Run Podcast Show → workflow_dispatch → age_of_ai` once `compile` has
  queued a packet, or locally: `python run_show.py age_of_ai`.
- X / YouTube / newsletter / multilingual: all off. RSS + site page only.
- Ep1 target: Nerra interviews **Patrick** (network founder) about building
  an AI podcast network — seeded as the first guest record. His real answers
  make the debut; nothing ships until they exist.

## Operator checklist (one-time)

1. Add cover art `assets/covers/age-of-ai.jpg` (1200×1200).
2. Answer the Ep1 questions: `python scripts/age_of_ai_guests.py questions
   patrick-novak`, write answers, `ingest`, set the consent flags in the
   guest record, `compile`.
3. Dispatch the episode; A/B-listen the `eve`/`ara` voices (landmine #17
   applies to any future voice change).
4. When a cadence emerges, add a cron via the standard CRON_MAP + scheduler
   Worker SLOTS pair.

## Later phases (not in Phase 1)

- **Phase 2 — real guest audio.** Guests record answers; the pipeline splices
  their actual audio between Nerra's turns (new assembly step next to
  `engine/tts_dialogue.py`; per-turn loudness normalization).
- **Phase 3 — live interviews.** Real-time voice conversation (Grok realtime
  voice session), recorded and edited by the same packet machinery.
- **Outreach automation.** Send invitations via Resend + a reply-ingestion
  inbox, with the operator approving each send.
