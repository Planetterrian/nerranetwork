# LLM Model Audit — Nerra Network

> Generated 2026-04-16 on branch `claude/audit-llm-models-9dpgL`.
> Scope: every LLM model referenced by the production pipeline, plus
> reliability, effectiveness, suitability, and cost-effectiveness review.
>
> **Status:** Recommendations 1, 2, 3, 4, 5, 6, 7, 9 in §7 were implemented
> in the same branch (commits after the initial audit). The "Not
> recommended" items remain deliberately unimplemented. The inventory
> below describes the state *before* those changes; current state is
> captured in `shows/_defaults.yaml` and the show YAMLs.
>
> **2026-05-01 update — Grok 4.3 migration:** xAI released `grok-4.3`
> on 2026-04-30 with always-on reasoning at **$1.25 / $2.50 per 1M
> tokens** (vs. the entire `grok-4.20-*` family at $2 / $6). Migrated
> in two PRs:
>
> 1. **Network default + synth + per-show overrides** (PR #278) —
>    flipped `shows/_defaults.yaml`, Tesla and Modern Investing
>    per-show YAMLs, plus the `_call_grok()` and synthesiser hard-coded
>    defaults. Collapses recommendations §7.4 (A/B reasoning on Tesla
>    / MIT) and §7.6 (widen synthesiser to reasoning variant) into a
>    single drop-in upgrade that is also ~55% cheaper per episode.
> 2. **Tool-use path** (PR #283) — `digests/xai_grok.py:grok_generate_text()`
>    default flipped from `grok-4.20-non-reasoning` to `grok-4.3` once
>    operator confirmed `grok-4.3` supports the `x_search` and
>    `web_search` built-in tools through the Responses API. Both
>    callers in `engine/fetcher.py` (X account fetch, web search
>    backfill) now route through 4.3.
>
> Refusal fallback stays on `grok-4.20-reasoning` so a refusal
> genuinely switches snapshot rather than retrying the same primary.
> Reviewer (`grok-4-1-fast-non-reasoning`) is unchanged — already the
> cheapest tier.

---

## 1. Executive summary

- The network is **100% xAI/Grok**. Every LLM call — digest, podcast script,
  cross-show synthesis, episode review, and refusal fallback — routes through
  `https://api.x.ai/v1` via the OpenAI-compatible client.
- All 10 shows inherit a **single default model** (`grok-4.20-non-reasoning`,
  `shows/_defaults.yaml:13`). No per-show `llm.model` override exists.
- A **single fallback model** (`grok-4`) is hard-coded in
  `engine/generator.py:42` for refusal recovery. It is 1.5× the input price
  and 2.5× the output price of the primary model.
- A **cost-optimised reviewer** (`grok-4-1-fast-non-reasoning`) is
  hard-coded in `review_episodes.py:1151` and is ~10× cheaper than the primary.
- A **tool-use variant** (`grok-4.20-multi-agent`) is selected in
  `digests/xai_grok.py:68` when web/X search tools are requested.
- Overall the model selection is **fit for purpose and defensible on cost**,
  but it has three weaknesses: (a) single-vendor risk, (b) a redundant "dated"
  variant list in pricing that invites drift, and (c) `grok-4` as the refusal
  fallback is the most expensive model the network touches — cheaper, more
  permissive options exist in the same family.

---

## 2. Inventory — every model reference

| # | Model | Where | Purpose | Config-driven? |
|---|-------|-------|---------|----------------|
| 1 | `grok-4.20-non-reasoning` | `shows/_defaults.yaml:13` | Default for digest + podcast across all 11 shows | YAML default |
| 2 | `grok-4.20-non-reasoning` | `engine/generator.py:82` | Hard-coded function default in `_call_grok()` (belt-and-suspenders) | Hard-coded |
| 3 | `grok-4.20-non-reasoning` | `engine/synthesizer.py:411` | Cross-show briefing generator | **Hard-coded** |
| 4 | `grok-4.20-non-reasoning` | `digests/xai_grok.py:25` | Default for legacy helper | Hard-coded |
| 5 | `grok-4.20-multi-agent` | `digests/xai_grok.py:68` | Tool-use path (xAI SDK: `web_search`, `x_search`) | Hard-coded |
| 6 | `grok-4` | `engine/generator.py:42` (`_LLM_FALLBACK_MODEL`) | Refusal fallback after educational retry, used at lines 983, 996, 1324, 1336 | Hard-coded |
| 7 | `grok-4-1-fast-non-reasoning` | `review_episodes.py:1151` | Optional AI quality review | **Hard-coded** |
| 8 | `gpt-4` | `tests/test_config.py:124,284,306,568,575` | Test fixture only (config validation) | Test-only |

Models present in `engine/tracking.py:22-39` pricing table but **not called
anywhere in code**: `grok-3`, `grok-3-mini`, `grok-4.20-reasoning`,
`grok-4.20-0309-non-reasoning`, `grok-4.20-0309-reasoning`,
`grok-4.20-multi-agent-0309`, `grok-4-1-fast-reasoning`, `grok-2`. These are
kept for historical cost reporting only — worth pruning if no legacy
episodes still report them.

### Per-show generation parameters (all use the default model)

| Show | Digest temp | Podcast temp | Max tokens (digest/podcast) | Chain |
|------|-------------|--------------|-----------------------------|-------|
| tesla | 0.5 | 0.7 | 5000 / 8000 | yes |
| omni_view | 0.5 | 0.7 | 4000 / 8000 | no |
| fascinating_frontiers | 0.5 | 0.75 | 3500 / 8000 | yes |
| planetterrian | 0.5 | 0.70 | 3500 / 8000 | yes |
| env_intel | 0.5 | 0.7 | 3500 / 8000 | no |
| models_agents | 0.5 | 0.7 | 3500 / 8000 | no |
| models_agents_beginners | 0.4 | 0.75 | 5000 / 6000 | no |
| finansy_prosto (ru) | 0.4 | 0.75 | inherits / varies | no |
| privet_russian (ru) | 0.5 | 0.75 | 4000 / 5000 | no |
| modern_investing | 0.5 | 0.7 | 4000 / 8000 | yes |

---

## 3. Reliability

**Strengths**

- **Refusal recovery is explicit.** `engine/generator.py` runs an
  anti-refusal suffix → educational-prompt retry → **different model**
  progression (lines 966–1005 for digest, 1315–1336 for podcast). This is
  more robust than most single-call pipelines and directly addresses the
  landmine noted in `docs/pipeline_audit_april2026.md` §P0.
- **Only transient API errors are retried** (`_TRANSIENT_ERRORS` =
  `APITimeoutError`, `APIConnectionError`, `RateLimitError`). Permanent
  errors fail fast — avoids 3× credit waste.
- **`finish_reason=length` is logged** at `engine/generator.py:116-120`,
  so truncation is observable rather than silent.

**Risks**

- **Single-vendor dependency.** Every show fails if xAI has an outage or
  deprecates a model id. There is no Anthropic/OpenAI escape hatch. The
  fallback model is *still xAI*.
- **`grok-4.20-*` ids have already rotated once** — the pricing table still
  carries `-0309-` dated variants. If xAI issues another dated snapshot and
  retires the aliased name, digests break silently for every show at once.
  Recommendation: add an integration smoke test that calls the configured
  model with 10 tokens as a pre-flight in `run_show.py`.
- **The reviewer model and the cross-show synthesiser are hard-coded**,
  bypassing `_defaults.yaml`. If the primary model is rolled forward, these
  two stay on the old id until someone remembers to touch the Python.

---

## 4. Effectiveness

**Temperature tuning is sensible.** 0.5 for digests (facts-heavy) and
0.7–0.75 for podcast narration (voice/flow) matches normal practice. The
Russian shows and the Beginners show correctly drop to 0.4 on digest,
where faithfulness to source matters more than variety. The reviewer sits
at 0.3, which is correct for evaluation.

**Token budgets look healthy.** 3500–5000 on digest and 6000–8000 on
podcast leave headroom for the 1500-word minimum podcast requirement
(`podcast_min_words`). Truncation is monitored via `finish_reason`.

**Chain mode (`podcast_chain: true`)** is enabled for the four long-form
shows (Tesla, FF, Planetterrian, Modern Investing). The two-stage
digest→podcast chain is the correct shape for narrative output; skipping
it on Omni View / Env Intel / M&A / the Russian shows is a valid
trade-off given their tighter structure.

**Gaps**

- `grok-4.20-non-reasoning` is picked even for **Modern Investing** and
  **Tesla Shorts Time**, both of which touch live market data and
  benefit most from step-by-step analysis. The reasoning variant
  (`grok-4.20-reasoning`, same price per `engine/tracking.py:28`) would
  likely improve factual grounding at zero marginal cost. Worth A/B-ing.
- The **cross-show synthesiser** runs at `temperature=0.5` and
  `max_tokens=4000` (`engine/synthesizer.py:411`). For a synthesis task
  across weekly/monthly episode corpora, 4000 output tokens is tight and
  0.5 may still be slightly high for a fact-summary role.
- The **reviewer** (`grok-4-1-fast-non-reasoning`) at `max_tokens=500`
  and `temperature=0.3` is fine for scoring but too thin to produce
  actionable critique. Its output feeds `review_episodes.py` summary
  strings only — no regression loop back into generation.

---

## 5. Suitability per use case

| Use case | Current choice | Verdict |
|----------|----------------|---------|
| Daily digest (news summarisation) | `grok-4.20-non-reasoning` @ 0.5 | Suitable |
| Podcast script (narrative, ~1500+ words) | `grok-4.20-non-reasoning` @ 0.7 (+ chain for long shows) | Suitable; consider reasoning variant for Tesla/MIT |
| Russian-language generation (FP, PR) | Same model, temp 0.4–0.75 | Suitable; no Russian-specific tuning exists, but Grok 4.x is multilingual — verify with `review_episodes.py` coverage on FP/PR |
| Cross-show synthesis (weekly/monthly) | `grok-4.20-non-reasoning` @ 0.5, 4000 tok | Under-resourced; larger context / reasoning variant preferable |
| Tool-use (web / X search) | `grok-4.20-multi-agent` | Suitable — the multi-agent variant is the intended tool-use path |
| Episode quality review | `grok-4-1-fast-non-reasoning` @ 0.3, 500 tok | Suitable for score; too thin for critique |
| Refusal fallback | `grok-4` | **Questionable** — most expensive model in the stack, same family as the refuser; a different *vendor* would be a truer fallback |

---

## 6. Cost effectiveness

Per `engine/tracking.py:22-39` (USD per 1M tokens, input / output):

| Model | In | Out | Role |
|-------|----|----|------|
| `grok-4.20-non-reasoning` | $2.00 | $6.00 | Primary (all shows) |
| `grok-4.20-reasoning` | $2.00 | $6.00 | **Same price, unused** |
| `grok-4.20-multi-agent` | $2.00 | $6.00 | Tool-use |
| `grok-4` | $3.00 | $15.00 | Refusal fallback |
| `grok-4-1-fast-non-reasoning` | $0.20 | $0.50 | Reviewer |
| `grok-3-mini` | $0.30 | $0.50 | Unused |

**Rough per-episode cost** (primary model, podcast chain on,
~4k input + 6k output tokens for digest + podcast combined):

```
(4,000 × $2.00 + 6,000 × $6.00) / 1,000,000 = $0.044 / episode
```

Across ~9 shows/day (modern_investing weekdays, others daily or alt-day)
this is roughly **$0.30–0.40/day, ~$10/month** for LLM spend — trivial
relative to ElevenLabs TTS (at $0.15/1K chars, ~$0.75 per 5k-char script
= **$6–7/day, ~$200/month**).

**Implication:** LLM cost is ~5% of content-generation spend. Optimising
the LLM for *quality* is a bigger lever than optimising for cost.
Downgrading to `grok-4-1-fast-*` for primary generation would save ~$8/mo
but risks the exact failure modes (repetition loops, weak narrative) the
April 2026 pipeline audit was commissioned to fix.

**The one real cost pocket:** the `grok-4` refusal fallback. It's 2.5×
the output price of the primary. Fortunately it only fires on refusal
retries, but each invocation costs ~2.5× a normal episode. Worth
tracking how often it fires in `tracking.py` output.

---

## 7. Recommendations

Ranked by expected impact ÷ effort.

### High impact, low effort

1. **Pipe the reviewer and synthesiser through `config.llm`**, not
   hard-coded strings. Touch points: `engine/synthesizer.py:411`,
   `review_episodes.py:1151`. Add optional `llm.reviewer_model` and
   `llm.synth_model` keys in `_defaults.yaml` so the network can roll
   them forward together. Closes the drift risk called out in §3.
2. **Add a pre-flight model ping** in `run_show.py:_validate_environment()`
   — a 10-token completion against `config.llm.model`. Catches
   model-id deprecations before the expensive stages run. Same pattern
   the TTS path already uses via `validate_elevenlabs_auth`.
3. **Prune dead entries from `GROK_PRICING`** — the `-0309-` dated
   variants, `grok-2`, `grok-3`, `grok-3-mini`. Keeping unused ids
   invites an operator to set `llm.model: grok-3-mini` and silently
   downgrade a show. If any old episode reports still reference them,
   gate pruning on a `data/` scan.

### Medium impact

4. **A/B the reasoning variant on Tesla Shorts Time and Modern
   Investing.** Same $2/$6 price. Run a 2-week parallel test using
   `--test` mode, score via the existing reviewer (`review_episodes.py`
   `ai_review_episode`), compare quality_score distributions. If
   reasoning wins, flip those two shows' `llm.model` override. These
   are the shows most exposed to factual error.
5. **Re-evaluate the refusal fallback.** `grok-4` is expensive and
   shares the refusal heuristics of its xAI siblings. Two options:
   (a) demote to `grok-4.20-reasoning` (same family, same price as
   primary, often more permissive under structured prompting), or
   (b) introduce a cross-vendor fallback (Anthropic Claude Haiku or
   OpenAI GPT-4o-mini) guarded by a new `ANTHROPIC_API_KEY` /
   `OPENAI_API_KEY`. Option (b) also addresses the single-vendor risk
   in §3 — worth the added env-var surface if xAI outages are a real
   concern.
6. **Widen the synthesiser's token budget** to 8000 and flip to the
   reasoning variant. Cross-show synthesis is the one LLM task where
   the reasoning model's step-by-step cohesion pays off most; the cost
   delta is zero.

### Low impact / optional

7. **Expand the reviewer's `max_tokens` to ~1500** so it can produce
   actionable critique, and feed severe findings (quality_score ≤ 5)
   back into a regeneration trigger. Cost is negligible at
   `grok-4-1-fast` pricing ($0.50/M output).
8. **Verify Russian-language quality on FP and PR.** The reviewer runs
   an English-focused prompt at `review_episodes.py:1083+`. Add a
   Russian-specific rubric or route FP/PR reviews through the reasoning
   variant, which historically handles non-English morphology better.
9. **Add a tracking metric for refusal-fallback firings** so operators
   know when `grok-4` usage spikes — both a cost signal and a prompt-
   regression signal.

### Not recommended

- **Downgrading the primary to `grok-4-1-fast-*`**. Savings ~$8/mo
  against a TTS bill ~25× that size, with real risk of re-introducing
  the repetition loops documented in `docs/pipeline_audit_april2026.md`.
- **Adding OpenAI/Anthropic as primary** for any show. No evidence that
  a cross-vendor swap improves quality enough to justify doubling the
  integration surface. Keep them on the bench as fallback only.

---

## 8. One-line verdict

The model selection is **sound, cheap, and well-instrumented** — the
bigger wins are (a) making the reviewer and synthesiser
config-driven, (b) A/B-ing the reasoning variant on the two
market-sensitive shows, and (c) choosing a cheaper or cross-vendor
refusal fallback than `grok-4`.
