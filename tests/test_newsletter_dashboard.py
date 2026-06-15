"""Guards for the per-show newsletter 'By the numbers' dashboard block
(June 2026: surface live dashboard data in the SpaceX/Tesla/MIT newsletters)."""

from __future__ import annotations

import json
from pathlib import Path

from engine.newsletter_dashboard import build_dashboard_stats


def _write(root: Path, rel: str, obj) -> None:
    p = root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(obj), encoding="utf-8")


def test_spacex_stats(tmp_path):
    _write(tmp_path, "api/spcx.json", {"price": 160.95, "prev_close": None})
    _write(tmp_path, "api/spacex_launches.json",
           {"stats": {"launches_ytd": 70}, "fleet": {"starlink_active": 10544}})
    stats = build_dashboard_stats("spacex", tmp_path)
    labels = {s["label"]: s["value"] for s in stats}
    assert labels["SPCX price"] == "$160.95"
    assert labels["Launches this year"] == "70"
    assert labels["Active Starlink sats"] == "10,544"
    assert len(stats) <= 3


def test_tesla_stats(tmp_path):
    _write(tmp_path, "api/tesla_dashboard.json", {"price": 406.43, "change_pct": 0.08})
    _write(tmp_path, "site/data/tesla_metrics.json",
           {"deliveries_annual": [{"year": "2023", "vehicles": 1808581},
                                   {"year": "2024", "vehicles": 1789226}]})
    labels = {s["label"]: s["value"] for s in build_dashboard_stats("tesla", tmp_path)}
    assert labels["TSLA price"] == "$406.43"
    assert labels["TSLA today"] == "+0.08%"
    assert labels["2024 deliveries"] == "1.79M"


def test_modern_investing_stats(tmp_path):
    _write(tmp_path, "api/dashboard.json", {"mit_performance": {"summary": {
        "cumulative_alpha_vs_nasdaq": 21.23, "win_rate_pct": 58.8, "total_trades": 34}}})
    labels = {s["label"]: s["value"] for s in build_dashboard_stats("modern_investing", tmp_path)}
    assert labels["Alpha vs NASDAQ"] == "+21.2%"
    assert labels["Win rate"] == "59%"
    assert labels["Simulated trades"] == "34"


def test_unmapped_show_returns_empty(tmp_path):
    assert build_dashboard_stats("omni_view", tmp_path) == []


def test_missing_data_is_safe(tmp_path):
    # No data files at all → empty, never raises.
    assert build_dashboard_stats("spacex", tmp_path) == []


def test_nan_and_zero_values_skipped(tmp_path):
    # Non-finite / zero prices must not render as 'nan' or '$0.00'.
    _write(tmp_path, "api/spcx.json", {"price": 0})
    _write(tmp_path, "api/spacex_launches.json", {"stats": {"launches_ytd": 0}, "fleet": {}})
    assert build_dashboard_stats("spacex", tmp_path) == []
    _write(tmp_path, "api/dashboard.json", {"mit_performance": {"summary": {
        "cumulative_alpha_vs_nasdaq": float("nan"), "win_rate_pct": 58.8}}})
    labels = {s["label"] for s in build_dashboard_stats("modern_investing", tmp_path)}
    assert "Alpha vs NASDAQ" not in labels  # NaN dropped
    assert "Win rate" in labels


def test_wired_into_send_show_newsletter():
    src = (Path(__file__).resolve().parent.parent / "engine" / "newsletter.py").read_text(encoding="utf-8")
    assert "by_the_numbers=_dashboard_stats_for(slug)" in src


def test_block_renders_in_branded_body():
    from engine.newsletter_template import wrap_with_branding
    stats = [{"value": "$160.95", "label": "SPCX price"}]
    body = wrap_with_branding("spacex", "Body.", daily_label="Ep 4", by_the_numbers=stats)
    assert "By the numbers" in body and "SPCX price" in body


def test_spacex_and_first_principles_newsletters_configured():
    """June 15 2026: operator created the 'SpaceX Daily' + 'First Principles
    Daily' Buttondown tags and asked for both shows' newsletters live. Pin that
    each is enabled with a tag that matches the created Buttondown tag exactly
    (a mismatch silently blocks the send — see the Jun 15 SpaceX incident)."""
    from engine.config import load_config
    expected = {
        "spacex": "SpaceX Daily",
        "first_principles": "First Principles Daily",
    }
    for slug, tag in expected.items():
        cfg = load_config(Path(__file__).resolve().parent.parent / "shows" / f"{slug}.yaml")
        n = cfg.newsletter
        assert n.enabled is True, f"{slug} newsletter must be enabled"
        assert n.tag == tag, f"{slug} tag {n.tag!r} must match Buttondown tag {tag!r}"
        assert n.api_key_env == "BUTTONDOWN_API_KEY"
        assert n.short_label and n.emoji, f"{slug} needs short_label + emoji"
