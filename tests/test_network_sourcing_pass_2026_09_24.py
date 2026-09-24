"""Network sourcing pass (2026-09-24): the launch cohort's sourcing floor
ported to every established news show, a Sources line in the show notes, a
comma-density instrument, and the Nerra Personal vocabulary widened to the
cohort. Pins the shape so a partial revert fails CI, and pins what must NOT
change: the narrative shows, the Russian lesson show, the hook_shape
arm/control experiment, and the Nerra Daily lineup.
"""

from __future__ import annotations

from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]

#: The news shows that gained the sourcing floor, with their full-text depth.
NEWS_SHOWS = {
    "tesla": 12, "spacex": 12, "models_agents": 12, "models_agents_beginners": 10,
    "fascinating_frontiers": 12, "planetterrian": 12, "omni_view": 12,
    "env_intel": 10, "modern_investing": 12, "finansy_prosto": 8,
}
#: Shows whose own posts are primary sources — X policy stays legacy.
OWN_VOICE_SHOWS = ("tesla", "spacex")
#: Shows the pass must leave byte-identical on these knobs.
UNTOUCHED = ("unintended_consequences", "first_principles", "dp_pod",
             "privet_russian", "age_of_ai")


def _cfg(slug):
    return yaml.safe_load((ROOT / "shows" / f"{slug}.yaml").read_text(encoding="utf-8"))


class TestSourcingFloorOnTheNewsShows:
    def test_full_text_depth(self):
        for slug, depth in NEWS_SHOWS.items():
            assert _cfg(slug).get("fetch_full_text") == depth, slug

    def test_preferred_domains_are_primary_publishers(self):
        for slug in NEWS_SHOWS:
            doms = _cfg(slug).get("preferred_domains") or []
            assert 4 <= len(doms) <= 8, (slug, doms)
            for d in doms:
                assert d == d.lower() and "/" not in d and not d.startswith("www."), (slug, d)
                assert d not in ("x.com", "twitter.com", "news.google.com"), (slug, d)

    def test_x_policy_follows_who_owns_the_story(self):
        for slug in NEWS_SHOWS:
            pol = _cfg(slug).get("x_posts_as_sources")
            if slug in OWN_VOICE_SHOWS:
                assert pol is None, slug  # Tesla's / SpaceX's own posts are primary
            else:
                assert pol == "secondary", slug

    def test_x_only_lead_lint_where_a_lead_section_exists(self):
        from engine.digest_lint import LEAD_SECTIONS, LINTS
        assert "x_only_lead" in LINTS
        for slug in ("models_agents", "models_agents_beginners", "fascinating_frontiers",
                     "planetterrian", "omni_view", "env_intel"):
            assert "x_only_lead" in (_cfg(slug).get("digest_lints") or []), slug
        # MIT and the Russian show have no LEAD_SECTIONS header — the lint would
        # be a no-op there, so it is not listed (the config stays honest).
        for slug in ("modern_investing", "finansy_prosto", "tesla", "spacex"):
            assert not _cfg(slug).get("digest_lints"), slug
        assert "Top News" in LEAD_SECTIONS and "Top Story" in LEAD_SECTIONS

    def test_evidence_rung_is_not_on_the_science_shows(self):
        # Its rung vocabulary is biomedical (mice, phase 2, n participants);
        # a paleontology or astronomy paper has none, so on FF / PT it fired
        # on 15-19 items per six digests in replay — a regeneration a day for
        # a false positive. Left off deliberately.
        for slug in ("fascinating_frontiers", "planetterrian"):
            assert "evidence_rung" not in (_cfg(slug).get("digest_lints") or []), slug

    def test_untouched_shows_stay_untouched(self):
        for slug in UNTOUCHED:
            c = _cfg(slug)
            for key in ("fetch_full_text", "preferred_domains", "x_posts_as_sources", "digest_lints"):
                assert not c.get(key), (slug, key)

    def test_hook_shape_experiment_is_not_disturbed(self):
        # The Sep 22 spoken-open experiment reads the three arm shows against
        # the control shows; this pass adds no hook_shape include anywhere.
        for slug in ("models_agents", "planetterrian", "omni_view", "env_intel",
                     "modern_investing", "models_agents_beginners"):
            p = ROOT / "shows" / "prompts" / f"{slug}_digest.txt"
            if p.exists():
                assert "hook_shape" not in p.read_text(encoding="utf-8"), slug

    def test_configs_load_with_the_new_keys(self):
        from engine.config import load_config
        for slug, depth in NEWS_SHOWS.items():
            c = load_config(ROOT / "shows" / f"{slug}.yaml")
            assert c.fetch_full_text == depth
            assert c.preferred_domains and all(d == d.lower() for d in c.preferred_domains)


class TestSourcesLineInShowNotes:
    DIGEST = (
        "# Show\n> **Hook.**\n\n### Top News\n"
        "**A: BBC**\nBody. Source: [bbc.com](https://www.bbc.com/news/articles/a1?at_medium=x)\n\n"
        "**B: Reuters**\nBody. Source: [reuters.com](https://www.reuters.com/world/b2)\n\n"
        "**C: BBC again**\nBody. Source: [bbc.com](https://www.bbc.com/news/articles/c3)\n\n"
        "**D: a post**\nBody. Source: [x.com](https://x.com/h/status/9)\n"
    )

    def test_one_link_per_domain_publishers_first(self):
        from engine.show_notes import source_pairs, sources_footer
        pairs = source_pairs(self.DIGEST)
        assert [d for d, _ in pairs] == ["bbc.com", "reuters.com", "x.com"]
        assert pairs[0][1].startswith("https://www.bbc.com/news/articles/a1")
        line = sources_footer(self.DIGEST)
        assert line.startswith("Sources: [bbc.com](")
        assert " · [reuters.com](" in line and line.endswith("(https://x.com/h/status/9)")

    def test_no_sources_no_line(self):
        from engine.show_notes import sources_footer
        assert sources_footer("# Show\n\nA digest with no links at all.") == ""
        assert sources_footer("") == ""

    def test_cap_and_language(self):
        from engine.show_notes import MAX_SOURCES, sources_footer
        many = "\n".join(f"Item. Source: [d{i}.com](https://d{i}.com/a)" for i in range(20))
        assert sources_footer(many).count("](") == MAX_SOURCES
        assert sources_footer(self.DIGEST, language="ru").startswith("Источники: ")

    def test_renders_as_anchors_in_rss_html(self):
        from engine.publisher import _markdown_to_rss_html
        from engine.show_notes import sources_footer
        html = _markdown_to_rss_html(sources_footer(self.DIGEST))
        assert '<a href="https://www.reuters.com/world/b2">reuters.com</a>' in html

    def test_run_show_appends_it_before_the_disclosure(self):
        src = (ROOT / "run_show.py").read_text(encoding="utf-8")
        i = src.index("from engine.show_notes import sources_footer")
        j = src.index("_rss_disclosure = _rss_disclosure_for(config, args.show)", i)
        assert i < j
        assert 'metrics.record("show_notes_sources"' in src[i:j]

    def test_the_committed_digests_would_carry_one(self):
        # The property is "the digest cites sources, so the feed gets a line"
        # — counted in SOURCES, not domains: M&A Ep183 (2026-09-24) cited
        # twelve arXiv papers and the line rightly collapsed to one domain.
        from engine.blog import _extract_source_urls
        from engine.show_notes import source_pairs
        for slug, d in (("spacex", "spacex"), ("models_agents", "models_agents"),
                        ("omni_view_africa_mideast", "omni_view_africa_mideast")):
            latest = sorted(p for p in (ROOT / "digests" / d).glob("*_Ep*.md") if "_reader" not in p.name)[-1]
            text = latest.read_text(encoding="utf-8")
            assert len(_extract_source_urls(text)) >= 3, slug
            assert len(source_pairs(text)) >= 1, slug


class TestCommaDensityInstrument:
    def test_measured_on_both_texts(self):
        from engine.script_audit import audit_script, commas_per_100_words
        assert commas_per_100_words("") is None
        assert commas_per_100_words("a, b, c d") == 50.0
        a = audit_script("One, two. Three four.", digest_text="Five, six, seven eight.", hook="")
        m = a.to_metrics()
        assert m["script_commas_per_100w"] == 25.0 and m["digest_commas_per_100w"] == 50.0

    def test_snapshot_has_the_column(self):
        src = (ROOT / "scripts" / "review_snapshot.py").read_text(encoding="utf-8")
        assert "| commas |" in src and "commas_per_100w" in src


class TestPersonalVocabularyWidened:
    def test_cohort_is_choosable_and_the_daily_is_unchanged(self):
        from engine.daily_edition import EDITIONS
        from engine.personal_edition import (
            PERSONAL_EXTRA_SHOW_SLUGS, PERSONAL_SHOW_SLUGS, personal_edition_spec,
        )
        assert set(PERSONAL_EXTRA_SHOW_SLUGS) == {
            "vancouver", "collingwood", "prediction_markets", "mag7", "ai_chips",
            "peptides", "longevity", "omni_view_world", "omni_view_north_america",
            "omni_view_europe", "omni_view_asia_pacific", "omni_view_africa_mideast",
            "omni_view_latam",
        }
        assert "vancouver" not in EDITIONS["en"].lineup
        spec = personal_edition_spec()
        assert spec.lineup == PERSONAL_SHOW_SLUGS and spec.slug == EDITIONS["en"].slug
        for slug in PERSONAL_EXTRA_SHOW_SLUGS:
            assert (ROOT / "shows" / f"{slug}.yaml").exists(), slug

    def test_builder_discovers_on_the_widened_spec(self):
        src = (ROOT / "scripts" / "build_personal_feeds.py").read_text(encoding="utf-8")
        assert "personal_edition_spec()" in src
        assert 'discover_segments(\n        EDITIONS["en"]' not in src

    def test_worker_and_join_page_follow(self):
        ts = (ROOT / "workers" / "gallery" / "src" / "personal.ts").read_text(encoding="utf-8")
        from engine.personal_edition import PERSONAL_SHOW_SLUGS
        for slug in PERSONAL_SHOW_SLUGS:
            assert f'"{slug}"' in ts, slug
        import generate_html as gh
        assert len(gh._personal_shows_list()) == len(PERSONAL_SHOW_SLUGS)


class TestDocsAndRegister:
    def test_register_entry(self):
        reg = yaml.safe_load((ROOT / "docs" / "experiments.yaml").read_text(encoding="utf-8"))
        ids = {e["id"] for e in reg["experiments"]}
        assert "network-sourcing-pass-2026-09-24" in ids

    def test_claude_md_no_longer_calls_the_description_line_a_hole(self):
        md = (ROOT / "CLAUDE.md").read_text(encoding="utf-8")
        assert "Known hole, not fixed here" not in md
        assert "network sourcing pass" in md.lower()
