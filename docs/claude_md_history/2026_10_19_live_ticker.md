# The front page's ticker is live (Oct 19 2026)

Moved verbatim from CLAUDE.md on 2026-11-03; the rules that still bind are summarised there.

### The front page's ticker is live (Oct 19 2026)

Operator: the ticker should carry live content, stocks and headlines (on a
Monday at noon the strip still printed Friday's closes). Guards
`tests/test_live_ticker_2026_10_19.py`, `workers/gallery/test/markets.test.ts`;
register `live-ticker-2026-10-19`. Rules that bind: **`GET /api/markets` on the
gallery Worker** (`workers/gallery/src/markets.ts`) fetches Yahoo's chart API
server-side for a CLOSED list (`MARKET_SYMBOLS` = `engine.newsroom.MARKET_TICKERS`
+ SPCX, drift-guarded), caches one body a minute while the session is open (ten
minutes otherwise) and keeps a two-day last-good copy that fills a refused
symbol — **an old quote is never "live"**; `as_of` is the quote's own time;
the previous close is the last bar dated before the quote's day, never
`chartPreviousClose` (landmine #22). **`assets/js/live-ticker.js`** updates the
strip and the flagship quote lines from it (`data-live-markets`,
`data-symbol`; "Live · 12:21 PM ET" only when the Worker says the regular
session is open, else "Close · <date>"), re-reads the page's own newest build
for the Latest headlines (`data-live-headlines`, every
`LIVE_HEADLINES_REFRESH_S`; the RU/FR hubs too), and moves an overflowing row
by advancing its own scroll (still swipeable) — paused on hover, focus, touch,
its Pause button and a hidden tab, never moving under reduced motion, copies
`aria-hidden` and out of the tab order. Network data is written with
`textContent` only. The printed build-time values stay whenever the Worker does
not answer. Operator: `wrangler deploy` in `workers/gallery`.
