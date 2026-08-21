Astronomy fetch-filter is clean (0 leakage) and chapters still parse, but 8/10 scripts remain under the 1600-word floor, the show still ships as a general-science firehose (archaeology/physics/policy crowding out longevity), and several episodes collapse the whole mid-body under one Science Deep Dive chapter.

_Generated on **grok-4.5** by `scripts/run_show_review.py` (replaces the Claude-Opus review agent). Estimated cost: **$0.1194**._

## Scored prior predictions
| Prediction | Verdict | Evidence |
|---|---|---|
| episodes under 1600-word floor, last 10 | hit | 8/10 ep147–156 under 1600 (only ep150=1681, ep155=1857 clear the floor) — matches expected 8+/10 with digest ceiling unchanged |
| unique boilerplate phrases recurring in 10/10 transcripts | hit | still 10/10 on AI-voice disclosure + YouTube/network CTA blocks; no prompt change shipped since prior review |
| fetch-filter leakage matches in last 10 digests | hit | snapshot fetch-filter section: 0 hits vs 21 exclude_title_patterns (was 6) |
| pure-astronomy items per PT episode digest | hit | 0 exclude-pattern leakage in last 10 digests; astronomy filter holding |
| article volume vs min_articles_skip (2) after the filter | hit | ep147–156 all produced; no filter-induced skip days visible in snapshot window |
| median _tts.txt words, last 10 eps | miss | still chronically short — 8/10 below 1600; median remains well under 1600 floor |

## ⚠️ A/B-listen required — NOT applied (landmine #17)
These prompt/audio changes are **proposals only**. Apply them yourself, render/listen, then merge if they sound right.

**`shows/prompts/planetterrian_digest.txt`** (prompt) — July-2 astronomy filter hit (0 leakage) but transcripts ep147–156 still ship archaeology, materials, lasers, maritime policy, music psychology — the longevity/health brand promise in shows/planetterrian.yaml description is not enforced at selection time.
```diff
- ### CONTENT-TYPE CAPS — DE-EMPHASIZE DRUG AND PHARMA-INDUSTRY NEWS
- This show covers broader science, longevity, and health — NOT a pharma trade newsletter. Enforce these caps on the Top 15:
- - **Drug-development items**: MAXIMUM 4 of 15.
+ ### CONTENT-TYPE CAPS — DE-EMPHASIZE DRUG AND PHARMA-INDUSTRY NEWS
+ This show covers broader science, longevity, and health — NOT a pharma trade newsletter and NOT a general-science firehose. Enforce these caps on the Top 15:
+ 
+ ### LIFE-SCIENCE MAJORITY FLOOR (hard)
+ - **Core life-science / longevity / health items: MINIMUM 8 of 15.** Count as core: neuroscience, microbiome, cellular/mitochondrial aging, senescence, sleep/circadian, nutrition science, exercise physiology, genetics/genomics with a health or aging reading, regenerative/stem-cell biology, clinical results, public/environmental health, diagnostics/biomarkers, and basic cell/molecular biology tied to human or model-organism healthspan.
+ - **Out-of-scope unless they have an explicit human-health or aging mechanism in the source** (prefer drop): pure archaeology/paleontology without biomedical method transfer; condensed-matter / materials / laser / semiconductor work without a bio or medical device readout; generic historiography; musicology/media studies; maritime or administrative policy with no health exposure pathway; space/astronomy (already fetch-filtered — do not re-import via web search).
+ - Before finalizing the list, count core life-science items. If under 8, drop the weakest out-of-scope items and pull primary-research health/longevity pieces you initially skipped — even if incremental.
+ 
+ - **Drug-development items**: MAXIMUM 4 of 15.
```

**`shows/prompts/planetterrian_podcast.txt`** (prompt) — Whisper transcripts ep147–156 show the same handoff line dominating; de-seed by ban + shape, not a new quotable example list (meta-review successor-tic rule).
```diff
- - Use natural transitions between stories ("Now, shifting to..." or "On a different note..." or simply "Next up...")
- - NEVER retell or revisit a story you already covered, even from a different angle. Each news item gets ONE treatment. Once you have covered a story, it is done — move on to the next topic.
- - Do NOT repeat transition sentences. When you write a transition at the end of one story, start the next story with NEW content — do not repeat the transition line.
+ - Use natural transitions between stories. Vary handoff **shape** every time (topic bridge, contrast, scale shift, or a plain "Next."). 
+ - VERBATIM BAN (do not write these strings again — they became every-episode tics): "shifting to a very different area of research", "Now, shifting to a very different area", "On a different note". Prefer unnamed bridges that name the *next* subject in the first clause.
+ - Do not elect the first example in any menu as the default tic; rotate shapes across the episode.
+ - NEVER retell or revisit a story you already covered, even from a different angle. Each news item gets ONE treatment. Once you have covered a story, it is done — move on to the next topic.
+ - Do NOT repeat transition sentences. When you write a transition at the end of one story, start the next story with NEW content — do not repeat the transition line.
```

**`shows/prompts/planetterrian_podcast.txt`** (prompt) — Snapshot: “keep an eye on” in 8/10 episodes — prompt-seeded convergence. Chapter YAML already accepts Before we go|Next time|before we wrap|keep an eye on|watch for, so rotation stays parseable.
```diff
- [Tomorrow Teaser — one sentence before the closing]
- Patrick: Before we go — briefly tease something listeners should watch for in the next episode based on developing stories from today's news. Keep it specific and forward-looking: "Next time, we'll be watching for..." or "Keep an eye on..." This builds habitual listening.
+ [Tomorrow Teaser — one sentence before the closing]
+ Patrick: Before we go — one specific, forward-looking beat from today's developing threads. Rotate opener **shape** (do not lock onto a single catchphrase): e.g. start with the subject, or "Before we wrap…", or "Next time…", or "Watch for…". VERBATIM soft-cap: "Keep an eye on" at most once per three episodes in your own habit — prefer naming the trial, paper, or readout directly. Still one sentence. This builds habitual listening.
```

**`shows/planetterrian.yaml`** (config) — Ep147 dairy segment used “most people have heard that…” and got no Dive chapter; aligns marker with prompt-seeded myth-bust openers without phonetic hacks. A/B-listen: changes player chapter boundaries.
```diff
-     - pattern: "science deep dive|deep dive|under the microscope|something most people get wrong|most people (picture|assume|think|believe|get wrong)"
-       title: "Science Deep Dive"
+     - pattern: "science deep dive|deep dive|under the microscope|something most people get wrong|most people (picture|assume|think|believe|get wrong|have heard)|you.?ve probably heard that"
+       title: "Science Deep Dive"
```

## Code/metadata-only proposals (no A/B needed)
- **`shows/planetterrian.yaml`** (config): Sanctioned length attack is digest-side only; 1400 has not lifted scripts past the 1600 floor on 8/10 recent episodes. No podcast expand/retry.

## Deferred (carried forward)
- Operator decision on chronic under-length after repeated misses with digest_expand already on: full-text journal fetch vs higher digest floors only vs lower min_podcast_words vs accept short days — do not re-propose podcast_expand_below_target or podcast word-pressure
- Engine-level split so content after Science Deep Dive can re-enter story auto-segments (body-swallow on ep148/149/152/153/156) — shared chapter architecture, not PT prompt padding
- Garbage mid-body LLM auto-segment titles — shared Tesla/M&A-deferred class
- Network pronunciation of Nerra / Planetterrian (Whisper: Narra/Narrow/Planetarian) — no phonetic respelling (landmine #17)

## Drift-guard status
```
============================= test session starts ==============================
collected 12 items

tests/test_planetterrian_quality_pass.py ............                    [100%]

============================== 12 passed in 0.80s ==============================
```

<sub>tokens: 45427 in / 4763 out</sub>