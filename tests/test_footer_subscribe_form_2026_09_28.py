"""Regression guards for the sitewide footer newsletter signup form.

2026-09-27 audit: ``templates/base.html.j2`` rendered
``onsubmit="…btn.textContent={{ t.subscribe_button_loading | tojson }};…"``.
Jinja ``tojson`` emits double-quoted JSON strings, which end a double-quoted
HTML attribute early. The live form's ``onsubmit`` truncated mid-statement,
submit fell through to a GET of the current page, and the visitor's email
landed in the URL (also invisible to ``/api/subscribe``).

The fix moves the handler into ``assets/js/footer-subscribe.js`` and binds
via ``data-nn-subscribe`` + ``method="post"``. These tests render a fresh
page (never a committed HTML file) and parse the form with an HTML parser
so a reintroduced inline ``| tojson`` inside ``onsubmit`` fails CI.
"""

from __future__ import annotations

import re
import sys
from html.parser import HTMLParser
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


def _render_page_with_footer(tmp_path) -> str:
    """Render a cheap page that extends base.html.j2 (fresh chrome)."""
    import generate_html as G
    out = G.generate_explore_page(output_dir=str(tmp_path))
    assert out is not None
    return Path(out).read_text(encoding="utf-8")


class _FooterSubscribeForm(HTMLParser):
    """Collect the footer ``.nn-subscribe-form`` start-tag attributes."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.form_attrs: dict[str, str | None] | None = None
        self._in_footer_subscribe = False
        self._depth = 0

    def handle_starttag(self, tag, attrs):
        d = dict(attrs)
        classes = (d.get("class") or "").split()
        if "nn-footer-subscribe" in classes:
            self._in_footer_subscribe = True
            self._depth = 0
        if self._in_footer_subscribe:
            if tag not in ("img", "br", "source", "input", "meta", "hr"):
                self._depth += 1
            if (
                tag == "form"
                and self.form_attrs is None
                and (
                    "nn-subscribe-form" in classes
                    or d.get("data-nn-subscribe") == "footer"
                )
            ):
                self.form_attrs = d

    def handle_endtag(self, tag):
        if not self._in_footer_subscribe:
            return
        if tag not in ("img", "br", "source", "input", "meta", "hr"):
            self._depth -= 1
        if self._depth <= 0:
            self._in_footer_subscribe = False
            self._depth = 0


class TestFooterSubscribeFormMarkup:
    def test_rendered_form_attributes_are_well_formed(self, tmp_path):
        html = _render_page_with_footer(tmp_path)
        parser = _FooterSubscribeForm()
        parser.feed(html)
        assert parser.form_attrs is not None, "footer subscribe form missing"

        attrs = parser.form_attrs
        # Allowed keys for a healthy form. Anything else is the quote-break
        # signature (truncated onsubmit turning the rest of the tag into junk
        # attributes like ``subscribing…";var``).
        allowed = {
            "class", "method", "action", "style", "id",
            "data-nn-subscribe", "data-nn-subscribe-bound",
            "data-source", "data-require-tags", "data-success-redirect",
            "data-label-loading", "data-label-done", "data-label-idle",
            "data-label-error", "data-label-need-tags",
        }
        unexpected = sorted(k for k in attrs if k and k not in allowed)
        assert unexpected == [], (
            f"broken onsubmit leaked into attributes: {unexpected}"
        )

        assert attrs.get("method", "").lower() == "post", (
            "method=post required so a no-JS submit cannot put email in the URL"
        )
        assert attrs.get("data-nn-subscribe") == "footer"
        assert attrs.get("data-source", "").startswith("src-"), (
            "Worker source tag missing or malformed"
        )
        assert attrs.get("data-label-loading")
        assert attrs.get("data-label-done")
        assert attrs.get("data-label-error")
        # Inline handler must be gone — the shared script owns submit.
        assert "onsubmit" not in attrs

    def test_page_loads_footer_subscribe_script(self, tmp_path):
        html = _render_page_with_footer(tmp_path)
        assert "assets/js/footer-subscribe.js" in html

    def test_template_does_not_embed_tojson_inside_onsubmit(self):
        """Source-level pin: the exact failure mode that shipped for months."""
        base = (ROOT / "templates" / "base.html.j2").read_text(encoding="utf-8")
        # Strip Jinja comments first — a comment describing the bug contains
        # the literal ``onsubmit=`` string (chrome-pass lesson, Sep 21).
        scrubbed = re.sub(r"\{#.*?#\}", "", base, flags=re.S)
        footer = scrubbed.split("nn-footer-subscribe", 1)[1].split(
            "nn-footer-bottom", 1
        )[0]
        assert "onsubmit=" not in footer
        assert "tojson" not in footer
        assert 'data-nn-subscribe="footer"' in footer
        assert 'method="post"' in footer

    def test_shared_script_posts_member_list_to_worker(self):
        src = (ROOT / "assets" / "js" / "footer-subscribe.js").read_text(
            encoding="utf-8"
        )
        assert "api.nerranetwork.com/api/subscribe" in src
        assert "list: 'member'" in src or 'list: "member"' in src
        assert "preventDefault" in src
        assert "JSON.stringify" in src
