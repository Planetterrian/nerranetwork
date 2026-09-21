"""The YouTube description's surface line is tagged, and dated by the episode.

Two defects, both invisible by construction, both closed here.

**Untagged.** ``engine/video_metadata.py`` hand-built
``https://nerranetwork.com/{url}`` for the rotating discovery line. It slipped
past the network's ban on hand-rolled funnel links because a BARE url carries
no ``utm_campaign`` at all — there was nothing for a linter to object to — so
roughly 125k views a month of description clicks were unattributable, and
``api/funnel.json`` could not say whether plugging the gallery did anything.
Same class as the signup forms the Sep 21 capture pass fixed: the guard there
asserted the Worker ACCEPTED every source tag and never that a page EMITTED
one, so guard both ends.

**Wrongly dated.** It picked the surface from ``date.today()`` — the RENDER
date — while the spoken outro picks from the GENERATION date. A render that
slipped past midnight advertised a surface the episode never speaks.
"""

from __future__ import annotations

import datetime
from urllib.parse import parse_qs, urlparse

import pytest

from engine import funnel as F
from engine.config import load_config
from engine.network_promo import ENGLISH_ORDER, pick_featured_surface
from engine.video_metadata import _episode_date, build_long_form_metadata


def _description(slug: str, today_str: str, episode_num: int = 600,
                 channel: str = "en") -> str:
    config = load_config(f"shows/{slug}.yaml")
    return build_long_form_metadata(
        config,
        episode_num=episode_num,
        today_str=today_str,
        hook="A hook for the guard.",
        digest_text="### Top News\n\nSome body text.\n",
        audio_url="https://audio.nerranetwork.com/x.mp3",
        channel=channel,
    )["description"]


def _surface_url(description: str) -> str:
    for line in description.split("\n"):
        if line.startswith("✨") and "— " in line:
            return line.split("— ", 1)[1].strip()
    return ""


class TestSurfaceLineIsAttributable:
    def test_the_line_carries_a_parseable_campaign(self):
        url = _surface_url(_description("tesla", "September 20, 2026"))
        assert url, "no discovery line in the description"
        query = parse_qs(urlparse(url).query)
        campaign = query.get("utm_campaign", [""])[0]
        assert campaign, "the surface line is untagged"
        parsed = F.parse_campaign_id(campaign)
        assert parsed is not None, f"{campaign!r} does not parse"
        assert parsed.show == "tesla"
        assert parsed.episode == 600

    def test_the_surface_rides_in_the_variant_slot(self):
        """Which plug earned the click is the whole question."""
        date = datetime.date(2026, 9, 20)
        surface = pick_featured_surface("tesla", date)
        url = _surface_url(_description("tesla", "September 20, 2026"))
        campaign = parse_qs(urlparse(url).query)["utm_campaign"][0]
        assert F.parse_campaign_id(campaign).variant == surface["id"]

    def test_the_source_follows_the_channel(self):
        """A dub channel's clicks must not be counted as the EN channel's."""
        for channel in ("en", "ru", "fr"):
            url = _surface_url(
                _description("tesla", "September 20, 2026", channel=channel))
            if not url:
                continue
            source = parse_qs(urlparse(url).query).get("utm_source", [""])[0]
            assert source == F.channel_source(channel), (
                f"channel {channel} emitted utm_source={source!r}")

    def test_every_promotional_network_link_is_tagged(self):
        """The shape that made this invisible: a naked nerranetwork.com link.

        Asserted as a property over the whole rendered description rather
        than by pinning a function name, so a rename cannot make it pass.

        ONE untagged network link is legitimate and is named here: the AI
        disclosure footer in ``shows/_defaults.yaml``. That is a canonical
        reference a viewer follows to check us, not a plug whose clicks we
        are trying to count, and it reads better clean. (It points at
        ``/about`` without the extension — verified 200, the host serves
        clean URLs — so it is not the dead-URL class either.)
        """
        disclosure_paths = {"about", "ai-disclosure.html", "about.html"}
        for slug in ("tesla", "spacex", "models_agents"):
            description = _description(slug, "September 20, 2026")
            for token in description.split():
                token = token.rstrip(".,)")
                if not token.startswith("https://nerranetwork.com/"):
                    continue
                path = urlparse(token).path.strip("/")
                if not path or path in disclosure_paths:
                    continue
                assert "utm_campaign=" in token, (
                    f"{slug}: untagged network link in description: {token}")

    def test_the_disclosure_link_points_at_a_real_page(self):
        """The exemption above is only safe while the page exists.

        Checked against the repo, not the network: a guard that makes an
        HTTP call fails on a runner with no egress.
        """
        from pathlib import Path

        root = Path(__file__).resolve().parent.parent
        description = _description("tesla", "September 20, 2026")
        for token in description.split():
            token = token.rstrip(".,)")
            if not token.startswith("https://nerranetwork.com/"):
                continue
            path = urlparse(token).path.strip("/")
            if not path or "utm_campaign=" in token:
                continue
            assert (root / path).exists() or (root / f"{path}.html").exists(), (
                f"the disclosure footer links a page with no file: /{path}")


class TestSurfaceLineFollowsTheEpisodeDate:
    def test_the_date_comes_from_the_episode_not_the_clock(self):
        """Two different episode dates must be able to pick different plugs.

        The rotation is deterministic in the date, so if the builder were
        still reading ``date.today()`` every date would give the same line.
        """
        seen = {
            _surface_url(_description("tesla", f"September {day}, 2026"))
            for day in range(10, 24)
        }
        assert len(seen) > 1, (
            "the surface line does not vary with the episode date — it is "
            "still keyed off the render clock")

    def test_the_description_names_what_the_episode_would_speak(self):
        """The description and the spoken outro agree on the surface.

        Both key off the episode's own date, so a render finishing after
        midnight can no longer advertise a surface the audio never names.
        """
        for slug in ("tesla", "spacex"):
            if slug not in ENGLISH_ORDER:
                continue
            for day in (11, 17, 20):
                date = datetime.date(2026, 9, day)
                spoken = pick_featured_surface(slug, date)
                url = _surface_url(
                    _description(slug, date.strftime("%B %d, %Y")))
                if not (spoken and url):
                    continue
                variant = F.parse_campaign_id(
                    parse_qs(urlparse(url).query)["utm_campaign"][0]).variant
                assert variant == spoken["id"], (
                    f"{slug} {date}: description plugs {variant!r} but the "
                    f"episode speaks {spoken['id']!r}")

    @pytest.mark.parametrize("value,expected", [
        ("September 19, 2026", datetime.date(2026, 9, 19)),
        ("2026-09-19", datetime.date(2026, 9, 19)),
        ("Sep 19, 2026", datetime.date(2026, 9, 19)),
    ])
    def test_known_date_formats_parse(self, value, expected):
        assert _episode_date(value) == expected

    def test_an_unparseable_date_falls_back_to_today(self):
        """Never worse than the behaviour it replaced."""
        for junk in ("", "   ", "not a date", None):
            assert _episode_date(junk) == datetime.date.today()
