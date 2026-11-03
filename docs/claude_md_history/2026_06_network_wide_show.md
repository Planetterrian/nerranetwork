# Network-wide show quality pass (June 2026)

Moved verbatim from CLAUDE.md on 2026-11-03; the rules that still bind are summarised there.

### Network-wide show quality pass (June 2026)

After the Tesla (#573) and Modern Investing (#574) flagship passes, the
same review ran across the other ten shows. Drift guards:
`tests/test_network_quality_pass.py`.

- **`engine/show_memory.py` inherited both Tesla memory bugs** (it was
  generalized from `tesla_memory` *before* the fixes). Theme mining read
  the narrative TEMPLATE every episode — "open questions" hit count 96 on
  Models & Agents, Fascinating Frontiers, AND Planetterrian — now
  digest-only with the shared `_THEME_STOPWORDS`; the three live histories
  were scrubbed. Narrative trackers were seeded May 29 with no program
  ever updated; `auto_update_narrative_from_digest` (ported from Tesla)
  now advances per-program "last covered on air" freshness each episode
  via `memory_post_generate`, and the status block gained the
  make-continuity-audible callback wording.
- **`podcast_expand_below_target: true`** added to the eight chronically-
  short shows (M&A, FF, PT, MAB, Env Intel, Финансы Просто, Unintended
  Consequences, First Principles — all were ≥50% below target, several
  100%). Models & Agents also got an explicit `min_podcast_words: 1500`
  (was relying on the implicit default).
  **SUPERSEDED 2026-07-29 — this flag is now `false` on the 11 shows that
  have a digest-side lever.** Measured over 901 committed episodes, 81%
  still shipped BELOW target *with* the retry running (Tesla 96.7%, M&A
  95.2%): it fires on nearly every episode and almost never reaches the
  goal, because the ceiling is the DIGEST. It also pads by
  paraphrase-duplication (the July 28 pass had to add
  `_dedup_expansion_sentences` to strip its near-duplicates), so what it
  did ship was the weaker copy — and the July 18 playbook had already
  banned podcast-side length levers network-wide. Only `env_intel` and
  `finansy_prosto` keep it, because they have no digest lever yet;
  give them one before switching theirs off. Drift guard:
  `tests/test_cost_efficiency_pass.py::TestLengthLeverPolicy`.
- **Hook-led X teasers network-wide**: Omni View / FF / Planetterrian's
  hardcoded teasers and the generic fallback (used by Unintended
  Consequences) now lead with the episode hook + link the episode blog
  post, matching Tesla/MIT. Models & Agents/MAB/Env Intel/Russian shows
  don't post to X (unchanged).
- **Boilerplate-tic bans** (prompt edits — A/B-listen per landmine #17):
  M&A "This development sits within the ongoing…"; FF "you know what's
  fascinating / blew my mind" deep-dive openers; PT "this development
  fits the tracked program on X" (ran 6×/episode); Omni View's
  every-story "the strongest case for X / for Y" template (now rotates
  three framings, "strongest case" ≤1×/episode); UC "That wraps today's
  case" closer. Plus: MAB requires ≥2 concrete "try this" experiments;
  Env Intel Compliance Brief required even on thin-news days; Финансы
  Просто requires 3-4 practical tips (was 2 → chronic shortfall).
- **RSS channel descriptions rewritten** as value props for the listing
  pages: M&A, FF, MAB, Omni View (Steel Man), Env Intel (odd-weekday
  cadence + Compliance Brief), Unintended Consequences. PT and the two
  Russian shows already had strong descriptions (kept).
- **Topic-queue restock** (the narrative shows' critical operational
  risk): Unintended Consequences +14 → 38 unproduced (~7.6 wk runway, was
  ~4.8); First Principles +12 → 27 unproduced (~3.9 wk, was ~1.3 and
  about to dry up), preserving the concrete/opportunity alternation.
  **July 24 2026 — restocks are now AUTOMATED** (drift guards:
  `tests/test_queue_restock.py`): `.github/workflows/restock-topic-queues.yml`
  (daily 13:37 UTC + dispatch, `force` input) runs
  `scripts/restock_topic_queues.py` — trigger-gated (FPD <4wk, UC <5wk;
  refills to ~8wk) Grok generation against per-show restock prompts
  (`shows/prompts/*_restock.txt` — full queue history injected for dedupe,
  category balance for FPD's alternation, an explicit never-invent honesty
  rule since briefs become episodes). Validation rejects thin briefs, bad
  categories, id dupes, and fuzzy near-duplicate titles vs the ENTIRE
  history (produced included); existing entries are never modified; the
  workflow re-runs `TestNarrativeQueueRunway` BEFORE committing, so the
  runway floors (3.0/4.0wk) are now the alarm that the AUTOMATION broke,
  not a manual chore. **Sep 17 2026:** it did break — four nights on
  grok-4.6 alone (no JSON array 09-14, `APIConnectionError` 09-16) while
  UC drained to 3.7 wk; `generate_candidates` now retries one failed
  primary call on `FALLBACK_RESTOCK_MODEL` (grok-4.3) and the result
  records `model` (`TestModelFallback`). **Same day, later:** the
  15:29 UTC dispatch made the count 0 for 11 — grok-4.6 timed out at
  300 s on BOTH shows and grok-4.3 answered each in under a minute — so
  `restock-topic-queues.yml` sets `NERRA_RESTOCK_MODEL: grok-4.3` (the
  documented override; delete the line to trial 4.6 again). That run
  also exposed a second blocker: the model answered, FPD was refilled
  4.0 → 8.0 weeks, and the workflow then died in its own validator
  because `resequence_unproduced` interleaved UC's three GATE-DEFERRED
  head entries while `test_uc_unproduced_interleaved_not_clustered`
  measures the pickable sequence without them; nothing was committed.
  Deferred entries now stay in place and only pickable entries are
  interleaved (`TestResequenceSkipsDeferred`). Age of AI's deliberately-empty queue is not
  registered and must never be. Generated topics sit unproduced for weeks
  — prune any weak ones directly in `shows/topic_queues/*.yaml`.
- **Финансы Просто YouTube category** fixed 25 (News) → 27 (Education).
- **Operator items (not code):** localize the Russian shows' spoken AI
  disclosure (still English on the Olya voice — A/B per #17); decide
  First Principles distribution-on after the queue/length fixes settle
  (review recommends waiting to ~Ep15); confirm X handles for the
  X-enabled shows so the follow CTA can be set.
