Sep-17 magic-wand de-seed missed (phrase still in 3/10 transcripts because system/episode prompts still seed it); length floor is largely recovered under grok-4.7 (2/10 under 1400); P0 chapter-title regressions on Ep136/137 plus high digest-verbatim on several 4.7 scripts.

_Generated on **grok-4.5** by `scripts/run_show_review.py` (replaces the Claude-Opus review agent). Estimated cost: **$0.1407**._

## Scored prior predictions
| Prediction | Verdict | Evidence |
|---|---|---|
| occurrences of 'rough magic wand estimate' / 'rough magic-wand estimate' across 10 transcripts | miss | Ep134/135/136/138 transcripts still speak 'a rough magic wand estimate…'; ≥3–4/10 vs expected 0/10 — Sep-17 de-seed never applied |
| successor hedging tic — any single stock estimate-opener (e.g. 'reported to be around', 'ballpark material floor') in 5+/10 transcripts | partial | Magic-wand estimate family is the active successor at 3–4/10 (under the 5/10 alarm but dominant); no distinct third formula at ≥5/10; on the order of still absent |

## ⚠️ A/B-listen required — NOT applied (landmine #17)
These prompt/audio changes are **proposals only**. Apply them yourself, render/listen, then merge if they sound right.

**`shows/prompts/first_principles_system.txt`** (prompt) — System prompt still seeds the exact hedging strings the podcast stage partially bans; Ep134–138 revived 'a rough magic wand estimate' because the teacher prompt keeps quoting it. De-seed by shape + verbatim ban per July 2026 meta-review (no replacement quotable example).
```diff
- ACCURACY IS NON-NEGOTIABLE (this show lives or dies on its numbers):
- - Use only well-established, widely-reported figures. Do NOT invent precise dollar amounts, dates, percentages, part counts, or quotes.
- - Every estimate must be framed as an estimate: "roughly," "on the order of," "a rough magic-wand estimate," "reported to be around." Prefer ratios and ranges over false-precision single numbers.
- - When the public record is thin or disputed, say so plainly ("exact figures aren't public, but the order of magnitude is clear because…"). A host who flags uncertainty earns more trust than one who fakes precision.
- - Never present a back-of-the-envelope Idiot Index as a measured fact. Make the reasoning visible so the listener can follow it and judge it themselves.
- - Never fabricate a quotation or attribute a specific claim to a named person or paper unless it is genuinely well known.
+ ACCURACY IS NON-NEGOTIABLE (this show lives or dies on its numbers):
+ - Use only well-established, widely-reported figures. Do NOT invent precise dollar amounts, dates, percentages, part counts, or quotes.
+ - Every estimate must be framed as an estimate. Hedge in natural, varied wording (e.g. roughly, approximately, about, somewhere around, a back-of-the-envelope floor). Prefer ratios and ranges over false-precision single numbers.
+ - BANNED as stock hedging formulas (do not write these strings, and do not teach them as the default): "on the order of", "a rough magic-wand estimate", "a rough magic wand estimate", "rough magic-wand estimate". Name the magic-wand *number* / raw-material floor as a concept, but open each estimate with fresh phrasing — never the same stock opener episode after episode.
+ - When the public record is thin or disputed, say so plainly ("exact figures aren't public, but the order of magnitude is clear because…"). A host who flags uncertainty earns more trust than one who fakes precision.
+ - Never present a back-of-the-envelope Idiot Index as a measured fact. Make the reasoning visible so the listener can follow it and judge it themselves.
+ - Never fabricate a quotation or attribute a specific claim to a named person or paper unless it is genuinely well known.
```

**`shows/prompts/first_principles_podcast.txt`** (prompt) — Mirrors the 'on the order of' ban that scored a hit; closes the magic-wand hole proven in Ep134–138. Adds explicit ban on copied Segment headers flagged by the density audit on 5/10 recent scripts. Shape ban + verbatim list; no new example phrase for the model to elect next.
```diff
- - Preserve the brief's hedging. If the brief says a figure is approximate, keep it approximate aloud, varying the hedging wording naturally. Never upgrade a hedged number into a hard fact. BANNED as a recurring on-air tic: the phrase "on the order of" — even when the brief uses it, hedge that figure in different natural words.
+ - Preserve the brief's hedging. If the brief says a figure is approximate, keep it approximate aloud, varying the hedging wording naturally. Never upgrade a hedged number into a hard fact. BANNED as recurring on-air tics — even when the brief uses them, re-hedge in different natural words: "on the order of"; "a rough magic wand estimate"; "a rough magic-wand estimate"; "rough magic-wand estimate"; and any near-clone that opens the floor with "a rough magic wand…". Name the magic-wand number as a concept; do not use that stock sentence stem.
+ - NEVER read brief section labels aloud. If the brief contains lines like "Segment 2 — Why It Costs What It Costs Today", "Segment 3 — The Magic Wand Number & The Idiot Index", "### Segment 4 — …", or other markdown/section headers, skip them entirely and continue in prose. Spoken output must not contain the words "Segment 2", "Segment 3", "Segment 4", or "Segment 5" as labels.
```

**`shows/prompts/first_principles_episode.txt`** (prompt) — Episode brief is upstream of the podcast stage; Track C arithmetic instructions still push the stock magic-wand estimate stem into the substrate the script copies. De-seed at source so 4.7 verbatim passes cannot re-elect it.
```diff
- Estimate the raw-material floor for this thing, reasoning out loud: name the major materials and their rough commodity values, add them up, and clearly flag every estimate AS an estimate.
+ Estimate the raw-material floor for this thing, reasoning out loud: name the major materials and their rough commodity values, add them up, and clearly flag every estimate AS an estimate. Vary the hedging wording each time — do NOT open with the stock stems "a rough magic wand estimate", "a rough magic-wand estimate", or "on the order of" (those calcified on air); name the magic-wand floor as a concept in fresh prose.
```

## Code/metadata-only proposals (no A/B needed)
- **`shows/prompts/first_principles_weekly.txt`** (prompt): Newsletter/recap surface; remove the same seeded phrases so weekly copy cannot reintroduce the on-air tic family. No audio path — ab_listen false.
- **`tests/test_first_principles_quality_pass.py`** (code): Every behavioral fix needs a drift-guard. Title fallback on Ep136/137 is P0 metadata; hedging + Segment-header bans need mechanical scoring next pass. Wiring through real committed artifacts, not stand-ins.

## Deferred (carried forward)
- OPERATOR DECISION (carry from Sep-17; urgency lower now that only 2/10 sit under 1400): accept grok narrative plateau and optionally lower min_podcast_words to a true thin-pass tripwire (~1100), OR invest in richer queue-brief substrate — do not attach another length prompt or re-enable podcast_expand_below_target
- Garbage auto-segment chapter body titles (shared network LLM-title class) — backlog only; Ep136/137 are title-field fallbacks handled as P0
- Further podcast-side length escalation / prompt word-floor pressure / podcast_expand_below_target — do_not_retry
- Reword stock closer if operator confirms written text causes Whisper 'depreciated' garble — no phonetic respelling (landmine #17)
- Optional code-side strip of markdown/Segment-N headers in narrative podcast scripts if the prompt ban misses next window
- Post-2026-10-24 X clip first-week download readout (monitor only)

## Drift-guard status
```
============================= test session starts ==============================
collected 16 items

tests/test_first_principles_quality_pass.py ................             [100%]

============================== 16 passed in 0.62s ==============================
```

<sub>tokens: 55969 in / 4786 out</sub>