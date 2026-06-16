"""Source-linking guards for blog posts (June 2026).

The network uses two source formats and BOTH must populate the "Sources"
section so no blog article ships without linked sources:
  1. inline ``Source: [domain](url)`` per story, and
  2. a trailing ``## Sources`` markdown list (Models & Agents / MAB /
     Planetterrian / Omni View) with no ``Source:`` prefix.
The trailing list must move into the favicon Sources section (deduped by URL),
not be duplicated as a raw list in the article body.
"""

from __future__ import annotations


class TestSourceExtraction:
    def test_inline_source_prefix(self):
        from engine.blog import _extract_source_urls
        md = "1. **Story** — text. Source: [reddit.com](https://reddit.com/r/x/1)\n"
        assert _extract_source_urls(md) == ["https://reddit.com/r/x/1"]

    def test_trailing_sources_list_markdown(self):
        from engine.blog import _extract_source_urls
        md = (
            "## Top News\n- a story\n\n"
            "## Sources\n"
            "- [phys.org](https://phys.org/a)\n"
            "- [reddit.com](https://www.reddit.com/r/s/2)\n"
        )
        assert _extract_source_urls(md) == [
            "https://phys.org/a",
            "https://www.reddit.com/r/s/2",
        ]

    def test_read_more_heading_variant(self):
        from engine.blog import _extract_source_urls
        md = "Read more\n- [x.com](https://x.com/a/1)\n"
        assert _extract_source_urls(md) == ["https://x.com/a/1"]

    def test_dedupes_repeated_url(self):
        from engine.blog import _extract_source_urls
        md = ("Source: https://reddit.com/r/x/1\n"
              "Source: https://reddit.com/r/x/1\n")
        assert _extract_source_urls(md) == ["https://reddit.com/r/x/1"]

    def test_mid_article_sources_heading_not_treated_as_list(self):
        # "## Sources of funding" is a real story heading, not the sources list.
        from engine.blog import _extract_source_urls
        md = "## Sources of funding\nThe program https://example.com/grant matters.\n"
        assert _extract_source_urls(md) == []

    def test_body_strips_trailing_sources_list(self):
        from engine.blog import clean_digest_for_blog
        md = ("# Show\n\nBody paragraph.\n\n"
              "## Sources\n- [phys.org](https://phys.org/a)\n- [x.com](https://x.com/b)\n")
        cleaned = clean_digest_for_blog(md)
        assert "## Sources" not in cleaned
        assert "phys.org/a" not in cleaned
        assert "Body paragraph." in cleaned

    def test_inline_source_pills_kept_in_body(self):
        # Per-story inline sources are NOT a trailing list — keep them.
        from engine.blog import clean_digest_for_blog
        md = "1. **Story** text. Source: [reddit.com](https://reddit.com/r/x/1)\n"
        cleaned = clean_digest_for_blog(md)
        assert "reddit.com/r/x/1" in cleaned


class TestSourceCardsDedupeByUrl:
    def test_distinct_urls_same_domain_all_kept(self):
        from engine.blog import generate_blog_post_html
        captured = {}

        class _T:
            def render(self, **kw):
                captured.update(kw); return "<html></html>"

        class _Env:
            def get_template(self, name): return _T()

        from generate_html import NETWORK_SHOWS
        meta = {
            "episode_num": 1, "date": "2026-06-15", "date_iso": "2026-06-15",
            "hook": "h", "title": "T",
            "source_urls": [
                "https://www.reddit.com/r/a/1",
                "https://www.reddit.com/r/a/2",
                "https://www.reddit.com/r/a/1",  # dup of #1
            ],
        }
        generate_blog_post_html("## Body\n\ntext", meta, NETWORK_SHOWS["tesla"], _Env())
        urls = [s["url"] for s in captured["source_domains"]]
        assert urls == [
            "https://www.reddit.com/r/a/1",
            "https://www.reddit.com/r/a/2",
        ]
