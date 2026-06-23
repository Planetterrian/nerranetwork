"""Tests for Grok Video generation pipeline.

Validates:
1. Audio integration (final_mp3_path parameter and FFmpeg composite)
2. Show-specific prompt generation
3. Drift guards for critical improvements
"""

import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from engine.config import load_config
from engine.grok_video import (
    _build_video_prompt,
    _composite_video_with_audio,
    GrokVideoResult,
    VideoClip,
)


class TestShowSpecificVideoPrompts:
    """Validate that video prompts use show-specific customization."""

    def test_tesla_prompt_includes_genre_and_keywords(self):
        """Tesla prompts should include automotive-tech-news genre."""
        config = load_config("shows/tesla.yaml")

        prompt = _build_video_prompt(
            segment_text="Tesla announces new Cybertruck features",
            show_config=config,
            hook="Cybertruck wireless BMS breakthrough",
            episode_title="Tesla Shorts Time Ep462",
        )

        # Check that show-specific fields are present
        assert "automotive-tech-news" in prompt
        assert "energetic-professional-urgent" in prompt
        assert "Tesla" in prompt or "electric vehicles" in prompt
        assert "technology and innovation news" not in prompt  # Old generic text

    def test_spacex_prompt_includes_aerospace_keywords(self):
        """SpaceX prompts should include aerospace-engineering and spaceflight keywords."""
        config = load_config("shows/spacex.yaml")

        prompt = _build_video_prompt(
            segment_text="Starship completes hot stage separation test",
            show_config=config,
            hook="Starship test proves raptor engine reliability",
            episode_title="SpaceX Daily Ep25",
        )

        assert "aerospace-engineering" in prompt
        assert "SpaceX" in prompt or "Starship" in prompt or "spaceflight" in prompt

    def test_fallback_to_generic_when_no_config(self):
        """Prompts should gracefully fall back when no config provided."""
        prompt = _build_video_prompt(
            segment_text="Some generic news",
            show_config=None,
            hook="A story",
            episode_title="Episode 1",
        )

        # Should not crash; should contain something reasonable
        assert "professional" in prompt.lower()
        assert "podcast" in prompt.lower()

    def test_prompt_includes_segment_context(self):
        """Prompts should include relevant context from the script segment."""
        script = "Breaking news: Tesla announces new battery technology with 50% higher density"
        config = load_config("shows/tesla.yaml")

        prompt = _build_video_prompt(
            segment_text=script,
            show_config=config,
            hook="Tesla battery breakthrough",
        )

        # Should include at least some part of the script
        assert "battery" in prompt.lower() or "technology" in prompt.lower()


class TestAudioIntegration:
    """Validate that audio integration works correctly."""

    def test_composite_requires_both_video_and_audio(self):
        """Composite should fail gracefully if either file is missing."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir = Path(tmpdir)
            nonexistent_video = tmpdir / "video.mp4"
            nonexistent_audio = tmpdir / "audio.mp3"
            output = tmpdir / "output.mp4"

            # Should return False, not crash
            result = _composite_video_with_audio(
                nonexistent_video, nonexistent_audio, output
            )
            assert result is False

    @patch("engine.grok_video.subprocess.run")
    def test_composite_uses_correct_ffmpeg_args(self, mock_run):
        """Composite should call FFmpeg with correct arguments."""
        mock_run.return_value = MagicMock(returncode=0)

        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir = Path(tmpdir)

            # Create dummy files
            video_file = tmpdir / "video.mp4"
            audio_file = tmpdir / "audio.mp3"
            output_file = tmpdir / "output.mp4"

            video_file.write_bytes(b"dummy video")
            audio_file.write_bytes(b"dummy audio")

            result = _composite_video_with_audio(video_file, audio_file, output_file)

            # Check FFmpeg was called
            assert mock_run.called
            call_args = mock_run.call_args[0][0]

            # Validate key FFmpeg flags
            assert "ffmpeg" in call_args
            assert "-c:v" in call_args
            assert "copy" in call_args  # Don't re-encode video
            assert "-c:a" in call_args
            assert "aac" in call_args  # YouTube-compatible audio
            assert "-shortest" in call_args  # Safety: don't exceed audio duration
            assert "-map" in call_args  # Explicit stream mapping


class TestVideoGenerationSignature:
    """Validate that generate_grok_videos has correct parameters."""

    def test_generate_grok_videos_accepts_final_mp3_path(self):
        """Function should accept final_mp3_path parameter."""
        from engine.grok_video import generate_grok_videos
        import inspect

        sig = inspect.signature(generate_grok_videos)
        param_names = list(sig.parameters.keys())

        assert "final_mp3_path" in param_names
        assert "show_config" in param_names

    def test_generate_grok_videos_has_default_values(self):
        """Optional parameters should have sensible defaults."""
        from engine.grok_video import generate_grok_videos
        import inspect

        sig = inspect.signature(generate_grok_videos)

        # final_mp3_path and show_config should be optional
        assert sig.parameters["final_mp3_path"].default is None
        assert sig.parameters["show_config"].default is None


class TestYAMLConfigIntegration:
    """Validate that YAML config has video customization fields."""

    def test_tesla_yaml_has_video_fields(self):
        """Tesla YAML should have video_genre, video_mood, video_keywords."""
        config = load_config("shows/tesla.yaml")
        yt = config.youtube

        assert hasattr(yt, "video_genre")
        assert hasattr(yt, "video_mood")
        assert hasattr(yt, "video_keywords")
        assert hasattr(yt, "video_visual_style")

        assert yt.video_genre == "automotive-tech-news"
        assert "energetic" in yt.video_mood
        assert len(yt.video_keywords) > 0
        assert yt.video_visual_style != ""

    def test_spacex_yaml_has_video_fields(self):
        """SpaceX YAML should have video customization."""
        config = load_config("shows/spacex.yaml")
        yt = config.youtube

        assert yt.video_genre == "aerospace-engineering"
        assert len(yt.video_keywords) > 0

    def test_all_shows_have_video_fields_defined(self):
        """All shows should have video field defaults (can be empty)."""
        show_names = [
            "tesla", "spacex", "omni_view", "planetterrian",
            "fascinating_frontiers", "models_agents", "models_agents_beginners",
            "modern_investing", "env_intel", "finansy_prosto",
            "privet_russian", "unintended_consequences", "first_principles",
        ]

        for slug in show_names:
            config = load_config(f"shows/{slug}.yaml")
            yt = config.youtube

            # All shows should have these fields (even if empty)
            assert hasattr(yt, "video_genre")
            assert hasattr(yt, "video_mood")
            assert hasattr(yt, "video_keywords")
            assert hasattr(yt, "video_visual_style")


class TestVideoClipDataClass:
    """Validate VideoClip structure."""

    def test_video_clip_has_required_fields(self):
        """VideoClip should track prompt, duration, resolution, and status."""
        clip = VideoClip(
            clip_id="test_001",
            request_id="req_123",
            prompt="Test prompt",
            duration_seconds=15,
            resolution="720p",
        )

        assert clip.clip_id == "test_001"
        assert clip.duration_seconds == 15
        assert clip.resolution == "720p"
        assert clip.status == "queued"  # Default status


class TestGrokVideoResult:
    """Validate GrokVideoResult structure."""

    def test_result_tracks_cost(self):
        """Result should accumulate and track total cost."""
        result = GrokVideoResult(episode_num=462)

        assert result.total_cost_usd == 0.0
        assert result.episode_num == 462
        assert result.is_fallback is False
        assert len(result.failures) == 0

    def test_result_tracks_full_and_short_paths(self):
        """Result should store paths to both full and short videos."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir = Path(tmpdir)
            full_path = tmpdir / "full.mp4"
            short_path = tmpdir / "short.mp4"

            result = GrokVideoResult(
                episode_num=462,
                full_video_path=full_path,
                short_video_path=short_path,
            )

            assert result.full_video_path == full_path
            assert result.short_video_path == short_path


class TestVideoBudget:
    """Drift guards: a stuck clip must never blow the pipeline budget.

    Regression: Tesla Ep519 (2026-06-23) timed out because the video step
    polled 46 clips sequentially at 15 min/clip with no overall budget; the
    pipeline SIGALRM fired mid-render and skipped the episode's git commit.
    """

    def test_signature_has_budget_param_defaulting_none(self):
        from engine.grok_video import generate_grok_videos
        import inspect

        sig = inspect.signature(generate_grok_videos)
        assert "max_total_seconds" in sig.parameters
        assert sig.parameters["max_total_seconds"].default is None

    def test_module_defines_budget_and_ratio(self):
        import engine.grok_video as g

        assert g.DEFAULT_VIDEO_BUDGET_S > 0
        assert 0 < g.MIN_CLIP_COMPLETION_RATIO <= 1.0

    def test_stuck_clips_respect_budget_and_fall_back(self):
        """Clips that never complete must not hang past the budget; with too
        few completed the result is a fallback (no full video path)."""
        import engine.grok_video as g

        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.object(g, "_request_one_video", side_effect=lambda *a, **k: "req-123"), \
                 patch.object(g, "_check_video_status_once", return_value={"status": "pending"}) as mock_status, \
                 patch.object(g, "DEFAULT_POLL_INTERVAL_S", 0):

                result = g.generate_grok_videos(
                    work_dir=Path(tmpdir),
                    episode_num=1,
                    podcast_script="One short sentence here.",  # 1 clip
                    hook="hook",
                    api_key="test-key",
                    max_total_seconds=0.5,  # clip never completes within budget
                )

            # Never produced a full video; flagged fallback so the caller
            # uses the image slideshow instead of a truncated episode.
            assert result.full_video_path is None
            assert result.is_fallback is True
            assert mock_status.called  # we did poll at least once


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
