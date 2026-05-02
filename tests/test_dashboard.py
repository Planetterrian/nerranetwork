"""Tests for scripts/generate_dashboard.py.

Six regression guards per the approved plan. The most important guarantees
encoded here are:

1. Models & Agents and Models & Agents for Beginners are ALWAYS loaded as
   two distinct shows. No future refactor is allowed to collapse them.
2. Landmine items 7 (NEWSAPI dead secret) and 10 (early-episode deletion)
   are never emitted by the dashboard generator.
3. Item 2 correctly fails when any RSS enclosure points at raw.githubusercontent.com
   (the LFS trap documented in CLAUDE.md).
4. Item 9 voice drift detection picks up per-show drift AND CLAUDE.md
   documentation drift (the 0.65/0.9/0.85 triple).
"""
from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts import generate_dashboard as gd


# ---------------------------------------------------------------------------
# Test 1 — MA and MAB stay strictly separate
# ---------------------------------------------------------------------------


def test_mab_and_ma_are_separate():
    """The generator must load models_agents and models_agents_beginners as
    two distinct shows with distinct RSS files and distinct slugs. This test
    is the canary against any future refactor that tries to merge them."""
    shows = gd.load_shows_from_yaml(ROOT / "shows", ROOT)
    slugs = [s["slug"] for s in shows]

    assert "models_agents" in slugs, "models_agents must load"
    assert "models_agents_beginners" in slugs, "models_agents_beginners must load"

    ma = next(s for s in shows if s["slug"] == "models_agents")
    mab = next(s for s in shows if s["slug"] == "models_agents_beginners")

    # Distinct identities at every layer.
    assert ma["slug"] != mab["slug"]
    assert ma["name"] != mab["name"]
    assert ma["cfg"].publishing.rss_file != mab["cfg"].publishing.rss_file
    assert ma["cfg"].publishing.rss_title != mab["cfg"].publishing.rss_title
    # Each must resolve tts.provider to grok on its own (network default
    # since May 2026; the original "elevenlabs" assertion regressed when
    # the network flipped — see CLAUDE.md landmines #11 and #16).
    assert ma["cfg"].tts.provider == "grok"
    assert mab["cfg"].tts.provider == "grok"


# ---------------------------------------------------------------------------
# Test 2 — items 7 and 10 are intentionally excluded
# ---------------------------------------------------------------------------


def test_landmine_items_7_and_10_excluded():
    """Per the approved plan, items 7 (NEWSAPI dead secret) and 10 (early
    episode deletion) must never be emitted as landmines on the dashboard."""
    data = gd.build_dashboard(ROOT, offline=True)
    ids = {lm["id"] for lm in data["landmines"]}
    for forbidden in ("item_7_newsapi", "item_7_newsapi_dead_secret",
                      "item_10_early_episodes", "item_10_early_episode_deletion"):
        assert forbidden not in ids, f"{forbidden} must not be emitted"


# ---------------------------------------------------------------------------
# Test 3 — item 1 passes on a clean-ish repo
# ---------------------------------------------------------------------------


def test_landmine_item_1_passes_on_small_checkout(monkeypatch):
    """Item 1 should report ok when the git-tracked MP3 count is low and the
    digests/ footprint is below the warn threshold."""
    monkeypatch.setattr(gd, "_git_tracked_mp3_count", lambda root: 5)
    monkeypatch.setattr(gd, "_dir_bytes", lambda path: 100 * 1024 * 1024)  # 100 MB

    result = gd.item_1_repo_size(ROOT)
    assert result["id"] == "item_1_repo_size"
    assert result["status"] == "ok"
    assert result["evidence"]["tracked_mp3_count"] == 5


# ---------------------------------------------------------------------------
# Test 4 — item 2 flags a raw.githubusercontent.com enclosure
# ---------------------------------------------------------------------------


def test_item_2_flags_raw_githubusercontent(tmp_path):
    """If any enclosure is still served from raw.githubusercontent.com (the
    LFS trap), item 2 must fail the dashboard."""
    # Build a tiny RSS feed with one offending enclosure.
    rss = tmp_path / "evil_podcast.rss"
    rss.write_text(
        """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <title>Evil Test Feed</title>
    <item>
      <title>Episode 1</title>
      <pubDate>Fri, 10 Apr 2026 08:00:00 +0000</pubDate>
      <enclosure url="https://raw.githubusercontent.com/x/y/main/ep1.mp3"
                 type="audio/mpeg" length="1000"/>
      <guid isPermaLink="false">evil-ep1</guid>
    </item>
  </channel>
</rss>
""",
        encoding="utf-8",
    )
    audit = gd.audit_rss_enclosures(tmp_path, offline=True)
    assert audit["raw_github_hits"], "expected at least one raw.githubusercontent.com hit"
    result = gd.item_2_rss_integrity(audit)
    assert result["status"] == "fail"
    assert "raw.githubusercontent.com" in result["details"]


# ---------------------------------------------------------------------------
# Test 5 — item 9 voice drift is detected per show
# ---------------------------------------------------------------------------


def test_item_9_voice_drift_detected(tmp_path):
    """audit_voice_config must report per-show drift when a show's
    tts.stability diverges from shows/_defaults.yaml."""
    # Create a minimal tree: shows/_defaults.yaml + one show yaml that drifts.
    shows_dir = tmp_path / "shows"
    shows_dir.mkdir()
    (shows_dir / "_defaults.yaml").write_text(
        "tts:\n  voice_id: dTrBzPvD2GpAqkk1MUzA\n  stability: 0.5\n"
        "  similarity_boost: 0.75\n  style: 0.0\n",
        encoding="utf-8",
    )
    (shows_dir / "drifty.yaml").write_text(
        "name: Drifty\nslug: drifty\n"
        "tts:\n  stability: 0.9\n  similarity_boost: 0.75\n  style: 0.0\n",
        encoding="utf-8",
    )

    # A synthetic show object that mimics gd.load_shows_from_yaml output.
    from engine.config import load_config
    cfg = load_config(str(shows_dir / "drifty.yaml"))
    synthetic = [{
        "slug": "drifty",
        "name": "Drifty",
        "cfg": cfg,
        "raw_yaml": {},
    }]

    voice = gd.audit_voice_config(synthetic, tmp_path)
    drifty = next(r for r in voice["shows"] if r["slug"] == "drifty")
    assert any(d["field"] == "stability" and d["actual"] == 0.9 for d in drifty["drift"]), \
        f"expected stability drift, got {drifty['drift']}"

    # And the landmine card must escalate from ok to warn.
    lm = gd.item_9_voice_settings(voice)
    assert lm["status"] == "warn"


# ---------------------------------------------------------------------------
# Test 6 — CLAUDE.md drift banner fires while 0.65/0.9/0.85 is still present
# ---------------------------------------------------------------------------


def test_item_3_escalates_to_fail_on_growth(tmp_path):
    """Item 3 must FAIL (not warn) when the top-level flat-file count
    has grown since the previously recorded baseline.

    This is the CI guard for CLAUDE.md landmine #3 — grandfathered flat
    files are tolerated but may never grow, because any new file at
    digests/<top level> means the pipeline leaked a write out of its
    per-show subdirectory.
    """
    digests = tmp_path / "digests"
    digests.mkdir()
    # Seed 3 grandfathered files.
    (digests / "legacy1.mp3").write_bytes(b"\x00")
    (digests / "legacy2.md").write_text("x", encoding="utf-8")
    (digests / "legacy3.txt").write_text("x", encoding="utf-8")

    # Baseline run — no previous count, count = 3, should warn.
    warn = gd.item_3_legacy_flatfiles(tmp_path, previous=None)
    assert warn["status"] == "warn"
    assert warn["evidence"]["total"] == 3

    # Same count as previous — stays warn.
    still = gd.item_3_legacy_flatfiles(tmp_path, previous=3)
    assert still["status"] == "warn"

    # One new file appears — growth detected, MUST fail.
    (digests / "leaked.mp3").write_bytes(b"\x00")
    grew = gd.item_3_legacy_flatfiles(tmp_path, previous=3)
    assert grew["status"] == "fail", \
        "growth from 3 → 4 must escalate to FAIL to trip the CI guard"
    assert "GREW" in grew["details"]
    assert grew["evidence"]["total"] == 4


def test_claude_md_drift_banner_fires_when_stale_triple_present():
    """While CLAUDE.md still mentions the old 0.65/0.9/0.85 triple AND
    shows/_defaults.yaml no longer matches, the dashboard's voice_config
    must set claude_md_drift_detected=True.

    This test is the enforcement mechanism: once CLAUDE.md is updated to
    remove the stale triple, the test keeps passing (it only asserts the
    banner is on *while* the drift is real; the banner flipping off is fine
    because the script no longer sets it and the test no longer runs through
    this path)."""
    claude = (ROOT / "CLAUDE.md").read_text(encoding="utf-8", errors="replace")
    defaults = (ROOT / "shows" / "_defaults.yaml").read_text(encoding="utf-8")

    if "0.65/0.9/0.85" not in claude:
        pytest.skip("CLAUDE.md no longer references the stale voice triple")
    if "stability: 0.65" in defaults:
        pytest.skip("_defaults.yaml was rolled back to the old triple; not a drift scenario")

    shows = gd.load_shows_from_yaml(ROOT / "shows", ROOT)
    voice = gd.audit_voice_config(shows, ROOT)
    assert voice["claude_md_drift_detected"] is True

    lm = gd.item_9_voice_settings(voice)
    assert lm["status"] in ("warn", "fail")
    assert "CLAUDE.md" in lm["details"]
