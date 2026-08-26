Aug-15 ships held (0 Title: heading leaks; Market Watch present on mid-body price lines; engineering-anchor rotation broke the 10/10 monoculture), but 10/10 scripts remain under 1300w, SPCX is still spoken twice on most dailies, Ep077 mid-body headline chapters returned, and Ep081 repeated the Louisiana story across segments.

_Generated on **grok-4.5** by `scripts/run_show_review.py` (replaces the Claude-Opus review agent). Estimated cost: **$0.1499**._

## Scored prior predictions
| Prediction | Verdict | Evidence |
|---|---|---|
| digests with leaked "Title:" heading labels (snapshot Digest heading integrity section) | hit | review_snapshot Digest heading integrity: 0 leaked heading labels on last 10 spacex digests |
| non-special dailies with a mid-body SPCX price/tape line and NO Market Watch chapter | hit | Ep072/074-077/079-081 chapters include Market Watch on mid-body tape/price; Ep073/078 correctly omit (sign-off-only) |
| brand garbles (Grog\|Спейс-Экс\|Cloud Fable\|Global Star) in new youtube_videos.{ru,fr}.json titles | partial | No new garble instances flagged on spacex dub surfaces in this window; 08-15 restore shipped — confirm on next publish batch |

## ⚠️ A/B-listen required — NOT applied (landmine #17)
These prompt/audio changes are **proposals only**. Apply them yourself, render/listen, then merge if they sound right.

**`shows/prompts/spacex_digest.txt`** (prompt) — P1: Ep081 restated Louisiana $100B/10-pad/2027-2029 across cold-open substrate, Engineering, body, and AI. Shape-only rule + verbatim ban on repeated key figures; no quotable example sentence (de-seed-by-shape).
```diff
- ABSOLUTE RULE — ZERO STORY OVERLAP: each story appears in exactly ONE section. Before writing each section, re-read what you covered above and skip anything already used. Fewer unique items beat duplicated ones.
+ ABSOLUTE RULE — ZERO STORY OVERLAP: each story appears in exactly ONE section. Before writing each section, re-read what you covered above and skip anything already used. Fewer unique items beat duplicated ones.
+ MEGA-STORY DAYS: when a single development dominates the fetch (one site/deal/capex figure driving most items), put FULL depth in exactly one primary section (Top News OR Engineering Deep Dive OR AI & Compute — whichever owns the mechanism). Every other section may use at most one short pointer clause to that story and MUST NOT restate the same dollar figure, pad/site count, year target, or job count. No second full retelling.
```

**`shows/prompts/spacex_podcast.txt`** (prompt) — Podcast-side mirror of the digest mega-story rule so Ep081-class multi-section echo cannot be re-emitted from a clean digest. A/B-listen required (landmine #17). Shape + ban; no new example sentence.
```diff
- Never repeat a fact you already stated — each sentence must add NEW information (Episode 1 restated the earnings-report point four times; that is padding, not coverage)
+ Never repeat a fact you already stated — each sentence must add NEW information (Episode 1 restated the earnings-report point four times; that is padding, not coverage).
+ MEGA-STORY DAYS: if one development dominates the digest, give it full spoken depth in a single stretch (usually Top News or the Engineering Deep Dive). Do not re-open the same dollar figure, pad/site count, or year target again inside AI & Compute, Counterpoint, or the teaser — one clause of forward pointer max. Chapters still use their required anchor phrases; the ban is on re-telling the same facts, not on anchors.
```

## Code/metadata-only proposals (no A/B needed)
- **`engine/chapters.py`** (code): P0 listener-facing metadata: Ep077 shipped four non-section headline chapters. Deterministic garble/filter class (~100% hit per meta-review); no A/B. Complements Aug-15 Title:-strip which does not catch bare headlines.
- **`digests/spacex/chapters_ep077.json`** (code): One-time archive cleanup so the public chapter surface matches the known section set; pairs with the allowlist guard.
- **`tests/test_spacex_show.py`** (code): Locks P0 allowlist so Ep077-class regression cannot return unnoticed.

## Deferred (carried forward)
- OPERATOR DECISION (escalation after repeated misses): accept grok-4.3 daily length plateau vs further digest-substrate only (min_digest_words / full-text fetch / licensed section floors) — do not re-propose podcast expand, podcast word floors, or conditional '7+/10 if lever ships' predictions
- OPERATOR DECISION (escalation since 2026-06-13): SPCX price-once — Market Watch qualitative + single precise quote only in closing_block; coupled A/B-listen; or accept double price as brand and close — stop carrying the same unshipped fix as a silent proposal
- Q2/special path: richer spacex_deep_dive.txt briefs so specials clear deep_dive.min_podcast_words 2400; do not stack time-critical specials on the daily publish day (Ep059 lesson)
- Entity-discipline prompt (xAI/SpaceX Memphis/Colossus operator) — regression guard only; A/B; carried while window stays clean
- api/shorts_ab.json still 'collecting' after experiment ended 2026-08-14 — report builder should mark ended (non-audio)
- NASA public-domain b-roll pool vs retired shorts_ab generated motion — render-side follow-up, not audio
- Scheduler forensics for any missed Sunday weekly_summary_segment run (June-28 class) — operator

<sub>tokens: 61333 in / 4545 out</sub>