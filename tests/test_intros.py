"""Tests for the dynamic daily intro system (engine.intros)."""

import datetime

import pytest

from engine.intros import (
    build_closing_block,
    build_intro_line,
    get_show_host,
    _pick,
    _milestone_note,
)


# ---------------------------------------------------------------------------
# Deterministic selection
# ---------------------------------------------------------------------------

class TestPick:
    def test_same_day_same_result(self):
        pool = ["a", "b", "c", "d"]
        d = datetime.date(2026, 3, 15)
        r1 = _pick(pool, "tesla", d, salt="greeting")
        r2 = _pick(pool, "tesla", d, salt="greeting")
        assert r1 == r2

    def test_different_days_can_differ(self):
        pool = list("abcdefghijklmnop")  # large pool to reduce collision chance
        results = set()
        for day in range(1, 30):
            d = datetime.date(2026, 3, day)
            results.add(_pick(pool, "tesla", d, salt="greeting"))
        # With 29 days and 16 options, we should see at least 3 different values
        assert len(results) >= 3

    def test_different_shows_can_differ(self):
        pool = list("abcdefghijklmnop")
        d = datetime.date(2026, 3, 15)
        results = set()
        for show in ["tesla", "omni_view", "env_intel", "models_agents", "planetterrian"]:
            results.add(_pick(pool, show, d, salt="greeting"))
        assert len(results) >= 2

    def test_empty_pool(self):
        assert _pick([], "tesla", datetime.date(2026, 1, 1)) == ""

    def test_single_item(self):
        assert _pick(["only"], "tesla", datetime.date(2026, 1, 1)) == "only"


# ---------------------------------------------------------------------------
# Milestone detection
# ---------------------------------------------------------------------------

class TestMilestones:
    def test_episode_100(self):
        note = _milestone_note(100)
        assert note is not None
        assert "one hundred" in note or "100" in note

    def test_episode_200(self):
        assert _milestone_note(200) is not None

    def test_episode_500(self):
        assert _milestone_note(500) is not None

    def test_episode_300(self):
        # Generic round number
        note = _milestone_note(300)
        assert note is not None

    def test_no_milestone(self):
        assert _milestone_note(42) is None
        assert _milestone_note(1) is None
        assert _milestone_note(99) is None


# ---------------------------------------------------------------------------
# build_intro_line
# ---------------------------------------------------------------------------

class TestBuildIntroLine:
    def test_tesla_contains_show_name(self):
        intro = build_intro_line(
            "tesla",
            episode_num=403,
            today_str="March 15, 2026",
            date=datetime.date(2026, 3, 15),
        )
        assert "Tesla Shorts Time Daily" in intro
        assert "Patrick:" in intro

    def test_env_intel_contains_show_name(self):
        intro = build_intro_line(
            "env_intel",
            episode_num=10,
            today_str="March 15, 2026",
            date=datetime.date(2026, 3, 15),
        )
        assert "Environmental Intelligence" in intro
        assert "Host:" in intro

    def test_models_agents_contains_show_name(self):
        intro = build_intro_line(
            "models_agents",
            episode_num=50,
            today_str="March 15, 2026",
            date=datetime.date(2026, 3, 15),
        )
        assert "Models and Agents" in intro

    def test_finansy_prosto_russian(self):
        intro = build_intro_line(
            "finansy_prosto",
            episode_num=5,
            today_str="15 марта 2026",
            date=datetime.date(2026, 3, 15),
        )
        assert "Финансы Просто" in intro
        assert "Ведущая:" in intro

    def test_unknown_show_returns_generic(self):
        intro = build_intro_line(
            "nonexistent_show",
            episode_num=1,
            today_str="March 15, 2026",
            date=datetime.date(2026, 3, 15),
        )
        assert "episode 1" in intro

    def test_monday_uses_day_specific_greetings(self):
        """Monday (weekday=0) should use day_colors greetings if available."""
        monday = datetime.date(2026, 3, 16)  # March 16, 2026 is a Monday
        intro = build_intro_line(
            "tesla",
            episode_num=10,
            today_str="March 16, 2026",
            date=monday,
        )
        # Should still contain show name regardless of day
        assert "Tesla Shorts Time Daily" in intro

    def test_intro_varies_across_days(self):
        """Different days should produce different intros (not identical)."""
        intros = set()
        for day in range(1, 28):
            d = datetime.date(2026, 3, day)
            # Skip weekends for consistency
            if d.weekday() in (5, 6):
                continue
            intro = build_intro_line(
                "tesla",
                episode_num=400 + day,
                today_str=f"March {day}, 2026",
                date=d,
            )
            intros.add(intro)
        # With ~20 weekdays and multiple greeting/framing pools,
        # we should see variation
        assert len(intros) >= 5

    def test_milestone_in_intro(self):
        intro = build_intro_line(
            "tesla",
            episode_num=100,
            today_str="March 15, 2026",
            date=datetime.date(2026, 3, 15),
        )
        assert "one hundred" in intro or "milestone" in intro


# ---------------------------------------------------------------------------
# build_closing_block
# ---------------------------------------------------------------------------

class TestBuildClosingBlock:
    def test_tesla_closing(self):
        closing = build_closing_block(
            "tesla",
            episode_num=100,
            today_str="March 15, 2026",
            date=datetime.date(2026, 3, 15),
        )
        assert "Patrick:" in closing
        assert "Tesla" in closing or "tomorrow" in closing or "listening" in closing

    def test_env_intel_closing(self):
        closing = build_closing_block(
            "env_intel",
            episode_num=10,
            today_str="March 15, 2026",
            date=datetime.date(2026, 3, 15),
        )
        assert "Host:" in closing

    def test_unknown_show_generic(self):
        closing = build_closing_block(
            "nonexistent",
            episode_num=1,
            today_str="March 15, 2026",
        )
        assert "tomorrow" in closing


# ---------------------------------------------------------------------------
# get_show_host
# ---------------------------------------------------------------------------

class TestGetShowHost:
    def test_tesla(self):
        assert get_show_host("tesla") == "Patrick"

    def test_env_intel(self):
        assert get_show_host("env_intel") == "Host"

    def test_finansy_prosto(self):
        assert get_show_host("finansy_prosto") == "Ведущая"

    def test_unknown(self):
        assert get_show_host("nonexistent") == "Patrick"


# ---------------------------------------------------------------------------
# All registered shows produce valid intros
# ---------------------------------------------------------------------------

_ALL_SHOWS = [
    "tesla", "omni_view", "fascinating_frontiers", "planetterrian",
    "env_intel", "models_agents", "models_agents_beginners",
    "finansy_prosto", "privet_russian", "modern_investing",
    "unintended_consequences",
]

@pytest.mark.parametrize("show_slug", _ALL_SHOWS)
def test_all_shows_produce_intros(show_slug):
    intro = build_intro_line(
        show_slug,
        episode_num=42,
        today_str="March 15, 2026",
        date=datetime.date(2026, 3, 15),
    )
    assert len(intro) > 20
    assert ":" in intro  # should have host prefix


@pytest.mark.parametrize("show_slug", _ALL_SHOWS)
def test_all_shows_produce_closings(show_slug):
    closing = build_closing_block(
        show_slug,
        episode_num=42,
        today_str="March 15, 2026",
        date=datetime.date(2026, 3, 15),
    )
    assert len(closing) > 20
    assert ":" in closing


# ---------------------------------------------------------------------------
# YouTube channel CTA in closing block
# ---------------------------------------------------------------------------

def test_closing_block_appends_youtube_cta_when_handle_set():
    closing = build_closing_block(
        "tesla",
        episode_num=42,
        today_str="April 30, 2026",
        youtube_channel_handle="@NerraNetwork",
    )
    assert "@NerraNetwork" in closing
    assert "YouTube" in closing
    assert "show notes" in closing


def test_closing_block_omits_youtube_cta_without_handle():
    closing = build_closing_block(
        "tesla",
        episode_num=42,
        today_str="April 30, 2026",
    )
    assert "@NerraNetwork" not in closing
    assert "YouTube" not in closing


def test_closing_block_youtube_cta_idempotent():
    """If the closing already mentions YouTube (e.g. handcrafted in
    show personality), the helper should not duplicate the line."""
    from engine.intros import _maybe_append_youtube_cta
    closing = "Patrick: That's it. Watch us on YouTube tomorrow."
    out = _maybe_append_youtube_cta(closing, "@NerraNetwork")
    # No duplicate "YouTube" sentence appended.
    assert out == closing


def test_closing_block_supports_russian_handle():
    closing = build_closing_block(
        "finansy_prosto",
        episode_num=1,
        today_str="30 апреля 2026",
        youtube_channel_handle="@NerraRU",
    )
    assert "@NerraRU" in closing
