"""Comprehensive tests for engine/config.py.

Covers all dataclasses, helper functions (_build_sources, _build_nested),
and the load_config loader, including real show YAML files.
"""

from __future__ import annotations

import textwrap
from pathlib import Path

import pytest
import yaml

from engine.config import (
    AnalyticsConfig,
    AudioConfig,
    ContentTrackingConfig,
    EpisodeConfig,
    LLMConfig,
    NewsletterConfig,
    PublishingConfig,
    ShowConfig,
    SourceConfig,
    StorageConfig,
    TTSConfig,
    _build_nested,
    _build_sources,
    load_config,
)

# ---- Repo root for real show files ----------------------------------------
REPO_ROOT = Path(__file__).resolve().parent.parent
SHOWS_DIR = REPO_ROOT / "shows"


# =========================================================================
# 1. TestSourceConfig
# =========================================================================
class TestSourceConfig:
    """SourceConfig dataclass basics."""

    def test_default_label_is_empty(self):
        sc = SourceConfig(url="https://example.com")
        assert sc.label == ""

    def test_explicit_label(self):
        sc = SourceConfig(url="https://example.com", label="Example")
        assert sc.url == "https://example.com"
        assert sc.label == "Example"

    def test_equality(self):
        a = SourceConfig(url="https://a.com", label="A")
        b = SourceConfig(url="https://a.com", label="A")
        assert a == b

    def test_inequality_different_label(self):
        a = SourceConfig(url="https://a.com", label="A")
        b = SourceConfig(url="https://a.com", label="B")
        assert a != b


# =========================================================================
# 2. TestBuildSources
# =========================================================================
class TestBuildSources:
    """Tests for the _build_sources helper."""

    def test_from_dicts(self):
        raw = [
            {"url": "https://a.com", "label": "A"},
            {"url": "https://b.com", "label": "B"},
        ]
        result = _build_sources(raw)
        assert len(result) == 2
        assert result[0] == SourceConfig(url="https://a.com", label="A")
        assert result[1] == SourceConfig(url="https://b.com", label="B")

    def test_from_strings(self):
        raw = ["https://x.com", "https://y.com"]
        result = _build_sources(raw)
        assert len(result) == 2
        assert all(isinstance(s, SourceConfig) for s in result)
        assert result[0].url == "https://x.com"
        assert result[0].label == ""

    def test_from_mixed(self):
        raw = [
            "https://plain.com",
            {"url": "https://dict.com", "label": "Dict"},
        ]
        result = _build_sources(raw)
        assert len(result) == 2
        assert result[0].url == "https://plain.com"
        assert result[0].label == ""
        assert result[1].label == "Dict"

    def test_none_returns_empty(self):
        assert _build_sources(None) == []

    def test_empty_list_returns_empty(self):
        assert _build_sources([]) == []

    def test_dict_missing_url_gets_empty_string(self):
        raw = [{"label": "No URL"}]
        result = _build_sources(raw)
        assert len(result) == 1
        assert result[0].url == ""
        assert result[0].label == "No URL"

    def test_dict_missing_label_gets_empty_string(self):
        raw = [{"url": "https://only-url.com"}]
        result = _build_sources(raw)
        assert result[0].label == ""


# =========================================================================
# 3. TestBuildNested
# =========================================================================
class TestBuildNested:
    """Tests for the _build_nested helper."""

    def test_normal_dict(self):
        raw = {"provider": "openai", "model": "gpt-4"}
        cfg = _build_nested(LLMConfig, raw)
        assert cfg.provider == "openai"
        assert cfg.model == "gpt-4"
        # Other fields should still have defaults
        assert cfg.digest_temperature == 0.7

    def test_unknown_keys_ignored(self):
        raw = {"provider": "openai", "nonexistent_key": 42, "another_junk": True}
        cfg = _build_nested(LLMConfig, raw)
        assert cfg.provider == "openai"
        assert not hasattr(cfg, "nonexistent_key")

    def test_empty_dict_returns_defaults(self):
        cfg = _build_nested(TTSConfig, {})
        assert cfg == TTSConfig()

    def test_none_returns_defaults(self):
        cfg = _build_nested(AudioConfig, None)
        assert cfg == AudioConfig()

    def test_non_dict_returns_defaults(self):
        """Passing a non-dict (e.g. a string) should return defaults."""
        cfg = _build_nested(EpisodeConfig, "not a dict")
        assert cfg == EpisodeConfig()

    def test_works_with_all_config_classes(self):
        """Ensure _build_nested works for every nested config class."""
        classes = [
            LLMConfig, TTSConfig, AudioConfig, PublishingConfig,
            EpisodeConfig, StorageConfig, AnalyticsConfig, NewsletterConfig,
        ]
        for cls in classes:
            cfg = _build_nested(cls, {})
            assert isinstance(cfg, cls)


# =========================================================================
# 4. TestDefaultValues
# =========================================================================
class TestDefaultValues:
    """Verify every dataclass default is exactly as documented."""

    def test_llm_defaults(self):
        c = LLMConfig()
        assert c.provider == "xai"
        assert c.model == "grok-4.3"
        assert c.system_prompt_file == ""
        assert c.digest_prompt_file == ""
        assert c.podcast_prompt_file == ""
        assert c.digest_temperature == 0.7
        assert c.podcast_temperature == 0.7
        assert c.max_tokens == 3500

    def test_tts_defaults(self):
        c = TTSConfig()
        assert c.voice_id == "dTrBzPvD2GpAqkk1MUzA"
        assert c.model == "eleven_flash_v2_5"
        assert c.stability == 0.5
        assert c.similarity_boost == 0.75
        assert c.style == 0.0
        assert c.use_speaker_boost is True
        assert c.max_chars == 10000
        assert c.speed == 1.0
        assert c.apply_text_normalization == "on"

    def test_audio_defaults(self):
        c = AudioConfig()
        assert c.music_file is None
        assert c.background_music_file is None
        assert c.intro_duration == 5.0
        assert c.overlap_duration == 3.0
        assert c.fade_duration == 18.0
        assert c.outro_duration == 30.0
        assert c.intro_volume == 0.6
        assert c.overlap_volume == 0.5
        assert c.fade_volume == 0.4
        assert c.outro_volume == 0.4
        assert c.voice_intro_delay == 0.0

    def test_publishing_defaults(self):
        c = PublishingConfig()
        assert c.rss_file == "podcast.rss"
        assert c.rss_title == "Podcast"
        assert c.rss_description == ""
        assert c.rss_author == "Patrick"
        assert c.rss_category == "Technology"
        assert c.rss_language == "en-us"
        assert c.x_enabled is True
        assert c.x_env_prefix == "X_"
        assert c.guid_prefix == "podcast"

    def test_episode_defaults(self):
        c = EpisodeConfig()
        assert c.prefix == "Podcast"
        assert c.filename_pattern == "{prefix}_Ep{num:03d}_{date:%Y%m%d_%H%M%S}.mp3"
        assert c.output_dir == "digests"
        assert c.mp3_glob == "*_Ep*.mp3"

    def test_storage_defaults(self):
        c = StorageConfig()
        assert c.provider == "github"
        assert c.bucket == "podcast-audio"
        assert c.endpoint_env == "R2_ENDPOINT_URL"
        assert c.access_key_env == "R2_ACCESS_KEY_ID"
        assert c.secret_key_env == "R2_SECRET_ACCESS_KEY"
        assert c.public_base_url == ""

    def test_analytics_defaults(self):
        c = AnalyticsConfig()
        assert c.enabled is False
        assert c.prefix_url == "https://op3.dev/e/"

    def test_newsletter_defaults(self):
        c = NewsletterConfig()
        assert c.enabled is False
        assert c.platform == "buttondown"
        assert c.api_key_env == "BUTTONDOWN_API_KEY"
        assert c.status == "about_to_send"

    def test_content_tracking_defaults(self):
        c = ContentTrackingConfig()
        assert c.enabled is True
        assert c.max_days == 14
        assert c.section_patterns == {}

    def test_show_config_defaults(self):
        c = ShowConfig()
        assert c.name == ""
        assert c.slug == ""
        assert c.description == ""
        assert c.sources == []
        assert c.keywords == []
        assert isinstance(c.llm, LLMConfig)
        assert isinstance(c.tts, TTSConfig)
        assert isinstance(c.audio, AudioConfig)
        assert isinstance(c.publishing, PublishingConfig)
        assert isinstance(c.episode, EpisodeConfig)
        assert isinstance(c.storage, StorageConfig)
        assert isinstance(c.analytics, AnalyticsConfig)
        assert isinstance(c.newsletter, NewsletterConfig)
        assert isinstance(c.content_tracking, ContentTrackingConfig)


# =========================================================================
# 5. TestLoadConfig
# =========================================================================
class TestLoadConfig:
    """Tests for load_config using temporary YAML files."""

    def test_full_yaml(self, tmp_path):
        data = {
            "name": "Test Show",
            "slug": "test_show",
            "description": "A test show.",
            "sources": [
                {"url": "https://a.com", "label": "A"},
                "https://b.com",
            ],
            "keywords": ["kw1", "kw2"],
            "llm": {"provider": "openai", "model": "gpt-4", "max_tokens": 2000},
            "tts": {"voice_id": "abc123", "stability": 0.5},
            "audio": {"music_file": "intro.mp3", "intro_duration": 10.0},
            "publishing": {"rss_title": "My RSS", "x_enabled": False},
            "episode": {"prefix": "TST", "output_dir": "out"},
            "storage": {"provider": "r2", "bucket": "my-bucket"},
            "analytics": {"enabled": True, "prefix_url": "https://analytics.dev/e/"},
            "newsletter": {"enabled": True, "api_key_env": "MY_KEY"},
        }
        p = tmp_path / "full.yaml"
        p.write_text(yaml.dump(data), encoding="utf-8")

        cfg = load_config(p)

        assert cfg.name == "Test Show"
        assert cfg.slug == "test_show"
        assert cfg.description == "A test show."
        assert len(cfg.sources) == 2
        assert cfg.sources[0].label == "A"
        assert cfg.sources[1].url == "https://b.com"
        assert cfg.keywords == ["kw1", "kw2"]
        assert cfg.llm.provider == "openai"
        assert cfg.llm.model == "gpt-4"
        assert cfg.llm.max_tokens == 2000
        assert cfg.tts.voice_id == "abc123"
        assert cfg.tts.stability == 0.5
        assert cfg.audio.music_file == "intro.mp3"
        assert cfg.audio.intro_duration == 10.0
        assert cfg.publishing.rss_title == "My RSS"
        assert cfg.publishing.x_enabled is False
        assert cfg.episode.prefix == "TST"
        assert cfg.episode.output_dir == "out"
        assert cfg.storage.provider == "r2"
        assert cfg.storage.bucket == "my-bucket"
        assert cfg.analytics.enabled is True
        assert cfg.analytics.prefix_url == "https://analytics.dev/e/"
        assert cfg.newsletter.enabled is True
        assert cfg.newsletter.api_key_env == "MY_KEY"

    def test_minimal_yaml(self, tmp_path):
        """A YAML with only a name should fill everything else with defaults."""
        p = tmp_path / "minimal.yaml"
        p.write_text("name: Minimal\n", encoding="utf-8")

        cfg = load_config(p)
        assert cfg.name == "Minimal"
        assert cfg.slug == ""
        assert cfg.sources == []
        assert cfg.llm == LLMConfig()
        assert cfg.tts == TTSConfig()
        assert cfg.audio == AudioConfig()
        assert cfg.episode == EpisodeConfig()

    def test_missing_file_raises(self, tmp_path):
        with pytest.raises(FileNotFoundError, match="Config file not found"):
            load_config(tmp_path / "does_not_exist.yaml")

    def test_empty_yaml(self, tmp_path):
        """An empty YAML file should produce a ShowConfig with all defaults."""
        p = tmp_path / "empty.yaml"
        p.write_text("", encoding="utf-8")

        cfg = load_config(p)
        assert cfg.name == ""
        assert cfg.sources == []
        assert cfg.llm == LLMConfig()

    def test_unknown_top_level_keys_ignored(self, tmp_path):
        data = {
            "name": "Ignored Keys",
            "totally_unknown": True,
            "another_bogus": [1, 2, 3],
        }
        p = tmp_path / "unknown.yaml"
        p.write_text(yaml.dump(data), encoding="utf-8")

        cfg = load_config(p)
        assert cfg.name == "Ignored Keys"
        assert not hasattr(cfg, "totally_unknown")

    def test_path_object_accepted(self, tmp_path):
        """load_config should accept both str and Path."""
        p = tmp_path / "pathobj.yaml"
        p.write_text("name: PathObj\n", encoding="utf-8")

        cfg = load_config(p)
        assert cfg.name == "PathObj"

    def test_string_path_accepted(self, tmp_path):
        p = tmp_path / "strpath.yaml"
        p.write_text("name: StrPath\n", encoding="utf-8")

        cfg = load_config(str(p))
        assert cfg.name == "StrPath"


# =========================================================================
# 6. TestLoadConfigRealFiles
# =========================================================================
class TestLoadConfigRealFiles:
    """Load each of the 5 real show YAML configs and verify key fields."""

    def test_tesla_show(self):
        cfg = load_config(SHOWS_DIR / "tesla.yaml")
        assert cfg.name == "Tesla Shorts Time"
        assert cfg.slug == "tesla"
        assert len(cfg.sources) >= 17  # electrek.co removed (blocked source)
        assert cfg.sources[0].label == "Teslarati"
        assert "tsla" in cfg.keywords
        assert len(cfg.web_search_queries) == 4
        # Tesla inherits the network default (grok-4.3) — always-on
        # reasoning at lower cost than the previous grok-4.20-reasoning
        # override.
        assert cfg.llm.model == "grok-4.3"
        assert cfg.llm.digest_temperature == 0.5
        assert cfg.llm.podcast_temperature == 0.7
        assert cfg.tts.voice_id == "dTrBzPvD2GpAqkk1MUzA"
        assert cfg.audio.music_file == "assets/music/tesla_shorts_time.mp3"
        assert cfg.publishing.rss_title == "Tesla Shorts Time Daily"
        assert cfg.publishing.x_enabled is True
        assert cfg.episode.prefix == "Tesla_Shorts_Time_Pod"
        assert cfg.episode.output_dir == "digests/tesla_shorts_time"

    def test_fascinating_frontiers_show(self):
        cfg = load_config(SHOWS_DIR / "fascinating_frontiers.yaml")
        assert cfg.name == "Fascinating Frontiers"
        assert cfg.slug == "fascinating_frontiers"
        assert len(cfg.sources) == 25
        assert cfg.sources[0].label == "NASA Breaking"
        assert "space" in cfg.keywords
        assert cfg.llm.model == "grok-4.3"
        assert cfg.tts.voice_id == "dTrBzPvD2GpAqkk1MUzA"
        assert cfg.audio.music_file == "assets/music/fascinatingfrontiers.mp3"
        assert cfg.audio.background_music_file == "assets/music/fascinatingfrontiers_bg.mp3"
        assert cfg.audio.voice_intro_delay == 5.0
        assert cfg.publishing.rss_category == "Science"
        assert cfg.publishing.x_env_prefix == "PLANETTERRIAN_X_"
        assert cfg.episode.prefix == "Fascinating_Frontiers"

    def test_planetterrian_show(self):
        cfg = load_config(SHOWS_DIR / "planetterrian.yaml")
        assert cfg.name == "Planetterrian Daily"
        assert cfg.slug == "planetterrian"
        assert len(cfg.sources) == 26
        assert cfg.sources[0].label == "Nature"
        assert "longevity" in cfg.keywords
        assert cfg.audio.music_file == "assets/music/oilers-pride.mp3"
        assert cfg.audio.outro_duration == 30.0
        assert cfg.publishing.guid_prefix == "planetterrian-daily"
        assert cfg.episode.prefix == "Planetterrian_Daily"
        assert cfg.episode.output_dir == "digests/planetterrian"

    def test_omni_view_show(self):
        cfg = load_config(SHOWS_DIR / "omni_view.yaml")
        assert cfg.name == "Omni View"
        assert cfg.slug == "omni_view"
        assert len(cfg.sources) == 28
        assert cfg.sources[0].label == "NPR"
        assert "election" in cfg.keywords
        assert cfg.llm.model == "grok-4.3"
        assert cfg.llm.digest_temperature == 0.5
        assert cfg.llm.max_tokens == 4000
        assert cfg.tts.stability == 0.5
        assert cfg.tts.style == 0.0
        assert cfg.audio.music_file == "assets/music/LubechangeOilers.mp3"
        assert cfg.publishing.rss_category == "News"
        assert cfg.publishing.guid_prefix == "omni-view"
        assert cfg.episode.prefix == "Omni_View"
        assert cfg.newsletter.enabled is True
        assert cfg.newsletter.api_key_env == "BUTTONDOWN_API_KEY"

    def test_env_intel_show(self):
        cfg = load_config(SHOWS_DIR / "env_intel.yaml")
        assert cfg.name == "Environmental Intelligence"
        assert cfg.slug == "env_intel"
        assert len(cfg.sources) >= 24  # thenarwhal.ca removed 2026-04-16 (HTTP 415)
        assert cfg.sources[0].label == "BC Ministry of Environment"
        assert "contaminated sites" in cfg.keywords
        assert "CCME" in cfg.keywords
        assert cfg.llm.model == "grok-4.3"
        assert cfg.llm.digest_temperature == 0.5
        assert cfg.tts.voice_id == "dTrBzPvD2GpAqkk1MUzA"
        assert cfg.tts.stability == 0.5  # Normalized to network standard
        assert cfg.tts.style == 0.0
        assert cfg.tts.max_chars == 10000
        assert cfg.audio.music_file == "assets/music/tesla_shorts_time.mp3"
        assert cfg.publishing.x_enabled is False
        assert cfg.episode.prefix == "Env_Intel"
        assert cfg.episode.output_dir == "digests/env_intel"
        assert cfg.newsletter.enabled is True
        assert cfg.newsletter.api_key_env == "BUTTONDOWN_API_KEY"
        assert cfg.newsletter.tag == "Environmental Intelligence"


# =========================================================================
# 7. TestNestedConfigOverrides
# =========================================================================
class TestNestedConfigOverrides:
    """Verify that only overridden fields change; others keep defaults."""

    def test_partial_llm_override(self, tmp_path):
        data = {"llm": {"model": "custom-model"}}
        p = tmp_path / "partial_llm.yaml"
        p.write_text(yaml.dump(data), encoding="utf-8")

        cfg = load_config(p)
        assert cfg.llm.model == "custom-model"
        # Everything else should be default
        assert cfg.llm.provider == "xai"
        assert cfg.llm.digest_temperature == 0.7
        assert cfg.llm.max_tokens == 3500

    def test_partial_tts_override(self, tmp_path):
        data = {"tts": {"stability": 0.3, "max_chars": 9999}}
        p = tmp_path / "partial_tts.yaml"
        p.write_text(yaml.dump(data), encoding="utf-8")

        cfg = load_config(p)
        assert cfg.tts.stability == 0.3
        assert cfg.tts.max_chars == 9999
        assert cfg.tts.voice_id == "dTrBzPvD2GpAqkk1MUzA"
        assert cfg.tts.model == "eleven_flash_v2_5"

    def test_partial_audio_override(self, tmp_path):
        data = {"audio": {"music_file": "custom.mp3", "voice_intro_delay": 15.0}}
        p = tmp_path / "partial_audio.yaml"
        p.write_text(yaml.dump(data), encoding="utf-8")

        cfg = load_config(p)
        assert cfg.audio.music_file == "custom.mp3"
        assert cfg.audio.voice_intro_delay == 15.0
        assert cfg.audio.intro_duration == 5.0
        assert cfg.audio.outro_duration == 30.0

    def test_partial_publishing_override(self, tmp_path):
        data = {"publishing": {"rss_title": "Custom Title", "x_enabled": False}}
        p = tmp_path / "partial_pub.yaml"
        p.write_text(yaml.dump(data), encoding="utf-8")

        cfg = load_config(p)
        assert cfg.publishing.rss_title == "Custom Title"
        assert cfg.publishing.x_enabled is False
        assert cfg.publishing.rss_language == "en-us"
        assert cfg.publishing.rss_author == "Patrick"

    def test_partial_episode_override(self, tmp_path):
        data = {"episode": {"prefix": "MY_SHOW"}}
        p = tmp_path / "partial_ep.yaml"
        p.write_text(yaml.dump(data), encoding="utf-8")

        cfg = load_config(p)
        assert cfg.episode.prefix == "MY_SHOW"
        assert cfg.episode.output_dir == "digests"
        assert cfg.episode.mp3_glob == "*_Ep*.mp3"

    def test_partial_storage_override(self, tmp_path):
        data = {"storage": {"provider": "r2", "public_base_url": "https://cdn.example.com"}}
        p = tmp_path / "partial_storage.yaml"
        p.write_text(yaml.dump(data), encoding="utf-8")

        cfg = load_config(p)
        assert cfg.storage.provider == "r2"
        assert cfg.storage.public_base_url == "https://cdn.example.com"
        assert cfg.storage.bucket == "podcast-audio"

    def test_partial_analytics_override(self, tmp_path):
        data = {"analytics": {"enabled": True}}
        p = tmp_path / "partial_analytics.yaml"
        p.write_text(yaml.dump(data), encoding="utf-8")

        cfg = load_config(p)
        assert cfg.analytics.enabled is True
        assert cfg.analytics.prefix_url == "https://op3.dev/e/"

    def test_partial_newsletter_override(self, tmp_path):
        data = {"newsletter": {"enabled": True, "status": "draft"}}
        p = tmp_path / "partial_newsletter.yaml"
        p.write_text(yaml.dump(data), encoding="utf-8")

        cfg = load_config(p)
        assert cfg.newsletter.enabled is True
        assert cfg.newsletter.status == "draft"
        assert cfg.newsletter.platform == "buttondown"

    def test_nested_unknown_keys_in_yaml(self, tmp_path):
        """Unknown keys inside nested sections should be silently ignored."""
        data = {
            "llm": {"model": "gpt-4", "fake_field": 999},
            "tts": {"voice_id": "xyz", "bogus": True},
        }
        p = tmp_path / "nested_unknown.yaml"
        p.write_text(yaml.dump(data), encoding="utf-8")

        cfg = load_config(p)
        assert cfg.llm.model == "gpt-4"
        assert cfg.tts.voice_id == "xyz"
        assert not hasattr(cfg.llm, "fake_field")
        assert not hasattr(cfg.tts, "bogus")

    def test_sources_only_yaml(self, tmp_path):
        """A YAML with only sources should still produce valid ShowConfig."""
        data = {
            "sources": [
                {"url": "https://feed.com/rss", "label": "Feed"},
                "https://raw.com",
            ]
        }
        p = tmp_path / "sources_only.yaml"
        p.write_text(yaml.dump(data), encoding="utf-8")

        cfg = load_config(p)
        assert len(cfg.sources) == 2
        assert cfg.sources[0].label == "Feed"
        assert cfg.sources[1].url == "https://raw.com"
        assert cfg.name == ""
        assert cfg.llm == LLMConfig()
