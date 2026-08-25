"""Drift guards for the growth-levers dashboard section (Aug 2026).

Five surfaces added after the Aug 5-7 week of growth work: the per-channel
WoW scorecard (with the zero-view early warning the FR launch lacked), the
experiments-in-flight register (docs/experiments.yaml with live metric
snapshots), staggered-Shorts / deferred-comment sweep health, the specials
queue, and analytics freshness (the Aug 6 outage made every number
silently a day stale — never again silently).

Honesty rules under test: unmeasured values are None (never 0), the
zero-view share compares INDEX uploads with analytics rows (the API omits
zero-activity videos), and every registry metric name must be one the
generator can actually compute — a typo'd metric must fail CI, not render
"no data yet" forever.
"""
from __future__ import annotations

import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts import generate_dashboard as gd  # noqa: E402


class TestChannelScorecard:
    def test_configured_with_channels_and_honest_fields(self):
        sc = gd.build_channel_scorecard(ROOT)
        assert sc["configured"] is True
        assert "en" in sc["channels"] and "ru" in sc["channels"]
        for ch, c in sc["channels"].items():
            assert c["views_7d"] >= 0
            # WoW is None when the prior week is 0 — never a fake number.
            assert c["views_wow_pct"] is None or isinstance(
                c["views_wow_pct"], (int, float))
            z = c["zero_view_share_14d"]
            assert z is None or 0.0 <= z <= 1.0
            # uploads come from the INDEX (complete record) and must be
            # >= the analytics rows the API deigned to return.
            assert c["uploads_14d"] >= c["analytics_rows_14d"]

    def test_window_note_documents_the_approximation(self):
        sc = gd.build_channel_scorecard(ROOT)
        assert "zero" in sc["window_note"].lower()


class TestExperimentsRegister:
    def test_registry_parses_and_entries_are_valid(self):
        ex = gd.build_experiments_section(ROOT)
        assert ex["configured"] is True and "error" not in ex
        rows = ex["experiments"]
        assert rows, "registry must not be empty"
        for r in rows:
            assert r["id"] and r["title"]
            assert r["status"] in gd._EXPERIMENT_STATUSES

    def test_every_registry_metric_is_computable(self):
        """A typo'd metric key would render 'no data yet' forever — the
        registry may only name metrics the generator computes."""
        computable = set(gd._experiment_live_metrics(ROOT).keys())
        data = yaml.safe_load((ROOT / "docs" / "experiments.yaml").read_text())
        for e in data["experiments"]:
            m = e.get("metric")
            assert m is None or m in computable, (
                f"experiment {e['id']!r} names unknown metric {m!r}; "
                f"computable: {sorted(computable)}")

    def test_live_metrics_are_none_or_numeric(self):
        for k, v in gd._experiment_live_metrics(ROOT).items():
            assert v is None or isinstance(v, (int, float)), (k, v)


class TestStaggerHealth:
    def test_section_shape(self):
        st = gd.build_stagger_section(ROOT)
        assert st["pending_total"] >= 0 and st["posted_total"] >= 0
        assert isinstance(st["sweep_stuck"], bool)
        for s in st["shows"]:
            assert s["slug"] and s["pending"] >= 0

    def test_sweep_maintains_posted_total(self, tmp_path, monkeypatch):
        """post_due_comments must increment the sidecar's rolling counter —
        it is the only evidence the sweep ever worked once entries clear."""
        import json
        import datetime as dt
        from engine.shorts_stagger import queue_comment, post_due_comments
        ddir = tmp_path / "digests" / "spacex"
        ddir.mkdir(parents=True)
        due = dt.datetime(2026, 8, 7, 15, tzinfo=dt.timezone.utc)
        queue_comment(ddir, video_id="v1", channel="ru", text="t",
                      publish_at=due)
        import engine.youtube as yt
        monkeypatch.setattr(yt, "get_channel_credentials_from_env",
                            lambda ch: object())
        monkeypatch.setattr(yt, "post_video_comment", lambda **kw: "cid")
        post_due_comments(tmp_path, now=due + dt.timedelta(hours=1))
        data = json.loads((ddir / "scheduled_comments.json").read_text())
        assert data["posted_total"] == 1 and data["pending"] == []


class TestSpecialsQueue:
    def test_prestaged_spacex_specials_visible(self):
        sp = gd.build_specials_section(ROOT)
        assert sp["configured"] is True
        pending_ids = {(r["show"], r["id"]) for r in sp["pending"]}
        assert ("spacex", "flight-14-catch-reaction") in pending_ids
        assert ("spacex", "q3-2026-earnings") in pending_ids
        produced_ids = {r["id"] for r in sp["produced"]}
        assert "q2-2026-earnings" in produced_ids


class TestFreshness:
    def test_all_four_sources_tracked(self):
        fr = gd.build_freshness_section(ROOT)
        assert set(fr["sources"]) == {
            "youtube_stats", "youtube_policy", "op3_stats", "funnel"}
        for s in fr["sources"].values():
            assert s["age_hours"] is None or s["age_hours"] >= 0


class TestHtmlWiring:
    def test_growth_section_rendered(self):
        html = (ROOT / "management.html").read_text()
        assert 'id="levers-grid"' in html
        assert "data.growth" in html
        for marker in ("Channel scorecard", "Levers in flight",
                       "Staggered Shorts", "Specials queue",
                       "Analytics freshness"):
            assert marker in html, f"missing card: {marker}"


class TestLagAwareAnalyticsWindows:
    """Aug 24 2026: YouTube Analytics day-data finalizes ~48h behind.
    Without trimming the unreported tail, every channel 'lost' its
    newest 2 days of uploads to zero-view counting and the RU WoW read
    -43% during a plain reporting lag."""

    def test_scorecard_trims_the_lag_tail(self):
        src = (ROOT / "scripts" / "generate_dashboard.py").read_text(
            encoding="utf-8")
        assert "_LAG_DAYS = 2" in src
        # Both the scorecard and the experiment WoW metric trim.
        assert src.count("ds = ds[:-2] if len(ds) > 2 else ds") == 2
        assert "excluded as unreported lag" in src


class TestVirtualShowCosts:
    """Nerra Daily's credit files live under digests/nerra_daily but the
    dashboard derives its show list from shows/*.yaml, so the edition's
    spend was invisible to every cost rollup (2026-08-25 review). The
    virtual-slug list keeps registry-only shows in the money math."""

    def test_nerra_daily_in_virtual_cost_slugs(self):
        assert "nerra_daily" in gd._VIRTUAL_COST_SLUGS

    def test_aggregate_costs_includes_virtual_shows(self):
        costs = gd.aggregate_costs(ROOT, [])
        assert "nerra_daily" in costs["per_show"]
