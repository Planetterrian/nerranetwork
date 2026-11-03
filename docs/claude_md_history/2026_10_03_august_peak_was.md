# Oct 3 2026 — the August peak was @NerraRU, and what fell was reach per video

Moved verbatim from CLAUDE.md on 2026-11-03; the rules that still bind are summarised there.

**Oct 3 2026 — the August peak was @NerraRU, and what fell was reach per
video** (review: [`docs/reviews/youtube_and_shows_review_2026_10_03.md`](docs/reviews/youtube_and_shows_review_2026_10_03.md);
guards `tests/test_show_review_2026_10_03.py`,
`tests/test_dub_short_titles_2026_10_03.py`). Network views ~44k/week
(08-03, 08-10) → ~20k (09-14, 09-21); RU Shorts were ~75% of them and
their median fell 260–400 → ~50 with uploads, retention and the country mix
unchanged; EN is at its early-August level. Our own volume cuts priced at
~6% of the loss. Rules that bind: **rebuild a daily series from the
snapshot history** (`git log -- api/youtube_stats.json`; a blobless clone
reads it — the CI checkout is depth-1) before calling a trend; **the body
opens on the story the cold open sold** (`build_cold_open_spec` bullet;
`script_hook_leads_body_pct` reads it — Tesla 82% / MAB 92% off since 09-22
while SpaceX, which held its long-form retention, was 25%); **a dub
window-Short title is written from `ScoredWindow.window_text` and never
ships `engine.titles.is_fragment_title`** — the fallback is the episode
headline + tail, tag last; **the sibling plug's cadence word comes from
`engine.cadence`**. Open: the 08-18..21 RU blackout (all Shorts 1–8 views,
no code change, self-recovered) — a Studio read, not a code fix.
