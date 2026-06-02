"""Verify X-post *fetching* is gated correctly, decoupled from X *posting*.

History:
  - Before May 12 2026 ``_run_x_fetch()`` gated only on ``x_accounts`` —
    so shows with accounts configured ran the X API call every tick even
    with posting off, spending quota on unused content.
  - May 12 2026: gated on ``publishing.x_enabled`` too.
  - May 2026 (MAB sourcing audit): that coupling ALSO killed X as a
    *content source* for non-posting shows (MAB had collapsed onto
    RSS-only). The gate now lives in ``engine.fetcher.x_fetch_allowed``
    and a show opts X sourcing back in with ``x_fetch_enabled: true`` —
    independent of whether it posts. Unset still inherits ``x_enabled``,
    so every other show is unchanged.

These tests pin the real ``x_fetch_allowed`` helper (no test-only copy).
"""

from engine.fetcher import x_fetch_allowed


def test_skip_when_no_accounts():
    """Empty x_accounts → never fetch, regardless of flags."""
    assert x_fetch_allowed([], True, True) is False
    assert x_fetch_allowed([], True, None) is False


def test_default_inherits_x_enabled():
    """x_fetch_enabled unset (None) → behaves exactly like the old gate:
    fetch iff x_enabled. Pins back-compat for every non-opted-in show."""
    assert x_fetch_allowed(["@a"], True, None) is True
    assert x_fetch_allowed(["@a"], False, None) is False


def test_explicit_override_enables_fetch_without_posting():
    """The MAB fix: posting off (x_enabled False) but x_fetch_enabled True
    → fetch the curated accounts for content anyway."""
    assert x_fetch_allowed(["@a"], False, True) is True


def test_explicit_override_can_disable_fetch_while_posting():
    """x_fetch_enabled False wins even if the show posts (x_enabled True)."""
    assert x_fetch_allowed(["@a"], True, False) is False


def test_mab_resolves_to_fetch_enabled_from_yaml():
    """MAB posts to nobody (x_enabled False) but opts into X sourcing
    (x_fetch_enabled True), so the gate now ALLOWS the fetch — reversing
    the dormant-accounts behaviour for this show specifically."""
    from engine.config import load_config

    cfg = load_config("shows/models_agents_beginners.yaml")
    assert cfg.publishing.x_enabled is False
    assert cfg.x_fetch_enabled is True
    assert cfg.x_accounts, "MAB must keep its curated X accounts"
    assert x_fetch_allowed(
        cfg.x_accounts, cfg.publishing.x_enabled, cfg.x_fetch_enabled
    ) is True


def test_other_non_posting_shows_stay_dormant():
    """Shows that did NOT opt in (no x_fetch_enabled) still don't fetch
    while posting is off — unchanged behaviour."""
    from engine.config import load_config

    for slug in ("env_intel", "finansy_prosto", "privet_russian"):
        cfg = load_config(f"shows/{slug}.yaml")
        assert cfg.publishing.x_enabled is False
        # Not opted in → inherits x_enabled=False → no fetch.
        assert x_fetch_allowed(
            cfg.x_accounts, cfg.publishing.x_enabled,
            getattr(cfg, "x_fetch_enabled", None),
        ) is False
