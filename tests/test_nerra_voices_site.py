"""Drift guards for Nerra Voices as the 18th network show (September 2026).

Nerra Voices is The Age of AI's sister interview show: same Mira pipeline,
no AI angle. These guards cover the *site + registry* side of the launch
(brand assets, network registration, the surfaces that hardcode a show
list). The pipeline/Worker routing has its own guards in
tests/test_nerra_voices_pipeline.py and tests/test_voices_worker_routing.py.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

SLUG = "nerra_voices"


def _meta() -> dict:
    return yaml.safe_load(
        (ROOT / "shows" / "network_meta.yaml").read_text(encoding="utf-8"))


def _show_yaml() -> dict:
    return yaml.safe_load(
        (ROOT / "shows" / SLUG.replace("-", "_")).with_suffix(".yaml")
        .read_text(encoding="utf-8"))


class TestBrandColour:
    """One teal, registered in four places, and it must clear WCAG AA on
    white — the newsletter contrast hard-block silently stops sends for
    any show whose brand colour drops below 4.5:1. The first draft
    (#0EA5A4) was 3.03:1."""

    def test_registered_everywhere_and_identical(self):
        meta = _meta()[SLUG]
        show = _show_yaml()
        colours = {
            "network_meta.brand_color": meta["brand_color"],
            "network_meta.brand_color_dark": meta["brand_color_dark"],
            "network_meta.theme_color": meta["theme_color"],
            "yaml.voices.brand_color": show["voices"]["brand_color"],
        }
        assert len({c.upper() for c in colours.values()}) == 1, colours

    def test_passes_aa_on_white(self):
        from engine.contrast_validator import contrast_ratio
        hexv = _meta()[SLUG]["brand_color"].lstrip("#")
        rgb = tuple(int(hexv[i:i + 2], 16) for i in (0, 2, 4))
        assert contrast_ratio(rgb, (255, 255, 255)) >= 4.5

    def test_generator_palette_matches_registered_brand_color(self):
        """scripts/generate_age_of_ai_brand.py draws Mira's bars in the
        registered teal; cover and site accent can never drift apart."""
        gen = (ROOT / "scripts" / "generate_age_of_ai_brand.py").read_text(
            encoding="utf-8")
        hexv = _meta()[SLUG]["brand_color"].lstrip("#")
        rgb = tuple(int(hexv[i:i + 2], 16) for i in (0, 2, 4))
        assert f"SIGNAL_TEAL = {rgb}" in gen


class TestBrandAssets:
    def test_cover_art_full_set(self):
        from PIL import Image
        covers = ROOT / "assets" / "covers"
        with Image.open(covers / "nerra-voices.jpg") as im:
            assert im.size == (3000, 3000), "podcast cover must be 3000x3000"
        for name in ("nerra-voices.webp", "nerra-voices-800.webp",
                     "nerra-voices-400.webp"):
            assert (covers / name).exists(), name

    def test_logo_svgs_carry_the_brand(self):
        """The Dialogue mark, teal edition: Human Amber wave UNCHANGED (amber
        = the human, brand rule 2), Deep Water surface, the show teal."""
        for name in ("nerra-voices-mark.svg", "nerra-voices-logo.svg"):
            svg = (ROOT / "assets" / name).read_text(encoding="utf-8")
            assert "#FBBF24" in svg, f"{name}: Human Amber wave missing"
            assert "#071E20" in svg, f"{name}: Deep Water surface missing"
            assert "polyline" in svg, f"{name}: the human wave is missing"
            assert "rgb(15, 118, 110)" in svg, f"{name}: Signal Teal bars missing"
            assert "#7C3AED" not in svg and "rgb(124, 58, 237)" not in svg, (
                f"{name}: Age of AI violet leaked into the sister brand")

    def test_generator_is_parameterised_not_forked(self):
        """One generator, two BrandSpecs — the Age of AI palette constants
        stay module-level for that show's own drift guard."""
        gen = (ROOT / "scripts" / "generate_age_of_ai_brand.py").read_text(
            encoding="utf-8")
        assert "class BrandSpec" in gen
        assert 'slug="nerra_voices"' in gen
        assert "SIGNAL_VIOLET = (124, 58, 237)" in gen
        assert "HUMAN_AMBER = (251, 191, 36)" in gen
        assert "--show" in gen
        assert not (ROOT / "scripts" / "generate_nerra_voices_brand.py").exists()


class TestNetworkRegistration:
    def test_in_network_shows_next_to_age_of_ai(self):
        import generate_html as g
        assert SLUG in g.NETWORK_SHOWS
        cfg = g.NETWORK_SHOWS[SLUG]
        assert cfg["show_page"] == "nerra-voices.html"
        assert cfg["summaries_page"] == "nerra-voices-summaries.html"
        assert cfg["rss_file"] == "nerra_voices_podcast.rss"
        assert cfg["podcast_image"] == "assets/covers/nerra-voices.jpg"
        assert cfg["related_show"] == "age_of_ai"
        assert SLUG in g._SHOW_PICKER_TAGS
        order = [s for s, _ in sorted(
            g.NETWORK_SHOWS.items(), key=lambda kv: kv[1].get("display_order", 0))]
        assert order.index(SLUG) == order.index("age_of_ai") + 1

    def test_show_pages_exist_and_carry_the_teal(self):
        for name in ("nerra-voices.html", "nerra-voices-summaries.html",
                     "blog/nerra_voices/index.html"):
            assert (ROOT / name).is_file(), name
        page = (ROOT / "nerra-voices.html").read_text(encoding="utf-8")
        assert "--show-color: #0F766E" in page
        assert "nerra-voices-apply.html" in page, "hero must promote the apply page"
        assert "#0EA5A4" not in page

    def test_summaries_json_is_the_voices_shape(self):
        import json
        data = json.loads((ROOT / "digests" / SLUG / f"summaries_{SLUG}.json")
                          .read_text(encoding="utf-8"))
        assert isinstance(data.get("episodes"), list)

    def test_no_hand_made_empty_feed(self):
        """engine.publisher.update_rss_feed creates the feed on first
        publish (that is how age_of_ai_podcast.rss appeared). A committed
        zero-item feed would be submitted to directories as a real show."""
        rss = ROOT / "nerra_voices_podcast.rss"
        if rss.exists():
            assert "<item>" in rss.read_text(encoding="utf-8")

    def test_audit_exempt_like_age_of_ai(self):
        import review_episodes
        assert SLUG in review_episodes.AUDIT_EXEMPT_SLUGS
        assert SLUG not in review_episodes.SHOW_REGISTRY

    def test_dashboard_treats_it_as_on_demand(self):
        import importlib
        gd = importlib.import_module("scripts.generate_dashboard")
        assert gd._SHOW_PAGE_BY_SLUG[SLUG] == "nerra-voices.html"
        assert gd._PUB_AGE_THRESHOLDS_H[SLUG] is None

    def test_newsletter_adjacency_points_at_the_sister(self):
        data = yaml.safe_load(
            (ROOT / "shows" / "_defaults.yaml").read_text(encoding="utf-8"))
        adj = data["newsletter"]["network_adjacencies"]
        assert "age_of_ai" in adj[SLUG]

    def test_review_rotation_registered(self):
        state = yaml.safe_load(
            (ROOT / "docs" / "reviews" / "review_state.yaml").read_text(encoding="utf-8"))
        found = any(SLUG in (v or {}) for v in state.values() if isinstance(v, dict))
        assert found, "nerra_voices missing from docs/reviews/review_state.yaml"

    def test_directory_submission_lists_it(self):
        src = (ROOT / "scripts" / "submit_to_directories.py").read_text(encoding="utf-8")
        assert '("nerra_voices", "Nerra Voices", "nerra_voices_podcast.rss")' in src


class TestTemplateSurfaces:
    T = ROOT / "templates"

    def test_show_page_and_blog_index_promote_the_apply_page(self):
        for name in ("show_page.html.j2", "blog_index.html.j2"):
            src = (self.T / name).read_text(encoding="utf-8")
            assert "nerra-voices-apply.html" in src, name
            assert "'nerra_voices'" in src, name

    def test_start_here_lists_it_under_stories(self):
        src = (self.T / "start_here.html.j2").read_text(encoding="utf-8")
        rows = re.findall(r"s\.slug in \[(.*?)\]", src)
        stories = [r for r in rows if "'unintended_consequences'" in r]
        assert stories and "'nerra_voices'" in stories[0]

    def test_personal_lineup_sample_excludes_it(self):
        src = (self.T / "network_page.html.j2").read_text(encoding="utf-8")
        assert "'nerra_voices'" in "".join(
            re.findall(r"rejectattr\('slug', 'in', \[(.*?)\]\)", src))

    def test_mira_disclosure_names_all_three_shows(self):
        disc = (self.T / "ai_disclosure.html.j2").read_text(encoding="utf-8")
        assert "nerra-voices.html" in disc
        faq = (self.T / "faq.html.j2").read_text(encoding="utf-8")
        assert faq.count("Nerra Voices") >= 2, "JSON-LD and visible FAQ answer"

    def test_search_legacy_fallback_includes_it(self):
        js = (ROOT / "assets" / "js" / "search.js").read_text(encoding="utf-8")
        assert "/api/nerra_voices.json" in js


class TestDocs:
    def test_runbook_exists_and_covers_launch_steps(self):
        doc = (ROOT / "docs" / "nerra_voices.md").read_text(encoding="utf-8")
        for needle in ("CALCOM_BOOKING_URL_NERRA_VOICES", "spotify_show_id",
                       "apple_show_id", "assets/music/nerra_voices.mp3",
                       "nerra_voices_podcast.rss", "Reassign"):
            assert needle in doc, needle

    def test_brand_doc_has_the_sister_section(self):
        doc = (ROOT / "docs" / "age_of_ai_brand.md").read_text(encoding="utf-8")
        assert "## Nerra Voices" in doc
        assert "#0F766E" in doc
        assert "--show nerra_voices" in doc
