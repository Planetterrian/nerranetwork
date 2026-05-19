"""Tesla-specific pre-fetch hook.

Provides extra context that the Tesla Shorts Time digest prompt needs:
- TSLA stock price and change string via Yahoo Finance's v8 chart API
  (direct HTTP, no library wrapper). Source of truth for the website,
  podcasts, RSS, blog, and newsletter — all consume the value this
  hook returns and the ``api/tsla.json`` cache it writes.
- X posts section placeholder (disabled by default)
- Market movers section (Monday only)
- Content tracking for freshness
"""

from __future__ import annotations

import datetime
import logging
import re

from engine.utils import number_to_words

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

    # Podcast-specific vars
    context["tone_hint"] = _tone_from_change(change_str)
    # Intro/closing are now handled by engine.intros (day-varying, dynamic).
    # Tesla hook only provides stock-specific closing with price data.
    context["closing_block"] = _pick_closing(context)

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
# (no proxy, no library wrapper). ``range=5d`` is enough to guarantee
# a non-null ``chartPreviousClose`` even across long weekends /
# holidays — ``range=1d`` returns nulls outside RTH.
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

# Timeout for the Yahoo call.  GitHub Actions runner egress occasionally
# stalls; 8 s is the website's own per-proxy timeout and well under the
# cron-job wall clock budget.
_YAHOO_TIMEOUT_S = 8.0


def _fetch_tsla_price() -> tuple[float, str]:
    """Get current TSLA price + change string via Yahoo Finance.

    Calls the v8 chart API (``query2.finance.yahoo.com/v8/finance/chart/TSLA``)
    directly with ``requests`` — no yfinance library, no CORS proxy,
    no third-party stock service.  Same authoritative endpoint
    ``tesla.html`` uses as its in-browser fallback, so the website,
    podcasts, RSS, blog, and newsletter all derive from one identical
    source of truth.

    History:
      yfinance (early 2026): the library wrapped this same endpoint
        but added aggressive retry / parallel-fetch logic that
        triggered Yahoo's rate-limit on the GitHub Actions runner's
        egress IPs.  Repeatedly returned ``$0.00 (price unavailable)``.
      Grok x_search (May 2026): queried X for the latest ``$TSLA``
        cashtag post.  Failed in two distinct ways operator caught
        within 48 h of each other — Ep473 (May 15) returned $250 vs
        a real ~$444 (pulled from a stale post), Ep474 (May 16)
        returned price == prev_close (single-number post, no change).
        X posts are not an authoritative quote source.
      Direct Yahoo (May 18 2026, this fetcher): one HTTP call, real
        ``regularMarketPrice`` + ``chartPreviousClose`` + ``marketState``
        from the same data that powers finance.yahoo.com.  One call
        per Tesla cron run (~once / day) is well below any practical
        rate limit when we're not using the yfinance retry-storm
        client.

    Returns ``(price, change_str)`` in the same shape as before so
    every downstream consumer keeps working without changes.

    Failure modes (network down, non-200 response, missing fields,
    out-of-range price, deviation guard trip): returns
    ``(0.0, "(price unavailable)")``.
    """
    try:
        import requests
    except Exception as exc:  # pragma: no cover — requests is in requirements.txt
        logger.error("Could not import requests for TSLA fetch: %s", exc)
        return 0.0, "(price unavailable)"

    try:
        resp = requests.get(
            _YAHOO_CHART_URL,
            headers={"User-Agent": _YAHOO_UA, "Accept": "application/json"},
            timeout=_YAHOO_TIMEOUT_S,
        )
    except Exception as exc:
        logger.error("Yahoo Finance request for TSLA failed: %s", exc)
        return 0.0, "(price unavailable)"

    if resp.status_code != 200:
        logger.error(
            "Yahoo Finance returned HTTP %s for TSLA (body=%r)",
            resp.status_code, resp.text[:200],
        )
        return 0.0, "(price unavailable)"

    try:
        data = resp.json()
    except Exception as exc:
        logger.error("TSLA Yahoo JSON parse error: %s", exc)
        return 0.0, "(price unavailable)"

    # Yahoo's chart response shape:
    #   { "chart": { "result": [ { "meta": { "regularMarketPrice": ...,
    #     "chartPreviousClose": ..., "previousClose": ...,
    #     "marketState": "REGULAR"|"PRE"|"POST"|"CLOSED" } } ] } }
    try:
        meta = data["chart"]["result"][0]["meta"]
        price = float(meta["regularMarketPrice"])
        # Yahoo provides both fields; ``chartPreviousClose`` is the one
        # the website's fallback path prefers because it's never null
        # when ``range >= 5d``.  ``previousClose`` is the secondary.
        prev_close = float(
            meta.get("chartPreviousClose") or meta.get("previousClose")
        )
    except (KeyError, IndexError, TypeError, ValueError) as exc:
        logger.error("TSLA meta fields missing/malformed: %s", exc)
        return 0.0, "(price unavailable)"

    # Hard sanity range — guards against Yahoo briefly returning a
    # stale split-adjusted figure or a malformed payload.
    if not (_TSLA_PRICE_MIN <= price <= _TSLA_PRICE_MAX):
        logger.error("TSLA price %.2f outside sanity band [%.0f, %.0f]",
                     price, _TSLA_PRICE_MIN, _TSLA_PRICE_MAX)
        return 0.0, "(price unavailable)"
    if not (_TSLA_PRICE_MIN <= prev_close <= _TSLA_PRICE_MAX):
        logger.error("TSLA prev_close %.2f outside sanity band", prev_close)
        return 0.0, "(price unavailable)"

    # Dynamic deviation check — reject prices that swing more than
    # 25% from the last cached close.  No cache → skip the check
    # (first-ever run can't compare).  Yahoo is unlikely to return a
    # 25%+ off price, but the guard is cheap defence-in-depth.
    last_cached = _load_last_cached_tsla_price()
    if last_cached is not None and last_cached > 0:
        deviation = abs(price - last_cached) / last_cached
        if deviation > _TSLA_MAX_PCT_DEVIATION:
            logger.error(
                "TSLA price %.2f deviates %.1f%% from last cached "
                "$%.2f (cap %.0f%%) — rejecting.",
                price, deviation * 100, last_cached,
                _TSLA_MAX_PCT_DEVIATION * 100,
            )
            return 0.0, "(price unavailable)"

    # Yahoo uses ``PRE`` / ``REGULAR`` / ``POST`` / ``CLOSED`` /
    # ``POSTPOST``, and occasionally returns ``null`` mid-session.
    # ``None`` and missing both default to REGULAR — that's the
    # honest fallback for an unknown state (no misleading
    # after-hours suffix).
    raw_state_val = meta.get("marketState")
    raw_state = str(raw_state_val).upper() if raw_state_val else "REGULAR"
    if raw_state == "PRE":
        market_state = "PRE"
        market_status = " (Pre-market)"
    elif raw_state == "REGULAR":
        market_state = "REGULAR"
        market_status = ""
    else:
        # POST, POSTPOST, CLOSED — all read as after-hours on a podcast
        # that ships at 8 AM ET (the most common case).
        market_state = "POST"
        market_status = " (After-hours)"

    change = price - prev_close
    pct = (change / prev_close) * 100 if prev_close else 0.0
    direction = "▲" if change >= 0 else "▼"
    change_str = f"{direction} ${abs(change):.2f} ({abs(pct):.1f}%){market_status}"
    logger.info("TSLA via Yahoo Finance: $%.2f %s", price, change_str)

    # Persist the live price to ``api/tsla.json`` so the public
    # website (tesla.html) can render it without depending on its own
    # client-side Yahoo fetch (which is subject to browser CORS and
    # public proxy availability — see landmine #22).
    _persist_tsla_price_json(
        price=price, prev_close=prev_close, change=change, pct=pct,
        change_str=change_str, market_state=market_state,
    )
    return price, change_str


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
    change_str: str, market_state: str,
) -> None:
    """Write the latest TSLA price to ``api/tsla.json`` (best-effort).

    Same-origin file served by GitHub Pages.  Updated every Tesla
    pipeline run (daily + the M&A / MIT shows that share this hook
    in their own pre-fetch loops where applicable).  Failure is
    non-fatal — the digest pipeline continues even if the write
    fails, and the website falls back to its Yahoo Finance path.
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
        "source": "yahoo_finance_v8",
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


def _pick_intro(
    context: dict,
    *,
    episode_num: int | None = None,
    today_str: str | None = None,
) -> str:
    """Return a standard intro line for the podcast script.

    Includes episode number and date so listeners know exactly which
    episode they're hearing.  Stock price is reserved for the closing.
    """
    ep_part = f", episode {episode_num}" if episode_num else ""
    date_part = f" Today is {today_str}." if today_str else ""
    return (
        f"Patrick: Hey, welcome to Tesla Shorts Time Daily{ep_part}. "
        f"I'm Patrick in Vancouver.{date_part} "
        f"Here's what's happening with Tesla today."
    )


def _pick_closing(context: dict) -> str:
    """Return a standard closing block with stock price and long-term perspective.

    Stock price is mentioned only at the end of the episode, paired with
    a reminder to focus on the long term over short-term fluctuations.
    """
    price = context.get("price", "0.00")
    change = context.get("change_str", "")

    price_spoken = _format_price_for_speech(price)
    change_spoken = _format_change_for_speech(change)

    return (
        "Patrick: That's your Tesla news for today. "
        "T S L A closed at {price}, {change}. "
        "If you found this useful, a rating or review on Apple Podcasts or Spotify "
        "really helps new listeners find the show. "
        "You can also find us on X at tesla shorts time. "
        "I'm Patrick in Vancouver. Thanks for listening, and I'll see you tomorrow."
    ).format(price=price_spoken, change=change_spoken)
