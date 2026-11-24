Length floor is now met under grok-4.7 (0/10 under 1400), but the still-seeded “rough magic-wand estimate” hedge recurs in recent transcripts, chapter markers mis-fire on hook “raw materials” / garbage auto-titles, and Ep151 shipped a literal “*” title.

_Generated on **grok-4.5** by `scripts/run_show_review.py` (replaces the Claude-Opus review agent). Estimated cost: **$0.1365**._

## Scored prior predictions
| Prediction | Verdict | Evidence |
|---|---|---|
| occurrences of 'rough magic wand estimate' / 'rough magic-wand estimate' across 10 transcripts | miss | De-seed never applied; ep155/156/158 still speak rough magic wand estimate/floor |
| successor hedging tic — any single stock estimate-opener (e.g. 'reported to be around', 'ballpark material floor') in 5+/10 transcripts | partial | No new opener at ≥5/10 (snapshot clear); old magic-wand family still 3/10 |

## ⚠️ A/B-listen required — NOT applied (landmine #17)
These prompt/audio changes are **proposals only**. Apply them yourself, render/listen, then merge if they sound right.

**`shows/prompts/first_principles_system.txt`** (prompt) — System prompt still seeds the exact hedge strings the podcast stage fights; Ep097 revival and ep155/156/158 prove the teacher prompt wins. Shape-based de-seed + verbatim ban, no replacement quotable example (July 2026 meta-review).
```diff
- ACCURACY IS NON-NEGOTIABLE (this show lives or dies on its numbers):
- - Use only well-established, widely-reported figures. Do NOT invent precise dollar amounts, dates, percentages, part counts, or quotes.
- - Every estimate must be framed as an estimate: "roughly," "on the order of," "a rough magic-wand estimate," "reported to be around." Prefer ratios and ranges over false-precision single numbers.
- - When the public record is thin or disputed, say so plainly ("exact figures aren't public, but the order of magnitude is clear because…"). A host who flags uncertainty earns more trust than one who fakes precision.
- - Never present a back-of-the-envelope Idiot Index as a measured fact. Make the reasoning visible so the listener can follow it and judge it themselves.
- - Never fabricate a quotation or attribute a specific claim to a named person or paper unless it is genuinely well known.
+ ACCURACY IS NON-NEGOTIABLE (this show lives or dies on its numbers):
+ - Use only well-established, widely-reported figures. Do NOT invent precise dollar amounts, dates, percentages, part counts, or quotes.
+ - Every estimate must be framed as an estimate. Vary the hedge naturally (shape: a short uncertainty marker before or after the figure — e.g. roughly / about / approximately / around / as a ballpark / as an estimate). Prefer ratios and ranges over false-precision single numbers.
+ - BANNED as stock teaching examples and as default phrasing (they became on-air tics): the exact strings "on the order of", "a rough magic-wand estimate", "a rough magic wand estimate", "rough magic wand floor". Do not quote them as the preferred pattern; pick a fresh hedge each time.
+ - When the public record is thin or disputed, say so plainly ("exact figures aren't public, but the order of magnitude is clear because…"). A host who flags uncertainty earns more trust than one who fakes precision.
+ - Never present a back-of-the-envelope Idiot Index as a measured fact. Make the reasoning visible so the listener can follow it and judge it themselves.
+ - Never fabricate a quotation or attribute a specific claim to a named person or paper unless it is genuinely well known.
```

**`shows/prompts/first_principles_podcast.txt`** (prompt) — Mirrors the on-the-order-of ban that scored a hit; closes the magic-wand estimate hole still shipping in ep155/156/158. Shape/verbatim ban only — no new example phrase for the model to elect next.
```diff
- - Preserve the brief's hedging. If the brief says a figure is approximate, keep it approximate aloud, varying the hedging wording naturally. Never upgrade a hedged number into a hard fact. BANNED as a recurring on-air tic: the phrase "on the order of" — even when the brief uses it, hedge that figure in different natural words.
+ - Preserve the brief's hedging. If the brief says a figure is approximate, keep it approximate aloud, varying the hedging wording naturally. Never upgrade a hedged number into a hard fact. BANNED as recurring on-air tics (even when the brief uses them — re-hedge in different natural words): "on the order of"; "a rough magic-wand estimate"; "a rough magic wand estimate"; "rough magic wand estimate"; "rough magic wand floor"; "magic wand estimate" as a stock opener before a figure. Name the magic-wand *tool* when teaching it; do not use that family as the default uncertainty wrapper every time a number appears.
```

## Code/metadata-only proposals (no A/B needed)
- **`shows/prompts/first_principles_weekly.txt`** (prompt): Newsletter-only surface; remove the same seeded phrases so weekly copy cannot reintroduce the on-air tic family. No audio path.
- **`shows/first_principles.yaml`** (config): Ep154 hook 'raw materials' matched bare 'raw material' and stole chapter 0 from Introduction. Drop bare raw material/atoms; keep phrases that mark the analytical section, not the cold-open hook. Metadata-only — no TTS field changes.
- **`tests/test_first_principles_quality_pass.py`** (code): Every behavioral fix gets a drift-guard; pins Ep151 title defect, Ep154 marker steal, and hedge re-seed. Judge committed episodes ≥1 day old so today's run does not false-red.

## Deferred (carried forward)
- Garbage auto-segment chapter titles (shared network LLM-title class) — Ep159 confirmed; network sanitizer not FP prompt
- Closer template reword if operator confirms Whisper 'depreciated' comes from written closer — no phonetics (landmine #17)
- Further podcast-side length escalation / min_podcast_words prompt pressure — do_not_retry; 0/10 under floor on grok-4.7
- Optional operator choice: lower min_podcast_words tripwire ~1100 for dashboard hygiene only — not required while floor is met
- Richer queue-brief / licensed-number substrate — only if length or emptiness regresses on 4.3 fallback windows; Aug 20 rejected write-past-floor expand

## Drift-guard status
```
============================= test session starts ==============================
collected 16 items

tests/test_first_principles_quality_pass.py ................             [100%]

============================== 16 passed in 0.73s ==============================
```

<sub>tokens: 56018 in / 4083 out</sub>