# Prompt + Grok API / Voice Review (July 9, 2026)

Follow-up to [`docs/prompt_review_2026_06_10.md`](../prompt_review_2026_06_10.md).
Scope: every show prompt surface, `_call_grok` / tracking, Grok TTS wiring, and
stale newsletter copy — checked against current xAI Chat Completions + TTS docs
(prompt caching via `x-grok-conv-id`, `cached_tokens` telemetry, TTS `speed`
0.7–1.5, 15k char cap). Drift guards: `tests/test_prompt_grok_review_2026_07_09.py`.

## Verdict

The June 10 prompt pass still holds for editorial quality. The biggest
**unclaimed** wins since then are infrastructure: sticky prompt-cache routing
was never wired, TTS `speed` never reached the single-voice Grok path, and two
Russian shows still capped chunks at 10k (risking the multi-chunk `<fast>` drop).
Those ship here. Bulk prompt rewrites and Voice/prosody experiments stay behind
landmine #17.

## Implemented (safe — no spoken-script change)

### 1. Prompt-cache sticky routing + telemetry
`engine.generator._call_grok` now accepts `cache_key` and sends
`x-grok-conv-id: nerra-<slug>` on every digest/podcast/retry call for that show.
`digests/xai_grok.grok_generate_text` gained the same optional `cache_key`
(Chat Completions header + Responses `prompt_cache_key`); fetch paths use
`nerra-fetch-x` / `nerra-fetch-web`. xAI automatically caches identical message
prefixes; the header maximizes hit rate by sticky-routing to one server. Cache
hits log `usage.prompt_tokens_details.cached_tokens` and flow into
`engine.tracking.record_llm_usage(..., cached_tokens=)`. Cost math still uses
full prompt tokens until cached pricing is added to `GROK_PRICING` (deferred —
needs a confirmed cached rate in the pricing table).

### 2. Grok TTS `speed` on the single-voice path
`synthesize()` / `synthesize_sections()` already accepted `speed` but only the
ElevenLabs branch and the dialogue path (`tts_dialogue.py`) forwarded it.
`_speak_with_grok` → `grok_speak_chunk` now pass `speed` through. Default `1.0`
keeps the request payload byte-identical for every show that does not opt in
(dp_pod already uses `1.05` on the dialogue path).

### 3. Russian shows `max_chars: 14000`
`finansy_prosto` and `privet_russian` overrode the network 14k default with
10k. Long scripts could split into multiple Grok TTS chunks and drop the
network `<fast>` wrap (landmine #17 safety guard). Aligned to 14000.

### 4. Anti-refusal educational fallback is show-generic
The digest refusal retry told every show to invent "financial concepts" —
wrong for SpaceX / FF / PT / etc. Now: "2–3 core concepts from this show's
topic domain."

### 5. Weekly newsletter prompts: "recap edition" retired
`shows/prompts/spacex_weekly.txt` and `shows/templates/weekly.txt.template`
still said "weekly recap edition" after the July 2026 full-Sunday-recap
retirement. Reworded to "weekly newsletter digest" + an explicit note that
this is email, not a spoken Sunday recap.

## Checked and left alone (with reasons)

| Item | Why |
|------|-----|
| Bulk `<<include:>>` of `_shared/accuracy_rules.txt` into show prompts | Mechanism is opt-in; README + June 10 review forbid bulk rewrites without per-show A/B. Snippets stay available for new shows / surgical edits. |
| Migrating digest/podcast to Responses API | Chat Completions still supported; Responses is preferred for *new* features. Migration is a large contract change (tools, streaming, cache key field name) with no listener benefit until we need those features. |
| `reasoning_effort` / Grok 4.5 model bump | Network is on grok-4.3 by design (landmine #13). Model bumps are operator cost/quality decisions, not a prompt-pass default. |
| Re-introducing speech tags / phonetic respellings / DELIVERY blocks | Landmine #17 — 100% regression rate on theory-driven TTS mods. |
| De-seeding third-gen tics (OV "Both sides agree…", EI menus, MAB openers) | July 2 network review already proposed these as A/B-gated; not auto-applied. |
| Digest length-ceiling / Cosmic Deep Dive expansion | Deferred behind the four-show length A/B (FF/PT/UC/Tesla class). |
| Cached-token discount in `_estimate_grok_cost` | Telemetry first; apply discount once `GROK_PRICING` has an explicit cached rate. |

## A/B-gated recommendations (NOT applied)

1. **Per-show few-shot exemplars** for podcast prompts that still describe
   shape without an ideal story block (OV/EI/M&A class) — high editorial
   leverage, one show at a time.
2. **Convert ban-lists → rotation menus** where June passes already proved
   the pattern (openers, deep-dive entries).
3. **Sunday weekly-summary segment prompt note** in daily podcast prompts
   for shows with `weekly_summary_segment: true` — clarify the host weaves
   one short look-back without turning the episode into a full recap.
4. **Optional `tts.speed` A/B** on one English show (e.g. 1.05 like dp_pod)
   only with operator listen evidence — the wire is now live for single-voice.
5. **Stable system-prompt prefix hygiene** — keep system prompts short and
   static; put day-varying context only in the user message so cache prefixes
   stay long. Most shows already do this; audit stragglers when editing.

## Operator follow-ups

- Watch `cached_tokens` in the next few `credit_usage_*.json` files / logs
  after merge; if consistently 0, verify sticky routing and system-prompt
  stability.
- When xAI publishes a clear cached-input rate for grok-4.3, add
  `cached_input_per_1m` to `GROK_PRICING` and subtract from cost estimates.
- Do **not** bulk-edit show prompts to use `_shared/` includes without A/B.
