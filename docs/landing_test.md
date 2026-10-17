# Landing Test — the network as a news front page (Oct 17 2026)

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
