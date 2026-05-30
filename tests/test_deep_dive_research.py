"""Tests for engine.deep_dive_research — live grounding for time-sensitive
deep dives.

A deep dive normally runs off its static brief with no fetch, which leaves a
time-sensitive topic grounded only in the model's training cutoff (MIT Ep059
shipped "no announced IPO ... speculative" for exactly this reason). When a
queue entry carries ``web_search_queries`` the runner calls
``research_current_context`` to pull the current, sourced state and inject it
into the brief prompt. These tests pin the contract + the best-effort
fallbacks (research must never block an episode).
"""

from __future__ import annotations

import datetime as _dt

import pytest

from engine.deep_dive_research import research_current_context


class TestResearchCurrentContext:

    def test_no_queries_returns_empty(self):
        assert research_current_context("SpaceX IPO", []) == ""

    def test_no_api_key_returns_empty(self, monkeypatch):
        """Without credentials, research degrades to '' so the deep dive
        falls back to the static brief instead of crashing."""
        monkeypatch.delenv("GROK_API_KEY", raising=False)
        monkeypatch.delenv("XAI_API_KEY", raising=False)
        assert research_current_context("SpaceX IPO", ["q"]) == ""

    def test_grok_error_is_swallowed(self, monkeypatch):
        """A network / tool error must not propagate — research is
        best-effort and never blocks the episode."""
        monkeypatch.setenv("GROK_API_KEY", "test-key")
        import digests.xai_grok as xg

        def _boom(**kwargs):
            raise RuntimeError("x.ai down")

        monkeypatch.setattr(xg, "grok_generate_text", _boom)
        assert research_current_context("SpaceX IPO", ["q"]) == ""

    def test_no_current_information_sentinel_returns_empty(self, monkeypatch):
        monkeypatch.setenv("GROK_API_KEY", "test-key")
        import digests.xai_grok as xg
        monkeypatch.setattr(
            xg, "grok_generate_text",
            lambda **kw: ("NO_CURRENT_INFORMATION_FOUND", {}),
        )
        assert research_current_context("SpaceX IPO", ["q"]) == ""

    def test_returns_research_text_and_passes_search_params(self, monkeypatch):
        monkeypatch.setenv("GROK_API_KEY", "test-key")
        import digests.xai_grok as xg
        captured = {}

        def _fake(**kwargs):
            captured.update(kwargs)
            return ("- per Reuters, June 1 2026: S-1 filed ...", {})

        monkeypatch.setattr(xg, "grok_generate_text", _fake)
        out = research_current_context(
            "SpaceX IPO", ["SpaceX IPO date"],
            x_handles=["SpaceX"], today=_dt.date(2026, 6, 1),
        )
        assert "S-1 filed" in out
        # Must actually enable both search tools and pass the date + queries.
        assert captured["enable_web_search"] is True
        assert captured["enable_x_search"] is True
        assert "2026-06-01" in captured["prompt"]
        assert "SpaceX IPO date" in captured["prompt"]
