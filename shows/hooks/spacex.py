"""SpaceX Daily hooks — narrative memory + SPCX market quote + IPO debut.

Thin adapter over engine.show_memory (same pattern as Models & Agents /
Fascinating Frontiers), plus two SpaceX-specific injections:

* ``spcx_market_block`` — real-time SPCX quote for the digest's Market
  Watch section. SpaceX listed on Nasdaq June 12 2026 (the show's launch
  day); the fetcher mirrors the hard-won TSLA lessons from landmine #22:
  yfinance ``history()`` primary, ``fast_info`` secondary, ``0.0`` treated
  as falsy, sanity band + deviation guard vs the last cached quote, and a
  failed fetch NEVER overwrites the previous-good cache. A failed/invalid
  quote renders an EMPTY block — the prompts instruct the model to omit
  the price line entirely rather than speak "price unavailable".
* ``ipo_debut_section`` — Episode 1 ONLY: series-premiere brief framing
  the show's launch on SpaceX's IPO day, with verified IPO facts the
  episode must cross-check against the day's fetched coverage.
"""

from __future__ import annotations

import datetime
import json
import logging
from pathlib import Path

from engine import show_memory

logger = logging.getLogger(__name__)

_ROOT = Path(__file__).resolve().parent.parent.parent
_CACHE_PATH = _ROOT / "api" / "spcx.json"

# Sanity band for a freshly listed stock: IPO priced $135, day-one close
# $161. Deliberately wide — early public-market price discovery can swing
# hard in either direction without being a data error.
_PRICE_MIN, _PRICE_MAX = 30.0, 2000.0
# Reject a new quote that swings more than this vs the last cached close
# (defence-in-depth against a bad source day, per landmine #22).
_MAX_DEVIATION = 0.35


def pre_fetch(config, *, episode_num=None, today_str=None) -> dict:
    context = show_memory.memory_pre_fetch(config, "spacex")

    try:
        price, change_str, source = _fetch_spcx_quote()
    except Exception as exc:  # never let a quote failure block the episode
        logger.warning("SPCX quote fetch failed (non-fatal): %s", exc)
        price, change_str, source = 0.0, "", ""
    context["spcx_market_block"] = _build_market_block(price, change_str)

    # TST parity: tone hint from the day's tape + a date-rotated closing
    # that speaks the price ONLY when the quote passed validation (a bad
    # price day skips the stock sentence, never "price unavailable").
    context["tone_hint"] = _tone_from_change(price, change_str)
    context["closing_block"] = _pick_closing(price, change_str, source)

    context["ipo_debut_section"] = _ipo_debut_section(episode_num)
    return context


def post_generate(config, *, digest_text: str = "", episode_num: int = 0) -> None:
    show_memory.memory_post_generate(config, "spacex", digest_text, episode_num)


# ---------------------------------------------------------------------------
# SPCX quote (landmine #22 pattern, lean two-source chain)
# ---------------------------------------------------------------------------

def _fetch_spcx_quote() -> tuple[float, str, str]:
    """Return ``(price, change_str, source)`` or ``(0.0, "", "")`` when no
    source yields a quote that passes validation. ``source`` lets callers
    phrase honestly: a ``history`` bar is a close; a ``fast_info`` quote at
    the ~12:07 UTC run time is a live pre-market price, not a close."""
    for source_name, fetch in (
        ("yfinance_history", _quote_from_history),
        ("yfinance_fast_info", _quote_from_fast_info),
    ):
        try:
            result = fetch()
        except Exception as exc:
            logger.info("SPCX source %s failed: %s", source_name, exc)
            continue
        if not result:
            continue
        price, prev_close = result
        if not _validate(price):
            logger.warning(
                "SPCX source %s returned %s — failed validation, trying next",
                source_name, price,
            )
            continue
        change_str = ""
        if prev_close and prev_close > 0:
            pct = (price - prev_close) / prev_close * 100.0
            change_str = f"{'+' if pct >= 0 else ''}{pct:.1f}%"
        _persist(price, prev_close, change_str, source_name)
        return price, change_str, source_name
    return 0.0, "", ""


def _quote_from_history():
    import yfinance as yf

    hist = yf.Ticker("SPCX").history(period="5d")
    closes = [float(c) for c in hist["Close"].tolist() if c == c]  # NaN-safe
    if not closes:
        return None
    price = closes[-1]
    if not price:  # 0.0 degraded response — fall through (landmine #22)
        return None
    # A young listing may have a single bar; previous close is then
    # unavailable from history and the change string is simply omitted.
    prev_close = closes[-2] if len(closes) >= 2 else None
    return price, prev_close


def _quote_from_fast_info():
    import yfinance as yf

    info = yf.Ticker("SPCX").fast_info
    price = float(getattr(info, "last_price", 0.0) or 0.0)
    if not price:
        return None
    prev = float(getattr(info, "previous_close", 0.0) or 0.0) or None
    return price, prev


def _validate(price: float) -> bool:
    if not (_PRICE_MIN <= price <= _PRICE_MAX):
        return False
    cached = _load_cached_price()
    if cached and abs(price - cached) / cached > _MAX_DEVIATION:
        logger.warning(
            "SPCX quote %.2f deviates >%.0f%% from cached %.2f — rejected",
            price, _MAX_DEVIATION * 100, cached,
        )
        return False
    return True


def _load_cached_price() -> float | None:
    try:
        data = json.loads(_CACHE_PATH.read_text(encoding="utf-8"))
        price = float(data.get("price") or 0.0)
        return price or None
    except Exception:
        return None


def _persist(price: float, prev_close, change_str: str, source: str) -> None:
    try:
        _CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
        _CACHE_PATH.write_text(json.dumps({
            "symbol": "SPCX",
            "price": round(price, 2),
            "prev_close": round(prev_close, 2) if prev_close else None,
            "change_str": change_str,
            "source": source,
            "updated_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        }, indent=2) + "\n", encoding="utf-8")
    except Exception as exc:
        logger.warning("Could not persist SPCX cache (non-fatal): %s", exc)


def _build_market_block(price: float, change_str: str) -> str:
    """Digest-prompt block carrying the validated quote, or '' to make the
    prompts omit the price line entirely (never 'price unavailable')."""
    if not price:
        return ""
    change_part = f", {change_str} vs the previous close" if change_str else ""
    return (
        "### REAL-TIME SPCX QUOTE (use this number verbatim — do not "
        "substitute any price found in articles):\n"
        f"SPCX is at ${price:.2f}{change_part}."
    )


# ---------------------------------------------------------------------------
# Tone hint + spoken closing (TST parity)
# ---------------------------------------------------------------------------

def _tone_from_change(price: float, change_str: str) -> str:
    """Delivery hint from the day's tape (mirrors the TST pattern)."""
    if not price or not change_str:
        return "steady day — natural and conversational"
    if change_str.startswith("+") and change_str not in ("+0.0%",):
        return "positive day — upbeat and energetic"
    if change_str.startswith("-"):
        return "quieter day — thoughtful but still engaged"
    return "steady day — natural and conversational"


def _spoken_number(value: float) -> str:
    """Spell a dollar price for TTS ('161.45' → 'one hundred sixty-one
    dollars and forty-five cents')."""
    from engine.utils import number_to_words

    dollars = int(value)
    cents = int(round((value - dollars) * 100))
    spoken = f"{number_to_words(dollars)} dollars"
    if cents:
        spoken += f" and {number_to_words(cents)} cents"
    return spoken


def _price_sentence(price: float, change_str: str, source: str) -> str:
    """Spoken SPCX sentence, or '' when the quote isn't trustworthy.

    Phrasing is honest about market state: a ``history`` bar is a close;
    a ``fast_info`` quote at the ~12:07 UTC run time is live pre-market
    trade and must not be presented as a close.
    """
    if not price:
        return ""
    spoken = _spoken_number(price)
    change_part = ""
    if change_str:
        pct = change_str.lstrip("+-").rstrip("%")
        direction = "up" if change_str.startswith("+") else "down"
        from engine.utils import number_to_words
        try:
            whole, _, frac = pct.partition(".")
            pct_spoken = number_to_words(int(whole)) + (
                f" point {number_to_words(int(frac))}" if frac and int(frac) else ""
            )
            change_part = f", {direction} {pct_spoken} percent"
        except (TypeError, ValueError):
            change_part = ""
    if source == "yfinance_history":
        return f"S P C X closed at {spoken}{change_part}. "
    return f"S P C X is trading at {spoken}{change_part}. "


# Closing variants, rotated by calendar date (the TST anti-fossilization
# pattern). {price_sentence} is empty when the quote failed validation.
# Every variant MUST match the Closing chapter pattern in shows/spacex.yaml
# (drift guard in tests/test_spacex_show.py).
_CLOSING_VARIANTS = (
    (
        "Patrick: That's your SpaceX news for today. {price_sentence}"
        "If the show saves you time, a rating or review on Apple Podcasts or "
        "Spotify genuinely helps new listeners find it. "
        "I'm Patrick in Vancouver. Thanks for listening — see you tomorrow."
    ),
    (
        "Patrick: And that's a wrap on today's SpaceX developments. {price_sentence}"
        "Share this with a fellow spaceflight fan if you found it useful, "
        "and subscribe so you don't miss tomorrow's episode. "
        "I'm Patrick in Vancouver. See you next time."
    ),
    (
        "Patrick: That covers everything worth knowing about SpaceX today. {price_sentence}"
        "A quick rating on Apple Podcasts or Spotify goes a long way. "
        "I'm Patrick in Vancouver. See you tomorrow."
    ),
    (
        "Patrick: That's the day at SpaceX — that's a wrap. {price_sentence}"
        "If you're new here, subscribe and this briefing finds you every day. "
        "I'm Patrick in Vancouver. Thanks for being here, and I'll see you tomorrow."
    ),
)


def _pick_closing(price: float, change_str: str, source: str, *, date=None) -> str:
    d = date or datetime.date.today()
    template = _CLOSING_VARIANTS[d.toordinal() % len(_CLOSING_VARIANTS)]
    return template.format(price_sentence=_price_sentence(price, change_str, source))


# ---------------------------------------------------------------------------
# Episode 1 — IPO-day series premiere
# ---------------------------------------------------------------------------

# Verified against June 12 2026 coverage (CNBC, SpaceNews, Investing.com).
# The brief instructs the model to prefer the day's fetched sources where
# they give fresher/conflicting numbers — this block is grounding, not a
# substitute for the news.
_IPO_DEBUT = """
### SERIES PREMIERE — IPO DAY (Episode 1 only; HIGHEST PRIORITY)
This show launches TODAY — the day SpaceX became a public company. Episode 1 must do three jobs, in this order:

1. INTRODUCE THE SHOW (first ~60 seconds, placed AFTER the supplied intro line — the script still begins with the exact supplied intro, never a rewrite of it): SpaceX Daily is the daily companion for following SpaceX now that anyone can own a piece of it — every weekday: the news with sources, what the community is buzzing about, one honest counterpoint, the engineering and economics behind the headlines, and the SPCX market picture. Make the daily promise concrete, then invite listeners once, warmly, to subscribe so they never miss a day ("subscribe" or "follow" must appear in this introduction). One subscribe ask in the intro and one in the closing — never more.

2. TELL THE IPO STORY as the anchor segment. Verified facts to weave in (cross-check against today's fetched coverage; where today's sources give different or fresher numbers, the sources win; hedge anything not corroborated):
   - SpaceX listed on the Nasdaq under the ticker SPCX, priced at one hundred thirty-five dollars a share, and began trading June twelfth, twenty twenty-six.
   - The offering raised about seventy-five billion dollars — the largest IPO in history — valuing the company near one point eight trillion dollars at pricing.
   - First-day trading: shares touched the high one-sixties intraday and closed around one hundred sixty-one dollars, up roughly nineteen percent from the IPO price.
   - From the prospectus: roughly eighteen point seven billion dollars of revenue in twenty twenty-five, with Starlink contributing about two-thirds of it and now solidly profitable; the launch and Starship side still runs at a loss as it invests.
   - Stated uses of proceeds include AI compute infrastructure, continued Starship development, and Starlink expansion.
   - A dual-class share structure leaves Elon Musk with a controlling majority of voting power (he sold no shares in the offering) — state this plainly as a governance fact investors should understand: you are along for HIS ride.

3. EXPLAIN WHAT GOING PUBLIC CHANGES — the show's reason to exist daily:
   - For investors: quarterly earnings, SEC filings, and disclosure replace rumor; launch cadence, Starlink subscriber growth, and Starship milestones become trackable leading indicators — exactly what this show watches every day.
   - For the world and humanity: the public now funds and audits the push that has already collapsed the cost of reaching orbit, connected millions via Starlink, and aims at the Moon and Mars. Public ownership means public accountability — and this show holds both the optimism and the scrutiny.
   Keep this genuinely balanced: the Counterpoint discipline applies to the premiere too (valuation expectations, Musk's voting control, and launch-business losses are fair first-episode counterpoints).

4. THE ROAD AHEAD — close the premiere with what listeners get to watch unfold (genuine anticipation, each beat one or two sentences, grounded in the narrative memory programs — hedge timelines as targets, not promises):
   - Starship's next flight tests: booster catches, full reuse, and the orbital refueling demonstration that unlocks everything beyond Earth orbit.
   - The first earnings report SpaceX ever delivers as a public company — the day the world finally sees the numbers quarterly.
   - Starlink's direct-to-cell ramp and subscriber growth — the cash engine behind the whole program.
   - Starship carrying NASA astronauts back to the lunar surface, and further out, the first uncrewed Mars window.
   Land the point: these arcs will take years, and this show will be here every single day tracking them — that is what subscribing gets you. Then hand off to the closing.

Do NOT reference previous episodes. Do NOT oversell — enthusiasm grounded in numbers is the brand.
"""


def _ipo_debut_section(episode_num) -> str:
    if episode_num == 1:
        return _IPO_DEBUT.strip()
    return ""
