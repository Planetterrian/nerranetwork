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


def test_item_11_expects_grok_provider_post_may_2026():
    """The May 2026 full-network migration moved every show to Grok TTS
    (CLAUDE.md landmine #17). The dashboard's item_11 invariant flipped
    from `provider == elevenlabs` (pre-migration) to `provider == grok`
    (current). This test pins the post-migration state so a copy-paste
    from the old YAML wouldn't silently revert the dashboard signal."""
    data = gd.build_dashboard(ROOT, offline=True)
    item_11 = next(
        (lm for lm in data["landmines"] if lm["id"] == "item_11_tts_provider"),
        None,
    )
    assert item_11 is not None, "item_11_tts_provider must be emitted"
    # Title and details must reflect Grok, not the old ElevenLabs check.
    assert "Grok" in item_11["title"], (
        f"item_11 title still references the pre-May-2026 expectation: "
        f"{item_11['title']!r}"
    )
    assert "grok" in item_11["details"].lower()
    # All 11 shows currently resolve to grok → status is ok.
    assert item_11["status"] == "ok", (
        f"All shows should resolve tts.provider == grok post-May 2026; "
        f"got status={item_11['status']!r}"
    )


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


def test_network_meta_and_scaffold_pending_excluded_from_shows():
    """``shows/network_meta.yaml`` and ``shows/scaffold_pending.yaml``
    are network-level helper YAMLs (cross-show metadata + pending
    scaffold-script state), NOT real shows. Loading them as shows
    pulls in the ``digests`` default for ``episode.output_dir`` /
    ``publishing.audio_subdir``, which the item_4_output_dirs
    landmine check then flags as a violation. That landmine has
    been firing FAIL on the management dashboard workflow on every
    daily run, blocking the workflow + spamming notifications.
    Regression guard: keep both files in ``_NON_SHOW_YAMLS`` so
    they never end up in the shows list."""
    import scripts.generate_dashboard as gd
    assert "network_meta" in gd._NON_SHOW_YAMLS, (
        "network_meta.yaml is a cross-show metadata file, not a show "
        "— include it in _NON_SHOW_YAMLS or item_4_output_dirs will "
        "fire FAIL on every dashboard run"
    )
    assert "scaffold_pending" in gd._NON_SHOW_YAMLS, (
        "scaffold_pending.yaml is scaffold-script state, not a show"
    )


def test_item_4_output_dirs_no_violations_on_real_shows(tmp_path, monkeypatch):
    """End-to-end: with the fixed ``_NON_SHOW_YAMLS`` set, the
    item_4_output_dirs check should report ``ok`` against the
    actual repo state. If this fails the dashboard workflow's
    final ``Fail the job on landmine FAIL`` step will fail again."""
    from pathlib import Path

    import scripts.generate_dashboard as gd

    repo_root = Path(__file__).resolve().parents[1]
    shows = gd.load_shows_from_yaml(repo_root / "shows", repo_root)
    result = gd.item_4_output_dirs(shows)
    assert result["status"] in ("ok", "warn"), (
        f"item_4_output_dirs still FAIL: {result.get('details')} "
        f"violations={result.get('evidence', {}).get('violations')}"
    )


# ---------------------------------------------------------------------------
# Audience section (June 2026 growth pass) — OP3 + Buttondown read-back
# ---------------------------------------------------------------------------


def test_audience_section_graceful_when_stats_missing(tmp_path):
    """A repo without api/op3_stats.json / api/buttondown_stats.json must
    still build a dashboard, with the audience section reporting
    configured: false (the management card renders a setup hint)."""
    section = gd.build_audience_section(tmp_path)
    assert section["op3"] == {"configured": False}
    assert section["newsletter"] == {"configured": False}


def test_audience_section_summarises_stats(tmp_path):
    import json as _json

    api_dir = tmp_path / "api"
    api_dir.mkdir()
    (api_dir / "op3_stats.json").write_text(_json.dumps({
        "fetched_at": "2026-06-10T00:00:00+00:00",
        "shows": {
            "tesla": {
                "downloads_7d": 149, "downloads_30d": 616, "weekly_avg": 150,
                "episodes": [
                    {"title": "Big ep", "downloads_7d": 12},
                    {"title": "Small ep", "downloads_7d": 1},
                ],
            },
            "env_intel": {
                "downloads_7d": 11, "downloads_30d": 24, "weekly_avg": 11,
                "episodes": [],
            },
        },
    }), encoding="utf-8")
    (api_dir / "buttondown_stats.json").write_text(_json.dumps({
        "fetched_at": "2026-06-10T00:00:00+00:00",
        "subscriber_count": 257,
    }), encoding="utf-8")

    section = gd.build_audience_section(tmp_path)

    assert section["op3"]["configured"] is True
    assert section["op3"]["network_downloads_30d"] == 640
    assert section["op3"]["network_downloads_7d"] == 160
    assert section["op3"]["per_show"]["tesla"]["downloads_30d"] == 616
    assert section["op3"]["top_episodes_7d"][0]["title"] == "Big ep"
    assert section["newsletter"]["subscriber_count"] == 257


def test_audience_section_in_dashboard_payload():
    data = gd.build_dashboard(ROOT, offline=True)
    assert "audience" in data, (
        "build_dashboard must always emit the audience section"
    )


def test_management_html_renders_audience_card():
    html = (ROOT / "management.html").read_text(encoding="utf-8")
    assert 'id="audience-section"' in html
    assert "data.audience" in html
