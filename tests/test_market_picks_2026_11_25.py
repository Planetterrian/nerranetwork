"""Nov 25 2026: Patrick's picks from the market review (7a, 8a).

7a. The six biggest shows' directory copy (Apple / Spotify read the feed's
channel description) opens on the sourcing promise. The AI disclosure is
appended by run_show, so the copy itself never repeats it.

8a. "SpaceX, once a week" is a Nerra Daily TAG set, never a second email
(CLAUDE.md "One email: Nerra Daily"): the gallery Worker's ``spacex-weekly``
list sets the SpaceX Daily follow and the Sunday-only tag, and the Sunday
edition gives that reader the whole SpaceX week instead of three rows.
"""

from __future__ import annotations

import datetime as dt
import re
from pathlib import Path

import pytest
import yaml

from engine import nerra_daily_email as nde

from tests.test_nerra_daily_email_2026_11_03 import NOW, _front  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
BIG_SIX = ("spacex", "tesla", "models_agents", "fascinating_frontiers",
           "modern_investing", "models_agents_beginners")
#: 9c: the three smallest shows keep running; their directory copy leads
#: with the words a listener searches for (the towns, the subject).
SMALL_THREE = {"collingwood": "Collingwood", "longevity": "longevity",
               "env_intel": "environmental regulation"}


def _rss(slug):
    cfg = yaml.safe_load((ROOT / "shows" / f"{slug}.yaml").read_text(encoding="utf-8"))
    return cfg["publishing"]["rss_description"]


class TestDirectoryCopy:
    @pytest.mark.parametrize("slug", BIG_SIX)
    def test_the_promise_is_inside_the_preview(self, slug):
        # Apple and Spotify list pages show about 150 characters.
        head = _rss(slug)[:150].lower()
        assert "source" in head or "ledger" in head

    @pytest.mark.parametrize("slug,word", sorted(SMALL_THREE.items()))
    def test_small_shows_lead_with_what_a_listener_searches(self, slug, word):
        assert word.lower() in _rss(slug)[:80].lower()
        assert "source" in _rss(slug).lower()

    @pytest.mark.parametrize("slug", BIG_SIX + tuple(SMALL_THREE))
    def test_copy_never_repeats_the_disclosure_or_promises_a_length(self, slug):
        text = _rss(slug)
        assert "AI Disclosure" not in text
        assert not re.search(r"\b(minutes?|min)\b", text)
        assert "ad-free" not in text.lower()

    @pytest.mark.parametrize("slug", ("spacex", "tesla", "modern_investing"))
    def test_market_shows_say_not_financial_advice(self, slug):
        assert "Not financial advice" in _rss(slug)

    def test_the_claims_page_the_copy_names_exists(self):
        assert (ROOT / "claims.html").exists()
        assert any("nerranetwork.com/claims" in _rss(s) for s in BIG_SIX)


SUNDAY = dt.date(2026, 11, 8)
WEEK = [{"episode_num": 100 - n, "date": SUNDAY - dt.timedelta(days=n), "hook": f"spacex day {n}"}
        for n in range(1, 7)]


@pytest.fixture
def sunday_copy(monkeypatch):
    monkeypatch.setattr(nde, "already_sent", lambda day, root=None, **k: {})
    monkeypatch.setattr(nde, "video_links", lambda *a: {})
    monkeypatch.setattr(nde, "most_played", lambda root=None, limit=5: [])
    asked = {}

    def week(slug, day, root=None, limit=nde.WEEK_LIST_MAX):
        asked[slug] = limit
        return WEEK[:limit] if slug == "spacex" else []

    monkeypatch.setattr(nde, "week_records", week)
    front = _front(SUNDAY)
    if "spacex" not in front["shows"]:
        pytest.skip("fixture has no SpaceX row")
    composed = nde.compose(SUNDAY, now=NOW + dt.timedelta(days=6), front=front, trial_days=7)
    return composed, asked


def test_planetterrian_points_its_listeners_at_longevity():
    import generate_html
    assert generate_html.NETWORK_SHOWS["planetterrian"]["related_show"] == "longevity"
    assert 'href="longevity.html"' in (ROOT / "planetterrian.html").read_text(encoding="utf-8")


class TestSpaceXWeek:
    def test_the_sunday_only_reader_gets_the_whole_week(self, sunday_copy):
        composed, asked = sunday_copy
        assert asked["spacex"] == nde.WEEK_LIST_FULL_MAX
        copy = nde.render_for(composed.body, ["SpaceX Daily", nde.WEEKLY_ONLY_TAG])
        week = copy.split("Your week", 1)[1]
        assert all(f"spacex day {n}" in week for n in range(1, 7))

    def test_a_daily_reader_keeps_three_rows(self, sunday_copy):
        composed, _ = sunday_copy
        copy = nde.render_for(composed.body, ["SpaceX Daily", "nerra-member"])
        week = copy.split("Your week", 1)[1]
        assert "spacex day 3" in week and "spacex day 4" not in week

    def test_the_archive_copy_carries_neither_list(self, sunday_copy):
        composed, _ = sunday_copy
        copy = nde.render_for(composed.body, [], subscriber=False)
        assert "spacex day 1" not in copy.split("Your week", 1)[-1]


class TestSpaceXWeeklySignup:
    def test_the_worker_list_is_the_follow_plus_sundays_only(self):
        src = (ROOT / "workers" / "gallery" / "src" / "handlers.ts").read_text(encoding="utf-8")
        line = next(ln for ln in src.splitlines() if '"spacex-weekly":' in ln)
        for tag in ("nerra-member", "SpaceX Daily", nde.WEEKLY_ONLY_TAG):
            assert f'"{tag}"' in line
        email_ts = (ROOT / "workers" / "gallery" / "src" / "email.ts").read_text(encoding="utf-8")
        assert f'WEEKLY_ONLY_TAG = "{nde.WEEKLY_ONLY_TAG}"' in email_ts

    def test_the_spacex_page_offers_it_and_no_other_page_does(self):
        page = (ROOT / "spacex.html").read_text(encoding="utf-8")
        assert 'data-list="spacex-weekly"' in page
        assert page.count('id="spacex-weekly-form"') == 1
        for other in ("tesla.html", "nerra-daily.html"):
            assert 'data-list="spacex-weekly"' not in (ROOT / other).read_text(encoding="utf-8")
