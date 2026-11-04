# Provenance — Oct 5 2026: the coverage floor reads the item's OWN source

Moved verbatim from CLAUDE.md on 2026-11-03; the rules that still bind are summarised there.

**Oct 5 2026 — the coverage floor reads the item's OWN source.** It had
added one verified claim in 24 flagship episodes: it asked the model to
name a fetchable page for each uncovered item from memory, and a truthful
model answered `[]` (Tesla Ep624, SpaceX Ep120) while every item already
cited its Source and the run held the fetched copy. Now
`attempt_item_coverage_repair` pins each item's Source URL and hands over
the passage of it that discusses the sentence (fetched copy first, then
the page); the model only judges support and copies the quote, and the
mechanical check is unchanged. Entries are added only when each verifies
on its own, the result is kept only when the gate verifies more and gets
no worse, and the floor now runs on a FAILING gate in flag mode too (it
never touches the failing entries). One `item coverage floor:` log line
gives the counts. Register `claims-coverage-grounded-2026-10-05`; guards
`tests/test_claims_coverage_grounded_2026_10_05.py`.
