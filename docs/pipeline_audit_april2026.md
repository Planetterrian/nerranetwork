# Nerra Network — Pipeline Audit (April 2026)

**Date:** 2026-04-11
**Trigger:** Round 4 task list — production bugs (metadata narration,
repetition loops, intra-episode story duplication, TTS phonetic artifacts,
AI-review false positives).
**Scope:** Full generation pipeline — prompts, generator, validation,
fetcher, content tracker, slow news, TTS, publisher, workflows.

This document captures what was fixed in this pass and what remains as
follow-up. Fixes referenced here are committed on `main` alongside this
file unless noted.

---

## Fixes applied in this pass

### P0-1 — Metadata narration in podcast scripts
- **Finding:** Every podcast prompt embedded word counts, sentence counts,
  and segment length targets in the main body (e.g.
  `shows/prompts/modern_investing_podcast.txt:7-15`). The LLM occasionally
  echoed those guardrails back as narration.
- **Fix:**
  - Prepended a `[PRODUCTION NOTES — DO NOT READ ALOUD]` block to all 10
    `*_podcast.txt` and all 10 `*_digest.txt` prompts. The block makes the
    never-narrate rule the very first instruction the LLM sees.
  - Added `_strip_metadata_from_script()` in `engine/generator.py`.
    It runs as the first step of `_sanitize_podcast_script()` and strips
    `[PRODUCTION NOTES ... [END PRODUCTION NOTES]` blocks, orphan
    `DO NOT READ ALOUD` markers, `N words / N sentences / script length`
    references, and stand-alone `Segment N:` labels.
  - Added a parallel `prepare_text_for_tts()` strip in `engine/tts.py` so
    any leak that slips past the generator is still caught before
    ElevenLabs sees the text.

### P0-2 — LLM repetition loops
- **Finding:** Three episodes on 2026-04-11 hit phrase-level repetition
  loops (`"the kind of" x5`, `"worth considering is" x5`,
  `"chwen three point" x5`). Existing repetition detection in
  `_validate_llm_output` only emitted warnings.
- **Fix:** Added public `detect_phrase_repetition()` in
  `engine/validation.py`. Sliding n-gram window (3..6 words), allowlist of
  common English phrases, severity `critical` at 6+ occurrences and
  `warning` at 4-5. Substring-of-longer-phrase suppression prevents a
  single loop from surfacing as many redundant reports.
- Wired into `generate_podcast_script()` after the initial generation. On
  a `critical` hit the pipeline issues one retry with an explicit
  anti-repetition suffix listing the offending phrases. Guards ensure we
  don't swap to a drastically shorter retry.

### P0-3 — Intra-episode story duplication
- **Finding:** Tesla Ep433 had the Semi factory tour and Dutch FSD
  approval each covered twice with near-verbatim phrasing across
  different digest sections. `check_within_episode_duplicates()` already
  caught this at 60% similarity but only warned.
- **Fix:**
  - Added `ABSOLUTE RULE — ZERO STORY OVERLAP` to the digest
    production-notes header (applied to all 10 digest prompts).
  - Added `_strip_duplicate_stories()` in `engine/generator.py`. Splits
    a digest into `\n\n`-separated blocks, compares non-adjacent pairs at
    0.60 similarity via `calculate_similarity()`, and drops the later
    occurrence. Called at the end of `generate_digest()` so the podcast
    script generator never sees the duplicate.
  - Made near-verbatim duplicates blocking in `run_show.py`: the post
    `validate_digest` check now parses `"similarity N%"` out of each
    `Duplicate within` issue and calls `sys.exit(2)` if any reach 80%.
    The 60% warning behaviour is unchanged.

### P1-4 — TTS phonetic artifacts + pronunciation map
- **Finding:** April-11 transcripts included `"nassa"`, `"nay-toe"`,
  `"star-mer"`, `"chwen three point"`. These are LLM-generated phonetic
  respellings triggered by prompt instructions like "spell out
  abbreviations". The audio was fine — ElevenLabs pronounces the standard
  forms correctly — but the transcripts were cosmetically wrong.
- **Fix:**
  - New `PRONUNCIATION GUIDE` section in every podcast prompt header:
    keep acronyms and proper nouns in standard written form, expand on
    first use only, never write phonetic respellings.
  - New `shows/pronunciation_map.yaml` (starts empty — add entries only
    when a mispronunciation is confirmed on the production voice/model).
  - New `prepare_text_for_tts()` in `engine/tts.py` loads the map,
    applies whole-word case-insensitive substitutions, and doubles as a
    final metadata stripper. Hooked into `speak()` before chunking.

### P1-5 — Daily review false positives
- **Finding:** The AI reviewer flagged `"Trump as president with Vance
  as VP"` as a factual error (correct for 2026 but contradicted the
  model's pre-2024 training data). The same review run also reported
  TTS phonetic artifacts as factual errors, inflating the critical count.
- **Fix:**
  - Expanded the review prompt in `review_episodes.py` with an explicit
    "CURRENT-REALITY GROUNDING (as of 2026)" block naming the current US
    President, VP, and UK PM, and instructing the reviewer to trust
    content consistent with current reality even when it contradicts
    pre-2024 training data.
  - Added `flag_tts_artifacts()` plus a `check_tts_artifacts()` runner.
    Known phonetic respellings (nassa, nay-toe, star-mer, chwen, etc.)
    are now reported at `info` severity rather than inflating the
    factual-error warning count.

---

## Comprehensive audit (P2-6)

### 6a — Prompt templates
- **Coverage:** all 11 shows have system / digest / podcast / weekly
  prompts.
- **Length metadata:** After the P0-1 header pass, every podcast prompt
  still contains word/sentence/minute references inside the main body
  (they were left in place rather than surgically relocated to avoid a
  high-risk 20-file rewrite). The prepended production-notes block +
  post-generation strip covers the risk. Follow-up: a later cleanup pass
  can move legacy length references into a single structured block per
  file.
- **Anti-duplication:** Podcast prompts like `tesla_podcast.txt` already
  include strong "NEVER retell a story" language. Digest prompts now also
  carry `ABSOLUTE RULE — ZERO STORY OVERLAP` via the prepended header.
- **Pronunciation:** Previously only the modern_investing prompt had a
  detailed pronunciation section; all 10 podcast prompts now share a
  standardised `PRONUNCIATION GUIDE` via the header.
- **Intro/outro references:** Not re-audited in this pass — no reported
  regressions.

### 6b — Generator pipeline (`engine/generator.py`)
- **Prompt assembly:** `load_prompt` uses `str.format_map`, which raises
  `KeyError` on missing keys and is safe with our placeholder set
  (`{episode_num}`, `{digest}`, `{intro_line}`, `{closing_block}`,
  `{hook}`, `{tone_hint}`, `{today_str}`). The new header contains no
  curly braces so it does not interact with `format_map`.
- **Retry logic:** `generate_digest()` has a 3-level refusal recovery
  (anti-refusal suffix → educational fallback → fallback model) and a
  separate repetition retry. `generate_podcast_script()` has refusal
  recovery, length-expansion retry, legacy repetition retry, and now the
  new P0-2 anti-repetition retry. None of the retry branches reuse
  metadata-leaky prompts.
- **Error handling:** LLM errors propagate as `LLMRefusalError` or
  transient-retryable errors; partial scripts are guarded by the
  `< len(text) * 0.5` swap guards in retries.
- **Token limits:** `podcast_max_tokens` is read per-show with fall-back
  to `max_tokens`; truncation triggers a 1.5x retry. Not changed.
- **Two-stage generation:** `podcast_chain` path prepends the outline and
  then goes through the same sanitizer/repetition detection.

### 6c — Fetcher pipeline (`engine/fetcher.py`)
- **RSS parsing:** Uses `feedparser`, which handles Atom / RSS 1.0 / RSS
  2.0 uniformly.
- **Error handling:** Per-feed `try/except` already wraps individual
  feed failures. Summary logging from Round 3 shows attempted /
  successful / failed counts.
- **Timeout:** 15s per feed via the shared `DEFAULT_HEADERS` path in
  `audit_feeds.py` and the `requests.get` calls in `fetch_rss_articles`.
- **Keyword matching:** Case-insensitive and substring-based; no change.
- **Source attribution:** `_SOURCE_MAP` now covers Google News + 17
  Reddit subreddits + the pre-existing per-domain list. A quick sweep of
  `shows/*.yaml` did not surface any new domains without a mapping.
- **X/Twitter:** `fetch_x_posts` handles per-account errors in a
  `try/except` and logs a total at the end.
- **Article dedup:** `remove_similar_items()` uses 0.85 by default. Not
  changed — the April-11 failures were intra-episode digest duplicates,
  not article-level false negatives.

### 6d — Content tracker (`engine/content_tracker.py`)
- **14-day window:** `_prune_old_episodes` runs in `record_episode`.
  Spot-checked `content_tracker.py:743` — still correct.
- **Section regexes:** Per-show patterns live in `SECTION_PATTERNS`.
  They are used both for write (episode records) and read (recent
  headlines). Prompt header changes did not touch the section header
  strings, so regexes remain valid.
- **Similarity threshold:** `calculate_similarity()` default 0.72 for
  cross-episode checks. Not tuned in this pass.
- **File locking:** Existing JSON writes go through the atomic-write
  helper. No observed corruption.

### 6e — Slow news (`engine/slow_news.py` + `shows/segments/*.json`)
- **Segment count:** Every show has a segment library, but each library
  contains **14 segments** — well below the "50+ segments" target called
  out in the task brief. This is a content-authoring follow-up, not a
  code bug.
- **Cooldown:** `slow_news.select_segments` already accepts and applies
  `covered_topics` from the content lake (wired in Round 3).
- **Thresholds:** `min_articles_skip` is per-show in YAML.
- **Quality spot-check:** Out of scope for an automated audit.

### 6f — TTS and audio (`engine/tts.py`, `engine/audio.py`)
- **Chunking:** Sentence-aware splitter in `chunk_text` preserves word
  boundaries.
- **API errors:** `speak_chunk` distinguishes 4xx (non-retryable,
  raises `ElevenLabsClientError`) from 429/5xx (retryable); the model
  fallback chain in `_MODEL_FALLBACKS` is triggered only on 4xx.
- **Text prep:** `prepare_text_for_tts()` now runs before chunking.
- **Audio mixing:** Not changed in this pass.

### 6g — Publishing (`engine/publisher.py`)
- Not changed in this pass. RSS GUID dedup and X character limits were
  not reported as regressions on 2026-04-11.

### 6h — Workflows (`.github/workflows/*.yml`)
- **Cron schedules:** `run-show.yml` has 12 cron entries handling the
  per-show gate, including weekday-only slots and 2-day-parity slots.
  Concurrency controls remain unchanged.
- **Feed audit:** `feed-audit.yml` runs weekly at Sun 12:00 UTC (added
  in Round 3).
- **Daily review:** `daily-review.yml` runs at 12:00 UTC; now receives
  both the 2026-grounded prompt and the TTS-artifact triage from P1-5.

---

## Remaining follow-ups (not addressed in this pass)

1. **Segment libraries are ~14 per show.** Expanding each to 50+ is a
   content-authoring task and should be scheduled separately.
2. **Legacy length references inside podcast prompt bodies.** The P0-1
   header is the active guardrail; later we can do a surgical pass to
   move all word/sentence/minute references into a single
   `[PRODUCTION NOTES]` block and remove them from the main body.
3. **Remove unused `digests/*.py` legacy scripts** (deprecated per
   CLAUDE.md but still in the tree).
4. **Pronunciation map starts empty.** Populate only after a confirmed
   mispronunciation on the production voice/model — the TTS engine
   handles the standard written forms correctly.

## Verification

- `pytest` — **1093 passed, 2 skipped** (no regressions).
- Smoke tests for new functions (`detect_phrase_repetition`,
  `_strip_metadata_from_script`, `_strip_duplicate_stories`,
  `prepare_text_for_tts`, `flag_tts_artifacts`) — all green.
- No end-to-end episode run was executed from this audit; any dry-run
  against live LLM/TTS should use `--test --skip-x` first.
