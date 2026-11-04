# Website review (October 7, 2026)

Moved verbatim from CLAUDE.md on 2026-11-03; the rules that still bind are summarised there.

### Website review (October 7, 2026)

Full render audit (58 pages at 1440 and 390 px) + five reviews + five
implementation passes — write-up
[`docs/website_review_2026_10_07.md`](docs/website_review_2026_10_07.md);
register `website-review-2026-10-07`; guards
`tests/test_site_review_2026_10_07_{chrome,blog,trust,dashboards,gallery_player}.py`.
Rules that bind:

- **`styles/main.css` has a brace-balance guard.** One stray `}` closed the
  phone media query early: the phone layout applied at every width and the
  tablet block (hamburger) was dropped, site-wide, for weeks.
- **A brand colour is never TEXT on the dark surfaces.** Use
  `var(--show-color-text)` / `var(--card-accent-text)` (derived on every
  element in main.css) or `var(--nn-purple-text)`; raw `--show-color`,
  `--card-accent` and `--nn-purple` are for fills, borders and tints. The
  guard fails a raw text use.
- **Prose links are visible** (`main :where(p, li, dd, td) > a` with no class
  or style): style a component's links with a class and it wins.
- **Every blog post with audio has a player** (`engine.blog.episode_audio_url`:
  summaries record, then the feed enclosure, OP3 kept), the headline is
  stated once, the body outline runs h2 → h3, and the provenance line wraps
  (it was a `nowrap` run that made every post wider than a phone).
- **The guest's terms are stated as built, everywhere a guest or reader sees
  them** (site, apply pages, interview posts, the producer's reply facts,
  booking emails, the Voices Worker pages): a week to approve, cut or
  refuse; then it publishes; takedown after. Never "nothing publishes until
  you approve".
- **Gallery and player data are slim indexes**
  (`site/data/gallery/*.index.json`, `--indexes-only` rebuilds them offline;
  the player embeds a compact OP3 index). A per-show gallery never falls
  back to the 22 MB manifest, and a show with no images mounts none.
- **Mission Control's sponsor/investor numbers come from the same honest
  sources as the tiles** (week-over-week from `audience_headline`, episodes
  from RSS pubDates, untracked spend `None`).
