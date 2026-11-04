# Oct 9 2026, later still — the narrative shows get sources

Moved verbatim from CLAUDE.md on 2026-11-03; the rules that still bind are summarised there.

**Oct 9 2026, later still — the narrative shows get sources** (register
`narrative-research-2026-10-09`; guards
`tests/test_narrative_research_2026_10_09.py`). Unintended Consequences
and First Principles wrote from the topic brief and nothing else — no
article ever reached the episode prompt, every Sources list was empty, UC
verified 0 claims in eight episodes. Now `narrative_research: N` runs ONE
web search for the picked topic (`engine.fetcher.fetch_topic_research_articles`
— ANY date, `exempt_stale`, `source_kind: research`; the news searcher
drops anything older than 72 h and a 1935 cane toad is the point), merges
the results beside the hook articles (so they reach `fetch_full_text`,
`news_section` and the claims gate like a fetched item) and renders them
into both `*_episode.txt` prompts as `{research_sources}` with an honest
fallback line when the search returns nothing — an empty search never
skips an episode. **The claims gate never verifies against the search
model's summary**: `build_local_texts` reads only the title and the fetched
PAGE for a research article (`full_text_source: page`, which
`enrich_articles_with_full_text` now fetches regardless of description
length), else the claim goes to HTTP. ⚠️ AUDIO on both shows (prompt and
input changed) — A/B-listen Ep1.
