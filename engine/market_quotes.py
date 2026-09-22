"""Daily-close quotes for multi-ticker market shows (MAG 7 Daily, Sep 2026).

Design choice, from the network's own failures (CLAUDE.md "Flagship
review", Sep 4 2026, and landmine #22): a quote's VERB must come from what
the number actually is. SpaceX's show ran before the pre-market and spoke
the prior close as "is trading at" ten days running; Tesla's history
source spoke a mid-session price as "closed at". MAG 7 Daily runs at
06:46 New York, before any regular session, so this module deals ONLY in
completed daily bars: every price it returns is a regular-session close,
and it carries the bar's DATE so the digest can say which session it was.
The one piece of clock logic is ``session_complete``: yfinance includes
TODAY's partial bar while New York is open, so a bar dated today only
counts as a close after 16:00 New York.

Validation per ticker: a loose sanity band plus the same deviation guard
the Tesla and SpaceX chains use against the last cached close. A ticker
that fails is omitted — the tape says so; it never guesses.

The cache (``api/mag7_quotes.json`` — never ``api/<slug>.json``, which is the
per-show public episode API) is the single source a web widget or a later
review reads, and run-show.yml's commit step adds it explicitly.
"""

from __future__ import annotations

import datetime as _dt
import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Dict, Iterable, List, Optional, Tuple

logger = logging.getLogger(__name__)

ROOT = Path(__file__).resolve().parent.parent

#: A close more than this far from the last cached close is rejected — the
#: landmine-#22 guard (a stale or garbled source, never a real one-day move
#: for a mega-cap). Tesla uses 25%, SpaceX 35%.
MAX_DEVIATION = 0.30

#: Sanity band for any mega-cap share price, in USD.
PRICE_MIN, PRICE_MAX = 5.0, 20000.0


@dataclass(frozen=True)
class Quote:
    ticker: str
    close: float
    prev_close: Optional[float]
    bar_date: str            # ISO date of the session the close belongs to

    @property
    def change_pct(self) -> Optional[float]:
        if not self.prev_close:
            return None
        pct = round((self.close - self.prev_close) / self.prev_close * 100.0, 1)
        return 0.0 if pct == 0 else pct


#: The regular session ends at 16:00 America/New_York.
SESSION_CLOSE_HOUR = 16


def session_complete(bar_date: str, now: Optional[_dt.datetime] = None) -> bool:
    """True when *bar_date*'s regular session has ended.

    yfinance's daily history includes TODAY's partial bar while the market
    is open — the first MAG 7 dry run (15:37 New York, 2026-09-22) got
    seven "closes" dated today that were live prices. A bar from today only
    counts once New York has passed 16:00.
    """
    now = now or _dt.datetime.now(_dt.timezone.utc)
    try:
        from zoneinfo import ZoneInfo
        ny = now.astimezone(ZoneInfo("America/New_York"))
    except Exception:  # pragma: no cover
        ny = now - _dt.timedelta(hours=4)
    if bar_date != ny.date().isoformat():
        return True
    return ny.hour >= SESSION_CLOSE_HOUR


def completed_bars(rows: List[Tuple[str, float]], now: Optional[_dt.datetime] = None
                   ) -> Optional[Tuple[float, Optional[float], str]]:
    """(close, prev_close, bar_date) from ``(iso_date, close)`` rows, oldest
    first, ignoring an in-progress bar for today."""
    rows = [r for r in rows if r[1]]
    if rows and not session_complete(rows[-1][0], now):
        rows = rows[:-1]
    if not rows:
        return None
    bar_date, close = rows[-1]
    prev = rows[-2][1] if len(rows) >= 2 else None
    return close, prev, bar_date


def _history_fetch(ticker: str) -> Optional[Tuple[float, Optional[float], str]]:
    import yfinance as yf

    hist = yf.Ticker(ticker).history(period="10d")
    rows = [
        (idx.date().isoformat() if hasattr(idx, "date") else str(idx)[:10], float(c))
        for idx, c in zip(hist.index, hist["Close"].tolist()) if c == c
    ]
    return completed_bars(rows)


def load_cache(path: Path) -> Dict[str, dict]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return {q["ticker"]: q for q in data.get("quotes", []) if q.get("ticker")}
    except Exception:
        return {}


def valid_close(price: float, cached: Optional[float]) -> bool:
    if not (PRICE_MIN <= price <= PRICE_MAX):
        return False
    if cached and abs(price - cached) / cached > MAX_DEVIATION:
        return False
    return True


def fetch_daily_closes(
    tickers: Iterable[str],
    *,
    cache_path: Path,
    fetch: Callable[[str], Optional[Tuple[float, Optional[float], str]]] = _history_fetch,
) -> List[Quote]:
    """Validated daily closes, in the order given. Failures are omitted."""
    cached = load_cache(cache_path)
    out: List[Quote] = []
    for t in tickers:
        try:
            got = fetch(t)
        except Exception as exc:  # noqa: BLE001 — one ticker never sinks the tape
            logger.info("quote fetch failed for %s: %s", t, exc)
            continue
        if not got:
            continue
        close, prev, bar_date = got
        prior = (cached.get(t) or {}).get("close")
        if not valid_close(close, prior):
            logger.warning("%s close %.2f failed validation (cached %s) — omitted", t, close, prior)
            continue
        out.append(Quote(t, round(close, 2), round(prev, 2) if prev else None, bar_date))
    return out


def persist(quotes: List[Quote], cache_path: Path) -> None:
    if not quotes:
        return  # never overwrite a good cache with an empty one
    try:
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        cache_path.write_text(json.dumps({
            "updated_at": _dt.datetime.now(_dt.timezone.utc).isoformat(),
            "basis": "regular-session daily close",
            "quotes": [
                {"ticker": q.ticker, "close": q.close, "prev_close": q.prev_close,
                 "change_pct": q.change_pct, "bar_date": q.bar_date}
                for q in quotes
            ],
        }, indent=2) + "\n", encoding="utf-8")
    except Exception as exc:  # noqa: BLE001
        logger.warning("could not persist %s (non-fatal): %s", cache_path, exc)


def _signed_pct(pct: float) -> str:
    """``+1%`` not ``+1.0%``: MAG 7 Ep1 spoke "up one point zero percent"."""
    text = f"{pct:+.1f}"
    if text.endswith(".0"):
        text = text[:-2]
    return text + "%"


def tape_block(quotes: List[Quote], names: Dict[str, str], expected: Iterable[str]) -> str:
    """The digest's REAL-TIME TAPE block, or a one-line 'no quotes' notice.

    Every line is a CLOSE with its session date — the digest and the script
    say "closed", never "trading at". A missing ticker is named as missing.
    """
    expected = list(expected)
    if not quotes:
        return (
            "### MARKET TAPE (instruction — do not include in output)\n"
            "No validated closing prices were available today. The Tape section "
            "must say in one sentence that the price feed was unavailable, and "
            "no price may appear anywhere in the digest."
        )
    have = {q.ticker for q in quotes}
    lines = [
        "### MARKET TAPE — regular-session closes (use these numbers verbatim; "
        "never substitute a price from an article; every price is a CLOSE)",
    ]
    for q in quotes:
        chg = ""
        if q.change_pct is not None:
            chg = " (unchanged)" if q.change_pct == 0 else f" ({_signed_pct(q.change_pct)})"
        lines.append(f"- {names.get(q.ticker, q.ticker)} ({q.ticker}): closed at "
                     f"${q.close:,.2f}{chg} on {q.bar_date}")
    missing = [t for t in expected if t not in have]
    if missing:
        lines.append("- No validated close today for: " + ", ".join(missing)
                     + " — say so; never estimate.")
    return "\n".join(lines)
