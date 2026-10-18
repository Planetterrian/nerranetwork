"""Homepage XSS hardening + non-blocking fonts (Oct 18 2026 review PR 2).

Digest hooks, correction text and other feed-derived strings on the news
front page used to render raw under ``autoescape=False``. An injected
``<script>`` / ``<img onerror>`` in a headline must escape; normal punctuation
must not double-escape. Google Fonts leave the critical path via
``media=print`` + ``onload`` swap (``display=swap`` kept).
"""

from __future__ import annotations

import datetime as dt
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import generate_html as G  # noqa: E402
from engine import landing_test as LT  # noqa: E402
from engine import newsroom as N  # noqa: E402

UTC = dt.timezone.utc
NOW = dt.datetime(2026, 10, 17, 13, 30, tzinfo=UTC)

XSS_HOOK = '<img src=x onerror=alert(1)> & "q"'
XSS_ESCAPED = "&lt;img src=x onerror=alert(1)&gt; &amp; &#34;q&#34;"
NORMAL_HOOK = "Tesla's Model Y – refresh"


def _poison_lead(page: dict, hook: str) -> dict:
    lead = page.get("lead")
    if lead is None:
        pytest.skip("no lead story at the fixed clock — cannot inject a fixture hook")
    lead["hook"] = hook
    lead["ticker_text"] = hook
    for bucket in ("top", "latest", "more"):
        for story in page.get(bucket) or []:
            story["hook"] = hook
            story["ticker_text"] = hook
    for flag in page.get("flagships") or []:
        flag["hook"] = hook
    for sec in page.get("sections") or []:
        for story in sec.get("stories") or []:
            story["hook"] = hook
    return page


def _render_poisoned(tmp_path, monkeypatch, *, hook: str, correction_text: str) -> str:
    real_assemble = LT.assemble

    def assemble_with_fixture(*args, **kwargs):
        return _poison_lead(real_assemble(*args, **kwargs), hook)

    monkeypatch.setattr(LT, "assemble", assemble_with_fixture)
    monkeypatch.setattr(
        N,
        "recent_corrections",
        lambda *_a, **_k: [{
            "date": "2026-10-17",
            "date_label": "Oct 17",
            "episode": 999,
            "text": correction_text,
            "show_name": "Tesla Shorts Time",
            "show_page": "tesla.html",
            "post_url": "tesla.html",
            "slug": "tesla",
        }],
    )
    out = G.generate_network_page(output_dir=tmp_path, now=NOW)
    return out.read_text(encoding="utf-8")


class TestHomepageEscape:
    def test_injected_img_onerror_in_hook_and_correction_is_escaped(
            self, tmp_path, monkeypatch):
        html = _render_poisoned(
            tmp_path, monkeypatch, hook=XSS_HOOK, correction_text=XSS_HOOK)
        assert XSS_ESCAPED in html
        # No live HTML tag — ``|tojson`` may still hold the payload as a
        # JSON string (``\u003cimg…``), which the review leaves alone.
        assert "<img src=x" not in html
        assert not re.search(r"<img\b[^>]*\bonerror\s*=", html, re.I)
        assert "Correction to episode 999" in html
        # Hook + correction body are the same payload, escaped once each.
        assert html.count(XSS_ESCAPED) >= 2

    def test_normal_hook_with_ampersand_quotes_and_dash_is_not_double_escaped(
            self, tmp_path, monkeypatch):
        html = _render_poisoned(
            tmp_path, monkeypatch, hook=NORMAL_HOOK, correction_text=NORMAL_HOOK)
        assert "&amp;amp;" not in html
        assert "–" in html
        # Apostrophe may stay literal or become &#39;; never double-escaped.
        assert "Tesla" in html
        assert "&#39;&#39;" not in html
        assert NORMAL_HOOK in html or "Tesla&#39;s Model Y – refresh" in html


class TestNonBlockingFonts:
    def test_base_loads_google_fonts_without_blocking_render(self):
        src = (ROOT / "templates" / "base.html.j2").read_text(encoding="utf-8")
        assert 'rel="preconnect" href="https://fonts.googleapis.com"' in src
        assert 'rel="preconnect" href="https://fonts.gstatic.com" crossorigin' in src
        assert 'rel="preconnect" href="https://www.googletagmanager.com"' in src
        assert "display=swap" in src
        fonts_block = src.split("Google Fonts", 1)[1].split("Favicon", 1)[0]
        assert "<noscript>" in fonts_block and "fonts.googleapis.com/css2?" in fonts_block
        assert 'media="print" onload="this.media=\'all\'"' in fonts_block
        assert 'rel="stylesheet" href="https://fonts.googleapis.com' in fonts_block

    def test_digest_fields_use_escape_filter(self):
        """Drift guard: every digest-/feed-derived field the review named."""
        src = (ROOT / "templates" / "network_page.html.j2").read_text(encoding="utf-8")
        for needle in (
            "s.hook | e",
            "f.hook | e",
            "e.hook | e",
            "c.hook | e",
            "s.ticker_text | e",
            "l.headline | e",
            "e.headline | e",
            "c.text | e",
            "ep.title | e",
            "v.display_title | e",
            "sp.title | e",
            "(sp.teaser or sp.summary) | e",
            "r.label | e",
            "r.detail | e",
            "b.title | e",
            "b.full_title | e",
            "b.subtitle | e",
            "st.label | e",
        ):
            assert needle in src, needle
        # Share / JSON-LD paths stay on their own filters.
        assert "s.hook | urlencode" in src
        assert "org_ld | tojson" in src
