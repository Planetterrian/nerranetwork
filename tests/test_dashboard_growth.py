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

import json
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


class TestReachNormalisedSubs:
    """Sep 22 2026: subscribers per 1,000 EN Short views — the CTA read
    that does not fall when reach falls."""

    def _root(self, tmp_path, videos):
        (tmp_path / "api").mkdir()
        (tmp_path / "api" / "youtube_stats.json").write_text(json.dumps({
            "generated": "2026-09-22T14:00:00Z",
            "channels": {"en": {"day_series": []}},
            "shows": {"x": {"videos": videos}},
        }), encoding="utf-8")
        (tmp_path / "digests").mkdir()
        return tmp_path

    def test_null_under_300_views_never_zero(self, tmp_path):
        vids = [{"kind": "short", "channel": "en", "published": "2026-09-20",
                 "views": 10, "subscribers_gained": 0} for _ in range(12)]
        m = gd._experiment_live_metrics(self._root(tmp_path, vids))
        assert m["short_subs_per_1k_views_14d_en"] is None
        assert m["short_subs_per_video_14d_en"] == 0.0

    def test_computes_per_1k_views(self, tmp_path):
        vids = [{"kind": "short", "channel": "en", "published": "2026-09-20",
                 "views": 100, "subscribers_gained": 1} for _ in range(12)]
        vids.append({"kind": "short", "channel": "ru", "published": "2026-09-20",
                     "views": 5000, "subscribers_gained": 9})  # other channel ignored
        m = gd._experiment_live_metrics(self._root(tmp_path, vids))
        assert m["short_subs_per_1k_views_14d_en"] == 10.0
        assert m["short_subs_per_video_14d_en"] == 1.0

    def test_cta_experiment_reads_the_normalised_metric(self):
        reg = yaml.safe_load((ROOT / "docs" / "experiments.yaml").read_text(encoding="utf-8"))
        rows = reg["experiments"] if isinstance(reg, dict) else reg
        cta = next(e for e in rows if e["id"] == "shorts-subscribe-cta")
        assert cta["metric"] == "short_subs_per_1k_views_14d_en"


class TestDubGateMetric:
    """Sep 22 2026: dub spoken-text gate fail share — null under 10 tracks."""

    def _root(self, tmp_path, rows):
        (tmp_path / "api").mkdir()
        (tmp_path / "api" / "youtube_stats.json").write_text(json.dumps({
            "generated": "2026-09-22T14:00:00Z", "channels": {}, "shows": {}}), encoding="utf-8")
        d = tmp_path / "digests" / "x"
        d.mkdir(parents=True)
        (d / "spoken_text_gate.ru.json").write_text(json.dumps({
            "schema_version": 1, "lang": "ru",
            "episodes": {str(i): {"gate": g, "generated_at": "2026-09-20T00:00:00+00:00"}
                         for i, g in enumerate(rows)}}), encoding="utf-8")
        return tmp_path

    def test_null_under_ten_tracks(self, tmp_path):
        m = gd._experiment_live_metrics(self._root(tmp_path, ["pass"] * 9))
        assert m["dub_gate_fail_share_14d"] is None and m["dub_gate_tracks_14d"] == 9

    def test_share_counts_only_gated_rows(self, tmp_path):
        rows = ["pass"] * 8 + ["fail_shadow"] * 2 + ["no_transcript", "off", "error"]
        m = gd._experiment_live_metrics(self._root(tmp_path, rows))
        assert m["dub_gate_tracks_14d"] == 10 and m["dub_gate_fail_share_14d"] == 0.2

    def test_no_sidecars_is_unmeasured(self, tmp_path):
        (tmp_path / "api").mkdir(); (tmp_path / "digests").mkdir()
        m = gd._experiment_live_metrics(tmp_path)
        assert m["dub_gate_fail_share_14d"] is None and m["dub_gate_tracks_14d"] is None


class TestTrafficMix:
    """Sep 22 2026: the traffic-source instrument — null until the series exists."""

    def _root(self, tmp_path, series):
        (tmp_path / "api").mkdir()
        (tmp_path / "digests").mkdir()
        (tmp_path / "api" / "youtube_stats.json").write_text(json.dumps({
            "generated": "2026-09-22T14:00:00Z",
            "channels": {"en": {"day_series": [], "traffic_day_series": series},
                         "ru": {"day_series": []}},
            "shows": {}}), encoding="utf-8")
        return tmp_path

    def test_null_without_the_series(self, tmp_path):
        sec = gd.build_traffic_mix_section(self._root(tmp_path, []))
        assert sec["configured"] is False
        assert gd._experiment_live_metrics(tmp_path)["shorts_feed_share_7d_en"] is None

    def test_shares_and_lag_trim(self, tmp_path):
        series = []
        for i in range(30):
            series.append({"day": f"2026-09-{(i % 30) + 1:02d}", "SHORTS": 60, "SUBSCRIBER": 30,
                           "YT_SEARCH": 5, "RELATED_VIDEO": 5, "other": 0, "total": 100})
        series.sort(key=lambda d: d["day"])
        series[-1]["SHORTS"] = 0      # the unreported tail must be trimmed
        series[-2]["SHORTS"] = 0
        sec = gd.build_traffic_mix_section(self._root(tmp_path, series))
        en = sec["channels"]["en"]
        assert sec["configured"] is True and en["as_of"] == "2026-09-28"
        assert en["shorts_share_7d"] == 0.6 and en["shorts_share_prior_7d"] == 0.6
        assert len(en["weeks"]) == 4 and all(0 <= w["shorts_share"] <= 1 for w in en["weeks"])
        assert sec["channels"]["ru"]["configured"] is False
        assert gd._experiment_live_metrics(tmp_path)["shorts_feed_share_7d_en"] == 0.6

    def test_card_is_rendered(self):
        html = (ROOT / "management.html").read_text(encoding="utf-8")
        assert "Traffic mix (by source)" in html and "growth.traffic_mix" in html


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


class TestSpokenOpenArmSplit:
    """Sep 22 2026: the spoken-open shape is staged on three shows; the
    open hold is read per arm, and the network-wide key is never reopened
    (long-open-cliff's outcome)."""

    def _root(self, tmp_path, videos):
        (tmp_path / "api").mkdir()
        (tmp_path / "api" / "youtube_stats.json").write_text(json.dumps({
            "generated": "2026-09-22T14:00:00Z",
            "channels": {"en": {"day_series": []}},
            "shows": {"x": {"videos": videos}},
        }), encoding="utf-8")
        (tmp_path / "digests").mkdir()
        return tmp_path

    def _video(self, slug, hold, ch="en"):
        return {"kind": "long", "channel": ch, "show_slug": slug,
                "published": "2026-09-20",
                "retention_curve": [{"t": 0.0, "ratio": 1.0}, {"t": 0.05, "ratio": hold},
                                    {"t": 0.1, "ratio": hold / 2}]}

    def test_arm_and_control_split_by_show_slug(self, tmp_path):
        vids = [self._video("tesla", 0.6), self._video("spacex", 0.5),
                self._video("omni_view", 0.3), self._video("models_agents", 0.4),
                self._video("tesla", 0.9, ch="ru")]   # dubs never count
        m = gd._experiment_live_metrics(self._root(tmp_path, vids))
        assert m["long_open_hold_5pct_arm"] == 0.55
        assert m["long_open_hold_5pct_control"] == 0.35
        assert m["long_open_hold_5pct_en"] == 0.45

    def test_null_when_no_curves(self, tmp_path):
        m = gd._experiment_live_metrics(self._root(tmp_path, []))
        assert m["long_open_hold_5pct_arm"] is None
        assert m["long_open_hold_5pct_control"] is None

    def test_no_new_entry_reopens_long_open_hold_5pct_en(self):
        data = yaml.safe_load((ROOT / "docs" / "experiments.yaml").read_text(encoding="utf-8"))
        for e in data["experiments"]:
            if e.get("metric") == "long_open_hold_5pct_en":
                assert str(e.get("shipped")) < "2026-09-22", (
                    f"{e['id']} reopens long_open_hold_5pct_en; score the arm metric")
