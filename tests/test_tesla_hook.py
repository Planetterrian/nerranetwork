"""Tests for ``shows/hooks/tesla.py:_fetch_tsla_price``.

The fetcher was flipped from yfinance to Grok's ``x_search`` built-in
tool in May 2026 after operator caught yfinance repeatedly returning
``$0.00 (price unavailable)``. These tests pin the contract:

* Happy-path JSON from Grok produces the canonical
  ``▲ $X.XX (X.X%)`` change string the existing pipeline expects.
* Out-of-range / malformed / missing-field responses fall back to
  ``(0.0, "(price unavailable)")`` so we never ship a hallucinated
  number to the digest.

The Grok call itself is monkey-patched out — these are pure-function
tests, never hit the network.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "shows" / "hooks"))

import tesla as tesla_hook  # noqa: E402  (sys.path manipulation needed)


def _patch_grok(monkeypatch, text: str):
    """Stub ``digests.xai_grok.grok_generate_text`` to return ``text``."""
    from digests import xai_grok

    def _fake(prompt, **kwargs):
        return text, {"provider": "stub"}

    monkeypatch.setattr(xai_grok, "grok_generate_text", _fake)


class TestHappyPath:

    def test_clean_json_regular_session(self, monkeypatch):
        _patch_grok(monkeypatch, '{"price": 411.82, "prev_close": 402.38, "market_state": "REGULAR"}')
        price, change_str = tesla_hook._fetch_tsla_price()
        assert price == 411.82
        # Up $9.44, ~2.3% — direction triangle ▲, no after-hours marker.
        assert "▲" in change_str
        assert "$9.44" in change_str
        assert "2.3%" in change_str
        assert "After-hours" not in change_str
        assert "Pre-market" not in change_str

    def test_negative_change_uses_down_arrow(self, monkeypatch):
        _patch_grok(monkeypatch, '{"price": 380.00, "prev_close": 400.00, "market_state": "REGULAR"}')
        price, change_str = tesla_hook._fetch_tsla_price()
        assert price == 380.00
        assert "▼" in change_str
        assert "$20.00" in change_str
        assert "5.0%" in change_str

    def test_after_hours_marker(self, monkeypatch):
        _patch_grok(monkeypatch, '{"price": 415.00, "prev_close": 411.82, "market_state": "POST"}')
        _, change_str = tesla_hook._fetch_tsla_price()
        assert "(After-hours)" in change_str

    def test_pre_market_marker(self, monkeypatch):
        _patch_grok(monkeypatch, '{"price": 405.00, "prev_close": 411.82, "market_state": "PRE"}')
        _, change_str = tesla_hook._fetch_tsla_price()
        assert "(Pre-market)" in change_str

    def test_extracts_json_when_grok_adds_prose(self, monkeypatch):
        """Grok occasionally wraps the JSON in code fences or adds
        a 'Here is the data:' preamble despite the prompt. The
        first-``{...}``-block regex must still parse it cleanly."""
        _patch_grok(
            monkeypatch,
            'Here is the latest:\n```json\n{"price": 400.00, "prev_close": 400.00, "market_state": "REGULAR"}\n```\nThat\'s from $TSLA on X.',
        )
        price, change_str = tesla_hook._fetch_tsla_price()
        assert price == 400.00
        assert "▲" in change_str
        assert "$0.00" in change_str


class TestFailureModes:
    """Every path that can't yield a trustworthy quote must return
    ``(0.0, "(price unavailable)")`` so the digest template renders
    a graceful placeholder rather than a hallucinated number."""

    def test_grok_call_raises(self, monkeypatch):
        from digests import xai_grok

        def _boom(prompt, **kwargs):
            raise RuntimeError("network down")

        monkeypatch.setattr(xai_grok, "grok_generate_text", _boom)
        price, change_str = tesla_hook._fetch_tsla_price()
        assert price == 0.0
        assert change_str == "(price unavailable)"

    def test_no_json_in_response(self, monkeypatch):
        _patch_grok(monkeypatch, "I'm sorry, I can't find that data on X right now.")
        price, change_str = tesla_hook._fetch_tsla_price()
        assert price == 0.0
        assert change_str == "(price unavailable)"

    def test_malformed_json(self, monkeypatch):
        _patch_grok(monkeypatch, '{"price": 411.82 "prev_close": 402.38}')  # missing comma
        price, change_str = tesla_hook._fetch_tsla_price()
        assert price == 0.0
        assert change_str == "(price unavailable)"

    def test_missing_field(self, monkeypatch):
        _patch_grok(monkeypatch, '{"price": 411.82}')
        price, change_str = tesla_hook._fetch_tsla_price()
        assert price == 0.0
        assert change_str == "(price unavailable)"

    def test_non_numeric_field(self, monkeypatch):
        _patch_grok(monkeypatch, '{"price": "FOUR HUNDRED", "prev_close": 402.38, "market_state": "REGULAR"}')
        price, change_str = tesla_hook._fetch_tsla_price()
        assert price == 0.0
        assert change_str == "(price unavailable)"

    def test_price_below_sanity_band(self, monkeypatch):
        """``$5`` is impossible for TSLA — likely a Grok hallucination
        or a stale stub from a parallel universe. Fall back gracefully."""
        _patch_grok(monkeypatch, '{"price": 5.00, "prev_close": 400.00, "market_state": "REGULAR"}')
        price, change_str = tesla_hook._fetch_tsla_price()
        assert price == 0.0
        assert change_str == "(price unavailable)"

    def test_price_above_sanity_band(self, monkeypatch):
        """``$5000`` is impossibly high; fall back."""
        _patch_grok(monkeypatch, '{"price": 5000.00, "prev_close": 400.00, "market_state": "REGULAR"}')
        price, change_str = tesla_hook._fetch_tsla_price()
        assert price == 0.0
        assert change_str == "(price unavailable)"

    def test_prev_close_out_of_band_fails(self, monkeypatch):
        """A plausible price with an impossible prev_close would compute
        a misleading change %; reject the whole response."""
        _patch_grok(monkeypatch, '{"price": 400.00, "prev_close": 0.05, "market_state": "REGULAR"}')
        price, change_str = tesla_hook._fetch_tsla_price()
        assert price == 0.0
        assert change_str == "(price unavailable)"


class TestMarketStateDefaulting:
    """If Grok omits ``market_state``, the fetcher should still return
    a valid quote — just without an after-hours/pre-market suffix."""

    def test_missing_market_state_defaults_to_regular(self, monkeypatch):
        _patch_grok(monkeypatch, '{"price": 411.82, "prev_close": 411.82}')
        price, change_str = tesla_hook._fetch_tsla_price()
        assert price == 411.82
        assert "(After-hours)" not in change_str
        assert "(Pre-market)" not in change_str

    def test_unknown_market_state_treated_as_regular(self, monkeypatch):
        _patch_grok(monkeypatch, '{"price": 411.82, "prev_close": 411.82, "market_state": "WEIRD"}')
        _, change_str = tesla_hook._fetch_tsla_price()
        assert "(After-hours)" not in change_str
        assert "(Pre-market)" not in change_str
