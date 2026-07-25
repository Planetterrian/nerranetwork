"""Drift guards for the July 26 2026 network improvements pack."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest
import yaml

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))


class TestDigestExpandOptIns:
    @pytest.mark.parametrize("slug,min_words", [
        ("planetterrian", 1400),
        ("unintended_consequences", 1200),
        ("models_agents_beginners", 1000),
    ])
    def test_digest_expand_enabled(self, slug, min_words):
        from engine.config import load_config
        cfg = load_config(_ROOT / "shows" / f"{slug}.yaml")
        assert cfg.llm.digest_expand_below_target is True
        assert cfg.llm.min_digest_words >= min_words


class TestContinuityBudgetAligned:
    def test_generator_retry_says_at_most_one(self):
        src = (_ROOT / "engine/generator.py").read_text(encoding="utf-8")
        assert "at most ONE continuity sentence" in src
        assert "1–2 continuity sentences into items" not in src

    def test_tesla_and_ma_digests_budget(self):
        for path in (
            "shows/prompts/tesla_digest.txt",
            "shows/prompts/models_agents_digest.txt",
        ):
            text = (_ROOT / path).read_text(encoding="utf-8")
            assert "CONTINUITY BUDGET" in text
            assert "1–2 continuity sentences" not in text


class TestTemplateDeSeeds:
    def test_fp_bans_verbatim_closer(self):
        digest = (_ROOT / "shows/prompts/fp_digest.txt").read_text(encoding="utf-8")
        podcast = (_ROOT / "shows/prompts/fp_podcast.txt").read_text(encoding="utf-8")
        assert "не так уж и сложно, правда?" in digest  # as BANNED example
        assert "BANNED" in digest
        assert "BANNED" in podcast
        assert "Подруга спросила меня вчера" in digest  # banned opener named

    def test_mit_drops_exact_scenario_template(self):
        text = (_ROOT / "shows/prompts/modern_investing_podcast.txt").read_text(
            encoding="utf-8")
        assert "exact scenario where our earlier rule" in text
        assert "do NOT reuse the template" in text


class TestBeatOwnership:
    def test_cross_show_handoffs_present(self):
        for path in (
            "shows/prompts/planetterrian_digest.txt",
            "shows/prompts/fascinating_frontiers_digest.txt",
            "shows/prompts/tesla_digest.txt",
            "shows/prompts/spacex_digest.txt",
        ):
            text = (_ROOT / path).read_text(encoding="utf-8")
            assert "BEAT OWNERSHIP" in text, path


class TestReaderTranscript:
    def test_run_show_writes_reader_txt(self):
        src = (_ROOT / "run_show.py").read_text(encoding="utf-8")
        assert "_reader.txt" in src
        assert "reader_script" in src

    def test_blog_prefers_reader_over_tts(self):
        src = (_ROOT / "engine/blog.py").read_text(encoding="utf-8")
        assert "_reader.txt" in src
        assert "Prefer *_reader.txt" in src or "prefer" in src.lower()


class TestMultiPlatformPilot:
    def test_tesla_and_spacex_enable_multi_platform_assets(self):
        for slug in ("tesla", "spacex"):
            raw = yaml.safe_load(
                (_ROOT / "shows" / f"{slug}.yaml").read_text(encoding="utf-8")
            )
            yt = raw.get("youtube") or {}
            assert yt.get("multi_platform_enabled") is True
            # Auto-post stays off until secrets + app approval.
            assert yt.get("instagram_enabled") is False
            assert yt.get("tiktok_enabled") is False


class TestVideoPodcastFF:
    def test_ff_video_podcast_enabled(self):
        from engine.config import load_config
        cfg = load_config(_ROOT / "shows/fascinating_frontiers.yaml")
        assert cfg.video_podcast.enabled is True


class TestSafeCommitRecovery:
    def test_composite_has_recovery_input(self):
        text = (_ROOT / ".github/actions/safe-commit-push/action.yml").read_text(
            encoding="utf-8")
        assert "recovery-on-failure" in text
        assert "create_recovery_pr.sh" in text

    def test_nightly_and_restock_opt_in(self):
        nightly = (_ROOT / ".github/workflows/nightly-maintenance.yml").read_text(
            encoding="utf-8")
        restock = (_ROOT / ".github/workflows/restock-topic-queues.yml").read_text(
            encoding="utf-8")
        assert "recovery-on-failure" in nightly
        assert "recovery-on-failure" in restock
        assert "pull-requests: write" in nightly
        assert "pull-requests: write" in restock


class TestManagementCoverDry:
    def test_prefers_rss_image(self):
        html = (_ROOT / "management.html").read_text(encoding="utf-8")
        assert "s.rss_image" in html
        assert "coverFor(s)" in html


class TestYoutubeHintChannels:
    def test_build_hint_accepts_channel(self):
        import inspect
        from scripts.update_youtube_performance import _build_hint
        assert "channel" in inspect.signature(_build_hint).parameters
