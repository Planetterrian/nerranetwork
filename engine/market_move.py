"""A big move in the show's own stock gets its sourced reason (Nov 24 2026).

The two flagships speak their company's share price in every closing. In the
sixteen episodes to Nov 24 2026 Tesla closed with "down seven point six
percent" on three mornings and "up eleven point five percent" on a fourth,
and SpaceX Daily with "down seven point seven percent" twice, and no episode
said one word about why: the digest prompts keep price commentary out of the
news (rightly, on an ordinary day), and nothing fetched the reason.

This module owns that case, and only that case:

* ``BIG_MOVE_PCT`` — the size at which a move is news on its own show.
* ``describe`` — the hook's one call: a move dict, or ``None`` below the bar.
* ``fetch_move_articles`` — ONE web search for reporting on that session's
  move, kept only when the result is dated inside the session's window. The
  results are ordinary articles: they reach the numbered news list, the page
  fetch and the claims gate like any other.
* ``render_block`` — the fact block for the digest prompt. It states the
  move and whether dated reporting was found; the standing instruction on
  what to do with it lives in the prompt (a block label states a fact).

No reason is ever written here, and none is inferred: when the search finds
nothing the block says so, and the prompt's rule is to give no reason.
"""

from __future__ import annotations

import datetime as _dt
import logging
import re
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)

#: A close-to-close move of at least this many percent is a story on the
#: company's own show. Nov 9-24 2026: 4 of 12 TSLA sessions and 3 of 11 SPCX
#: sessions cleared it; none was explained on air.
BIG_MOVE_PCT = 4.0

#: Results kept per move.
MAX_ARTICLES = 4

#: Marks the articles' origin for metrics and debugging.
SOURCE_KIND_MARKET_MOVE = "market_move"

_PCT_RE = re.compile(r"(-?\d+(?:\.\d+)?)\s*%")


def parse_pct(change_str: str) -> Optional[float]:
    """Signed percent from either hook's change string.

    Tesla writes ``"▲ $39.64 (11.5%)"`` / ``"▼ $28.59 (7.6%)"``; SpaceX
    writes ``"+4.4%"`` / ``"-7.7%"``. ``None`` when there is no percent.
    """
    text = change_str or ""
    m = _PCT_RE.search(text)
    if not m:
        return None
    pct = abs(float(m.group(1)))
    down = "▼" in text or m.group(1).startswith("-") or text.strip().startswith("-")
    return -pct if down else pct


def describe(
    ticker: str, company: str, change_str: str, *,
    price: float = 0.0, now: Optional[_dt.datetime] = None,
    threshold: float = BIG_MOVE_PCT,
) -> Optional[Dict[str, Any]]:
    """The move as data, or ``None`` when it is under the bar or the quote
    is not a completed session's close (a pre-market or intraday print is a
    move still in progress; its reason is not yet reported)."""
    pct = parse_pct(change_str)
    if pct is None or abs(pct) < threshold:
        return None
    if any(tag in (change_str or "") for tag in ("Pre-market", "After-hours", "Intraday")):
        return None
    from engine.market_calendar import close_session_date
    session = close_session_date(now)
    return {
        "ticker": ticker,
        "company": company,
        "pct": round(pct, 1),
        "direction": "up" if pct > 0 else "down",
        "price": float(price or 0.0),
        "session_date": session.isoformat(),
        "session_label": f"{session.strftime('%A, %B')} {session.day}, {session.year}",
    }


def _session(move: Dict[str, Any]) -> Optional[_dt.date]:
    try:
        return _dt.date.fromisoformat(str(move.get("session_date") or ""))
    except ValueError:
        return None


def search_topic(move: Dict[str, Any]) -> tuple:
    """``(title, brief)`` for the one search."""
    verb = "rose" if move["direction"] == "up" else "fell"
    pct = abs(float(move["pct"]))
    title = (f"Why {move['company']} ({move['ticker']}) shares {verb} about "
             f"{pct:g} percent on {move['session_label']}")
    brief = (
        "Find NEWS REPORTS published on that trading day or the day after "
        "that state what moved the stock: the event, filing, analyst action, "
        "deal report or market-wide move the report itself gives as the "
        "reason. Prefer wire services and established financial newsrooms. "
        "A page that only lists the price, a stock-screener page, a forum "
        "and a prediction about future prices are not results. Give each "
        "result's publication date."
    )
    return title, brief


def _dated_in_window(article: Dict[str, Any], session: _dt.date,
                     today: _dt.date) -> bool:
    raw = str(article.get("published_date") or "")
    m = re.match(r"(\d{4})-(\d{2})-(\d{2})", raw)
    if not m:
        return False  # an undated page is not evidence for THIS session
    try:
        day = _dt.date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
    except ValueError:
        return False
    return session - _dt.timedelta(days=1) <= day <= today


def fetch_move_articles(
    move: Dict[str, Any], *,
    research: Optional[Callable] = None,
    today: Optional[_dt.date] = None,
    max_articles: int = MAX_ARTICLES,
) -> List[Dict[str, Any]]:
    """Dated reporting on the move, or ``[]``. Never raises."""
    session = _session(move)
    if session is None:
        return []
    today = today or _dt.datetime.now(_dt.timezone.utc).date()
    try:
        if research is None:
            from engine.fetcher import fetch_topic_research_articles as research
        title, brief = search_topic(move)
        found = research(title, brief, max_results=max_articles * 2) or []
    except Exception as exc:  # noqa: BLE001 — the episode runs without it
        logger.warning("Market move search failed (%s) — no reason today", exc)
        return []
    kept: List[Dict[str, Any]] = []
    for art in found:
        if not isinstance(art, dict) or not art.get("url") or not art.get("title"):
            continue
        if "x.com/" in art["url"] or "twitter.com/" in art["url"]:
            continue
        if not _dated_in_window(art, session, today):
            continue
        kept.append({**art, "source_kind": SOURCE_KIND_MARKET_MOVE,
                     "exempt_stale": False})
        if len(kept) >= max_articles:
            break
    logger.info("Market move: %s %+.1f%% on %s — %d dated report(s) of %d found",
                move.get("ticker"), float(move.get("pct") or 0.0),
                move.get("session_date"), len(kept), len(found))
    return kept


def render_block(move: Optional[Dict[str, Any]],
                 articles: Optional[List[Dict[str, Any]]] = None) -> str:
    """The digest-prompt block, or ``""`` when there is no big move."""
    if not move:
        return ""
    pct = abs(float(move["pct"]))
    lines = [
        "### MARKET MOVE (data)",
        f"{move['ticker']} closed {move['direction']} {pct:g}% on "
        f"{move['session_label']}. A move of this size is news on this show.",
    ]
    arts = [a for a in (articles or []) if a.get("title")]
    if arts:
        lines.append("Dated reporting on this session's move, found by the "
                     "search made for it (in the news list above):")
        for a in arts:
            lines.append(f"- {a['title'].strip()} — {a.get('url', '')}")
    else:
        lines.append("No dated report explaining this session's move was "
                     "found by the search made for it.")
    return "\n".join(lines) + "\n"
