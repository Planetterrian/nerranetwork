"""Cross-cutting drift guards for the Sep 4 2026 flagship pass
(docs/reviews/flagship_review_2026_09_04.md). Per-show guards live in the
show test files; these pin the shared-pipeline fixes."""

from __future__ import annotations

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))


class TestWallClockDuration:
    def test_wall_duration_counts_timed_counters(self):
        from engine.metrics import PipelineMetrics
        m = PipelineMetrics("spacex", 89)
        with m.stage("fetch"):
            pass
        m.record("tts_duration_s", 120.5)
        m.record("audio_mix_duration_s", 30.0)
        m.record("youtube_publish_duration_s", 1493.5)
        m.record("audio_duration_s", 612.0)   # episode length, not a timing
        m.record("x_post_duration_s", "0.63")
        d = m.to_dict()
        assert d["wall_duration_s"] >= 1644.0 and d["wall_duration_s"] < 1660.0
        assert d["total_duration_s"] < 5.0
        assert "wall_duration_s" in d

    def test_dashboard_prefers_wall_duration(self):
        src = (_ROOT / "scripts" / "generate_dashboard.py").read_text(encoding="utf-8")
        assert 'data.get("wall_duration_s") or data.get("total_duration_s")' in src


class TestNightlyWhitelistCoversEveryPerformanceTracker:
    def test_glob_not_literals(self):
        text = (_ROOT / ".github/workflows/nightly-maintenance.yml").read_text(encoding="utf-8")
        assert "digests/**/*_performance_tracker.json" in text
        assert "digests/spacex/spacex_performance_tracker.json" not in text


class TestRegenerableIntermediatesIgnored:
    def test_gitignore_patterns_present(self):
        text = (_ROOT / ".gitignore").read_text(encoding="utf-8")
        for pat in ("digests/*/youtube_tmp/*_square.jpg",
                    "digests/*/youtube_tmp/*.social.json",
                    "digests/*/youtube_tmp/*.chapters.ffmeta"):
            assert pat in text, pat


class TestBlogPlayerIsMeasured:
    def test_network_audio_gets_op3_prefix(self):
        from engine.blog import _measured_audio_url
        assert _measured_audio_url("https://audio.nerranetwork.com/spacex/x.mp3") == \
            "https://op3.dev/e/audio.nerranetwork.com/spacex/x.mp3"
        assert _measured_audio_url("https://op3.dev/e/audio.nerranetwork.com/spacex/x.mp3") == \
            "https://op3.dev/e/audio.nerranetwork.com/spacex/x.mp3"
        assert _measured_audio_url("https://example.org/guest.mp3") == "https://example.org/guest.mp3"
        assert _measured_audio_url("") == ""


class TestLanguageAudienceNullStaysNull:
    """OP3 answers 404 for feeds it never indexed (every ZH feed + three FR
    feeds). The dashboard turned that into "0 downloads, measured: true" —
    on the card the July-29 language-cull rule reads from."""

    def test_unindexed_feed_is_unmeasured_not_zero(self, tmp_path):
        import json
        import scripts.generate_dashboard as gd
        from engine.config import load_config
        cfg = load_config("shows/tesla.yaml")
        cfg.publishing.summaries_json = "summaries.json"
        (tmp_path / "summaries.json").write_text(json.dumps({
            "podcast": "t", "summaries": [{"episode_num": 1, "translations": {
                "fr": {"audio_url": "a"}, "zh": {"audio_url": "b"}}}]}), encoding="utf-8")
        (tmp_path / "api").mkdir()
        (tmp_path / "api" / "op3_stats.json").write_text(json.dumps({"language_feeds": {
            "tesla:fr": {"show_slug": "tesla", "language": "fr", "downloads_7d": 12, "downloads_30d": 40},
            "tesla:zh": {"show_slug": "tesla", "language": "zh", "downloads_7d": None,
                          "downloads_30d": None, "note": "OP3 has not indexed this feed (404)"},
        }}), encoding="utf-8")
        cfg.multilingual.languages = ["fr", "zh"]
        out = gd.aggregate_multilingual(tmp_path, [{"slug": "tesla", "cfg": cfg}])
        aud = out["per_show"]["tesla"]["audience_by_language"]
        assert aud["fr"]["downloads_30d"] == 40 and aud["fr"]["measured"] is True
        assert aud["zh"]["downloads_30d"] is None and aud["zh"]["measured"] is False
        assert "404" in aud["zh"]["note"]
        assert out["by_language"]["fr"]["measured"] is True
        assert out["by_language"]["zh"]["measured"] is False
        assert out["by_language"]["zh"]["downloads_30d"] == 0  # rollup sums only measured shows
        assert out["by_language"]["zh"]["unmeasured_shows"] == 1
