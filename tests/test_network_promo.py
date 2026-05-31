"""Drift guards for the spoken Nerra Network cross-promo (engine.network_promo).

Every English show's spoken closing gets a short network plug + ONE rotating
sibling show, chosen deterministically from the date so it varies daily, differs
across shows on the same day, and eventually advertises every English sibling.
Russian shows are excluded entirely.
"""

from __future__ import annotations

import datetime as dt

from engine.network_promo import (
    ENGLISH_ORDER,
    RUSSIAN_SHOWS,
    build_network_promo,
    pick_featured_show,
)

_DAY = dt.date(2026, 6, 1)


def test_never_features_itself():
    for slug in ENGLISH_ORDER:
        assert pick_featured_show(slug, _DAY) != slug


def test_featured_is_always_an_english_show():
    for slug in ENGLISH_ORDER:
        assert pick_featured_show(slug, _DAY) in ENGLISH_ORDER


def test_russian_shows_get_no_promo():
    for slug in RUSSIAN_SHOWS:
        assert pick_featured_show(slug, _DAY) is None
        assert build_network_promo(slug, _DAY) == ""


def test_unknown_show_gets_no_promo():
    assert build_network_promo("does_not_exist", _DAY) == ""
    assert pick_featured_show("does_not_exist", _DAY) is None


def test_promo_varies_by_day():
    """The featured sibling for a given show changes across consecutive days
    (so listeners don't hear the same plug every episode)."""
    feats = [pick_featured_show("tesla", _DAY + dt.timedelta(days=i)) for i in range(4)]
    assert len(set(feats)) > 1


def test_full_coverage_over_rotation():
    """Over enough days, every show features every English sibling — no
    sibling is permanently left unadvertised."""
    for slug in ENGLISH_ORDER:
        seen = {
            pick_featured_show(slug, _DAY + dt.timedelta(days=i))
            for i in range(40)
        }
        assert seen == set(ENGLISH_ORDER) - {slug}


def test_promo_text_mentions_network_and_featured_show():
    promo = build_network_promo("tesla", _DAY)
    assert "Nerra Network" in promo
    assert "nerranetwork.com" in promo
    featured = pick_featured_show("tesla", _DAY)
    from engine.network_promo import ENGLISH_SHOWS
    assert ENGLISH_SHOWS[featured]["spoken_name"] in promo


def test_promo_text_has_no_ampersand():
    """TTS must never read a stray '&' — Models & Agents → 'Models and Agents'."""
    for slug in ENGLISH_ORDER:
        for i in range(len(ENGLISH_ORDER) + 1):
            promo = build_network_promo(slug, _DAY + dt.timedelta(days=i))
            assert "&" not in promo
