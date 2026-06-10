# Russian Shows Quality Review — Финансы Просто + Привет, Русский! (June 10, 2026)

Same review-then-fix process as the Tesla (#576) and four-show (#577) passes,
applied to the two Russian shows. Drift guards:
`tests/test_russian_shows_quality_pass.py`. As with #577, all audited episodes
(FP Ep45–49, PR Ep32–36, June 2–8) predate the June 9 evening merges, so
"expand-retry not firing" / "tips shortfall" findings are pre-fix artifacts.

## Fixed in this pass

### 1. English AI disclosure spoken on the Russian voice (the known wart)
Every FP/PR episode ended with *"This episode used AI voice synthesis of my
voice…"* in English on the Olya voice — flagged as an operator item in two
prior network reviews. `run_show.py` now defines `_AI_DISCLOSURE_RU` +
`_AI_DISCLOSURE_RSS_RU` and gates all three injection points (spoken script,
per-episode RSS description, channel description) on `_RUSSIAN_SHOWS`.
**Changes shipped audio — A/B-listen per landmine #17.**

### 2. Mixed-language episode titles
"Финансы Просто - Episode 49" / "Ep 48: Сегодня разберёмся…" — the Russian
feeds now title episodes "Выпуск 49: …" (hook path and no-hook fallback).

### 3. Closing chapters + rotation (the Tesla bug class)
- FP's second closing variant ("Вот и всё на сегодня!") matched no pattern →
  the closing got an auto-segment fragment title (verified Ep48). Pattern now
  covers it; Приветствие/Завершение carry `where: start/end` anchors.
- PR had **one** closing — identical sign-off on every episode ever. Pool now
  rotates 3 variants, each pinned to match the Closing pattern.
- Both shows' under-matching mid-section patterns broadened to phrases the
  natural scripts actually speak (FP: "сегодня разберёмся", "первый совет",
  "как это устроено"; PR: "let's build more", "little grammar", "story
  behind") — recent episodes were losing 3–4 of their 6–8 chapters to the
  fallback segmenter.

### 4. Word floors raised to make the expand-retry meaningful
- FP: 900 → **1000** (prompt targets 1,300–1,700; floor deliberately NOT at
  the prompt's low end — the 60% skip line stays at 600, under the worst
  recent raw output of 645 words, so an episode still ships even if the
  retry fails entirely).
- PR: 650 → **800** (prompt targets 900–1,200; the explicit
  `min_podcast_word_floor: 550` ship floor is kept).

### 5. Привет, Русский! vocabulary memory (new: `engine/vocab_tracker.py`)
The show's biggest pedagogical gap: vocabulary was taught in complete
isolation — words never reappeared, and themes repeated back-to-back
(Animals ran Ep33/34/35) because nothing remembered what had been taught.
New lightweight memory, the show's equivalent of the narrative-memory
engines:
- `post_generate` (new `shows/hooks/privet_russian.py`) mines the episode's
  taught Cyrillic vocabulary (frequency ranking after a Russian
  function-word filter — verified to recover космос/звезда/ракета and
  яблоко/хлеб/молоко from real episodes) into
  `digests/privet_russian/vocab_taught.json`, idempotent per episode.
- `pre_fetch` composes `{vocab_review_section}`: 2–3 words due for a spoken
  spaced-repetition callback (taught ≥2 episodes ago, oldest first) plus a
  recently-taught DO-NOT-RETEACH list that also forces theme rotation.
- Placeholder added to both PR prompts; `run_show.py` setdefaults the key on
  both the digest and podcast paths so a hook failure can never KeyError.
  Empty history composes to an empty string — a true no-op until data
  accrues.

### 6. Stale TTS claim in the PR prompt
"This script is synthesized by AI text-to-speech **in English**" — false
since the May 2026 Olya-voice migration (and the scripts already write
Cyrillic). Now: "synthesized by a bilingual AI voice (Russian + English);
write Russian words in Cyrillic with pronunciation guidance nearby" —
matches what recent episodes already do.

## Checked and rejected

- **"RSS feed missing"** (PR) — the agent looked in `digests/privet_russian/`;
  `privet_russian_podcast.rss` lives at the repo root like every feed.
- **FP tips shortfall / both shows' under-target word counts** — all audited
  episodes predate #575's "3–4 tips" requirement and the expand-retry flag;
  the digest-carrying retry from #576 applies network-wide. Verify the next
  even-day episodes (June 10/12).
- **FP "Главная тема" missing because writers don't speak labels** — partially
  true; addressed by pattern broadening rather than forcing the host to
  announce section headers (which the prompts deliberately avoid).

## Operator items
- A/B-listen the next FP/PR episodes: localized disclosure, PR closing
  rotation, PR vocab-review callbacks, and the raised length targets all
  change shipped audio (landmine #17).
- The vocab tracker starts empty — review callbacks begin once two episodes
  have been recorded (≈June 14).
