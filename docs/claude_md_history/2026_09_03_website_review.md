# Website review (September 3, 2026)

Moved verbatim from CLAUDE.md on 2026-11-03; the rules that still bind are summarised there.

### Website review (September 3, 2026)

Second full public-site pass — canonical writeup:
[`docs/website_review_2026_09_03.md`](docs/website_review_2026_09_03.md);
drift guards: `tests/test_website_review_2026_09_03.py`. Rules that now
bind:

- **The legal/trust pages are TEMPLATES** (`templates/ai_disclosure.html.j2`,
  `privacy_policy.html.j2`, `terms_of_service.html.j2` on the shared
  `_legal_page.html.j2` chrome; `generate_legal_page()` / `--legal`).
  Never hand-edit `ai-disclosure.html` / `privacy-policy.html` /
  `terms-of-service.html` at the root again — they were hand-written
  for five months, drifted off-brand (Inter, no nav/footer, hardcoded
  GA4 id) and off-truth (the AI disclosure claimed every episode was
  personally reviewed before publication and cited a Supreme Court
  ruling that does not exist). The disclosure says plainly that no
  human reads every episode before it ships and describes the
  safeguards instead; keep it that way.
- **`--static-pages` is the one flag for every cheap page** (start-here,
  about, FAQ, how-to-listen, press, contact, editorial, legal, gallery,
  books, 404); nightly runs it. A new static page is added to
  `generate_static_pages()`, or it silently stops refreshing between
  `--all` runs (editorial/press/contact/legal had for months).
- **`<title>` comes from `page_title` OR a `block title`** — base now
  renders both. The MIT performance page shipped `<title></title>` for
  the same reason the Tesla tracker did in August; pass `page_title`
  in every generator regardless.
- **The blog hub renders the newest `NETWORK_BLOG_INDEX_MAX_POSTS`
  (240)** plus an archive-by-show rail; per-show indexes stay complete.
  Do not "restore" the full list — it was 1.7 MB and growing daily.
- **Homepage claims are computed, not typed**: show count, ticker,
  About paragraph, cadence wording ("most shows daily"), Most Played
  (`POPULAR_EPISODES_MAX_PER_SHOW = 2`). The homepage newsletter form
  posts to the account Worker like every other form — the Buttondown
  embed endpoint is gone from the site for good.
- **Navigation contract** (`base.html.j2`): "More" dropdown for
  Mira/Topics/Books/Gallery/Data/Editorial/FAQ/Press/Support (Mira and the
  topics map joined it Sep 19–20 2026 — a fourth dropdown would crowd the bar,
  and `topics/index.html` is the crawlable map that carries all twelve hubs);
  no "Home" item (the
  logo is home); dropdowns capped + keyboard-operable; ONE delegated
  mobile-menu close handler (no inline `onclick` on menu links — the
  homepage override forgot `body.menu-open` and scroll-locked phones);
  `scroll-padding-top` under the sticky nav; footer About column
  inside the 6-child grid. `--nn-accent` / `--nn-text-secondary` are
  defined tokens now.
- **Scaffolded shows need a real `display_order`** in
  `shows/network_meta.yaml` (the five were 99–102 and rendered last,
  Nerra Daily dead last; ties fall back to insertion order, guarded).
- **Mission Control never fabricates a zero** (`fmtOrDash` on the show
  cards) and every top-level read is guarded; a data-age pill is
  visible in all three views; the site footer's "Network Status" lands
  on `?view=sponsor`.

Deferred with rationale in the doc: blog `<h1>`==hook duplication
(needs `**TITLE:**` in 13 digest prompts — A/B), boilerplate Story
Trackers on 10 of 11 shows (`last_major_update_episode` never written),
per-show blog pagination, SSR summaries, stale curated Tesla/SpaceX
series under "Live" badges, MIT alpha framing on Mission Control, and
the remaining hand-written pages (`modern-investing-resources.html`,
`age-of-ai-apply.html`; `ru/index.html` is generated since Oct 18 2026).
