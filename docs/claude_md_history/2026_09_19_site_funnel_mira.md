# Site + funnel + Mira program (Sep 19–20, 2026)

Moved verbatim from CLAUDE.md on 2026-11-03; the rules that still bind are summarised there.

### Site + funnel + Mira program (Sep 19–20, 2026)

Operator brief: review the site and the last 30 days, then a plan driven by
analytics, with Nerra Personal's visibility and the Mira shows' novelty as the
priorities. The finding was that the factory is healthy and almost nothing it
makes reaches a person: **134,171 YouTube views in 30 days produced 10
attributed sessions and 1 newsletter signup**, the site saw 243 sessions in 28
days with **26% of measured landing sessions hitting a path with no file**, and
the three most differentiated, cheapest, best-trending and most-visited
properties — Nerra Daily, The Age of AI, Nerra Voices — were the three with no
YouTube, no X, no newsletter and no on-air presence. Plan:
`/root/.claude/plans/` (session artifact); guards
`tests/test_site_funnel_pass_2026_09_19.py`,
`tests/test_mira_pass_2026_09_20.py`. Rules that now bind:

- **`engine/brand.py` owns every claim the network makes about itself**, the
  way `engine/titles.py` owns limits and `engine/funnel.py` owns campaign ids.
  Import `mira_claim_paragraphs()`; render it through the `mira_claim` macro in
  `templates/_macros.html.j2` (fed by the `mira` / `mira_shows` Jinja globals).
  A template that hardcodes the sentence fails CI.
- **The Mira claim is NARROW on purpose, and widening it is the failure mode.**
  It rests on the guest holding the publish decision — *an AI asks the
  questions, and the human guest decides whether the conversation is published
  at all* — because the general shape ("an AI host interviews real people") is
  **not ours to claim**: a prior-art search found platforms doing exactly that,
  at least one since 2024, so the broad version is disprovable in one search on
  the page a journalist reads. The basis must also stay true of BOTH call modes:
  the pre-2026-09-09 basis said Mira "places the call", which is now the
  fallback, and it had already shipped inside `llms.txt`. Guards:
  `TestTheClaimHasOneOwner`.
- **The claim never ships without its basis and its correction invitation.**
  A superlative nobody can challenge is a superlative nobody should believe, and
  the AI-disclosure page is the asset the claim trades on.
- **`strand` groups shows in the chrome** (`shows/network_meta.yaml`;
  `_merge_scaffolded_network_registry` passes it through untouched, so a
  registry-only show needs no Python change). It drives the nav Shows dropdown
  group, the mobile menu, and a badge on the homepage grid card. The FOOTER show
  list stays flat — its mobile accordion targets `.nn-footer-col > a` directly,
  so nesting would stop it collapsing on phones.
- **A show that bypasses `run_show.py` gets none of run_show's publish
  surface.** `newsletter.enabled` and `youtube.enabled` on `age_of_ai` were read
  by NOTHING for months; `pipelines/voices/publish_episode.py` reads them now
  (see the AOAI entry above for the mechanics). This is the third instance of
  the class after the OP3 prefix and the per-language OP3 feeds — when a new
  show skips run_show, wire its distribution explicitly and check the secret
  NAMES (`YOUTUBE_REFRESH_TOKEN_EN`, not `YOUTUBE_REFRESH_TOKEN`).
- **No surface advertises something that does not exist.** A show with no feed
  FILE gets no feed link, no `webFeed` JSON-LD, no `alternate`, no JS fetch and
  no Story Tracker link (`has_feed`, Sep 19 — Nerra Voices' dead feed link was
  on ~1,990 pages, the most-repeated broken link on the site), and its page
  leads with a "Not published yet" band and the apply CTA instead of an empty
  episode rail.
- **An internal link never carries a `utm_*` tag.** GA4 starts a new session on
  any page_view carrying `utm_source`, so an internal UTM inflates the session
  count and overwrites the visitor's real acquisition source. Internal CTAs are
  measured with a GA4 EVENT (`select_personal_upsell`). The blog Story Tracker
  link had been doing exactly this.
- **`site/redirects.yaml` + `scripts/audit_dead_urls.py`** own dead URLs: a
  committed stub (meta-refresh + canonical + `noindex`) per retired path, and a
  nightly loud-but-non-blocking audit against the GA4 landing pages. A redirect
  stub is **not** an episode page — `_blog_url_for_episode` skips
  `redirect_stub_paths()`, because "the file exists" stopped being a proxy for
  "the article exists" the moment stubs appeared at `blog/<slug>/epNNN.html`.
- **`age-of-ai-studio.html` stays out of the sitemap** (a private join link for
  a scheduled interview); both `*-apply.html` forms are now IN it, having been
  the unfindable acquisition surface for the network's most differentiated
  shows. Each interview show links its OWN form (registry `apply_page`) —
  the Worker files an application against whichever form posted it.
