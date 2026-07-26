"""Drift guards for July 2026 depth + network-discovery pass.

See ``docs/reviews/depth_and_network_discovery_2026_07_09.md``.
"""

from __future__ import annotations

import datetime as dt
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parent.parent
SHOWS = ROOT / "shows"

_DAY = dt.date(2026, 7, 9)


# ---------------------------------------------------------------------------
# Digest-depth pilots
# ---------------------------------------------------------------------------

_DEPTH_PILOTS = {
    "tesla": 1600,
    "fascinating_frontiers": 1400,
    "spacex": 1200,
    "models_agents": 1300,
}


class TestDigestExpandPilots:
    @pytest.mark.parametrize("slug,floor", list(_DEPTH_PILOTS.items()))
    def test_pilot_opts_into_digest_expand(self, slug, floor):
        data = yaml.safe_load(
            (SHOWS / f"{slug}.yaml").read_text(encoding="utf-8")
        ) or {}
        llm = data.get("llm") or {}
        assert llm.get("digest_expand_below_target") is True, slug
        assert llm.get("min_digest_words") == floor, slug

    @pytest.mark.parametrize("slug", list(_DEPTH_PILOTS))
    def test_pilot_digest_prompt_has_depth_over_breadth(self, slug):
        path = SHOWS / "prompts" / f"{slug}_digest.txt"
        text = path.read_text(encoding="utf-8")
        assert "DEPTH OVER BREADTH" in text, slug
        assert "continuity" in text.lower() or "tracked program" in text.lower()

    def test_news_digest_expansion_prompt_mentions_deep_dive_lever(self):
        from engine.generator import _build_digest_expansion_retry_prompt

        prompt = _build_digest_expansion_retry_prompt(
            800, 1400, "short draft", narrative=False,
        )
        assert "licensed deep-dive" in prompt.lower() or "deep-dive" in prompt
        assert "continuity" in prompt.lower()
        assert "invent" in prompt.lower()


# ---------------------------------------------------------------------------
# Network discovery promo
# ---------------------------------------------------------------------------

class TestNetworkDiscoverySurfaces:
    def test_first_principles_and_dp_pod_in_rotation(self):
        from engine.network_promo import ENGLISH_ORDER, ENGLISH_SHOWS

        assert "first_principles" in ENGLISH_SHOWS
        assert "dp_pod" in ENGLISH_SHOWS
        assert ENGLISH_ORDER[-2:] == ["first_principles", "dp_pod"]

    def test_promo_includes_surface_sentence(self):
        from engine.network_promo import (
            NETWORK_SURFACES,
            build_network_promo,
            pick_featured_surface,
        )

        promo = build_network_promo("tesla", _DAY)
        assert "Nerra Network" in promo
        assert "nerranetwork.com" in promo
        surface = pick_featured_surface("tesla", _DAY)
        assert surface is not None
        assert surface["spoken"] in promo
        # No chapter-marker landmines in any surface spoken copy.
        for s in NETWORK_SURFACES:
            low = s["spoken"].lower()
            assert " under the hood" not in low
            assert "next time" not in low

    def test_surface_rotation_covers_all(self):
        from engine.network_promo import (
            NETWORK_SURFACES,
            _weighted_surface_pool,
            pick_featured_surface,
        )

        # Walk the weighted pool (gallery weight 3) so every unique id appears.
        pool_len = len(_weighted_surface_pool())
        seen = {
            pick_featured_surface("tesla", _DAY + dt.timedelta(days=i))["id"]
            for i in range(pool_len * 2)
        }
        assert seen == {s["id"] for s in NETWORK_SURFACES}

    def test_gallery_is_weighted_above_peers(self):
        from engine.network_promo import (
            NETWORK_SURFACES,
            _weighted_surface_pool,
            pick_featured_surface,
        )

        pool = _weighted_surface_pool()
        gallery_slots = sum(1 for s in pool if s["id"] == "gallery")
        peer_slots = sum(1 for s in pool if s["id"] == "blogs")
        assert gallery_slots >= 3
        assert gallery_slots > peer_slots
        # Over a long window gallery should appear more often than blogs.
        counts = {"gallery": 0, "blogs": 0}
        for i in range(len(pool) * 4):
            sid = pick_featured_surface(
                "tesla", _DAY + dt.timedelta(days=i))["id"]
            if sid in counts:
                counts[sid] += 1
        assert counts["gallery"] > counts["blogs"]

    def test_surface_x_reply_has_utm(self):
        from engine.network_promo import build_surface_x_reply

        text = build_surface_x_reply("tesla", _DAY)
        assert "utm_campaign=network_discovery" in text
        assert "nerranetwork.com/" in text
        assert "More from the Nerra Network:" in text

    def test_x_reply_alternates_sibling_and_surface(self):
        import run_show
        from engine.config import load_config

        cfg = load_config("shows/tesla.yaml")
        even = dt.date(2026, 7, 9)  # even toordinal → sibling
        odd = dt.date(2026, 7, 8)   # odd → surface
        assert even.toordinal() % 2 == 0
        assert odd.toordinal() % 2 == 1
        sibling = run_show._build_cross_promo_reply(cfg, even)
        surface = run_show._build_cross_promo_reply(cfg, odd)
        assert "utm_campaign=cross_promo" in sibling
        assert "utm_campaign=network_discovery" in surface

    def test_newsletter_footer_links_gallery_and_data(self):
        src = (
            ROOT / "engine" / "newsletter_template.py"
        ).read_text(encoding="utf-8")
        assert "gallery.html" in src
        assert "data.html" in src
        assert "start-here.html" in src

    def test_youtube_description_can_include_discovery(self):
        src = (ROOT / "engine" / "video_metadata.py").read_text(encoding="utf-8")
        assert "pick_featured_surface" in src
        assert "discovery_line" in src


class TestReviewDoc:
    def test_review_doc_present(self):
        path = (
            ROOT / "docs" / "reviews"
            / "depth_and_network_discovery_2026_07_09.md"
        )
        assert path.is_file()
        body = path.read_text(encoding="utf-8")
        assert "digest_expand_below_target" in body
        assert "gallery" in body.lower()
        assert "landmine #17" in body
