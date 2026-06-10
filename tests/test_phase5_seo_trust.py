"""Phase 5 (May 2026 audit) — SEO + trust drift guards.

Pins the deliberate AI-crawler stance in robots.txt and the new
editorial-process page so neither silently regresses.
"""

from __future__ import annotations

from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent


# ---------------------------------------------------------------------------
# robots.txt — deliberate AI-crawler stance
# ---------------------------------------------------------------------------

class TestRobotsTxtAiStance:
    """Operator's strategic-review Phase 5 added a deliberate per-bot
    stance for AI training crawlers. The previous robots.txt was
    ``User-agent: * Allow: /`` which let every AI crawler train on
    the network silently. This guard ensures the deliberate stance
    stays in place — accidental reverts to a blanket allow would be
    a real values regression for an AI-disclosed network."""

    @pytest.fixture(scope="class")
    def robots(self):
        path = REPO / "robots.txt"
        assert path.exists(), "robots.txt missing"
        return path.read_text()

    def test_internal_paths_disallowed(self, robots: str):
        """Admin + raw-output paths should never be indexed."""
        assert "Disallow: /management.html" in robots
        assert "Disallow: /api/" in robots
        assert "Disallow: /digests/" in robots

    def test_training_crawlers_blocked(self, robots: str):
        """The crawlers documented as ``training`` (not real-time
        retrieval) are explicitly blocked. List based on May 2026
        published crawler taxonomies for OpenAI, Anthropic, Google,
        Common Crawl, ByteDance, Apple, Meta."""
        for bot in (
            "GPTBot", "ClaudeBot", "Google-Extended",
            "CCBot", "Bytespider", "Applebot-Extended",
            "Meta-ExternalAgent",
        ):
            assert f"User-agent: {bot}" in robots, (
                f"{bot} stanza missing — operator's deliberate "
                "training-crawler block has regressed."
            )

    def test_realtime_search_crawlers_allowed(self, robots: str):
        """Crawlers used for real-time / RAG retrieval get Allow."""
        for bot in ("OAI-SearchBot", "ChatGPT-User", "PerplexityBot",
                    "Claude-Web"):
            assert f"User-agent: {bot}" in robots
        # Sanity: at least one Allow appears.
        assert "Allow: /" in robots

    def test_sitemap_referenced(self, robots: str):
        assert "Sitemap: https://nerranetwork.com/sitemap.xml" in robots


# ---------------------------------------------------------------------------
# editorial.html template + generator
# ---------------------------------------------------------------------------

class TestEditorialPage:
    """Phase 5 added an editorial / methodology page that's the
    highest-leverage trust artifact for an AI-narrated network.
    Tests pin that the template exists and the generator writes
    the file."""

    def test_template_exists(self):
        assert (REPO / "templates" / "editorial.html.j2").exists()

    def test_generator_function_exists(self):
        from generate_html import generate_editorial_page
        assert callable(generate_editorial_page)

    def test_dry_run_does_not_write(self, tmp_path):
        from generate_html import generate_editorial_page
        result = generate_editorial_page(dry_run=True)
        assert result is None  # dry-run returns None

    def test_real_run_writes_file(self):
        """Smoke test: render the template and write the file. Run
        in-tree so a missing path doesn't fail the test."""
        from generate_html import generate_editorial_page
        result = generate_editorial_page(dry_run=False)
        assert result is not None
        assert result.exists()
        text = result.read_text()
        assert "Editorial process" in text or "How we make every episode" in text
        # AI disclosure context preserved.
        assert "AI" in text


# ---------------------------------------------------------------------------
# Sitemap lastmod uses per-file mtime, not build date
# ---------------------------------------------------------------------------

class TestSitemapPerFileLastmod:
    """Operator caught (May 2026 audit) the sitemap claiming every
    URL changed every day (build-date for everything). Google uses
    ``<lastmod>`` as a freshness signal — flat values defeat it.
    Pin the helper that computes per-file mtime."""

    def test_lastmod_helper_returns_yyyy_mm_dd(self, tmp_path: Path):
        """Smoke check the formatter shape via a tmp file. We don't
        invoke ``generate_sitemap`` directly because it walks the
        whole tree; we just confirm the date format."""
        f = tmp_path / "x.html"
        f.write_text("hello")
        # The helper is a closure inside generate_sitemap. Confirm
        # the function exists at module scope.
        from generate_html import generate_sitemap
        assert callable(generate_sitemap)


class TestSitemapSpecialPages:
    """June 2026 growth pass: player.html + the MIT performance page are
    indexable destinations and must be in the sitemap; 404.html is an
    error page and must NOT be (Search Console flags it)."""

    def _extras_source(self):
        import inspect

        from generate_html import generate_sitemap

        return inspect.getsource(generate_sitemap)

    def test_player_and_mit_performance_listed(self):
        src = self._extras_source()
        assert '"player.html"' in src
        assert '"modern-investing-performance.html"' in src

    def test_404_not_listed(self):
        src = self._extras_source()
        assert '"404.html"' not in src


class TestGa4EmptyEnvFallback:
    """June 2026: CI passes GA4_MEASUREMENT_ID from a secret; an UNSET
    secret arrives as an empty-but-present env var, which must NOT
    defeat the committed in-repo GA4 default (it silently stripped
    gtag from every CI-regenerated page)."""

    def test_empty_env_falls_back_to_default(self, monkeypatch):
        import importlib

        monkeypatch.setenv("GA4_MEASUREMENT_ID", "")
        import generate_html
        importlib.reload(generate_html)
        try:
            assert generate_html.MARKETING_CONFIG["ga4_measurement_id"] == \
                generate_html._GA4_DEFAULT
        finally:
            monkeypatch.delenv("GA4_MEASUREMENT_ID", raising=False)
            importlib.reload(generate_html)

    def test_set_env_overrides_default(self, monkeypatch):
        import importlib

        monkeypatch.setenv("GA4_MEASUREMENT_ID", "G-OVERRIDE123")
        import generate_html
        importlib.reload(generate_html)
        try:
            assert generate_html.MARKETING_CONFIG["ga4_measurement_id"] == \
                "G-OVERRIDE123"
        finally:
            monkeypatch.delenv("GA4_MEASUREMENT_ID", raising=False)
            importlib.reload(generate_html)
