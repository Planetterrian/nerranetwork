"""Nov 10 2026 growth review, item 6: Nerra Personal takes two slots of the
outro rotation on the flagships only."""
from __future__ import annotations

import datetime as dt
import math
from collections import Counter

from engine.brand import FLAGSHIP_SHOW_SLUGS
from engine.network_promo import (
    ENGLISH_SHOWS, _weighted_surface_pool, pick_featured_surface,
)


def test_flagships_get_personal_twice():
    for slug in FLAGSHIP_SHOW_SLUGS:
        assert Counter(s["id"] for s in _weighted_surface_pool(slug))["personal"] == 2


def test_every_other_show_keeps_the_default_pool():
    base = [s["id"] for s in _weighted_surface_pool()]
    assert Counter(base)["personal"] == 1
    for slug in ENGLISH_SHOWS:
        if slug not in FLAGSHIP_SHOW_SLUGS:
            assert [s["id"] for s in _weighted_surface_pool(slug)] == base


def test_flagship_pool_stays_coprime_with_the_stride():
    for slug in FLAGSHIP_SHOW_SLUGS:
        assert math.gcd(len(_weighted_surface_pool(slug)), 3) == 1


def test_flagship_personal_never_airs_two_days_running():
    day = dt.date(2026, 11, 11)
    for slug in FLAGSHIP_SHOW_SLUGS:
        n = len(_weighted_surface_pool(slug))
        ids = [pick_featured_surface(slug, day + dt.timedelta(d))["id"] for d in range(n * 2)]
        assert not [a for a, b in zip(ids, ids[1:]) if a == b]
        assert ids.count("personal") == 4
