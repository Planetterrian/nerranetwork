"""Google Ads tag ID is AW-949617778; customer ID AW-7411462618 never ships.

Oct 17 2026: the live site had been configured with AW-7411462618, which is
the Ads *customer* ID, not a tag ID. The real Google tag is AW-949617778.
Conversions are imported from GA4 key events, so Ads ``send_to`` conversion
labels are not used on the site.
"""
from __future__ import annotations

import importlib
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]

ADS_TAG = "AW-949617778"
ADS_CUSTOMER_WRONG = "AW-7411462618"

# Surfaces we own and may assert on. Generated blog/rss/digests/engine are
# out of scope for this guard (operator: leave unchanged if they appear).
_SCAN_GLOBS = (
    "assets/js/*.js",
    "templates/**/*.j2",
    "generate_html.py",
    "tests/test_google_ads_tag_id_2026_10_17.py",
    "README.md",
    "docs/env_var_inventory.md",
    ".github/workflows/nightly-maintenance.yml",
    ".github/workflows/run-show.yml",
)


def _read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def _iter_scanned_files():
    seen = set()
    for pattern in _SCAN_GLOBS:
        for path in ROOT.glob(pattern):
            if path.is_file() and path not in seen:
                seen.add(path)
                yield path


class TestAdsTagDefault:
    def test_default_is_real_tag_id(self, monkeypatch):
        monkeypatch.delenv("GOOGLE_ADS_ID", raising=False)
        import generate_html

        importlib.reload(generate_html)
        try:
            assert generate_html._ADS_DEFAULT == ADS_TAG
            assert generate_html.MARKETING_CONFIG["google_ads_id"] == ADS_TAG
            assert generate_html.MARKETING_CONFIG["google_ads_signup_label"] == ""
        finally:
            importlib.reload(generate_html)

    def test_empty_env_falls_back_to_tag(self, monkeypatch):
        monkeypatch.setenv("GOOGLE_ADS_ID", "")
        import generate_html

        importlib.reload(generate_html)
        try:
            assert generate_html.MARKETING_CONFIG["google_ads_id"] == ADS_TAG
        finally:
            monkeypatch.delenv("GOOGLE_ADS_ID", raising=False)
            importlib.reload(generate_html)

    def test_customer_id_secret_is_rejected(self, monkeypatch):
        """A secret still holding the customer ID must not reach the page.

        run-show.yml / nightly-maintenance.yml still pass
        ``GOOGLE_ADS_ID: ${{ secrets.GOOGLE_ADS_ID }}`` unchanged. If that
        secret is the customer ID ``AW-7411462618``, this guard must fall
        back to the real tag ``AW-949617778``.
        """
        monkeypatch.setenv("GOOGLE_ADS_ID", ADS_CUSTOMER_WRONG)
        import generate_html

        importlib.reload(generate_html)
        try:
            assert generate_html._resolve_google_ads_id() == ADS_TAG
            assert generate_html.MARKETING_CONFIG["google_ads_id"] == ADS_TAG
            assert ADS_CUSTOMER_WRONG not in generate_html.MARKETING_CONFIG["google_ads_id"]
            assert ADS_CUSTOMER_WRONG in generate_html._ADS_REJECTED_IDS
        finally:
            monkeypatch.delenv("GOOGLE_ADS_ID", raising=False)
            importlib.reload(generate_html)

    def test_pipeline_env_pair_cannot_emit_wrong_tag_or_label(self, monkeypatch):
        """Exact env pair the pipeline workflows still inject."""
        monkeypatch.setenv("GOOGLE_ADS_ID", ADS_CUSTOMER_WRONG)
        monkeypatch.setenv("GOOGLE_ADS_SIGNUP_LABEL", "AbCdEfGhIjKlMnOp")
        import generate_html

        importlib.reload(generate_html)
        try:
            assert generate_html.MARKETING_CONFIG["google_ads_id"] == ADS_TAG
            assert generate_html.MARKETING_CONFIG["google_ads_signup_label"] == ""
        finally:
            monkeypatch.delenv("GOOGLE_ADS_ID", raising=False)
            monkeypatch.delenv("GOOGLE_ADS_SIGNUP_LABEL", raising=False)
            importlib.reload(generate_html)

    def test_valid_override_still_works(self, monkeypatch):
        monkeypatch.setenv("GOOGLE_ADS_ID", "AW-111222333")
        import generate_html

        importlib.reload(generate_html)
        try:
            assert generate_html.MARKETING_CONFIG["google_ads_id"] == "AW-111222333"
        finally:
            monkeypatch.delenv("GOOGLE_ADS_ID", raising=False)
            importlib.reload(generate_html)


class TestNoSendToConversionLabels:
    def test_tracking_js_has_no_send_to(self):
        js = _read("assets/js/tracking.js")
        # No live conversion payload — comments may mention send_to.
        assert "send_to:" not in js
        assert "send_to :" not in js
        assert "_GOOGLE_ADS_SIGNUP_TARGET" not in js
        assert re.search(r"track\(\s*['\"]conversion['\"]", js) is None

    def test_consent_js_does_not_build_signup_target(self):
        js = _read("assets/js/consent.js")
        assert "_GOOGLE_ADS_SIGNUP_TARGET" not in js
        assert "ads-signup-label" not in js
        assert "adsLabel:" not in js or "BANNER_COPY" in js  # banner copy key only
        assert "data-nn-ads-signup-label" not in js
        # Config for the Ads tag remains (consent-gated); personalization off.
        assert "gtag('config', ids.ads" in js
        assert "allow_ad_personalization_signals: false" in js
        assert "ids.ads + '/' +" not in js and "ids.ads+'/'+" not in js

    def test_template_has_no_signup_label_attr(self):
        base = _read("templates/base.html.j2")
        assert "data-nn-ads-id=" in base
        assert "data-nn-ads-signup-label" not in base

    def test_signup_label_env_ignored(self, monkeypatch):
        monkeypatch.setenv("GOOGLE_ADS_SIGNUP_LABEL", "AbCdEfGhIjKlMnOp")
        import generate_html

        importlib.reload(generate_html)
        try:
            assert generate_html.MARKETING_CONFIG["google_ads_signup_label"] == ""
        finally:
            monkeypatch.delenv("GOOGLE_ADS_SIGNUP_LABEL", raising=False)
            importlib.reload(generate_html)

    def test_pipeline_workflows_still_pass_ads_env_unchanged(self):
        """Patrick's pipelines are off-limits — still pass both secrets.

        generate_html must tolerate whatever they inject (see
        test_pipeline_env_pair_cannot_emit_wrong_tag_or_label).
        """
        for rel in (
            ".github/workflows/nightly-maintenance.yml",
            ".github/workflows/run-show.yml",
        ):
            src = _read(rel)
            assert "GOOGLE_ADS_ID: ${{ secrets.GOOGLE_ADS_ID }}" in src
            assert "GOOGLE_ADS_SIGNUP_LABEL: ${{ secrets.GOOGLE_ADS_SIGNUP_LABEL }}" in src


class TestWrongIdAbsentEverywhereScanned:
    def test_customer_id_absent_as_live_tag(self):
        """Wrong ID may appear in docs/tests that name it as rejected; never
        as a data-nn-ads-id value or gtag config argument."""
        live_patterns = (
            re.compile(rf'data-nn-ads-id=["\']?{re.escape(ADS_CUSTOMER_WRONG)}'),
            re.compile(rf"gtag\(\s*['\"]config['\"]\s*,\s*['\"]{re.escape(ADS_CUSTOMER_WRONG)}['\"]"),
            re.compile(rf"_ADS_DEFAULT\s*=\s*[\"']{re.escape(ADS_CUSTOMER_WRONG)}[\"']"),
        )
        hits = []
        for path in _iter_scanned_files():
            text = path.read_text(encoding="utf-8", errors="replace")
            for pat in live_patterns:
                for m in pat.finditer(text):
                    line_no = text.count("\n", 0, m.start()) + 1
                    hits.append(f"{path.relative_to(ROOT)}:{line_no}:{m.group(0)}")
        # Also scan regenerated root HTML we own (not blog/).
        for path in ROOT.glob("*.html"):
            text = path.read_text(encoding="utf-8", errors="replace")
            if ADS_CUSTOMER_WRONG in text:
                hits.append(f"{path.name}: contains {ADS_CUSTOMER_WRONG}")
        assert hits == [], "wrong customer ID must not appear as a live tag:\n" + "\n".join(hits)

    def test_correct_tag_present_in_generate_html(self):
        src = _read("generate_html.py")
        assert f'_ADS_DEFAULT = "{ADS_TAG}"' in src
        assert ADS_CUSTOMER_WRONG in src  # listed in the reject set


class TestConsentGatingUnchanged:
    """Ads config must stay under Consent Mode v2 advanced defaults."""

    def test_defaults_still_deny_ad_storage(self):
        js = _read("assets/js/consent.js")
        assert re.search(r"var CONSENT_MODE\s*=\s*'advanced'", js)
        assert "'ad_storage': 'denied'" in js
        assert "'ad_user_data': 'denied'" in js
        assert "'ad_personalization': 'denied'" in js

    def test_rendered_page_carries_ads_tag_under_consent(self, tmp_path, monkeypatch):
        monkeypatch.delenv("GOOGLE_ADS_ID", raising=False)
        import generate_html

        importlib.reload(generate_html)
        try:
            out = generate_html.generate_about_page(
                dry_run=False, output_dir=tmp_path
            )
            html = (tmp_path / Path(out).name).read_text(encoding="utf-8")
            assert f'data-nn-ads-id="{ADS_TAG}"' in html
            assert ADS_CUSTOMER_WRONG not in html
            assert "data-nn-ads-signup-label" not in html
            assert "assets/js/consent.js" in html
            # Template must not hard-load a second gtag (consent.js owns it).
            assert "googletagmanager.com/gtag/js" not in html
        finally:
            importlib.reload(generate_html)
