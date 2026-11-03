# The front page and the share cards (Oct 18 2026)

Moved verbatim from CLAUDE.md on 2026-11-03; the rules that still bind are summarised there.

### The front page and the share cards (Oct 18 2026)

Operator-directed: the landing test becomes the homepage, a news site's front
page; every shared link gets a proper preview. Guards
`tests/test_homepage_landing_2026_10_18.py`, `tests/test_share_cards_2026_10_18.py`;
docs `docs/landing_test.md` ("v3 — the homepage"). Rules that bind:

- **`index.html` is the front page** (`generate_network_page`, template
  `network_page.html.j2` — the old homepage template is gone; `--homepage`
  writes index.html only, and the finalize job and the Nerra Daily build run
  it so the page follows the day). `landing-test.html` is a redirect stub.
  **`engine/newsroom.py` owns the news behaviour**: story times from the
  summary record's `datetime` in Eastern time (the feed pubDate is a fixed
  08:00 UTC), the markets strip (a value older than 3 days or a passed launch
  is not shown), the newest corrections, Today on Nerra from the schedule
  constants, and **developing stories** — two headlines are one thread at ≥ 3
  shared salient words that are ≥ 50% of the shorter (2 words was measured and
  doubled the count with false threads), on ≥ 2 days with an update in the
  last 3. The homepage's one email form is the Soft Personal band (Oct 9 rule).
- **`engine/share_cards.py` owns every link preview**, and `base.html.j2`
  decides through ONE Jinja global, `resolve_og_image`: a square cover becomes
  its show's 1200x630 card, nothing becomes the page's own card (keyed by the
  canonical path) or the network card, anything else (an episode card) passes
  through. **A template never writes its own `og:image`** (guarded) — the
  homepage shares as the network card, never the day's lead scene. The
  committed cards (`assets/share/`: network, every show, the site pages, every
  topic hub; alt text in `manifest.json`) are built by
  `scripts/build_share_cards.py` nightly and rewritten only when their pixels
  change; `assets/og-preview.png` IS the network card (hand-written pages and
  cached links still name it — it had carried the retired no-ads promise).
  Fonts are bundled (`assets/fonts`, OFL: DM Sans, Source Serif 4, Golos Text
  for Cyrillic) so a runner draws the same bytes as a laptop. **Episode cards
  are never committed** (landmine #1): run_show draws one on the show's art
  before the post is written and one on the episode's own scene in the video
  stage, each to a new R2 key `share/<slug>/epNNN-<art|scene>.jpg`, recorded in
  `digests/<dir>/share_cards.json` (metric `share_card`); members-only episodes
  get none. The hook budget is `engine.titles.SHARE_CARD_HOOK_MAX`; an overflow
  shortens through `clip_words`, never a slice. A new site page adds itself to
  `_page_cards` in the build script; a new show needs nothing. Backfill:
  Actions "Share Cards — backfill episodes" (gallery originals via R2).
