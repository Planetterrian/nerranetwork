"""MAG 7 Daily hooks (Sep 2026, docs/new_shows_plan_2026_09_22.md §4.2).

pre_fetch supplies, in one ``hook_context`` block for the digest prompt:
  1. THE TAPE — the seven companies' last regular-session closes with the
     session date (engine.market_quotes). Every price is a CLOSE; the show
     runs before New York opens, so nothing it says is "trading at".
  2. The next earnings date per company when the data source has one —
     "not listed" otherwise, never a guessed date.
  3. What Tesla Shorts Time covered in the last day, so MAG 7 speaks Tesla
     only at company level (results, capital, regulation, the share) and
     never re-tells TST's product and community stories.
Plus the show's narrative memory. Every step is non-fatal.
"""

from __future__ import annotations

import datetime as _dt
import logging
from pathlib import Path

from engine import show_memory
from engine.market_quotes import fetch_daily_closes, persist, tape_block
from engine.sibling_coverage import sibling_block

logger = logging.getLogger(__name__)

_SLUG = "mag7"
_ROOT = Path(__file__).resolve().parent.parent.parent
CACHE_PATH = _ROOT / "api" / "mag7.json"

#: The seven, in the show's fixed order. Alphabet trades as GOOGL and GOOG;
#: the tape carries GOOGL (the two classes move together) and the show copy
#: names both.
TICKERS = ("GOOGL", "AMZN", "AAPL", "META", "MSFT", "NVDA", "TSLA")
NAMES = {
    "GOOGL": "Alphabet", "AMZN": "Amazon", "AAPL": "Apple", "META": "Meta",
    "MSFT": "Microsoft", "NVDA": "NVIDIA", "TSLA": "Tesla",
}

_TST_LENS = (
    "MAG 7 covers Tesla only as a company — results, guidance, capital, "
    "regulation and the share — and leaves products, FSD, energy and "
    "community to Tesla Shorts Time."
)


def _earnings_block(today: _dt.date) -> str:
    """Next earnings date per company, or 'not listed'. Best-effort."""
    lines = ["### EARNINGS CALENDAR (from the market-data source; instruction — "
             "use only dates listed here, never infer one)"]
    try:
        import yfinance as yf
    except Exception:  # noqa: BLE001
        return ""
    for t in TICKERS:
        when = "not listed"
        try:
            cal = yf.Ticker(t).calendar or {}
            dates = cal.get("Earnings Date") if isinstance(cal, dict) else None
            future = sorted(d for d in (dates or []) if hasattr(d, "isoformat") and d >= today)
            if future and (future[0] - today).days <= 60:
                when = future[0].isoformat()
        except Exception as exc:  # noqa: BLE001
            logger.info("earnings date lookup failed for %s: %s", t, exc)
        lines.append(f"- {NAMES[t]} ({t}): {when}")
    return "\n".join(lines)


#: run_show waits 60 s for pre_fetch, then DROPS the whole hook context. The
#: tape comes first; the earnings calendar (seven more network calls) is
#: skipped if the tape has already used this much of that budget.
_CALENDAR_BUDGET_S = 25.0


def pre_fetch(config, *, episode_num=None, today_str=None) -> dict:
    import time

    started = time.monotonic()
    context = show_memory.memory_pre_fetch(config, _SLUG)
    parts = []
    try:
        quotes = fetch_daily_closes(TICKERS, cache_path=CACHE_PATH)
        # A --test run must not rewrite the public cache (NERRA_HOOKS_READONLY).
        import os
        if os.environ.get("NERRA_HOOKS_READONLY", "").strip() != "1":
            persist(quotes, CACHE_PATH)
        parts.append(tape_block(quotes, NAMES, TICKERS))
    except Exception as exc:  # noqa: BLE001
        logger.warning("mag7 tape failed (non-fatal): %s", exc)
        parts.append(tape_block([], NAMES, TICKERS))
    try:
        cal = ""
        if time.monotonic() - started < _CALENDAR_BUDGET_S:
            cal = _earnings_block(_dt.date.today())
        else:
            logger.warning("mag7: tape took >%.0fs — earnings calendar skipped", _CALENDAR_BUDGET_S)
        if cal:
            parts.append(cal)
    except Exception as exc:  # noqa: BLE001
        logger.warning("mag7 earnings calendar failed (non-fatal): %s", exc)
    try:
        sib = sibling_block("Tesla Shorts Time", "digests/tesla_shorts_time",
                            days=1, lens=_TST_LENS)
        if sib:
            parts.append(sib)
    except Exception as exc:  # noqa: BLE001
        logger.warning("mag7 sibling block failed (non-fatal): %s", exc)
    context["hook_context"] = "\n\n".join(p for p in parts if p)
    return context


def post_generate(config, *, digest_text="", episode_num=None) -> None:
    show_memory.memory_post_generate(config, _SLUG, digest_text or "", episode_num or 0)
