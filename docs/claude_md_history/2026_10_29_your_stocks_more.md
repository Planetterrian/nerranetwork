# Your stocks, more of Mira, and the app on the Home Screen (Oct 29 2026)

Moved verbatim from CLAUDE.md on 2026-11-03; the rules that still bind are summarised there.

### Your stocks, more of Mira, and the app on the Home Screen (Oct 29 2026)

Operator: My Nerra showed the wrong prices; members should choose their own
stocks; Mira should personalize more between shows; and visitors and members
should be told to add the app to their Home Screen (register
`markets-mira-app-2026-10-29`; guards `tests/test_markets_mira_app_2026_10_29.py`,
`workers/gallery/test/markets.test.ts`, `personal.test.ts`, `handlers.test.ts`).
Rules that bind:

- **No page prints a price from api/tsla.json or api/spcx.json.** The show
  run writes them before the market opens, so after the bell My Nerra printed
  the previous day's close under today's date. Quotes come from the markets
  route through `assets/js/nn-markets.js` (one module, My Nerra and the front
  page's strip). The committed files remain the edition builder's fallback
  for TSLA and SPCX only.
- **One ticker shape in three places**: `engine.personal_edition.TICKER_RE`,
  the Worker's `MEMBER_SYMBOL_RE` (markets.ts, also used by personal.ts
  `cleanTickers`) and `nn-markets.js` `SHAPE`; `TICKERS_MAX` 8 in all three.
  `GET /api/markets?extra=` takes up to 10 symbols outside the closed list,
  each fetched and cached on its own (same TTLs, its own last-good copy);
  a symbol Yahoo does not know comes back in `unknown`. A member's stocks
  are `preferences.tickers` (absent = never saved = Tesla and SpaceX); a
  visitor's stay in `localStorage nnMe.tickers` and become the account's
  list on My Nerra.
- **The markets minute speaks the member's own stocks** from one route call
  per build for every member (`fetch_market_quotes`): a listing name with its
  suffix dropped, else the ticker as letter-name words (never "S P", the
  SPCX lesson); "trading at" only for a live quote; a stock with no quote is
  left out.
- **Mira's links call gets more of the listener, still one call**: their
  stocks and which of today's episodes name them (a one-word name, or the
  whole name; "Advanced" never stands in for AMD), names that turn up in two
  or more episodes (`cross_show_connections`: proper names read mid-sentence,
  never a word the text also uses in lower case, outlets, demonyms or short
  acronyms), the shows absent today and why (`absent_show_notes`, from the
  registry schedule), milestone editions, and a whole-day `title` that
  becomes the episode's name (validated by `validate_edition_title`; the
  first show's hook is the fallback). Memory notes say an edition CARRIED a
  story, never that the listener heard it. ⚠️ AUDIO: A/B-listen the first
  edition.
- **A member's feed token never reaches analytics**: the player reports an
  `/api/feed/` URL as `personal_edition/<file>`; signing out clears every
  private item the browser kept (`NNPlayer.forgetPrivate`).
- **The installed app signs in by code**: the sign-in email carries a
  six-digit code (`POST /api/login-code`, hashed in KV for the link's
  lifetime, five wrong tries and it is gone, its own rate limit), because on
  iPhone an emailed link opens Safari, whose cookies the Home Screen app
  does not share.
- **The app is offered, not pushed**: a sheet (`nn-app.js`) for a member, a
  visitor on their second day, or someone who just pressed play; once a
  session, snoozed 14 days by "Not now", never over the cookie choice, never
  in the app. `/app.html` says what the app does as built and how to add it
  on each device; cards on My Nerra and in the footer. The app badge shows
  while today's edition is built and unplayed on this device. Shared scripts
  and the stylesheet carry a content hash (`asset_v`) so the service worker
  never pairs a new page with an old script.

- **Every page is the app.** 1,479 of 3,042 committed pages predate the app
  layer, so the tab bar vanished on any older blog post. `sw.js`
  (`withAppLayer`) adds the three shared scripts before `</body>` of any page
  that does not load `nn-app.js`; a regenerated page passes through untouched
  (`VERSION` bumped so installed apps pick it up). The tab bar lights the
  section a page belongs to (a post, a show page or a topic is Shows), carries
  **Back** whenever the app session has a page to go back to (an iPhone Home
  Screen app has no browser Back), scrolls to the top or reloads on a second
  tap of its own tab, and same-site `target="_blank"` links open in place.
- **A template change to a static page commits the page it renders.** PR
  #1577 changed `account_page.html.j2` and never committed `account.html`,
  so the site kept serving the old page, which read the morning's
  `api/tsla.json`, and members saw yesterday's close until the nightly ran.
  `tests/test_read_buttons_2026_10_29.py` reads the committed file too.
- **Read sits beside every Play and Watch** (`.nn-read` in `styles/main.css`):
  My Nerra's cards, Latest rail and catch-up list, the front page and language
  hubs' story meta (not the lead, which has "Read the full story"), Watch's
  cards, the For you band, and the player bar (`nn-gp-read`, icon-only on a
  phone). An edition's Read opens its written notes from the feed item,
  rebuilt from an allow-list of tags with https links only, never pasted as
  markup.

Operator: `wrangler deploy` in `workers/gallery` (member symbols, tickers,
the sign-in code). Until then member stocks show "No quote yet" and the
markets minute speaks only what the route answers.
