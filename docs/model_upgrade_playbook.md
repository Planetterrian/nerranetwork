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

## Quick checklist for the PR that changes a model

- [ ] Only one show's YAML (or one stage) changes on day one
- [ ] `GROK_PRICING` has the new id
- [ ] `docs/experiments.yaml` entry with readout + latency/run-success revert triggers
- [ ] `NERRA_LLM_TIMEOUT_SECONDS` / envelope arithmetic rechecked if the model is slower
- [ ] After 3+ scheduled days: metrics durations reviewed, no `Slow LLM completion` warnings
- [ ] Widen to one flagship-size show before the network
- [ ] Landmine #17 still applies: prose changes with the model — A/B-listen
