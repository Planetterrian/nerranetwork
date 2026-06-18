# Planetterrian Daily Quality Review (June 18, 2026)

Same review-then-fix process as the Tesla (#576), four-show (#577), EI
(June 10/11/15), and FF (June 12/16) passes. Drift guards:
`tests/test_planetterrian_quality_pass.py`. This is the first PT review since
the June 10 pass (`docs/planetterrian_review_2026_06_10.md`) and the first PT
entry in the recursive ledger (`docs/reviews/ledger/planetterrian.yaml`).

**Snapshot:** `python scripts/review_snapshot.py planetterrian` — scripts run
1178–1378w (all 10 below the 1600 floor); chapter-shape flags on Ep086/Ep088
("only 1 chapter"); cost ~$0.115/episode; OP3 28 downloads/7d, 183/30d.

## Scoring the June 10 pass

- **Unified length target (floor 1250→1600, target 1,800–2,100).** **MISS.**
  Post-fix episodes Ep085–093 ship 1178–1378w — still well under the 1600
  floor, none near 1,800. Root cause confirmed identical to the FF twin
  (`docs/reviews/fascinating_frontiers_review_2026_06_12.md`): the **digest is
  the ceiling**, not the target. PT's digests run 1055–1429w (Nature/Science/
  bioRxiv RSS return snippets, not full text); the podcast — told to use only
  the brief — can't exceed them without the padding/invention both prompts
  ban, and the digest-carrying expand-retry plateaus there. Re-attacking length
  stays **deferred** behind the operator's four-show length A/B, exactly as
  FF/UC are deferred (the only non-padding lever is expanding the Science Deep
  Dive, which is licensed to use the model's own knowledge — held until the
  A/B settles). No soft-floor skips fired in the post-fix week, so the June 10
  operator note ("drop to 1400 if PT skips more than once") did not trigger;
  floor stays 1600.
- **Chapter `where` anchors + "see you next" closing coverage.** **Partial.**
  The anchors landed and the Closing pattern gained "see you next", but the
  anchoring exposed two *deeper* chapter bugs the June 10 pass didn't reach —
  see P0 below. The "watch the first post-pass week" instruction is what
  surfaced them.

## P0 — listener-facing bugs shipping today

### 1. Introduction chapter missing on ~50% of episodes → orphaned body

The Introduction marker was `Welcome.*Planet|Planet-terry-an.*episode`
(`shows/planetterrian.yaml:273`). But the intro line rotates **four** greetings
(`engine/intros.py` `_SHOW_PERSONALITIES["planetterrian"]["greetings"]`):
"Welcome to", "Hey, welcome to", **"Good to have you on"**, **"Thanks for
tuning in to"**. The last two carry no "Welcome", and the respelling
alternative `Planet-terry-an` never matches the real spoken spelling
`Planetterrian`. Verified misses: Ep085 ("Good to have you on…"), Ep086 & Ep088
("Thanks for tuning in to…"), Ep093 ("Good to have you on…").

When Introduction misses, `chapters[0]` becomes the teaser/closing marker (both
`where: end`), so the auto-segmentation fallback — which only splits the
**first** chapter — has nothing to splice across the body. The result: the
entire first ~88% of the episode has **no chapter at all**, and the player's
first navigation mark lands at the Tomorrow Teaser (Ep086/Ep088 shipped with
literally one chapter). This is the Tesla/EI/UC orphaned-body class.

**Fix (config, metadata-only — no audio change):** anchor on the show name +
"episode", which every greeting variant contains:
`Welcome.*Planet|Planetterrian.*episode|Planet-terry-an.*episode`. Verified
10/10 recent episodes now open with an `Introduction` chapter at word 0.

### 2. Closing chapter stolen by the Tomorrow Teaser ("keep an eye on" class)

The spoken Tomorrow Teaser opens "Keep an eye on…" / "Watch for…" (the digest/
podcast prompt's seeded teaser lead-ins, `*_podcast.txt:123`), which the teaser
marker `Before we go|Next time|before we wrap` did **not** match. With the real
teaser line unmatched, the teaser's `Next time` token then matched **"See you
next time"** in the *closing* line — and because Closing was listed *after*
Tomorrow Teaser, the first-marker-per-line rule assigned the sign-off line to
"Tomorrow Teaser" and never reached Closing. Ep086 and Ep090 shipped with no
Closing chapter and the closing mislabeled as the teaser.

**Fix (config, metadata-only):** the EI June-11 ordering rule — list **Closing
before Tomorrow Teaser** so Closing wins the sign-off line — plus broaden the
teaser pattern with `keep an eye on|watch for` so the real teaser line matches
on its own line. Verified: Ep085/086/088/090–093 now parse Introduction →
… → Tomorrow Teaser → Closing in order.

## P1 — quality ceiling

### 3. Science Deep Dive marker was dead

The deep-dive markers required the literal label (`science deep dive|deep dive|
under the microscope`), but the podcast prompt explicitly forbids announcing
the section ("Do NOT announce it as 'Science Deep Dive'", `*_podcast.txt:119`),
so the marker never matched and the section fell into the garbage auto-segment
fallback (the M&A "pop the hood" / EI deep-dive class). The prompt instead
seeds a highly consistent spoken opener, verified in Ep090–093:
"Now, here's something most people get wrong about…" / "Most people picture/
assume…". Extended the marker to match that opener
(`something most people get wrong|most people (picture|assume|think|believe|get
wrong)`). Verified: 6/10 recent episodes now carry a real `Science Deep Dive`
chapter (the rest had no deep-dive that day). Metadata-only.

## Deferred (carried forward — re-evaluate next pass)

- **Chronic under-length** (digest ceiling, FF/UC root cause). The only
  non-padding lever is Science-Deep-Dive expansion; held behind the operator's
  four-show length A/B. Do not re-litigate the target.
- **Garbage mid-body auto-segment chapter titles.** Episodes with a long body
  and no deep-dive opener (Ep084/088/089) still title interior chapters from
  raw mid-sentence fragments ("The jmjd genes encode H3K27me3 demethylases…",
  "It aims to enhance consumer acceptance of protein beverages"). The P0/P1
  fixes above shrink the head that auto-segments (Deep Dive now bounds it) but
  don't eliminate it. The clean fix is digest-driven / LLM-generated chapter
  titles — the shared, medium-effort, Tesla-/M&A-deferred class. Carried.

## Checked / no action

- **Narrative tracker freshness** — healthy; `auto_update_narrative_from_digest`
  advances every program's `last_mentioned` each episode (all six programs at
  Ep091–093 / today).
- **"Right now, as you…" deep-dive tic** (7/10) and **"Keep an eye on" teaser**
  (8/10) are prompt-seeded signature structure, not boilerplate to ban — and
  the chapter fixes above now *lean on* their consistency. Left unchanged.
- Cost (~$0.115/ep), success rate, RSS hook-first titles, X teaser — healthy
  (re-confirmed from the June 10 pass; no regression).

## Operator items

- The chapter fixes are **metadata-only** (chapters.json) — no A/B listen
  required. New chapter shapes apply on the next generated episode.
- Length and the garbage-title classes remain deferred pending the four-show
  length A/B and the shared LLM-chapter-title work, respectively.
