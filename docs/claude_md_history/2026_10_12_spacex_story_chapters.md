# Oct 12 2026, later — SpaceX story chapters and @grok leads

Moved verbatim from CLAUDE.md on 2026-11-03; the rules that still bind are summarised there.

**Same day, later — SpaceX story chapters and @grok leads** (register
`spacex-story-chapters-and-grok-leads-2026-10-12`). **A `known_sections_only`
show gets story chapters, headline used whole**: a digest headline anchored
where its story begins in any body chapter, only when it fits
`engine.titles.HEADLINE_CHAPTER_TITLE_MAX` (80) — never a clipped title, never
the fixed-interval / first-sentence fallback (SpaceX had eight stories inside
"Introduction" on every episode). **@grok leads search subject by subject**
(`engine.grok_leads.lead_subjects`): one search over the whole beat found 0
leads; a probe found 2-4 per show with one search per subject. Request shape
was never the problem — `scripts/probe_x_search.py` (Actions "Probe x_search",
read-only) compares shapes and prompts with the real key; read it before
changing an x_search request. @SpaceX returns 0 posts from x_search with or
without a handle filter (xAI's index). ⚠️ AUDIO: SpaceX segment order.
