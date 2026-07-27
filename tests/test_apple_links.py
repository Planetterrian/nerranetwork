"""Drift guards for Apple Podcasts links on show pages.

Background (July 2026): the site registry (``NETWORK_SHOWS`` in
generate_html.py, plus the ``shows/network_meta.yaml`` overlay) carried
hand-typed ``apple_podcasts_url`` strings. Six shows that are live on
Apple had ``apple_podcasts_url: None`` there and therefore rendered no
Apple link at all — env_intel, unintended_consequences, first_principles,
dp_pod, spacex and age_of_ai.

Meanwhile every one of those shows already had an authoritative
``apple_show_id`` in ``shows/<slug>.yaml``, captured from Podcasts
Connect. So the link was derivable and simply wasn't being derived.

This pins that behaviour, and pins the two things that are easy to
break later: registry URLs must keep winning over derived ones (so
unchanged pages stay byte-identical), and the badge must stay gated on
the asset actually existing, because Apple's lockup is Apple's artwork
and can't be checked in as a hand-drawn substitute.
"""

from __future__ import annotations

from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent

import generate_html as gh  # noqa: E402

# Live on Apple, but the registry had no URL for them.
PREVIOUSLY_LINKLESS = [
    "env_intel", "unintended_consequences", "first_principles",
    "dp_pod", "spacex", "age_of_ai",
]


class TestIdResolution:
    def test_reads_the_id_from_show_yaml(self):
        assert gh._read_show_apple("tesla")["apple_show_id"] == "1855142939"

    def test_unknown_slug_is_empty_not_an_error(self):
        assert gh._read_show_apple("no_such_show_xyz") == {
            "apple_show_id": "",
            "apple_podcasts_url_derived": "",
            "apple_video_url": "",
        }

    def test_video_edition_is_a_separate_apple_show(self):
        """The five video editions are distinct Apple shows with their own
        IDs — linking the audio ID would send video listeners to the
        wrong place."""
        apple = gh._read_show_apple("tesla")
        assert apple["apple_video_url"].endswith("id6795235986")
        assert apple["apple_show_id"] == "1855142939"

    def test_audio_only_show_has_no_video_url(self):
        assert gh._read_show_apple("omni_view")["apple_video_url"] == ""


class TestLinkPrecedence:
    def test_registry_url_wins_when_set(self):
        """Existing pages must not churn: where the registry has the nicer
        slugged URL, that is what renders."""
        registry = "https://podcasts.apple.com/us/podcast/tesla-shorts-time/id1855142939"
        assert gh._apple_links_for("tesla", registry)["apple_podcasts_url"] == registry

    def test_derived_url_fills_a_none(self):
        got = gh._apple_links_for("spacex", None)["apple_podcasts_url"]
        assert got == "https://podcasts.apple.com/us/podcast/id1896920957"

    def test_derived_url_fills_an_empty_string(self):
        assert gh._apple_links_for("dp_pod", "")["apple_podcasts_url"]

    @pytest.mark.parametrize("slug", PREVIOUSLY_LINKLESS)
    def test_every_previously_linkless_show_now_resolves(self, slug):
        cfg = gh.NETWORK_SHOWS.get(slug, {})
        got = gh._apple_links_for(slug, cfg.get("apple_podcasts_url"))
        assert got["apple_podcasts_url"], f"{slug} still has no Apple link"
        assert got["apple_show_id"], f"{slug} lost its Apple show ID"


class TestNoShowIsSilentlyDropped:
    def test_shows_with_an_id_all_get_a_link(self):
        """The failure mode this whole change exists to prevent: a show
        that is live on Apple rendering no Apple link because a registry
        field was never filled in."""
        for slug, cfg in gh.NETWORK_SHOWS.items():
            if not gh._read_show_apple(slug)["apple_show_id"]:
                continue
            resolved = gh._apple_links_for(slug, cfg.get("apple_podcasts_url"))
            assert resolved["apple_podcasts_url"], (
                f"{slug} has an apple_show_id but resolves to no URL")

    def test_all_shows_list_carries_the_derived_links(self):
        by_slug = {s["slug"]: s for s in gh._build_all_shows_list()}
        for slug in PREVIOUSLY_LINKLESS:
            if slug in by_slug:
                assert by_slug[slug]["apple_podcasts_url"], (
                    f"{slug} missing from the network show list's Apple links")


class TestBadgeGating:
    def test_badge_only_renders_once_the_asset_exists(self):
        """Apple's identity guidelines require the official lockup used
        unmodified. Until someone downloads it from the marketing
        toolbox into assets/badges/, the template must fall back to the
        plain text chip rather than render a broken <img>."""
        asset = gh._apple_badge_asset()
        if asset:
            assert (ROOT / asset).exists()
        else:
            assert not (ROOT / gh._APPLE_BADGE_REL).exists()

    def test_template_gates_the_badge_on_the_asset(self):
        tpl = (ROOT / "templates" / "show_page.html.j2").read_text(encoding="utf-8")
        # Whitespace-control markers ({%- ... %}) matter here: without
        # them the added blocks emit blank lines into all 30 pages and
        # every unchanged show churns in the commit.
        assert "{%- if apple_badge_asset %}" in tpl
        assert "{%- if apple_video_url %}" in tpl
        assert "nn-apple-badge" in tpl

    def test_badge_css_applies_no_filters(self):
        """Recolouring or filtering Apple's badge breaches the identity
        guidelines — keep the rule to positioning only."""
        css = (ROOT / "styles" / "main.css").read_text(encoding="utf-8")
        start = css.index(".nn-apple-badge")
        block = css[start:start + 400]
        for banned in ("filter:", "background:", "border-radius:"):
            assert banned not in block, f"badge CSS must not set {banned}"
