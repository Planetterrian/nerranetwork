# SpaceX Daily — quality review (2026-06-13)

First scheduled review of **SpaceX Daily**, two days after launch (Ep1 + Ep2,
both produced 2026-06-13 — launch turbulence is documented in `shows/spacex.yaml`:
Ep1 double-ran and polluted the 7-day URL dedup, Ep2 was a thin Saturday).
The operator had already done a same-day mini-pass (commits `20886ed2`,
`68487c60`): the Ep2 **AI-chapter `A I` spacing** bug and the **AI-section
accuracy guardrail** (Colossus/Anthropic is real news in this timeline, not a
hallucination — do not relitigate) are both resolved. This review finds the
next tier.

Evidence: `shows/spacex.yaml`, all four prompts, `shows/hooks/spacex.py`,
`assets/pronunciation.py`, `engine/chapters.py`, `engine/show_memory.py`, both
episodes' digests + `_tts.txt` + Whisper transcripts + `chapters_ep00*.json`,
the trackers, `spacex_podcast.rss`, and `tests/test_spacex_show.py`.
`scripts/review_snapshot.py spacex`: ep1 1544w / ep2 1406w (both above the
1300 floor), $0.132/ep, no OP3 data yet.

## P0 — listener-facing bugs shipping today

None. The operator's same-day pass cleared the AI-chapter and AI-accuracy
issues; chapter shape is otherwise within tolerance on the two shipped
episodes. (Two P1 quality items below ship in audio but are not failures.)

## P1 — quality ceiling

### 1. Theme miner mines source-attribution labels → "google spacex" is the #1 "theme" (SHIPPED)
`engine/show_memory.update_theme_history_from_digest` stripped bare URLs
before mining but **not** the markdown source-link LABEL. Digests format every
source as `Source: [Google News](https://…)`; after the bare-URL strip the
label `Google News` survived and the repeated source name paired with the next
story's first word into junk bigrams. `digests/spacex/spacex_theme_history.json`
shipped with **`"google spacex": 6`** as the single highest-weighted recurring
theme (verified: `google spacex` counted 2× in Ep1's digest, 4× in Ep2's),
ahead of every real theme (`full flow`, `staged combustion`, `idiot index`…).
That polluted top theme feeds `{narrative_memory_section}` into the prompts.

This is the **same class** as the network theme-pollution bugs prior passes
fixed (Tesla "open questions" ×112; the June network pass's `_THEME_STOPWORDS`).
The bare-URL strip was the documented fix then — it just didn't cover the
markdown-link form. **It is latent on every memory show:** Fascinating
Frontiers carries `science nasa` / `nasa` (from `[nasa.gov]`), Models & Agents
carries `reddit localllama` (from `[reddit.com]`).

**Fix:** strip the whole `[label](url)` construct before mining, then bare
URLs (`engine/show_memory.py`). Confirmed it removes 100% of `google`-bigrams
from both SpaceX digests and leaves real themes intact (`elon musk`, `staged
combustion`…). Real in-content mentions (e.g. "NASA" spoken in a story) are
unaffected — only the source-label inflation is removed. Rebuilt
`spacex_theme_history.json` clean via the fixed miner (the one-time
stopword scrub doesn't catch `google`, so the existing file was regenerated).
Sibling histories left to re-balance naturally as clean episodes accumulate.
Drift guard: `test_theme_mining_strips_source_attribution_labels`.

### 2. Rocket-thrust unit "tf" spoken letter-by-letter as "T F" (SHIPPED)
Ep2 `_tts.txt`: "Thrust now exceeds **280 tf**…" and "…survives the thermal
environment at **280 tf**." The Whisper transcript rendered both as
"**280 TF**" — i.e. the audio said "tee eff". `tf` (tonne-force, the standard
unit for rocket-engine thrust) is not in `UNIT_ABBREVIATIONS`, so it reached
Grok TTS and was read as letters. On an engineering-first show where thrust is
core content, this recurs whenever the model copies `tf` from a source headline
(Ep2 took it from the Raptor-3 MEXC piece).

**Fix:** a per-show `pronunciation_overrides()` in `shows/hooks/spacex.py`
(the existing `run_show._apply_pronunciation` mechanism) expanding
`tf → tons-force`. This is a **unit expansion** (the `km→kilometers` class),
NOT a phonetic respelling — outside the landmine #17 ban. Scoped to SpaceX
(no shared-module change), whole-word/case-insensitive, verified not to touch
`software`/`lift`. Drift guard: `test_tf_thrust_unit_expanded_for_tts`.
⚠️ Audio-affecting — A/B-listen (landmine #17).

## P2 / deferred (recommendations, not shipped)

- **SPCX price spoken twice every episode.** The dedicated Market Watch
  segment speaks the price (podcast prompt lines 93–94) AND the code-supplied
  closing block appends a price sentence (`shows/hooks/spacex.py`
  `_price_sentence`). Result: Ep1 "SPCX is at $160.95 … [≈15s] … SPCX closed
  at $160.95"; Ep2 identical. Redundant, and over-weights the stock on a show
  whose stated principle is "engineering first, the stock is the quiet thread."
  **Deferred because the obvious fix is not cleanly safe:** removing the price
  from the *closing* breaks three intended/tested behaviours
  (`test_price_sentence_*`, `test_closing_rotates_by_date`); removing it from
  the *Market Watch* spoken segment risks a chapter regression — with no
  earlier "Market Watch" match, the closing's "S P C X **closed** at…" would be
  grabbed by the Market Watch marker (`S ?P ?C ?X (closed|…)`, listed before
  Closing) and the episode would ship with no Closing chapter (the orphan-
  closing class). A correct fix needs to reorder the Closing marker ahead of
  Market Watch (so `where: end` Closing wins the sign-off line) *and* drop the
  Market Watch spoken price — a coupled change worth its own A/B pass. Lever
  recorded for the next review.

- **Chapter lumping: "AI & Compute" swallows trailing Top News.** Now that
  today's `a ?i` marker fix lets "On the A I front" match, a fresh parse of
  Ep2 puts 662 words (the lawsuits, the Fish & Wildlife suit, the LandSpace
  item, the grid-fin and Boca-Chica buzz) under the **AI & Compute** chapter,
  because the LLM emitted those news items *after* the AI marker rather than
  before the Counterpoint/AI/Engineering editorial block. Root cause is
  section-ordering adherence, not the markers. The marker fix is brand-new
  (Ep3 is the first normal episode to even have an AI chapter), so **observe
  Ep3+ before touching the prompt.** Lever: reinforce in the podcast prompt
  that ALL Top News + Community Buzz come before the three editorial segments,
  never interleaved. The next review scores whether the lump recurs.

- **Cold-open hook leads with unglossed jargon.** Ep2's first spoken content
  line: "…cut the **Idiot Index** on each engine" — the system prompt's own
  "never use jargon without a plain-language gloss on first use" rule, violated
  in the very first sentence. The Engineering Deep Dive later glosses it; the
  hook does not. n=1; watch whether the digest HOOK keeps front-loading the
  First-Principles terms.

- **Tomorrow-teaser tic.** Both episodes opened the teaser "watch for the
  first …" (Ep1 "first quarterly filing", Ep2 "first integrated test"). n=2;
  monitor for a dead-rotation pattern.

- **Ep1 Engineering Deep Dive was thin** (51s chapter, no magic-wand / Idiot
  Index reasoning) — but Ep1 is the one-time IPO-debut episode with a
  non-standard structure; not generalizable.

## Hard guardrails honored
No R2/RSS-enclosure changes, no MP3s, no `min_articles_skip` default change, no
TTS-coupled-field flips, no voice/provider changes, no phonetic respellings
(the `tf` fix is a unit expansion), no posting/sending/uploading/paid APIs.

## Tests
`tests/test_spacex_show.py` (44), `tests/test_network_quality_pass.py` (32),
`test_show_memory.py`, `test_phase3_memory.py`, `test_prompt_fidelity.py`,
`test_episode_validity.py`, `test_generator.py`,
`test_four_show_quality_pass.py`, `test_fascinating_frontiers_quality_pass.py`
— all pass (254 total).
