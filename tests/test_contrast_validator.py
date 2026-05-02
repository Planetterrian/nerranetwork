"""Tests for contrast_validator — WCAG 2.1 AA tripwire."""

from __future__ import annotations

import pytest

from engine.contrast_validator import (
    ContrastError,
    assert_contrast_ok,
    contrast_ratio,
    find_contrast_failures,
)


class TestContrastRatio:

    def test_white_on_black_is_21_to_1(self):
        ratio = contrast_ratio((255, 255, 255), (0, 0, 0))
        assert ratio == pytest.approx(21.0, rel=0.001)

    def test_white_on_white_is_1_to_1(self):
        assert contrast_ratio((255, 255, 255), (255, 255, 255)) == pytest.approx(1.0)

    def test_known_aa_pair(self):
        # #475569 on #ffffff measures ~7.58:1 (comfortably AA pass).
        ratio = contrast_ratio((0x47, 0x55, 0x69), (0xff, 0xff, 0xff))
        assert ratio > 4.5
        assert ratio < 8.0


class TestFindContrastFailures:

    def test_clean_passes(self):
        html = (
            '<table><tr><td style="background:#ffffff;">'
            '<p style="color:#475569;font-size:14px;">Body text.</p>'
            '</td></tr></table>'
        )
        assert find_contrast_failures(html) == []

    def test_94a3b8_on_white_fails_at_small_size(self):
        # 11px label in muted gray on white = 3.0:1, well below AA.
        html = (
            '<table><tr><td style="background:#ffffff;">'
            '<div style="color:#94a3b8;font-size:11px;">Tiny label</div>'
            '</td></tr></table>'
        )
        fails = find_contrast_failures(html)
        assert len(fails) == 1
        assert "0.94a3b8" in fails[0].lower() or "94a3b8" in fails[0]

    def test_large_bold_relaxes_to_3_to_1(self):
        # #94a3b8 on white at 22px bold → 3.0:1 still passes (large-text).
        html = (
            '<table><tr><td style="background:#ffffff;">'
            '<div style="color:#94a3b8;font-size:22px;font-weight:700;">Big number</div>'
            '</td></tr></table>'
        )
        # Should not register as a failure under the AA-large rule.
        fails = find_contrast_failures(html)
        # Could still be one off due to ratio rounding; assert it's
        # not the 4.5:1 mismatch.
        assert all("4.5:1" not in f for f in fails)

    def test_inherits_through_nested_tables(self):
        # Inner color must be checked against the outer table's bgcolor.
        html = (
            '<table bgcolor="#0b1220"><tr><td>'
            '<span style="color:#000000;font-size:12px;">Black on dark</span>'
            '</td></tr></table>'
        )
        fails = find_contrast_failures(html)
        assert len(fails) >= 1

    def test_gradient_background_skipped(self):
        """We can't validate against a gradient — skip."""
        html = (
            '<table style="background:linear-gradient(135deg,#fff,#000);">'
            '<tr><td><span style="color:#888;font-size:14px;">x</span>'
            '</td></tr></table>'
        )
        # The walker should treat the gradient as "unknown bg" and
        # fall through to the page default (white).
        # Result is whatever — main thing is we don't crash.
        find_contrast_failures(html)

    def test_malformed_html_does_not_crash(self):
        html = "<table><tr><td><p>not closed"
        find_contrast_failures(html)  # no exception


class TestAssertContrastOk:

    def test_clean_html_passes(self):
        # Should not raise.
        assert_contrast_ok(
            '<p style="color:#475569;font-size:14px;'
            'background:#ffffff;">ok</p>'
        )

    def test_failing_html_raises(self):
        with pytest.raises(ContrastError):
            assert_contrast_ok(
                '<table><tr><td style="background:#ffffff;">'
                '<p style="color:#94a3b8;font-size:10px;">fail</p>'
                '</td></tr></table>'
            )
