# Landmine 22 — TSLA price source: multi-source fallback chain (May 2026)

Moved verbatim from CLAUDE.md on 2026-11-03; the rules that still bind are summarised there.

22. **TSLA price source: multi-source fallback chain (May 2026)** —
    `shows/hooks/tesla.py:_fetch_tsla_price()` tries three sources
    in priority order until one returns a quote that passes
    validation:

    1. **`yfinance.Ticker.history(period="5d")`** — primary.  Same
       library + endpoint Modern Investing uses successfully every
       weekday.  yfinance manages a cookie + crumb-token session
       against Yahoo internally, which Yahoo's anti-bot trusts.
    2. **`yfinance.Ticker.fast_info`** — secondary.  Adds the live
       pre / post-market price when `history()` alone gives only
       end-of-day closes.  Treats `0.0` as falsy (the historical
       degraded-response failure mode) so it falls through cleanly.
    3. **Direct HTTP to Yahoo v8 chart API** — last resort.  Works
       locally and from some egress IPs but the bare `requests.get`
       call (no session cookies / no crumb token) is observed to
       return non-200s from GitHub Actions runner IPs at times.

    Each source returns `(price, prev_close, market_state)` or
    `None`; the same validation (`$200–$1500` sanity band, 25%
    deviation guard) gates every source, so a single bad source
    can't ship a wrong number.

    The `api/tsla.json` cache the hook writes is the single source
    the website's primary path reads.  Cache file records
    `"source": "yfinance_history"` / `"yfinance_fast_info"` /
    `"yahoo_v8_chart"` so the management dashboard can tell at a
    glance which path is winning — and notice if the primary has
    been silently failing for days.

    **Three prior fetchers failed and were superseded:**

    - **yfinance `fast_info` only (early 2026):** operator caught
      it repeatedly returning `$0.00 (price unavailable)`.  The
      `or` chain treated `0.0` as falsy and fell through every
      fallback to no data.  See git blame on commit `3247317`.
    - **Grok `x_search` (May 1–18 2026):** queried X for the latest
      `$TSLA` cashtag post.  Failed twice within 48 h.  TST Ep473
      (May 15) returned $250 vs a real ~$444 (Grok pulled from a
      stale post — caught by the deviation guard).  TST Ep474 (May
      16) returned `price == prev_close == $415.50` because the X
      post Grok latched onto only quoted a single number (caught
      by the operator).  X posts are not an authoritative quote
      source.
    - **Direct Yahoo HTTP only (PR #385, May 18 2026):** worked
      locally but Ep477 (May 19) + Ep478 (May 20) both shipped
      `(price unavailable)` on GitHub Actions.  Bare `requests.get`
      doesn't carry the cookie + crumb session yfinance manages,
      and Yahoo's anti-bot apparently treats GHA egress IPs
      differently for unauthenticated v8 calls than for
      session-managed yfinance calls to the same endpoint.

    **Subtle previous-close bug fixed at the same time:** the
    direct HTTP source originally read `meta.chartPreviousClose`
    as previous close.  That field is the close BEFORE the chart's
    range window (so for `range=5d` it's the close from 6 trading
    days ago — `$445.27` on 2026-05-20 vs the correct
    `$404.11` for yesterday).  The HTTP source now reads
    `indicators.quote[0].close[-2]` (the bar immediately before
    the latest), which mirrors what `yfinance.Ticker.history()`
    returns.  Meta fields are only fallbacks for null bar data.

    **Sanity band:** prices outside `$200 – $1500` are rejected.

    **Dynamic deviation guard:** new prices that swing more than
    25% from the last cached close are rejected.  Load-bearing
    under the Grok fetcher; kept on the multi-source chain as
    defence-in-depth (any single source's bad day still gets the
    chain to fall through to the next).

    **`yfinance` is now also the primary** — it remains required
    for Modern Investing's trade-execution pricing across many
    tickers, and now powers Tesla too.

    **Drift guards:** 31 unit tests in `tests/test_tesla_hook.py`
    pin per-source happy paths, chain fall-through semantics
    (source 1 fails → source 2 tries; source 1 + 2 fail → source
    3 tries), validation rejection forcing fall-through to the
    next source, `marketState: null` rendering as REGULAR (not
    After-hours), and persistence (success writes, failure does
    NOT overwrite the previous-good cache).  Plus the
    `test_bar_close_array_is_authoritative` guard explicitly
    pins the HTTP source on `indicators.quote[0].close[-2]` over
    `meta.chartPreviousClose`.
