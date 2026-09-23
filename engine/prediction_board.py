"""The prediction-market board as hook articles (Sep 2026).

Prediction Markets Daily (docs/new_shows_plan_2026_09_22.md §4.11) carries
one short segment, The Board: at most five of the day's most-traded markets,
each with its implied probability, its venue, its 24-hour volume and the time
it was read. A model asked for "the popular markets" with nothing in front of
it writes them from memory, and the claims gate strips every number it cannot
trace — so, like the local shows' roads and weather
(engine/local_conditions.py), the board arrives as ordinary hook ARTICLES: one
per market, a real public URL, the numbers in ``content_text``. The digest
cites each by its URL and ``engine.claims.build_local_texts`` verifies a quote
against the copy the run already holds, with no second fetch.

Venues (public, keyless endpoints, probed 2026-09-23 from this session):

* Polymarket's Gamma API (``gamma-api.polymarket.com/events``) — events
  sorted server-side by 24-hour volume, with tags. Volume is US dollars.
* Kalshi's public trade API (``api.elections.kalshi.com/trade-api/v2/events``)
  — events with their markets and a category, NOT sorted by volume, and it
  rate-limits a fast crawl (HTTP 429 after ~15 quick pages). Paged slowly,
  one retry on a 429, then ranked from what was read. Volume is contracts,
  each paying at most one dollar — never reported as dollars.
* Manifold's search API (``api.manifold.markets/v0/search-markets``) — PLAY
  MONEY (mana). Binary markets with many traders only; its perpetual
  contracts are excluded.

What is left off the board, by rule (the MAG 7 lesson, plan §9b): sports
games and parlays, esports, recurring "what price will X hit" ladders and
tweet-count markets, near-certain markets (a market priced at 0.05% or 99.9%
tells a listener nothing and draws volume from arbitrage), and markets under
the volume floor. What survives is still only a candidate: the digest picks
five at most and says so plainly when a market is thin.

Every function is best-effort: a network error, a 429 or a bad payload
returns what it has (often nothing) and logs. Nothing here writes a file.
"""

from __future__ import annotations

import datetime as _dt
import json
import logging
import time
from typing import Any, Callable, Dict, Iterable, List, Optional, Sequence

logger = logging.getLogger(__name__)

USER_AGENT = "Mozilla/5.0 (compatible; NerraNetwork/1.0; +https://nerranetwork.com)"
TIMEOUT_S = 20

#: A fetcher returns parsed JSON given a URL. Injectable so tests never
#: touch the network. It may raise; callers treat any exception as "no data".
Fetch = Callable[[str], Any]

POLYMARKET_EVENTS_URL = (
    "https://gamma-api.polymarket.com/events?order=volume24hr&ascending=false"
    "&active=true&closed=false&limit=100")
KALSHI_EVENTS_URL = (
    "https://api.elections.kalshi.com/trade-api/v2/events?status=open"
    "&with_nested_markets=true&limit=200")
MANIFOLD_SEARCH_URL = (
    "https://api.manifold.markets/v0/search-markets?sort=24-hour-vol&limit=100")

#: Real-money floor for the board, in US dollars of 24-hour volume (plan
#: §4.11: "sub-$10k-volume markets" are dropped).
MIN_USD_VOLUME_24H = 10_000
#: Kalshi reports contracts; a contract pays at most $1, so the same floor in
#: contracts is the conservative reading of it.
MIN_KALSHI_CONTRACTS_24H = 10_000
#: Manifold is play money: its floor is traders, not volume.
MIN_MANIFOLD_TRADERS = 100
#: Below this 24-hour volume the digest calls a real-money market thin.
THIN_USD_VOLUME_24H = 25_000

#: A market whose most likely outcome is priced outside this band is
#: near-certain either way and says nothing a listener can use (the first live
#: read put "Will the US confirm that aliens exist" on the board at 3.1%).
MIN_PROB, MAX_PROB = 0.05, 0.97

#: A market that opened inside this many hours is "new" (New and Notable).
NEW_WINDOW_H = 72

#: Candidates per venue. The board itself is five at most (the prompt).
MAX_POLYMARKET, MAX_KALSHI, MAX_MANIFOLD = 4, 4, 2
#: Outcomes shown for a multi-outcome event.
MAX_OUTCOMES = 3

#: Polymarket tags that keep an event off the board.
POLYMARKET_EXCLUDED_TAGS = frozenset({
    "sports", "esports", "games", "crypto-prices", "hit-price", "recurring",
    "finance-updown", "tweets-markets", "up-or-down", "daily-close",
})
#: Kalshi categories that keep an event off the board. "Mentions" (will a
#: speaker say a word) are a regulatory STORY this week — the CFTC's staff
#: advisory — but a board of them is noise.
KALSHI_EXCLUDED_CATEGORIES = frozenset({"Sports", "Mentions", "Crypto"})
#: Kalshi strike types that make a market a numeric ladder rung (GDP above
#: 2.5%, S&P above 7,000): one rung is not a question a listener can follow.
KALSHI_LADDER_STRIKES = frozenset({
    "greater", "less", "between", "greater_or_equal", "less_or_equal",
})
#: The one legal line a board article carries. Deliberately neutral: this
#: text is the pipeline's own copy, so the claims gate treats anything in it
#: as sourced — a specific claim about which provinces or states allow which
#: venue would be verified against nothing and would go stale with the next
#: ruling. Specific legal claims come from dated news articles only.
VENUE_ACCESS_LINE = ("Whether {venue} is available, and for which contracts, depends "
                     "on where the user lives; the rules differ by country, province "
                     "and state and are changing.")
#: Kalshi's paging: slow, bounded, one retry on a 429.
KALSHI_MAX_PAGES = 20
KALSHI_PAGE_PAUSE_S = 0.35
KALSHI_RETRY_PAUSE_S = 3.0


def _http_json(url: str) -> Any:
    import requests

    resp = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=TIMEOUT_S)
    resp.raise_for_status()
    return resp.json()


def _now() -> _dt.datetime:
    return _dt.datetime.now(_dt.timezone.utc).replace(microsecond=0)


def _read_stamp(now: _dt.datetime) -> str:
    return now.strftime("%Y-%m-%d %H:%M UTC")


def _f(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _parse_time(value: Any) -> Optional[_dt.datetime]:
    if not value:
        return None
    if isinstance(value, (int, float)):
        # Manifold uses epoch milliseconds.
        return _dt.datetime.fromtimestamp(float(value) / 1000.0, tz=_dt.timezone.utc)
    text = str(value).strip().replace("Z", "+00:00")
    try:
        parsed = _dt.datetime.fromisoformat(text)
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=_dt.timezone.utc)


def _pct(p: float) -> str:
    """0.455 -> '45.5%'; whole numbers lose the decimal."""
    value = round(p * 100, 1)
    return f"{value:.0f}%" if value == int(value) else f"{value:.1f}%"


def _money(n: float) -> str:
    return f"${n:,.0f}"


def _points(delta: float) -> str:
    return f"{delta * 100:+.1f} points"


def _date(d: Optional[_dt.datetime]) -> str:
    return d.strftime("%Y-%m-%d") if d else "unknown"


def _is_new(opened: Optional[_dt.datetime], now: _dt.datetime) -> bool:
    return bool(opened) and (now - opened) <= _dt.timedelta(hours=NEW_WINDOW_H)


def _article(*, title: str, url: str, source: str, lines: Sequence[str],
             now: _dt.datetime, new: bool) -> Dict[str, Any]:
    body = "\n".join(lines)
    return {
        "title": title,
        "url": url,
        "description": lines[1][:300] if len(lines) > 1 else title,
        "content_text": body,
        "source_name": source,
        "published_date": now.isoformat(),
        # A market opened last spring and trading hard today is today's news.
        "exempt_stale": True,
        # Consumed by board_block() only; the pipeline ignores unknown keys.
        "board_new": new,
    }


# ---------------------------------------------------------------------------
# Polymarket
# ---------------------------------------------------------------------------

def _poly_yes(market: Dict[str, Any]) -> Optional[float]:
    raw = market.get("outcomePrices")
    try:
        prices = json.loads(raw) if isinstance(raw, str) else list(raw or [])
        return float(prices[0])
    except (TypeError, ValueError, IndexError, json.JSONDecodeError):
        return None


def _poly_outcomes(event: Dict[str, Any]) -> List[tuple]:
    """(label, yes_probability, one_day_change) for the outcomes to show.

    Mutually exclusive outcomes (``negRisk`` — candidates in one race) are
    ranked by probability. Anything else keeps the event's own order: a
    "by...?" event is a ladder of cumulative DATES, and ranking it by price
    put December above October on the first live read.
    """
    live = [m for m in event.get("markets") or []
            if m.get("active", True) and not m.get("closed")]
    rows = []
    for m in live:
        p = _poly_yes(m)
        if p is None:
            continue
        label = str(m.get("groupItemTitle") or "").strip()
        rows.append((label, p, _f(m.get("oneDayPriceChange"))))
    if len(rows) == 1 and not rows[0][0]:
        return [("Yes", rows[0][1], rows[0][2])]
    rows = [r for r in rows if r[0]]
    if event.get("negRisk"):
        rows.sort(key=lambda r: -r[1])
    return rows[:MAX_OUTCOMES]


def polymarket_articles(fetch: Fetch = _http_json, now: Optional[_dt.datetime] = None,
                        max_markets: int = MAX_POLYMARKET) -> List[Dict[str, Any]]:
    now = now or _now()
    try:
        events = fetch(POLYMARKET_EVENTS_URL)
    except Exception as exc:  # noqa: BLE001
        logger.warning("Polymarket board fetch failed (non-fatal): %s", exc)
        return []
    out: List[Dict[str, Any]] = []
    for ev in events if isinstance(events, list) else []:
        tags = {str(t.get("slug") or "").lower() for t in ev.get("tags") or []
                if isinstance(t, dict)}
        if tags & POLYMARKET_EXCLUDED_TAGS:
            continue
        vol = _f(ev.get("volume24hr"))
        if vol < MIN_USD_VOLUME_24H:
            continue
        outcomes = _poly_outcomes(ev)
        if not outcomes or not (MIN_PROB <= max(o[1] for o in outcomes) <= MAX_PROB):
            continue
        opened = _parse_time(ev.get("startDate") or ev.get("createdAt"))
        closes = _parse_time(ev.get("endDate"))
        title = str(ev.get("title") or "").strip()
        slug = str(ev.get("slug") or "").strip()
        if not title or not slug:
            continue
        lines = [f"Polymarket market, read at {_read_stamp(now)}.",
                 f"Question: {title}"]
        for label, p, change in outcomes:
            line = f"- {label}: {_pct(p)} implied probability"
            if abs(change) >= 0.03:
                line += f" ({_points(change)} in 24 hours)"
            lines.append(line)
        lines.append(f"24-hour trading volume: {_money(vol)} (US dollars).")
        total = _f(ev.get("volume"))
        if total:
            lines.append(f"Total volume since the market opened: {_money(total)}.")
        if vol < THIN_USD_VOLUME_24H:
            lines.append("This is a thin market by 24-hour volume.")
        lines.append(f"Opened: {_date(opened)}. Scheduled to close: {_date(closes)}.")
        lines.append(VENUE_ACCESS_LINE.format(venue="Polymarket"))
        out.append(_article(title=f"Polymarket: {title}",
                            url=f"https://polymarket.com/event/{slug}",
                            source="Polymarket", lines=lines, now=now,
                            new=_is_new(opened, now)))
        if len(out) >= max_markets:
            break
    return out


# ---------------------------------------------------------------------------
# Kalshi
# ---------------------------------------------------------------------------

def _kalshi_pages(fetch: Fetch, max_pages: int, sleep: Callable[[float], None]) -> List[dict]:
    events: List[dict] = []
    cursor = ""
    for page in range(max_pages):
        url = KALSHI_EVENTS_URL + (f"&cursor={cursor}" if cursor else "")
        data = None
        for attempt in range(2):
            try:
                data = fetch(url)
                break
            except Exception as exc:  # noqa: BLE001
                if attempt == 0 and "429" in str(exc):
                    sleep(KALSHI_RETRY_PAUSE_S)
                    continue
                logger.info("Kalshi paging stopped at page %d: %s", page + 1, exc)
                return events
        if not isinstance(data, dict):
            return events
        events.extend(data.get("events") or [])
        cursor = data.get("cursor") or ""
        if not cursor:
            break
        sleep(KALSHI_PAGE_PAUSE_S)
    return events


def _kalshi_price(m: Dict[str, Any]) -> float:
    last = _f(m.get("last_price_dollars"))
    if last > 0:
        return last
    bid, ask = _f(m.get("yes_bid_dollars")), _f(m.get("yes_ask_dollars"))
    return (bid + ask) / 2 if bid and ask else 0.0


def kalshi_articles(fetch: Fetch = _http_json, now: Optional[_dt.datetime] = None,
                    max_markets: int = MAX_KALSHI, max_pages: int = KALSHI_MAX_PAGES,
                    sleep: Callable[[float], None] = time.sleep) -> List[Dict[str, Any]]:
    now = now or _now()
    events = _kalshi_pages(fetch, max_pages, sleep)
    ranked = []
    for ev in events:
        if str(ev.get("category") or "") in KALSHI_EXCLUDED_CATEGORIES:
            continue
        markets = [m for m in ev.get("markets") or []
                   if str(m.get("strike_type") or "") not in KALSHI_LADDER_STRIKES
                   and not m.get("mve_collection_ticker")]
        if not markets:
            continue
        vol = sum(_f(m.get("volume_24h_fp")) for m in markets)
        if vol < MIN_KALSHI_CONTRACTS_24H:
            continue
        rows = [(str(m.get("yes_sub_title") or m.get("title") or "").strip(),
                 _kalshi_price(m), _f(m.get("previous_price_dollars")),
                 _parse_time(m.get("open_time"))) for m in markets]
        rows = [r for r in rows if r[0]]
        # Rank only mutually exclusive outcomes; a date ladder keeps its order
        # (the Polymarket rule — see _poly_outcomes).
        if ev.get("mutually_exclusive"):
            rows.sort(key=lambda r: -r[1])
        rows = rows[:MAX_OUTCOMES]
        if not rows or not (MIN_PROB <= max(r[1] for r in rows) <= MAX_PROB):
            continue
        ranked.append((vol, ev, rows))
    ranked.sort(key=lambda r: -r[0])
    out: List[Dict[str, Any]] = []
    for vol, ev, rows in ranked[:max_markets]:
        title = str(ev.get("title") or "").strip()
        series = str(ev.get("series_ticker") or ev.get("event_ticker") or "").lower()
        opened = min((r[3] for r in rows if r[3]), default=None)
        lines = [f"Kalshi market, read at {_read_stamp(now)}.",
                 f"Question: {title}"]
        for label, p, prev, _o in rows:
            line = f"- {label}: {_pct(p)} implied probability"
            if prev and abs(p - prev) >= 0.03:
                line += f" ({_points(p - prev)} since the previous day's price)"
            lines.append(line)
        lines.append(f"24-hour volume: {vol:,.0f} contracts (each pays at most one "
                     "US dollar).")
        lines.append(f"Category on Kalshi: {ev.get('category') or 'unlisted'}.")
        lines.append(VENUE_ACCESS_LINE.format(venue="Kalshi"))
        out.append(_article(title=f"Kalshi: {title}",
                            url=f"https://kalshi.com/markets/{series}",
                            source="Kalshi", lines=lines, now=now,
                            new=_is_new(opened, now)))
    return out


# ---------------------------------------------------------------------------
# Manifold (play money)
# ---------------------------------------------------------------------------

def manifold_articles(fetch: Fetch = _http_json, now: Optional[_dt.datetime] = None,
                      max_markets: int = MAX_MANIFOLD) -> List[Dict[str, Any]]:
    now = now or _now()
    try:
        markets = fetch(MANIFOLD_SEARCH_URL)
    except Exception as exc:  # noqa: BLE001
        logger.warning("Manifold board fetch failed (non-fatal): %s", exc)
        return []
    out: List[Dict[str, Any]] = []
    for m in markets if isinstance(markets, list) else []:
        if m.get("outcomeType") != "BINARY" or m.get("isResolved"):
            continue
        traders = int(_f(m.get("uniqueBettorCount")))
        p = m.get("probability")
        if traders < MIN_MANIFOLD_TRADERS or p is None:
            continue
        p = float(p)
        if not (MIN_PROB <= p <= MAX_PROB):
            continue
        question = str(m.get("question") or "").strip()
        url = str(m.get("url") or "").strip()
        if not question or not url.startswith("https://manifold.markets/"):
            continue
        opened = _parse_time(m.get("createdTime"))
        lines = [f"Manifold market, read at {_read_stamp(now)}.",
                 f"Question: {question}",
                 f"- Yes: {_pct(p)} implied probability",
                 f"Traders: {traders:,}. 24-hour volume: {_f(m.get('volume24Hours')):,.0f} "
                 "mana.",
                 "Manifold uses play money (mana), not dollars; its prices are "
                 "forecasts from traders with nothing but reputation at stake.",
                 f"Opened: {_date(opened)}."]
        out.append(_article(title=f"Manifold: {question}", url=url, source="Manifold",
                            lines=lines, now=now, new=_is_new(opened, now)))
        if len(out) >= max_markets:
            break
    return out


# ---------------------------------------------------------------------------
# Assembly
# ---------------------------------------------------------------------------

def gather_board(builders: Iterable[Callable[[], List[Dict[str, Any]]]]) -> List[Dict[str, Any]]:
    """Run each venue builder, keep what came back. Never raises."""
    out: List[Dict[str, Any]] = []
    for build in builders:
        try:
            out.extend(build() or [])
        except Exception as exc:  # noqa: BLE001
            logger.warning("prediction board builder failed (non-fatal): %s", exc)
    return out


def board_block(articles: Sequence[Dict[str, Any]]) -> str:
    """The digest instruction that goes with the board articles.

    Names the two sections these articles feed, the five-market cap and the
    posture, and — on a day no venue answered — the one honest fallback, so
    a data-less day produces one sentence rather than a board from memory.
    """
    if not articles:
        return ("### THE BOARD DATA (instruction — do not include in output)\n"
                "No venue's market data reached the pipeline today. The Board is ONE "
                "sentence saying the market data was unavailable — never a market, "
                "a probability or a volume from memory. New and Notable uses only "
                "markets a news article above names.")
    venues = sorted({a.get("source_name", "") for a in articles})
    new = [a.get("title", "") for a in articles if a.get("board_new")]
    lines = [
        "### THE BOARD DATA (instruction — do not include in output)",
        f"The market articles above from {', '.join(venues)} are the ONLY source for "
        "The Board. Choose at most FIVE, favouring questions a listener would recognize "
        "and real-money venues. Each board line gives the question, the leading "
        "outcome's implied probability, the venue, the 24-hour volume in that venue's "
        "own unit (dollars, contracts or mana — never convert), and the read time. "
        "Call a market thin when its article says so. Say why a price moved ONLY when "
        "a news article above says why; otherwise report the move and nothing more. "
        "Never add a market, a probability or a volume those articles do not carry.",
    ]
    if new:
        lines.append("Markets that opened in the last three days (candidates for New "
                     "and Notable): " + "; ".join(new) + ".")
    return "\n".join(lines)
