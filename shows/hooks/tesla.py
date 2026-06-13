"""Tesla-specific pre-fetch hook.

Provides extra context that the Tesla Shorts Time digest prompt needs:
- TSLA stock price and change string via a multi-source fallback chain
  (yfinance ``history`` → yfinance ``fast_info`` → direct Yahoo HTTP).
  Source of truth for the website, podcasts, RSS, blog, and newsletter
  — all consume the value this hook returns and the ``api/tsla.json``
  cache it writes.  See ``_fetch_tsla_price()`` and landmine #22.
- X posts section placeholder (disabled by default)
- Market movers section (Monday only)
- Content tracking for freshness
"""

from __future__ import annotations

import datetime
import logging
import re
from pathlib import Path

from engine.utils import number_to_words
from engine import tesla_memory

logger = logging.getLogger(__name__)


def pre_fetch(config, *, episode_num: int | None = None, today_str: str | None = None) -> dict:
    """Return extra template variables for the Tesla digest/podcast prompts.

    Called by ``run_show.py`` before digest generation.  Returns a dict
    that gets merged into the prompt template variables.
    """
    context: dict = {}

    # Stock price via Yahoo Finance v8 chart API (direct HTTP).
    # Same endpoint the website (`tesla.html`) uses as its fallback —
    # consolidating everything onto the authoritative real-time quote
    # source so website / podcasts / RSS / blog / newsletter never
    # diverge again.
    price, change_str = _fetch_tsla_price()
    context["price"] = f"{price:.2f}"
    context["change_str"] = change_str

    # Refresh the public Tesla data dashboard (best-effort, non-fatal):
    # live TSLA market data + 1y price history for tesla-dashboard.html.
    try:
        import subprocess, sys as _sys
        subprocess.run(
            [_sys.executable, str(Path(__file__).resolve().parent.parent.parent
                                  / "scripts" / "fetch_tesla_dashboard.py")],
            timeout=120, check=False,
        )
    except Exception as exc:
        logger.warning("Tesla dashboard data refresh failed (non-fatal): %s", exc)

    # X posts section (disabled — placeholder)
    context["x_posts_section"] = ""

    # NOTE: used_content_summary is populated by run_show.py from the
    # content tracker — do NOT override it here with an empty string.

    # Market movers (Monday only)
    if datetime.date.today().weekday() == 0:  # Monday
        context["market_movers_section"] = (
            "\n\n━━━━━━━━━━━━━━━━━━━━\n"
            "### Tesla Market Movers\n"
            "📊 Weekly Market Recap — Summarize this past week's key TSLA "
            "price movements, catalysts, and market sentiment shifts."
        )
    else:
        context["market_movers_section"] = ""

    # Podcast-specific vars.
    # The intro comes from engine.intros (day-varying pool; run_show.py
    # setdefaults it). The closing is supplied HERE because it carries the
    # stock price — but it rotates daily and gates the price sentence on
    # quote validity (see _pick_closing).
    context["tone_hint"] = _tone_from_change(change_str)
    context["closing_block"] = _pick_closing(context)

    # === Tesla Recursive Memory System (Narrative + Performance + Theme loops) ===
    # This is the core of TST's long-term self-improvement capability.
    try:
        output_dir = Path(config.episode.output_dir)
        memory_ctx = tesla_memory.get_tesla_memory_context(output_dir)
        context.update(memory_ctx)
    except Exception as exc:
        # A corrupt/unreadable tracker silently degrades every prompt the
        # show generates — make it loud enough to notice the day it
        # happens (ERROR + an Actions annotation), while staying non-fatal.
        logger.error("Tesla memory context injection failed (non-fatal): %s", exc)
        import os
        if os.environ.get("GITHUB_ACTIONS"):
            print(f"::warning::Tesla memory context injection failed — "
                  f"episode will generate WITHOUT narrative memory: {exc}")

    return context


def pronunciation_overrides() -> dict:
    """Return Tesla-specific pronunciation overrides.

    Called by ``run_show.py:_apply_pronunciation()`` to customize the
    shared ``prepare_text_for_tts()`` pipeline.
    """
    return {
        # Don't expand "ICE" to "I C E" — Tesla context uses it as
        # "internal combustion engine" but TTS reads it fine as the word.
        "skip_acronyms": {"ICE"},
    }


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

# Hard sanity range for parsed prices.  A real-time TSLA quote outside
# this band almost certainly means the upstream API returned a stale /
# malformed number; we'd rather ship ``(price unavailable)`` than a
# garbage figure into the digest.
#
# Updated May 15 2026: tightened from $50-$2000 to $200-$1500.
# TSLA hasn't traded below $200 in over a year and is structurally
# unlikely to drop below $200 in the near term given the post-2024
# trading range.
_TSLA_PRICE_MIN = 200.0
_TSLA_PRICE_MAX = 1500.0

# Tighter dynamic validation: a new price more than this fraction
# away from the LAST CACHED price (``api/tsla.json``) gets rejected as
# a probable bad quote.  TSLA's largest single-day moves over the past
# 2 years sit around 12-15%; setting the floor at 25% gives a
# comfortable margin for an unusually volatile earnings day while
# still catching the May 15 2026 "$444 → $250" regression
# (a ~44% drop) that motivated this guard.
_TSLA_MAX_PCT_DEVIATION = 0.25  # 25% from last known close

# Yahoo Finance v8 chart API endpoint — same one tesla.html falls back
# to via CORS proxies in the browser.  Server-side we call it directly
# (no proxy). ``range=5d`` is enough to guarantee a non-null
# ``chartPreviousClose`` even across long weekends / holidays —
# ``range=1d`` returns nulls outside RTH.
_YAHOO_CHART_URL = (
    "https://query2.finance.yahoo.com/v8/finance/chart/TSLA"
    "?interval=1d&range=5d"
)

# Yahoo Finance rejects requests without a real-browser User-Agent
# header (returns 401 ``Unauthorized``).  Mirror a current Firefox
# UA so the endpoint treats us as a regular fetch.
_YAHOO_UA = (
    "Mozilla/5.0 (X11; Linux x86_64; rv:121.0) "
    "Gecko/20100101 Firefox/121.0"
)

# Timeout for any single HTTP call.  GitHub Actions runner egress
# occasionally stalls; 10 s leaves plenty of headroom while staying
# under the cron-job wall clock budget.
_HTTP_TIMEOUT_S = 10.0


def _fetch_tsla_price() -> tuple[float, str]:
    """Get current TSLA price + change string with multi-source fallback.

    Tries sources in priority order until one returns a quote that
    passes validation (sanity band + deviation guard).  Each source
    is wrapped in its own try / except so a single failure cannot
    take down the chain.

    Sources (priority order):
      1. ``yfinance`` ``Ticker.history(period="5d")`` — proven reliable
         on GitHub Actions runners (the Modern Investing show uses
         the same library + endpoint successfully every weekday).
         yfinance manages its own cookie + crumb-token session, which
         Yahoo's anti-bot apparently trusts more than a bare
         ``requests.get``.
      2. ``yfinance`` ``Ticker.fast_info`` — adds the live last_price
         (intraday / pre-market / post-market) when history alone only
         gives end-of-day closes.  Falls through if ``fast_info``
         returns empty / None fields (its historical failure mode).
      3. Direct HTTP to Yahoo v8 chart API — works locally and from
         some egress IPs; useful as a third opinion if the yfinance
         session can't be established.

    Each source returns ``(price, prev_close, market_state)`` or
    ``None``.  Validation is applied uniformly.

    History:
      yfinance ``fast_info`` only (early 2026): operator caught it
        repeatedly returning ``$0.00 (price unavailable)``.  The
        ``or`` chain treated a returned ``0.0`` as falsy and fell
        through every fallback to no data.  See git blame on
        commit ``3247317``.
      Grok ``x_search`` (May 2026): queried X for the latest
        ``$TSLA`` cashtag post.  Failed twice within 48 h — Ep473
        (May 15) returned ``$250`` vs real ``~$444`` (stale post),
        Ep474 (May 16) returned ``price == prev_close`` (single-number
        post).  X posts are not an authoritative quote source.
      Direct Yahoo HTTP only (PR #385, May 18 2026): worked locally
        but Ep477 + Ep478 on GitHub Actions both came back
        ``(price unavailable)``.  The bare ``requests.get`` call
        doesn't carry Yahoo's session cookie / crumb, so Yahoo's
        anti-bot apparently returns a non-200 response for the GHA
        runner's egress IP range — even though yfinance's session-
        managed call to the same endpoint works fine in the same
        environment.  Multi-source chain (this fetcher, PR #386)
        keeps direct HTTP as the third opinion but leads with
        yfinance.

    Returns ``(price, change_str)``.  Failure modes (every source
    fails, every source returns out-of-band data): returns
    ``(0.0, "(price unavailable)")``.
    """
    last_cached = _load_last_cached_tsla_price()

    sources = (
        ("yfinance_history", _fetch_via_yfinance_history),
        ("yfinance_fast_info", _fetch_via_yfinance_fast_info),
        ("yahoo_v8_chart", _fetch_via_yahoo_v8_chart),
    )

    for source_name, source_fn in sources:
        try:
            quote = source_fn()
        except Exception as exc:
            logger.warning("TSLA source %s raised: %s", source_name, exc)
            continue
        if quote is None:
            logger.warning("TSLA source %s returned no data", source_name)
            continue

        price, prev_close, market_state = quote
        if not _validate_quote(price, prev_close, last_cached, source_name):
            continue

        market_status = _market_status_suffix(market_state)
        change = price - prev_close
        pct = (change / prev_close) * 100 if prev_close else 0.0
        direction = "▲" if change >= 0 else "▼"
        change_str = (
            f"{direction} ${abs(change):.2f} ({abs(pct):.1f}%){market_status}"
        )
        logger.info("TSLA via %s: $%.2f %s", source_name, price, change_str)

        # Persist the live price to ``api/tsla.json`` so the public
        # website (tesla.html) can render it without depending on its
        # own client-side Yahoo fetch (which is subject to browser
        # CORS and public proxy availability — see landmine #22).
        _persist_tsla_price_json(
            price=price, prev_close=prev_close, change=change, pct=pct,
            change_str=change_str, market_state=market_state,
            source=source_name,
        )
        return price, change_str

    logger.error("All TSLA price sources failed — returning placeholder")
    return 0.0, "(price unavailable)"


def is_price_publishable(price: float, change_str: str) -> bool:
    """Return True when TSLA price is safe to ship in RSS / newsletter."""
    if price <= 0:
        return False
    if "unavailable" in (change_str or "").lower():
        return False
    return _TSLA_PRICE_MIN <= price <= _TSLA_PRICE_MAX


_TSLA_BAD_PRICE_LINE = re.compile(
    r"^\*\*(?:REAL-TIME TSLA price|TSLA today):\*\*.*"
    r"(?:\(price unavailable\)|\$0\.00\b)",
    re.MULTILINE | re.IGNORECASE,
)


def scrub_unavailable_tsla_from_digest(text: str) -> str:
    """Strip broken TSLA price lines before audience-facing publish."""
    if not text:
        return text
    cleaned = _TSLA_BAD_PRICE_LINE.sub("", text)
    if cleaned != text:
        logger.warning(
            "Scrubbed unavailable TSLA price line from digest before publish",
        )
    return cleaned


def _validate_quote(
    price: float, prev_close: float, last_cached: float | None,
    source_name: str,
) -> bool:
    """Run sanity band + dynamic deviation guard against a candidate
    quote.  Returns True if the quote is trustworthy."""
    if not (_TSLA_PRICE_MIN <= price <= _TSLA_PRICE_MAX):
        logger.warning(
            "TSLA via %s: price %.2f outside sanity band [%.0f, %.0f]",
            source_name, price, _TSLA_PRICE_MIN, _TSLA_PRICE_MAX,
        )
        return False
    if not (_TSLA_PRICE_MIN <= prev_close <= _TSLA_PRICE_MAX):
        logger.warning(
            "TSLA via %s: prev_close %.2f outside sanity band",
            source_name, prev_close,
        )
        return False
    if last_cached is not None and last_cached > 0:
        deviation = abs(price - last_cached) / last_cached
        if deviation > _TSLA_MAX_PCT_DEVIATION:
            logger.warning(
                "TSLA via %s: price %.2f deviates %.1f%% from last "
                "cached $%.2f (cap %.0f%%) — rejecting.",
                source_name, price, deviation * 100, last_cached,
                _TSLA_MAX_PCT_DEVIATION * 100,
            )
            return False
    return True


def _market_status_suffix(market_state: str) -> str:
    """Render the ``(After-hours)`` / ``(Pre-market)`` suffix
    appended to the change string."""
    s = (market_state or "REGULAR").upper()
    if s == "PRE":
        return " (Pre-market)"
    if s == "REGULAR":
        return ""
    # POST, POSTPOST, CLOSED, anything unknown → after-hours.
    return " (After-hours)"


def _normalize_market_state(raw: object) -> str:
    """Bucket Yahoo's various ``marketState`` values into the three
    states our renderers know about (PRE / REGULAR / POST).
    ``None``, missing, or unknown values default to REGULAR (the
    honest fallback — no misleading after-hours suffix on a real
    regular-session quote)."""
    if not raw:
        return "REGULAR"
    s = str(raw).upper()
    if s == "PRE":
        return "PRE"
    if s == "REGULAR":
        return "REGULAR"
    return "POST"


def _fetch_via_yfinance_history() -> tuple[float, float, str] | None:
    """Pull TSLA price + previous close from
    ``yfinance.Ticker.history(period="5d")``.

    yfinance manages a cookie + crumb-token session against Yahoo
    that the bare ``requests.get`` path doesn't, which is why this
    works reliably on GitHub Actions egress IPs where direct HTTP
    has been observed to fail.

    Returns ``None`` on any failure or empty data; the dispatcher
    then moves on to the next source.
    """
    import yfinance as yf

    ticker = yf.Ticker("TSLA")
    hist = ticker.history(period="5d", interval="1d")
    if hist is None or hist.empty or len(hist) < 1:
        return None

    price = float(hist["Close"].iloc[-1])
    # ``history()`` doesn't expose marketState; default to REGULAR
    # (close-of-day is by definition a regular-session price).  The
    # fast_info source below picks up pre/post-market when relevant.
    prev_close = float(hist["Close"].iloc[-2]) if len(hist) >= 2 else price
    return price, prev_close, "REGULAR"


def _fetch_via_yfinance_fast_info() -> tuple[float, float, str] | None:
    """Pull TSLA via ``yfinance.Ticker.fast_info``.

    Historically flaky — operator caught it returning ``0.0`` for
    ``last_price`` mid-2026.  Kept as a secondary source because
    when it works it carries the live (pre / post-market) price
    that ``history()`` alone doesn't expose.  Treats ``0.0`` as
    falsy so a degraded response falls through to the next source.
    """
    import yfinance as yf

    ticker = yf.Ticker("TSLA")
    info = ticker.fast_info
    price = (
        getattr(info, "last_price", None)
        or getattr(info, "regularMarketPrice", None)
        or getattr(info, "postMarketPrice", None)
    )
    prev_close = (
        getattr(info, "previous_close", None)
        or getattr(info, "regular_market_previous_close", None)
    )
    if not price or not prev_close:
        return None

    raw_state = (
        getattr(info, "market_state", None)
        or getattr(info, "marketState", None)
    )
    return float(price), float(prev_close), _normalize_market_state(raw_state)


def _fetch_via_yahoo_v8_chart() -> tuple[float, float, str] | None:
    """Direct HTTP call to Yahoo Finance v8 chart API.

    Last-resort source — same endpoint the in-browser fallback on
    ``tesla.html`` uses.  Works locally and from some egress IPs;
    on GitHub Actions Yahoo has been observed returning non-200
    responses to the bare-``requests.get`` call (the yfinance
    sources above carry a cookie + crumb session that Yahoo trusts
    more).  Kept for environments where it does work, and as a
    third opinion the validator can cross-check.
    """
    import requests

    resp = requests.get(
        _YAHOO_CHART_URL,
        headers={"User-Agent": _YAHOO_UA, "Accept": "application/json"},
        timeout=_HTTP_TIMEOUT_S,
    )
    if resp.status_code != 200:
        logger.warning(
            "Yahoo v8 chart returned HTTP %s for TSLA (body=%r)",
            resp.status_code, resp.text[:200],
        )
        return None

    data = resp.json()
    result = data["chart"]["result"][0]
    meta = result["meta"]
    price = float(meta["regularMarketPrice"])

    # Previous close = the close of the bar immediately BEFORE the
    # latest bar.  ``meta.chartPreviousClose`` looks tempting but it
    # refers to the close BEFORE the chart's range window starts
    # (so for ``range=5d`` it's the close from 6 trading days ago) —
    # not yesterday's close.  Pull the actual previous bar's close
    # from the ``indicators.quote`` array instead, which mirrors what
    # ``yfinance.Ticker.history()`` returns.
    prev_close: float | None = None
    try:
        closes = result["indicators"]["quote"][0]["close"]
        # Skip any trailing None bars (Yahoo sometimes returns a
        # null placeholder for a not-yet-traded session).
        valid = [c for c in closes if c is not None]
        if len(valid) >= 2:
            prev_close = float(valid[-2])
    except (KeyError, IndexError, TypeError, ValueError):
        prev_close = None

    # Final fallback chain for prev_close: meta's previousClose
    # (yesterday's regular-session close, when populated) → meta's
    # chartPreviousClose (always populated but anchors before the
    # range window — usable only when no better option exists).
    if prev_close is None:
        prev_close_raw = meta.get("previousClose") or meta.get("chartPreviousClose")
        if prev_close_raw is None:
            return None
        prev_close = float(prev_close_raw)

    return price, prev_close, _normalize_market_state(meta.get("marketState"))


def _load_last_cached_tsla_price() -> float | None:
    """Read the last cached TSLA price from ``api/tsla.json``.

    Returns ``None`` if the file doesn't exist, can't be parsed, or
    has a missing/invalid ``price`` field.  Used by
    :func:`_fetch_tsla_price` as the baseline for the dynamic
    deviation guard (rejects new prices that swing > 25% from the
    last known close).

    First-ever run has no cache; the check is skipped on ``None`` so
    the very first persist after a deploy isn't blocked.
    """
    import json
    from pathlib import Path

    try:
        path = Path(__file__).resolve().parent.parent.parent / "api" / "tsla.json"
        if not path.exists():
            return None
        data = json.loads(path.read_text(encoding="utf-8"))
        price = float(data.get("price", 0))
        return price if price > 0 else None
    except Exception as exc:  # pragma: no cover — best-effort
        logger.warning("Could not read last cached tsla.json: %s", exc)
        return None


def _persist_tsla_price_json(
    *, price: float, prev_close: float, change: float, pct: float,
    change_str: str, market_state: str, source: str = "unknown",
) -> None:
    """Write the latest TSLA price to ``api/tsla.json`` (best-effort).

    Same-origin file served by GitHub Pages.  Updated every Tesla
    pipeline run.  Failure is non-fatal — the digest pipeline
    continues even if the write fails, and the website falls back to
    its in-browser Yahoo Finance path.

    The ``source`` field records which of the multi-source chain
    actually produced the value (``yfinance_history`` /
    ``yfinance_fast_info`` / ``yahoo_v8_chart``).  The management
    dashboard surfaces this so the operator can tell at a glance
    which path is winning — and notice if a particular source has
    been silently failing for days.
    """
    import json
    import datetime as _dt
    from pathlib import Path

    payload = {
        "price": round(price, 2),
        "prev_close": round(prev_close, 2),
        "change": round(change, 2),
        "change_pct": round(pct, 2),
        "change_str": change_str,
        "market_state": market_state,
        "fetched_at": _dt.datetime.utcnow().replace(microsecond=0).isoformat() + "Z",
        "source": source,
    }
    try:
        api_dir = Path(__file__).resolve().parent.parent.parent / "api"
        api_dir.mkdir(exist_ok=True)
        out_path = api_dir / "tsla.json"
        out_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        logger.info("TSLA price cached to %s", out_path)
    except Exception as exc:  # pragma: no cover — best-effort
        logger.warning("Failed to persist tsla.json (non-fatal): %s", exc)


def _format_price_for_speech(price_str: str) -> str:
    """Convert a price string like '411.82' to spoken words."""
    try:
        price = float(price_str)
        whole = int(price)
        cents = round((price - whole) * 100)
        whole_words = number_to_words(whole)
        if cents:
            cents_words = number_to_words(cents)
            return f"{whole_words} dollars and {cents_words} cents"
        return f"{whole_words} dollars"
    except (ValueError, TypeError):
        return f"{price_str} dollars"


def _format_change_for_speech(change_str: str) -> str:
    """Convert '▲ $0.57 (0.1%)' to natural speech like 'up fifty-seven cents, zero point one percent'."""
    if not change_str or change_str == "(price unavailable)":
        return "price unavailable"

    direction = "up" if "▲" in change_str else "down"

    # Extract dollar amount and percentage
    dollar_match = re.search(r"\$([\d.]+)", change_str)
    pct_match = re.search(r"([\d.]+)%", change_str)

    parts = [direction]

    if dollar_match:
        try:
            amount = float(dollar_match.group(1))
            whole = int(amount)
            cents = round((amount - whole) * 100)
            if whole > 0 and cents > 0:
                parts.append(f"{number_to_words(whole)} dollars and {number_to_words(cents)} cents")
            elif whole > 0:
                parts.append(f"{number_to_words(whole)} dollars")
            elif cents > 0:
                parts.append(f"{number_to_words(cents)} cents")
        except (ValueError, TypeError):
            pass

    if pct_match:
        try:
            pct_val = float(pct_match.group(1))
            pct_words = number_to_words(pct_val)
            parts.append(f"{pct_words} percent")
        except (ValueError, TypeError):
            pass

    return ", ".join(parts)


def _tone_from_change(change_str: str) -> str:
    """Pick a tone hint based on overall energy of the day."""
    if "▲" in change_str:
        return "positive day — upbeat and energetic"
    elif "▼" in change_str:
        return "quieter day — thoughtful but still optimistic"
    return "steady day — natural and conversational"


# Closing variants, rotated deterministically by date so the daily
# sign-off doesn't fossilize into a single sentence (through Ep505 every
# episode ended with the identical words — the exact daily-show tic the
# network bans everywhere else). ``{price_sentence}`` is empty when the
# quote failed validation, so a bad price day simply skips the stock
# mention instead of speaking "closed at zero dollars, price unavailable".
_CLOSING_VARIANTS = (
    (
        "Patrick: That's your Tesla news for today. {price_sentence}"
        "If you found this useful, a rating or review on Apple Podcasts or Spotify "
        "really helps new listeners find the show. "
        "You can also find us on X at tesla shorts time. "
        "I'm Patrick in Vancouver. Thanks for listening, and I'll see you tomorrow."
    ),
    (
        "Patrick: And that's a wrap on today's Tesla news. {price_sentence}"
        "If you enjoyed this episode, please leave a rating or review — "
        "it genuinely helps other Tesla fans find us. "
        "I'm Patrick in Vancouver. See you tomorrow."
    ),
    (
        "Patrick: That covers it for today's Tesla developments. {price_sentence}"
        "Share this episode with a fellow Tesla enthusiast if you found it useful, "
        "and subscribe so you don't miss tomorrow's episode. "
        "I'm Patrick in Vancouver. Thanks for being here."
    ),
    (
        "Patrick: And that's everything worth knowing about Tesla today. {price_sentence}"
        "If the show saves you time, a quick rating on Apple Podcasts or Spotify "
        "goes a long way. You can also find us on X at tesla shorts time. "
        "I'm Patrick in Vancouver. I'll see you tomorrow."
    ),
)


def _price_sentence(price_str: str, change_str: str) -> str:
    """Build the spoken stock sentence, or '' when the quote isn't trustworthy.

    Phrasing follows the market state embedded in ``change_str`` — the
    pipeline runs ~12:00 UTC (~8 AM ET), so a ``fast_info`` quote can be a
    live pre-market price that must not be presented as a close.
    """
    try:
        price_val = float(price_str)
    except (TypeError, ValueError):
        return ""
    if not is_price_publishable(price_val, change_str):
        return ""

    price_spoken = _format_price_for_speech(price_str)
    change_spoken = _format_change_for_speech(change_str)
    if "Pre-market" in change_str:
        return f"T S L A is trading at {price_spoken} in the pre-market, {change_spoken}. "
    if "After-hours" in change_str:
        return f"T S L A is at {price_spoken} in after-hours trading, {change_spoken}. "
    return f"T S L A closed at {price_spoken}, {change_spoken}. "


def _pick_closing(context: dict, *, date: datetime.date | None = None) -> str:
    """Return the day's closing block.

    Rotates through ``_CLOSING_VARIANTS`` by calendar date and injects the
    stock sentence only when the quote passed validation (see
    ``_price_sentence``). Stock price is mentioned only at the end of the
    episode, keeping the focus on the news over the ticker.
    """
    d = date or datetime.date.today()
    template = _CLOSING_VARIANTS[d.toordinal() % len(_CLOSING_VARIANTS)]
    sentence = _price_sentence(
        context.get("price", "0.00"), context.get("change_str", ""),
    )
    return template.format(price_sentence=sentence)
