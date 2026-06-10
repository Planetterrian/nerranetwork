"""Drift guards for the June 10 2026 website review
(docs/website_review_2026_06_10.md)."""

from __future__ import annotations

import re
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent


def test_og_image_default_is_absolute():
    base = (_ROOT / "templates" / "base.html.j2").read_text(encoding="utf-8")
    assert "default('https://nerranetwork.com/assets/og-preview.png'" in base
    # The relative default must never come back — social platforms
    # require absolute og:image URLs.
    assert "default(path_prefix ~ 'assets/og-preview.png'" not in base


def test_404_is_noindex():
    tpl = (_ROOT / "templates" / "404.html.j2").read_text(encoding="utf-8")
    assert re.search(r'<meta name="robots" content="noindex">', tpl)


def test_footer_links_gallery():
    base = (_ROOT / "templates" / "base.html.j2").read_text(encoding="utf-8")
    assert "gallery.html" in base


def test_social_proof_threshold():
    import sys
    sys.path.insert(0, str(_ROOT))
    import generate_html
    assert generate_html.MIN_SOCIAL_PROOF_SUBSCRIBERS == 50
