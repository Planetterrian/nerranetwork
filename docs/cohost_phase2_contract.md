# Phase 2 — Patrick in the room (co-host conference) — build contract

Goal: every Mira interview (The Age of AI and Nerra Voices) has three
participants in one live session: the guest (browser studio, WebRTC), Patrick
as co-host (browser studio, WebRTC, best audio), and Mira (Grok Voice Agent).
Each participant is recorded on its own clean track. Both humans also
record locally in the browser at full quality (Riverside model) and upload
chunks during the call; post-production prefers the local tracks when they
are complete and falls back to the Voximplant tracks.

## Roles and identities

* Voximplant users (application `nerra-voices`): `guest` (exists) and a new
  `host` user. Worker env: `VOX_GUEST_USER/VOX_GUEST_PASSWORD` (exist),
  `VOX_HOST_USER/VOX_HOST_PASSWORD` (new). `voximplant_client.add_user()`
  creates the user for the operator bootstrap.
* Studio page roles: `?interview=<uuid>&show=<slug>&role=guest|host`.
  Default role `guest`. Host links carry `&token=<ADMIN_TOKEN>` and the
  Worker only issues host credentials when the token matches.

## Session topology (single Voximplant session per interview)

1. Guest joins from the studio → inbound call with `X-Run-Id` (as today).
   This call starts the session.
2. Scenario creates a local conference (`VoxEngine.createConference`,
   hd_audio) and adds the guest call. Grok agent media is bridged to and
   from the conference (Mira hears the mix; everyone hears Mira).
3. If `interview_runs.host_mode = true` (default true from Phase 2), the
   scenario dials the host user with `VoxEngine.callUser({username: host,
   video: false, extraHeaders: {"X-Run-Id": run_id, "X-Role": "host"}})`.
   The host studio page is already logged in and auto-answers. On Failed
   (host not online) retry every 20 s until connected or the hard cap.
   Mira's opening `responseCreate` waits for the host leg OR 20 s,
   whichever first, so the show opens with everyone present.
4. Host leg drop: interview continues; scenario re-dials the host every
   20 s; `host_joined_at` / `host_left_at` recorded via the webhook.
5. Guest leg drop: existing behaviour (Disconnected → webhook). The host
   leg is hung up after the guest leaves.

## Recording

* `guestCall.record({stereo:true, hd_audio:true})` → L = guest mic, R = what
  the guest hears (Mira + host). Existing `recording_guest_url` semantic.
* `hostCall.record({stereo:true, hd_audio:true})` → L = host mic. New
  `recording_host_url`.
* `miraRecorder = VoxEngine.createRecorder({hd_audio:true})`;
  `grokAgent.sendMediaTo(miraRecorder)` → Mira only. New `recording_mira_url`.
* Video recorder unchanged (guest camera + mixed audio).
* Local browser recording (both humans): `MediaRecorder` on the selected
  mic, `audio/webm;codecs=opus`, 48 kHz, `audioBitsPerSecond: 192000`,
  `timeslice = 5000` ms, echoCancellation/noiseSuppression/autoGainControl
  OFF for the local track (the call track keeps its defaults). Chunks are
  POSTed as they arrive; on hangup the page flushes remaining chunks and
  calls upload-done. `local_<role>_url` on the run row points at the R2
  manifest.

## Worker API (workers/voices/src/index.ts) — additions

* `POST /voices/studio-auth {key, role, interview?, token?}` → `{token, user}`.
  role=host requires `token === ADMIN_TOKEN`; uses VOX_HOST_* creds.
* `GET /voices/studio-state?interview=&show=&role=` → adds
  `host_mode`, `host_joined`, `guest_joined` (from interview_runs columns
  `host_joined_at` / `guest_joined_at`, set by the interview-complete
  webhook and by a new `POST /voices/leg-event {run_id, role, event:
  "joined"|"left"}` the scenario calls on each leg's Connected/Disconnected).
* `POST /voices/upload-chunk?run_id=&role=&seq=` body = raw webm bytes
  (`Content-Type: audio/webm`). Stores at R2 key
  `<r2_prefix>/local/<run_id>/<role>/<seq:05d>.webm` via a new R2 binding
  `VOICES_R2` (wrangler.toml `[[r2_buckets]] binding="VOICES_R2"
  bucket_name="podcast-audio"`). Max 10 MB per chunk. Auth: guest uploads
  need the run to be `in_progress|awaiting_guest|fired`; host uploads
  need `token`.
* `POST /voices/upload-done {run_id, role, chunks, mime, started_at,
  duration_ms}` → writes manifest `<prefix>/local/<run_id>/<role>/manifest.json`
  and sets `interview_runs.local_<role>_url` to the manifest URL.
* `POST /voices/interview-complete` accepts new payload fields:
  `voximplant_host_record_url`, `voximplant_mira_record_url`,
  `host_joined_at`, `host_left_at`, `host_attempts`.
* Triage/booking unchanged. `handleCalComBooked` studio URL for the guest
  gains `&role=guest`. A host link is
  `<studio>?interview=<id>&show=<slug>&role=host&token=<ADMIN_TOKEN>`;
  the Worker exposes `GET /voices/host-link?interview=` (admin) returning it.

## Supabase (supabase/migrations/20260906_cohost_conference.sql)

`interview_runs`: `host_mode boolean not null default true`,
`recording_host_url text`, `recording_mira_url text`, `local_guest_url
text`, `local_host_url text`, `host_joined_at timestamptz`, `host_left_at
timestamptz`, `guest_joined_at timestamptz`, `host_attempts int default 0`.
`interviews`: `host_mode boolean not null default true`.

## Pipelines

* `fire_interviews.py`: writes `host_mode` on the run; at fire time emails
  and SMSes Patrick (OPERATOR_EMAIL / OPERATOR_PHONE env) the host link;
  the T-2h reminder includes it too. Mira's prompt gets the co-host block
  (below) via new `load_prompt` subs `cohost_name`, `cohost_block`.
* `post_interview.py`: build three mono tracks — guest, host, mira — using
  local uploads when their manifest exists and is complete
  (`pipelines/voices/audio/local_tracks.py`: download chunks in seq order,
  ffmpeg concat, resample 48 kHz; alignment = trim to the Voximplant
  track's start using cross-correlation against the Voximplant guest/host
  channel, fallback = no offset), else Voximplant per-leg L channels.
  Whisper per track → speaker-labelled transcript (`Mira:`, `Patrick:`,
  `<Guest name>:`), merged by segment start time. `mix_tracks.mix_three()`
  → leveled mono mix. R2 keys `<prefix>/raw/<run>_{guest,host,mira}.wav`.
  Editorial passes get `{{cohost_name}}` so notes/chapters attribute
  correctly. Everything degrades: no host track → today's two-track path.
* Mira prompt co-host block (shared prompt, tokenised):
  "CO-HOST: Patrick Novak, the network's founder, is in the room as your
  co-host. He may interject with a question, a clarification, or to fix a
  technical problem. When he speaks, answer him briefly if he asked you
  something, otherwise acknowledge in a few words and hand the floor back
  to the guest. He is not the interviewee: never interview Patrick, never
  ask him the lightning round, and keep the guest as the centre of the
  conversation. If Patrick says 'let's pause' or 'hold on', stop talking
  and wait for him."

## Tests / docs

* `tests/test_cohost_conference.py` (scenario string contracts, Worker
  routes, migration columns, prompt block, fire host link, post-interview
  track selection with fakes, local_tracks concat/alignment with synthetic
  audio), plus updates to test_age_of_ai_show.py contracts if they pin the
  old bridge line.
* `docs/age_of_ai_resilience.md`: new rows (host not online, host drop,
  local upload gaps). `docs/age_of_ai_plan.md` bootstrap: Voximplant
  `host` user + Worker secrets + R2 binding + deploy.
