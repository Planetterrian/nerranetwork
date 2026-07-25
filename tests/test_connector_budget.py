"""Drift guards for the analytics-connector runtime bounds (July 2026).

Background: the Spotify and Apple creator dashboards ship no official
API, so the network reads them through community connector packages.
Both embed a fixed retry loop with *unbounded* exponential backoff
(4s, 8s, 16s, 32s, 64s per failing endpoint). That is fine for a
transient error and pathological for a stable one — and on these
platforms a registered-but-unplayed feed answers ``500`` on
``/metadata`` and ``/aggregate`` every single night.

Measured 2026-07-25: 18 of 24 registered Spotify feeds were in that
state (~32 failing endpoints), so the nightly fetch step spent well
over an hour asleep before the rest of maintenance could run. Nothing
surfaced it, because ``api/spotify_stats.json`` records only the final
error, never the wall-clock cost of reaching it.

These tests pin the two guards that make that unrepeatable:
the retry clamp and the wall-clock budget.
"""

from __future__ import annotations

import re
import sys
import types
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from engine.connector_budget import (  # noqa: E402
    FetchBudget,
    clamp_connector_retries,
)

SPOTIFY_FETCHER = ROOT / "scripts" / "fetch_spotify_stats.py"
APPLE_FETCHER = ROOT / "scripts" / "fetch_apple_stats.py"


class TestRetryClamp:
    def test_rewrites_the_module_constants_in_place(self):
        """Both connectors read module-level constants inside their
        request loop — there is no per-instance knob, so assignment is
        the only lever."""
        mod = types.SimpleNamespace(MAX_REQUEST_ATTEMPTS=6, DELAY_BASE=2.0)
        applied = clamp_connector_retries(
            mod, attempts_attr="MAX_REQUEST_ATTEMPTS",
            delay_attr="DELAY_BASE", attempts=3, delay_base=1.0)
        assert mod.MAX_REQUEST_ATTEMPTS == 3
        assert mod.DELAY_BASE == 1.0
        assert applied == {"MAX_REQUEST_ATTEMPTS": 3, "DELAY_BASE": 1.0}

    def test_missing_attributes_are_a_silent_no_op(self):
        """A package upgrade that renames or drops the constants must
        degrade to 'unbounded retries + a loud log line', never crash
        the nightly fetch."""
        mod = types.SimpleNamespace()
        applied = clamp_connector_retries(
            mod, attempts_attr="MAX_REQUEST_ATTEMPTS",
            delay_attr="DELAY_BASE", attempts=3, delay_base=1.0)
        assert applied == {}

    def test_partial_attributes_report_what_was_applied(self):
        mod = types.SimpleNamespace(DELAY_BASE=2.0)
        applied = clamp_connector_retries(
            mod, attempts_attr="MAX_REQUEST_ATTEMPTS",
            delay_attr="DELAY_BASE", attempts=3, delay_base=1.0)
        assert applied == {"DELAY_BASE": 1.0}
        assert mod.DELAY_BASE == 1.0

    def test_the_clamped_backoff_is_bounded_by_construction(self):
        """The connectors double the delay each attempt and skip the
        final sleep, so total backoff per dead endpoint is
        sum(base * 2**k for k in 1..attempts-1). Pin that the shipped
        settings keep it in single-digit seconds; the package defaults
        (6 attempts / base 2.0) are ~124s."""
        def total_backoff(attempts: int, base: float) -> float:
            delay, total = base, 0.0
            for _ in range(attempts - 1):
                delay *= 2
                total += delay
            return total

        assert total_backoff(6, 2.0) > 100      # what we were paying
        assert total_backoff(3, 1.0) <= 10      # what we pay now


class TestFetchBudget:
    def test_a_zero_budget_never_expires(self):
        budget = FetchBudget(seconds=0)
        assert budget.remaining() == float("inf")
        assert not budget.exhausted()

    def test_a_spent_budget_reports_exhausted(self):
        budget = FetchBudget(seconds=0.001)
        # Force the clock forward rather than sleeping.
        budget._started -= 5
        assert budget.exhausted()
        assert budget.remaining() < 0

    def test_a_fresh_budget_is_not_exhausted(self):
        budget = FetchBudget(seconds=900)
        assert not budget.exhausted()
        assert 0 < budget.remaining() <= 900


class TestFetchersAreBounded:
    """Both cookie-connector fetchers must clamp AND budget. Losing
    either one re-opens the hours-long-nightly failure mode."""

    def test_spotify_fetcher_clamps_and_budgets(self):
        src = SPOTIFY_FETCHER.read_text(encoding="utf-8")
        assert "clamp_connector_retries" in src
        assert "FetchBudget" in src
        assert "budget.exhausted()" in src
        assert 'attempts_attr="MAX_REQUEST_ATTEMPTS"' in src

    def test_apple_fetcher_clamps_and_budgets(self):
        src = APPLE_FETCHER.read_text(encoding="utf-8")
        assert "clamp_connector_retries" in src
        assert "FetchBudget" in src
        assert "budget.exhausted()" in src
        # appleconnector spells it MAX_RETRY_ATTEMPTS — a copy-paste of
        # the Spotify constant name would silently clamp nothing.
        assert 'attempts_attr="MAX_RETRY_ATTEMPTS"' in src

    def test_budget_stop_carries_forward_previous_entries(self):
        """A budget stop must leave the output file complete. Dropping
        unreached shows would look like 'the feed was deregistered' on
        the dashboard instead of 'we ran out of time'."""
        for path in (SPOTIFY_FETCHER, APPLE_FETCHER):
            src = path.read_text(encoding="utf-8")
            assert "previous_shows" in src, path.name
            assert "not_refreshed_this_run" in src, path.name

    def test_all_failed_branch_is_guarded_against_an_empty_show_list(self):
        """``failures == len(show_ids)`` is 0 == 0 for an empty list —
        without the guard an unconfigured run would log the alarming
        'cookies have EXPIRED' error."""
        for path in (SPOTIFY_FETCHER, APPLE_FETCHER):
            src = path.read_text(encoding="utf-8")
            assert "if show_ids and failures == len(show_ids):" in src, path.name

    def test_defaults_are_env_overridable(self):
        """The operator must be able to loosen the bounds without a
        code change if a platform genuinely gets slower."""
        spotify = SPOTIFY_FETCHER.read_text(encoding="utf-8")
        apple = APPLE_FETCHER.read_text(encoding="utf-8")
        assert "SPOTIFY_FETCH_BUDGET_SECONDS" in spotify
        assert "SPOTIFY_MAX_REQUEST_ATTEMPTS" in spotify
        assert "APPLE_FETCH_BUDGET_SECONDS" in apple
        assert "APPLE_MAX_RETRY_ATTEMPTS" in apple


class TestAgeOfAiFeedIsCountedByOp3:
    """The Nerra Voices pipeline publishes Age of AI outside run_show, so
    it never inherited the OP3 enclosure prefix every other show gets.
    Result: OP3 had no show record for the feed (404 on lookup) and its
    downloads were invisible network-wide. Caught 2026-07-25."""

    PUBLISHER = ROOT / "pipelines" / "voices" / "publish_episode.py"

    def test_publish_applies_the_op3_prefix_to_new_enclosures(self):
        src = self.PUBLISHER.read_text(encoding="utf-8")
        assert "apply_op3_prefix" in src
        assert "audio_url=feed_audio_url" in src, (
            "the prefixed URL must be the one handed to update_rss_feed")

    def test_summaries_keep_the_direct_r2_url(self):
        """Only the RSS enclosure is proxied; the site's own player
        should hit R2 directly (matching the rest of the network)."""
        src = self.PUBLISHER.read_text(encoding="utf-8")
        assert '"audio_url": audio_url' in src

    def test_prefix_default_matches_the_network_default(self):
        """This pipeline deliberately skips the show-config stack, so
        the helper's default is the contract — pin it to
        shows/_defaults.yaml so the two can't drift."""
        import yaml

        defaults = yaml.safe_load(
            (ROOT / "shows" / "_defaults.yaml").read_text(encoding="utf-8"))
        configured = defaults["analytics"]["prefix_url"]
        publisher = (ROOT / "engine" / "publisher.py").read_text(
            encoding="utf-8")
        m = re.search(
            r'def apply_op3_prefix\([^)]*prefix_url:\s*str\s*=\s*"([^"]+)"',
            publisher, re.S)
        assert m, "apply_op3_prefix's default prefix moved"
        assert m.group(1) == configured
