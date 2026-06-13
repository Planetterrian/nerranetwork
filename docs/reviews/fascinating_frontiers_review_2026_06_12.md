# Fascinating Frontiers — Quality Review (June 12, 2026)

First scheduled-agent review of Fascinating Frontiers (FF). The June 10
four-show pass ([`docs/four_show_review_2026_06_10.md`](../four_show_review_2026_06_10.md))
covered FF among MIT/M&A/MAB; this pass scores that pass's length prediction
against the three episodes shipped since (Ep097–099) and attacks the next
tier. Snapshot: `scripts/review_snapshot.py fascinating_frontiers`.

/ TLDR /
- **The four-show length fix MISSED.** Ep097/098/099 (all generated *after*
  the pass) shipped 1634/1390/1637 words — all under the 1700 floor, all
  flagged `script_below_target: true`. Root cause is the **digest ceiling**,
  not the prompt target: FF fetches RSS *snippets* (title + summary, not full
  text) → the digest is ~1,300–1,600 words → the podcast can't exceed it
  without the padding/invention both prompts ban. Ep099's script (1664w) was
  already *longer* than its digest (1572w). The expand-retry fires every
  episode (correct) but plateaus. Documented + deferred (see P1-1); not
  re-litigated with more prompt pressure mid-A/B.
- **Shipped (code-only, no A/B):** (1) phonetic-garble repair extended to
  the space names the model spelled phonetically despite the ban —
  "En-sell-uh-dus" → Enceladus, "Tee-en-wen" → Tianwen; (2) theme-mining
  self-reference filter — the show's own name was mined as a top "recurring
  theme" every episode.

---

## P0 — listener-facing bugs shipping today

### P0-1. Phonetic-spelling leaks reach TTS verbatim *(shipped fix)*

The podcast-generation step spelled hard space names phonetically despite
the prompt's explicit ban (`shows/prompts/fascinating_frontiers_podcast.txt`
lines 12–13: "DO NOT attempt phonetic spellings"). These appear in the
`_tts.txt` (the text fed to TTS) but **not** in the source digest `.md`, so
the model introduces them at script-gen:

| Garble | Correct | Episodes |
|---|---|---|
| `En-sell-uh-dus` | Enceladus | Ep048, Ep088, Ep094 (recap reuse) |
| `Tee-en-wen-2` | Tianwen-2 | Ep090 (×2, incl. the Tomorrow Teaser) |

This is the exact failure class the June 10 prompt review built
`engine.utils.fix_phonetic_garbles` for ("nassa" shipped in FF Ep096) —
"bans alone don't stop a known finite failure set." The repair layer is
already wired into the podcast path (`run_show.py:2228`) but only knew
`nassa/nay-toe/chwen/en-vidia/open-ay-eye/star-mer`.

**Fix (`engine/utils.py`):** added `en-sell-uh-dus → Enceladus` and
`tee-en-wen → Tianwen` to `_PHONETIC_GARBLES`. Deterministic restoration of
the standard spelling the TTS handles natively (the regex's trailing `\b`
leaves the numeric suffix intact, so `Tee-en-wen-2 → Tianwen-2`). **No
audio-regression risk** — this is the opposite of adding a phonetic
respelling (landmine #17); it *removes* one. Guard:
`tests/test_fascinating_frontiers_quality_pass.py::TestPhoneticGarbleRepairSpaceNames`.

---

## P1 — quality ceiling

### P1-1. Chronic under-length — the four-show fix missed; the ceiling is the digest *(documented + deferred)*

Verified against the three episodes shipped since the four-show pass merged
(commit `882aff94`, June 10):

| Ep | Date | Script words | `script_below_target` |
|---|---|---|---|
| 097 | 06-10 | 1634 | true |
| 098 | 06-11 | 1390 | true |
| 099 | 06-12 | 1637 | true |

The four-show pass set `min_podcast_words: 1700` + `podcast_expand_below_target:
true` on the theory that "these floors are actually reachable by covering more
stories." The evidence says otherwise — **the four-show length prediction is a
MISS** (recorded in the ledger).

Root cause is *not* the prompt target — it's the digest:
- FF's sources are RSS feeds that return **snippets** (headline + 1–2 sentence
  summary), not full article text. The digest honestly reflects that: Ep090–099
  digests are 1027–1597 words for 15 stories (~85–100 words/story, ~4 terse
  sentences each), with `max_tokens: 5000` — nowhere near the token cap. The
  model isn't being truncated; the *source facts run out*.
- The podcast prompt targets 1,900–2,200 words but is told "Use ONLY
  information from the digest below — nothing else" (line 33). A 1,400-word
  digest cannot become a fact-dense 1,900-word script without padding (banned,
  lines 54–63) or invention (banned). Ep099's script (1664w) was already
  **longer than its digest** (1572w).
- So the expand-retry (`engine/generator.py:1832`, threshold = full target for
  FF) fires every episode, costs ~$0.03, and plateaus — there are no more
  source facts to add. On the thinnest news day in the window (Ep099, June 12:
  observing guides, city-satellite photos, a Moon–Mars pairing) the retry
  visibly padded instead: **6 stories ended with a clumsy title-case
  restatement of the digest headline** ("Sentinel-1 Radar Image Shows Buenos
  Aires Seasons through this multi-month composite approach"; "A waning crescent
  Moon pairs with Mars at dawn under these specific viewing conditions").
  Ep094–098 had zero such echoes — this is the retry-padding failure mode under
  the worst-case thin day, not an every-episode tic, so no standalone fix was
  shipped for it (it would over-fit one episode).

This is the same conclusion the First Principles review reached and the
operator accepted ("grok-4.3 plateaus, length ceiling accepted, not
re-litigated"). The genuine lever it flagged as "next" — the digest stage being
under-length — applies here too, but for a *news* show the right escape valve
is different.

**Deferred (recommendation, not shipped):** strengthen the **Cosmic Deep
Dive** — the one section the digest prompt explicitly licenses to use the
model's OWN astrophysics knowledge (digest line 56), not the snippet-bound
news. It is currently ~145–170 words in the digest (6–8 sentences) and gets
"90–120 seconds" in the podcast. Expanding it to ~12–16 sentences (digest) and
~150–180 s (podcast) is a non-padding, on-brand way to add ~200–300 words on
thin days — and the deep dive is the show's signature "blow their minds"
segment, so longer-but-substantive is plausibly *better*, not just longer.

**Why deferred rather than shipped now:** the operator is still A/B-listening
the four-show length change (2 days old; the pass itself says "A/B-listen the
next 2–3 episodes"). Layering a second length-oriented prompt change this week
would confound that A/B — exactly the churn the operating lesson warns against.
Ship the deep-dive lever as a *separate* change once the four-show A/B settles,
with a `--test` before/after pasted in the PR. If the operator prefers the
plateau accepted (per First Principles), the alternative is to align
`min_podcast_words` down to the real ceiling (~1,500) so the every-episode
`script_below_target` flag and the wasted retry stop — but that reverses a
floor set 2 days ago and is itself audio-affecting, so it is the operator's
call, not the agent's.

### P1-2. Theme-mining counted the show's own name as a top theme *(shipped fix)*

The June 10 four-show pass ported Tesla's theme-mining hardening
(narrative-prose echo filter, URL strip, idempotency, word-boundary program
detection) into `engine/show_memory.py` and scrubbed FF's history. It missed
the **show-name echo**: the digest *template header* repeats the show name
("# Fascinating Frontiers", "🚀 **Fascinating Frontiers** - Space & Astronomy
News"), so "fascinating frontiers" was mined as a bigram every episode and rose
to a top theme (count 22). Ep097/098/099 all produced an **identical** top-8
theme list led by `fascinating frontiers` →
`science nasa` → `nasa` → `launch` → `orbit` → `satellite`.

That list feeds `build_theme_context_block` → the `{narrative_memory_section}`
injected into the digest prompt as "RECURRING THEMES … deserving extra depth or
a connection back to the larger conversation." Telling the model its own name
is a recurring theme is nonsense guidance.

**Fix (`engine/show_memory.py`):** new `_self_reference_bigrams(cfg)` derives
the show-name bigram from `cfg.label`/`cfg.slug`; the mining loop and the
existing scrub loop both skip it. **Only the full multi-word name is
filtered, never component tokens** — "models"/"agents" remain legitimate themes
for Models & Agents (verified: `_self_reference_bigrams(models_agents)` does not
contain "models" or "agents"). FF's committed theme history was re-scrubbed
(top theme is now "dark matter"). Guard:
`tests/test_fascinating_frontiers_quality_pass.py::TestThemeSelfReferenceFilter`.

**Residual (deferred):** `science nasa` (count 18) survives — a generic
cross-sentence-boundary adjacency ("…space science. NASA announced…") and/or a
bare `science.nasa.gov` domain not behind an `https://` prefix that the URL
strip catches. Different mechanism, lower harm (it's at least topical), and
filtering it risks removing real content; left for a future pass.

---

## P2 — growth / discoverability

Verified already addressed by recent network work — **no action**:
- **X teaser is hook-led** (`run_show.py:4543`, network pass #575): FF leads
  with the episode hook + links the episode blog post, not the old
  date-only "Episode N: …" + generic summaries page.
- **Per-episode blog title** uses the unique hook (Phase 4).
- **RSS channel description** is a value-prop (set in the four-show pass).
- **Chapters**: snapshot reports 10/10 recent episodes have clean chapters;
  the `where: start|end` anchors + widened Closing pattern from the four-show
  pass are holding.
- **Banned deep-dive openers** ("you know what's fascinating", "blew my mind"):
  present only in pre-fix episodes (≤ Ep093); absent from Ep097–099.

---

## Findings checked and rejected / not actioned (for the record)

- **Headline-echo padding as an every-episode tic** — rejected as a standalone
  fix: 6 occurrences in Ep099, 0 in Ep094–098. It's the retry-padding failure
  mode under a worst-case thin news day (evidence for P1-1), not a recurring
  tic. A fix here would over-fit one episode; the real lever is the digest
  ceiling (P1-1).
- **Lowering `min_podcast_words` to the real ceiling now** — deferred to the
  operator: it would reverse a floor set 2 days ago and is audio-affecting.
- **Narrative tracker `last_major_update_episode: null` on every program** —
  noted in the four-show pass as an operator item (a curated status pass via
  `scripts/update_tesla_narrative.py --slug fascinating_frontiers`). Auto
  per-program freshness *is* advancing (Ep099 dates verified); the curated
  status text is an operator task, not a code bug.

## Shipped this pass

| Change | File | A/B needed? |
|---|---|---|
| Enceladus/Tianwen garble repair | `engine/utils.py` | No (deterministic) |
| Show-name theme-mining filter + FF re-scrub | `engine/show_memory.py`, `digests/fascinating_frontiers/fascinating_frontiers_theme_history.json` | No (context cleanup, removes noise) |
| Drift guards | `tests/test_fascinating_frontiers_quality_pass.py` | — |

## ⚠️ A/B-listen required (landmine #17)

**None.** Both shipped fixes are deterministic and strictly remove noise
(a phonetic garble; a nonsense theme). Neither adds a creative audio change.
The one audio-affecting recommendation (Cosmic Deep Dive expansion) is
**deferred**, not shipped.

## Tests

`pytest tests/test_fascinating_frontiers_quality_pass.py
tests/test_four_show_quality_pass.py tests/test_show_memory.py
tests/test_phase3_memory.py tests/test_network_quality_pass.py
tests/test_prompt_quality_pass.py tests/test_prompt_fidelity.py
tests/test_episode_validity.py tests/test_generator.py tests/test_utils.py`
— **267 passed**.
