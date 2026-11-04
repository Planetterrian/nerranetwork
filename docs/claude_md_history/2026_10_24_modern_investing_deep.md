# Modern Investing: the stop is enforced, the factors are measured, the record leads (Oct 24 2026)

Moved verbatim from CLAUDE.md on 2026-11-03; the rules that still bind are summarised there.

### Modern Investing: the stop is enforced, the factors are measured, the record leads (Oct 24 2026)

Operator-directed deep review (review
[`docs/reviews/modern_investing_review_2026_10_24.md`](docs/reviews/modern_investing_review_2026_10_24.md);
ledger `modern_investing` 2026-10-24; register `mit-deep-review-2026-10-24`;
guards `tests/test_mit_review_2026_10_24.py`). The era record reconciles to
the cent (36 closed trades, −0.76% average alpha, 17 beat the index) but its
published rules were partly in force. Rules that bind:

- **A stop is whatever loss the pick states, and the percent form wins.**
  The sim could read a stop on 9 of 41 era picks: "maximum acceptable loss
  8 percent" was not a shape it knew, and "stop-loss set 6 percent below
  entry to limit loss to roughly $60" recorded a **$60 stop on an $82.75
  stock** (GM Ep206, published in the ledger as a 27% stop). Now a
  maximum-loss sentence is the stop, whichever form comes first wins, the
  $1,000 position size is never a stop, `_stop_already_breached` carries
  `_close_trade`'s sanity guard, and **open trades' stops are re-read from
  their committed digests every run** (`_refresh_open_stops`). The digest
  carries a required `**Stop-Loss:**` line and the `pick_stop_loss` lint
  regenerates a pick without a readable one.
- **The loop measures the market's record, not the writer's exposure.**
  `rules_in_effect` says which rule TEXT was shown; the four active rules
  were one constraint in four scopes, so every with/without comparison was
  one sample twice. `_entry_factors` records the entry day's volume against
  its 20-session average and the entry open against the 50-session average
  from the bars at close (`_backfill_entry_factors` stamps eight older era
  trades a run); `_build_factor_scoreboard` scores alpha with and without
  each condition — "not measurable yet" under five a side, a finding only at
  ten a side with mean AND median agreeing. First read on 36 trades: the
  show's most repeated rule (volume above the 20-day average) is NOT paying
  (−2.86% alpha on 14 vs +0.57% on 22). The ledger carries the columns.
- **The trade review hands the model the tracker's NASDAQ window and alpha**
  — it never had, and 6 of 8 spoken verdicts in Ep199–210 were invented
  (the day's −0.10% pasted onto six-day windows) — plus the stated
  confidence, invalidation and stop so the review grades the forecast; the
  hold is counted in sessions; the lifetime running total and win rate are
  gone from the block (they were the 87-trade blend the Aug 18 restart
  exists to keep off the air).
- **Portfolio Performance leads with the era** and labels the lifetime
  block HISTORY ONLY whenever the era has trades (best/worst out); the
  compounded-to-average basis change of Oct 22, which moved the headline
  32 points between Ep208 and Ep209 with nothing said, is explained once
  (`BASIS_NOTE_EPISODES` 2, stamped in `metadata.basis_note_episodes`).
- **Budgets, counted from the recorded picks, where prose failed:**
  `_confidence_budget_block` (five Mediums → the next pick is High or Low by
  factor count; 44 of 44 era picks were Medium) and
  `_options_cadence_block` (ten share picks → the next is a covered call or
  cash-secured put on a US-listed name; 0 options in 103 trades). Dashboard
  `mit_stop_stated_share_10ep`, `mit_non_medium_share_10ep`.
- Also: the extractor reads the digest's `**Sector:**` line (27 of 44 era
  picks were "other") and accepts `TSX:H` (Ep205's pick was lost); the
  narrative callback recalls each trade once; the validator requires
  Investor Education and Portfolio Performance (Ep208 shipped without the
  first); the public method doc, performance page and show page lead with
  the era record and describe the rulebook — "one position at a time" and
  the Monday-pick/Friday-close model were false on every surface. The
  recompute `--apply` stays the operator's. ⚠️ AUDIO — three prompts
  changed (rulebook cadence, Spotlight worked example, forecast-graded
  review, era-first record, de-seeded "parking spot" / "habit to copy" /
  per-tool disclosure): A/B-listen the first two episodes.
