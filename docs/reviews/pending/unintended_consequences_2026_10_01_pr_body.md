Prior chapter/closing/gate fixes held, but chronic under-length remains (9/10 scripts below 1300) despite digest_expand, and the Lesson segment has converged on prompt-seeded stock principles (“Incentive structures always find their loopholes” / “Complex systems resist simple interventions”).

_Generated on **grok-4.5** by `scripts/run_show_review.py` (replaces the Claude-Opus review agent). Estimated cost: **$0.1100**._

## Scored prior predictions
| Prediction | Verdict | Evidence |
|---|---|---|
| fraction of last-10 episodes with Introduction-first + Closing-last chapter shape | hit | chapters_ep120–129 all Introduction at start, Closing at end, clean 4–6 chapter shapes |
| fraction of last-10 episodes shipping 'That wraps today's case' as the sign-off | hit | Still absent across ep119–128 transcripts; pool variants only |
| distinct closing variants across the last 10 episodes | hit | ≥3 variants live: 'That's unintended consequences for today' / 'And that's where today's story leaves us' / 'We'll leave it there for today…' |
| median _tts.txt words, last 10 episodes (under-length; NOT fixed this pass) | hit | median ≈1053 words; 9/10 still below 1300 — digest ceiling still the open problem |
| consecutive same-category episodes in produced queue order | partial | ep119–129 domain-diverse (fisheries→rabbits→bags→timber→rice→Aral→uniforms→HFCs→nuclear→labor→peat); queue category-field runs not re-audited from YAML this pass |
| UC consecutive missed days from a single gate-blocked topic | hit | Continuous ep120–129 publish window; no repeat of the 2026-08-24/25 same-topic multi-day hole |
| enforce-mode gate blocks recovered by claim repair (metrics: source_integrity_repair_succeeded) | miss | No source_integrity_repair_succeeded (or equivalent) signal in provided snapshot/health context |

## ⚠️ A/B-listen required — NOT applied (landmine #17)
These prompt/audio changes are **proposals only**. Apply them yourself, render/listen, then merge if they sound right.

**`shows/prompts/unintended_consequences_episode.txt`** (prompt) — Episode brief examples seeded a Lesson tic heard on multiple recent eps (ep121/122/128). De-seed by shape + verbatim ban per meta-review; feeds spoken audio so A/B-listen.
```diff
- ### Segment 6 — The Lesson
- 3–5 sentences. Extract one to three actionable principles. Frame them as general lessons listeners can apply to their own decisions ("incentive structures always find their loopholes," "complex systems resist simple interventions," etc.). Close with a forward-looking question or connection to today.
+ ### Segment 6 — The Lesson
+ 3–5 sentences. Extract one to three actionable principles. Each principle must be stated in plain prose tied to THIS case's mechanism (who optimized what signal, what went unmeasured, what adapted) so the same sentence could not be pasted unchanged into a different episode. Shape: name the mechanism → state the general rule in fresh wording → one present-day domain to watch. Do NOT use stock couplets or close paraphrases of: "incentive structures always find their loopholes"; "complex systems resist simple interventions"; "Goodhart's law" as a standalone punch line without the case-specific mechanism. Close with a forward-looking question or connection to today.
```

**`shows/prompts/unintended_consequences_podcast.txt`** (prompt) — June deferred lowering the fantasy 2200–2800/15–18m band until the digest lever landed; digest_expand is on and spoken runtime still plateaus ~7–10m. Re-point targets to stop ungrounded length pressure (not a podcast expand/grow lever).
```diff
- You are writing a 15–18 minute solo podcast script for "Unintended Consequences" Episode {episode_num}.
- 
- HOST: Patrick in Vancouver — narrator and journalist. Curious, analytical, warm. Never cynical, never mocking the past. The cadence is slightly slower and more reflective than a news show — this is documentary storytelling, not a briefing.
- 
- STRUCTURAL REQUIREMENTS:
- - 15–18 minutes target ≈ 2200–2800 spoken words
- - Six narrative segments (do NOT label them in the spoken script — flow naturally between them):
-   1. The Hook — vivid opening, ~1 minute
-   2. The Good Intention — who, why, when, what made it seem right, ~2–3 minutes
-   3. The Implementation — rollout, early signs, voices on both sides, ~2–3 minutes
-   4. The Unintended Consequences — the heart of the episode, specific data and human stories, causal chains, second and third-order effects, ~4–5 minutes
-   5. The Aftermath — response, reversal, redesign, meta-ironies, current state, ~2–3 minutes
-   6. The Lesson — actionable principles, forward-looking close, ~2 minutes
+ You are writing a ~10–12 minute solo podcast script for "Unintended Consequences" Episode {episode_num}.
+ 
+ HOST: Patrick in Vancouver — narrator and journalist. Curious, analytical, warm. Never cynical, never mocking the past. The cadence is slightly slower and more reflective than a news show — this is documentary storytelling, not a briefing.
+ 
+ STRUCTURAL REQUIREMENTS:
+ - ~10–12 minutes target ≈ 1400–1800 spoken words (do NOT pad with restated percentages-as-counts, repeated causal chains, or generic lesson couplets to hit a number; depth comes only from the brief)
+ - Six narrative segments (do NOT label them in the spoken script — flow naturally between them):
+   1. The Hook — vivid opening, ~45–60 seconds
+   2. The Good Intention — who, why, when, what made it seem right, ~1.5–2 minutes
+   3. The Implementation — rollout, early signs, voices on both sides, ~1.5–2 minutes
+   4. The Unintended Consequences — the heart of the episode, specific data and human stories, causal chains, second and third-order effects, ~3–4 minutes
+   5. The Aftermath — response, reversal, redesign, meta-ironies, current state, ~1.5–2 minutes
+   6. The Lesson — actionable principles, forward-looking close, ~1–1.5 minutes
```

**`shows/prompts/unintended_consequences_podcast.txt`** (prompt) — Matches de-seeded brief + shorter honest runtime; bans the observed Lesson tic at the script stage as belt-and-suspenders.
```diff
- - LESSON SEGMENT must end with one specific forward-looking question or modern parallel (not a generic "think about what we incentivize"). The lesson should run roughly two minutes — about 250 to 350 spoken words. Each principle stated only once. Do not restate the case study one more time as the close — instead, name a present-day situation that exhibits the same dynamic and ask the listener what they would watch for.
+ - LESSON SEGMENT must end with one specific forward-looking question or modern parallel (not a generic "think about what we incentivize"). Keep the lesson tight — about 150 to 250 spoken words. Each principle stated only once, in wording specific to this case's mechanism. Do NOT close on stock lines or close paraphrases of "incentive structures always find their loopholes" or "complex systems resist simple interventions." Do not restate the case study one more time as the close — instead, name a present-day situation that exhibits the same dynamic and ask the listener what they would watch for.
```

## Code/metadata-only proposals (no A/B needed)
- **`shows/unintended_consequences.yaml`** (config): Align the enforceable digest expand gate with the episode prompt's 1500–2200 target. Sanctioned length lever only; podcast_expand stays false.

## Deferred (carried forward)
- Missing-intro guard (June) — double-greeting risk; identity line looks healthier in ep119–128 but not formally guarded
- Re-clear Philippine land-reform topic (delete gate_blocks) once claim-repair has a scored track record (Aug 25)
- Cap 'One might ask/object' ≤1/ep and forbid absolute cost-effectiveness claims without units sanity (July 2 A/B, still shipping e.g. ep124)
- Data-side lesson-principle rotation memory from last N scripts if stock couplet survives prompt de-seed (prefer over a third prompt-only pass)
- Brief→script re-scene steer for Segments 4–5 without coverage%/overlap numeric gates
- Operator decision: accept ~8–10 min product (lower min_podcast_words + public expectations) vs keep 1300 spoken floor and only attack digest depth
- Verify Ep126 spoken episode number in _tts.txt (Whisper '146' vs Ep126)
- YouTube long-form ~9% retention — separate growth pass (thumbnails/policy), not a UC prompt tweak
- Do not re-pin grok-4.6 on UC without fresh staged trial (Aug 27 withdrawal still binds)

## Drift-guard status
```
============================= test session starts ==============================
collected 9 items

tests/test_unintended_consequences_quality_pass.py .........             [100%]

============================== 9 passed in 0.19s ===============================
```

<sub>tokens: 38562 in / 5483 out</sub>