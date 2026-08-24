# Citation-shape exposure across the published corpus

> **A count is a floor, not a measurement. These patterns detect known fabrication templates; novel shapes are not detected.** The Aug 22 report's original template set caught 4 of 14 hand-verified fabrications — a low per-show number here is not evidence of health.

Measured 2026-08-24 by `scripts/measure_citation_exposure.py` — deterministic regex counts of citation-shaped constructions (`engine.claims.CITATION_SHAPE_PATTERNS`, the fabrication signature) over every committed digest `.md`. A count is EXPOSURE, not a verdict: each match is a sentence asserting provenance that no ledger backs, which may be true, stale, or invented — unverifiable either way.

This ranking is the triage order for the backfill (soften-in-place / re-source / regenerate — operator decision per show).

| Show | Episodes | With shapes | Shapes | Per episode |
|---|---:|---:|---:|---:|
| unintended_consequences | 98 | 54 | 83 | 0.85 |
| planetterrian | 137 | 56 | 73 | 0.53 |
| dp_pod | 25 | 7 | 7 | 0.28 |
| omni_view | 150 | 19 | 25 | 0.17 |
| models_agents_beginners | 137 | 8 | 10 | 0.07 |
| first_principles | 79 | 5 | 5 | 0.06 |
| tesla_shorts_time | 188 | 11 | 11 | 0.06 |
| fascinating_frontiers | 139 | 7 | 7 | 0.05 |
| spacex | 78 | 4 | 4 | 0.05 |
| modern_investing | 148 | 6 | 6 | 0.04 |
| env_intel | 62 | 2 | 2 | 0.03 |
| models_agents | 151 | 5 | 5 | 0.03 |
| finansy_prosto | 73 | 0 | 0 | 0.00 |
| nerra_daily | 3 | 0 | 0 | 0.00 |
| offshore_north | 1 | 0 | 0 | 0.00 |
| privet_russian | 66 | 0 | 0 | 0.00 |

## Highest-exposure episodes (top 20)

- **digests/unintended_consequences/Unintended_Consequences_Ep071_20260727.md** — 7 (`Estimates from`, `In 1952, the Lorillard Tobacco Company introduced`, `Internal documents`, `Internal memos`, `The Federal Trade Commission briefly required tar-and-nicotine disclosures in 1957`, `memo from British American Tobacco observed that “`)
- **digests/models_agents_beginners/MAB_Ep079_20260621.md** — 3 (`Researchers noted`, `according to The D`)
- **digests/omni_view/Omni_View_Ep103_20260705.md** — 3 (`analysts noted`, `researchers noted`)
- **digests/planetterrian/Planetterrian_Daily_Ep078_20260603.md** — 3 (`Researchers documented`, `monitoring across managed forests showed`, `researchers documented`)
- **digests/planetterrian/Planetterrian_Daily_Ep109_20260703.md** — 3 (`Researchers documented`, `Sampling of cats and their fleas in the region detected`, `scientists found`)
- **digests/unintended_consequences/Unintended_Consequences_Ep032_20260617.md** — 3 (`Estimates compiled by`, `In 1962 the World Health Organization issued`, `compiled by the A`)
- **digests/unintended_consequences/Unintended_Consequences_Ep069_20260725.md** — 3 (`A 2018 study`, `Estimates from`, `a 2014 study`)
- **digests/unintended_consequences/Unintended_Consequences_Ep072_20260728.md** — 3 (`a 1975 paper`, `engineer Nils Bohlin, who filed the patent in 1959 after studying crash data that showed`, `researchers documented`)
- **digests/unintended_consequences/Unintended_Consequences_Ep094_20260819.md** — 3 (`A 2008 paper`, `A 2012 study`, `chemist Arlene Blum and the biochemist Bruce Ames showed`)
- **digests/omni_view/Omni_View_Ep035_20260421.md** — 2 (`according to the c`, `according to the r`)
- **digests/omni_view/Omni_View_Ep054_20260518.md** — 2 (`Analysts noted`, `analysts noted`)
- **digests/omni_view/Omni_View_Ep132_20260803.md** — 2 (`according to a r`, `survey of UK factories showed`)
- **digests/omni_view/Omni_View_Ep144_20260815.md** — 2 (`according to a s`, `according to the U`)
- **digests/planetterrian/Planetterrian_Daily_Ep027_20260307.md** — 2 (`Researchers found`, `studies showed`)
- **digests/planetterrian/Planetterrian_Daily_Ep032_20260320.md** — 2 (`Researchers found`, `researchers found`)
- **digests/planetterrian/Planetterrian_Daily_Ep038_20260331.md** — 2 (`Researchers found`)
- **digests/planetterrian/Planetterrian_Daily_Ep051_20260427.md** — 2 (`Data compiled by the B`, `compiled by the B`)
- **digests/planetterrian/Planetterrian_Daily_Ep085_20260610.md** — 2 (`researchers documented`, `studies found`)
- **digests/planetterrian/Planetterrian_Daily_Ep093_20260618.md** — 2 (`survey of Australian native bees found`, `testing across multiple ape species revealed`)
- **digests/planetterrian/Planetterrian_Daily_Ep112_20260706.md** — 2 (`Researchers documented`, `measurements in large population datasets and found`)

## Pattern breakdown (network-wide)

- `(?i)\b(?:researchers|scientists|analysts|officials) (?:found|noted|estimated|documented)\b` — 80
- `(?i)\baccording to (?:a|an|the) [a-z]` — 46
- `(?i)\b(?:sampling|testing|monitoring|surveys?|measurements?|audits?)\s+(?:in|across|of|at)\s+[^.]{0,70}?\b(?:detected|found|showed|revealed|recorded|documented)\b` — 20
- `(?i)\bestimates (?:from|compiled by)\b` — 18
- `(?i)\ba \d{4} (?:study|paper|report|memo|survey|analysis|bulletin|note)\b` — 13
- `(?i)\bstudies (?:later )?(?:showed|estimated|found)\b` — 10
- `(?i)\binternal (?:documents|memos|reports)\b` — 9
- `\b(?:[Ii]n|[Bb]y)\s+\d{4},?\s+the\s+[A-Z][\w'&.\- ]{3,50}?\s+(?i:issued|published|released|adopted|recommended|established|introduced|required|banned|mandated|approved|suspended)\b` — 9
- `(?i)\bmost accounts\b` — 7
- `\b[Tt]he\s+[A-Z][\w'&.\- ]{3,50}?\s+(?i:briefly\s+|formally\s+|first\s+|quietly\s+)?(?i:issued|published|adopted|recommended|established|introduced|required|banned|mandated|approved|suspended|authorized)\b[^.]{0,60}?\bin\s+\d{4}\b` — 5
- `\b(?i:physician|pharmacologist|chemist|biologist|economist|engineer|scientist|professor|researcher|historian|epidemiologist|statistician)\s+(?:Sir\s+|Dr\.?\s+)?[A-Z][a-z]+\s+[A-Z][a-z]+\b[^.]{0,80}?\b(?i:noted|found|warned|observed|argued|reported|showed|concluded|estimated)\b` — 5
- `\b(?i:tracked|compiled|catalogued|documented|maintained|preserved)\s+by\s+the\s+[A-Z]` — 4
- `(?i)\bcontemporary\s+(?:accounts?|records?|reports?|sources?|documentation)\s+(?:describe|record|show|indicate|note|suggest|confirm)\b` — 3
- `(?i)\baccording to\s+(?:surveys?|data|figures|records|analyses?|estimates?|reports?|research)\s+(?:by|from|conducted by)\b` — 2
- `\b(?i:records|documents|archives|papers|files|data|figures|statistics)\s+(?i:(?:are|were|is|now)\s+)?(?i:preserved|held|housed|maintained|tracked|compiled|collected|published)\s+(?i:by|at|in)\s+(?:the\s+)?[A-Z]` — 2
- `(?i)\b(?:accounts?|records?|reports?|sources?)\s+from\s+the\s+(?:period|time|era|day)\b` — 2
- `(?i)\ba\s+\d{4}\s+[\w\- ]{0,35}?(?:journal|magazine|newspaper|publication|periodical|trade press|newsletter)\b` — 2
- `(?i)\b(?:memo|memorandum|report|study|letter|document|paper|bulletin)\b[^.]{0,90}?\b(?:observed|noted|stated|concluded|said|wrote|argued)\s+that\s+[\"'‘“]` — 1


## Delta vs the 2026-08-22 report (the useful artifact)

The template set was widened after hand fact-check showed the original 8
patterns caught **4 of 14 (28%)** independently verified fabrications. The
widened set (18 patterns) catches **14 of 14**, pinned by
`tests/test_citation_shapes.py`.

| Measure | 2026-08-22 (8 patterns) | 2026-08-23 (18 patterns) |
|---|---:|---:|
| Digests scanned | 1,523 | 1,535 |
| Citation shapes | 182 | 238 |
| Episodes with shapes | 152 | 184 |
| unintended_consequences per-ep | 0.56 | **0.85** (+52%) |
| planetterrian per-ep | 0.42 | **0.53** (+26%) |

New-pattern hits: **55**. The biggest movers are exactly the shows whose
formats invite invented provenance — UC's history essays (dated
institutional actions, archival records, quoted documents) and
Planetterrian's study summaries (attributed empirical findings).

## Precision of the widened patterns (hand-classified, 2026-08-23)

Per WO-1: 40 of the 55 new-pattern hits were sampled at random
(seed 20260823) and hand-classified. **TP** = the sentence genuinely
asserts a provenance-bearing fact (attributed study/survey/data, dated
institutional action, named expert, archival record, quoted document) —
i.e., the flag is actionable: the sentence needs a ledger entry or the
general form. TP does **not** mean the claim is false — on the news shows
many flagged sentences summarize real, source-linked studies.

- **Post case-fix precision: 40/40 TP (100%) on the sample.** The 15
  unsampled hits were also eyeballed: all provenance-bearing, no
  mechanical misfires.
- **The case-sensitivity fix is what got it there.** The first measurement
  pass compiled every pattern `IGNORECASE`, which nullified the `[A-Z]`
  named-entity anchors; the same 40-hit sample then contained at least 7
  clear misfires (~82% precision) — "data collected by the rover's
  instruments", "the record cadence established in 2025", "the first
  versions of the algorithmic News Feed introduced in 2011", an
  Anthropic reported-speech fragment. Case handling now lives inside each
  pattern and a comment in `engine/claims.py` pins why.
- **Noisiest surviving class:** dated corporate/institutional actions
  ("In 1952, the Lorillard Tobacco Company introduced the Kent
  cigarette…"). Counted TP because invented institutional history is a
  verified fabrication category (the FTC-1957 claim; "the 1947 Rent
  Control Law" which never existed), but these are the flags most likely
  to be true-and-easily-sourced during backfill.

Both figures clear WO-1's ~60% floor with a wide margin; no tightening
beyond the case fix was needed.
