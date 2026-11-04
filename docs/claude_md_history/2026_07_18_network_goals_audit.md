# Network goals & differentiation audit (July 18, 2026)

Moved verbatim from CLAUDE.md on 2026-11-03; the rules that still bind are summarised there.

### Network goals & differentiation audit (July 18, 2026)

Operator-requested whole-network review — canonical writeup:
[`docs/reviews/network_review_2026_07_18.md`](docs/reviews/network_review_2026_07_18.md).
Verdict: the factory is world-class (100% run success, ~90 eps/week in 5
languages at ~$35-40/mo) while the funnel is the product gap (3,070
downloads/30d, 3 newsletter subs); differentiation is TOPICAL AUTHORITY
(Tesla+M&A+SpaceX = 53% of downloads), and the two most differentiated bets
(DP Pod, Age of AI) have no market feedback loop. Shipped (all
code/metadata-only): **closing-is-final chapter invariant** in
`engine/chapters.py` (the 07-16 rotating network outro's sibling-show plugs
were stolen by un-anchored body markers AFTER the closing — Tesla Ep544
"First Principles" at 642s, MIT Ep104 "Investor Education"; terminal signal
is the closing TITLE set, not the `where: end` anchor, because EI anchors
only its Teaser); **dp_pod Network-pick rotation memory**
(`_recent_network_picks` — FF was the pick 5/10 with a fixed host+frame); **July 20 2026 Ep016 name-swap fix + banter pass (operator listened:
  hosts signed off as each other; wants human flow + comedic banter):**
  the LLM rotated the supplied closing's speaker labels to dodge a
  same-host boundary (turn before the closing and the closing's first
  line were both DAN's), so Dan's voice said "I'm Patrick Novak" on air.
  Two-layer fix: `_fix_self_introduction_labels` in
  `engine/tts_dialogue.py` relabels any turn whose self-intro names the
  OTHER host (deterministic; joint intros untouched; verified self-healing
  on the real Ep016 script), and the podcast prompt forbids closing-label
  rotation outright. Flow: Ep014-016 shipped ZERO exclamations, ZERO
  voice tags, 12-26% one-liners against the DELIVERY asks — enforcement
  moved INTO the Positive Papers segment spec (per-story 3+ turn volley +
  earned exclamation) and a COMEDY block (2-3 character-driven beats,
  one callback, device rotates daily, no catchphrases). Prompt edits
  change shipped audio — A/B-listen per landmine #17. Drift guards:
  `tests/test_tts_dialogue.py::TestSelfIntroductionRelabel`,
  `tests/test_dp_pod_show.py::TestEp016NameSwapAndBanter`;
**dashboard voice-baseline fix** (stale ElevenLabs RU baseline flagged
FP/PR/Age-of-AI as drift on every build; now Olya `0b875ae2` + sanctioned
`ara`); **snapshot fetch-filter leakage counter** (scored three long-pending
filter predictions immediately: SpaceX/Tesla clean, FF ephemeris still
leaking 3/10 → reopened); **playbook category rules** from the 15-ledger
meta-review (podcast-side length levers formally banned network-wide via
`do_not_retry` — ~10 misses vs 1 hit; de-seed-by-shape + rotation memory
required; conditional predictions banned; two-miss escalation; ledger entry
required for every prediction-bearing pass). Verified with new data: the
07-16 denoise chain IS engaged in shipped audio (re-denoising shipped
episodes removes ~0 dB). P0 operator item: **FP/PR publish off-schedule via
the daily-audit retry path** — CRON_MAP/Worker say Monday-only,
`review_episodes.py` says even days, FP's description says daily; 8
unplanned episodes in one week; pick a cadence and align all three. A/B
proposals (NOT applied): FP double-seeded templates (100% saturation), MIT
seeded transition, PT takeaway tic, PR secret opener, FF ephemeris
digest-scope bullet. Drift guards:
`tests/test_chapters.py::TestClosingIsFinal`,
`tests/test_dp_pod_show.py::TestNetworkPickRotationMemory`,
`tests/test_review_agent.py::{TestSnapshotFetchFilterLeakage,TestDashboardVoiceBaseline}`.
