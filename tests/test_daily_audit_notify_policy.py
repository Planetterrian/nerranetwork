"""Drift guard for the daily-audit notification policy (May 2026).

Operator decision: the daily Episode Review / audit workflow should PAGE
(red-X the run + notify) only for OPERATIONAL problems — a show that was due
but produced no episode. Editorial-quality criticals (short script,
repetition, ``nay-toe`` / ``nassa`` garbles) plus warnings are recorded in
the GitHub issue + api/daily-review.json, but must NOT fail the run —
otherwise the audit emailed a failure daily for routine quality notes.

These tests pin ``review_episodes._review_exit_code`` so a future change
that re-couples editorial findings to the paging exit code (1) trips here.
"""

from __future__ import annotations

from review_episodes import _review_exit_code


def test_missed_episode_pages():
    """An operational problem (a due episode is missing) returns 1 → the
    workflow red-X's / notifies."""
    assert _review_exit_code(operational_critical=1, editorial_critical=0, total_warnings=0) == 1


def test_editorial_criticals_do_not_page():
    """Short-script / repetition / garble criticals on episodes that DID
    ship are editorial — return 2 (recorded, non-paging), NOT 1."""
    assert _review_exit_code(operational_critical=0, editorial_critical=4, total_warnings=15) == 2


def test_warnings_only_do_not_page():
    assert _review_exit_code(operational_critical=0, editorial_critical=0, total_warnings=3) == 2


def test_clean_run_is_zero():
    assert _review_exit_code(operational_critical=0, editorial_critical=0, total_warnings=0) == 0


def test_operational_wins_even_with_editorial():
    """If a real episode is missing AND others have editorial notes, the
    operational signal dominates — still page (1)."""
    assert _review_exit_code(operational_critical=1, editorial_critical=9, total_warnings=20) == 1


def test_todays_real_tally_would_not_page():
    """The 2026-05-30 run had 4 critical / 15 warnings, ALL editorial (no
    missed episodes). Under the new policy that's a non-paging exit 2 —
    exactly the daily failure email the operator asked to stop."""
    # All 4 criticals were editorial (short script + repetition), 0 missed.
    assert _review_exit_code(operational_critical=0, editorial_critical=4, total_warnings=15) == 2
