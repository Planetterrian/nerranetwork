# Nerra Network Website Review (September 3, 2026)

Full review of the public site — homepage, navigation, every show
surface (show page, summaries, story tracker, blog), the informational
and conversion pages, the legal/trust pages, and Mission Control
(`management.html`) — for messaging, navigation, look and feel, and
usefulness. Method: four parallel audits (homepage + global chrome;
show/blog surfaces; info/marketing/conversion pages; Mission Control +
data dashboards) plus a scripted crawl of all 1,772 generated pages
(436,007 internal links; zero broken static links) and a metadata sweep
of every root page. Previous pass:
[`website_review_2026_06_10.md`](website_review_2026_06_10.md).
Drift guards for everything shipped here:
`tests/test_website_review_2026_09_03.py`.

## Headline findings

1. **The three legal/trust pages were hand-written, off-brand, and
   wrong.** `ai-disclosure.html`, `privacy-policy.html` and
   `terms-of-service.html` used a different font (Inter), had no site
   nav or footer (a visitor who landed there was stuck), no meta
   description or canonical, a hard-coded GA4 id, and copy last touched
   March 31. The AI disclosure — linked from every footer, every AI
   badge and every feed description — claimed Patrick "personally
   reviews and approves every episode" and cited a US Supreme Court
   ruling that does not exist. It never mentioned Mira. The terms had no
   clause on memberships or donations while the site bills $4.99/$8.99.
2. **`modern-investing-performance.html` shipped `<title></title>`.**
   Six templates declare `{% block title %}`; `base.html.j2` rendered
   `{{ page_title }}` and never the block. The other five happened to
   pass a variable; the MIT page passed neither.
3. **`blog/index.html` was 1.7 MB.** All 1,674 article cards were in the
   DOM behind client-side pagination; every visitor downloaded the whole
   archive to see 24 cards, and it grew ~13 cards a day.
4. **The homepage said things that were not true.** "Published daily"
   (6 of 17 shows are not), "Free forever / no paywalls" two screens from
   the $4.99 Personal band, "the most recent episodes from all shows"
   over a 10-of-17 rail, a hand-maintained topic ticker stuck at 15
   shows, and a "Most Played This Week" rail whose six slots were all
   SpaceX Daily. The homepage newsletter form still POSTed straight to
   Buttondown's embed endpoint — opening the raw response in a new tab,
   declaring success on a timer, and creating no Nerra account, so
   homepage subscribers never got the perks the join page promised.
5. **Navigation defects on every page.** Two 17/18-item hover dropdowns
   with no max-height; dropdowns not keyboard-operable (focus set
   `aria-expanded="true"` while nothing opened); no `scroll-padding-top`
   under a 72 px sticky nav; the homepage mobile menu forgot to clear
   `body.menu-open`, leaving the page scroll-locked after tapping
   "Latest" or "Subscribe"; the footer "About" column sat outside the
   footer grid; Books/Gallery/Data/Editorial/Support were reachable only
   from a ~70-link footer.
6. **The editorial page claimed "no third-party analytics that profile
   visitors"** while the base template loads GA4, and still described the
   pre-cold-open "25 seconds of music before voice" mix.

## Implemented in this pass ✅

Source-only unless noted; the nightly regen propagates template changes
(blog posts pick up the new chrome on their next per-show regen).

**Titles, metadata, SEO**
- `base.html.j2` renders `<title>{% block title %}{{ page_title }}{% endblock %}</title>`; `generate_mit_performance_page` passes title, description, canonical, og:image, brand colour.
- Narrative tracker pages: canonical URL, absolute og:image (was a relative path, so shares rendered imageless); Tesla's tracker gets its cover instead of the generic card.
- Homepage canonical and `hreflang` use the bare origin (`https://nerranetwork.com/`), not `/index.html`.
- `blog/index.html` og:image is the PNG (Facebook/LinkedIn/X reject SVG).
- `account.html` is `noindex` (a member console, already excluded from the sitemap).
- `editorial.html` no longer emits a second meta description + canonical.
- `ru/*.html` landing pages no longer nest a second `<main id="main-content">`.
- Footer copyright year is computed (`current_year` Jinja global).

**Legal / trust pages → templates on the shared chrome**
- New `templates/ai_disclosure.html.j2`, `privacy_policy.html.j2`, `terms_of_service.html.j2` sharing `_legal_page.html.j2` (site tokens, DM Sans / Source Serif 4, skip link, nav, footer, consent script).
- AI disclosure rewritten to describe the real pipeline: what AI does (writing, narration incl. Patrick's custom voice and Mira, imagery, translation, books, automated review), what people own (briefs, sources, standards, spot-listening, corrections), and the safeguards (claims ledger + source-integrity gate, grounding rules, spoken disclosure, verbatim guests). It states plainly that no human reads every episode before publication.
- Privacy policy now covers Nerra accounts, Stripe, Cloudflare (audio/gallery/API), the session cookie, and the city/name collected for the morning brief. Terms gained a memberships-and-donations section, the CC BY-SA gallery licence, and the simulated-portfolio framing for MIT.
- `generate_legal_page()` / `--legal`, plus a new `--static-pages` flag that regenerates every cheap static page in one call; `nightly-maintenance.yml` uses it (previously only Start Here / FAQ / About were refreshed between `--all` runs, so editorial/press/contact/legal/gallery/books/404 could sit stale for weeks).

**Blog hub**
- `engine.blog.NETWORK_BLOG_INDEX_MAX_POSTS = 240`: the hub renders the newest 240 (ten pages) plus an archive-by-show rail with post counts and latest dates linking each show's complete index. 1,754 KB → 321 KB.
- Per-show blog index hides the RSS button when a show has no posts yet (`blog_age_of_ai.rss` 404'd).

**Homepage**
- Claims corrected: subtitle and show-grid copy say "most shows daily"; "Zero Ads" card no longer says "free forever / no paywalls" (it names Personal as the optional upgrade); "Sourced, Not Vibes" card links the editorial page; "Four Listening Languages" is accurate about native vs dubbed; Latest rail says "ten newest"; About paragraph lists every show incl. Offshore North, Unintended Consequences, Nerra Daily.
- Proof stats: show count from the registry, episode count formatted, "listening languages".
- Topic ticker driven from `all_shows` and `aria-hidden` (it duplicates the grid for screen readers).
- "Most Played" capped at 2 per show (`POPULAR_EPISODES_MAX_PER_SHOW`), ranks renumbered.
- Newsletter form posts to `api.nerranetwork.com/api/subscribe` (`list: member`) like every other form, reports the real result, and reveals an account link on success. Copy says per-show briefings, not "weekly digest".
- Hero CTAs: Explore Shows / Start Here / Open Player / Subscribe Free (Blog is in the nav). Only the first 7 covers are `fetchpriority=high`; on phones the orbit caps at 8 covers and keeps its side gutters.
- Inline duplicate `@keyframes` block removed (it overrode `main.css` and staggered only 11 of 17 cards).
- Show grid: "In Russian" badge on the two RU shows; blog cards use `<h3>` and skip the hook when it equals the title; every link carries `path_prefix`.
- `display_order` assigned to the five scaffolded shows (Nerra Daily first, SpaceX beside Tesla, DP Pod / Age of AI / Offshore North after the narrative shows) — they were all 99–102 and rendered last, with the Personal band's sample lineup showing shows that are not in the lineup.

**Navigation and chrome (`base.html.j2`, `styles/main.css`)**
- "More" dropdown (Books · Image Gallery · Data & Dashboards · Editorial Process · FAQ · Press Kit · Support) + mirrored mobile section; redundant "Home" nav item removed (the logo is the home link).
- Dropdowns: `max-height: min(72vh, 620px)` + scroll; click/Enter/Space toggle `.open`, Escape and outside-click close, `aria-expanded` reflects reality.
- One delegated mobile-menu close handler (clears `body.menu-open`, resets the hamburger's `aria-expanded`); all inline `onclick`s removed.
- `scroll-padding-top` under the sticky nav; `scroll-behavior: auto` under reduced motion.
- Footer: About column inside the grid, grid is `1.6fr repeat(5, 1fr)`; accordion headers are keyboard-operable and bound at every width; "Apple Podcasts" link labelled as Tesla's; YouTube channels and Contact added to Connect; "Network Status" lands on `management.html?view=sponsor`.
- `--nn-accent` / `--nn-text-secondary` defined (the newsletter checkboxes and Subscribe button had referenced undefined tokens since May).
- Search-result hover/keyboard/`<mark>`/focus styles moved out of the `<640px` media query (desktop had none).
- `search.js` legacy fallback list includes `offshore_north` and `nerra_daily`.

**Show surfaces**
- Show hero uses the punchy `description_long`; the long `about_text` renders once (12 of 12 pages printed the same ~800-char paragraph twice).
- Environmental Intelligence no longer advertises `@teslashortstime` (with a Tesla timeline embed) as its own handle.
- Subscribe line says "next episode" on non-daily shows.
- Summaries pages: honest subtitle ("most recent episodes … the complete archive is on the blog"), accept the Age of AI JSON shape (`episodes` + `episode`/`title`), no more third-party CORS proxy for a same-origin fetch, per-card markdown `# ` renders `<h3>` (was dozens of `<h1>`s).
- Story Tracker pages: chip row back to the show / articles / summaries / RSS, and the real `last_updated` date.
- DP Pod page links its summaries page (it was reachable from nowhere on its own show page).
- Related-show graph: tesla→spacex, omni_view→nerra_daily, env_intel→offshore_north, first_principles↔unintended_consequences — five shows previously had zero inbound recommendations.
- Nerra Daily's registry copy no longer says "thirteen subscriptions".

**Info / conversion pages**
- Support / join / press / FAQ no longer say "Seventeen daily shows"; support's "$3 covers a day" is computed from `monthly_cost_usd` (it is $4); press "At a glance" gains show count, production model, funding; boilerplate mentions SpaceX and Nerra Daily.
- FAQ: cadence answer corrected (MIT is daily; Offshore North weekly on Mondays) in both JSON-LD and visible copy; new entries **What does it cost? / Who is Mira? / What languages?**; "weekly newsletter" → per-show briefings (also on How to Listen).
- How to Listen no longer advertises Español (no ES feed has been built since June).
- About: "AI-produced, human-owned" names Mira; funding section covers Personal, donations, books; CTA row gains "Join Nerra Personal".
- Start Here lists Nerra Daily and Offshore North (were hidden by hardcoded allowlists).
- Join page explains why the Personal lineup is 13 of 17.
- Books page shows an honest "store listings are on their way" line when a volume has a price but no buy link.
- 404 offers Start Here / All Shows / Player / Blog and points at site search.

**Mission Control (`management.html`)**
- Guarded reads (`data.network`, `data.voice_config`, `mit.trades`, `rss.feeds`) plus a window error handler that surfaces render failures — a missing section used to silently kill MIT, the feed audit, the sponsor panel and the view switcher.
- Show cards use `fmtOrDash` for RSS/YouTube (Age of AI, Offshore North, DP Pod read "—", not a fabricated 0).
- A data-age pill visible in every view, amber past 36 h and red past 72 h (sponsor/investor readers had no staleness signal).
- Nav gains `← nerranetwork.com`, the missing Growth anchor, and Public dashboards.
- Card grids use `minmax(min(340px, 100%), 1fr)` (phones scrolled sideways on seven sections).
- Distribution notes (which name secrets and failing integrations) are `data-ops`, so they never render in the sponsor/investor views.

## Checked and rejected / left as is

- **Reordering homepage sections** (grid above Latest/Personal): the May and Aug 2026 operator requests put Fresh Episodes → Personal → Blog → Why Nerra above the grid deliberately. Kept.
- **Rewriting the H1 into a value proposition**: brand decision; the subtitle now carries it. Kept `Nerra Network`.
- **Unchecking the 17 newsletter boxes by default**: the copy explicitly describes "everything's selected by default" as intended. Kept.
- **`Disallow: /docs/` in robots.txt**: `docs/mit_trading_method.md` and `docs/analytics.md` are deliberately public (the MIT page's "verify this record" panel links the first). See operator items.
- **Nav search/language control inline styles → classes**: pure refactor touching every page; deferred.
- **Inline-style density of `show_page.html.j2` (213 `style=`)**: a rewrite, not a review fix; deferred.

## Recommended next (not implemented)

| Priority | Item | Why deferred |
|---|---|---|
| P1 | **Blog titles duplicate the hook** on ~29/30 posts and ~3,600 index cards (`engine/blog.py:491-506` falls back to the hook when the digest has no `**TITLE:**` line; only Offshore North's prompt emits one). Add `**TITLE:**` to the other digest prompts. | Prompt change → A/B-listen per landmine #17; the network hub now skips the duplicate hook, the per-post `<h1>`/hook pair remains. |
| P1 | **Story Trackers are boilerplate on 10 of 11 shows** — every program reads "Not yet deeply covered" because the memory updater never writes `last_major_update_episode`. Either write it in `engine/show_memory.py` or hide the CTA when zero programs are attributed. | Pipeline change with output effects. |
| P1 | **Per-show blog indexes have no pagination/search** (Tesla: 198 cards, 220 KB). Lift the hub's pagination block into `blog_index.html.j2`. | Touches ~1,900 regenerated files; do it in its own PR. |
| P1 | **Summaries pages are 100% client-rendered** with no `<noscript>`; SSR the first 20 cards like the show page does. | Template + generator work. |
| P1 | **Curated Tesla/SpaceX series are stale under "Live" badges** (`site/data/tesla_metrics.json` deliveries end 2025 Q1; `api/spacex_launches.json` annual launches end 2024, Starship tracker ends IFT-9). Add a freshness assertion to `tests/test_tesla_dashboard.py` and render `updated_at`. | Data entry is the operator's; the guard is worth adding next. |
| P1 | **MIT alpha on Mission Control**: the panel leads with the blended `matched_window_alpha_pct` (+1.68 %, 55 trades) and never renders `verified_window_alpha_pct` (−8.21 %, 20 trades, not significant) or `indices_beaten` (0 of 3) — the number the show's own rule says must not reach air. The public performance page has the same two figures 40 lines apart with no reconciling label. | Needs the MIT owner's framing; see `tests/test_mit_benchmark_integrity.py` for the on-air rule. |
| P2 | `ru/index.html` and `modern-investing-resources.html` are hand-written with an 11-show footer ("Eleven shows", "семь подкастов"); `age-of-ai-apply.html` collects phone numbers with no privacy link, nav, footer or sitemap entry. Convert all three to templates. | Each is a small port; RU copy needs the operator. |
| P2 | Reciprocal `hreflang` between `tesla.html`/`ru/tesla.html` and `spacex.html`/`ru/spacex.html`; the RU landers are otherwise orphaned (link them from `ru/index.html` and a "Читать по-русски" chip). | Needs the RU hub port above. |
| P2 | Mission Control: nine populated JSON sections never render (`benchmarks.sources`, `mit.execution_health`, `mit.sectors`, `funnel.by_source`, `shows[].load_error` …); add the contract test "every top-level key has a consumer". Two contrast failures (`--ink-4` captions 3.65:1; active view button 3.58:1). | Design + data decisions. |
| P2 | Podcast RSS item `<link>` points at the MP3 rather than the episode page. | Feed change; verify with Apple/Spotify before flipping. |
| P2 | `search-index.json` is 2.2 MB and the localStorage cache silently fails; ship a slim title index. | Separate build step. |

## Operator items

- **One contact address per purpose.** The site publishes eight: `hello@`/`press@`/`partners@`/`tech@`/`privacy@nerranetwork.com` (contact page), `patrick@planetterrian.com` (editorial), `patricknovak1@gmail.com` (legal pages, kept as-is in this pass), `mira@nerranetwork.com` (studio). Confirm which mailboxes exist and pick one per page.
- **Legal text review.** The privacy policy and terms were extended to cover accounts, Stripe, Cloudflare, memberships and donations from what the code actually does; they are not legal advice. The refund position for memberships is deliberately not stated.
- **`docs/` is publicly served** (`.nojekyll`), unblocked in `robots.txt`, and contains `env_var_inventory.md` plus two personal email addresses; only two docs are meant to be public. Decide whether to move those two and disallow the rest.
- **Two public TSLA endpoints disagree** (`api/tesla_dashboard.json` vs `api/tsla.json`, ~7 % apart on the same day).
- **Books**: both volumes show "from $7.99" with no store link; add `buy_links` or the page keeps its new "listings on their way" line.
- After tonight's regen, spot-check a share preview of `ai-disclosure.html` and `blog/index.html`, and open `management.html` in the sponsor view to confirm the data-age pill.
