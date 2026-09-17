All 10 recent scripts sit under the 1400-word floor (length misses again — escalate, do not re-litigate), the 'on the order of' ban hit, but the system prompt still seeds 'a rough magic-wand estimate' (revived in Ep097) and must be de-seeded by shape.

_Generated on **grok-4.5** by `scripts/run_show_review.py` (replaces the Claude-Opus review agent). Estimated cost: **$0.1055**._

## Scored prior predictions
| Prediction | Verdict | Evidence |
|---|---|---|
| episodes below 1500-word floor in last 10 _tts.txt | miss | Live floor is 1400; 10/10 last _tts.txt are 1200–1388w (ep94–103 snapshot) — worse than July 29 baseline 6/10 |
| occurrences of 'on the order of' across 10 transcripts | hit | Phrase absent from ep94–103 Whisper transcripts; prior baseline was 6/10 |

## ⚠️ A/B-listen required — NOT applied (landmine #17)
These prompt/audio changes are **proposals only**. Apply them yourself, render/listen, then merge if they sound right.

**`shows/prompts/first_principles_system.txt`** (prompt) — System prompt still seeds the exact hedging strings the podcast stage bans; Ep097 revived 'A rough magic wand estimate' because the teacher prompt keeps quoting it. De-seed by shape + verbatim ban per July 2026 meta-review (no replacement quotable example).
```diff
- - Every estimate must be framed as an estimate: "roughly," "on the order of," "a rough magic-wand estimate," "reported to be around." Prefer ratios and ranges over false-precision single numbers.
+ - Every estimate must be framed as an estimate. Vary the hedge naturally each time (approximate range, clearly-flagged back-of-envelope, public-record uncertainty) — never lean on one stock opener. Prefer ratios and ranges over false-precision single numbers. Do NOT use the stock formulas "on the order of" or "a rough magic-wand estimate" / "rough magic wand estimate"; those calcified on air.
```

**`shows/prompts/first_principles_podcast.txt`** (prompt) — Mirrors the 'on the order of' ban that scored a hit; closes the successor hole proven in Ep097 transcript. Shape ban + verbatim list; no new example phrase for the model to elect next.
```diff
- - Preserve the brief's hedging. If the brief says a figure is approximate, keep it approximate aloud, varying the hedging wording naturally. Never upgrade a hedged number into a hard fact. BANNED as a recurring on-air tic: the phrase "on the order of" — even when the brief uses it, hedge that figure in different natural words.
+ - Preserve the brief's hedging. If the brief says a figure is approximate, keep it approximate aloud, varying the hedging wording naturally. Never upgrade a hedged number into a hard fact. BANNED as recurring on-air tics (even when the brief uses them — re-hedge in different natural words): (1) the phrase "on the order of"; (2) "a rough magic wand estimate" / "a rough magic-wand estimate" / "rough magic-wand estimate". Shape ban: do not open an estimate with a stock "rough … estimate" formula; state the figure as an approximate range or clearly-flagged back-of-envelope in fresh words each time.
```

## Code/metadata-only proposals (no A/B needed)
- **`shows/prompts/first_principles_weekly.txt`** (prompt): Newsletter-only surface; remove the same seeded phrases so weekly copy cannot reintroduce the on-air tic family. No audio path — ab_listen false.

## Deferred (carried forward)
- OPERATOR DECISION (escalate — length metric missed repeatedly July→Sep with the same proposal class): accept ~1200–1400w grok-4.3 plateau and lower min_podcast_words to a real thin-pass tripwire (~1100), OR invest in richer queue-brief substrate without 'write past the floor' prompt pressure (Aug 20 listen already rejected that as repetitive). Do not ship another length prompt or re-enable podcast_expand_below_target.
- Garbage auto-segment chapter titles (shared network LLM-title class) — not seen in ep94–103; keep on backlog only.
- Further podcast-side length escalation / prompt word-floor pressure — do_not_retry (network category rule + FP ledger).
- Reword stock closer if operator confirms written text causes Whisper 'depreciated' garble — no phonetic respelling (landmine #17).
- Growth/P2: first-week downloads median 0 despite YT+newsletter on — needs operator distribution strategy, not a prompt tweak.

## Drift-guard status
```
============================= test session starts ==============================
collected 16 items

tests/test_first_principles_quality_pass.py ................             [100%]

============================== 16 passed in 1.26s ==============================
```

<sub>tokens: 43954 in / 2927 out</sub>