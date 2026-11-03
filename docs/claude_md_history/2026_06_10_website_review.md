# Website review (June 10, 2026)

Moved verbatim from CLAUDE.md on 2026-11-03; the rules that still bind are summarised there.

### Website review (June 10, 2026)

Full public-site review — canonical writeup:
[`docs/website_review_2026_06_10.md`](docs/website_review_2026_06_10.md);
drift guards: `tests/test_website_quality_pass.py`. Implemented (source-only,
propagates via nightly regen): absolute `og:image` default in
`templates/base.html.j2` (the relative default broke share previews on every
page without an explicit `og_image`); `noindex` on the 404 template; footer
Gallery link (287 CC-licensed images were reachable from nowhere);
`MIN_SOCIAL_PROOF_SUBSCRIBERS` 100→50. Deferred with rationale in the doc:
blog-index pagination, hero inline-CSS extraction, homepage gallery rail,
Russian brand-page translations, inline-style cleanup, contrast audit.
Rejected after verification: nav-cover empty alts (correct WCAG — visible
text adjacent), search loading state (already exists), blog next-episode nav
(already exists).
