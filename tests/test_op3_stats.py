"""Drift guards for scripts/fetch_op3_stats.py (June 2026 growth pass).

The OP3 integration is the network's first read-back of real audience
data. Contract pinned here:

* clean no-op when ``OP3_API_TOKEN`` is unset (exit 0, files untouched);
* correct parsing of the live OP3 response shapes (verified against the
  real API 2026-06: show-download-counts ``monthlyDownloads`` /
  ``weeklyDownloads`` and episode-download-counts ``downloads1/3/7/30/All``
  with window keys omitted on young feeds);
* the public ``site/data/popular_episodes.json`` carries display fields
  only — never tokens or show UUIDs.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from scripts.fetch_op3_stats import (  # noqa: E402
    _PUBLIC_EPISODE_FIELDS,
    _fetch_show_stats,
    build_popular_episodes,
    main,
)


class TestNoOpWithoutToken:
    def test_exit_zero_and_files_untouched(self, tmp_path, monkeypatch):
        monkeypatch.delenv("OP3_API_TOKEN", raising=False)
        out = tmp_path / "op3_stats.json"
        popular = tmp_path / "popular.json"
        out.write_text('{"sentinel": true}', encoding="utf-8")

        rc = main(["--out", str(out), "--popular-out", str(popular)])

        assert rc == 0
        assert json.loads(out.read_text()) == {"sentinel": True}, (
            "existing stats file must be left untouched when token unset"
        )
        assert not popular.exists()

    def test_blank_token_is_unset(self, tmp_path, monkeypatch):
        monkeypatch.setenv("OP3_API_TOKEN", "   ")
        rc = main(["--out", str(tmp_path / "o.json"),
                   "--popular-out", str(tmp_path / "p.json")])
        assert rc == 0
        assert not (tmp_path / "o.json").exists()


# Canned responses mirroring the live API shapes (captured 2026-06).
_SHOW_COUNTS = {
    "asof": "2026-06-08",
    "showDownloadCounts": {
        "abc123": {
            "days": "000000000000000000000111111101",
            "monthlyDownloads": 24,
            "weeklyDownloads": [0, 0, 13, 11],
            "weeklyAvgDownloads": 11,
            "numWeeks": 1,
        }
    },
}
_EPISODE_COUNTS = {
    "showUuid": "abc123",
    "episodes": [
        {  # young episode: downloads7/30 omitted by the API
            "itemGuid": "guid-young",
            "title": "Young episode",
            "pubdate": "2026-06-05T08:00:00.000Z",
            "downloads1": 2,
            "downloads3": 2,
            "downloadsAll": 3,
        },
        {  # mature episode: all windows present
            "itemGuid": "guid-mature",
            "title": "Mature episode",
            "pubdate": "2026-05-20T08:00:00.000Z",
            "downloads3": 1,
            "downloads7": 9,
            "downloads30": 20,
            "downloadsAll": 40,
        },
    ],
}


def _fake_get(url, token, params=None):
    if "/shows/" in url:
        return {"showUuid": "abc123"}
    if "show-download-counts" in url:
        return _SHOW_COUNTS
    if "episode-download-counts" in url:
        return _EPISODE_COUNTS
    raise AssertionError(f"unexpected url {url}")


class TestResponseParsing:
    def test_show_and_episode_fields(self):
        with patch("scripts.fetch_op3_stats._get", side_effect=_fake_get):
            stats = _fetch_show_stats(
                "env_intel", "https://nerranetwork.com/env_intel_podcast.rss",
                "tok", None,
            )
        assert stats is not None
        assert stats["downloads_30d"] == 24
        assert stats["downloads_7d"] == 11  # last weeklyDownloads bucket
        assert stats["weekly_avg"] == 11
        assert stats["show_uuid"] == "abc123"

        by_guid = {e["item_guid"]: e for e in stats["episodes"]}
        mature = by_guid["guid-mature"]
        assert mature["downloads_7d"] == 9
        assert mature["downloads_30d"] == 20
        assert mature["downloads_all_time"] == 40
        # Young feed: 7d falls back to the 3d window so it still ranks.
        young = by_guid["guid-young"]
        assert young["downloads_7d"] == 2
        assert young["downloads_30d"] == 3  # falls back to all-time

    def test_episodes_sorted_by_7d(self):
        with patch("scripts.fetch_op3_stats._get", side_effect=_fake_get):
            stats = _fetch_show_stats("x", "https://e/feed.rss", "tok", None)
        sevens = [e["downloads_7d"] for e in stats["episodes"]]
        assert sevens == sorted(sevens, reverse=True)

    def test_cached_uuid_skips_lookup(self):
        calls = []

        def tracking_get(url, token, params=None):
            calls.append(url)
            return _fake_get(url, token, params)

        with patch("scripts.fetch_op3_stats._get", side_effect=tracking_get):
            _fetch_show_stats("x", "https://e/feed.rss", "tok", "abc123")
        assert not any("/shows/" in u for u in calls)

    def test_one_show_failure_returns_none(self):
        with patch("scripts.fetch_op3_stats._get",
                   side_effect=RuntimeError("boom")):
            assert _fetch_show_stats("x", "https://e/f.rss", "tok", None) is None


class TestPopularEpisodes:
    def _stats(self, n=20):
        return {
            "shows": {
                "tesla": {
                    "show_uuid": "secret-uuid",
                    "episodes": [
                        {"title": f"Ep {i}", "item_guid": f"g{i}",
                         "downloads_7d": i, "downloads_30d": i,
                         "downloads_all_time": i}
                        for i in range(1, n + 1)
                    ],
                }
            }
        }

    def test_caps_at_twelve_sorted_with_ranks(self, tmp_path):
        popular = build_popular_episodes(self._stats(), tmp_path)
        assert len(popular) == 12
        assert [e["rank"] for e in popular] == list(range(1, 13))
        downloads = [e["downloads_7d"] for e in popular]
        assert downloads == sorted(downloads, reverse=True)

    def test_public_fields_whitelisted_no_uuid_leak(self, tmp_path):
        popular = build_popular_episodes(self._stats(), tmp_path)
        for ep in popular:
            assert set(ep.keys()) <= set(_PUBLIC_EPISODE_FIELDS)
        blob = json.dumps(popular)
        assert "secret-uuid" not in blob
        assert "item_guid" not in blob

    def test_zero_download_episodes_excluded(self, tmp_path):
        stats = {"shows": {"tesla": {"episodes": [
            {"title": "Quiet", "item_guid": "g", "downloads_7d": 0},
        ]}}}
        assert build_popular_episodes(stats, tmp_path) == []


def test_nightly_maintenance_runs_op3_fetch():
    """The nightly workflow must invoke the fetch script before the
    dashboard build, with the token passed from secrets."""
    wf = (_ROOT / ".github" / "workflows" / "nightly-maintenance.yml").read_text(
        encoding="utf-8")
    assert "scripts/fetch_op3_stats.py" in wf
    assert "OP3_API_TOKEN" in wf
    assert wf.index("fetch_op3_stats.py") < wf.index("generate_dashboard.py"), (
        "OP3 stats must be fetched before the dashboard build consumes them"
    )
