# Oct 11 2026 — a narrative show writes only from sources

Moved verbatim from CLAUDE.md on 2026-11-03; the rules that still bind are summarised there.

**Oct 11 2026 — a narrative show writes only from sources** (review:
[`docs/reviews/slate_review_2026_10_11.md`](docs/reviews/slate_review_2026_10_11.md);
register `slate-2026-10-11`; guards `tests/test_slate_2026_10_11.py`). UC
Ep139 aired an invented case (Argentina licensing toothfish off South Georgia,
a British territory) from a restock-written brief with 0 research sources;
correction filed. **`narrative_research_min: 2`** on UC and FPD: fewer
sources tries the next topic (up to three, `pick_next_topic(exclude_ids=)`),
then skips `narrative_research_thin` — never a case from memory; a topic is
annotated only when the search WORKED and came back thin (an outage also
returns `[]`). **@grok is a research desk, never a source**
(`engine/grok_leads.py`, `grok_leads:` on SpaceX/Tesla/M&A/AI Chips): its
topical explainer replies become writer-only deep-dive ANGLES
(`{deep_dive_leads}`), each kept only when two primary PAGES were fetched for
it; the reply is never an article, a Source line or claims evidence (an X
post's text verifies by local copy, so a @grok reply "verified" only that
Grok said it — SpaceX Ep127). Metrics `grok_leads_found/kept`,
`grok_lead_sources`. SpaceX deep-dive numbers come from the digest, a
constant, or a labelled estimate. Mira's live prompt states the guest's built terms.
Desk/Top World **Both Sides is optional** (prompt and validator) — it runs
only on a named disagreement. The AI Chips / MAG 7 teaser never restates the
calendar item just read (this reverses the Sep 23 "teaser names the nearest
item"). **Visuals:** story briefs top the image set up to `MIN_STORY_SET` (4),
never pad it to `count` with static `image_queries`; duplicate briefs collapse;
essay sections supply scene contexts; dub thumbnails use a scene; a decimal
title keeps its number. **Workflows:** multilingual concurrency is per SHOW on
the translate job (a workflow-level group cancels pending runs) and a show
that skipped today is not swept; Nerra Daily's links call gets a second
attempt and names why a reply was refused, and its fallback speaks full hooks,
never a "…" title; **The Age of AI renders its own waveform video** when the
edit path left none (0 uploads since Sep 20) and caps feed titles through
`engine.titles`. ⚠️ AUDIO: Mira, FF/PT, Tesla X Takeover, MIT Market
Mechanics, SpaceX deep dive, Both Sides, the Sunday segment, the two teasers.
