July 31 handoff/magic/opener tics and Closing/Welcome gaps are cleared in ep219–228; remaining ceiling is high script fact-free rates (69–90%) plus stale phonetic hook entries and a digest-substrate length decision after the Nov floor cut.

_Generated on **grok-4.5** by `scripts/run_show_review.py` (replaces the Claude-Opus review agent). Estimated cost: **$0.1095**._

## Scored prior predictions
| Prediction | Verdict | Evidence |
|---|---|---|
| "okay now for my favorite part of the show" in last-10 transcripts | hit | 0/10 in ep219–228 Whisper transcripts; Deep Dive handoffs vary without that stem |
| Deep Dive closers using "stops feeling like magic\|mysterious" or "less like magic" (last 10) | hit | 0/10; closers use checklist/loop/notebook payoffs without magic/mysterious |
| Big Story openers starting "Here's something that" / "that's going to change" / "could change how you" (last 10) | hit | 0/10; cold opens are concrete scene/fact hooks (Airbnb agent, Fermi, Australia law, …) |
| episodes whose chapters include Closing (last 10) | hit | 10/10 chapters_ep219–228 end on Closing |
| cold-open episodes speaking an identity line matching Welcome anchor (last 10) | hit | 10/10 transcripts speak "This is Models & Agents for Beginners, Episode #" after the hook; Welcome chapter present |
| median _tts.txt words, last 10 (July 31 no-regression) | hit | median ≈1220 vs baseline ~1089; min_podcast_words later cut 1200→1000 and all 10 clear 1000 |
| source_integrity_claims median (Sep 24 network sourcing) | partial | fetch_full_text 10 + preferred_domains + x_only_lead live in YAML; snapshot has no claims median to score numerically |
| episodes with repeated boilerplate outro phrases ≤4/10 after de-seed (July 30) | miss | still 10/10 — intentional network outro + AI disclosure; de-seed correctly rejected (do_not_retry) |
| median _tts.txt words raise above 1200 floor (June 25 / July 30 length hopes) | miss | podcast-side length levers banned; operator cut floor to 1000 instead of raising digest substrate further |

## ⚠️ A/B-listen required — NOT applied (landmine #17)
These prompt/audio changes are **proposals only**. Apply them yourself, render/listen, then merge if they sound right.

**`shows/prompts/mab_podcast.txt`** (prompt) — Script fact-free 69–90% is the live REPETITIVE driver after the Nov 14 floor cut; density audit + ep219/ep226 transcript stacks show multi-metaphor restatement, not missing digest substrate.
```diff
- Analogy / explain-like-I'm-14 guidance that allows multiple restatements per beat (prompt currently pressures rich beginner metaphor coverage; exact block varies — operator should locate the analogies / "explain like" section).
+ HARD RULE — one analogy per story beat, then move. Every body sentence after the cold open must add at least one fresh number, named entity, date, or named try-this step that appears in the digest. Ban stacked spectator metaphors (do not restate the same idea in a second or third picture). Do NOT seed replacement cliché stems. Shape only: cold fact, one listener-moment picture, one concrete try-step.
```

**`shows/hooks/models_agents_beginners.py`** (code) — Stale Fish-era phonetics on Grok custom voice; landmine #17 / do_not_retry forbids adding phonetics (100% regression). Remove-only align with sister M&A letter-spellings; keep AI/GPT expansions and foreign names.
```diff
- "SOTA": "so-tah",
-             "LoRA": "laura",
-             "LoRAs": "lauras",
-             "QLoRA": "cue-laura",
-             "GGUF": "gee-guff",
-             "ONNX": "onyx",
+ 
```

## Code/metadata-only proposals (no A/B needed)
- **`tests/test_mab_quality_pass.py`** (code): Playbook: every behavioral fix gets a drift-guard; pins July 31 hits so they cannot silently regress and locks the hook cleanup.

## Deferred (carried forward)
- Operator decision only: raise min_digest_words / licensed-knowledge floors if longer beginner eps wanted — never podcast_expand_below_target or prompt word-pressure (network do_not_retry; June 25 miss + Nov 14 floor cut already accepted ~1000-word eps).
- Network digest-driven / position-aware chapter titles (raw-sentence class clear this window; still the right long-term lever).
- "Try this" items ineligible unless the tool is NAMED in the source (July 2; still intermittent).
- Quick Bits ≤3 sentences / every sentence a new fact (July 2 A/B, not applied).
- Analogy-stem variety (think of it like / picture / the way you) only if one stem >6/10 next window — shape ban, no replacement seed.
- NVIDIA identity override in MAB hook vs network pronunciation_map — listen-test only.
- MAB pronunciation hook full align with sister M&A beyond jargon phonetics removal (letter-spell policy already documented in hook docstring).

<sub>tokens: 42264 in / 4165 out</sub>