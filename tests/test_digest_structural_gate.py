"""Drift guards for the digest structural-integrity gate (run_show 7d).

Tesla Ep493 (2026-05-30) shipped a 12,904-char digest that cleared the
800-char length floor but was structurally broken: it had no **HOOK:** line
and an empty "First Principles" section. Because the digest was long, the
empty-section issue was logged as a non-blocking "formatting mismatch" and
the broken digest was handed to the podcast stage — which then dropped the
entire main-news body, producing an 818-word script that was skipped as too
thin.

The gate now distinguishes a *0-item* mandatory section (a structural defect
worth one corrective regeneration) from a soft item-count shortfall (a
formatting mismatch that should not trigger a regen). These tests pin that
distinction.
"""

from __future__ import annotations

from run_show import _empty_mandatory_section_issues


class TestEmptyMandatorySectionIssues:

    def test_ep493_empty_first_principles_is_flagged(self):
        """The exact Ep493 validator message for an empty section must be
        recognized as structural."""
        issues = ["Section 'First Principles': 0 items (minimum 1)"]
        assert _empty_mandatory_section_issues(issues) == issues

    def test_soft_shortfall_is_not_flagged(self):
        """A non-zero shortfall ("8 of 10") is a formatting mismatch on a
        long digest, NOT a structural defect — it must not trigger a regen."""
        issues = ["Section 'Top 12 News Items' has only 8 items (minimum 10)"]
        assert _empty_mandatory_section_issues(issues) == []

    def test_mixed_returns_only_empty_sections(self):
        issues = [
            "Section 'Top 12 News Items' has only 9 items (minimum 10)",
            "Section 'First Principles': 0 items (minimum 1)",
            "Section 'Short Spot': 0 items (minimum 1)",
        ]
        assert _empty_mandatory_section_issues(issues) == [
            "Section 'First Principles': 0 items (minimum 1)",
            "Section 'Short Spot': 0 items (minimum 1)",
        ]

    def test_empty_input_returns_empty(self):
        assert _empty_mandatory_section_issues([]) == []

    def test_does_not_false_match_ten_items(self):
        """A regex that matched a bare '0' could catch '10 items'. Ensure the
        word-boundary on the count keeps '10 items' out."""
        issues = ["Section 'Top 12 News Items': 10 items (minimum 10)"]
        assert _empty_mandatory_section_issues(issues) == []
