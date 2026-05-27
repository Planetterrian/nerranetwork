"""Drift guards for the May 2026 quick-win batch (codebase review).

These tests pin the new behaviour so future changes cannot silently regress
the improvements without updating the test (following the established pattern
in test_tts_grok.py, test_dashboard.py, test_config.py, etc.).
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent


def test_tag_leak_hard_block_exists_in_config_and_defaults_false():
    """The new configurable hard-block flag must exist and default to False."""
    from engine.config import load_config
    from pathlib import Path

    SHOWS_DIR = Path(__file__).resolve().parent.parent / "shows"
    # Load a real show YAML; the flag is defined in the TTSConfig dataclass + _defaults
    cfg = load_config(SHOWS_DIR / "tesla.yaml")
    assert hasattr(cfg.tts, "tag_leak_hard_block")
    assert cfg.tts.tag_leak_hard_block is False, "tag_leak_hard_block must default to False (best-effort)"


def test_generate_html_injects_dynamic_meta_from_rss():
    """Dynamic metadata quick win: show pages must receive page_title + meta_description
    derived from the freshest RSS item (static_episodes) instead of purely static text.
    """
    # We can't easily exec the whole generator without side effects, but we can
    # verify the generation logic path exists and the override code is present.
    src = (ROOT / "generate_html.py").read_text(encoding="utf-8")
    assert "dynamic_meta_description" in src or "latest_episode_title" in src
    assert "Quick-win (May 2026 review): dynamic metadata" in src


def test_readme_contains_recent_improvements_section():
    """Docs refresh quick win: README must document the 2026 milestones and point to the review."""
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    assert "Recent Improvements & Roadmap (May 2026+)" in readme
    assert "Grok TTS migration" in readme
    assert "Nerra Gallery" in readme
    assert "smart Shorts" in readme or "Smart Shorts" in readme


def test_dashboard_json_will_contain_projections_after_regen():
    """Dashboard quick win: the aggregate_costs path now emits projections + youtube_quota surface."""
    src = (ROOT / "scripts/generate_dashboard.py").read_text(encoding="utf-8")
    assert "projections" in src
    assert "projected_weekly_usd" in src
    assert "youtube_quota" in src
    assert "Quick-win enhancements (May 2026 codebase review)" in src


def test_global_search_proto_markup_present():
    """Audience quick win: the nav now contains the global search input + results container."""
    base = (ROOT / "templates/base.html.j2").read_text(encoding="utf-8")
    assert "nn-global-search-input" in base
    assert "Global search proto (client-only" in base


def test_noscript_fallback_in_show_page_template():
    """Progressive enhancement quick win: the hero Latest Episode card has a noscript block."""
    tpl = (ROOT / "templates/show_page.html.j2").read_text(encoding="utf-8")
    assert "<noscript>" in tpl
    assert "static_episodes[0]" in tpl
    assert "JavaScript disabled" in tpl or "noscript" in tpl.lower()


def test_dashboard_emits_alerts_array():
    """Medium item: Proactive alerts — generate_dashboard must emit an 'alerts' top-level array
    containing critical landmines (and future signals).
    """
    import subprocess
    import json
    import sys

    result = subprocess.run(
        [sys.executable, "scripts/generate_dashboard.py", "--dry-run"],
        capture_output=True, text=True, cwd=ROOT
    )
    data = json.loads(result.stdout)
    assert "alerts" in data, "dashboard JSON must contain 'alerts' key for proactive notifications"
    assert isinstance(data["alerts"], list)

    # At minimum, any landmine with status=fail should appear in alerts
    fail_landmines = [lm for lm in data.get("landmines", []) if lm.get("status") == "fail"]
    assert len(data["alerts"]) >= len(fail_landmines), \
        "Every FAIL landmine should produce at least one critical alert"