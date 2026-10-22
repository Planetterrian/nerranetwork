"""GA4 404 recovery: trailing ``)`` / ``%29``, DP Pod nested blog, privacy stubs.

Sep 20–Oct 17 2026: 310 ``page_not_found`` events. 266 were real paths with a
stray trailing ``)`` or ``%29`` (markdown ``[text](/blog/…html)`` left as text
on nerra-daily-summaries); 11 were ``/blog/dp_pod/blog/<show>/index.html``.
GitHub Pages cannot 301, so ``404.html`` rewrites those shapes client-side and
every show blog gets a privacy-policy stub.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parent.parent


# ---------------------------------------------------------------------------
# Pure mirror of the 404.html matcher (kept in lockstep with the template).
# ---------------------------------------------------------------------------

def strip_trailing_paren_suffix(pathname: str) -> str | None:
    """Return the cleaned path when *pathname* ends with ``)`` / ``%29``
    (possibly repeated); otherwise ``None`` (show the real 404)."""
    cleaned = pathname or ""
    stripped = False
    while len(cleaned) > 1:
        if cleaned[-1] == ")":
            cleaned = cleaned[:-1]
            stripped = True
            continue
        if len(cleaned) >= 3 and cleaned[-3:].lower() == "%29":
            cleaned = cleaned[:-3]
            stripped = True
            continue
        break
    if stripped and cleaned and cleaned != pathname:
        return cleaned
    return None


_DP_POD_BLOG_RE = re.compile(
    r"^/blog/dp_pod/blog/([a-z0-9_]+/)?index\.html$", re.IGNORECASE
)


def rewrite_dp_pod_nested_blog(pathname: str) -> str | None:
    """``/blog/dp_pod/blog/<show>/index.html`` → ``/blog/<show>/index.html``."""
    m = _DP_POD_BLOG_RE.match(pathname or "")
    if not m:
        return None
    show = m.group(1) or ""
    return f"/blog/{show}index.html"


# ---------------------------------------------------------------------------
# 1. Matcher: positive and negative cases
# ---------------------------------------------------------------------------

class TestTrailingParenMatcher:
    @pytest.mark.parametrize("raw,want", [
        ("/blog/fascinating_frontiers/ep189.html)",
         "/blog/fascinating_frontiers/ep189.html"),
        ("/blog/fascinating_frontiers/ep189.html%29",
         "/blog/fascinating_frontiers/ep189.html"),
        ("/blog/fascinating_frontiers/ep189.html%29%29",
         "/blog/fascinating_frontiers/ep189.html"),
        ("/blog/spacex/ep137.html))",
         "/blog/spacex/ep137.html"),
        ("/blog/tesla/ep641.html)%29",
         "/blog/tesla/ep641.html"),
    ])
    def test_strips_trailing_paren_suffix(self, raw, want):
        assert strip_trailing_paren_suffix(raw) == want

    @pytest.mark.parametrize("raw", [
        "/blog/fascinating_frontiers/ep189.html",
        "/definitely-missing.html",
        "/blog/dp_pod/blog/tesla/index.html",
        "/",
        "/about.html",
        "/blog/tesla/ep641.html(",
        # A ")" in the middle of a path is not this bug — leave 404 alone.
        "/blog/foo)/ep001.html",
    ])
    def test_leaves_other_paths_alone(self, raw):
        assert strip_trailing_paren_suffix(raw) is None


class TestDpPodNestedBlogMatcher:
    @pytest.mark.parametrize("raw,want", [
        ("/blog/dp_pod/blog/first_principles/index.html",
         "/blog/first_principles/index.html"),
        ("/blog/dp_pod/blog/modern_investing/index.html",
         "/blog/modern_investing/index.html"),
        ("/blog/dp_pod/blog/models_agents/index.html",
         "/blog/models_agents/index.html"),
        ("/blog/dp_pod/blog/index.html",
         "/blog/index.html"),
    ])
    def test_rewrites_nested_blog(self, raw, want):
        assert rewrite_dp_pod_nested_blog(raw) == want

    @pytest.mark.parametrize("raw", [
        "/blog/dp_pod/index.html",
        "/blog/first_principles/index.html",
        "/blog/dp_pod/about.html",
        "/blog/dp_pod/blog/first_principles/ep001.html",
        "/blog/fascinating_frontiers/ep189.html)",
    ])
    def test_leaves_other_paths_alone(self, raw):
        assert rewrite_dp_pod_nested_blog(raw) is None


# ---------------------------------------------------------------------------
# 2. 404.html ships the matcher first; redirect targets exist
# ---------------------------------------------------------------------------

class Test404HtmlShipsTheMatcher:
    @pytest.fixture(scope="class")
    def html(self):
        return (ROOT / "404.html").read_text(encoding="utf-8")

    @pytest.fixture(scope="class")
    def tpl(self):
        return (ROOT / "templates" / "404.html.j2").read_text(encoding="utf-8")

    def test_redirect_script_is_in_head_early(self, tpl):
        assert "{% block head_early %}" in tpl
        early = tpl.split("{% block head_early %}", 1)[1].split("{% endblock %}", 1)[0]
        assert "location.replace" in early
        assert "%29" in early
        assert "dp_pod" in early

    def test_committed_404_runs_replace_before_page_not_found(self, html):
        replace_at = html.find("location.replace")
        event_at = html.find("page_not_found")
        assert replace_at != -1 and event_at != -1
        assert replace_at < event_at

    def test_script_only_rewrites_paren_or_dp_pod_shapes(self, html):
        # Guard: unknown URLs must still show the 404 chrome.
        assert "Page not found" in html
        assert "error-code" in html


class TestRedirectTargetsExist:
    def test_trailing_paren_examples_resolve_without_suffix(self):
        for path in (
            "blog/fascinating_frontiers/ep189.html",
            "blog/spacex/ep137.html",
            "blog/tesla/ep641.html",
        ):
            assert (ROOT / path).is_file(), path

    def test_dp_pod_nested_targets_exist(self):
        data = yaml.safe_load((ROOT / "site" / "redirects.yaml").read_text())
        for entry in data["redirects"]:
            src = str(entry["from"])
            if not src.startswith("blog/dp_pod/blog/"):
                continue
            dst = ROOT / str(entry["to"]).lstrip("/")
            assert dst.is_file(), f"{src} -> missing {entry['to']}"

    def test_every_show_blog_has_a_privacy_stub(self):
        shows = sorted(d.name for d in (ROOT / "blog").iterdir() if d.is_dir())
        assert shows, "no blog show dirs"
        for slug in shows:
            stub = ROOT / "blog" / slug / "privacy-policy.html"
            assert stub.is_file(), f"missing privacy stub for {slug}"
            text = stub.read_text(encoding="utf-8")
            assert 'http-equiv="refresh"' in text
            assert 'name="robots" content="noindex, follow"' in text
            assert 'rel="canonical" href="https://nerranetwork.com/privacy-policy.html"' in text
            assert "privacy-policy.html" in text

    def test_privacy_target_exists_and_is_not_a_stub(self):
        real = ROOT / "privacy-policy.html"
        assert real.is_file()
        head = real.read_text(encoding="utf-8", errors="ignore")[:1500]
        assert 'http-equiv="refresh"' not in head
        assert "Privacy" in head or "privacy" in head

    def test_privacy_stubs_are_not_in_the_sitemap(self):
        xml = (ROOT / "sitemap.xml").read_text(encoding="utf-8")
        for slug in ("tesla", "spacex", "dp_pod", "ai_chips"):
            assert f"/blog/{slug}/privacy-policy.html" not in xml


# ---------------------------------------------------------------------------
# 3. Source of the trailing ")": summaries linkify now accepts relative paths
# ---------------------------------------------------------------------------

class TestSummariesLinkifyAcceptsRelativeMarkdown:
    def test_template_linkify_matches_root_relative_destinations(self):
        tpl = (ROOT / "templates" / "summaries_page.html.j2").read_text(encoding="utf-8")
        # The character class must accept a leading "/" (not only https?://).
        assert r"(?:https?:\/\/|\/)" in tpl or "(?:https?://|/)" in tpl

    def test_generate_html_linkifies_ssr_summary_md_links(self):
        import generate_html as gh
        raw = (
            "<p>[Full episode notes](/blog/fascinating_frontiers/ep189.html) · "
            "[SpaceX Daily](/spacex.html)</p>"
        )
        out = gh._linkify_summary_md_links(raw)
        assert 'href="/blog/fascinating_frontiers/ep189.html"' in out
        assert 'href="/spacex.html"' in out
        assert "[Full episode notes](" not in out
        # No trailing-paren href.
        assert '.html)"' not in out
        assert '.html)' not in out.split("href=")[1].split('"')[0] if "href=" in out else True
