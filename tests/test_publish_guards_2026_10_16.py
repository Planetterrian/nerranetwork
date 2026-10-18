"""Oct 16 2026 — publish-time guards from the claims audit.

News shows must ship Sources on the episode page, chapter titles must not
be mid-sentence fragments, the lead story needs its own named chapter, and
Source hrefs must drop referral / gift-link query params.
"""
from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from engine.publish_guards import (  # noqa: E402
    assert_chapter_titles_whole,
    chapter_title_is_fragment,
    chapter_title_is_url_slug,
    check_publish_guards,
    counterpoint_references_lead,
    counterpoint_reused_from_previous,
    digest_has_rendered_sources,
    lead_chapter_present,
    lead_title_is_generic,
    show_requires_lead_chapter,
    show_requires_rendered_sources,
)
from engine.url_utils import strip_tracking  # noqa: E402
from engine.publisher import update_rss_feed, write_rss_aliases  # noqa: E402


def _cfg(**kwargs):
    base = dict(
        slug="tesla",
        narrative_mode=False,
        chapters=SimpleNamespace(known_sections_only=False),
    )
    base.update(kwargs)
    return SimpleNamespace(**base)


class TestSourcesGuard:
    def test_news_show_requires_sources(self):
        assert show_requires_rendered_sources(_cfg()) is True

    def test_narrative_exempt(self):
        assert show_requires_rendered_sources(_cfg(narrative_mode=True)) is False

    def test_interview_exempt(self):
        assert show_requires_rendered_sources(_cfg(slug="age_of_ai")) is False

    def test_digest_with_source_passes(self):
        md = "Story.\n\nSource: [Example](https://example.com/a)\n"
        assert digest_has_rendered_sources(md) is True

    def test_empty_digest_fails_news(self):
        fails = check_publish_guards(config=_cfg(), digest_md="No sources here.\n")
        assert any("no Sources" in f for f in fails)


class TestChapterTitleGuard:
    def test_ellipsis_is_fragment(self):
        assert chapter_title_is_fragment(
            "Yet these observations received little weight in the final…"
        )

    def test_whole_sentence_ok(self):
        assert not chapter_title_is_fragment("Tesla opens sixteen Superchargers.")

    def test_assert_skips_introduction(self):
        chapters = [
            SimpleNamespace(title="Introduction"),
            SimpleNamespace(title="Yet these observations received little weight…"),
        ]
        bad = assert_chapter_titles_whole(chapters)
        assert len(bad) == 1


class TestLeadChapterGuard:
    def test_lead_present(self):
        chapters = [
            SimpleNamespace(title="Introduction"),
            SimpleNamespace(title="Tesla opens sixteen Superchargers"),
            SimpleNamespace(title="Closing"),
        ]
        assert lead_chapter_present(
            chapters, hook="Tesla opens sixteen Superchargers on a vacant site"
        )

    def test_missing_lead_fails_news(self):
        chapters = [
            SimpleNamespace(title="Introduction"),
            SimpleNamespace(title="Closing"),
        ]
        fails = check_publish_guards(
            config=_cfg(),
            digest_md="Source: https://example.com/a\n",
            chapters=chapters,
            hook="Tesla opens sixteen Superchargers",
        )
        assert any("lead story" in f for f in fails)

    def test_spacex_known_sections_exempt(self):
        cfg = _cfg(slug="spacex", chapters=SimpleNamespace(known_sections_only=True))
        assert show_requires_lead_chapter(cfg) is False


class TestStripTracking:
    def test_strips_utm_and_gift_token(self):
        url = (
            "https://www.bloomberg.com/news/a?utm_source=x&accessToken=eyJ.x.y&id=1"
        )
        out = strip_tracking(url)
        assert "utm_source" not in out
        assert "accessToken" not in out
        assert "id=1" in out

    def test_blog_extract_strips(self):
        from engine.blog import _extract_source_urls
        md = (
            "Lead.\n\nSource: [Bloomy](https://www.bloomberg.com/a"
            "?accessToken=eyJ.fake&utm_medium=email)\n"
        )
        urls = _extract_source_urls(md)
        assert urls
        assert "accessToken" not in urls[0]
        assert "utm_medium" not in urls[0]


class TestTeslaRssAlias:
    def test_generator_step_writes_canonical_and_alias(self, tmp_path: Path):
        """run_show's RSS step: update_rss_feed then write_rss_aliases.

        Both files must exist and be byte-identical; atom:link rel=self
        stays on podcast.rss so directories do not fork the feed.
        """
        import datetime as _dt

        canonical = tmp_path / "podcast.rss"
        mp3 = tmp_path / "seed.mp3"
        mp3.write_bytes(b"ID3" + b"\x00" * 128)
        update_rss_feed(
            canonical,
            1,
            "Ep 1: Seed",
            "Seed episode for alias test",
            _dt.date(2024, 1, 1),
            "seed.mp3",
            60.0,
            mp3,
            audio_url="https://audio.nerranetwork.com/digests/seed.mp3",
            channel_title="Tesla Shorts Time",
            channel_description="Daily Tesla news",
            channel_link="https://nerranetwork.com/tesla.html",
            channel_author="Patrick",
            channel_email="contact@nerranetwork.com",
            base_url="https://nerranetwork.com",
        )
        written = write_rss_aliases(canonical, ["tesla_podcast.rss"])
        alias = tmp_path / "tesla_podcast.rss"
        assert written == [alias]
        assert canonical.exists() and alias.exists()
        assert canonical.read_bytes() == alias.read_bytes()
        body = alias.read_bytes()
        assert b'href="https://nerranetwork.com/podcast.rss"' in body
        assert b'tesla_podcast.rss" rel="self"' not in body

    def test_tesla_yaml_declares_alias(self):
        import yaml
        raw = yaml.safe_load((ROOT / "shows" / "tesla.yaml").read_text())
        assert "tesla_podcast.rss" in (raw.get("publishing") or {}).get("rss_aliases", [])

    def test_alias_not_double_listed_in_audit_or_rss_tests(self):
        """Canonical podcast.rss is the only Tesla entry in feed audits."""
        audit = (ROOT / ".github" / "workflows" / "daily-audit.yml").read_text()
        assert '"podcast.rss": ("Tesla Shorts Time"' in audit
        assert "tesla_podcast.rss" not in audit
        rss_tests = (ROOT / "tests" / "test_rss.py").read_text()
        assert 'PROJECT_ROOT / "podcast.rss"' in rss_tests
        assert "tesla_podcast.rss" not in rss_tests
        # VTT backfill globs *_podcast.rss — aliases must stay out.
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "backfill_transcript_vtt",
            ROOT / "scripts" / "backfill_transcript_vtt.py",
        )
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        names = {p.name for p in mod.root_audio_feeds(ROOT)}
        assert "podcast.rss" in names
        assert "tesla_podcast.rss" not in names


class TestUrlSlugChapterTitles:
    def test_slug_detected(self):
        assert chapter_title_is_url_slug("tesla-taiwan-megapack-taipei")

    def test_human_title_ok(self):
        assert not chapter_title_is_url_slug("Taiwan Megapack order for Taipei")

    def test_guard_flags_slug(self):
        chapters = [
            SimpleNamespace(title="Introduction"),
            SimpleNamespace(title="tesla-taiwan-megapack-taipei"),
        ]
        bad = assert_chapter_titles_whole(chapters)
        assert "tesla-taiwan-megapack-taipei" in bad


class TestGenericLeadTitles:
    def test_top_story_is_generic(self):
        assert lead_title_is_generic("Top Story")
        assert lead_title_is_generic("Lead")
        assert lead_title_is_generic("The Ten")

    def test_named_story_ok(self):
        assert not lead_title_is_generic("Peshawar school roof collapse")

    def test_generic_lead_fails_guard(self):
        chapters = [
            SimpleNamespace(title="Introduction"),
            SimpleNamespace(title="Top Story"),
            SimpleNamespace(title="Closing"),
        ]
        fails = check_publish_guards(
            config=_cfg(),
            digest_md="Source: https://example.com/a\n",
            chapters=chapters,
            hook="Peshawar school roof collapse kills 34 children",
        )
        assert any("generic label" in f for f in fails)
        assert not lead_chapter_present(
            chapters, hook="Peshawar school roof collapse kills 34 children"
        )


class TestCounterpointGuards:
    LEAD = (
        "# Show\n\n> **Grok purchase guarantee for Bot buyers.**\n\n"
        "### Top Story\nSpaceX is guaranteeing Grok Bot purchases.\n\n"
    )
    CP_ON_LEAD = (
        "### The Counterpoint\n"
        "Critics say a Grok Bot purchase guarantee shifts risk onto SpaceX "
        "shareholders without fixing Bot quality.\n"
    )
    CP_OFF_LEAD = (
        "### The Counterpoint\n"
        "Ukrainian officials received no advance warning that Starshield "
        "terminals would lose service at speed.\n"
    )

    def test_on_lead_passes(self):
        assert counterpoint_references_lead(
            self.LEAD + self.CP_ON_LEAD,
            hook="Grok purchase guarantee for Bot buyers.",
        )

    def test_off_lead_fails(self):
        assert not counterpoint_references_lead(
            self.LEAD + self.CP_OFF_LEAD,
            hook="Grok purchase guarantee for Bot buyers.",
        )

    def test_reuse_detected(self):
        today = self.LEAD + self.CP_OFF_LEAD
        yesterday = (
            "# Show\n\n> **Starshield outage.**\n\n"
            + self.CP_OFF_LEAD
        )
        assert counterpoint_reused_from_previous(today, yesterday)

    def test_no_counterpoint_section_passes_guard(self):
        fails = check_publish_guards(
            config=_cfg(),
            digest_md="Source: https://example.com/a\nJust news, no counterpoint.\n",
            chapters=None,
            hook="Anything",
            previous_digest_md="old",
        )
        assert not any("Counterpoint" in f for f in fails)

    def test_check_publish_guards_flags_off_lead_and_reuse(self):
        today = self.LEAD + self.CP_OFF_LEAD + "\nSource: https://example.com/a\n"
        yesterday = "# Y\n\n" + self.CP_OFF_LEAD
        fails = check_publish_guards(
            config=_cfg(slug="spacex"),
            digest_md=today,
            chapters=None,
            hook="Grok purchase guarantee for Bot buyers.",
            previous_digest_md=yesterday,
        )
        assert any("does not reference the lead" in f for f in fails)
        assert any("reuses the previous" in f for f in fails)


class TestNerraDailySources:
    def test_rundown_links_count_as_sources(self):
        from engine.blog import _extract_source_urls
        md = (
            "# Nerra Daily\n\n"
            "### SpaceX Daily — Hook\n\n"
            "[Full episode notes](/blog/spacex/ep131.html) · "
            "[SpaceX Daily](/spacex.html)\n\n"
            "### Tesla Shorts Time — Hook\n\n"
            "[Full episode notes](/blog/tesla/ep635.html)\n"
        )
        urls = _extract_source_urls(md)
        assert "https://nerranetwork.com/blog/spacex/ep131.html" in urls
        assert "https://nerranetwork.com/blog/tesla/ep635.html" in urls
        assert len(urls) >= 2


class TestMarketingCopyHonesty:
    def test_home_footer_says_ocean_racing_not_energy(self):
        src = (ROOT / "templates" / "network_page.html.j2").read_text()
        assert "offshore ocean-racing" in src
        assert "offshore energy story" not in src

    def test_faq_does_not_promise_every_transcript(self):
        src = (ROOT / "templates" / "faq.html.j2").read_text()
        assert "Every episode has a written article counterpart on the blog with full transcripts" not in src
        assert "When a transcript is available" in src

    def test_editorial_matches_flag_policy(self):
        src = (ROOT / "templates" / "editorial.html.j2").read_text()
        assert "every sourced item must be covered by a\n                verified claim" not in src
        assert "publish-and-mark" in src


class TestTheGuardsNeverCostAPublishedEpisode:
    """Same-day correction. Replayed over the 334 October episodes, the
    first version stopped 98 — every desk's "Also Today" section, a "WHO
    warns…" headline, a paper titled "Whose Data, Whose Benchmark?", and
    Привет, Русский! (a lesson show with no Sources by design) after its
    feed was already updated."""

    @pytest.mark.parametrize("title", [
        "Also Today", "WHO warns of consequences from delayed medical aid into Gaza",
        "Whose Data, Whose Benchmark? A User-Centric Framework",
        "Still no deal on the port strike", "For the record",
    ])
    def test_whole_titles_are_not_fragments(self, title):
        assert not chapter_title_is_fragment(title)

    def test_a_connective_opener_still_is(self):
        assert chapter_title_is_fragment("And the regulator said it would wait")

    def test_the_lesson_show_has_no_sources_by_design(self):
        assert show_requires_rendered_sources(_cfg(slug="privet_russian")) is False

    def test_run_show_stops_only_before_synthesis_and_only_as_a_skip(self):
        src = (ROOT / "run_show.py").read_text(encoding="utf-8")
        tts = src.index("# 9. TTS")
        guard = src.index("from engine.publish_guards import check_publish_guards")
        assert guard < tts
        early = src[guard:tts]
        assert '_skip_episode("publish_guard_no_sources"' in early
        assert "sys.exit(1)" not in early
        # After the feed is updated, a guard may only warn.
        blog = src.index("# 12a. Generate blog post")
        assert src.index("# 11. Update RSS feed") < blog < src.index("# 12a-pre. Post-run validation")
        # Oct 18 2026: the blog writer is built by _make_blog_writer (the
        # separate video job calls it too); its body is what runs after the feed.
        late = src[src.index("def _make_blog_writer("):src.index("    return _write_blog_post\n")]
        assert "check_publish_guards(" in late
        assert "sys.exit" not in late
        assert "_skip_episode(" not in late
