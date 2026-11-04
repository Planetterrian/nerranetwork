# Model upgrade playbook

Written after the 2026-08-18 grok-4.6 outage: a network-wide, all-stages
model flip shipped in one evening and **7 of 12 scheduled shows failed the
next morning**. This document is the rule for how any future LLM model
change reaches production. It applies to `llm.model`, `fallback_model`,
`synth_model`, `reviewer_model`, `podcast_model`, the fetch-path model in
`digests/xai_grok.py`, and the translation pin in `engine/translate.py`.

## What happened (post-mortem, 2026-08-18)

PR #1019 moved every LLM stage from grok-4.3 to grok-4.6 (operator-directed,
merged 2026-08-17 22:53 PT). grok-4.6's digest latency was **5-10× grok-4.3**
on identical prompts, measured from committed per-episode metrics on the day:

| Show | 4.3 digest (prev. day) | 4.6 digest (day one) |
|---|---|---|
| planetterrian | 44 s | 420 s |
| models_agents_beginners | 36 s | 242 s |
| dp_pod | 55 s | 225 s |
| first_principles | 36 s | 205 s |

The four largest digest prompts (tesla, spacex, omni_view, modern_investing)
went past the 300 s per-request client timeout entirely — requests hung to
the timeout or the server disconnected mid-generation. Three failure shapes
resulted:

1. **Retry spiral.** The OpenAI SDK's default internal retry (2) sat *under*
   the tenacity retry on `generate_digest` (3 attempts), so one hanging
   upstream became 3 × 3 = nine 5-minute stalls — a 41-45 minute burn per
   show, ended by the CI step's 45-minute hard kill (spacex, omni_view,
   modern_investing) or by connection-drop exhaustion (tesla, exit 1).
2. **Budget blowout.** Shows whose LLM calls *succeeded* spent 15-20 extra
   minutes on them, pushing the ~25-32-minute long-form render past the
   45-minute step limit mid-ffmpeg (models_agents, fascinating_frontiers).
3. **Photo finish.** unintended_consequences finished a fully-published
   episode 0.35 s before the 45-minute kill; the commit step was skipped and
   the episode was orphaned — live on YouTube, R2, and in 544 inboxes, but
   absent from git (recovered by hand the same day).

The upgrade was reverted the same day (experiment `network-grok-46-upgrade`,
status `reverted`). Note what the registered revert triggers watched:
hallucination rate, reviewer flags, fetch tool-calls. **Nobody watched
latency.** The failure mode that actually fired was operational.

## The rules

### 1. One show first — never network-wide on day one

Stage any model change on a single show via its per-show YAML override
(`llm.model`, or `llm.podcast_model` for script-only trials — the dp_pod
grok-4.5 A/B was the correct shape). Prefer a mid-size news show whose
digest prompt is representative (planetterrian, models_agents). Run it for
**at least 3 scheduled days** before widening.

### 2. Gate on latency before quality

Before any widening, read `generate_digest` / stage durations from the
show's committed `metrics_ep*.json` and compare with its trailing week:

- p95 digest duration must stay **under 50% of the request timeout**
  (`NERRA_LLM_TIMEOUT_SECONDS`, default 300 s). A model that needs more
  time is not disqualified — but then the timeout must be raised *in the
  same PR*, and the arithmetic below re-checked.
- `_call_grok` logs a `Slow LLM completion` warning at >60% of the
  timeout budget. Any of these in the staged show's logs = do not widen yet.

The biggest shows (tesla `max_tokens: 5500`, spacex, modern_investing,
omni_view) are the canaries-in-reverse: they fail *first* under a slower
model. Widen to one of them explicitly before the rest of the network.

### 3. Keep the timeout envelope's arithmetic true

The envelope has three layers; each must fire before the one above it:

```
per-request timeout (NERRA_LLM_TIMEOUT_SECONDS, default 300 s)
  × tenacity attempts (3 on generate_digest / generate_podcast_script)
  = worst-case LLM stage ≈ 15 min          ← SDK max_retries is 0, always
< PIPELINE_TIMEOUT_SECONDS (3000 s = 50 min, SIGALRM, clean abort)
< step timeout-minutes (60, CI hard kill)
```

Drift guards: `tests/test_pipeline_safety.py::TestTimeoutEnvelope` (watchdog
below hard-kill; SDK retries off; timeout env-tunable) and
`tests/test_generator.py::test_client_disables_sdk_retries`. If a model
needs a bigger per-request timeout, recompute the whole chain — three
tenacity attempts at 900 s is 45 minutes and breaks the watchdog ordering.

### 4. Update pricing and the experiment register in the same PR

- `engine/tracking.py` `GROK_PRICING` must price the new model id before
  any show uses it (the retired grok-4-1-fast slug was mis-costed 6× for
  three months because it wasn't).
- Register the change in `docs/experiments.yaml` with a readout date and
  revert triggers that include **latency and run-success**, not just
  quality metrics.

### 5. Rollback must stay one line

`model:` in `shows/_defaults.yaml` is the rollback lever; per-show pins and
stage models must keep inheriting from it so one line really does revert the
network. If a refusal-fallback repoint rides along with an upgrade (the
fallback must always be a *different* snapshot than the primary), the
rollback plan includes repointing it back — write that in the experiment
entry.

### 6. Floating aliases never reach a published stage

`grok-latest`-style aliases let vendor releases change shipped content
silently (the translation stage rode one until 2026-08-18). Every stage
pins an explicit model id; `tests/test_llm_usage_pass.py` guards the
translation pin.


### 7. A pinned reasoning model streams, gets one bounded retry, and a retry never changes the arm (2026-09-24)

grok-4.7 writes a digest in 200–390 s where grok-4.3 takes 35–85 s, and a
NON-STREAMING request that sends nothing for that long is what gets
dropped: 9 of the launch cohort's first 24 episodes fell back to the
default on one transient error (five dropped connections at ~260 s, three
600 s timeouts, one pre-flight ping), and every fallback episode was the
thin one. xAI's own guidance for its reasoning models is to stream and to
lengthen the client timeout. What binds now:

- `llm.stream: true` on a pinned show (`engine.generator._stream_completion`):
  the completion is read as chunks, a stall is recognised by SILENCE
  (`NERRA_LLM_STREAM_IDLE_SECONDS`, default 180 s) and the request timeout
  is a wall between chunks. `False` is the exact pre-existing request —
  never flip it on an established show without this playbook's staging.
- A transient failure on a pinned model gets ONE same-model retry after 20 s
  (`_call_pinned`, `llm.pinned_model_retries`), only while the pipeline
  budget leaves room for the retry AND the rest of the episode
  (`PINNED_RETRY_RESERVE_S`); a 5xx still switches at once. The envelope
  arithmetic in rule 3 gains that one attempt — recompute it if you raise
  the retries.
- A RETRY of a digest that already exists (run_show's structural
  regeneration) runs with `allow_model_switch=False`: a pinned model that
  fails there raises `PinnedModelUnavailable` and the first digest is kept.
  Top World Ep2 (2026-09-24) lost a 1,548-word 4.7 digest to a 908-word 4.3
  one exactly this way.
- The pre-flight ping sends the show's own `reasoning_effort` (a reasoning
  model at default effort against a 30 s ping is the Europe Ep1 fallback)
  and a pinned model gets two attempts.
- Read `llm_pinned_fallback_share_7d` / `llm_pinned_recovered_7d` on the
  dashboard and the trial report's fallback / time-to-first-token line
  before scoring a trial: a fallback episode is never a trial data point.

## Audio changes (added 2026-11-03)

The same discipline, for anything a listener hears. The record before this
section: the Oct 13 story beat and the Oct 14 music swell each shipped to every
show and were reversed within a day; the Oct 20 `[breath]` tag reached 14
episodes before the operator heard it, and every one was re-voiced; 11 commits
to `shows/_defaults.yaml` in October (five of them between Oct 13 and 20),
and 13 since Oct 1. CLAUDE.md's Oct 20 rule — *a candidate is LISTENED to on a shipped
episode before it ships to a slate* — had no mechanism. Now it has three, and
a place to write the listen down.

### A1. One show first — the value in that show's YAML

`engine.config.load_config` deep-merges each show's YAML over
`shows/_defaults.yaml`, so a trial of any `audio:` / `tts:` value IS that value
in one or two show YAMLs (`voice_declick: strong` on Vancouver and `tts.speed`
on the DP Pod are trials that stuck). There is no canary layer and there must
not be one: a third place a value can live is against the one-owner rule.
Pick a show whose voice and theme the change is about. Listen to the first
episode. Then move the value to `_defaults.yaml` (or delete it).

### A2. Listen before the slate, and have something to listen to

- **A rehearsal of a show**: Actions "Run show" → the show → `rehearse: true`.
  The run fetches, writes, synthesizes and mixes the day's real episode
  through the real chain (`run_show.py --rehearse`), uploads the MP3 and the
  exact text it voiced as a 3-day artifact, and commits and publishes
  nothing (the episode numbering is untouched; the run's working tree is
  discarded). Dispatch it on a branch that carries the change.
- **A minute of a committed script through the builders**: Actions
  "Probe audio chain" with `script` = a committed `digests/<dir>/<ep>_tts.txt`,
  `seconds` (75), `variants` (`legacy` is the chain as shipped; a name the
  builders on this tree do not offer is reported and skipped) and an
  optional `voice`. The probe voices the first minute of the REAL script on
  the show's voice (cents of TTS) and renders each variant through
  `master_voice_track` and `mix_with_music` with the show's own theme and
  settings; it attaches before/after audio with loudness, clicks and hiss
  per file. A `tts.dialogue_mode` show renders at speed 1.0 and 1.05.
  Locally, `--dry-run` prints the ffmpeg commands the builders would issue
  with no API key. Nothing it writes goes under `digests/` or the feeds.
- **A chain or mix builder change** (`voice_chain_filters`, `_final_mix_cmd`,
  `_music_*_cmd`, `master_voice_track`): the probe on a flagship script AND a
  Mira script, at minimum, before the PR is opened.

### A3. The listen is written down

`tests/fixtures/defaults_audio_snapshot.yaml` holds the `audio:` and `tts:`
sections of `shows/_defaults.yaml`. `tests/test_listen_before_slate_2026_11_03.py`
fails when a value differs from the snapshot, and it stays red until two
things happen in the same PR: the snapshot is updated (the test file prints
the command) AND `docs/listens.md` gains a line in the form

    <key> — listened by <who> on <date>, episode <show> Ep<N> · snapshot <fingerprint>

where the fingerprint is the one the failing test prints for the new values.
This is a reminder with teeth, not proof: the guard can confirm that a line
was written, never that the listening happened. The PR template asks for the
rehearsal artifact link, the listener and the trial show beside it.

### A4. Rollback is one line, and the readout is a listen

A `_defaults.yaml` value reverts in one line (plus the snapshot and a
`docs/listens.md` line saying what was heard). A builder change reverts by
PR. The count of "Re-synthesize Episode" runs is NOT the readout for this
section — most of those runs are corrections of content, not reversals of an
audio change. The readout is `docs/listens.md`: one line per ⚠️ AUDIO change,
and zero network-wide audio reversals inside 48 h of a merge.

### A5. The operator's listening protocol (30 minutes, first session)

Four listens nobody has done, each a question a measurement cannot answer.
Each answer goes into `docs/experiments.yaml` as a `listen:` note on the
entry it belongs to (hit / miss / inconclusive, and what was heard), so the
next reviewer does not re-ask:

1. **Brightness (Patrick's voice).** A blind A/B of one Tesla minute against
   one NPR News Now minute, both normalized to -16 LUFS with the same
   `loudnorm`, on the same headphones. The 5.5–8.5 kHz share measured
   -13.2 dB against NPR's -20.7 — a listen, not a chain change, is the only
   admissible next step.
2. **Mira's residual ticks.** Omni View Top World Ep041 (2.57 clicks/min on
   the measurement) on headphones: are the sub-millisecond ticks audible?
3. **Collingwood's "calling wood".** Collingwood Ep006 at the place the
   transcript reads "calling wood": real on the audio, or Whisper's?
4. **FP's English halves on Olya.** Финансы Просто Ep090: how the English
   terms sit on the Russian voice.

Group C27 in the Nov 3 review's ranked plan. Prompts stay as they are
(landmine #17): the protocol produces answers, not changes.

## The instrument (added 2026-09-21)

`scripts/model_trial_report.py` answers rule 2 from the committed record, so
a trial's verdict is reproducible later by anyone with no API key:

```
python scripts/model_trial_report.py --since 2026-09-22
python scripts/model_trial_report.py --since 2026-09-22 --shows omni_view
```

It reads every show's `digests/<slug>/metrics_ep*.json` (`stages` →
`{name, duration_s, success}`), dates each episode from the sibling digest
filename — **never file mtime, which a fresh checkout rewrites** — and
reports p50/p95/max per stage for the trial window against a trailing
baseline. It exits 1 when an LLM stage's p95 passes 50% of the request
timeout, regresses more than 50% against baseline, or any stage failed.
Render and fetch stages are reported but never gate a MODEL trial.

**It runs nightly since Nov 3 2026** (`nightly-maintenance.yml`, step "Read
the script-arm latency gate"): a ROLLING window (`--since` defaults to today
minus 14 days — a fixed date measures an ever-longer past) over the six shows
whose script stage runs on a pinned model arm, against the 600 s request
timeout the run uses, written to `api/model_trial.json` with `--out`. A show's
digest directory is read from its YAML `episode.output_dir` (Tesla writes to
`digests/tesla_shorts_time`). The dashboard carries the same read as the live
metric `script_stage_p95_s_14d_<show>` so a register entry can name it. The
first nightly read (Nov 4 2026): SpaceX p95 903 s — 150% of the timeout.

## Staged migrations on record

| Date | Change | Outcome |
|---|---|---|
| 2026-08-18 | grok-4.3 → 4.6, all stages, one evening | REVERTED same day; 7 of 12 shows failed |
| 2026-08-18 | staged 4.6 trial (dp_pod script, FPD/UC whole-show, synth, reviewer) | FPD/UC arms withdrawn 08-27 on the latency gate; the rest held |
| 2026-09-21 | grok-4.6 → 4.7, two sites (reviewer, omni_view script) | `grok-47-staged-migration`, readout 09-25 |
| 2026-09-23 | grok-4.7 on the 13 new shows' writing stages | `new-shows-grok-47-2026-09-23`; 9/24 episodes fell back by 09-24 → rule 7 |

## Quick checklist for the PR that changes a model

- [ ] Only one show's YAML (or one stage) changes on day one
- [ ] `GROK_PRICING` has the new id
- [ ] `docs/experiments.yaml` entry with readout + latency/run-success revert triggers
- [ ] `NERRA_LLM_TIMEOUT_SECONDS` / envelope arithmetic rechecked if the model is slower
- [ ] A reasoning model pinned per show carries `llm.stream: true` and the bounded retry (rule 7)
- [ ] After 3+ scheduled days: metrics durations reviewed, no `Slow LLM completion` warnings
- [ ] Widen to one flagship-size show before the network
- [ ] Landmine #17 still applies: prose changes with the model — A/B-listen
