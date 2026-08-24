# Citation-shape exposure across the published corpus

> **A count is a floor, not a measurement. These patterns detect known
> fabrication templates; novel shapes are not detected.** Tested against 14
> fabrications independently verified by hand fact-check, the template set
> this report was measured with caught **4 of 14 (28%)** — the counts below
> measure *one template*, not exposure. Superseded by
> [`citation_exposure_2026_08_23.md`](citation_exposure_2026_08_23.md)
> (widened pattern set); this file is retained because the delta between the
> two is the useful artifact.

Measured 2026-08-22 by `scripts/measure_citation_exposure.py` — deterministic regex counts of citation-shaped constructions (`engine.claims.CITATION_SHAPE_PATTERNS`, the fabrication signature) over every committed digest `.md`. A count is EXPOSURE, not a verdict: each match is a sentence asserting provenance that no ledger backs, which may be true, stale, or invented — unverifiable either way.

This ranking is the triage order for the backfill (soften-in-place / re-source / regenerate — operator decision per show).

| Show | Episodes | With shapes | Shapes | Per episode |
|---|---:|---:|---:|---:|
| unintended_consequences | 97 | 41 | 54 | 0.56 |
| planetterrian | 136 | 47 | 57 | 0.42 |
| dp_pod | 24 | 7 | 7 | 0.29 |
| omni_view | 149 | 16 | 21 | 0.14 |
| models_agents_beginners | 136 | 7 | 9 | 0.07 |
| spacex | 77 | 4 | 4 | 0.05 |
| tesla_shorts_time | 187 | 9 | 9 | 0.05 |
| fascinating_frontiers | 138 | 5 | 5 | 0.04 |
| first_principles | 78 | 3 | 3 | 0.04 |
| modern_investing | 147 | 6 | 6 | 0.04 |
| env_intel | 62 | 2 | 2 | 0.03 |
| models_agents | 150 | 5 | 5 | 0.03 |
| finansy_prosto | 73 | 0 | 0 | 0.00 |
| nerra_daily | 2 | 0 | 0 | 0.00 |
| offshore_north | 1 | 0 | 0 | 0.00 |
| privet_russian | 66 | 0 | 0 | 0.00 |

## Highest-exposure episodes (top 20)

- **digests/unintended_consequences/Unintended_Consequences_Ep071_20260727.md** — 4 (`Estimates from`, `Internal documents`, `Internal memos`, `researchers documented`)
- **digests/models_agents_beginners/MAB_Ep079_20260621.md** — 3 (`Researchers noted`, `according to The D`)
- **digests/omni_view/Omni_View_Ep103_20260705.md** — 3 (`analysts noted`, `researchers noted`)
- **digests/unintended_consequences/Unintended_Consequences_Ep069_20260725.md** — 3 (`A 2018 study`, `Estimates from`, `a 2014 study`)
- **digests/omni_view/Omni_View_Ep035_20260421.md** — 2 (`according to the c`, `according to the r`)
- **digests/omni_view/Omni_View_Ep054_20260518.md** — 2 (`Analysts noted`, `analysts noted`)
- **digests/omni_view/Omni_View_Ep144_20260815.md** — 2 (`according to a s`, `according to the U`)
- **digests/planetterrian/Planetterrian_Daily_Ep027_20260307.md** — 2 (`Researchers found`, `studies showed`)
- **digests/planetterrian/Planetterrian_Daily_Ep032_20260320.md** — 2 (`Researchers found`, `researchers found`)
- **digests/planetterrian/Planetterrian_Daily_Ep038_20260331.md** — 2 (`Researchers found`)
- **digests/planetterrian/Planetterrian_Daily_Ep078_20260603.md** — 2 (`Researchers documented`, `researchers documented`)
- **digests/planetterrian/Planetterrian_Daily_Ep085_20260610.md** — 2 (`researchers documented`, `studies found`)
- **digests/planetterrian/Planetterrian_Daily_Ep109_20260703.md** — 2 (`Researchers documented`, `scientists found`)
- **digests/planetterrian/Planetterrian_Daily_Ep117_20260711.md** — 2 (`Researchers documented`, `researchers documented`)
- **digests/planetterrian/Planetterrian_Daily_Ep124_20260718.md** — 2 (`Researchers documented`, `Researchers found`)
- **digests/planetterrian/Planetterrian_Daily_Ep134_20260728.md** — 2 (`Researchers documented`, `researchers found`)
- **digests/planetterrian/Planetterrian_Daily_Ep150_20260813.md** — 2 (`Researchers found`, `a 2023 study`)
- **digests/unintended_consequences/Unintended_Consequences_Ep015_20260522.md** — 2 (`estimates from`, `researchers noted`)
- **digests/unintended_consequences/Unintended_Consequences_Ep016_20260525.md** — 2 (`Estimates from`, `according to the s`)
- **digests/unintended_consequences/Unintended_Consequences_Ep026_20260609.md** — 2 (`A 2007 survey`, `analysts noted`)

## Pattern breakdown (network-wide)

- `\b(?:researchers|scientists|analysts|officials) (?:found|noted|estimated|documented)\b` — 79
- `\baccording to (?:a|an|the) [a-z]` — 45
- `\bestimates (?:from|compiled by)\b` — 17
- `\ba \d{4} (?:study|paper|report|memo|survey|analysis|bulletin|note)\b` — 15
- `\bstudies (?:later )?(?:showed|estimated|found)\b` — 10
- `\binternal (?:documents|memos|reports)\b` — 9
- `\bmost accounts\b` — 7

