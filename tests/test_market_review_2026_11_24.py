"""Nov 24 2026 market review: the on-air rotation asks for the email.

docs/reviews/market_review_2026_11_24.md. 16,113 downloads in 30 days made
5 email subscribers; no surface in the outro rotation ever asked for the email.
"""
from __future__ import annotations

import datetime as dt
import math
from collections import Counter
from pathlib import Path

from engine.brand import FLAGSHIP_SHOW_SLUGS
from engine.network_promo import (
    ENGLISH_SHOWS, NETWORK_SURFACES, _weighted_surface_pool, pick_featured_surface,
)

ROOT = Path(__file__).resolve().parents[1]


def _email():
    return next(s for s in NETWORK_SURFACES if s["id"] == "email")


def test_the_rotation_asks_for_the_email():
    surface = _email()
    assert "nerranetwork.com/nerra-daily" in surface["spoken"]
    assert (ROOT / surface["url"]).exists()
    assert "data-nn-subscribe" in (ROOT / surface["url"]).read_text(encoding="utf-8")


def test_the_flagships_ask_twice_and_every_other_show_once():
    for slug in ENGLISH_SHOWS:
        want = 2 if slug in FLAGSHIP_SHOW_SLUGS else 1
        assert Counter(s["id"] for s in _weighted_surface_pool(slug))["email"] == want


def test_every_pool_stays_coprime_with_the_stride():
    for slug in list(ENGLISH_SHOWS) + [""]:
        assert math.gcd(len(_weighted_surface_pool(slug)), 3) == 1


def test_the_email_ask_never_airs_two_days_running():
    day = dt.date(2026, 11, 25)
    for slug in ENGLISH_SHOWS:
        n = len(_weighted_surface_pool(slug))
        ids = [pick_featured_surface(slug, day + dt.timedelta(d))["id"] for d in range(n * 2)]
        assert not [a for a, b in zip(ids, ids[1:]) if a == b == "email"]
        assert "email" in ids


def test_the_spoken_line_makes_no_promise_the_brand_rules_ban():
    spoken = _email()["spoken"].lower()
    for banned in ("ad-free", "ad free", "no ads", "no spam"):
        assert banned not in spoken
