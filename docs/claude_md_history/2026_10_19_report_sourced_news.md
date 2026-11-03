# Report the sourced news, never discard it (Oct 19 2026)

Moved verbatim from CLAUDE.md on 2026-11-03; the rules that still bind are summarised there.

### Report the sourced news, never discard it (Oct 19 2026)

Operator-directed (register `report-more-sourced-news-2026-10-19`; guards
`tests/test_report_more_sourced_news_2026_10_19.py`). Measured Oct 13-19: a
show fetched 50-480 articles, the prompt listed at most 40 of them, the digest
carried 6-15 items (8-25% of the list), and the prompts said why — "prefer
fewer stories at full depth", "7 stories properly, not 12 shallowly", the
desks' "3 to 5" Also Today cap — so the rest of a sourced day was cut before
anyone heard it. Rules that bind: **every news digest carries an Also Today
run** (`shows/prompts/_shared/also_today.txt` on 14 digest prompts; the desks'
own section is uncapped now; MAB's Quick Bits and MIT's Quick Hits are the same
run under their names; Top World's items 6-10 already are) — one sentence per
remaining qualifying story, the count follows the day, omitted under two, and
a story that earns only a sentence goes THERE rather than being dropped (the
depth lines and the expansion retry say so; the selection tests still apply,
so a birthday or a price move does not qualify). The run is spoken as a brisk
run after the last developed story (`content_discipline.txt`; ⚠️ AUDIO —
A/B-listen one flagship and one desk) and chaptered on its digest section.
**The prompt lists `DEFAULT_MAX_PROMPT_ARTICLES` (60) articles**
(`ShowConfig.max_prompt_articles`; the literal 40 is gone). The run sits
outside every developed section's validator span, so item floors still
measure developed items. Readout: `articles_in_prompt`, `items_shipped`,
`digest_also_today_items`, `prompt_articles_reported_pct` per episode;
`prompt_articles_reported_pct_7d` / `also_today_items_7d` on the dashboard.
