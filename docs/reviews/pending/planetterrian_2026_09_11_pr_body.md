9/10 scripts still under the 1600-word floor, Science Deep Dive body-swallow on ~8/10, residual banned tails and transition tics, one telescope fetch leak, and longevity brand still shipping general-science firehose; escalate length again and re-propose only digest-side scope plus residual ban/MEMORY fixes.

_Generated on **grok-4.5** by `scripts/run_show_review.py` (replaces the Claude-Opus review agent). Estimated cost: **$0.1486**._

## Scored prior predictions
| Prediction | Verdict | Evidence |
|---|---|---|
| fetch-filter leakage matches in last 10 digests | partial | 1 hit ep176 Parkes telescope vs baseline 0; not multi-hit regression but not clean |
| life-science / longevity / clinical-health items in Top 15 per digest (manual count, last 10) | miss | scope floor never shipped; ep172–180 still mix archaeology, materials, graphene, Mercury, dark matter, conflict, education with longevity items |
| episodes under 1600-word floor, last 10 | hit | 9/10 under (only ep171=1709 clears) — matches expected still 8+/10 with digest ceiling unchanged |
| script_hook_orphaned rate, last 10 after hook_coverage gate | miss | ep175 hook cov 10% (Uzbekistan points never in body); ep180 36% |
| transcripts with 'The practical takeaway is' OR sole teaser lead-in 'keep an eye on', last 10 | miss | practical takeaway on ep171/173/174/175; keep an eye on in 9/10 teasers |
| episodes with Science Deep Dive spanning >50% runtime or missing Introduction, last 10 | miss | ~8/10: ep172/174/175/177/178/179 swallow; ep173 no Intro; ep180 no Teaser |
| script_digest_overlap_pct median + Dive listed in copied_sections, last 10 | miss | ep173/174/179 at 63–64% verbatim; Dive under copied_sections on ep171–176 and ep179 |
| median _tts.txt words, last 10 eps | miss | median ~1330 on ep171–180; 9/10 below 1600 floor |
| deep dive restating a covered story (manual) | miss | copied_sections flags Dive majority of window; ep171 dive retells obesity leukocyte body story |
| surviving banned tails / Sep-5 transition shapes | partial | shifting line still ep173; successor 'on a different note' rises; filler 2–11% not zeroed |

## ⚠️ A/B-listen required — NOT applied (landmine #17)
These prompt/audio changes are **proposals only**. Apply them yourself, render/listen, then merge if they sound right.

**`shows/prompts/planetterrian_digest.txt`** (prompt) — July-2 through Sep-6 scope proposals never applied; ep172–180 still read as general-science radio while YAML description promises longevity/health. Digest-only lever; A/B changes spoken mix.
```diff
- ### SELECTION & COUNTS
- - **News**: Target 15 high-quality items every day.
+ ### SELECTION & COUNTS
+ - **Brand scope floor (longevity / life-science)**: At least 8 of 15 Top items must be core life-science, longevity, clinical-health, neuroscience, microbiome, cellular/aging biology, sleep/circadian, nutrition, genetics/genomics, regenerative biology, or public-health biology. Out-of-scope as lead items (use only if life-science pool is exhausted below 8): archaeology-as-lead, pure materials/condensed-matter/physics, pure astronomy/space-physics, routine climate-tech without human-biology mechanism, education/criminal-justice/armed-conflict policy without biology, music/psychology surveys without a health endpoint. Prefer Nature/Science/bioRxiv/Lifespan/primary biology over general Phys.org/ScienceDaily oddities.
+ - **News**: Target 15 high-quality items every day.
```

**`shows/prompts/planetterrian_digest.txt`** (prompt) — Digest framework still seeds the exact spoken tics (Right now / memorable detail / practical takeaway) that survive into podcast audio on ep171–179. De-seed by shape; meta-review successor-tic rule.
```diff
- Write 6-8 sentences following this "Body/Nature Explainer" framework:
- - **Open with the myth or misconception** — name what most people believe, then flip it. ("You've probably heard that you lose most body heat through your head. That's a myth — here's what actually happens..." / "Everyone thinks antibiotics kill bacteria. They don't, exactly — here's the surprising way they work...")
- - **Make it personal and immediate** — "Right now, as you listen to this, your body is..." or "The next time you [everyday action], here's what's actually happening inside..."
- - **Include one memorable number** that listeners will want to share. ("Your gut has 38 trillion bacteria — that's more than your own cells." / "A single nerve signal travels at 120 metres per second — faster than a Formula 1 car.")
- - **Close with a practical takeaway** — what can a listener actually DO differently with this knowledge, or one specific thing to watch for in future science news.
+ Write 6-8 sentences following this "Body/Nature Explainer" framework (SHAPE only — never paste the example wording into the digest):
+ - **Open with the myth or misconception** — name the common belief in your own words, then flip it with the real mechanism. Do NOT use stock openers like "You've probably heard that…" as a fixed template.
+ - **Make it concrete and immediate** — name the tissue, cell type, molecule, or process and what it is doing; never a stock second-person frame ("Right now, as you listen/sit…").
+ - **Include one sourced number** (sample size, rate, duration, count) from knowledge or today's papers — state the number, do not label it "one memorable number/detail is".
+ - **End on the last fact** — no "practical takeaway is…", no generic watch-for closer; the listener draws the implication. If a dated next step exists in a source, one factual clause is enough.
```

**`shows/prompts/planetterrian_podcast.txt`** (prompt) — ep173 still speaks the shifting line; successor 'on a different note' on ep175/176/177/179. Meta-review: ban + shape + MEMORY, no new example menu.
```diff
- - Use natural transitions between stories ("Now, shifting to..." or "On a different note..." or simply "Next up...")
- - NEVER retell or revisit a story you already covered, even from a different angle. Each news item gets ONE treatment. Once you have covered a story, it is done — move on to the next topic.
- - Do NOT repeat transition sentences. When you write a transition at the end of one story, start the next story with NEW content — do not repeat the transition line.
+ - Transitions: move by the next story's first fact — no recited handoff line. VERBATIM BAN (never speak): "shifting to a very different area of research", "on a different note", "now shifting to", "from X we turn/move to Y" as empty bridges, "pairs well with", "leads naturally to". Shape ban: analogy bridges that assert a false link between unrelated studies. Prefer silence or one concrete noun from the next finding.
+ - NEVER retell or revisit a story you already covered, even from a different angle. Each news item gets ONE treatment. Once you have covered a story, it is done — move on to the next topic.
+ - Do NOT repeat transition sentences. When you write a transition at the end of one story, start the next story with NEW content — do not repeat the transition line.
+ - RECENT HANDOFF MEMORY: do not reuse the last several episodes' transition openers; invent a fresh factual entry each time.
```

**`shows/prompts/planetterrian_podcast.txt`** (prompt) — Sep-5/6 de-seed incomplete: practical takeaway + memorable detail + Right now frames survive through ep179; ep171 restated body obesity story. Reinforce zero-overlap + bans.
```diff
- [Science Deep Dive — 90-120 seconds; on thin-news days this is the length lever — go longer, not pad news]
- If the digest has a Science Deep Dive section, this is your myth-busting moment. Expand it into a spoken explanation that makes listeners rethink something they thought they knew:
- - The segment's first sentence must contain one of the anchor phrases "something most people get wrong" or "most people assume" (podcast-app chapters key off them), inside a sentence of your own that names the belief being corrected — never a recited transition line.
- - Make it immediate by naming what the body is actually doing, in specifics from the digest — never a stock second-person frame.
- - Deliver the surprising number with emphasis — let listeners absorb it before moving on.
- - It is a second story, not a second pass: if the deep dive grows out of a story already covered, nothing from that story's body is restated — only the mechanism and the numbers the body did not use. End on the last fact; the listener draws the takeaway.
- - Do NOT announce it as "Science Deep Dive" — flow into it as a moment of "actually, did you know..."
- Target: 90-120 seconds of audio (longer on thin-news days — deepen the mechanism, not the significance padding).
+ [Science Deep Dive — 90-120 seconds; on thin-news days this is the length lever — go longer, not pad news]
+ If the digest has a Science Deep Dive section, this is your myth-busting moment. Expand it into a spoken explanation that makes listeners rethink something they thought they knew:
+ - The segment's first sentence must contain one of the anchor phrases "something most people get wrong" or "most people assume" (podcast-app chapters key off them), inside a sentence of your own that names the belief being corrected — never a recited transition line.
+ - Make it immediate by naming tissue/cell/molecule and mechanism from the digest — never a stock second-person frame.
+ - Deliver one sourced number with a beat of silence around it — do not label it "one memorable detail/figure/number is".
+ - It is a second story, not a second pass: if the deep dive grows out of a story already covered, nothing from that story's body is restated — only the mechanism and the numbers the body did not use. End on the last fact; the listener draws the takeaway.
+ - VERBATIM BAN inside the dive (never speak): "The practical takeaway is", "One memorable detail is", "One memorable figure", "One memorable number", "Right now, as you sit", "Right now, as you listen", "Right now, as you're", "Right now, as you focus".
+ - Do NOT announce it as "Science Deep Dive" — flow into it as a moment of actually-did-you-know without that label.
+ Target: 90-120 seconds of audio (longer on thin-news days — deepen the mechanism, not the significance padding).
```

**`shows/prompts/planetterrian_podcast.txt`** (prompt) — Snapshot 9/10 “keep an eye on” — prompt-seeded convergence. Chapter YAML already accepts alternate anchors; rotation stays parseable.
```diff
- [Tomorrow Teaser — one sentence before the closing]
- Patrick: Before we go — briefly tease something listeners should watch for in the next episode based on developing stories from today's news. Keep it specific and forward-looking: "Next time, we'll be watching for..." or "Keep an eye on..." This builds habitual listening.
+ [Tomorrow Teaser — one sentence before the closing]
+ Patrick: Before we go — briefly tease one specific developing story from today's news (named trial, mission data, follow-up measurement). Keep it forward-looking and concrete.
+ - Rotate lead-ins across episodes; chapter markers already accept: Before we go | Next time | before we wrap | keep an eye on | watch for.
+ - VERBATIM BAN as the default sole lead-in every night: do not open 3+ consecutive teasers with "Keep an eye on". Prefer "Before we go" / "Next time" / "Watch for" / a bare factual clause.
+ - RECENT TEASER MEMORY: do not reuse the exact lead-in phrase from the prior 5 episodes' teasers.
```

**`shows/planetterrian.yaml`** (config) — Belt-and-braces for paraphrase myth openers that skip the Dive chapter; does NOT fix body-swallow (engine split still deferred). A/B-listen: changes player chapter boundaries.
```diff
-     - pattern: "science deep dive|deep dive|under the microscope|something most people get wrong|most people (picture|assume|think|believe|get wrong)"
-       title: "Science Deep Dive"
+     - pattern: "science deep dive|deep dive|under the microscope|something most people get wrong|most people (picture|assume|think|believe|get wrong|have heard)|here's something most people"
+       title: "Science Deep Dive"
```

## Code/metadata-only proposals (no A/B needed)
- **`shows/planetterrian.yaml`** (config): ep176 Parkes telescope/pulsar glitch leaked despite telescope pattern — likely mid-title or alternate wording path; add pulsar class (no life-science reading) and keep telescope. Code path audit still recommended if leakage repeats. No A/B (fetch only).

## Deferred (carried forward)
- OPERATOR DECISION on chronic under-length after repeated misses with digest_expand already on: (a) full-text journal fetch Nature/Science/bioRxiv, (b) higher min_digest_words + per-item sentence floors only, (c) lower min_podcast_words to honest ceiling, (d) accept short days — do NOT re-propose podcast_expand_below_target or podcast word-pressure
- Engine-level split so content after Science Deep Dive re-enters story auto-segments (body-swallow ep172/174/175/177–179; missing Intro ep173; missing Teaser ep180) — shared chapter architecture, not PT prompt padding
- Garbage mid-body LLM auto-segment titles — shared Tesla/M&A-deferred class (ep171 samples)
- Network pronunciation of Nerra / Planetterrian (Whisper: Narra/Narrow/Planetarian) — no phonetic respelling (landmine #17)
- Optional min_digest_words 1400→1700 only if operator explicitly picks length option (b); no conditional length hit prediction
- Confirm hook_coverage / copied_sections gates fail closed on PT (ep175 orphan + Dive copy) rather than rewrite-and-accept weak scripts

## Drift-guard status
```
============================= test session starts ==============================
collected 12 items

tests/test_planetterrian_quality_pass.py ............                    [100%]

============================== 12 passed in 1.57s ==============================
```

<sub>tokens: 52139 in / 7393 out</sub>