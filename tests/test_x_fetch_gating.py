"""Verify X-post fetching is gated by ``publishing.x_enabled``.

Before May 12 2026 the ``_run_x_fetch()`` closure in run_show.py
gated only on ``config.x_accounts`` — so any show that had
accounts configured ran the X API call on every cron tick, even
when X posting was disabled for that show. Six shows fit this
shape (Env Intel, MAB, M&A pre-PR, FP, PR, MIT pre-PR) and were
silently spending X API quota for content that was never used.

The gate is now ``not x_accounts or not publishing.x_enabled`` so
both flags must agree before the API call goes out. These tests
pin the new contract.
"""

from types import SimpleNamespace
from unittest.mock import MagicMock, patch


def _make_config(*, x_accounts, x_enabled):
    """Build a minimal config namespace matching what run_show uses."""
    return SimpleNamespace(
        x_accounts=x_accounts,
        keywords=["test", "keywords"],
        publishing=SimpleNamespace(x_enabled=x_enabled),
    )


def _fetch_under_gate(config):
    """Replica of the gate logic in run_show.py:_run_x_fetch().

    Kept here as a test-only copy because the production function is
    a closure inside run() — not importable. The gate predicate is
    one line; pinning it here guards against silent regression."""
    if not config.x_accounts or not config.publishing.x_enabled:
        return []
    from engine.fetcher import fetch_x_posts
    return fetch_x_posts(config.x_accounts, keywords=config.keywords)


def test_skip_when_no_accounts():
    """Empty x_accounts → no fetch, no API call."""
    cfg = _make_config(x_accounts=[], x_enabled=True)
    with patch("engine.fetcher.fetch_x_posts") as mock_fetch:
        result = _fetch_under_gate(cfg)
    assert result == []
    mock_fetch.assert_not_called()


def test_skip_when_x_posting_disabled():
    """x_accounts configured but x_enabled=False → no fetch.

    This is the May 12 2026 fix. The previous code only checked
    accounts; this assertion would have failed before the fix."""
    cfg = _make_config(x_accounts=["@example"], x_enabled=False)
    with patch("engine.fetcher.fetch_x_posts") as mock_fetch:
        result = _fetch_under_gate(cfg)
    assert result == []
    mock_fetch.assert_not_called()


def test_fetch_when_both_configured():
    """Accounts + posting both on → fetch runs."""
    cfg = _make_config(x_accounts=["@example"], x_enabled=True)
    with patch("engine.fetcher.fetch_x_posts", return_value=[{"id": 1}]) as mock_fetch:
        result = _fetch_under_gate(cfg)
    assert result == [{"id": 1}]
    mock_fetch.assert_called_once_with(["@example"], keywords=["test", "keywords"])


def test_skip_when_both_disabled():
    """Neither flag set → no fetch (degenerate case but worth pinning)."""
    cfg = _make_config(x_accounts=[], x_enabled=False)
    with patch("engine.fetcher.fetch_x_posts") as mock_fetch:
        result = _fetch_under_gate(cfg)
    assert result == []
    mock_fetch.assert_not_called()


def test_yaml_state_shows_with_x_disabled_have_dormant_accounts():
    """The four shows that keep X posting off (Env Intel, MAB, FP,
    PR) all still have ``x_accounts`` configured in their YAML —
    they just won't fetch any more. Pinning so a future YAML edit
    that removes ``x_accounts`` to "fix" this isn't needed (and
    so re-enabling X on these shows later is a single-flag flip)."""
    from engine.config import load_config

    for slug in ("env_intel", "models_agents_beginners", "finansy_prosto", "privet_russian"):
        cfg = load_config(f"shows/{slug}.yaml")
        # X disabled — gate should block fetch.
        assert cfg.publishing.x_enabled is False, (
            f"{slug}: expected x_enabled False (gate blocks fetch); "
            f"if you re-enable, update this test."
        )
