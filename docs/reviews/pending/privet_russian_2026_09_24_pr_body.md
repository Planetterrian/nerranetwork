Aug-13 levers never shipped: 9/10 scripts still under 800 words, AI-disclosure tails remain Whisper-garbage, chapters still collapse (ep66/70 WOTD megachapters; Origins ~7s stubs), while WOTD/theme diversity holds and the secret-opener tic only partially faded without MEMORY.

_Generated on **grok-4.5** by `scripts/run_show_review.py` (replaces the Claude-Opus review agent). Estimated cost: **$0.1204**._

## Scored prior predictions
| Prediction | Verdict | Evidence |
|---|---|---|
| tts_word_count last 5 episodes vs min_podcast_words 800 | miss | ep66–70 words 699/987/690/635/636 (1/5 ≥800); Aug-13 section-band+digest-floor proposals never applied (ledger shipped: []) |
| want_to_know_a_secret opener rate in Word Origins (last 8 eps) | partial | ep61–63 still use secret-question Origins open; ep64–70 mostly required glue only; MEMORY de-seed never shipped so not a clean 0/8 hit |
| chapters with ≥6 pedagogical sections (Welcome/WOTD/Vocab/Grammar/Origins/Culture/Practice/Closing) | miss | ep66/70 WOTD megachapters (4–5 sections); ep61/62 Origins ~7s; only ~6/10 reach ≥6 titles — marker/glue proposals unapplied |
| spoken AI disclosure intelligibility (English, stable wording) | miss | ep61–70 tails still e-synth/person/Vypusk garble or RU credit paragraph; stable English line never shipped |
| Я есть / ungrammatical eat-construction in shipped _tts.txt | partial | no clear Я есть in ep61–70; ep70 correctly uses я ем; residual wrong forms (ep61 он купишь); code lint never shipped |
| off-theme магазин false-friend in Origins when магазин ∉ episode vocab | partial | ep63 travel Origins still drops magazine→shop filler; ep64–70 clear of that drop; on-list constraint unapplied |

## ⚠️ A/B-listen required — NOT applied (landmine #17)
These prompt/audio changes are **proposals only**. Apply them yourself, render/listen, then merge if they sound right.

**`engine/publisher.py`** (code) — P0.1: ep61–70 tails are listener-facing garbage; July+Aug deferred English disclosure still open. A/B-listen credit only (landmine #17).
```diff
- <current fixed AI/synthesis credit appended to privet_russian scripts — RU paragraph that Whisper+Olya render as e-synth/person/Vypusk garble>
+ Append one short stable English line only, e.g. "This episode's voice is AI-synthesized. Theme selection and teaching content are human-curated." — no RU disclosure paragraph on this EN-audience show. Single source of truth for the credit string.
```

**`shows/prompts/privet_russian_digest.txt`** (prompt) — P1.1 network length rule: digest-substrate levers only. Vague 'meaty' language already failed; countable floors match DP Pod digest arithmetic fix without podcast expand-retry.
```diff
- **LENGTH & COMPLETENESS RULE (CRITICAL):**
- Your episode plan must contain enough rich, detailed content across all required sections (especially a substantial Word of the Day + 8-12 vocabulary items + Grammar + Word Origins + Cultural Corner + Practice Challenge) to allow the downstream podcast script writer to produce a full, natural 900-1,200 word bilingual script. Do not produce thin or placeholder content. Every section must have concrete examples, sentences, and teaching value.
- 
- Select a theme and create the episode plan exactly as formatted above. Make every section meaty enough to support a complete, engaging 6-8 minute lesson.
+ **LENGTH & COMPLETENESS RULE (CRITICAL) — COUNTABLE FLOORS:**
+ Thin plans arithmetically cap the podcast under its 800-word floor. Every plan MUST meet all of:
+ - **Theme:** line present; theme not in the recent-themes list.
+ - **Word of the Day:** Cyrillic + transliteration + meaning + 1 correct example sentence + translation + memory hook + repeat-after-me prompt (no empty fields).
+ - **Vocabulary List:** 8–12 additional items, each with Cyrillic, transliteration, English, example sentence, translation, memory hook.
+ - **Grammar Spotlight:** concept in plain English + **at least 2 fully conjugated/agreeing example sentences** using today's words (never bare infinitive «есть» as “I eat”).
+ - **Word Origins:** 4–6 sentences on ONE on-list word; attested etymology only; one false friend/cognate from today's list (never stock «магазин» unless магазин is on today's list); fresh open/close — no fixed reveal-question template.
+ - **Cultural Corner:** 2–3 concrete sentences tied to today's theme.
+ - **Practice Challenge:** one kid activity + one adult real-life prompt naming at least 3 of today's words.
+ If any floor is missed, expand that section before finishing — do not ship placeholder bullets.
+ 
+ Select a theme and create the episode plan exactly as formatted above.
```

**`shows/prompts/privet_russian_podcast.txt`** (prompt) — P0.2+P1.1: current 35–48 sentence budget caps ~525–720 words under min 800; missing glue causes chapter collapse. Completeness bands + glue, not expand-retry or min_podcast_words raise.
```diff
- STRUCTURAL REQUIREMENTS: Each segment has a fixed sentence count (Word of the Day: 6-8, Vocabulary Builder: 15-20, Grammar Bite: 6-8, Culture Corner: 4-6, Practice Time: 4-6). Total: 35-48 sentences, producing a 6-8 minute episode.
+ STRUCTURAL REQUIREMENTS — ALL segments required every episode (missing Grammar/Origins/Culture/Practice is a failure). Sentence bands sized so a complete lesson can reach the show floor without padding: Word of the Day 8–10, Vocabulary Builder 20–26, Grammar Bite 8–10, Word Origins 8–10, Culture Corner 5–7, Practice Time 5–7. Speak substance (examples, repeats, one mini-dialogue) — never narrate word counts or 'padding' lines.
+ 
+ REQUIRED SPOKEN GLUE (say each once, natural prose — chapter markers depend on them):
+ - Grammar: include the words "quick grammar" or "grammar bite" once when the bite starts.
+ - Origins: include "something really cool about one of today's words" once (keep this exact phrase); never open with a secret/did-you-know question.
+ - Culture: start with a culture framing, not "did you know".
+ - Practice: include "practice" or "do you remember" once at the segment start.
```

**`shows/prompts/privet_russian_podcast.txt`** (prompt) — P0.4: ban-alone failed (ep61–63); closer formula still templated; off-list magazine on ep63. Shape-ban + MEMORY + on-list constraint; ledger successor-tic prediction.
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
+ [Word Origins — 60-90 seconds]
+ Expand the plan's Origins into a spoken story. Rules:
+ - MUST include the exact glue phrase "something really cool about one of today's words" once (chapter anchor). Vary the words around it.
+ - BANNED openers (verbatim or paraphrase): any secret-question ("want to know a secret…"), any did-you-know reveal-question, "language detective time", "hidden journey of this word" as a stock cold open — de-seed by SHAPE, not by swapping in a new catchphrase.
+ - BANNED closers (verbatim or paraphrase): "cousins with … they both come from …", "secret shortcut to remembering it forever", "that connection is your secret shortcut…".
+ - False friend/cognate MUST use a word from TODAY's taught list only — never drop stock «магазин»/magazine unless магазин is on today's list.
+ - Honor {origins_rotation_memory} when present: do not reuse listed recent openers/closers.
+ - Etymology must be attested or explicitly framed as a memory trick, never invented history.
+ - 8–10 sentences of real journey + gotcha + fresh memory hook. Keep energy playful.
+ {origins_rotation_memory}
```

**`shows/prompts/privet_russian_podcast.txt`** (prompt) — P1.2: ep70 'I am Olga', ep67 'I'm Olia' — identity drift in shipped audio.
```diff
- Olya is introduced ONCE by the fixed identity line right after the cold open (it already says "I'm Olya"). After that line, NEVER say her name again — the listener already knows who is speaking. Do not say "Olya here", "this is Olya", or refer to herself in third person, and do not add any additional greeting or self-introduction.
+ Olya is introduced ONCE by the fixed identity line right after the cold open (it already says "I'm Olya"). After that line, NEVER say her name again — the listener already knows who is speaking. Do not say "Olya here", "this is Olya", or refer to herself in third person, and do not add any additional greeting or self-introduction.
+ HOST NAME — NON-NEGOTIABLE: the host is only "Olya". NEVER write Olga, Olia, Olya Petrovna, Allia, or any other variant in the script (ep70 said Olga; ep67 Olia — both wrong).
```

## Code/metadata-only proposals (no A/B needed)
- **`engine/generator.py`** (code): P0.3: prompt-only missed twice on this show's core product (correct Russian). Deterministic code guard; ep63 still shows off-list magazine drop.
- **`shows/hooks/privet_russian.py`** (code): P0.4: verbatim ban already in podcast prompt and still missed ep61–63; network de-seed lesson = shape ban + MEMORY (DP Pod pattern).
- **`shows/privet_russian.yaml`** (config): P0.2: Culture `did you know` steals Origins; align markers with forced podcast glue; stop 7s Origins stubs and missing section titles.
- **`tests/test_privet_russian_quality_pass.py`** (code): Playbook: every behavioral fix gets a drift-guard test (tesla/mit/network quality_pass pattern).

## Deferred (carried forward)
- Operator: June-22 2026 double-publish (Ep046+Ep047) + June 26/28 skip forensics — still open from 2026-07-02 unless closed elsewhere
- Product: rss_language ru vs English-majority learner audience / podcast-directory filing — do not silent-flip
- Product: dedicated spaced-repetition review episode cadence beyond vocab_tracker callbacks
- Full written scope-and-sequence (CEFR-ish beginner path) outside vocab_tracker windows
- No podcast-side min_podcast_words raise / expand-below-target paraphrase retry (network length do_not_retry class)
- No phonetic respellings or speech-tag injection (landmine #17)
- Stop narrating plan-field labels ('The memory hook notes that…') — watch; not dominant in ep61–70
- Escalate length to operator-decision only if digest floors ship and last-5 ≥800 still misses on two subsequent scored passes — do not re-file identical podcast expand-retry a third time
- Growth: near-zero first-week downloads — distribution/discovery outside prompt scope this pass

<sub>tokens: 37498 in / 7566 out</sub>