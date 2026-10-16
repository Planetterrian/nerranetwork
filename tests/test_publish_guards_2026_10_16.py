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
    check_publish_guards,
    digest_has_rendered_sources,
    lead_chapter_present,
    show_requires_lead_chapter,
    show_requires_rendered_sources,
)
from engine.url_utils import strip_tracking  # noqa: E402
from engine.publisher import write_rss_aliases  # noqa: E402


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
    def test_alias_is_byte_copy_with_canonical_self(self, tmp_path: Path):
        canonical = tmp_path / "podcast.rss"
        body = (
            b"<?xml version='1.0'?><rss><channel>"
            b'<atom:link href="https://nerranetwork.com/podcast.rss" rel="self" />'
            b"</channel></rss>"
        )
        canonical.write_bytes(body)
        written = write_rss_aliases(canonical, ["tesla_podcast.rss"])
        assert len(written) == 1
        alias = tmp_path / "tesla_podcast.rss"
        assert alias.read_bytes() == body
        assert b"podcast.rss" in alias.read_bytes()

    def test_tesla_yaml_declares_alias(self):
        import yaml
        raw = yaml.safe_load((ROOT / "shows" / "tesla.yaml").read_text())
        assert "tesla_podcast.rss" in (raw.get("publishing") or {}).get("rss_aliases", [])


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
        late = src[blog:src.index("# 12a-pre. Post-run validation")]
        assert src.index("# 11. Update RSS feed") < blog
        assert "check_publish_guards(" in late
        assert "sys.exit" not in late
        assert "_skip_episode(" not in late
