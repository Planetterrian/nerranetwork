"""The daily audit reviews the network's Eastern day, never the runner's UTC one.

Nov 10 2026: GitHub delivered the 16:15 UTC audit cron at 00:13 UTC the next
day. The default review date was ``datetime.date.today()`` on the runner, so
the run audited Nov 10, whose shows had not run yet, and paged "Missed
episode" for nine of them. That is the only red Daily Audit in the week; the
editorial findings were already non-paging (tests/test_daily_audit_notify_policy.py).
"""

from __future__ import annotations

import datetime as dt

from review_episodes import network_today


UTC = dt.timezone.utc


def test_after_midnight_utc_is_still_the_eastern_evening():
    now = dt.datetime(2026, 11, 10, 0, 13, tzinfo=UTC)  # 19:13 ET, Nov 9
    assert network_today(now) == dt.date(2026, 11, 9)


def test_the_scheduled_slot_reviews_the_same_day():
    now = dt.datetime(2026, 11, 10, 16, 15, tzinfo=UTC)  # 11:15 ET
    assert network_today(now) == dt.date(2026, 11, 10)


def test_summer_time_too():
    now = dt.datetime(2026, 7, 2, 3, 30, tzinfo=UTC)  # 23:30 EDT, Jul 1
    assert network_today(now) == dt.date(2026, 7, 1)
