"""Privacy policy discloses Soft Personal enhanced-conversion hashing.

Oct 16 2026: section 3 (Google Analytics and Google Ads measurement)
must state that a consenting Personal tips submit may send Google a
SHA-256 hash of the email — never the plaintext — and link Google's
privacy policy. Last-updated date moves with the material change.
"""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

_NEW_SNIPPET = (
    "If you accept cookies and then enter your email in a Personal tips "
    "form, your browser sends Google a SHA-256 hash of your email address"
)
_OLD_SNIPPET = (
    "If we ever run ads, Google Ads conversion tracking would count "
    "anonymous newsletter signups from those ads."
)
_GOOGLE_PRIVACY_HREF = 'href="https://policies.google.com/privacy"'


def _read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


class TestPrivacyEnhancedConversionsDisclosure:
    def test_template_has_approved_disclosure(self):
        src = _read("templates/privacy_policy.html.j2")
        assert _NEW_SNIPPET in src
        assert "Google calls this enhanced conversions" in src
        assert "If you don't allow Ad measurement, your email hash is never sent." in src
        assert "we never sell your email" in src
        assert _GOOGLE_PRIVACY_HREF in src
        assert _OLD_SNIPPET not in src

    def test_committed_html_matches_template_disclosure(self):
        html = _read("privacy-policy.html")
        assert _NEW_SNIPPET in html
        assert "Google calls this enhanced conversions" in html
        assert _GOOGLE_PRIVACY_HREF in html
        assert 'target="_blank"' in html[html.index(_GOOGLE_PRIVACY_HREF):html.index(_GOOGLE_PRIVACY_HREF) + 200]
        assert _OLD_SNIPPET not in html

    def test_last_updated_is_october_16_2026(self):
        html = _read("privacy-policy.html")
        assert "Last updated October 16, 2026" in html
        assert "Last reviewed October 16, 2026" in html
        # Generator label is the source for {{ updated_label }} on regen.
        gen = _read("generate_html.py")
        assert 'LEGAL_PAGES_UPDATED_LABEL = "October 16, 2026"' in gen
