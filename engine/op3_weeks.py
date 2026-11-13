"""What an OP3 "week" is — the one reading every surface uses (Nov 12 2026).

OP3's ``show-download-counts`` returns ``weeklyDownloads``: four numbers,
oldest first, beside an ``asof`` date. Until this module the network read
them as CALENDAR weeks whose newest entry was the week in progress: the
ledger keyed the newest entry to the Monday of the fetch, and the audience
headline, the media kit and Mission Control's growth panel all skipped it
as "partial, never compared".

That reading was wrong, and the nightly files prove it. Across 29
consecutive fetches (Oct 16 - Nov 12 2026) every one of the four numbers
moved every night, and each night's series reappeared seven nights later
shifted one place to the left::

    fetched Oct 22 (asof Oct 21)   [1942, 3013, 4651, 3881]
    fetched Oct 29 (asof Oct 28)   [3013, 4651, 3861, 2977]
    fetched Nov  5 (asof Nov  4)   [4651, 3861, 2977, 3685]

A calendar week would stand still for seven nights while only the newest
entry grew. These are four back-to-back TRAILING seven-day windows ending
on ``asof``, every one of them complete (OP3's own field notes call them
"weeks with full data"). OP3's documentation does not define ``asof``; the
same files do: in all 145 show-fetches checked, the episode published ON
the ``asof`` day was already listed with downloads and no episode published
after it ever was, so the data runs through the end of that day. So:

* the newest entry is the latest seven complete days, and week over week is
  the newest entry against the one before it. Skipping it reported the week
  before last: on Nov 10 the headline read -16.9% while the latest seven
  days were up on the seven before;
* a window is a fixed week only on the night it ends on the ledger's
  week-ending day. The ledger (``api/op3_history.json``) therefore takes a
  fetch's windows only when ``asof`` is a Saturday: its weeks run Sunday to
  Saturday, keyed by the Monday inside them (the key the file has always
  used, and the span its frozen weeks already held, because their last
  write was the Sunday fetch). Any other night's windows overlap the
  ledger's weeks by one to six days, and writing them made the ledger's
  newest four weeks change value every night.

Nothing here estimates a part of a week: a number is a whole window OP3
reported, or it is absent.

The check, with every night's numbers:
``docs/reviews/op3_week_definition_2026_11_12.md``.
"""
from __future__ import annotations

import datetime as _dt
from typing import Any, Dict, List, Optional, Sequence, Tuple

#: Days in one OP3 window.
WINDOW_DAYS = 7
#: ``date.weekday()`` of the day a ledger week ends on: Saturday.
LEDGER_WEEK_END_WEEKDAY = 5
#: Reader copy for the ledger's week, for the pages that chart it.
LEDGER_WEEK_LABEL = "Sunday to Saturday"


def _day(value: Any) -> Optional[_dt.date]:
    if isinstance(value, _dt.datetime):
        return value.date()
    if isinstance(value, _dt.date):
        return value
    try:
        return _dt.date.fromisoformat(str(value)[:10])
    except (TypeError, ValueError):
        return None


def latest_and_prior(weekly: Optional[Sequence[Any]]) -> Tuple[Optional[int], Optional[int]]:
    """The latest seven complete days and the seven before them.

    ``(None, None)`` when the series cannot make the comparison: fewer than
    two windows is unmeasured, never 0.
    """
    series = list(weekly or [])
    if len(series) < 2:
        return None, None
    return int(series[-1] or 0), int(series[-2] or 0)


def window_bounds(asof: Any, back: int = 0) -> Optional[Tuple[_dt.date, _dt.date]]:
    """First and last day of the window ``back`` places before the newest
    (0 = the window ending on ``asof``). ``None`` without a readable date."""
    end = _day(asof)
    if end is None or back < 0:
        return None
    end = end - _dt.timedelta(days=WINDOW_DAYS * back)
    return end - _dt.timedelta(days=WINDOW_DAYS - 1), end


def is_ledger_aligned(asof: Any) -> bool:
    """True on the one night a week whose windows are the ledger's weeks."""
    day = _day(asof)
    return day is not None and day.weekday() == LEDGER_WEEK_END_WEEKDAY


def ledger_weeks(asof: Any, weekly: Optional[Sequence[Any]]) -> Dict[str, int]:
    """``{monday_key: downloads}`` for a fetch whose windows are ledger weeks.

    Empty on every other night. The key is the Monday inside the Sunday to
    Saturday window, so the file's keys keep their meaning.
    """
    if not is_ledger_aligned(asof):
        return {}
    end = _day(asof)
    out: Dict[str, int] = {}
    for back, n in enumerate(reversed(list(weekly or []))):
        saturday = end - _dt.timedelta(days=WINDOW_DAYS * back)
        monday = saturday - _dt.timedelta(days=5)
        out[monday.isoformat()] = int(n or 0)
    return out


def ledger_week_bounds(key: Any) -> Optional[Tuple[_dt.date, _dt.date]]:
    """The Sunday and Saturday of the ledger week stored under ``key``."""
    monday = _day(key)
    if monday is None:
        return None
    return monday - _dt.timedelta(days=1), monday + _dt.timedelta(days=5)


def complete_ledger_weeks(hist: Optional[Dict[str, Any]]) -> List[Tuple[_dt.date, Dict[str, Any]]]:
    """The ledger's weeks, oldest first, as ``(monday, row)``.

    Every week the writer stores is complete. The one check kept is for a
    file written before Nov 12 2026, whose newest key was a window still
    ahead of its own week: a week is read only once its Saturday is behind
    the file's ``updated_at`` day.
    """
    hist = hist or {}
    updated = _day(hist.get("updated_at"))
    out: List[Tuple[_dt.date, Dict[str, Any]]] = []
    for key in sorted(hist.get("weeks") or {}):
        row = (hist.get("weeks") or {}).get(key)
        bounds = ledger_week_bounds(key)
        if bounds is None or not isinstance(row, dict):
            continue
        if updated is None or bounds[1] >= updated:
            continue
        out.append((bounds[0] + _dt.timedelta(days=1), row))
    return out
