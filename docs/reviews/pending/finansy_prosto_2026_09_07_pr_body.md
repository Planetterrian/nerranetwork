FP still ships chronic under-length (10/10 below 1000w), live Russian source-scaffold and section-chapter collapses the Aug-6 proposals never fixed, plus unchanged boilerplate tics and off-niche Коротко—re-propose digest-side length + scrub/chapter/de-seed only; escalate length to operator if digest lever is declined again.

_Generated on **grok-4.5** by `scripts/run_show_review.py` (replaces the Claude-Opus review agent). Estimated cost: **$0.1074**._

## Scored prior predictions
| Prediction | Verdict | Evidence |
|---|---|---|
| spoken Russian/English source-scaffold lines in FP _tts.txt (Источник информации / Информация размещена на / Source / Сорс) | miss | Scrub never shipped; ep75 «Источник информации BNN…» ×3, ep76 «Источник Медузы», ep73/79/82 «Информация размещена/доступна на …» still on air |
| median FP _tts.txt words, last ~5 episodes after digest-side lever | miss | Lever never merged; ep78–82 words 732/768/634/741/938, median ~741w, 10/10 still under 1000w |
| podcast_expand_below_target firings / cost spikes on FP | miss | YAML still podcast_expand_below_target true; avg $0.249/ep, ep82 $0.447 expand-burn signature |
| episodes using «а теперь моя любимая часть» OR «Подруга спросила меня вчера» OR «не так уж и сложно, правда?» shapes | miss | De-seed never applied; ep73 all three shapes; ep74–76 keep любимая часть ± подруга/не так уж |
| Коротко и ясно items with no household-finance hook (pure tech/corp/geopolitics) | miss | ep74 bosses RTO + Meta–Anthropic; ep75 Chinese AI freeze; ep76 Rostov storm + Japan delegation still shipped |
| ep chapters including both Практические советы and Коротко when those segments exist in transcript | miss | chapters_ep077/079/081.json still 3-chapter collapses; ep80/82 body-text titles; YAML patterns never broadened |
| spoken source-scaffold lines («Сорс …» / «Source …») in _tts.txt | miss | July-2 Latin scrub held but Russian equivalents replaced it; still open as Aug-6 miss |

## ⚠️ A/B-listen required — NOT applied (landmine #17)
These prompt/audio changes are **proposals only**. Apply them yourself, render/listen, then merge if they sound right.

**`shows/finansy_prosto.yaml`** (config) — Length miss ×2 at podcast/digest-depth prompts; network policy = digest-substrate only. FP last podcast-expand holdout. Flipping expand off stops $0.25–0.45 burn; digest floor is the real ceiling. Net audio longer/richer → operator A/B-listen. If declined or misses after full window: operator product decision, do not re-file.
```diff
-   min_podcast_words: 1000
-   podcast_expand_below_target: true
+   min_podcast_words: 1000
+   min_digest_words: 950
+   digest_expand_below_target: true
+   podcast_expand_below_target: false
```

**`shows/prompts/fp_podcast.txt`** (prompt) — July-2/Aug-6 deferred de-seed + relevance + non-repeat never applied; ep73–76 still tic; ep74–76 off-niche Коротко; ep76/80 deep-dive re-teaches. Shape ban + memory per playbook.
```diff
- (any rotation examples or allowed stock phrases that seed «а теперь моя любимая часть», «Подруга спросила меня вчера», «не так уж и сложно, правда?», «под капотом» as preferred openers/closers — remove quotable examples)
+ Add a SHAPE ban + MEMORY block (no replacement one-liners):\n- Deep-dive opener: do NOT use shapes «моя любимая часть», «подруга спросила…», «под капотом». Rotate cold mechanism setups; ban list = last 6 episode deep-dive first sentences (injected).\n- Deep-dive closer: do NOT use «не так уж и сложно» / «правда?» tag questions.\n- Do not paste a cute exemplar phrase in the prompt (anti-seed).\n- Deep-dive must teach a mechanism or adjacent instrument NOT already covered in Главная тема (main = renewal timing → dive = prepayment/stress test, not renewal again).\n- Коротко и ясно: only items with a direct household-money hook stated in sentence one (rates, tax accounts, housing, benefits, jobs/pay, insurance, scams for newcomers); 2–3 sentences each; drop pure tech/corp/geopolitics.
```

**`shows/prompts/fp_digest.txt`** (prompt) — Podcast cannot hit 1000w from a ~700w digest; June depth steer alone missed. Digest is the lever; A/B because spoken length/content change.
```diff
- (digest formatting targets that still allow thin 2-topic / short Коротко days without a hard substrate floor)
+ Align digest substrate with podcast honesty: enforce 3–4 practical tips, ≥3 Коротко items each with explicit household-finance hook in the first sentence, 5–7 article-backed beats on normal news days; state that a normal day must not collapse to two topics. No padding instructions that invent facts — depth from real sources only. Complements yaml min_digest_words.
```

## Code/metadata-only proposals (no A/B needed)
- **`engine/generator.py`** (code): Aug-6 miss: Latin scrub left Russian scaffold on air (ep75/76/73/79/82). Deterministic high-yield garble class; no A/B.
- **`shows/finansy_prosto.yaml`** (config): ep77/79/81 collapse and ep78/80/82 mis-markers: body uses «коротко о других новостях», «практическим шагам», «практической стороне» which current regex misses. Metadata-only.
- **`tests/test_finansy_prosto_quality_pass.py`** (code): Every behavioral fix needs a drift-guard per playbook.

## Deferred (carried forward)
- Operator: resolve cadence contradiction (YAML «ежедневный» vs CLAUDE.md Monday vs historical even-days; actual ep73–82 roughly weekly).
- Operator: YOUTUBE_REFRESH_TOKEN_RU so RU YouTube uploads are real.
- Operator A/B: fully localized AI-disclosure wording on Olya (still garble-prone «с помощью и синтеза голоса» / ИИ drop).
- If digest-side lever is declined again OR misses length after a full post-merge window: operator product decision (accept ~5–6 min vs restructure segments) — do not re-propose podcast expand/word-floor.
- Optional later: stabilize YouTube CTA spoken brand as pure Cyrillic «Нерра РУ» if handle garble persists after source scrub (A/B; no phonetic respelling).
- Optional: first-use Russian expansion of RRSP/TFSA/FHSA then Russian short name (A/B; no letter-salad Latin).
- Closing-pool disclaimer already on most eps; only chase short closer path (ep76/78/80-style) if advisor line drops after other prompt edits.

## Drift-guard status
```
============================= test session starts ==============================
collected 14 items

tests/test_finansy_prosto_quality_pass.py ..............                 [100%]

============================== 14 passed in 0.19s ==============================
```

<sub>tokens: 37375 in / 5436 out</sub>