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
        # Hard-floor default mirrors the network-wide 600-word
        # tuning baked into run_show.py:1685 since the start of
        # the Phase-3 calibration. Only shows that explicitly
        # opt into a thinner content surface (env_intel) override
        # it lower.
        assert c.min_podcast_word_floor == 600

    def test_tts_defaults(self):
        c = TTSConfig()
        # Network default since May 2026 (full-network migration) —
        # Grok TTS with the operator's custom-trained voice
        # `kdif6sqjcyiq`, used by every English show including Tesla.
        assert c.provider == "grok"
        assert c.voice_id == "kdif6sqjcyiq"
        assert c.language_code == "en"
        assert c.max_chars == 10000
        # Legacy ElevenLabs baseline — preserved on the dataclass so
        # any show that overrides ``provider: elevenlabs`` inherits a
        # tuned starting point. Harmless under provider=grok.
        assert c.model == "eleven_flash_v2_5"
        assert c.stability == 0.5
        assert c.similarity_boost == 0.75
        assert c.style == 0.0
        assert c.use_speaker_boost is True
        assert c.speed == 1.0
        assert c.apply_text_normalization == "on"

    def test_audio_defaults(self):
        """May 12 2026 retune: AudioConfig defaults align with the
        network's ``shows/_defaults.yaml`` baseline. Voice enters at
        10 s (was 25 s), music continues 45 s under voice with a 30 s
        log-fade (total intro music presence still 55 s, just
        front-shifted), and the post-voice outro is 20 s with most of
        that being a slow 15 s fade-out. ``voice_intro_delay`` must
        equal ``intro_duration`` so voice enters exactly when the
        music intro alone-period ends."""
        c = AudioConfig()
        assert c.music_file is None
        assert c.background_music_file is None
        assert c.intro_duration == 10.0
        assert c.overlap_duration == 15.0
        assert c.fade_duration == 30.0
        # May 13 2026 retune — outro lengthened to 30s with shorter fade.
        # Music now starts AFTER voice ends (outro_crossfade=0), plays
        # ~20s "by itself", then fades over 10s.
        assert c.outro_duration == 30.0
        assert c.outro_fade_out_duration == 10.0
        assert c.intro_volume == 0.6
        assert c.overlap_volume == 0.5
        assert c.fade_volume == 0.4
        assert c.outro_volume == 0.6  # May 15 2026: matches intro_volume for clear post-voice cue
        # voice_intro_delay must be >= intro_duration so the voice
        # doesn't start before the music intro alone-period finishes.
        assert c.voice_intro_delay == 10.0
        assert c.voice_intro_delay >= c.intro_duration
        # Total intro music presence (alone + overlap + fade) preserved
        # at 55 s across the May 12 2026 retune.
        assert c.intro_duration + c.overlap_duration + c.fade_duration == 55.0

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

    def test_min_audio_duration_from_audio_block(self, tmp_path):
        data = {
            "name": "Audio Gate Show",
            "slug": "audio_gate",
            "audio": {"min_audio_duration": 240},
        }
        p = tmp_path / "audio_gate.yaml"
        p.write_text(yaml.dump(data), encoding="utf-8")
        cfg = load_config(p)
        assert cfg.min_audio_duration == 240

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
        assert len(cfg.sources) >= 16  # electrek.co + driveteslacanada.ca removed (blocked sources)
        assert cfg.sources[0].label == "Teslarati"
        assert "tsla" in cfg.keywords
        assert len(cfg.web_search_queries) == 4
        # Tesla inherits the network default (grok-4.3) — always-on
        # reasoning at lower cost than the previous grok-4.20-reasoning
        # override.
        assert cfg.llm.model == "grok-4.3"
        assert cfg.llm.digest_temperature == 0.5
        assert cfg.llm.podcast_temperature == 0.7
        # Tesla migrated off ElevenLabs in May 2026; now inherits the
        # network's Grok TTS custom voice from _defaults.yaml.
        assert cfg.tts.provider == "grok"
        assert cfg.tts.voice_id == "kdif6sqjcyiq"
        assert cfg.audio.music_file == "assets/music/tesla_shorts_time.mp3"
        # rss_title aligned to "Tesla Shorts Time" in May 2026 audit
        # to match Apple Podcasts listing exactly.
        assert cfg.publishing.rss_title == "Tesla Shorts Time"
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
        # English shows migrated to Grok TTS (sal voice) in May 2026.
        assert cfg.tts.provider == "grok"
        assert cfg.tts.voice_id == "kdif6sqjcyiq"
        # May 2026: FF unified intro + outro on the long ``_bg`` track
        # (operator preferred a single musical identity). Short jingle
        # file kept in repo for emergency rollback.
        assert cfg.audio.music_file == "assets/music/fascinatingfrontiers_bg.mp3"
        assert cfg.audio.background_music_file is None
        # May 12 2026 retune — 10s music alone before voice.
        assert cfg.audio.voice_intro_delay == 10.0
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
        # May 13 2026 retune — post-voice outro lengthened to 30s
        # (was 20s), with music now playing alone after voice ends
        # rather than ramping under the final 20s of voice.
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
        # OV got its own dedicated theme in May 2026 (replaced LubechangeOilers.mp3).
        assert cfg.audio.music_file == "assets/music/OmniView.mp3"
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
        # English shows migrated to Grok TTS (sal voice) in May 2026. The
        # ElevenLabs settings (stability/style) still inherit from the
        # legacy block in _defaults.yaml — harmless since the Grok path
        # ignores them — so these assertions still pass.
        assert cfg.tts.provider == "grok"
        assert cfg.tts.voice_id == "kdif6sqjcyiq"
        assert cfg.tts.stability == 0.5  # Inherited from legacy ElevenLabs baseline
        assert cfg.tts.style == 0.0
        # max_chars bumped to 14000 (May 13 2026) so the typical
        # 6-12k podcast script fits in a single Grok TTS call —
        # required for the network-wide ``<fast>`` wrap to apply
        # safely without leaking at chunk boundaries.
        assert cfg.tts.max_chars == 14000
        # EI got its own dedicated theme in May 2026
        # (replaced the shared tesla_shorts_time.mp3).
        assert cfg.audio.music_file == "assets/music/EnvIntel.mp3"
        assert cfg.publishing.x_enabled is False
        assert cfg.episode.prefix == "Env_Intel"
        assert cfg.episode.output_dir == "digests/env_intel"
        assert cfg.newsletter.enabled is True
        assert cfg.newsletter.api_key_env == "BUTTONDOWN_API_KEY"
        assert cfg.newsletter.tag == "Environmental Intelligence"
        # env_intel is structurally a shorter show (alt-cadence,
        # narrow content surface). Last five episodes ran 693–928
        # words — the network 1500 default was never close. Ep036
        # (2026-05-21) came in at 539 words on a narrow-news day
        # and was incorrectly aborted at the 600 hard floor; the
        # explicit floor + target keep narrow-but-legitimate
        # episodes shippable. See run_show.py:1685.
        assert cfg.llm.min_podcast_words == 900
        assert cfg.llm.min_podcast_word_floor == 450


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
        # Overrides applied
        assert cfg.tts.stability == 0.3
        assert cfg.tts.max_chars == 9999
        # Network defaults preserved (Grok TTS + sal voice; legacy
        # ElevenLabs baseline still set on the dataclass for back-compat).
        assert cfg.tts.provider == "grok"
        assert cfg.tts.voice_id == "kdif6sqjcyiq"
        assert cfg.tts.model == "eleven_flash_v2_5"

    def test_partial_audio_override(self, tmp_path):
        data = {"audio": {"music_file": "custom.mp3", "voice_intro_delay": 25.0}}
        p = tmp_path / "partial_audio.yaml"
        p.write_text(yaml.dump(data), encoding="utf-8")

        cfg = load_config(p)
        assert cfg.audio.music_file == "custom.mp3"
        # Per-show override wins.
        assert cfg.audio.voice_intro_delay == 25.0
        # Network defaults inherited from shows/_defaults.yaml — May 13
        # 2026 retune (10s intro alone, 30s post-voice outro with no
        # crossfade ramp).
        assert cfg.audio.intro_duration == 10.0
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


# ---------------------------------------------------------------------------
# YouTube image provider — May 2026 Grok Imagine rollout
# ---------------------------------------------------------------------------

class TestYouTubeImageProviderConfig:
    """Phase 1 of the Grok Imagine rollout. The new fields default to
    the old Pexels behaviour so any show that doesn't opt in keeps its
    current pipeline; only Tesla + MAB are flipped to ``grok`` in this
    PR (per CLAUDE.md landmine #20 those are the only YouTube-enabled
    shows). Pin the defaults so a future YAML refactor doesn't
    silently regress to a different provider."""

    def test_default_image_provider_is_pexels(self):
        from engine.config import YouTubeConfig
        c = YouTubeConfig()
        assert c.image_provider == "pexels"
        # Per-show overrides are the only path to non-default providers.

    def test_default_grok_image_model_is_standard(self):
        """Standard model is $0.02/img; pro is $0.07/img. Default to
        the cheaper one so a misconfigured show doesn't surprise-bill."""
        from engine.config import YouTubeConfig


def test_deep_merge_is_now_recursive():
    """Regression guard for the recursive _deep_merge upgrade (item 1 of the
    May 2026 review plan)."""
    from engine.config import _deep_merge

    base = {
        "tts": {"voice_id": "default", "settings": {"stability": 0.5, "style": 0.0}},
        "audio": {"intro_duration": 10},
    }
    override = {
        "tts": {"settings": {"stability": 0.7}},  # should merge inside the nested dict
        "youtube": {"enabled": True},
    }

    result = _deep_merge(base, override)

    # Nested merge happened
    assert result["tts"]["voice_id"] == "default"
    assert result["tts"]["settings"]["stability"] == 0.7
    assert result["tts"]["settings"]["style"] == 0.0  # preserved from base

    # Top-level new key added
    assert result["youtube"]["enabled"] is True

    # Original base not mutated
    assert base["tts"]["settings"]["stability"] == 0.5


def test_deep_merge_is_now_recursive():
    """Regression guard for the recursive _deep_merge upgrade (item 1 of the
    May 2026 review plan)."""
    from engine.config import _deep_merge

    base = {
        "tts": {"voice_id": "default", "settings": {"stability": 0.5, "style": 0.0}},
        "audio": {"intro_duration": 10},
    }
    override = {
        "tts": {"settings": {"stability": 0.7}},  # should merge inside the nested dict
        "youtube": {"enabled": True},
    }

    result = _deep_merge(base, override)

    # Nested merge happened
    assert result["tts"]["voice_id"] == "default"
    assert result["tts"]["settings"]["stability"] == 0.7
    assert result["tts"]["settings"]["style"] == 0.0  # preserved from base

    # Top-level new key added
    assert result["youtube"]["enabled"] is True

    # Original base not mutated
    assert base["tts"]["settings"]["stability"] == 0.5


class TestYouTubeImageProviderConfig:
    """Phase 1 of the Grok Imagine rollout. The new fields default to
    the old Pexels behaviour so any show that doesn't opt in keeps its
    current pipeline; only Tesla + MAB are flipped to ``grok`` in this
    PR (per CLAUDE.md landmine #20 those are the only YouTube-enabled
    shows). Pin the defaults so a future YAML refactor doesn't
    silently regress to a different provider."""

    def test_default_image_provider_is_pexels(self):
        from engine.config import YouTubeConfig
        c = YouTubeConfig()
        assert c.image_provider == "pexels"
        # Per-show overrides are the only path to non-default providers.

    def test_default_grok_image_model_is_standard(self):
        """Standard model is $0.02/img; pro is $0.07/img. Default to
        the cheaper one so a misconfigured show doesn't surprise-bill."""
        from engine.config import YouTubeConfig
        c = YouTubeConfig()
        assert c.grok_image_model == "grok-imagine-image"
        assert "pro" not in c.grok_image_model

    def test_tesla_yaml_uses_grok_image_provider(self):
        """Tesla is one of the two shows opting in to Grok Imagine in
        this PR. If the YAML drifts back to ``pexels`` (or worse, the
        field disappears) we want CI to flag it before next deploy."""
        cfg = load_config(SHOWS_DIR / "tesla.yaml")
        assert cfg.youtube.image_provider == "grok"

    def test_mab_yaml_uses_grok_image_provider(self):
        """MAB ran on ``pexels`` for the May 2026 A/B test against
        Tesla on Grok Imagine; operator concluded the A/B was
        inconclusive AND the Phase 1 gallery uploader is wired only
        into the Grok Imagine code path (Pexels images never reach
        the gallery R2 bucket). MAB flipped back to ``grok`` so the
        per-show gallery embed on the MAB show page actually has
        images to render. Cost: ~$0.16/episode added (8 images ×
        $0.02 standard model). Flip the YAML AND this assertion in
        the same commit if the show ever moves back to Pexels."""
        cfg = load_config(SHOWS_DIR / "models_agents_beginners.yaml")
        assert cfg.youtube.image_provider == "grok"

    def test_other_shows_remain_on_pexels(self):
        """Every other show (the 9 that aren't YouTube-enabled today,
        plus any future YouTube-enabled show) must stay on Pexels
        until the operator explicitly flips them. Pexels is free;
        Grok costs $0.32/episode."""
        for slug in ("omni_view", "fascinating_frontiers", "planetterrian",
                     "env_intel", "models_agents", "modern_investing",
                     "finansy_prosto", "privet_russian",
                     "unintended_consequences"):
            cfg = load_config(SHOWS_DIR / f"{slug}.yaml")
            assert cfg.youtube.image_provider == "pexels", (
                f"{slug} drifted off pexels — would silently incur Grok "
                f"Imagine cost"
            )
