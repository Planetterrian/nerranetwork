9/10 scripts still under the 1600-word floor, astronomy filter leakage returned (3 hits in ep160), brand scope still general-science firehose, and Science Deep Dive body-swallow is worse (6/10); prior August proposals never shipped so life-science floor and transition de-seed remain open.

_Generated on **grok-4.5** by `scripts/run_show_review.py` (replaces the Claude-Opus review agent). Estimated cost: **$0.1263**._

## Scored prior predictions
| Prediction | Verdict | Evidence |
|---|---|---|
| life-science / longevity / clinical-health items in Top 15 per digest (manual count, last 10) | miss | August scope floor never shipped; ep160–169 still mix archaeology, materials, education policy, climate-tech, dental crowns, lunar ops with longevity items |
| fetch-filter leakage matches in last 10 digests | miss | snapshot: 3 hits in ep160 (black hole, superstorm, solar wind) vs August baseline 0 |
| episodes under 1600-word floor, last 10 | miss | 9/10 under (only ep163=1649 clears); min_digest_words 1700 never shipped — score as lever-not-shipped + digest ceiling |
| transcripts with verbatim transition 'shifting to a very different area of research', last 10 | miss | still in ep160/161/162/163/165/167; podcast EXAMPLE block still seeds the line; de-seed never shipped |
| episodes whose Science Deep Dive chapter spans >50% of runtime (body swallow), last 10 | partial | worse: ep161/163/164/165/166 swallow; ep168 missing Introduction (Dive first); ~6/10 vs prior 5/10 |
| median _tts.txt words, last 10 eps | miss | ep160–169 median ~1260 words; 9/10 below 1600 floor — chronic under-length unchanged |

## ⚠️ A/B-listen required — NOT applied (landmine #17)
These prompt/audio changes are **proposals only**. Apply them yourself, render/listen, then merge if they sound right.

**`shows/prompts/planetterrian_digest.txt`** (prompt) — August-19 scope proposal never applied; transcripts ep160–169 still read as general-science radio. Enforces YAML description brand. A/B-listen: changes story mix and spoken content.
```diff
- ### CONTENT-TYPE CAPS — DE-EMPHASIZE DRUG AND PHARMA-INDUSTRY NEWS
- This show covers broader science, longevity, and health — NOT a pharma trade newsletter. Enforce these caps on the Top 15:
- - **Drug-development items**: MAXIMUM 4 of 15.
+ ### CONTENT-TYPE CAPS — DE-EMPHASIZE DRUG AND PHARMA-INDUSTRY NEWS
+ This show covers broader science, longevity, and health — NOT a pharma trade newsletter. Enforce these caps on the Top 15:
+ - **Life-science majority floor**: AT LEAST 8 of 15 items must be core life-science / longevity / clinical-health on Earth — neuroscience, microbiome, cellular aging, sleep/circadian, nutrition, genetics/genomics of health, regenerative biology, exercise physiology, public-health physiology, diagnostics/biomarkers. Before finalising, count core life-science items; if under 8, drop the weakest out-of-scope items and pull primary-research life-science you initially skipped.
+ - **Out of scope (exclude unless the finding is directly about human/animal health physiology)**: archaeology/anthropology without a health mechanism; pure materials/condensed-matter/photonics; generic education, hospitality, or labor-market policy; pure climate/earth-tech without human physiology; dental lab process; spaceflight ops. Astronomy/space physics remain FF-owned (fetch filter + beat ownership).
+ - **Drug-development items**: MAXIMUM 4 of 15.
```

**`shows/prompts/planetterrian_podcast.txt`** (prompt) — Meta-review: de-seed by shape + verbatim ban, never leave quotable EXAMPLE the model elects. 6+/10 transcripts still speak the EXAMPLE line. Successor-tic prediction logged for 'on a different note'.
```diff
- Patrick: The paper identifies a specific receptor on vagal afferent fibres, F F A R three, as the molecular site of the interaction.
- Patrick: Now, shifting to a very different area of research...
- 
- Do not include any of the following
+ Patrick: The paper identifies a specific receptor on vagal afferent fibres, F F A R three, as the molecular site of the interaction.
+ Patrick: Next, a separate line of work takes us to cellular aging clocks.
+ 
+ TRANSITION RULES (do not read aloud): Never use the verbatim handoff "Now, shifting to a very different area of research" or "shifting to a very different area of research" — banned as a repeated tic. Also avoid leaning on a single fallback like "On a different note" every time. Vary handoffs by SHAPE only: (a) bridge via a shared mechanism or scale, (b) one-clause contrast without the banned string, (c) direct next-finding open with no bridge clause. Do not copy example bridge wording as a template.
+ 
+ Do not include any of the following
```

**`shows/prompts/planetterrian_podcast.txt`** (prompt) — Snapshot: 'keep an eye on' in 9/10 — prompt-seeded convergence. Rotation keeps chapter regex valid (shows/planetterrian.yaml teaser pattern).
```diff
- [Tomorrow Teaser — one sentence before the closing]
- Patrick: Before we go — briefly tease something listeners should watch for in the next episode based on developing stories from today's news. Keep it specific and forward-looking: "Next time, we'll be watching for..." or "Keep an eye on..." This builds habitual listening.
+ [Tomorrow Teaser — one sentence before the closing]
+ Patrick: Before we go — briefly tease something listeners should watch for next, based on developing stories from today's news. Keep it specific and forward-looking. Rotate the opener SHAPE across episodes (do not default to the same lead-in every day): a watch-for clause, a next-time clause, a before-we-wrap clause, or a developing-thread clause. Chapter markers already parse Before we go|Next time|before we wrap|keep an eye on|watch for — stay within that family so chapters still match. Do not invent a new stock sentence used every episode.
```

**`shows/planetterrian.yaml`** (config) — Prior miss class: paraphrase openers ('most people have heard' / dairy ep147-class) skip the Dive chapter. Belt-and-braces only — does NOT fix body-swallow (engine split still deferred). A/B-listen: changes player chapter boundaries.
```diff
- - pattern: "science deep dive|deep dive|under the microscope|something most people get wrong|most people (picture|assume|think|believe|get wrong)"
-       title: "Science Deep Dive"
+ - pattern: "science deep dive|deep dive|under the microscope|something most people get wrong|most people (picture|assume|think|believe|get wrong|have heard)|you've probably heard|you have probably heard"
+       title: "Science Deep Dive"
```

## Code/metadata-only proposals (no A/B needed)
- **`engine/fetcher.py`** (code): P0 regression: August leakage was 0; ep160 shipped FF-beat astronomy on air despite patterns already listed in shows/planetterrian.yaml. Garble/fetch-filter fixes are highest-yield per meta-review.

## Deferred (carried forward)
- Operator decision on chronic under-length after repeated misses with digest_expand already on: (a) full-text journal fetch Nature/Science/bioRxiv, (b) higher min_digest_words + per-item sentence floors only, (c) lower min_podcast_words to honest ceiling, (d) accept short days — do NOT re-propose podcast_expand_below_target or podcast word-pressure
- Engine-level split so content after Science Deep Dive re-enters story auto-segments (body-swallow on ep161/163/164/165/166; missing Intro on ep168) — shared chapter architecture, not PT prompt padding
- Garbage mid-body LLM auto-segment titles — shared Tesla/M&A-deferred class
- Network pronunciation of Nerra / Planetterrian (Whisper: Narra/Narrow/Planetarian) — no phonetic respelling (landmine #17)
- Optional min_digest_words 1400→1700 only if operator explicitly picks length option (b); do not treat as automatic ship with a conditional length hit prediction

## Drift-guard status
```
============================= test session starts ==============================
collected 12 items

tests/test_planetterrian_quality_pass.py ............                    [100%]

============================== 12 passed in 1.25s ==============================
```

<sub>tokens: 47096 in / 5345 out</sub>