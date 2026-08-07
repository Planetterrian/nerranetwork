FP still ships chronic under-length (9/10 eps below 1000w), live boilerplate tics the July-2 pass only deferred, and residual spoken source-scaffold («Источник информации…») plus off-topic Коротко beats—attack digest-side length and scrub/de-seed, not podcast expand.

_Generated on **grok-4.5** by `scripts/run_show_review.py` (replaces the Claude-Opus review agent). Estimated cost: **$0.1010**._

## Scored prior predictions
| Prediction | Verdict | Evidence |
|---|---|---|
| spoken source-scaffold lines («Сорс …» / «Source …») in _tts.txt | miss | Russian shapes still ship: ep71/75/76 «Источник информации…» / «Источник Медузы» / bare BNN Bloomberg attributions in Коротко |

## ⚠️ A/B-listen required — NOT applied (landmine #17)
These prompt/audio changes are **proposals only**. Apply them yourself, render/listen, then merge if they sound right.

**`shows/finansy_prosto.yaml`** (config) — Length miss ×2 at podcast/digest-depth prompts; network policy forbids another podcast-side lever. Digest is the ceiling; env_intel already moved this way. Audio length/content will change → operator A/B-listen net episodes.
```diff
- llm:
-   min_podcast_words: 1000
-   podcast_expand_below_target: true
-   # no min_digest_words
+ llm:
+   min_podcast_words: 1000
+   min_digest_words: 950
+   digest_expand_below_target: true   # same digest-side lever as env_intel
+   podcast_expand_below_target: false  # leave last podcast-expand holdout
```

**`shows/prompts/fp_podcast.txt`** (prompt) — July-2 deferred de-seed never applied; snapshot still shows 7–9/10 recurrence. Shape ban + memory per playbook anti-seed rule.
```diff
- Implicit/allowed stock transitions heard every episode: «А теперь моя любимая часть выпуска. Давайте разберёмся, как это работает под капотом.»; deep-dive often opens «Подруга спросила меня вчера…»; closes «И вот так работает … не так уж и сложно, правда?»
+ DE-SEED BY SHAPE (do not replace with one new catchphrase):
+ - Never open the deep-dive with «моя любимая часть», «под капотом», or a «подруга спросила» anecdote.
+ - Never close a mechanism with «не так уж и сложно (правда)?» / «не магия, а…».
+ - Rotate cold, concrete bridges (one sentence stating the mechanism name + who it helps in Vancouver/Lower Mainland).
+ - MEMORY: do-not-reuse the last 5 episodes' deep-dive first and last sentences (runtime list if available; else prompt-stated ban on the shapes above).
+ Do NOT give a quotable example opener the model can elect as the next tic.
```

**`shows/prompts/fp_podcast.txt`** (prompt) — Stops runtime theft and niche dilution verified in ep68/69/74/76.
```diff
- Коротко и ясно accepts general Canada/business wires (Meta, chips, foreign storms) with weak or missing household-money link.
+ Коротко и ясно: 2–3 items max, each ≤3 sentences. Every item must open with a household-finance consequence for women/families in Canada (rates, TFSA/RRSP/FHSA/RESP, mortgage/rent, benefits, pay/jobs, insurance, scams, taxes). Drop pure tech/corp/geopolitics/natural-disaster wires unless sentence 1 states the money link. No source URLs or «источник информации» tails (scrub is backup).
```

**`shows/prompts/fp_podcast.txt`** (prompt) — July-2 deferred item; still wastes the longest segment on duplicate teaching.
```diff
- Deep-dive may re-explain the same instrument/headline as Главная тема (e.g. ep76 renewal twice).
+ Deep-dive («как это работает») MUST be a different mechanism or adjacent rule from Главная тема. If main = mortgage renewal timing, deep-dive ≠ renewal steps again — pick prepayment, stress test, HELOC vs refinance, etc. If main already defined TFSA, deep-dive ≠ TFSA 101.
```

**`shows/prompts/fp_digest.txt`** (prompt) — Digest is the substrate; without digest floor the podcast cannot honestly hit 1000w. Complements yaml lever; A/B because spoken length/content changes.
```diff
- Digest depth raised June-16 to 3–4 tips / 3 quick-news / 5–7 articles but shipped length still ~digest-sized ~700–850w podcast.
+ Keep tip/article floors. Add explicit substance floors tied to min_digest_words: each practical tip needs a named Canadian account/institution + a 5–10 minute action; each quick-news item needs the household hook in sentence 1; reject padding by synonym restatement. Align with config min_digest_words 950 so expand-retry has real gaps to fill (facts/steps), not paraphrase.
```

## Code/metadata-only proposals (no A/B needed)
- **`engine/generator.py (or run_show script-save scrub path used July-2)`** (code): July-2 prediction missed: FP still speaks source scaffold in Russian. Deterministic, high-yield garble/fetch class; no A/B.
- **`shows/finansy_prosto.yaml`** (config): ep77 used «коротко о других новостях» and «практическим шагам» and lost two chapters; metadata-only fix.
- **`tests/test_finansy_prosto_quality_pass.py`** (code): Every behavioral fix needs a drift-guard per playbook.

## Deferred (carried forward)
- Operator: resolve cadence contradiction (YAML «ежедневный» vs CLAUDE.md Monday vs historical even-days cron; actual July run was near-daily).
- Operator: YOUTUBE_REFRESH_TOKEN_RU so RU YouTube uploads are real.
- Operator A/B: fully localized AI-disclosure wording on Olya (still garble-prone «с помощью и синтеза голоса»).
- If digest-side lever misses length again after a full post-merge window: operator product decision (accept ~5–6 min vs restructure segments)—do not re-propose podcast expand/word-floor.
- Optional later: stabilize YouTube CTA spoken brand as pure Cyrillic «Нерра РУ» if handle garble persists after source scrub (A/B; no phonetic respelling).
- Closing-pool disclaimer already on 8/10; only chase the short closer path (ep69/76) if it drops the advisor line after other prompt edits.

## Drift-guard status
```
============================= test session starts ==============================
collected 14 items

tests/test_finansy_prosto_quality_pass.py ..............                 [100%]

============================== 14 passed in 0.18s ==============================
```

<sub>tokens: 34192 in / 5438 out</sub>