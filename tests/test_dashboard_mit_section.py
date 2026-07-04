"""Tests for ``aggregate_mit_performance`` in scripts/generate_dashboard.py.

Verifies the shape and defaults of the ``mit_performance`` block that
powers both the operator dashboard (management.html) and the public
show page (modern-investing.html via the show template).
"""
from __future__ import annotations

import datetime
import json
from pathlib import Path

import pytest

from scripts.generate_dashboard import aggregate_mit_performance


def _write_mit(tmp_path: Path, *, tracker: dict, taught: dict | None = None, lessons: dict | None = None) -> Path:
    """Seed a temp repo-root with MIT JSON files and return the root."""
    mit_dir = tmp_path / "digests" / "modern_investing"
    mit_dir.mkdir(parents=True, exist_ok=True)
    (mit_dir / "investment_tracker.json").write_text(json.dumps(tracker), encoding="utf-8")
    if taught is not None:
        (mit_dir / "taught_lessons.json").write_text(json.dumps(taught), encoding="utf-8")
    if lessons is not None:
        (mit_dir / "lessons_learned.json").write_text(json.dumps(lessons), encoding="utf-8")
    return tmp_path


class TestMissingData:
    def test_no_tracker_returns_unavailable(self, tmp_path: Path):
        result = aggregate_mit_performance(tmp_path)
        assert result["available"] is False
        assert result["trades"] == []
        assert result["summary"] == {}

    def test_corrupt_tracker_returns_unavailable(self, tmp_path: Path):
        mit_dir = tmp_path / "digests" / "modern_investing"
        mit_dir.mkdir(parents=True, exist_ok=True)
        (mit_dir / "investment_tracker.json").write_text("{not json", encoding="utf-8")
        result = aggregate_mit_performance(tmp_path)
        assert result["available"] is False


class TestNormalisedShape:
    def test_benchmark_subkeys_always_present(self, tmp_path: Path):
        """Older trackers lack 'benchmark' — aggregator must still return the subkeys."""
        root = _write_mit(tmp_path, tracker={
            "metadata": {}, "summary": {}, "trades": [],
        })
        result = aggregate_mit_performance(root)
        for k in ("current_close", "ytd_pct", "inception_to_date_pct", "last_updated"):
            assert k in result["benchmark"], f"benchmark missing {k}"
        for k in ("ytd_pct", "inception_to_date_pct", "monthly"):
            assert k in result["alpha"], f"alpha missing {k}"

    def test_trades_newest_first_capped_at_100(self, tmp_path: Path):
        trades = [
            {
                "episode_num": i,
                "date": f"2026-01-{(i % 28) + 1:02d}",
                "symbol": f"T{i}",
                "status": "closed",
                "pnl_pct": 1.0,
            }
            for i in range(120)
        ]
        root = _write_mit(tmp_path, tracker={
            "metadata": {}, "summary": {}, "trades": trades,
        })
        result = aggregate_mit_performance(root)
        assert len(result["trades"]) == 100
        # Newest first: date strings sort lexically — highest day first
        dates = [t["date"] for t in result["trades"]]
        assert dates == sorted(dates, reverse=True)

    def test_trades_expose_alpha_and_sector(self, tmp_path: Path):
        root = _write_mit(tmp_path, tracker={
            "metadata": {}, "summary": {},
            "trades": [{
                "episode_num": 7,
                "date": "2026-04-01",
                "symbol": "WDC",
                "sector": "tech",
                "pnl_pct": 4.44,
                "nasdaq_return_pct": 2.1,
                "alpha_pct": 2.34,
                "lesson_tags": ["momentum_entry"],
                "status": "closed",
            }],
        })
        result = aggregate_mit_performance(root)
        trade = result["trades"][0]
        assert trade["sector"] == "tech"
        assert trade["alpha_pct"] == 2.34
        assert trade["lesson_tags"] == ["momentum_entry"]


class TestSectorConcentrationWarning:
    def test_fires_at_30_percent_threshold(self, tmp_path: Path):
        root = _write_mit(tmp_path, tracker={
            "metadata": {}, "summary": {},
            "trades": [],
            "sectors": {
                "precious_metals": {"trade_count": 4, "exposure_pct": 40.0, "cumulative_pnl": -10.5},
                "tech": {"trade_count": 3, "exposure_pct": 30.0, "cumulative_pnl": 25.0},
                "energy": {"trade_count": 3, "exposure_pct": 30.0, "cumulative_pnl": 0.0},
            },
        })
        result = aggregate_mit_performance(root)
        assert "precious_metals" in result["sector_concentration_warning"]

    def test_balanced_no_warning(self, tmp_path: Path):
        root = _write_mit(tmp_path, tracker={
            "metadata": {}, "summary": {},
            "trades": [],
            "sectors": {
                "tech": {"trade_count": 2, "exposure_pct": 20.0, "cumulative_pnl": 0.0},
                "financials": {"trade_count": 3, "exposure_pct": 20.0, "cumulative_pnl": 0.0},
            },
        })
        result = aggregate_mit_performance(root)
        assert result["sector_concentration_warning"] == ""


class TestLessonsLearned:
    def test_returns_active_only_newest_first(self, tmp_path: Path):
        root = _write_mit(
            tmp_path,
            tracker={"metadata": {}, "summary": {}, "trades": []},
            lessons={
                "metadata": {"schema_version": 1},
                "entries": [
                    {"id": "LL-001", "date": "2026-01-01", "status": "retired",
                     "observation": "old", "adjustment": "none"},
                    {"id": "LL-002", "date": "2026-04-01", "status": "active",
                     "observation": "obs2", "adjustment": "adj2"},
                    {"id": "LL-003", "date": "2026-04-10", "status": "active",
                     "observation": "obs3", "adjustment": "adj3"},
                ],
            },
        )
        result = aggregate_mit_performance(root)
        ids = [e["id"] for e in result["lessons_learned"]]
        assert ids == ["LL-003", "LL-002"]

    def test_capped_at_ten(self, tmp_path: Path):
        entries = [
            {"id": f"LL-{i:03d}", "date": f"2026-04-{i:02d}", "status": "active",
             "observation": f"o{i}", "adjustment": f"a{i}"}
            for i in range(1, 16)
        ]
        root = _write_mit(
            tmp_path,
            tracker={"metadata": {}, "summary": {}, "trades": []},
            lessons={"metadata": {}, "entries": entries},
        )
        result = aggregate_mit_performance(root)
        assert len(result["lessons_learned"]) == 10


class TestTaughtLessonsHot:
    def test_includes_tags_inside_cooldown(self, tmp_path: Path):
        today_iso = datetime.date.today().isoformat()
        root = _write_mit(
            tmp_path,
            tracker={"metadata": {}, "summary": {}, "trades": []},
            taught={
                "metadata": {},
                "cooldown_days_default": 21,
                "lessons": {
                    "bid_ask_spread": {
                        "count": 6, "last_episode": 21, "last_date": today_iso,
                        "cooldown_days": 45,
                    },
                    "old_thing": {
                        "count": 1, "last_episode": 1,
                        "last_date": (datetime.date.today() - datetime.timedelta(days=60)).isoformat(),
                        "cooldown_days": 21,
                    },
                },
            },
        )
        result = aggregate_mit_performance(root)
        tags = [t["tag"] for t in result["taught_lessons_hot"]]
        assert "bid_ask_spread" in tags
        assert "old_thing" not in tags  # expired

    def test_empty_when_no_cooldown(self, tmp_path: Path):
        root = _write_mit(
            tmp_path,
            tracker={"metadata": {}, "summary": {}, "trades": []},
            taught={"metadata": {}, "cooldown_days_default": 21, "lessons": {}},
        )
        result = aggregate_mit_performance(root)
        assert result["taught_lessons_hot"] == []


class TestBuildDashboardIntegration:
    def test_build_dashboard_includes_mit_key(self, tmp_path: Path, monkeypatch):
        """End-to-end check: build_dashboard surfaces mit_performance."""
        # Minimal shows/ so load_shows_from_yaml doesn't explode
        (tmp_path / "shows").mkdir()
        (tmp_path / "shows" / "_defaults.yaml").write_text(
            "llm:\n  provider: xai\n  model: grok-4.20-non-reasoning\n"
            "tts:\n  provider: elevenlabs\n  voice_id: V1\n"
            "  stability: 0.5\n  similarity_boost: 0.75\n  style: 0.0\n",
            encoding="utf-8",
        )
        _write_mit(tmp_path, tracker={"metadata": {}, "summary": {}, "trades": []})

        from scripts.generate_dashboard import build_dashboard
        result = build_dashboard(tmp_path, offline=True)
        assert "mit_performance" in result
        assert result["mit_performance"]["available"] is True


class TestExecutionHealth:
    """July 2026 live-trading prep: the dashboard surfaces signal
    freshness + shadow-ledger vitals so the operator sees at a glance
    whether the execution bridge artifacts are flowing."""

    def test_execution_health_none_when_artifacts_missing(self, tmp_path: Path):
        root = _write_mit(tmp_path, tracker={
            "metadata": {}, "summary": {}, "trades": [],
        })
        result = aggregate_mit_performance(root)
        assert result["execution_health"] == {"signal": None, "shadow": None}

    def test_signal_freshness_and_staleness(self, tmp_path: Path):
        root = _write_mit(tmp_path, tracker={
            "metadata": {}, "summary": {}, "trades": [],
        })
        mit_dir = root / "digests" / "modern_investing"
        (mit_dir / "trade_signal_latest.json").write_text(json.dumps({
            "schema_version": 1, "generated_at": "2020-01-01",
            "action": "new_trade",
            "trade": {"snaptrade_symbol": "CNR.TO"},
        }), encoding="utf-8")
        result = aggregate_mit_performance(root)
        sig = result["execution_health"]["signal"]
        assert sig["action"] == "new_trade"
        assert sig["symbol"] == "CNR.TO"
        assert sig["stale"] is True  # ancient signal must be flagged

    def test_shadow_ledger_vitals(self, tmp_path: Path):
        root = _write_mit(tmp_path, tracker={
            "metadata": {}, "summary": {}, "trades": [],
        })
        mit_dir = root / "digests" / "modern_investing"
        (mit_dir / "shadow_ledger.json").write_text(json.dumps({
            "schema_version": 1, "mode": "shadow", "orders": [
                {"decision": "would_place", "logged_at": "2026-07-06T13:50:00+00:00"},
                {"decision": "skipped", "logged_at": "2026-07-07T13:50:00+00:00"},
                {"decision": "would_sell", "shadow_return_pct": 2.5,
                 "logged_at": "2026-07-10T13:50:00+00:00"},
            ],
        }), encoding="utf-8")
        result = aggregate_mit_performance(root)
        sh = result["execution_health"]["shadow"]
        assert sh["orders"] == 3
        assert sh["decisions"] == {"would_place": 1, "skipped": 1,
                                   "would_sell": 1}
        assert sh["round_trips"] == 1
        assert sh["avg_round_trip_pct"] == 2.5
        assert sh["last_logged_at"] == "2026-07-10T13:50:00+00:00"
