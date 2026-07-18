# Network review — 2026-07-18 (goals & differentiation audit + meta-review)

Operator request: *"a thorough review of all the podcasts that have been
produced — determine if all the goals are being met or if further improvements
can be made to really deliver a high quality differentiated product."*

Method: fresh `review_snapshot.py` for all 14 producing shows, transcript
verification of every flagged item (last ~10 episodes per show, deep sweep of
Jul 13–18), full ledger meta-review (15 ledgers, ~75 predictions), health/
funnel/cost data, and direct audio measurement of shipped episodes. This pass
deliberately sits ABOVE the July defect passes (07-02 editorial, 07-09
depth/discovery/quick-wins/prompt, 07-16 audio forensics): it scores their
predictions, verifies their fixes shipped, and answers the product question
they didn't.

---

## The product verdict

**The factory is world-class. The audience funnel is the product gap.**

- Operations: 100% run success across all 15 shows/30 days, zero recovery
  incidents, zero missed daily slots Jul 10–18, ~90 episodes/week in 5
  languages at **~$35–40/month total content cost** (~$0.03–0.09/episode).
- Audience: **3,070 downloads/30d network-wide** (~130/day), 3 newsletter
  subscribers. The pipeline-quality machine (this review included) is now
  optimizing far past the marginal value of the next listener acquired.
- **Differentiation is topical authority, not format.** Tesla + Models &
  Agents + SpaceX = 53% of downloads — the three clearest "chronicle of a
  beat" shows (and the ones carrying narrative memory). The fastest growers
  are beat-owners (SpaceX 2.4×, Planetterrian 3× last week). The
  format-differentiated but topic-generic shows (Omni View steel-man,
  First Principles) are flat or fading. FPD and Привет, Русский! (17
  downloads/30d) need a reposition/merge/sunset decision, not more polish.
- **The two most differentiated bets are dark.** The DP Pod — the only
  two-host dialogue show, 14/14 clean episodes — has zero distribution and
  zero download telemetry (feed never submitted to any podcast index, so
  OP3 can't attribute its traffic). Age of AI — the only live-interview
  product, arguably the most defensible format in the portfolio — has
  shipped 0 episodes. The differentiation thesis is riding on two products
  with no market feedback loop.

### Per-show goals scorecard (positioning vs delivery vs audience)

| Show | Delivers its stated goal? | Audience signal | Note |
|---|---|---|---|
| Tesla | ✅ chronicle + trackers | #1, flat-choppy | 10/10 below word floor (digest ceiling) |
| Models & Agents | ✅ builder briefing | #2, growing | healthiest show in the network |
| SpaceX | ✅ engineering-first | #3, growing fast | post-IPO beat ownership working |
| MAB | ✅ from-zero explainer | #4, growing | chapters fixed 07-16; verified re-parse clean |
| Modern Investing | ⚠️ record honest but alpha not yet significant (t=0.31) | #5, **declining** | differentiation claim unproven on-air |
| Fascinating Frontiers | ⚠️ ephemeris/almanac still leaking 3/10 | #6, recovering | see P1-2 |
| Planetterrian | ✅ health/longevity | #7, breakout week | astronomy leak closed 07-16, holding |
| Omni View | 🔄 realigned 07-18 | #8, flat | next 10 episodes are the read |
| Unintended Consequences | ✅ narrative formula | #9, steady growth | |
| First Principles | ✅ formula, ⚠️ audience | #10, **stagnating** | distribution still off (operator gate at ~Ep15 passed?) |
| Env Intel | ⚠️ "all-province" positioning vs last 3 episodes all-BC | #11, growing (tiny) | |
| Финансы Просто | ⚠️ description says "Ежедневный" (daily); actual cadence contested (see P0-1) | #12, flat tiny | |
| Привет, Русский! | ✅ vocabulary-first | #13, ~zero | decision item |
| DP Pod | ✅ format + club mechanics; ⚠️ club loop hollow (0 real dispatches, empty state aired 6/10) | unmeasured | see P2-1 |
| Age of AI | — not launched | — | |

---

## P0 — operational

**P0-1 — Russian shows publish OFF-SCHEDULE via the daily-audit retry path
(8 unplanned public episodes in one week).** Three config sources disagree
about FP/PR cadence: `run-show.yml` CRON_MAP + the scheduler Worker say
**Monday-only**; `review_episodes.py:195,219` models them as **even days**;
FP's own YAML description says **"Ежедневный" (daily)**. Result: on even
non-Mondays no cron fires → the audit's missed-episode detector flags them →
`dispatch_audit_retries.py` auto-dispatches → episodes publish at random
afternoon times (Jul 11/12/14/16 at 14:23–17:52 UTC vs the 06:07/09:37
slots). **Operator decision required — this review deliberately does NOT
pick the cadence** (either "fix" changes the shipped product): choose
Monday-only or even-days, then align all three sources + the FP description
in one change. Evidence: auto-generated commit times Jul 10–18;
`api/daily-review.json` remediation block.

## P1 — quality ceiling (verified, this pass)

**P1-1 — Promo-tail chapter theft (FIXED, engine-wide).** The 07-16 rotating
network outro names sibling shows AFTER the closing; un-anchored body markers
stole those mentions as spurious final chapters: Tesla `chapters_ep544.json`
shipped "First Principles" at 642s (after Closing 616s — the phrase occurs
ONCE in the episode, inside the promo line); MIT `chapters_ep104.json`
"Investor Education" from the promo's "daily deep dive". Fix:
`engine/chapters.py` — a `where: end` chapter is final; matches starting
after it are dropped with a loud warning. Verified by re-parsing both real
episodes (both now end on Closing). Drift guards:
`tests/test_chapters.py::TestClosingIsFinal`.

**P1-2 — FF ephemeris/almanac items still shipping (3/10)** despite two
filter rounds: Ep126 "Venus Passes Close to Regulus in Evening Sky", Ep127
"Upper Scorpius Dominates Evening Sky This Week", Ep134 (07-17, post-web-
search-fix) "Moon passes 2° south of Venus this afternoon" — pure almanac
content on a science-news show. The digest normalizes fetched titles, so
title-pattern filtering alone cannot hold the line. Recommended (A/B-gated,
NOT applied): a digest-prompt scope bullet — "NO sky-calendar/ephemeris
items (planet X passes/shines/conjunction/what's in the sky tonight) — these
are almanac, not news". The new snapshot leakage counter (below) now scores
this class mechanically.

**P1-3 — Seeded-template tics, fourth generation (A/B proposals only,
per the ledger meta-lesson — de-seed by SHAPE, add rotation memory, never
seed a replacement phrase):**
- **FP (Финансы Просто), 100% saturation:** «А теперь моя любимая часть…»
  10/10 (seeded verbatim `fp_podcast.txt:63`); «И вот так работает [X] — не
  так уж и сложно/страшно, правда?» 12/12 consecutive (seeded TWICE:
  `fp_digest.txt:111` + `fp_podcast.txt:137`).
- **MIT:** "here's something that most retail investors get wrong" 7/10 —
  the exact quoted example at `modern_investing_podcast.txt:194`.
- **PT:** "The practical takeaway is…" 8/10 (converged from "Close with a
  practical takeaway", both prompts).
- **PR:** "Want to know a secret about…" 9/10 (dead-rotation opener).
- (EI's "nuance" tic and OV's "Next time you see…" are already covered by
  the 07-16 de-seed and 07-18 realignment respectively — scored next cycle.)

**P1-4 — DP Pod Network pick convergence (FIXED, code-only).** The pick was
grounded and date-accurate in 9/10 episodes (zero phantom episodes) but
converged: FF picked 5/10 including consecutive days, same host + "If you
liked X…" frame 3 episodes running. Fix: `shows/hooks/dp_pod.py`
`_recent_network_picks` mines recent Network pick lines into a vary-away
list (live output confirms FF 4 of last 6). Drift guards:
`tests/test_dp_pod_show.py::TestNetworkPickRotationMemory`.

**P1-5 — Chronic under-length: the July digest-expand pilots have not moved
the flagships yet.** Tesla 10/10 below floor (median 1570/2000), MIT 10/10
(1560/1800), MAB 10/10 (1103/1200), UC 10/10 (1082/1300), DP 8/10
(1247/1550). OV's 07-18 slot-depth realignment is the first root-cause
attack; its next 10 episodes are the natural read for the whole class.
Per the ledger meta-review (see below), podcast-side length levers are now
formally banned network-wide — digest-substrate levers only.

## P2 — growth / discoverability

**P2-1 — DP Pod is flying blind (operator, 15 minutes):** submit
`dp_pod_podcast.rss` to the Podcast Index / Apple / Spotify so OP3 can
attribute its traffic; seed the first real Dispatch (the honest empty state
aired 6/10 episodes — the club's proof-loop can't start itself).
**P2-2 — First Principles distribution gate:** the "wait to ~Ep15" operator
gate has passed (Ep40+); it is the #10 show with distribution still off —
decide on/off.
**P2-3 — MIT decline + unproven alpha:** downloads fell 4 weeks straight
while the on-air differentiation claim ("beat the indices") remains honest
but statistically unproven (t=0.31, beats 1 of 3 indices). The show's fate
follows the record; no code action.
**P2-4 — Dashboard voice-drift false positives (FIXED):** the blessed-voice
baseline still pointed at the retired ElevenLabs RU voice, flagging
FP/PR/Age-of-AI on every build — warnings that train the operator to ignore
warnings. `scripts/generate_dashboard.py` now blesses Olya `0b875ae2` + the
sanctioned `ara` (Mira).

## Audio verification (new data on the 07-16 A/B items)

- **The denoise chain is ENGAGED in shipped audio:** re-applying
  `adeclick,afftdn` to the shipped Jul-18 episodes removes ~0.0–0.5 dB
  (denoising an already-denoised file is a no-op) — the production chain ran.
  The operator's A/B listen remains the quality gate per landmine #17.
- The final-script dedup fix is holding (SpaceX Ep035/036 clean after the
  Ep034 double-spoken deep dive). One residual: MIT Ep109 speaks one
  sentence twice in far-apart sections — below the conservative dedup's
  radar, acceptable.
- Jul 13–18 sweep (75 scripts): no scaffold leaks, no `$nan`, no known
  phonetic garbles, clean flagship hooks, FP episodes fully Russian.

## Meta-review of the review process (ledger aggregate, 15 ledgers)

Verdict rates by category: **garble/pronunciation fixes ~100% hit; fetch
filters ~100% hit when scored; chapter fixes high-hit but whack-a-mole;
prompt de-seeds bimodal (banned phrase dies, successor template emerges —
proven ≥4×); podcast-side length levers ~10 misses vs 1 hit.** Shipped
process fixes:

1. **Playbook category rules** (`.claude/commands/review-show.md`): length
   findings restricted to digest-substrate levers network-wide; de-seed by
   shape + rotation memory + successor-tic prediction required;
   garble/filter categories weighted up; conditional predictions banned
   (score `n/a-lever-not-shipped`); two-miss escalation to operator
   decision; closed-unmerged PRs require an explicit rejection signal
   before `do_not_retry` (PRs #758/#827/#832 were infrastructure closes,
   not rejections — their proposals remain live in `docs/reviews/pending/`).
2. **Ledger discipline rule:** every pass that writes predictions must
   append a ledger entry — five July passes (07-09 ×4, 07-16) wrote
   predictions into docs the rotation cannot score.
3. **Snapshot fetch-filter leakage counter** (`scripts/review_snapshot.py`):
   scans recent digests for excluded-class content, with bold-title probing
   and date-suffix stripping to kill false positives. Immediately scored
   three long-pending predictions (SpaceX junk titles 0 hits ✅, Tesla 13F
   0 hits ✅, FF ephemeris 3 leaks ❌ → P1-2).

## Scoring the 07-02 network predictions (ledger updated)

1. Guard/retry audio defects = 0 over 2 weeks → **partial**: the two fixed
   classes did not recur, but sibling classes shipped (SpaceX Ep034
   whole-section duplication — different mechanism, fixed 07-16; MAB 5/14
   missing closings from two new causes, fixed 07-16 and verified
   re-parsing clean this pass).
2. Snapshot surfaces Cyrillic tics + missing-final-Closing → **partial**:
   both checks landed and caught real defects (FP tics, EI Ep49-51), but
   the Closing check was English-only until 07-16 (false-flagged every FP
   episode).
3. PT-vs-FF same-day duplication = 0 → **partial**: verbatim same-day
   duplication ended; the astronomy class kept leaking via the un-filtered
   web-search route until 07-16 (PT Ep116/119/120); PT clean since, FF's
   own ephemeris class still open (P1-2).

## Shipped this pass (all code/metadata-only, no audio changes)

- `engine/chapters.py` — closing-is-final invariant (P1-1)
- `shows/hooks/dp_pod.py` — Network pick rotation memory (P1-4)
- `scripts/generate_dashboard.py` — voice-baseline fix (P2-4)
- `scripts/review_snapshot.py` — fetch-filter leakage counter
- `.claude/commands/review-show.md` — meta-review category rules + ledger
  discipline
- Ledger: 07-02 predictions scored; today's entry with predictions;
  network-wide `do_not_retry` for podcast-side length levers
- Drift guards: `tests/test_chapters.py::TestClosingIsFinal`,
  `tests/test_dp_pod_show.py::TestNetworkPickRotationMemory`,
  `tests/test_review_agent.py::{TestSnapshotFetchFilterLeakage,
  TestDashboardVoiceBaseline}`

## ⚠️ A/B-listen required

**None applied.** The four tic de-seeds (P1-3: FP ×2, MIT, PT, PR) and the
FF ephemeris digest-scope bullet (P1-2) are PROPOSED only — apply per the
de-seed-by-shape rules with rotation memory, render before/after with
`--test`, and listen before trusting.

## Operator decision items (ranked by leverage)

1. **Distribution > polish.** The single highest-leverage hour is now
   funnel work: submit dp_pod's feed (P2-1), decide FPD distribution
   (P2-2), and consider the same for SpaceX X-posting (fastest-growing
   show, X off).
2. **RU cadence decision** (P0-1) — pick one cadence, align three configs +
   the FP description.
3. **FPD + PR product decision** — reposition, merge, or sunset the two
   flat/zero-audience shows rather than continue polishing.
4. **Seed the DP Pod club loop** — one real dispatch (P2-1) and the patron
   rail when ready.
5. **Age of AI** — every week unshipped is a week the most defensible
   format earns nothing; the phase-1 smoke test is the gate.
6. Env Intel's all-BC drift (watch 5 episodes; re-steer via the provincial
   search queries if it persists).
