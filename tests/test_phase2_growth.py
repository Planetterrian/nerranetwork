"""Phase 2 (Growth & Trust Surface) drift guards.

Additive web/distribution enhancements, all non-breaking:
  * PodcastEpisode JSON-LD on blog posts is now fully populated + valid
    (previously rendered empty url/datePublished/transcript).
  * Per-show AI-transparency badge on blog posts and show pages.
  * Share row gains Facebook + Email and UTM attribution on every network.
  * Inline transcript section is anchored (#transcript) and referenced by the
    PodcastEpisode JSON-LD transcript field.

Tests render through the real generators so a template regression is caught.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
TESLA_DIGESTS = PROJECT_ROOT / "digests" / "tesla_shorts_time"


def _tesla_episode_with_transcript():
    """Find a Tesla episode number that has a committed *_tts.txt (so the
    blog renderer will load + render a transcript). Tesla always has many."""
    for tts in sorted(TESLA_DIGESTS.glob("*_tts.txt")):
        m = re.search(r"_Ep(\d+)_", tts.stem)
        if m:
            return int(m.group(1))
    return None


def _metadata(ep_num):
    return {
        "episode_num": ep_num,
        "date": "2026-05-29",
        "date_iso": "2026-05-29",
        "hook": "A uniquely worded hook about Tesla robotaxis expanding to Texas.",
        "source_urls": ["https://www.teslarati.com/example"],
        "word_count": 500,
        "reading_time_min": 3,
        # Parent dir drives the transcript (_tts.txt) glob.
        "_md_path": str(TESLA_DIGESTS / "probe.md"),
    }


_MD = "## Top Story\n\nTesla expanded its robotaxi program today. " * 5


def _render_blog_html(ep_num):
    from engine.blog import generate_blog_post_html
    from generate_html import NETWORK_SHOWS, _get_jinja_env

    return generate_blog_post_html(
        _MD, _metadata(ep_num), NETWORK_SHOWS["tesla"], _get_jinja_env()
    )


def _ld_json_blocks(html):
    raw = re.findall(
        r'<script type="application/ld\+json">\s*(.*?)\s*</script>', html, re.DOTALL
    )
    return [json.loads(b) for b in raw]  # raises if any block is invalid JSON


# ---------------------------------------------------------------------------
# engine/blog.py context (captured via a fake template env)
# ---------------------------------------------------------------------------

class TestBlogContext:
    def _capture_context(self, ep_num):
        captured = {}

        class _T:
            def render(self, **kw):
                captured.update(kw)
                return "<html></html>"

        class _Env:
            def get_template(self, name):
                return _T()

        from engine.blog import generate_blog_post_html
        from generate_html import NETWORK_SHOWS

        generate_blog_post_html(_MD, _metadata(ep_num), NETWORK_SHOWS["tesla"], _Env())
        return captured

    def test_seo_context_keys_present(self):
        ep = _tesla_episode_with_transcript()
        assert ep is not None, "expected at least one Tesla _tts.txt"
        ctx = self._capture_context(ep)
        assert ctx["page_url"].endswith(f"/ep{ep:03d}.html")
        assert ctx["date"], "datePublished source must be populated"
        assert "audio_url" in ctx
        assert ctx["_is_ru"] is False

    def test_transcript_url_anchors_when_transcript_present(self):
        ep = _tesla_episode_with_transcript()
        ctx = self._capture_context(ep)
        assert ctx["transcript"], "transcript text should load for an ep with a tts file"
        assert ctx["transcript_url"] == f"{ctx['page_url']}#transcript"

    def test_transcript_url_empty_when_absent(self):
        # Episode number with no matching _tts.txt -> no transcript -> empty url.
        ctx = self._capture_context(999999)
        assert ctx["transcript"] == ""
        assert ctx["transcript_url"] == ""


# ---------------------------------------------------------------------------
# Rendered blog post HTML
# ---------------------------------------------------------------------------

class TestBlogPostRender:
    @pytest.fixture(scope="class")
    def html(self):
        ep = _tesla_episode_with_transcript()
        assert ep is not None
        return _render_blog_html(ep)

    def test_all_jsonld_blocks_are_valid_json(self, html):
        blocks = _ld_json_blocks(html)
        assert blocks, "expected JSON-LD blocks"

    def test_podcastepisode_jsonld_is_populated(self, html):
        # Find the standalone PodcastEpisode block (the supplementary one).
        eps = []
        for b in _ld_json_blocks(html):
            items = b if isinstance(b, list) else [b]
            eps += [x for x in items if x.get("@type") == "PodcastEpisode"]
        assert eps, "no PodcastEpisode JSON-LD found"
        ep = eps[-1]
        assert ep["url"].startswith("https://nerranetwork.com/blog/tesla/")
        assert ep["datePublished"], "datePublished must not be empty"
        assert ep["name"], "name must not be empty"
        assert ep["isPartOf"]["@type"] == "PodcastSeries"
        assert ep["inLanguage"] == "en"
        assert ep["transcript"].endswith("#transcript")

    def test_share_row_has_facebook_email_and_utm(self, html):
        assert "facebook.com/sharer" in html
        assert "mailto:?subject=" in html
        # Every share network is UTM-tagged (url-encoded '=' -> %3D).
        for src in ("twitter", "linkedin", "facebook", "whatsapp", "telegram", "email"):
            assert f"utm_source%3D{src}" in html, f"missing UTM for {src}"

    def test_transcript_section_is_anchored(self, html):
        assert 'class="blog-transcript" id="transcript"' in html

    def test_ai_badge_present(self, html):
        assert "nn-ai-badge" in html
        assert "ai-disclosure.html" in html


# ---------------------------------------------------------------------------
# ai_badge macro + show page
# ---------------------------------------------------------------------------

class TestAiBadge:
    def test_macro_renders_en_and_ru(self):
        from generate_html import _get_jinja_env

        env = _get_jinja_env()
        tmpl = env.from_string(
            '{% from "_macros.html.j2" import ai_badge %}'
            "{{ ai_badge(path_prefix='', is_ru=false) }}"
            "{{ ai_badge(path_prefix='', is_ru=true) }}"
        )
        out = tmpl.render()
        assert "nn-ai-badge" in out
        assert "ai-disclosure.html" in out
        assert "Made with AI" in out
        assert "Создано с ИИ" in out

    def test_show_page_template_wires_ai_badge(self):
        # The blog render test above proves the macro emits nn-ai-badge in real
        # output; here we guard that the show-page template imports and invokes
        # the badge, so a future edit can't silently drop it from show pages.
        src = (PROJECT_ROOT / "templates" / "show_page.html.j2").read_text(encoding="utf-8")
        assert 'import ai_badge' in src
        assert "ai_badge(" in src

    def test_blog_post_template_wires_ai_badge(self):
        src = (PROJECT_ROOT / "templates" / "blog_post.html.j2").read_text(encoding="utf-8")
        assert 'import ai_badge' in src
        assert "ai_badge(" in src
