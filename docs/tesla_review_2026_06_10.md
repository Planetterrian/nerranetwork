# Tesla Shorts Time — Full Pipeline Review (June 10, 2026)

Full-stack review of the Tesla Shorts Time show: YAML config, prompts, hooks,
memory system, runner paths, generated episodes (Ep496–505), chapters, RSS,
blog, website, YouTube, and newsletter surfaces. Conducted the same day the
flagship quality pass (`d35ee12`) landed, so this review deliberately focuses
on what that pass did **not** fix, plus the next tier of improvements toward
"the best daily Tesla podcast that exists."

**State of the show:** healthiest property on the network — 505 episodes,
success rate 1.0, $0.69/week pipeline cost, 149 downloads/7d (network #1),
hook-first titles everywhere, chapters + transcripts in the feed, four of the
top-12 most-played network episodes. The foundation is strong; the findings
below are the gap between "solid" and "best in class."

Everything here was verified against the working tree at commit `d35ee12`
(2026-06-10). Items the June 10 pass already addressed (expand-retry on any
below-target script, narrative auto-freshness, "Taking a step back" ban,
hook-led X teaser) are noted only where the fix is incomplete.

---

## P0 — Listener-facing bugs shipping today

### 1. Chapter metadata is malformed on every recent episode

All ten of Ep496–505 ship broken `chapters_ep*.json` (duplicate
"Introduction" entries, spurious mid-episode "Tomorrow Teaser" chapters,
truncated sentence fragments as titles). Apple Podcasts / Pocket Casts render
these directly. Three distinct root causes:

1. **The closing always re-matches the Introduction marker.** The spoken
   closing (`shows/hooks/tesla.py:_pick_closing`) contains "find us on X at
   tesla shorts time". The first chapter marker in `shows/tesla.yaml:217` is
   the case-insensitive pattern `Tesla Shorts Time|coming to you from
   Vancouver|Pulling up to another day`, and `engine/chapters.py:146-151`
   tries markers **in YAML order, first match wins per line** — so the
   closing line is titled "Introduction" on every single episode (visible as
   the trailing duplicate in Ep501/504/505). The Closing pattern never gets a
   chance.
2. **`tomorrow` over-matches.** The Tomorrow Teaser pattern
   (`tesla.yaml:227`) includes the bare word `tomorrow`, so any news sentence
   mentioning tomorrow opens a teaser chapter mid-episode (Ep501 has two).
   Same risk class: `the kicker` in the Counterpoint pattern.
3. **Fragment titles from auto-segmentation.** When markers under-match,
   `engine/chapters.py:188-255` splices segments titled by each segment's
   first sentence — producing titles like "What stands out is that Duan had
   been skeptical earlier…" (Ep504). Better than "Segment 2", but far worse
   than the actual story titles which exist in the digest.
4. The duplicate-collapse at `engine/chapters.py:259-264` only removes
   *consecutive* duplicates, so Introduction…Introduction at opposite ends
   survives.

**Recommended fix (code, no prompt change — safe to ship):**
- Positional anchoring in `parse_chapters`: Introduction may only match in
  the first ~10% of the script; Closing/Teaser only in the last ~15%; story
  markers never in the first/last 5%.
- Check the Closing pattern before Introduction for lines in the final 15%
  (or simply drop the brand name from the Introduction pattern — anchor on
  `^` + greeting words instead).
- Tighten the teaser pattern to `Before we go|before we wrap|keep an eye
  on|we'll be watching` (drop the bare `tomorrow`).
- **Bigger win (medium effort):** chapter titles from the digest, not regex.
  The digest already carries 12 numbered story titles; fuzzy-match each
  Top-12 title's keywords against the auto-segment text and title the
  segment with the actual story headline ("Cybercabs spotted at Atlanta
  service center" beats any sentence fragment). This is the single biggest
  in-app navigation upgrade available.
- Add drift guards: feed `parse_chapters` a realistic script including the
  exact production closing line and assert no trailing "Introduction" and no
  mid-episode "Tomorrow Teaser".

### 2. The spoken closing has a "zero dollars" failure mode and never varies

`shows/hooks/tesla.py:_pick_closing` (line 597) builds the closing
unconditionally from `price`/`change_str`. When all three price sources fail
(`_fetch_tsla_price` returns `(0.0, "(price unavailable)")`), the episode
**speaks**: *"T S L A closed at zero dollars, price unavailable."* The
`is_price_publishable()` guard exists (line 239) but is not applied to the
spoken closing. Two more issues in the same function:

- "closed at" is spoken regardless of `market_state`. Tesla runs ~12:00 UTC
  (~8 AM ET, pre-market); when the quote comes from `fast_info` it can be a
  live pre-market price presented as a close.
- Because the hook supplies `closing_block`, `run_show.py:1937`'s
  `setdefault` never fires — the rotating 3-closing pool in
  `engine/intros.py:97-117` is **dead for Tesla**. Every episode ends with
  the identical sentence, the exact daily-show tic the network has been
  hunting everywhere else.

**Fix:** gate the price sentence on `is_price_publishable` (omit it
entirely when unavailable); phrase by market state ("TSLA is trading at …
in pre-market" / "closed at …"); rotate 3–4 closing variants with the price
sentence injected, reusing the `engine/intros` pool pattern.

### 3. ~~The "(price unavailable)" scrub protects only the X teaser~~ (CORRECTED)

**Correction during implementation:** the scrub at `run_show.py:1716-1718`
runs on the canonical digest text *before* it is saved and before podcast
generation, so the digest/RSS/blog/newsletter path was already protected.
The real remaining gaps were the spoken `closing_block` (finding 2) and the
LLM seeing "$0.00 (price unavailable)" in the digest-prompt header — both
addressed by gating the closing's price sentence on `is_price_publishable`.

### 4. Committed content tracker ships profanity to the public repo and the daily prompt

`digests/tesla_shorts_time/tesla_content_tracker.json` (committed to git,
publicly fetchable via GitHub Pages) contains raw fetched X/Reddit post
titles among the recorded headlines — emoji spam ("Laughing Emojis 🤣🤣",
"Video post") and an outright slur-bearing line ("NY is full of liberal
retards 🤣"). Worse than cosmetic: these headlines are re-injected into
every digest prompt as the "RECENTLY COVERED STORIES" block. The
`source_titles` merge in `engine/content_tracker.py:885-893` should filter
non-editorial titles: fewer than three alphabetic words carries no dedup
signal, and slurs are dropped unconditionally; plus a one-time scrub of the
committed file.

---

## P1 — Quality ceiling (why episodes under-deliver)

### 5. The expansion retry cannot add facts — it only sees its own short script

`engine/generator.py:1778-1787`: the retry prompt contains **only the short
script**, not the digest, while instructing "staying strictly faithful to
the provided stories… add 1-2 listener takeaways, implications… 'why this
matters'". The model has no access to the un-covered Top-12 facts, so the
only available lengthening move is exactly the editorial padding the main
prompt bans and the listener-value heuristic penalizes. This is the most
likely reason 9 of 10 recent episodes shipped 18–36% under target despite
retry infrastructure existing (Ep497 1003w, Ep501 1039w, Ep505 1035w vs the
1600 target; the one on-target episode, Ep498 at 1638w, scored 4.5
listener-value vs 3.0–3.2 for the short ones).

**Fix:** include the full digest in the retry prompt and flip the
instruction to fact-coverage: "stories from the digest below that your
script skipped or compressed — cover them at 5–7 fact-bearing sentences
each; do not add commentary to stories already covered." One extra LLM call,
same cost, but the model can now actually comply.

### 6. The podcast prompt argues with itself about length

`shows/prompts/tesla_podcast.txt` simultaneously demands: "12–15 minute"
(line 27), "13–17 minute… 110–140 lines" (line 32), "at least 2800 words"
(line 169), "under ~950 words is unacceptable" (line 37) — while the YAML
enforces `min_podcast_words: 1600`. 2800 words is an 18–19 minute episode;
1600 is ~10–11 minutes. Conflicting anchors give the model permission to
satisfy the smallest one. Pick a single chain and align every number:
recommend **2,200–2,400 words ≈ 14–16 min** (matches the "12–15 minute"
promise and the RSS description's "in 10 minutes" is also worth revisiting),
set `min_podcast_words: 2000`, and state the word target exactly once.
Prompt edit → A/B-listen per landmine #17. Also stale in the same prompt:
line 14 still says "The ElevenLabs text-to-speech engine" (it's Grok TTS).

### 7. The performance-feedback third of the memory system is dead code

`engine/tesla_memory.py:record_performance_signal` (line 307) has **zero
production callers** (same for the generalized
`engine/show_memory.py:303`). `tesla_performance_tracker.json` is
hand-edited and 13 days stale on a daily show (last touched 2026-05-27);
`{tesla_performance_signals_block}` injects effectively static text into
every prompt. The "recursive improvement architecture" currently runs at
two loops out of three.

**Fix (highest-ROI item in this review):** the data already exists in-repo —
`api/op3_stats.json` has per-episode downloads, and the YouTube publish path
returns video IDs. Add a nightly step that (a) maps top/bottom OP3 episodes
to their hooks + mined themes, (b) pulls YouTube views/avg-watch for the
last N uploads, and (c) writes `strong_topics_last_30d` /
`weak_topics_last_30d` + hook-style notes via `record_performance_signal`.
Then the prompts' existing "favor topics with strong recent engagement"
instruction starts operating on real data instead of a stale hand-curated
list.

### 8. Theme mining is still dominated by the memory system echoing itself

`tesla_theme_history.json` post-fix still shows chains of overlapping
bigrams with identical counts ("texas dedicated" / "dedicated factory" /
"factory construction" / "construction underway" / "cells humanoid", all
count 17) — that's one fixed sentence mined 17 times, and it's the Optimus
*narrative-status* text. The injection → LLM-echo → digest → mining loop
means tracker prose gets re-mined as a "theme" every episode. Latest entries
(Ep504, first Ep505 record) still lead with "open questions" / "questions
show" boilerplate, and **Ep505 has two divergent entries** (mining ran
twice on June 10 — pre- and post-fix runs; there's no per-episode
idempotency guard).

**Fix:** before mining, strip sentences that fuzzy-match the injected
narrative-status block (or mine only the Top-12 + X Takeover sections);
make `update_theme_history` replace-by-episode instead of append; one-time
re-scrub of the count-17 echo chains and remaining boilerplate.

### 9. Program-mention detection is word-boundary-blind

`engine/tesla_memory.py:_PROGRAM_MENTION_KEYWORDS` uses substring matching:
"unsupervised" in any context advances the FSD-unsupervised program,
"robotaxis" (plural) does match but "robo-taxi" variants are patchy, and
several programs can claim the same sentence. Since `d35ee12` made these
matches drive on-air freshness callbacks ("last covered on air"), false
positives now produce wrong continuity lines. Switch to `\b`-anchored
regexes with explicit plural/hyphen variants and require program-specific
anchor words for ambiguous terms.

### 10. Sunday recap robustness

`engine/weekly_recap.py:195-235`: the Tesla narrative injection is wrapped
in a bare `except: pass` (silent omission if the tracker is unreadable) and
uses a hardcoded `digests/tesla_shorts_time` path instead of
`config.episode.output_dir`. The June 7 recap (Ep503) was editorially good
but also under-length (1291w) and chapter-broken like the dailies — both
inherit fixes 1 and 5/6. Log loudly on tracker-load failure and use the
config path.

---

## P2 — Growth and positioning

### 11. Audio brand ≠ store brand

Every episode **speaks** "Tesla Shorts Time Daily" (intro pool
`engine/intros.py:39`, prompt brand rules) while the Apple/Spotify/website
brand was deliberately aligned to "Tesla Shorts Time" in May 2026. A
listener who hears the show name and searches it gets a string mismatch.
Recommend dropping "Daily" from the spoken name to match the listing
(operator decision; intro-pool + prompt edit; A/B-listen). The chapters
Introduction-pattern fix in finding 1 interacts with this — do them
together.

### 12. Make the narrative tracker a public flagship, not a sidebar

`tesla-narrative.html` is a genuine differentiator (no other Tesla podcast
has a public program tracker), but as of this review its "last deep
coverage" stamps trail ~30 episodes behind and only surface 3 of the 6
tracked programs prominently. `d35ee12`'s auto-freshness should fix the
staleness — verify it propagates to the page on tonight's run. Then promote
it: link it from every blog post and episode show-note (it's currently only
a button on tesla.html), and add a "this episode advanced: Optimus,
Cybercab" line to blog posts from the same program-mention data. That turns
each episode page into an entry point to the binge surface.

### 13. Distribution items already in flight — verify, don't rebuild

- `podcast:funding` + `podcast:person` injection landed in `1b4dcf3`
  **today**; the live `podcast.rss` predates it. Confirm tags appear after
  the next episode rebuild — no further work needed.
- X cross-promo reply flag is on network-wide; Tesla has `x_handle` set, so
  the follow-CTA thread should be live — spot-check the next teaser thread.
- Old feed items (≤Ep355) have generic titles. **Do not bulk-retitle** —
  rewriting historical GUID'd items risks duplicate-detection and churns
  subscribers' clients for ~zero discovery gain on a back catalog this thin.
- iTunes owner email is `patrick@planetterrian.com` on a Tesla property —
  cosmetic, operator's call.

### 14. RSS description over-promises brevity

The June listing description says "in 10 minutes" while the show targets
(and should target) 14–16 minutes. Align the listing with whatever length
target finding 6 settles on — Apple listing copy that undersells length is
fine; one that *mis*-sells cadence/format invites churny first plays.

---

## P3 — Hygiene

- `shows/hooks/tesla.py:_pick_intro` (line 577) is dead code (`_pick_closing`
  is live); delete it and update the stale comment at lines 63-64.
- `shows/hooks/tesla.py:69-75` swallows memory-injection failure at WARNING
  with no fallback — raise to ERROR and emit a GitHub `::warning::`
  annotation so a corrupt tracker is noticed the day it happens, not weeks
  later.
- Test gaps worth closing: chapter parsing against the real closing line
  (finding 1), `is_price_publishable` gating of the spoken closing
  (finding 2), expansion-retry prompt containing the digest (finding 5),
  per-episode theme-history idempotency (finding 8).

---

## Recommended order of attack

| # | Item | Effort | Impact | Risk |
|---|------|--------|--------|------|
| 1 | Chapter fixes: positional anchoring + pattern tightening + drift guards (finding 1) | S | High — visible in every podcast app | Low (code-only) |
| 2 | Closing gate + market-state phrasing + closing rotation (finding 2) | S | High — kills an on-air failure mode + daily tic | Low |
| 3 | Expansion retry gets the digest + fact-coverage instruction (finding 5) | S | High — directly attacks chronic under-length | Low |
| 4 | Digest scrub before podcast generation (finding 3) | S | Medium | Low |
| 5 | Summaries JSON content filter (finding 4) | S | Medium — reputational | Low |
| 6 | Wire OP3 + YouTube into `record_performance_signal` nightly (finding 7) | M | High — activates the dead feedback loop | Low |
| 7 | Theme-mining echo filter + idempotency + re-scrub (finding 8) | M | Medium | Low |
| 8 | Unify length targets in prompt + YAML (finding 6) | S | High | **A/B-listen** (landmine #17) |
| 9 | Word-boundary program matching (finding 9) | S | Medium | Low |
| 10 | Story-title chapters from digest Top-12 (finding 1, phase 2) | M | High — best-in-class navigation | Medium |
| 11 | Brand alignment "Daily" decision (finding 11) | S | Medium | Operator + A/B |
| 12 | Narrative page promotion + per-episode program links (finding 12) | M | Medium — growth | Low |
| 13 | Recap robustness, dead code, hygiene (findings 10, P3) | S | Low | Low |

Items 1–7 and 9 are code-only and safe to ship without changing generated
editorial content. Items 8 and 11 change what listeners hear — per landmine
#17, A/B-listen before trusting them and revert via git if quality dips.

## Implementation status (June 10, 2026 — same PR)

All items above were implemented on this branch the same day (operator
request: "fix all identified issues"):

- **Chapters (1):** `SectionMarker` gained a `where: start|end` positional
  constraint (`engine/config.py`, `engine/chapters.py`), markers match
  once-per-title, and `shows/tesla.yaml` anchors Introduction to the
  opening window and Teaser/Closing to the closing window, drops bare
  `tomorrow` and `the kicker`. Drift guards:
  `tests/test_chapters.py::TestPositionalConstraints`.
- **Closing (2):** `_pick_closing` rotates 4 date-keyed variants, gates the
  price sentence on `is_price_publishable`, and phrases by market state
  (pre-market / after-hours / closed). Every variant is pinned to match
  the YAML Closing chapter pattern.
  Drift guards: `tests/test_tesla_hook.py::TestClosingBlock`.
- **Content tracker profanity (4):** `_is_dedupe_worthy_title` filter on
  the `source_titles` merge + one-time scrub of the committed JSON.
  Drift guard: `tests/test_content_tracker.py::TestSourceTitleJunkFilter`.
- **Expansion retry (5):** the retry prompt now carries the full digest
  with a fact-coverage instruction ("cover skipped/compressed stories at
  5–7 fact-bearing sentences"), replacing the pad-inviting wording.
  Drift guard: `test_tesla_quality_pass.py::TestExpansionRetryCarriesDigest`.
- **Length unification (6):** the podcast prompt now states ONE target
  (2,200–2,400 words ≈ 14–16 min); `min_podcast_words: 2000`; stale
  ElevenLabs reference removed; RSS description updated to "15 focused
  minutes". **A/B-listen the next episodes per landmine #17.**
- **Performance loop (7):** `tesla_memory.update_performance_from_op3`
  derives `strong_topics_last_30d` from real OP3 download data, run
  nightly via `scripts/update_tesla_performance.py` (wired into
  `nightly-maintenance.yml`, tracker committed by the nightly push).
  Drift guards: `test_tesla_quality_pass.py::TestPerformanceLoopFromOp3`.
- **Theme mining (8):** narrative-prose echo filter
  (`_narrative_prose_bigrams`), per-episode idempotency, URL stripping,
  expanded stopwords, hardened one-time scrub; the committed history was
  re-scrubbed (left only genuine themes: "giga texas", "optimus",
  "service center", "rivian drive").
  Drift guards: `test_tesla_quality_pass.py::TestThemeMiningHardening`.
- **Program matching (9):** word-boundary regexes; bare "unsupervised"
  no longer advances FSD. Drift guards:
  `test_tesla_quality_pass.py::TestProgramMentionWordBoundaries`.
- **Recap robustness (10):** narrative-injection failures now log loudly
  instead of `except: pass`.
- **Brand (11, operator-approved via "fix all"):** spoken name is now
  "Tesla Shorts Time" (engine/intros.py + prompt brand rules) matching
  the listing. **A/B-listen per landmine #17.**
- **Narrative page promotion (12):** blog posts for narrative-memory
  shows now link the Story Tracker page (UTM-tagged).
- **Hygiene (P3):** dead `_pick_intro` deleted; memory-injection failure
  raised to ERROR + GitHub Actions `::warning::` annotation.

## Claims checked and rejected during this review

For the record, several plausible-looking issues were investigated and are
**not** problems: `tests/test_tesla_quality_pass.py` exists and pins the
June pass; `op3.dev/e/` enclosure prefixes are the intentional OP3 analytics
wrapper around R2 URLs, not a mixed-CDN problem; `x_accounts` in
`tesla.yaml` is live config consumed by `fetch_x_posts`
(`run_show.py:639`); and the missing `podcast:person`/`podcast:funding`
tags are simply awaiting the first rebuild after today's `1b4dcf3`.
