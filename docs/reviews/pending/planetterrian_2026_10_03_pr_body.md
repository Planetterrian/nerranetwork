9/10 scripts still under the 1600-word floor, ep201 is pure astronomy with telescope-filter leakage and Dive body-swallow, keep-an-eye-on remains 10/10, and longevity brand scope still ships general-science firehose—escalate length again and propose only fetch tighten + residual ban/MEMORY fixes.

_Generated on **grok-4.5** by `scripts/run_show_review.py` (replaces the Claude-Opus review agent). Estimated cost: **$0.1593**._

## Scored prior predictions
| Prediction | Verdict | Evidence |
|---|---|---|
| fetch-filter leakage matches in last 10 digests | miss | 3 telescope hits on ep201 (GRAPES-3 muon telescope) vs expected 0 after tighten |
| life-science / longevity / clinical-health items in Top 15 per digest (manual count, last 10) | miss | scope floor never shipped; ep193-202 still mix paleontology, quakes, spaceflight, muon telescopes, quantum, policy with longevity |
| episodes under 1600-word floor, last 10 | hit | 9/10 under (only ep201=1910 clears) — matches expected still 8+/10 with digest ceiling unchanged |
| transcripts with 'The practical takeaway is' OR sole teaser lead-in 'keep an eye on' OR stock 'Right now, as you', last 10 | miss | keep an eye on 10/10; practical takeaway on ep198; Right now frames multi-ep through ep202 |
| transcripts with verbatim 'shifting to a very different area of research' OR 'on a different note' handoff, last 10 | miss | on a different note + now-shifting/shifting focus multi-ep (192,193,195,197,200,202) |
| script_hook_orphaned rate, last 10 | partial | no ep175-class 10% orphan in ep193-202; hook cov still 40-54% on ep194/195/199 |
| episodes with Science Deep Dive spanning >50% runtime or missing Introduction/Teaser, last 10 | miss | ep201 Dive 112.6-809.8s (~78%); ep194 Intro-to-Dive swallow; ep200 no Dive chapter |
| script_digest_overlap_pct median + Dive listed in copied_sections, last 10 | miss | verbatim 45-74%; Dive/Top15 under copied_sections on 10/10 ep193-202 |
| median _tts.txt words, last 10 eps | miss | median ~1260 on ep193-202; 9/10 below 1600 floor |
| source_integrity_claims median | partial | fetch_full_text 12 + preferred_domains live; ep201 still astronomy-led — claims not re-scored in snapshot |
| episodes with items_without_source > half of items after the retry | partial | lint shipped Sep-24; snapshot does not flag empty Sources this window — monitor next 10 |
| show_notes_sources on the feed item | partial | not re-verified against RSS in this snapshot; carry expected >=5 on 10/10 |

## ⚠️ A/B-listen required — NOT applied (landmine #17)
These prompt/audio changes are **proposals only**. Apply them yourself, render/listen, then merge if they sound right.

**`shows/prompts/planetterrian_digest.txt`** (prompt) — July-2 through Sep-11 scope proposals never applied; ep193-202 still read as general-science radio while YAML description promises longevity/health. ep201 astronomy lead is the failure mode. Digest-only lever; A/B changes spoken mix.
```diff
- ### SELECTION & COUNTS
- - **News**: Target 15 high-quality items every day.
+ ### SELECTION & COUNTS
+ - **Life-science floor (brand)**: At least 8 of 15 Top items must be core life-science / longevity / clinical-health / neuroscience / microbiome / cellular-aging / sleep-circadian / genetics-of-health / regenerative biology on Earth. Archaeology, pure materials, space physics, astronomy, quantum hardware, education-policy, and generic climate-tech count toward the other 7 only. If the pool cannot fill 8, prefer fewer total items over padding with off-brand science. BEAT OWNERSHIP already assigns astronomy/space physics to Fascinating Frontiers — do not smuggle them back as Deep Dive or cold open.
+ - **News**: Target 15 high-quality items every day.
```

**`shows/prompts/planetterrian_digest.txt`** (prompt) — Digest framework still seeds the exact spoken tics (Right now / memorable detail / practical takeaway) that survive into podcast audio on ep193-202. De-seed by shape + ban; meta-review successor-tic rule.
```diff
- Write 6-8 sentences following this "Body/Nature Explainer" framework:
- - **Open with the myth or misconception** — name what most people believe, then flip it. ("You've probably heard that you lose most body heat through your head. That's a myth — here's what actually happens..." / "Everyone thinks antibiotics kill bacteria. They don't, exactly — here's the surprising way they work...")
- - **Make it personal and immediate** — "Right now, as you listen to this, your body is..." or "The next time you [everyday action], here's what's actually happening inside..."
- - **Include one memorable number** that listeners will want to share. ("Your gut has 38 trillion bacteria — that's more than your own cells." / "A single nerve signal travels at 120 metres per second — faster than a Formula 1 car.")
- - **Close with a practical takeaway** — what can a listener actually DO differently with this knowledge, or one specific thing to watch for in future science news.
+ Write 6-8 sentences as a Body/Nature Explainer (shapes only — never copy example wording):
+ - **Open by naming the misconception, then flip it** — state the false belief in plain words inside a fresh sentence; do NOT reuse stock openers from prior episodes.
+ - **Make it immediate with a concrete in-body mechanism from THIS topic** — name the tissue, molecule, or process; NEVER a stock second-person frame ("Right now, as you listen/sit/read...").
+ - **One surprising number the source or licensed knowledge actually supports** — deliver it once; do not label it "the memorable detail/number".
+ - **End on the last fact** — no "practical takeaway" closer, no "one thing to watch for" tail; the listener draws the implication.
+ BANNED VERBATIM in this section (and anywhere spoken): "Right now, as you"; "The practical takeaway is"; "One memorable detail/figure/number"; "something most people get wrong" as a recited bare line (anchor phrase may appear inside a full original sentence for chapters only).
```

**`shows/prompts/planetterrian_podcast.txt`** (prompt) — ep192-202 still speak on-a-different-note / now-shifting multi-ep; prompt still seeds those EXAMPLE strings. Meta-review: ban + shape + MEMORY, no new example menu. Successor-tic watch logged.
```diff
- - Use natural transitions between stories ("Now, shifting to..." or "On a different note..." or simply "Next up...")
+ - Transitions: move by the next story's first fact — no stock handoff line. BANNED VERBATIM (and close paraphrases): "Now, shifting to a very different area of research"; "On a different note"; "Now shifting to"; "Shifting focus"; "Shifting to". Do not replace them with a new fixed menu; vary or omit.
```

**`shows/prompts/planetterrian_podcast.txt`** (prompt) — Snapshot 10/10 keep an eye on — prompt-seeded convergence third generation. Chapter YAML already accepts alternate anchors; rotation stays parseable. Data-side MEMORY preferred over prompt-only after repeated misses.
```diff
- [Tomorrow Teaser — one sentence before the closing]
- Patrick: Before we go — briefly tease something listeners should watch for in the next episode based on developing stories from today's news. Keep it specific and forward-looking: "Next time, we'll be watching for..." or "Keep an eye on..." This builds habitual listening.
+ [Tomorrow Teaser — one sentence before the closing]
+ Patrick: One short forward-looking line on a dated next step from today's sources only. Shape: before-signoff + specific watch-target (a trial readout, a follow-up paper, a named cohort). BANNED VERBATIM as the teaser lead-in: "Keep an eye on"; "keep an eye on further". Prefer rotating shapes already valid for chapters (Before we go / Next time / before we wrap / watch for) without locking one phrase. If frame_memory or recent-teaser MEMORY is injected, honor it — do not reuse the last six teasers' opening verbs.
```

**`shows/prompts/planetterrian_podcast.txt`** (prompt) — copied_sections flags Dive/Top15 on 10/10; practical takeaway ep198; Right now multi-ep. Reinforce Sep-5/6 gates with explicit podcast-side bans + zero-overlap.
```diff
- - It is a second story, not a second pass: if the deep dive grows out of a story already covered, nothing from that story's body is restated — only the mechanism and the numbers the body did not use. End on the last fact; the listener draws the takeaway.
+ - It is a second story, not a second pass: if the deep dive grows out of a story already covered, nothing from that story's body is restated — only the mechanism and the numbers the body did not use. End on the last fact; the listener draws the takeaway.
+ - BANNED in the dive and anywhere: "The practical takeaway is"; "Right now, as you"; "One memorable detail/figure/number"; stock second-person body tours. Zero sentence-level overlap with Top 15 / Spotlight body text (copied_sections must stay clean).
```

**`shows/planetterrian.yaml`** (config) — Belt-and-braces for paraphrase myth openers that skip the Dive chapter; does NOT fix body-swallow (engine split still deferred). A/B-listen: changes player chapter boundaries.
```diff
- - pattern: "science deep dive|deep dive|under the microscope|something most people get wrong|most people (picture|assume|think|believe|get wrong)"
-       title: "Science Deep Dive"
+ - pattern: "science deep dive|deep dive|under the microscope|something most people get wrong|most people (picture|assume|think|believe|get wrong|have heard)|here's what actually happens|in reality,"
+       title: "Science Deep Dive"
```

## Code/metadata-only proposals (no A/B needed)
- **`shows/planetterrian.yaml`** (config): P0: ep201 shipped GRAPES-3 muon telescope / thunderstorm electric-field lead despite existing \btelescope\b — three snapshot leakage hits. Add muon-telescope / cosmic-ray / GRAPES / pulsar classes (no life-science reading). Fetch-only; no A/B. If leakage repeats after YAML, audit fetcher path (Aug-31 class).

## Deferred (carried forward)
- OPERATOR DECISION on chronic under-length after repeated misses with digest_expand + fetch_full_text already on: (a) deeper journal full-text / per-item sentence floors, (b) higher min_digest_words 1400→1700 + per-item floors only, (c) lower min_podcast_words to honest ceiling, (d) accept short days — do NOT re-propose podcast_expand_below_target or podcast word-pressure
- Engine-level split so content after Science Deep Dive re-enters story auto-segments (body-swallow ep194/201; missing Dive ep200) — shared chapter architecture, not PT prompt padding
- Garbage mid-body LLM auto-segment titles — shared Tesla/M&A-deferred class
- Network pronunciation of Nerra / Planetterrian (Whisper: Narra/Narrow/Planetarian) — no phonetic respelling (landmine #17)
- Optional min_digest_words 1400→1700 only if operator explicitly picks length option (b); no conditional length hit prediction
- Confirm hook_coverage / copied_sections gates fail closed on PT (10/10 Dive copy this window) rather than rewrite-and-accept weak scripts
- items_without_source + show_notes_sources monitor post Sep-24 lint until next feed re-check scores hit/miss cleanly

## Drift-guard status
```
============================= test session starts ==============================
collected 12 items

tests/test_planetterrian_quality_pass.py ............                    [100%]

============================== 12 passed in 0.97s ==============================
```

<sub>tokens: 57423 in / 7401 out</sub>