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


# --- Analytics on by default outside the opt-in regions (operator decision,
# Nov 24 2026). Ad measurement stays opt-in everywhere.

import shutil  # noqa: E402

import pytest  # noqa: E402

_OPT_IN = {"GB", "CH", "CA-QC", "FR", "DE", "IE", "NO", "IS", "LI"}


@pytest.mark.skipif(shutil.which("node") is None, reason="node not installed")
def test_analytics_waits_only_in_the_opt_in_regions():
    from tests.test_consent_mode_v2_advanced_2026_10_16 import _run

    defaults = _run()["defaults"]
    regional = [d for d in defaults if d.get("region")]
    global_ = [d for d in defaults if not d.get("region")]
    assert len(regional) == 1 and len(global_) == 1
    assert _OPT_IN <= set(regional[0]["region"])
    assert "US" not in regional[0]["region"] and "CA" not in regional[0]["region"]
    assert regional[0]["analytics_storage"] == "denied"
    assert global_[0]["analytics_storage"] == "granted"
    for d in defaults:
        assert d["ad_storage"] == d["ad_user_data"] == d["ad_personalization"] == "denied"


def test_the_banner_and_the_policy_say_where_analytics_waits():
    js = (ROOT / "assets" / "js" / "consent.js").read_text(encoding="utf-8")
    policy = (ROOT / "templates" / "privacy_policy.html.j2").read_text(encoding="utf-8")
    assert "Everywhere else, Analytics is on until you turn" in js
    assert "denied by default in the EU, the UK, Switzerland and Quebec" in policy
    assert "Advertising storage is <strong>denied by default everywhere" in policy
