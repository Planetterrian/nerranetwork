# Network editorial review (July 2026)

Moved verbatim from CLAUDE.md on 2026-11-03; the rules that still bind are summarised there.

### Network editorial review (July 2026)

Full editorial pass over every transcript in the 2026-06-18 → 07-02 window
(~150 episodes, all 13 shows — fit, interest, content quality, positioning).
Canonical writeup:
[`docs/reviews/network_review_2026_07_02.md`](docs/reviews/network_review_2026_07_02.md);
prediction verdicts + new entries in every per-show ledger
([`docs/reviews/ledger/`](docs/reviews/ledger/) — new ledgers for
privet_russian, modern_investing, network). Four cross-cutting classes:
(1) **number/name garbles in flagship positions** — the comma-blind
currency/ordinal formatter shipped "fifty-nine dollars,990"-class hooks on
Tesla/SpaceX (fixed, `assets/pronunciation.py`); (2) **guard/retry mechanisms
degrading the audio they protect** — the missing-closing guard's literal
signature match double-spoke MAB's closing 5/15 (fixed: fuzzy match in
`engine/pipeline.py`) and the expand-below-target retry pads by
paraphrase-duplication (fixed: near-duplicate sentence stripping);
(3) **third-generation seeded-template convergence** (OV "Both sides
agree…" 12/12, EI "There's a nuance here…" 6/6, MAB/FP/MIT/SpaceX tics) —
ALL prompt de-seeds are PROPOSED-not-applied pending operator A/B (landmine
#17); meta-lesson: de-seed by shape, never with a quotable example;
(4) **same-day sibling overlap** — PT astronomy fetch filter (the pass's
highest-leverage fix), FF lookback 2→7 + ephemeris filter, SpaceX junk-title
filter. Also shipped: EI Closing/Teaser-before-body chapter reorder, MIT
voided phantom trades (honest 37-trade record + review-once), PR vocab
no-reteach 8 + WOTD never-repeat + theme gap, network-wide Source-line scrub
(FP scaffold leak), UC/FPD queue hygiene, Tesla second-brand-normalizer
completion, and `review_snapshot.py` Unicode + missing-final-Closing fixes.
Operator items: three same-day double-publishes + SpaceX's silently missed
June-28 recap (scheduler forensics).
