"""Which session a "closed at" price belongs to (Nov 24 2026).

Both flagship hooks speak the last close before the New York open, and each
had grown its own clock rule for naming the day: SpaceX said "closed Friday
at" on a weekend and before Monday's open; Tesla only on a weekend, so
Monday's episode (Ep667, Ep674) spoke Friday's close as "closed at" for the
third morning running. Neither knew an exchange holiday, so the morning after
Thanksgiving would have repeated Wednesday's close as if it were fresh.

One rule, owned here: a close is spoken without a day only when it is the
session a listener would assume, yesterday's, on a morning the market trades.
Any other close names its weekday.

NYSE full-day holidays are computed by rule, so no table goes stale. Early
closes (1 pm) are still sessions and need nothing here.
"""

from __future__ import annotations

import datetime as _dt

_OPEN = _dt.time(9, 30)


def _easter(year: int) -> _dt.date:
    """Gregorian Easter Sunday (anonymous algorithm)."""
    a, b, c = year % 19, year // 100, year % 100
    d, e = b // 4, b % 4
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i, k = c // 4, c % 4
    l = (32 + 2 * e + 2 * i - h - k) % 7  # noqa: E741
    m = (a + 11 * h + 22 * l) // 451
    month = (h + l - 7 * m + 114) // 31
    day = (h + l - 7 * m + 114) % 31 + 1
    return _dt.date(year, month, day)


def _nth_weekday(year: int, month: int, weekday: int, n: int) -> _dt.date:
    first = _dt.date(year, month, 1)
    return first + _dt.timedelta(days=(weekday - first.weekday()) % 7 + 7 * (n - 1))


def _last_weekday(year: int, month: int, weekday: int) -> _dt.date:
    nxt = _dt.date(year + (month == 12), month % 12 + 1, 1)
    last = nxt - _dt.timedelta(days=1)
    return last - _dt.timedelta(days=(last.weekday() - weekday) % 7)


def _observed(day: _dt.date) -> _dt.date | None:
    """A fixed-date holiday's market closure: Friday when it falls on a
    Saturday, Monday when on a Sunday."""
    if day.weekday() == 5:
        return day - _dt.timedelta(days=1)
    if day.weekday() == 6:
        return day + _dt.timedelta(days=1)
    return day


def holidays(year: int) -> frozenset:
    """NYSE full-day closures in *year*."""
    days = {
        _nth_weekday(year, 1, 0, 3),            # Martin Luther King Jr. Day
        _nth_weekday(year, 2, 0, 3),            # Presidents' Day
        _easter(year) - _dt.timedelta(days=2),  # Good Friday
        _last_weekday(year, 5, 0),              # Memorial Day
        _observed(_dt.date(year, 6, 19)),       # Juneteenth
        _observed(_dt.date(year, 7, 4)),        # Independence Day
        _nth_weekday(year, 9, 0, 1),            # Labor Day
        _nth_weekday(year, 11, 3, 4),           # Thanksgiving
        _observed(_dt.date(year, 12, 25)),      # Christmas
    }
    # New Year's Day is not observed on the Friday before when it falls on a
    # Saturday (the exchange's own rule), only on the Monday after a Sunday.
    new_year = _dt.date(year, 1, 1)
    if new_year.weekday() == 6:
        days.add(new_year + _dt.timedelta(days=1))
    elif new_year.weekday() < 5:
        days.add(new_year)
    return frozenset(d for d in days if d is not None)


def is_trading_day(day: _dt.date) -> bool:
    return day.weekday() < 5 and day not in holidays(day.year)


def previous_session(day: _dt.date) -> _dt.date:
    """The last trading day strictly before *day*."""
    d = day - _dt.timedelta(days=1)
    while not is_trading_day(d):
        d -= _dt.timedelta(days=1)
    return d


def _new_york(now: _dt.datetime | None) -> _dt.datetime:
    now = now or _dt.datetime.now(_dt.timezone.utc)
    if now.tzinfo is None:
        now = now.replace(tzinfo=_dt.timezone.utc)
    try:
        from zoneinfo import ZoneInfo
        return now.astimezone(ZoneInfo("America/New_York"))
    except Exception:  # pragma: no cover - zoneinfo missing on exotic hosts
        return now - _dt.timedelta(hours=5)


def close_session_date(now: _dt.datetime | None = None) -> _dt.date:
    """The session whose close is the last one at *now*, read before the
    open: the previous trading day. From the open on a trading day the hooks
    keep their old reading (the bar may be today's), so this answers only
    the before-the-open question."""
    return previous_session(_new_york(now).date())


def close_day_word(now: _dt.datetime | None = None) -> str:
    """``""`` or ``" Friday"`` — the word that follows "closed".

    Empty when the close is yesterday's and today trades (the ordinary
    weekday morning), and from the open on a trading day (the hooks' old
    behaviour, unchanged). Otherwise the weekday of the session the close
    belongs to, with a leading space.
    """
    local = _new_york(now)
    today = local.date()
    trades_today = is_trading_day(today)
    if trades_today and local.time() >= _OPEN:
        return ""
    session = previous_session(today)
    if trades_today and session == today - _dt.timedelta(days=1):
        return ""
    return " " + session.strftime("%A")
