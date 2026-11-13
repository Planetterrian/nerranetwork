# Mission Control's three views (Aug 2026)

Moved verbatim from CLAUDE.md on 2026-11-13 (size cap); the binding rules stay there in one line.

The page carries **three views** (Aug 2026): Operator (everything),
Sponsor (`?view=sponsor` — audience + catalogue, no spend/valuation) and
**Investor** (`?view=investor` — audience, unit economics, industry
benchmarks and now/1yr/5yr value scenarios). Every external market figure
(percentile ladder, CPMs, production costs, M&A multiples) lives ONLY in
[`docs/industry_benchmarks.yaml`](docs/industry_benchmarks.yaml) with
sources + an `as_of` date the page renders; the generator's
`build_benchmarks_section` / `build_investor_section` compute placement
and scenarios from the same audience/cost sections the rest of the page
uses. Honesty rules: episode denominators come from RSS pubDates (credit
files count dub tracks and overstate episodes), unmeasured = null never 0,
projections are labelled scenarios with their assumptions serialized next
to them. Drift guards: `tests/test_investor_dashboard.py`.
