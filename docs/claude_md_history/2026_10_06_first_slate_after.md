# Oct 6 2026 — the first slate after those merges

Moved verbatim from CLAUDE.md on 2026-11-03; the rules that still bind are summarised there.

**Oct 6 2026 — the first slate after those merges** (register
`slate-2026-10-06`; guards `tests/test_slate_2026_10_06.py`). Every Oct 5
target held on its first episode; **Modern Investing published nothing.**
The share-class fix priced HPS.A 40 days late, the benchmark's fixed
one-month fetch could not reach its entry bar, the trade closed with no
alpha, and one `+= None` in the strategy-performance sum dropped the whole
pre-fetch hook — after which the digest prompt died on a missing variable.
Rules that bind: **a benchmark window reaches the entry bar**
(`_period_covering`, never narrower than a month); **a missing alpha is
never a zero** (averages over the trades that carry one); **the MIT hook's
analysis blocks fail one at a time** (`_section`, `::error::` +
`mit_prefetch_failed_sections`) — the record (trade review, portfolio,
indices, benchmark) stays unguarded on purpose. **The claims metrics record
what SHIPS**: `source_integrity_claims` / `_verified` are re-written after
repair and the coverage floor (`_pre_floor` keeps the first reading);
Tesla Ep626 had read 2 beside a committed ledger of 7.
