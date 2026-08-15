Prior curriculum fixes hit (themes/WOTD diversity), but every recent episode still ships under-length, banned Word-Origins tics, thin/mis-marked chapters, residual ungrammatical Russian, and a garbled spoken AI-disclosure tail.

_Generated on **grok-4.5** by `scripts/run_show_review.py` (replaces the Claude-Opus review agent). Estimated cost: **$0.1085**._

## Scored prior predictions
| Prediction | Verdict | Evidence |
|---|---|---|
| distinct themes across the next 8 episodes | hit | ep56–65 themes School/Feelings/Animals/Weather/Food/Shopping/Nature/Travel/Home/Clothing = 10 distinct (expected ≥6) |
| repeated Word-of-the-Day within any 12-day span | hit | WOTDs школа/счастливый/собака/солнце/яблоко/магазин/дерево/путешествие/дом/одежда — zero repeats in window |
| share of taught word-slots that are NEW words | partial | Theme-gap forces mostly new lists, but transcripts still reteach/callback high-frequency items (мышь/кот, фрукты, летает, большая) inside builder segments |

## ⚠️ A/B-listen required — NOT applied (landmine #17)
These prompt/audio changes are **proposals only**. Apply them yourself, render/listen, then merge if they sound right.

**`shows/prompts/privet_russian_podcast.txt`** (prompt) — Verbatim ban alone failed (7/10 still use the secret question). Shape-ban + on-list word constraint + rotation MEMORY matches network de-seed lesson; keeps chapter glue phrase.
```diff
- [Word Origins — 60-90 seconds]
- If the episode plan has a "Word Origins" section, this is your "language detective" moment. Expand it into a fun spoken story that makes the word unforgettable:
- - Transition in with "…something really cool about one of today's words" (keep that phrase — it anchors the chapter marker), but vary the sentence around it each episode. BANNED as a verbatim transition: "Want to know a secret about [word]?" — that exact question has opened this segment in 9 of the last 10 episodes and listeners hear the template.
- - Deliver the surprise connection with enthusiasm, in FRESH words each episode — never the same reveal question two episodes running (the verbatim "Did you know that [X] and [Y] are actually the same word?" has become a template).
- - Tell the word's journey like a mini-adventure story — keep it light and fun.
- - Include the false friend or cognate as a playful "gotcha!" moment.
- - Close with the memory trick — give listeners a shortcut they'll actually remember.
- - Keep the energy playful and delighted — this should feel like sharing a fun discovery with a friend.
- Target: 60-90 seconds of audio.
+ [Word Origins — 60-90 seconds · 8-10 short sentences]
+ If the episode plan has a "Word Origins" section, this is your "language detective" moment. Expand it into a fun spoken story that makes ONE word from TODAY's vocabulary list unforgettable (never a word that is not on today's list).
+ - Transition in with a sentence that CONTAINS the exact glue phrase "something really cool about one of today's words" (chapter anchor). Build a fresh sentence around that glue each episode.
+ - BANNED openers / shapes (do not paraphrase into the same move): any "want to know a secret…" question; any "Did you know that X and Y are actually the same word/cousins?" reveal; any closing of the form "remember it's cousins with … they both come from … secret shortcut … forever".
+ - BANNED filler: do NOT drag in the магазин/magazine false-friend unless магазин is on today's vocabulary list. Pick a false-friend or cognate that belongs to TODAY's word.
+ - Do NOT reuse an opener or closer from the recent Origins MEMORY block below when present.
+ - Trace a verifiable journey (or clearly label a mnemonic as a memory trick, never as history).
+ - Keep energy playful; 8-10 short sentences; 60-90 seconds.
+ {recent_origins_memory}
```

**`shows/prompts/privet_russian_podcast.txt`** (prompt) — Same arithmetic-cap fix class as DP Pod section floors: current bands cannot reach min_podcast_words. Glue lines fix missing Grammar/Origins/Culture chapters without TTS hacks.
```diff
- STRUCTURAL REQUIREMENTS: Each segment has a fixed sentence count (Word of the Day: 6-8, Vocabulary Builder: 15-20, Grammar Bite: 6-8, Culture Corner: 4-6, Practice Time: 4-6). Total: 35-48 sentences, producing a 6-8 minute episode.
+ STRUCTURAL REQUIREMENTS: Each segment has a fixed sentence count chosen so the spoken script can clear ~800+ words without padding (prior 35-48 sentence budget arithmetically capped episodes at ~600-700 words). Word of the Day: 8-10. Vocabulary Builder: 22-28. Grammar Bite: 8-10. Word Origins: 8-10. Culture Corner: 5-7. Practice Time: 5-7. Total body ~56-72 short sentences plus the fixed identity line and closing_block — aim 6-8 minutes / 900-1200 words. Never narrate these counts aloud.
+ 
+ SECTION GLUE (say each once, naturally, so chapters mark): after identity, teach WOTD; open builder with a "let's build more" / "let's learn more" line; open grammar with "grammar bite" or "quick grammar"; open origins with the required "something really cool about one of today's words" glue; open culture with "culture corner" or "fun fact"; open practice with "practice time".
```

**`shows/prompts/privet_russian_digest.txt`** (prompt) — Network length rule: digest-substrate levers only. Countable floors beat vague 'meaty' language that already failed.
```diff
- **LENGTH & COMPLETENESS RULE (CRITICAL):**
- Your episode plan must contain enough rich, detailed content across all required sections (especially a substantial Word of the Day + 8-12 vocabulary items + Grammar + Word Origins + Cultural Corner + Practice Challenge) to allow the downstream podcast script writer to produce a full, natural 900-1,200 word bilingual script. Do not produce thin or placeholder content. Every section must have concrete examples, sentences, and teaching value.
+ **LENGTH & COMPLETENESS RULE (CRITICAL):**
+ Your episode plan is the ONLY substrate for a 900-1,200 word bilingual script — thin plans are why recent episodes shipped at ~650 words. Countable minimums (failure if any missed):
+ - Word of the Day: ≥6 bullet fields filled (Cyrillic, transliteration, meaning, example RU, example EN, memory hook, repeat prompt).
+ - Vocabulary List: 8-12 items BEYOND WOTD; every item has Cyrillic + transliteration + English + example sentence + translation + memory hook (no bare rows).
+ - Grammar Spotlight: concept + ≥3 full example pairs (RU+EN) using today's words; verbs conjugated for subject.
+ - Word Origins: 4-6 sentences on ONE word from today's list only; attested etymology or explicit mnemonic label; no stock магазин digression unless that word is on the list.
+ - Cultural Corner: 3-5 sentences tied to theme.
+ - Practice Challenge: kid activity + adult activity, each naming ≥3 of today's words.
+ Do not produce placeholder content. Never narrate these minimums in the plan body.
```

**`engine/publisher.py`** (code) — July deferred English AI disclosure; current tails are listener-facing garbage on an EN teaching show. A/B-listen credit only.
```diff
- (wherever the fixed end-credit / AI disclosure is appended for privet_russian — currently yields RU paragraph that Olya-voice renders as unintelligible English in ep56,59,60,62,64,65 transcripts)
+ For privet_russian (English-speaking learner audience), append one stable English credit only, e.g.:
+ "This episode's voice is AI-synthesized. Theme selection and teaching content are human-directed."
+ Do not use the long Russian disclosure paragraph on this show. Keep identical wording every episode for TTS stability.
```

## Code/metadata-only proposals (no A/B needed)
- **`shows/hooks/privet_russian.py`** (code): Data-side rotation memory for Origins openers/closers — prompt-only ban already missed; same pattern as DP Pod lever memory.
- **`engine/generator.py`** (code): Prompt grammar rules shipped and still missed (Ep060 class). Code lint is deterministic P0 guard; no phonetic/TTS landmine.
- **`shows/privet_russian.yaml`** (config): Align markers with forced glue; stop 'did you know' stealing Culture/Origins boundaries; ep59 WOTD megachapter / 7s Origins stubs.
- **`tests/test_privet_russian_quality_pass.py`** (code): Playbook: every behavioral fix gets a drift-guard test.

## Deferred (carried forward)
- Operator: June-22 2026 double-publish (Ep046+Ep047) + June 26/28 skip forensics — still listed open from 2026-07-02 ledger unless closed elsewhere
- Product: rss_language ru vs English-majority learner audience / podcast-directory filing — do not silent-flip
- Product: dedicated spaced-repetition review episode cadence beyond vocab_tracker callbacks
- Full written scope-and-sequence (CEFR-ish beginner path) outside vocab_tracker windows
- No podcast-side min_podcast_words raise / expand-below-target paraphrase retry (network length do_not_retry class)
- No phonetic respellings or speech-tag injection (landmine #17)
- Stop narrating plan-field labels ('The memory hook notes that…') — July deferred; not re-observed as dominant in ep56-65 evidence sample, keep watching

<sub>tokens: 32600 in / 7225 out</sub>