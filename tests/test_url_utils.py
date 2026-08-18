"""Tests for url_utils — URL sanitization + Google News redirect resolution."""

from __future__ import annotations

import pytest
from unittest.mock import MagicMock

from engine.url_utils import (
    is_google_news_url,
    resolve_google_news_url,
    sanitize_url,
    shorten_for_email,
)


# ---------------------------------------------------------------------------
# sanitize_url
# ---------------------------------------------------------------------------

class TestSanitizeUrl:

    def test_clean_url_passes_through(self):
        url = "https://example.com/article?id=42"
        assert sanitize_url(url) == url

    def test_strips_dc4_control_character(self):
        # The DC4 byte (`\x14`) leaked through Omni View's RSS
        # scrape on May 2, producing `?ito\x14...` literals in
        # href attributes.
        url = "https://www.dailymail.co.uk/article/123?ito\x14490"
        out = sanitize_url(url)
        assert "\x14" not in out
        assert out.startswith("https://www.dailymail.co.uk")

    def test_drops_url_with_no_scheme(self):
        assert sanitize_url("not-a-url") is None

    def test_drops_ftp_scheme(self):
        # We only ship http/https. ftp:// would render as a dead link
        # in 99% of email clients.
        assert sanitize_url("ftp://example.com") is None

    def test_drops_empty_input(self):
        assert sanitize_url("") is None
        assert sanitize_url(None) is None
        assert sanitize_url("   ") is None

    def test_drops_url_with_internal_whitespace(self):
        # Concatenation downstream sometimes produces "https://a.com /more"
        # — clearly broken, drop it.
        assert sanitize_url("https://example.com /article") is None

    def test_idempotent_for_clean_input(self):
        url = "https://example.com/foo?bar=baz"
        assert sanitize_url(sanitize_url(url)) == url


# ---------------------------------------------------------------------------
# is_google_news_url
# ---------------------------------------------------------------------------

class TestIsGoogleNewsUrl:

    def test_recognises_rss_articles_path(self):
        url = "https://news.google.com/rss/articles/CBMi..."
        assert is_google_news_url(url) is True

    def test_recognises_articles_path(self):
        assert is_google_news_url("https://news.google.com/articles/abc") is True

    def test_recognises_country_subdomain(self):
        assert is_google_news_url("https://news.google.ca/articles/abc") is True

    def test_publisher_url_is_not_a_google_redirect(self):
        url = "https://www.bbc.com/news/world-12345"
        assert is_google_news_url(url) is False

    def test_empty_input(self):
        assert is_google_news_url("") is False
        assert is_google_news_url(None) is False  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# resolve_google_news_url
# ---------------------------------------------------------------------------

class TestResolveGoogleNewsUrl:

    @pytest.fixture(autouse=True)
    def _clear_resolve_cache(self):
        """Resolution is memoised per process (two round-trips per URL).

        Without this, a test that stubs a successful resolve leaves the
        answer in the cache and the next test gets it back instead of
        exercising its own stub.
        """
        from engine import url_utils as _u

        _u._GN_RESOLVE_CACHE.clear()
        yield
        _u._GN_RESOLVE_CACHE.clear()

    def test_non_google_url_returns_unchanged(self):
        url = "https://www.bbc.com/news/world-12345"
        assert resolve_google_news_url(url) == url

    def test_resolves_to_canonical(self, monkeypatch):
        canonical = "https://www.bbc.com/news/world-canada-12345"

        class _FakeResp:
            url = canonical
        monkeypatch.setattr(
            "engine.url_utils.requests.head",
            lambda *a, **kw: _FakeResp(),
        )
        out = resolve_google_news_url(
            "https://news.google.com/rss/articles/CBMi..."
        )
        assert out == canonical

    def test_returns_input_on_network_error(self, monkeypatch):
        from engine import url_utils as _u
        import requests as _req

        def _raise(*a, **kw):
            raise _req.ConnectionError("nope")
        monkeypatch.setattr(_u.requests, "head", _raise)
        monkeypatch.setattr(_u.requests, "get", _raise)
        original = "https://news.google.com/rss/articles/CBMi..."
        assert resolve_google_news_url(original) == original


# ---------------------------------------------------------------------------
# shorten_for_email
# ---------------------------------------------------------------------------

class TestShortenForEmail:

    def test_short_url_passes_through(self):
        url = "https://example.com/foo"
        assert shorten_for_email(url) == url

    def test_strips_utm_params(self):
        url = (
            "https://example.com/foo?id=42&utm_source=newsletter"
            "&utm_medium=email&utm_campaign=may2"
        )
        out = shorten_for_email(url, max_len=10)
        assert "utm_source" not in out
        assert "id=42" in out  # unrelated params kept

    def test_keeps_long_url_when_no_noise_to_strip(self):
        # If we can't shorten further, return as-is rather than mangle.
        url = "https://example.com/" + "x" * 300
        out = shorten_for_email(url, max_len=100)
        assert out == url


# ---------------------------------------------------------------------------
# repair_aggregator_urls — Aug 18 2026
#
# The fetcher resolves aggregated items before the prompt sees them, but the
# model writes its own Sources section and retypes long URLs into it.
# Offshore North Ep001 shipped two 468-character Google News ids that each
# differed from the real link by a single character, so both were dead.
# ---------------------------------------------------------------------------

class TestRepairAggregatorUrls:

    AGG = "https://news.google.com/rss/articles/CBMi" + "Ab3Xy" * 80 + "?oc=5"
    PUB = "https://voilesetvoiliers.ouest-france.fr/course-au-large/article"

    def _articles(self):
        return [{
            "url": self.PUB,
            "aggregator_url": self.AGG,
            "source_name": "Voiles et Voiliers",
        }]

    def test_exact_url_is_replaced(self):
        from engine.url_utils import repair_aggregator_urls

        out, count = repair_aggregator_urls(f"see {self.AGG} ok", self._articles())
        assert count == 1 and self.PUB in out and "news.google.com" not in out

    def test_retyped_url_is_matched_by_id_prefix(self):
        from engine.url_utils import repair_aggregator_urls

        retyped = self.AGG[:300] + ("Z" if self.AGG[300] != "Z" else "Q") + self.AGG[301:]
        assert retyped != self.AGG
        out, count = repair_aggregator_urls(retyped, self._articles())
        assert count == 1 and out == self.PUB

    def test_trailing_punctuation_is_not_swallowed(self):
        from engine.url_utils import repair_aggregator_urls

        out, _ = repair_aggregator_urls(f"({self.AGG}).", self._articles())
        assert out == f"({self.PUB})."

    def test_unknown_aggregator_url_is_left_alone(self):
        from engine.url_utils import repair_aggregator_urls

        stray = "https://news.google.com/rss/articles/CBMi" + "Qq9Wz" * 80
        out, count = repair_aggregator_urls(stray, self._articles())
        assert count == 0 and out == stray

    def test_noop_without_input(self):
        from engine.url_utils import repair_aggregator_urls

        assert repair_aggregator_urls("", self._articles()) == ("", 0)
        assert repair_aggregator_urls("text", []) == ("text", 0)

    def test_relabel_still_names_the_publisher_after_repair(self):
        from engine.url_utils import relabel_aggregator_links, repair_aggregator_urls

        text = f"Source: [Google News]({self.AGG})"
        text, _ = repair_aggregator_urls(text, self._articles())
        text, renamed = relabel_aggregator_links(text, self._articles())
        assert renamed == 1, (
            "relabel keyed on the href still being a Google URL — the repair "
            "would otherwise silently stop it naming the publisher."
        )
        assert text == f"Source: [Voiles et Voiliers]({self.PUB})"

    def test_relabel_leaves_an_already_specific_label(self):
        from engine.url_utils import relabel_aggregator_links

        text = f"Source: [Ouest-France]({self.PUB})"
        out, renamed = relabel_aggregator_links(text, self._articles())
        assert renamed == 0 and out == text


class TestGoogleNewsRpcFallback:
    """The modern opaque ids only resolve through Google's own RPC."""

    def test_rpc_is_tried_when_redirects_stay_on_google(self, monkeypatch):
        from engine import url_utils as _u

        _u._GN_RESOLVE_CACHE.clear()
        url = "https://news.google.com/rss/articles/CBMi" + "Kk4Pn" * 80
        page = 'x data-n-a-sg="SIG123" data-n-a-ts="1787063843" x'
        canonical = "https://example.org/the-real-article"

        class _Resp:
            def __init__(self, text="", u=url):
                self.text = text
                self.url = u

            def __enter__(self):
                return self

            def __exit__(self, *a):
                return False

        posted = {}

        def _get(u, **kw):
            return _Resp(page, url)

        def _post(u, **kw):
            posted["url"] = u
            posted["data"] = kw.get("data", "")
            return _Resp(
                ')]}\'\n\n[["wrb.fr","Fbv4je","[\\"garturlres\\",\\"'
                + canonical + '\\",1]",null,null,null,"generic"]]'
            )

        monkeypatch.setattr(_u.requests, "head", lambda *a, **kw: _Resp("", url))
        monkeypatch.setattr(_u.requests, "get", _get)
        monkeypatch.setattr(_u.requests, "post", _post)

        assert _u.resolve_google_news_url(url) == canonical
        assert "batchexecute" in posted["url"]
        assert "Fbv4je" in posted["data"] and "SIG123" in posted["data"]
        _u._GN_RESOLVE_CACHE.clear()

    def test_missing_signature_pair_gives_up_quietly(self, monkeypatch):
        from engine import url_utils as _u

        _u._GN_RESOLVE_CACHE.clear()
        url = "https://news.google.com/rss/articles/CBMi" + "Rr5Tm" * 80

        class _Resp:
            text = "<html>no signature here</html>"

            def __init__(self):
                self.url = url

            def __enter__(self):
                return self

            def __exit__(self, *a):
                return False

        def _post(*a, **kw):
            raise AssertionError("must not call the RPC without a signature")

        monkeypatch.setattr(_u.requests, "head", lambda *a, **kw: _Resp())
        monkeypatch.setattr(_u.requests, "get", lambda *a, **kw: _Resp())
        monkeypatch.setattr(_u.requests, "post", _post)

        assert _u.resolve_google_news_url(url) == url
        _u._GN_RESOLVE_CACHE.clear()
