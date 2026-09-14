FP still ships 10/10 under-length scripts, live Russian source-scaffold and section-chapter collapses never fixed across two proposal-only passes, plus unchanged boilerplate tics and off-niche Коротко—re-propose scrub/chapters/de-seed/cost-flag only and escalate length to an operator product decision.

_Generated on **grok-4.5** by `scripts/run_show_review.py` (replaces the Claude-Opus review agent). Estimated cost: **$0.1124**._

## Scored prior predictions
| Prediction | Verdict | Evidence |
|---|---|---|
| spoken Russian source-scaffold lines in FP _tts.txt (Источник… / Информация размещена\|доступна\|поступила… / Подробности доступны на / История опубликована на) | miss | Scrub never shipped; ep75/76/79/82/83 still speak Источник/Информация размещена\|поступила/История опубликована and bare outlet hosts in Коротко |
| FP episodes whose chapters omit Практические советы or Коротко when those segments exist in transcript | miss | ep77/79/81 still 3-chapter collapses; ep78 drops practical; ep80/82 body-sentence titles; YAML patterns never broadened |
| median FP _tts.txt words, last ~5 episodes after digest-side lever merges | miss | Lever never merged; ep79–83 = 768/634/741/938/663, median ~741w; 10/10 under 1000w |
| podcast_expand_below_target true and expand-retry cost spikes on FP | miss | YAML still podcast_expand_below_target: true; avg $0.259/ep, ep82 $0.447 expand-burn signature |
| episodes using «а теперь моя любимая часть» OR «Подруга спросила меня вчера» OR «не так уж и сложно, правда?» shapes | miss | De-seed never applied; ep74 cluster all three; ep75 любимая + не так уж и сложно; ep76 любимая часть |
| Коротко и ясно items with no household-finance hook in sentence one | miss | ep74 RTO bosses + Meta–Anthropic; ep75 Chinese AI freeze; ep76 Rostov storm + Japan delegation; ep83 ferry-to-China + summit deals |
| successor deep-dive/transition tic after de-seed (rhetorical Q or «по полочкам»/equivalent cute closer) | partial | Prior cluster still live; soft successors recurring — bank-counter «Представьте, что вы стоите в банке» (ep76/78/79/80/83) and «по шагам» (ep79) |

## ⚠️ A/B-listen required — NOT applied (landmine #17)
These prompt/audio changes are **proposals only**. Apply them yourself, render/listen, then merge if they sound right.

**`shows/prompts/fp_podcast.txt`** (prompt) — July-2/Aug-6/Sep-7 deferred de-seed never applied; ep74–76 still tic; playbook anti-seed rule = shape ban + memory, never a quotable example.
```diff
- Implicit allowed transitions that the model has calcified: «а теперь моя любимая часть (выпуска)», «Подруга спросила меня вчера…», «не так уж и сложно, правда?», «давайте разберёмся… под капотом» as default deep-dive openers/closers (and any single quotable replacement example).
+ DE-SEED BY SHAPE + MEMORY (no example phrases): ban the shapes (a) cute possession-of-segment openers («любимая часть» class), (b) friend-asked-me-yesterday anecdote openers, (c) «не так уж и сложно»/rhetorical-ease closers, (d) default «под капотом» crutch if overused. Inject last-N episode deep-dive openers/closers as do-not-reuse MEMORY. Require a fresh mechanism image each episode without a prompt-quoted exemplar. Predict successor tics (bank-counter / по шагам) for next review.
```

**`shows/prompts/fp_podcast.txt`** (prompt) — Stops niche dilution verified in ep74/75/76/83 and runtime theft from deep-dive re-teach (ep76/80). A/B because spoken content changes.
```diff
- Коротко и ясно accepts general news beats; deep-dive may re-explain the episode main topic/mechanism.
+ Коротко и ясно: only items with a direct household-money hook stated in sentence one (rates, tax accounts, housing, benefits, jobs/pay, insurance, scams targeting newcomers, BC/Vancouver cost of living); 2–3 sentences each; drop pure tech/corp/geopolitics/weather unless the money link is explicit in sentence one. Deep-dive: adjacent mechanism or instrument NOT already covered in Главная тема (e.g. main = renewal timing → deep-dive = prepayment privileges/stress test — not «how renewal works» again).
```

## Code/metadata-only proposals (no A/B needed)
- **`engine/generator.py`** (code): Sep-7/Aug-6 miss: Latin scrub left Russian scaffold on air (ep75/76/79/82/83). Deterministic high-yield garble/fetch class; no A/B.
- **`shows/finansy_prosto.yaml`** (config): ep77/79/81 collapse and ep78/80/82/83 mis-markers: body uses «коротко о других новостях», «практическим шагам», «практической стороне» which current regex misses. Metadata-only.
- **`shows/finansy_prosto.yaml`** (config): Cost-only fix: FP is last podcast-expand holdout burning $0.25–0.45/ep without clearing 1000w. Network policy forbids podcast-side length levers; flipping the flag stops expand-burn. NOT a length claim — length escalated to operator digest-floor decision.
- **`tests/test_finansy_prosto_quality_pass.py`** (code): Every behavioral fix needs a drift-guard per playbook.

## Deferred (carried forward)
- OPERATOR PRODUCT DECISION on length (escalated — identical digest-side lever proposed Aug-6 and Sep-7, never merged; June-16 digest-depth miss; 10/10 still <1000w): (A) ship min_digest_words ~950 + digest expand-below-target and keep podcast_expand false, or (B) accept ~5–6 min product and lower honest floor/metadata, or (C) restructure segments. Do not re-file podcast word-floor/expand/«пиши длиннее».

## Drift-guard status
```
============================= test session starts ==============================
collected 14 items

tests/test_finansy_prosto_quality_pass.py ..............                 [100%]

============================== 14 passed in 0.18s ==============================
```

<sub>tokens: 39530 in / 5550 out</sub>