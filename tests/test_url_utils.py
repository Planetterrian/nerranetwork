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
