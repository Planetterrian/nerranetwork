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

#: Nov 24 2026: NVDA closed 165.05 on Nov 23 after 125.53 on Nov 20 (+31.5%,
#: the session after a 14% fall) and the guard above omitted it from the tape
#: on the day it was the story. A move past ``MAX_DEVIATION`` is accepted when
#: the SAME fetch's previous bar agrees with the cached close: the source's
#: series is continuous with the record, so the move is the source's own and
#: not a stale or garbled quote. Still bounded.
CORROBORATION_TOLERANCE = 0.02
MAX_CORROBORATED_DEVIATION = 0.60

#: A cached close this many calendar days older than the fetched bar cannot
#: judge it (the ticker was missing for a while); the fetch's own previous
#: bar is the reference then, so a rejection can never lock a ticker out.
CACHE_STALE_DAYS = 7

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


def expected_last_session(now: Optional[_dt.datetime] = None) -> str:
    """ISO date of the most recent weekday session that has closed.

    Holidays are not modelled: on one, this names a session that never
    happened, and the only consequence is one extra fetch below.
    """
    now = now or _dt.datetime.now(_dt.timezone.utc)
    try:
        from zoneinfo import ZoneInfo
        ny = now.astimezone(ZoneInfo("America/New_York"))
    except Exception:  # pragma: no cover
        ny = now - _dt.timedelta(hours=4)
    day = ny.date()
    if ny.hour < SESSION_CLOSE_HOUR or day.weekday() >= 5:
        day -= _dt.timedelta(days=1)
    while day.weekday() >= 5:
        day -= _dt.timedelta(days=1)
    return day.isoformat()


def _rows(hist) -> List[Tuple[str, float]]:
    return [
        (idx.date().isoformat() if hasattr(idx, "date") else str(idx)[:10], float(c))
        for idx, c in zip(hist.index, hist["Close"].tolist()) if c == c
    ]


def _history_fetch(ticker: str) -> Optional[Tuple[float, Optional[float], str]]:
    import yfinance as yf

    t = yf.Ticker(ticker)
    got = completed_bars(_rows(t.history(period="10d")))
    want = expected_last_session()
    if got and got[2] < want:
        # MAG 7 Ep1 (run 20:44 New York, 2026-09-22) printed Sep 21 closes:
        # the period query had not yet carried that day's completed bar.
        # An explicit start/end range asks for it by date.
        try:
            end = (_dt.date.fromisoformat(want) + _dt.timedelta(days=1)).isoformat()
            start = (_dt.date.fromisoformat(want) - _dt.timedelta(days=14)).isoformat()
            retry = completed_bars(_rows(t.history(start=start, end=end)))
            if retry and retry[2] > got[2]:
                return retry
        except Exception as exc:  # noqa: BLE001 — keep the older close
            logger.info("dated history retry failed for %s: %s", ticker, exc)
        logger.warning("%s: newest close is %s, expected %s — the tape names its date",
                       ticker, got[2], want)
    return got


def load_cache(path: Path) -> Dict[str, dict]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        # ``last_verified`` holds the last validated close of a ticker that
        # is missing from ``quotes`` (see ``persist``): the guard's memory,
        # never a quote any page prints.
        out = {q["ticker"]: q for q in data.get("last_verified", []) if q.get("ticker")}
        out.update({q["ticker"]: q for q in data.get("quotes", []) if q.get("ticker")})
        return out
    except Exception:
        return {}


def valid_close(price: float, cached: Optional[float],
                prev: Optional[float] = None) -> bool:
    if not (PRICE_MIN <= price <= PRICE_MAX):
        return False
    if cached and abs(price - cached) / cached > MAX_DEVIATION:
        deviation = abs(price - cached) / cached
        corroborated = bool(
            prev and abs(prev - cached) / cached <= CORROBORATION_TOLERANCE)
        return corroborated and deviation <= MAX_CORROBORATED_DEVIATION
    return True


def _cache_is_stale(cached_bar: Optional[str], bar_date: str) -> bool:
    try:
        gap = _dt.date.fromisoformat(bar_date) - _dt.date.fromisoformat(str(cached_bar))
    except (TypeError, ValueError):
        return False
    return gap.days > CACHE_STALE_DAYS


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
        entry = cached.get(t) or {}
        prior = entry.get("close")
        if prior and _cache_is_stale(entry.get("bar_date"), bar_date):
            logger.warning("%s: cached close is from %s, too old to judge the %s "
                           "bar — validating against the fetch's previous bar",
                           t, entry.get("bar_date"), bar_date)
            prior = prev
        if not valid_close(close, prior, prev):
            # Annotated: an omitted ticker is a hole in the published tape.
            print(f"::warning::market quotes: {t} close {close:.2f} failed "
                  f"validation (cached {prior}, previous bar {prev}) — omitted "
                  f"from the tape", flush=True)
            logger.warning("%s close %.2f failed validation (cached %s) — omitted", t, close, prior)
            continue
        if prior and abs(close - prior) / prior > MAX_DEVIATION:
            logger.warning("%s close %.2f is %.0f%% from the cached %s — accepted: "
                           "the fetch's previous bar (%s) matches the cache",
                           t, close, abs(close - prior) / prior * 100, prior, prev)
        out.append(Quote(t, round(close, 2), round(prev, 2) if prev else None, bar_date))
    return out


def persist(quotes: List[Quote], cache_path: Path) -> None:
    if not quotes:
        return  # never overwrite a good cache with an empty one
    try:
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        # A ticker omitted today used to vanish from the cache, so the next
        # run validated it against nothing. Its last validated close is kept
        # under ``last_verified`` (the guard reads it; no page prints it).
        have = {q.ticker for q in quotes}
        carried = [
            {"ticker": t, "close": e.get("close"), "bar_date": e.get("bar_date")}
            for t, e in load_cache(cache_path).items()
            if t not in have and e.get("close")
        ]
        payload = {
            "updated_at": _dt.datetime.now(_dt.timezone.utc).isoformat(),
            "basis": "regular-session daily close",
            "quotes": [
                {"ticker": q.ticker, "close": q.close, "prev_close": q.prev_close,
                 "change_pct": q.change_pct, "bar_date": q.bar_date}
                for q in quotes
            ],
        }
        if carried:
            payload["last_verified"] = carried
        cache_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    except Exception as exc:  # noqa: BLE001
        logger.warning("could not persist %s (non-fatal): %s", cache_path, exc)


def _signed_pct(pct: float) -> str:
    """``+1%`` not ``+1.0%``: MAG 7 Ep1 spoke "up one point zero percent"."""
    text = f"{pct:+.1f}"
    if text.endswith(".0"):
        text = text[:-2]
    return text + "%"


def tape_block(quotes: List[Quote], names: Dict[str, str], expected: Iterable[str]) -> str:
    """The digest's MARKET TAPE block, or a one-line 'no quotes' notice.

    Every line is a CLOSE with its session date — the digest says "closed",
    never "trading at". A missing ticker is named as missing. On MAG 7 the
    tape feeds one reader-only line at the foot of the digest; the script
    never reads it (operator brief, 2026-09-23).
    """
    expected = list(expected)
    if not quotes:
        return (
            "### MARKET TAPE (instruction — do not include in output)\n"
            "No validated closing prices were available today. Leave The Tape "
            "section out entirely, and no price may appear anywhere in the "
            "digest."
        )
    have = {q.ticker for q in quotes}
    # One session date, said once: MAG 7 Ep1's tape carried the date on all
    # seven lines and the script spoke "on September twenty one" seven times.
    dates = {q.bar_date for q in quotes}
    one_date = next(iter(dates)) if len(dates) == 1 else ""
    lines = [
        "### MARKET TAPE — regular-session closes"
        + (f" for the {one_date} session" if one_date else "")
        + " (use these numbers verbatim; never substitute a price from an "
        "article; every price is a CLOSE"
        + ("; say the session date ONCE, never per company)" if one_date else ")"),
    ]
    for q in quotes:
        chg = ""
        if q.change_pct is not None:
            chg = " (unchanged)" if q.change_pct == 0 else f" ({_signed_pct(q.change_pct)})"
        lines.append(f"- {names.get(q.ticker, q.ticker)} ({q.ticker}): closed at "
                     f"${q.close:,.2f}{chg}" + ("" if one_date else f" on {q.bar_date}"))
    missing = [t for t in expected if t not in have]
    if missing:
        lines.append("- No validated close today for: " + ", ".join(missing)
                     + " — say so; never estimate.")
    return "\n".join(lines)
