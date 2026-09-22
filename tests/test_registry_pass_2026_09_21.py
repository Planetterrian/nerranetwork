"""Guards for the registry-consolidation pass (C1, 2026-09-21).

Three changes, all of them meant to be invisible in the rendered output:

* the scaffolded-registry merge became PER-KEY, so a YAML entry for a slug that
  also exists in the hardcoded registry fills the gaps instead of being dropped
  whole (``if slug not in NETWORK_SHOWS`` discarded 30-odd keys silently);
* ``picker_tags`` lives in the registry entry rather than in a parallel
  ``_SHOW_PICKER_TAGS`` dict that only registry-only shows could write to;
* the page language comes from ``engine.show_lang`` instead of a hardcoded pair
  of Russian slugs repeated seven times across two modules.

The hub snapshot below is the load-bearing one. ``picker_tags.topics`` is what
puts a show in a ``/topics/`` hub (``engine.topic_hubs.hub_shows``), so a
transcription slip while moving twelve tag blocks would quietly shrink or empty
a hub — a page that still renders, still validates, and is simply missing half
its shows. A count assertion would pass through exactly that, so this pins the
slug SETS, measured on main at 10988fe1 before the refactor.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

#: hub id -> the shows in it, measured before the refactor.
EXPECTED_HUB_SHOWS = {
    "ai": {"age_of_ai", "models_agents", "models_agents_beginners"},
    "space": {"fascinating_frontiers", "spacex"},
    "markets": {"finansy_prosto", "modern_investing", "spacex", "tesla"},
    "tesla": {"tesla"},
    "science": {"dp_pod", "fascinating_frontiers", "planetterrian"},
    "health-and-longevity": {"planetterrian"},
    "climate-and-energy": {"dp_pod", "env_intel", "tesla"},
    "world-news": {"omni_view"},
    "history-and-consequences": {"first_principles", "unintended_consequences"},
    "engineering": {"first_principles"},
    "language-learning": {"privet_russian"},
    "good-news": {"dp_pod"},
}

#: The slugs every one of the seven replaced tuples named. ``engine.show_lang``
#: derives this from ``tts.language_code``; this pins that the derivation still
#: agrees with the literal it replaced.
HISTORICAL_RU_SLUGS = {"finansy_prosto", "privet_russian"}


class TestTopicHubsDidNotSilentlyShrink:
    def test_every_hub_has_exactly_the_shows_it_had_before(self):
        import generate_html as G
        from engine import topic_hubs as H

        index = H.load_search_index()
        assert index, "no search index — cannot verify hub membership"
        shows = G._build_all_shows_list()
        got = {
            c["hub"]["id"]: {s["slug"] for s in (c.get("shows") or [])}
            for c in H.renderable_hubs(shows, index)
        }
        assert got == EXPECTED_HUB_SHOWS

    def test_every_registered_show_still_declares_picker_topics(self):
        """A show whose tags went missing joins no hub and is not otherwise
        detectable — the homepage card simply stops matching any filter."""
        import generate_html as G

        shows = G._build_all_shows_list()
        # 22 since 2026-09-22 (new-shows Phase 1).
        assert len(shows) == 22
        missing = [
            s["slug"] for s in shows
            if not ((s.get("picker_tags") or {}).get("topics"))
        ]
        assert missing == []


class TestPickerTagsHasOneOwner:
    def test_the_registry_carries_the_tags(self):
        import generate_html as G

        for slug, cfg in G.NETWORK_SHOWS.items():
            assert (cfg.get("picker_tags") or {}).get("topics"), slug

    def test_the_parallel_dict_is_gone(self):
        """``_SHOW_PICKER_TAGS`` was writable only by the YAML path, so a
        hardcoded show could not declare tags at all."""
        import generate_html as G

        assert not hasattr(G, "_SHOW_PICKER_TAGS")


class TestTheMergeIsPerKey:
    def test_a_hardcoded_value_wins_and_yaml_fills_the_gaps(self):
        from generate_html import _merge_show_meta

        existing = {"name": "Hardcoded", "brand_color": "#fff"}
        _merge_show_meta(existing, {"name": "FromYaml", "tagline": "added"})
        assert existing["name"] == "Hardcoded", "YAML overwrote a curated value"
        assert existing["tagline"] == "added", "YAML did not fill a gap"
        assert existing["brand_color"] == "#fff"

    def test_it_does_not_mutate_the_incoming_meta(self):
        from generate_html import _merge_show_meta

        meta = {"tagline": "added"}
        _merge_show_meta({"name": "X"}, meta)
        assert meta == {"tagline": "added"}

    def test_every_registry_only_show_still_arrives_whole(self):
        import generate_html as G

        for slug in ("spacex", "dp_pod", "age_of_ai", "nerra_daily",
                     "nerra_voices", "offshore_north"):
            assert slug in G.NETWORK_SHOWS, slug
            assert G.NETWORK_SHOWS[slug].get("name"), slug


class TestLanguageHasOneOwner:
    def test_it_agrees_with_the_literal_it_replaced(self):
        import generate_html as G
        from engine.show_lang import is_russian

        for slug in G.NETWORK_SHOWS:
            assert is_russian(slug) == (slug in HISTORICAL_RU_SLUGS), slug

    def test_an_unknown_or_empty_slug_is_english(self):
        from engine.show_lang import DEFAULT_LANG, page_lang

        assert page_lang("no_such_show") == DEFAULT_LANG
        assert page_lang(None) == DEFAULT_LANG
        assert page_lang("") == DEFAULT_LANG

    def test_no_module_still_hardcodes_the_russian_pair(self):
        """The reason this pass exists: the pair was repeated seven times, and
        a missed copy renders a page in the wrong language with nothing
        failing. ``engine/show_lang.py`` may name the slugs (its docstring
        explains what it replaced); no renderer may."""
        offenders = []
        for rel in ("generate_html.py", "engine/blog.py"):
            text = (ROOT / rel).read_text(encoding="utf-8")
            for needle in (
                '("finansy_prosto", "privet_russian")',
                '("privet_russian", "finansy_prosto")',
            ):
                if needle in text:
                    offenders.append(f"{rel}: {needle}")
        assert offenders == [], offenders

    def test_a_registry_only_show_can_declare_a_language(self):
        """The property the refactor buys: Nerra Daily has no show YAML, so
        before this it could not be anything but English."""
        import engine.show_lang as SL

        original = SL._META_LANGS
        try:
            SL._reset_cache()
            SL._META_LANGS = {"nerra_daily": "ru"}
            assert SL.is_russian("nerra_daily")
        finally:
            SL._reset_cache()
            SL._META_LANGS = original


class TestTheRussianNewsletterTagStaysAscii:
    """The registry's ``newsletter_tag`` looks dead and is not.

    This pass very nearly deleted it. ``_newsletter_tag_for_slug`` resolves the
    tag from the show YAML for the summaries and show-page context, so checking
    ``_build_all_shows_list()`` shows every show carrying a correct tag with the
    registry key absent — which reads as proof the key is unused. It is not: the
    blog path renders from the RAW registry entry (``generate_blog_posts`` does
    ``cfg = NETWORK_SHOWS[slug]``, and ``engine.blog`` reads
    ``show_config.get("newsletter_tag") or show_config["name"]``), so removing
    it falls back to the Cyrillic display NAME on ~150 Russian blog posts and
    ships a signup tag Buttondown refuses. A full-tree diff caught it; these
    assertions are cheaper than the diff.
    """

    RU_TAGS = {"finansy_prosto": "Finansy Prosto",
               "privet_russian": "Privet Russian"}

    def test_the_registry_still_carries_the_ascii_tag(self):
        import generate_html as G

        for slug, tag in self.RU_TAGS.items():
            assert G.NETWORK_SHOWS[slug].get("newsletter_tag") == tag, slug

    def test_what_a_blog_post_would_render_is_ascii(self):
        """Exactly the expression ``engine.blog`` evaluates."""
        import generate_html as G

        for slug in self.RU_TAGS:
            cfg = G.NETWORK_SHOWS[slug]
            rendered = cfg.get("newsletter_tag") or cfg["name"]
            assert rendered.isascii(), (
                f"{slug} blog posts would post {rendered!r} to Buttondown, "
                "which rejects a tag with no ASCII letter or digit"
            )

    def test_the_context_path_agrees_with_the_registry(self):
        import generate_html as G

        by_slug = {s["slug"]: s for s in G._build_all_shows_list()}
        assert all(s.get("newsletter_tag") for s in by_slug.values())
        for slug, tag in self.RU_TAGS.items():
            assert by_slug[slug]["newsletter_tag"] == tag, slug


class TestDeadWeightIsGone:
    def test_has_performance_loop_is_gone(self):
        """No reader repo-wide — unlike ``newsletter_tag`` above, which was
        checked the same way and turned out to have one."""
        import generate_html as G

        assert [s for s, c in G.NETWORK_SHOWS.items()
                if "has_performance_loop" in c] == []
