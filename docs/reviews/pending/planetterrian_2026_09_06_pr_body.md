Sep 5–6 delivery gates and de-seeds partly landed but ep166–175 still show 9/10 under-length, Deep Dive body-swallow on ~7/10, orphaned cold-open on ep175, surviving banned tails, and general-science firehose scope; escalate length to operator decision and propose only digest-side scope + residual ban/MEMORY fixes.

_Generated on **grok-4.5** by `scripts/run_show_review.py` (replaces the Claude-Opus review agent). Estimated cost: **$0.1338**._

## Scored prior predictions
| Prediction | Verdict | Evidence |
|---|---|---|
| fetch-filter leakage matches in last 10 digests (black hole\|superstorm\|solar wind\|exoplanet\|telescope classes) | hit | snapshot fetch-filter section: 0 hits vs 21 exclude_title_patterns (was 3 on ep160) |
| life-science / longevity / clinical-health items in Top 15 per digest (manual count, last 10) | miss | scope floor never shipped; ep168–175 still mix archaeology, materials, graphene, Mercury geology, dark matter, policy with longevity items |
| transcripts with verbatim 'shifting to a very different area of research', last 10 | partial | still spoken on ep167 and ep173; down from 6+/10 but ban not clean |
| episodes under 1600-word floor, last 10 | hit | 9/10 under (only ep171=1709 clears) — matches expected still 8+/10 with digest ceiling unchanged |
| episodes with Science Deep Dive spanning >50% runtime or missing Introduction, last 10 | miss | worse: ep166/172/174/175 swallow; ep168 missing Intro; ep170 missing Teaser; ~7/10 |
| median _tts.txt words, last 10 eps | miss | median ~1280 words on ep166–175; 9/10 below 1600 floor |
| 'announcing' filler shape per episode (script_audit) | partial | density filler column 3–11% across ep166–175; not held to ≤1 |
| deep dive restating a covered story (manual) | miss | snapshot copied_sections flags Science Deep Dive on most of ep166–175; ep171 dive retells obesity leukocyte body story |
| script_digest_overlap_pct median | miss | ep166/168/170/173/174 at 53–77% verbatim; median well above ≤25% target |
| script_hook_orphaned, next 15 episodes | miss | ep175 hook coverage 10% — Uzbekistan projectile cold open never covered in body |
| script_copied_sections on the Science Deep Dive, last 10 | miss | snapshot marks Dive under copied sections on ~10/10 ep166–175 |
| surviving banned tails ('practical takeaway', 'keep an eye on') per episode | miss | both still multi-episode through ep175 (practical takeaway in dives; keep an eye on in 9/10 teasers) |

## ⚠️ A/B-listen required — NOT applied (landmine #17)
These prompt/audio changes are **proposals only**. Apply them yourself, render/listen, then merge if they sound right.

**`shows/prompts/planetterrian_digest.txt`** (prompt) — July-2 through Aug-31 scope proposals never applied; ep168–175 still read as general-science radio while YAML description promises longevity/health. Digest-only lever; A/B changes spoken mix.
```diff
- ### SELECTION & COUNTS
- - **News**: Target 15 high-quality items every day.
+ ### SELECTION & COUNTS
+ - **Brand scope floor (life-science majority):** At least 8 of 15 Top items must be core Planetterrian beat — longevity/aging biology, neuroscience/cognition, microbiome, sleep/circadian, nutrition/exercise physiology, genetics/genomics mechanisms, regenerative/stem-cell biology, cellular/molecular physiology, clinical health with a biological mechanism, public-health biology, or environmental health with a human physiology link. Explicitly OUT of scope as lead items (use only if life-science pool cannot reach 8): pure archaeology/paleopathology without a living-biology mechanism, pure condensed-matter/materials/physics, routine climate-tech/energy without human health mechanism, education/criminal-justice/policing policy, sports economics, and pure astronomy/space physics (FF-owned; fetch filter should already drop most). Prefer Nature/Science/bioRxiv/Lifespan/medical RSS over generic Phys.org/ScienceDaily oddities when trimming.
+ - **News**: Target 15 high-quality items every day.
```

**`shows/prompts/planetterrian_podcast.txt`** (prompt) — Sep-5 de-seed incomplete: ep167/173 still speak the shifting line; practical takeaway + one memorable detail + right-now frames survive through ep175. Meta-review: ban + shape, no new example menu; log successor tics.
```diff
- - Use natural transitions between stories ("Now, shifting to..." or "On a different note..." or simply "Next up...")
+ - Transitions: one short bridge naming the next finding’s domain — never a recited stock line. VERBATIM BAN (do not write): "Now, shifting to a very different area of research", "shifting to a very different area", "On a different note", "The practical takeaway is", "A practical takeaway is", "One memorable detail is that", "Right now, as you listen", "Right now, as you're listening", "Right now, as you sit listening". Shape ban: no “practical takeaway” closer; no “one memorable detail/figure” template; no stock second-person “right now as you…” frame — if immediacy is needed, name a specific physiological process from the digest only. Prefer silent handoff or “Next:” + first fact of the new story.
```

**`shows/prompts/planetterrian_podcast.txt`** (prompt) — Snapshot 9/10 “keep an eye on” — prompt-seeded convergence. Chapter YAML already accepts alternate anchors; rotation stays parseable.
```diff
- [Tomorrow Teaser — one sentence before the closing]
- Patrick: Before we go — briefly tease something listeners should watch for in the next episode based on developing stories from today's news. Keep it specific and forward-looking: "Next time, we'll be watching for..." or "Keep an eye on..." This builds habitual listening.
+ [Tomorrow Teaser — one sentence before the closing]
+ Patrick: One specific forward-looking beat from today’s sources (a named trial, readout, follow-up animal study, or dated next step the digest actually reported). Rotate the lead-in shape — do NOT default to "Keep an eye on". Allowed shapes (pick one, vary across episodes): "Before we go — …", "Next time we’re watching …", "Still ahead: …", "One thread to follow: …". VERBATIM BAN as teaser opener: "Keep an eye on". Chapter markers still match Before we go|Next time|before we wrap|watch for.
```

**`shows/prompts/planetterrian_podcast.txt`** (prompt) — copied_sections still flags Dive most days; ep171 re-told obesity body story. Reinforces Sep-5/6 gates with explicit podcast-side no-restatement + no takeaway closer.
```diff
- - It is a second story, not a second pass: if the deep dive grows out of a story already covered, nothing from that story's body is restated — only the mechanism and the numbers the body did not use. End on the last fact; the listener draws the takeaway.
+ - It is a second story, not a second pass: if the deep dive grows out of a story already covered, nothing from that story's body is restated — only the mechanism and the numbers the body did not use. Prefer a concept the Top 15 and Spotlight did NOT already report (digest zero-overlap). End on the last fact; the listener draws the takeaway. Never close the dive with "practical takeaway" / "what you can do" boilerplate.
```

**`shows/planetterrian.yaml`** (config) — Belt-and-braces for paraphrase myth openers that skip the Dive chapter; does NOT fix body-swallow (engine split still deferred). A/B-listen: changes player chapter boundaries.
```diff
- - pattern: "science deep dive|deep dive|under the microscope|something most people get wrong|most people (picture|assume|think|believe|get wrong)"
-       title: "Science Deep Dive"
+ - pattern: "science deep dive|deep dive|under the microscope|something most people get wrong|most people (picture|assume|think|believe|get wrong|have heard)|you've probably (heard|been told)|everyone thinks"
+       title: "Science Deep Dive"
```

## Deferred (carried forward)
- OPERATOR DECISION on chronic under-length after repeated misses with digest_expand already on: (a) full-text journal fetch Nature/Science/bioRxiv, (b) higher min_digest_words + per-item sentence floors only, (c) lower min_podcast_words to honest ceiling, (d) accept short days — do NOT re-propose podcast_expand_below_target or podcast word-pressure
- Engine-level split so content after Science Deep Dive re-enters story auto-segments (body-swallow ep166/172/174/175; missing Intro ep168; missing Teaser ep170) — shared chapter architecture, not PT prompt padding
- Garbage mid-body LLM auto-segment titles — shared Tesla/M&A-deferred class (ep171 samples)
- Network pronunciation of Nerra / Planetterrian (Whisper: Narra/Narrow/Planetarian) — no phonetic respelling (landmine #17)
- Optional min_digest_words 1400→1700 only if operator explicitly picks length option (b); no conditional length hit prediction
- Confirm hook_coverage / copied_sections gates fail closed on PT (ep175 orphan + Dive copy) rather than rewrite-and-accept weak scripts

## Drift-guard status
```
============================= test session starts ==============================
collected 12 items

tests/test_planetterrian_quality_pass.py ............                    [100%]

============================== 12 passed in 0.87s ==============================
```

<sub>tokens: 49974 in / 5637 out</sub>