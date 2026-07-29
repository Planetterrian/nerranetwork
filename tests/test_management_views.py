"""Drift guards for management.html — the Apple card and the view switch.

Two things this pins:

1. **The Apple card's emptiness test.** The two Apple sources count
   shows under different keys — the cookie scrape publishes
   ``feeds_reporting``, the official Reporter feed publishes
   ``shows_reporting`` — and the dashboard flattens only whichever the
   primary source used. Testing ``feeds_reporting`` alone therefore read
   as "not reporting" on every Reporter-primary run: the card announced
   "0 of 0 registered shows returned engagement" while sitting on real
   Apple data (60 plays across 2 shows on 2026-07-27). That is the
   "Apple Podcasts section shows no information" the operator reported.

2. **The operator ⇄ sponsor view contract.** The same page serves an
   internal console and a shareable audience view. Operator is the
   default and must keep showing everything; sponsor must hide internal
   spend and pipeline-health surfaces. A regression in either direction
   is silent — the page still renders, it just shows the wrong audience
   the wrong thing.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
PAGE = REPO_ROOT / "management.html"


def _page() -> str:
    return PAGE.read_text(encoding="utf-8")


class TestAppleCardReadsEitherSource:
    def test_emptiness_check_is_not_source_specific(self):
        src = _page()
        assert "function appleIsReporting" in src
        # The old guard: a bare feeds_reporting test in the card's own
        # branch. It must not come back.
        assert "!(ap.feeds_reporting > 0)" not in src
        assert "} else if (!appleIsReporting(ap)) {" in src

    def test_helper_accepts_the_reporter_key(self):
        src = _page()
        body = src[src.index("function appleIsReporting"):]
        body = body[:body.index("\n  }")]
        assert "shows_reporting" in body, (
            "the official Reporter feed counts shows under shows_reporting"
        )
        assert "feeds_reporting" in body, (
            "the cookie scrape counts them under feeds_reporting"
        )

    def test_helper_falls_back_to_the_numbers(self):
        """Neither key is guaranteed — a source that reports totals but
        no count must still render rather than claim nothing arrived."""
        body = _page()
        body = body[body.index("function appleIsReporting"):]
        body = body[:body.index("\n  }")]
        assert "totals" in body and "per_show" in body

    def test_live_dashboard_would_render_the_card(self):
        """Guards the actual committed data, not just the code: with the
        current api/dashboard.json the card must have something to show."""
        data = json.loads(
            (REPO_ROOT / "api" / "dashboard.json").read_text(encoding="utf-8"))
        ap = ((data.get("audience") or {}).get("apple") or {})
        if not ap.get("configured"):
            return  # unconfigured is a legitimate state
        totals = ap.get("totals") or {}
        per_show = ap.get("per_show") or {}
        reporting = (
            (ap.get("shows_reporting") or 0) > 0
            or (ap.get("feeds_reporting") or 0) > 0
            or (totals.get("plays") or 0) > 0
            or (totals.get("listeners") or 0) > 0
            or any((v or {}).get("plays") for v in per_show.values())
        )
        assert reporting, (
            "Apple is configured but the committed dashboard has no "
            "renderable engagement — regenerate api/dashboard.json"
        )

    def test_flattening_survives_in_the_generator(self):
        """The card reads flattened keys; the generator must keep
        producing them alongside the two-source `sources` block."""
        gen = (REPO_ROOT / "scripts" / "generate_dashboard.py").read_text(
            encoding="utf-8")
        assert "Flattened view of the primary source" in gen


class TestViewSwitch:
    def test_operator_is_the_default(self):
        src = _page()
        assert 'id="view-operator" aria-pressed="true"' in src
        assert 'id="view-sponsor" aria-pressed="false"' in src

    def test_sponsor_hides_ops_and_shows_sponsor_surfaces(self):
        src = _page()
        assert "body.view-sponsor [data-ops] { display: none !important; }" in src
        assert "[data-sponsor] { display: none; }" in src
        assert "body.view-sponsor [data-sponsor] { display: revert; }" in src

    def test_internal_surfaces_are_tagged(self):
        """Spend, alerts, health pills and the ops-only sections must all
        carry data-ops or the sponsor view leaks internals."""
        src = _page()
        for marker in (
            '<div class="alert-band" id="alert-band" data-ops>',
            '<div class="health-pills" id="status-summary" data-ops hidden>',
        ):
            assert marker in src, marker
        for section in ("operations", "library", "guards", "voice", "feeds"):
            assert f'<section class="mc-section" data-ops id="{section}">' in src, section

    def test_spend_tiles_are_operator_only(self):
        src = _page()
        spend = src[src.index('statTile("Spend · 7d"'):]
        assert "ops: true" in spend[:400]
        episodes = src[src.index('statTile("Episodes · 7d"'):]
        assert "ops: true" in episodes[:400]

    def test_url_parameter_overrides_the_stored_preference(self):
        """A shared ?view=sponsor link must open in sponsor view even for
        someone whose localStorage says operator."""
        src = _page()
        switch = src[src.index("function viewSwitch"):]
        url_idx = switch.index('URLSearchParams(window.location.search).get("view")')
        store_idx = switch.index('localStorage.getItem("nerraDashView")')
        assert url_idx < store_idx, "URL must be consulted before localStorage"

    def test_private_mode_cannot_break_the_switch(self):
        """localStorage throws in some privacy modes; the toggle must not
        take the page down with it."""
        src = _page()
        switch = src[src.index("function viewSwitch"):]
        assert re.search(r"try \{ localStorage\.setItem", switch)
        assert re.search(r"catch \(e\) \{ /\* private mode \*/ \}", switch)


class TestSponsorFiguresStayHonest:
    """The sponsor view is the one surface an outside party may rely on,
    so its claims have to match what the data actually means."""

    def test_youtube_views_are_labelled_lifetime(self):
        src = _page()
        assert 'l: "YouTube views · lifetime"' in src
        # network_views is the 90-day Analytics window, not lifetime; it
        # may appear as the secondary line but never as the headline.
        panel = src[src.index("function renderSponsorPanel"):]
        panel = panel[:panel.index("// ---------- view switch")]
        headline = panel[panel.index('l: "YouTube views · lifetime"') - 200:
                         panel.index('l: "YouTube views · lifetime"')]
        assert 'chSum("total_views")' in headline

    def test_platform_count_is_derived_not_hardcoded(self):
        src = _page()
        assert "function liveFeedCount" in src
        body = src[src.index("function liveFeedCount"):]
        body = body[:body.index("\n  }")]
        assert "distribution" in body and "live" in body

    def test_no_blended_reach_number(self):
        """The analytics contract forbids summing downloads, streams and
        views into one figure. The sponsor panel must respect it."""
        src = _page()
        panel = src[src.index("function renderSponsorPanel"):]
        panel = panel[:panel.index("// ---------- view switch")]
        assert "never" in panel.lower() and "sum" in panel.lower()
