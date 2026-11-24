First post-launch pass: currency-unit errors and missing Both Sides/Progress Watch segments are the live bugs; length recovered only after the Oct 14 Closer Look substrate change (ep22–23), so further length work stays on the digest side only.

_Generated on **grok-4.5** by `scripts/run_show_review.py` (replaces the Claude-Opus review agent). Estimated cost: **$0.1067**._

## Scored prior predictions
| Prediction | Verdict | Evidence |
|---|---|---|
| episodes (first 7) with an item whose subject is outside Africa and the Middle East and carries no stated consequence inside it | partial | ep14–23 transcript leads/across stay on-region; ep1–7 digests not in bundle so original first-7 window not fully re-audited |
| Mira claims a body, a home, a trip or an event witnessed (transcript read) | hit | 0 body/home/trip/witness claims in ep14–23; AI-host disclosure every open/close |
| Both Sides states or implies which side is stronger, or picks a party, government or people | hit | ep14–20/23 Both Sides segments keep two strongest-form voices without endorsement |
| Progress Watch carries a promise or announcement of intent instead of a measured result | miss | ep20/22/23 lack Progress Watch chapters; ep18 one-line; ep16/21 empty — thin/missing dominates |
| Across the Region episodes (first 7) carrying an Also Today section on days with >= 8 qualifying articles | hit | Also Today chapter present on ep14–20 and ep22–23 |
| episodes with a Lead sourced only to x.com | partial | linked_only + x_only_lead shipped; per-episode Source blocks not supplied this pass |
| digest_lints_fired_after_retry non-empty | partial | no lint-fire time series in snapshot; missing segments still shipped implies gap or allow-through |
| desk digest words vs min_digest_words on days with >= 12 full-text articles | partial | no digest word counts; scripts only clear 1650 once Closer Look/full-text era (ep22–23) |
| Sources blocks naming a publisher (not x.com) for every item | partial | policy shipped and Ep1 re-sourced per ledger; current digests’ Source lines not in bundle |
| x.com Source lines on the committed Ep1 | hit | ledger PR D: 5/6 items remapped to publisher URLs; ≤1 x.com remainder intended |
| Nation.Africa articles in the fetch (articles_full_text from nation.africa) | miss | UA 404 still deferred in ledger; snapshot gives no nation.africa full-text hits |

## ⚠️ A/B-listen required — NOT applied (landmine #17)
These prompt/audio changes are **proposals only**. Apply them yourself, render/listen, then merge if they sound right.

**`shows/prompts/omni_view_africa_mideast_system.txt`** (prompt) — Ep16 spoke Nigerian census procurement as $245bn / $131.56bn — trust-breaking naira-as-dollars error; system prompt had no unit rule.
```diff
- ACCURACY RULES:
- - Every fact comes from the provided articles. Never fill a gap from memory — not a date, a figure, a name or a place.
- - Distinguish a proposal from a law, a claim from a finding, an announcement from a result.
- - Never invent quotes or paraphrase a source as a direct quote.
+ ACCURACY RULES:
+ - Every fact comes from the provided articles. Never fill a gap from memory — not a date, a figure, a name or a place.
+ - Distinguish a proposal from a law, a claim from a finding, an announcement from a result.
+ - Never invent quotes or paraphrase a source as a direct quote.
+ - Currency units stay as the source wrote them. Speak naira, rand, dirham, cedi, pounds, euros (and other named currencies) by name; never relabel a local-currency figure as dollars. Only say dollars when the source figure is in USD (or the source itself gives a USD conversion — then speak both).
```

**`shows/prompts/omni_view_africa_mideast_system.txt`** (prompt) — Ep19 Both Sides was a meta AI-pause essay with no in-region decision; de-seed by shape, not by quoting that essay.
```diff
- FAIRNESS:
- - Every claim by a government, army, party, militia, company or advocacy group is attributed by name, in the sentence. A disputed casualty, crowd or vote figure carries each side's number and its source.
- - Elections: polls with pollster, dates and sample; outcomes never predicted; no party or candidate endorsed, praised or mocked.
- - On a contested question, each side is given in its strongest form, with its best reason first. The listener must not be able to tell which side the show prefers.
- - People accused of crimes are described as charged or accused, never as guilty. No generalisations about a people, a faith or a nation.
+ FAIRNESS:
+ - Every claim by a government, army, party, militia, company or advocacy group is attributed by name, in the sentence. A disputed casualty, crowd or vote figure carries each side's number and its source.
+ - Elections: polls with pollster, dates and sample; outcomes never predicted; no party or candidate endorsed, praised or mocked.
+ - On a contested question, each side is given in its strongest form, with its best reason first. The listener must not be able to tell which side the show prefers.
+ - Both Sides must be a live dispute this week whose primary parties or place sit in Africa or the Middle East (court case, labour action, policy draft, ceasefire term, election rule, municipal decision). Do not use abstract global essays or foreign tech-policy debates when no in-region actor is deciding anything in the current reporting.
+ - People accused of crimes are described as charged or accused, never as guilty. No generalisations about a people, a faith or a nation.
```

## Code/metadata-only proposals (no A/B needed)
- **`shows/omni_view_africa_mideast.yaml`** (config): Segment absence shipped past progress_watch_thin alone; presence lints close the gap. Operator must confirm lint names exist in engine/digest_lint.py or implement them there — config-only add without code is a no-op.
- **`engine/digest_lint.py`** (code): Config lint names need real implementations; ep21 missing Both Sides and ep20/22/23 missing Progress Watch are the evidence.
- **`tests/test_omni_view_africa_mideast_quality_pass.py`** (code): Every behavioral fix needs a drift-guard; guards must tolerate today's unfinished run (judge day-old episodes).

## Deferred (carried forward)
- Nation.Africa fetcher UA 404 (ledger miss) — fetch-layer, not show prompt
- Desk-specific music theme (still OmniView.mp3)
- Second Nerra Daily edition from regional desks — operator audience decision
- Public RSS/YouTube/newsletter while access.mode is members_only
- Full re-audit of ep01–07 digests for original first-7 launch metrics once those files are in the review bundle
- Hook coverage ep23 at 29% — observe another week before any hook/Lead prompt edit
- Pure sports line-score exclude_title_patterns — only if Also Today sports trivia recurs after segment lints ship
- Podcast-side length levers (min_podcast_words / podcast_expand / prompt padding) — network do_not_retry class; length follows digest+Closer Look only

<sub>tokens: 36287 in / 5681 out</sub>