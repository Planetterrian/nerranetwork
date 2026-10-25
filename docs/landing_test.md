# Landing Test — the network as a news front page (Oct 17 2026)

> **Since Oct 18 2026 this design is the homepage (`index.html`) and
> `landing-test.html` is a redirect stub to it — see "v3 — the homepage"
> at the end. v1 and v2 below describe the test as it was built.**

Operator request: a test landing page that takes the top story from every
show, with images and the story hooks, and lays it out like a news network's
front page — so a visitor wants to stay and discover more.

- Page: `landing-test.html` (repo root), `noindex`, **not in the sitemap, not
  linked from the nav**. It is a test.
- Built by `generate_landing_test_page()` in `generate_html.py`
  (`--landing-test`, and in `--static-pages` / `--all`, so the nightly
  refreshes it with each day's stories).
- Data: `engine/landing_test.py`. Template: `templates/landing_test.html.j2`.
- Guards: `tests/test_landing_test_2026_10_17.py`.

## What the research said

Direct fetches of the major front pages (BBC, Guardian, AP, NPR, Axios) were
blocked from this environment, so the notes below combine what the trade press
documents about those redesigns with the conventions every one of them shares.

| Pattern | Seen at | Adopted here as |
|---|---|---|
| A tiered hierarchy: one lead, a band of top stories, then section rails; size and image weight signal importance | NYT 2018 redesign ("much more intentional in the hierarchy and presentation of Top Stories", sections less hierarchical below); news-site guides on lead / top / category tiers | Lead story with the big 16:9 picture and a ~2.6rem serif headline; a 4-up **Top stories** grid; then topic sections |
| A right-hand "Latest" rail beside the lead | BBC, Guardian, Reuters, NYT live rails | **Latest across the network** list beside the lead (chronological, show kicker + date) |
| Containers ("slices") with varied layouts so the page is not one repeated card | Guardian 2014 fronts ("visually fatigued by very repetitive layout forms"; stories → slices → containers) | Each topic section is a container: one pictured feature + a stack of headline-and-thumbnail rows; a two-story section becomes a pair; leftovers become a dense 3-column "More from the network" |
| Kicker + headline + timestamp on every card | Every front page | Kicker = topic hub / show name (show colour, text-safe tint), serif headline, date and Read / Listen links |
| A "Most read / Most popular" list | BBC, Guardian, NYT | **Most played this week**, from the same OP3 data (and freshness rule) as the homepage rail |
| A horizontal "latest" strip under the masthead | Verge Storystream / breaking tickers | A scrollable **Latest** ticker (no marquee animation — static, keyboard reachable, faded right edge) |
| Section navigation near the top | Every front | In-page section nav (anchors to each section) |
| Phones: one column, headline beside a small thumbnail, not a stack of full-width pictures | BBC / Guardian mobile; WSJ editor quoted on keeping hierarchy from desktop columns to one phone column | At ≤640 px the top stories and section rows become headline + 112 px thumbnail; the Latest list caps at five; per-section "Also in this episode" lists hide |
| A newsletter ask | Axios, NPR, Guardian | A band near the end that jumps to the existing footer signup form (`#newsletter-signup`) — no new form, no new endpoint |
| A "listen" or "watch" rail | NPR, CNN | **Listen to every show**: cover art rail, each with Listen (show page) and Articles (blog index) |
| A network-produced daily edition | morning-briefing products (Axios AM, NYT The Morning) | The **Nerra Daily** strip, hosted by Mira, with its own player |

Sources: [Design Week on the Guardian's 2015 site](https://www.designweek.co.uk/issues/26-january-1-february-2015/guardian-launches-new-website-to-complete-multi-platform-redesign/),
[Journalism.co.uk, key principles behind the new Guardian website](https://www.journalism.co.uk/key-principles-behind-the-new-guardian-website/),
[Nieman Lab on the Guardian redesign](https://www.niemanlab.org/2014/09/the-guardian-wants-to-know-what-you-think-of-its-redesign/),
[Dezeen on the NYT 2018 redesign](https://www.dezeen.com/2018/08/17/new-york-times-newspaper-website-redesign-news-design/amp/),
[Pratt IXD critique of the NYT site](https://ixd.prattsi.org/2020/11/design-critique-the-new-york-times-website/),
[Nieman Lab on The Verge's 2022 Storystream](https://www.niemanlab.org/2022/09/the-verge-goes-back-to-bloggy-basics-with-a-new-redesign/),
[Smashing Magazine, newspaper website design](https://www.smashingmagazine.com/2008/11/newspaper-website-design-trends-and-examples).

## Honesty rules (what the page will not do)

- **Headline = the digest's own hook, printed whole.** Not the feed title,
  which `engine.titles.episode_title` clips to 100 characters with an "Ep N:"
  label. Only the one-line ticker clips, via
  `engine.titles.LANDING_TICKER_MAX` + `clip_words`.
- **"Also in this episode" = the digest's own story headlines**
  (`engine.grok_imagine.extract_story_headlines`), linked to the article.
  Shown only when the article exists.
- **The picture is that episode's own scene art** — matched in the slim
  gallery index by show + `epNNN` + date. Among the episode's scenes, the one
  whose Grok Imagine prompt shares the most words with the headline wins
  (read at build time from the show's gallery slice; nothing of it ships).
  No match → the episode's first scene. No scene at all → the show's cover
  art on a brand-tinted band. Never an older episode's picture.
- **Links** to articles go through `_blog_url_for_episode` (a redirect stub
  is never an article); no internal link carries `utm_*`.
- **Members-only shows never appear** (the five Omni View desks), and nothing
  reads `digests/*/members/`.
- Stories older than 14 days before the newest one drop off the front; their
  shows stay in the Listen rail. Unknown or missing data renders nothing.
- Display-size images only: the 800×450 `.thumb.webp` gallery thumbnails and
  the `-400.webp` cover variants, `loading="lazy"`, explicit width/height.

## Ordering

Newest date first, then the homepage's audience order (30-day downloads from
`api/audience_headline.json`), then slug — deterministic. The lead is the
first story with a landscape scene of its own. Each remaining story lands in
the first section of `SECTION_ORDER` (curated `engine.topic_hubs` ids) whose
hub lists its show, so nothing prints twice; a section with fewer than two
stories folds into "More from the network". Section headers link to the
topic hub only when that hub page is actually built (`renderable_hubs`).

## Open questions for the operator

- Should the real homepage borrow any of this (e.g. a "Today" band of hooks
  above the show grid), or should this become the homepage outright?
- Shows without gallery art (the launch cohort, the weeklies) fall back to
  cover art; turning on scene art for them would make the page much richer.

## v2 — the whole site (Oct 17 2026, second pass)

Operator request: "do another full review of the existing site and integrate
items such that the full site is covered off and represented on the new
landing page and would help to grow traffic and audience and subscribers
from the content." Guards: `tests/test_landing_test_v2_2026_10_17.py` (and
one intentional change to the v1 guard, below).

### What the data said, and the order it set

| Signal (committed file) | Reading | What it decided |
|---|---|---|
| GA4 landing pages, 28 days (`api/ga4_stats.json`) | `/` 45 sessions, then `/blog/age_of_ai/ep005.html` 24 and `/age-of-ai.html` 23; then Nerra Daily, Mira, SpaceX, claims, Peptides | The interviews are the strongest web draw → **Conversations** sits directly under the lead + Latest, above Top stories |
| Audience headline (`api/audience_headline.json`) | 11,937 RSS downloads / 30 d, +67% week over week; 62,244 YouTube views / 28 d (Shorts ~70%) | **Watch** gets its own band high on the page; downloads + views are the glance tiles |
| Newsletter (`api/buttondown_stats.json`) | 12 subscribers | Signup is the weakest stage → a **real inline form** right after Top stories (the old band only jumped to the footer); the footer form is suppressed on this page so there is one ask, not two |
| Claims ledgers (`digests/*/…_claims.json`) | 4,599 claims / 30 d, 95.5% verified | A **trust strip** with the same numbers `claims.html` prints |

Final order: masthead · section nav · Latest ticker · **lead + Latest** ·
**Conversations** · Top stories · **signup** · Nerra Daily · **Watch** ·
topic sections · More · **Most popular** (played + read) · **By the numbers**
(+ claims record) · **Live dashboards & trackers** · **Find your subject** ·
**Nerra Personal** · **Books & the image gallery** · Listen to every show
(+ **apps and languages**) · **Partners & guests** · note.

### Inventory: every public surface, and where it is on the page

| Surface | On the page as | Source of truth |
|---|---|---|
| Show pages (public shows) | Story kickers, Listen rail, app list | registry (`_build_all_shows_list`) |
| Episode articles `blog/<slug>/epNNN.html` | Every headline (v1); Most read; Conversations | `_blog_url_for_episode` (stubs excluded) |
| `blog/index.html` | "Every article" | — |
| The Age of AI / Nerra Voices (show pages, articles) | **Conversations**: newest interview featured (guest, identifier, the digest's hook, run time, co-host read from the transcript, player), four more | `_interview_episode_cards` (the show page's own builder) |
| `mira.html` + the Mira claim | "Meet Mira" + the claim block | `mira_claim` macro → `engine.brand` (claim + basis + correction invitation, never retyped) |
| `age-of-ai-apply.html`, `nerra-voices-apply.html` | "Be interviewed by Mira" + Partners row | registry `apply_page` |
| `guest-picks.html` | Link in the apply card | — |
| `topics/interviews.html` | "All interviews" (only while the hub is built) | `renderable_hubs` |
| YouTube @NerraNetwork / @NerraRU / @NerraFR | **Watch**: newest EN long-form per show (4) + newest hook Short per show (6), subscribe chips for all three channels | `digests/<dir>/youtube_videos.json`; `engine.video_metadata.channel_subscribe_url` |
| OP3 most played | Most played (v1, unchanged rule) | `_load_popular_episodes` |
| GA4 most read | **Most read on the site** — articles only, ranks only, no counts; hidden when the snapshot is > 8 days old | `engine.landing_test.most_read_pages` |
| `claims.html`, corrections policy, `ai-disclosure.html`, `editorial.html`, `data.html` | **Every claim, on the record** tiles + links (`editorial.html#corrections` — the section gained that id) | `_claims_network_ledger`, now the ONE function `claims.html` also calls |
| Network numbers | **By the numbers**: public shows, episodes in the last 7 days (feed pubDates), languages, 30-day downloads (+ week over week only when up), 28-day YouTube views | `engine.landing_test.glance_numbers`; a missing figure is no tile, never 0 |
| `spacex-dashboard.html`, `tesla-dashboard.html`, `offshore-north-dashboard.html`, `offshore-north-glossary.html`, `modern-investing-performance.html` | **Live dashboards** cards; a dated one-line fact where the committed data has one (next launch NET, TSLA last quote with its date, EMIRA IV's last tracker fix with date + source, glossary term count) | `api/spacex_launches.json`, `api/tsla.json`, `api/offshore_north_dashboard.json`, `site/data/offshore_north_glossary.json` |
| Story Trackers `*-narrative.html` | Chip row, public shows only (the desks' trackers are not linked) | file exists |
| Topic hubs, `topics/index.html`, `explore.html`, `start-here.html` | **Find your subject** chips + links | `renderable_hubs` (never a hub that is not built) |
| `join.html`, `account.html`, `support.html`, `personal-interest.html` | **Nerra Personal** band; CTA fires `select_personal_upsell` (`placement: landing_test`), already in `ENGAGEMENT_EVENTS` | `STRIPE_LINK_PERSONAL` decides "See plans" vs "Launching soon", the join page's own rule |
| `books.html` | **Books**: the live volumes as typographic covers | `books_page_volumes` (retired volumes never appear) |
| `gallery.html` | **Image gallery** strip: 8 recent scenes, one per show, none already printed on the page, with the licence from the index | slim `_network.index.json` (never the 22 MB manifest) |
| `how-to-listen.html`, `player.html`, `network.rss`, per-show Apple/Spotify/RSS, per-language feeds, `ru/` | **Listen** band: the six most-listened shows' app links, languages the network still produces (with feed counts → `how-to-listen.html#feeds`), the Russian pages | registry; `_collect_language_feeds` filtered by `_listening_languages()` |
| `sponsor.html`, `press.html`, `contact.html` | **Partners & guests** row | — |

Growth details: Open Graph / Twitter image = the lead story's own scene
(800×450 thumbnail with alt; the full-size file is behind the gallery's
download gate), a schema.org `ItemList` of every story on the page (built as
a dict, piped through `tojson`), and a share row on the lead whose URLs come
from `engine.blog._share_urls` (`engine.funnel` campaigns, the blog's own
share builder).

### Deliberately left out

- **Personal prices.** `$4.99` / `$8.99` are typed in `join_page.html.j2`, not
  config, so this page names the product and links to the plans.
- **YouTube-hosted thumbnails.** A video card shows its episode's own gallery
  scene (a different one from the story card above it when the episode has
  one), else a titled card. Nothing is fetched from `ytimg.com`.
- **Book cover images.** The store covers are 3.4 MB PNGs and the gallery's
  `book_cover` art belongs to the retired volume builds; the shelf uses
  typographic covers in the show's colour.
- **Subscriber count.** 12 is below `MIN_SOCIAL_PROOF_SUBSCRIBERS` (50).
- **MIT's record numbers.** The alpha figures carry their own scoping rules;
  the card links the verified record and states no number.
- **A Prediction Markets board page.** None exists; the Board lives in the
  episodes.
- **A new capture source.** `engine.funnel` sources are acquisition channels
  (`utm_source`), not placements; a new value would also need a Worker
  deploy. The form sends `capture_source_site`, and a signup from this page
  is already attributable by the `newsletter_signup` event's `page_path`.
  **No Worker change.**
- `login.html` (the account link covers it), `management.html` (operator
  dashboard), `modern-investing-resources.html` (one show's hand-written
  list), `about.html` / `faq.html` (in the footer on every page), per-show
  `*-summaries.html` and `claims/<slug>.html` (one click from the show page
  and `claims.html`), and the members-only desks (never shown).

### Changed guard

`tests/test_landing_test_2026_10_17.py::TestLinks::test_no_utm_on_internal_links`
now treats a link as internal when it is relative or its HOST is
`nerranetwork.com`. The lead's share row links to x.com, LinkedIn, Facebook
and WhatsApp with the funnel-tagged article URL as a parameter — the blog
share row's pattern — and the old substring check read those as internal.

## v3 — the homepage (Oct 18 2026)

Operator direction: "make the landing page test the new landing page … ensure
it properly captures and highlights all the features of Nerra Network while
also updating and containing timely news information and updates as any
successful news and information site would be expected to have." Guards:
`tests/test_homepage_landing_2026_10_18.py` (plus the v1/v2 files, updated,
and the old homepage guards, ported — below).

### What moved

- **`index.html` is the front page.** `generate_network_page()` renders
  `templates/network_page.html.j2`, which is the landing template (moved by
  `git mv`); the old homepage template is gone. `generate_landing_test_page()`
  and `--landing-test` are removed; `--homepage` regenerates `index.html`
  alone (for workflows that commit only the homepage). `--network`,
  `--all` and the nightly still build it; `--all` now builds it after the
  posts, hubs and claims pages it links.
- **`landing-test.html` is a redirect stub** to the homepage
  (`site/redirects.yaml`; the committed test page was deleted in the same
  change, so the stub never shadows a real page).
- It is a homepage now: indexable, canonical = the bare origin, in the
  sitemap as `/`, the approved `SEO_PAGE_COPY["index.html"]` title and meta,
  bilingual hreflang, the Organization JSON-LD (every PUBLIC show as a
  `PodcastSeries`, built as a dict) plus a WebSite block and the stories'
  `ItemList`, and the site's real nav (no override; the in-page anchors the
  old override carried are gone).
- **Old homepage features folded in:** the Soft Personal band (the
  homepage's one email ask — the Oct 9 "Homepage Soft-only" rule wins over
  v2's inline per-show newsletter form, which did NOT come across; the footer
  form stays suppressed); the Nerra Personal promo (`#personal-promo`, sample
  lineup, soft interest link, `select_personal_upsell` with
  `placement: homepage`); Most Played This Week; the full grid of every
  public show (`#shows`, the shared `show_card`); Subscribe everywhere
  (`#subscribe`: app links, every feed in `details.subscribe-all`, network
  and blog RSS, languages); the About paragraph with the values list (Canada
  flag, sponsor policy from `engine.brand`, the listening languages computed
  from the language registry — the old typed list still said 中文 after the
  ZH track was switched off); the episode count from the feeds. The
  decorative show-name ticker, the cover "orbit" and the "0 ads" stat were
  not carried over.

### Timely: what a news front shows (`engine/newsroom.py`)

| Element | Source | Rule |
|---|---|---|
| Story timestamp | the summary record's `datetime` (runner clock, UTC) | Printed as Eastern time server-side ("Oct 17, 5:47 AM ET"), upgraded by an inline script to "2 hours ago" / "Yesterday" with the absolute stamp as the tooltip. A record with no time prints its date only. **Never the feed `pubDate`** — every feed item carries `08:00:00 +0000`. |
| "Today" marker | the story's Eastern date vs the build's | The script removes it once the Eastern date has moved on. |
| Masthead | the build clock | Weekday + date and "Updated 9:30 AM ET"; "N new episodes today" counted from the same stamps. |
| Developing stories | the digests' hooks + story headlines, 7 days | See calibration below. |
| Markets & launches | `api/mag7_quotes.json` (closes with `bar_date`), `api/spcx.json`, `api/tsla.json` (fallback only), `api/spacex_launches.json` `next` | Every value under its as-of date; older than 3 days = absent; a launch whose NET has passed = absent (server-side, and the script removes it client-side). TSLA from the quote file is labelled a "last quote", never "trading at". |
| Corrections | `engine.corrections.load_corrections` on every public show | Newest three, full text, each linking the corrected article; none = no block. |
| Claims record | `_claims_network_ledger` — the function `claims.html` calls | Unchanged from v2. |
| Today on Nerra | `engine.daily_edition.RELEASE_EASTERN`, `engine.release_schedule` (`NEWSLETTER_SLOT`, `SHORT_FIRST`, `SHORT_SPACING`; the long-form shares the Short's slot) | No typed times; the script ticks rows that have gone out today. |

### Developing stories — calibration

Matching is the `engine.story_recurrence` idea widened from one show's window
to the network's: salient words (its stopwords plus a list of generic
headline verbs, quantities and spelled-out numbers), minus words in more than
1.5% of the window's headlines (and never fewer than 8 — the beat words:
"tesla", "spacex", "launch"). Two headlines are one story at **≥ 3 shared
words that are ≥ 50% of the shorter headline's**; a thread needs **two or more
days** and an update in the **last 3 days**; a line the same show prints on
two days, or a one-word variant of it, is a segment label and never a story.
Nerra Daily (it re-tells every show), the interview shows and the
members-only desks are excluded.

Replayed on the committed digests for windows ending Oct 10 … Oct 17 2026
(~113 episodes, ~740-850 headlines each): **3-9 threads per window**, every
one a real thread. Window ending Oct 17: SpaceX's Super Heavy Booster 23
cryogenic testing (Oct 13 → 17), the Ebola case in Kenya (Omni View, Oct 11 →
Omni View Top World News, Oct 15), Perseverance's Mars distance record (FF,
Oct 14 → 15). Window ending Oct 14 adds the Pope's lung surgery and diagnosis,
Google's prediction-market ad policy, Kalshi/Polymarket volume records, the
delayed Roadster reveal, the Taiwan Megapack order, X's bundled subscription
and the CRS-35 launch and landing. Rejected settings: 2 shared words doubled
the count with false threads ("Google releases an AI detection tool" beside
"Google releases Gemini 4", two unrelated dinosaur finds, "trade deficit
widens" beside "Rome's deficit widens"); without the generic-word list
"Canucks visit the Hurricanes tonight" matched "Canucks visit the Islanders
tonight"; without the furniture rule MIT's daily "Unusual Whales Options
Flow" line read as a three-day story. A borderline case kept: "Arctic sea ice
shrinks to its 2026 minimum" and "New algorithm forecasts Arctic sea ice"
(FF → Planetterrian) — the same subject on two days, which is what the label
"Covered on 2 days" says.

### Freshness wiring

- **run-show finalize** (after every show): `--network --blogs --sitemap` as
  before, then — after the gallery manifest and search index are rebuilt —
  `generate_html.py --homepage` once more, so the front page's pictures and
  topic links come from the freshest indexes. `index.html` was already in its
  add list.
- **nerra-daily.yml**: a "Refresh the homepage" step after the edition is
  built (only when this run published it — a `--when-ready` exit leaves the
  homepage alone), `--homepage` only (`--network` would rewrite claims.html,
  the dashboards and member pages this workflow does not commit), and
  `index.html` added to the commit's add-paths. A failed refresh warns and
  never costs the edition commit.
- The nightly already regenerates and commits `index.html`.

### Guards changed in the promotion (each asserts the same property on the new page)

- `test_capture_measurement_2026_09_21`: the homepage left the text-level
  FORMS list (its one form is the shared Soft Personal macro); a rendered
  test checks every capture form on the page sends `engine.funnel`'s source.
- `test_multilingual::test_homepage_card_lists_languages`: rendered; names
  every produced language and no switched-off one (was: "中文" in the
  template).
- `test_site_review_2026_10_07_chrome`: the nav test accepts no override (and
  bans in-page anchors in any future one); the ranked-list test drops the
  retired orbit and pins `_rank_shows_by_audience(public)`.
- `test_network_quick_wins_2026_07_09`: the ticker iterates the day's stories
  (`p.latest`), not a typed list; article links via `story_href` /
  `ep.blog_url` replace the retired `episode-card-title` cards.
- `test_website_review_2026_09_03`: ticker + computed counts
  (`public_show_count`, `glance`); eager images capped at two on the RENDERED
  page.
- `test_landing_test_2026_10_17` / `_v2_`: render `generate_network_page`;
  the four "it is a test" guards became "it is the homepage" (indexable, in
  the sitemap as `/`, stub, no generator); the inline-signup class became the
  Soft-only rule; `alt=""` is allowed only on the shared show card's cover;
  the page-weight ceiling rose 400 → 450 KB.
