"""Show configuration schema and YAML loader for the podcast pipeline.

Each show is defined by a YAML file under ``shows/``.  The ``load_config()``
function parses the YAML and returns a typed ``ShowConfig`` dataclass.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional

import yaml

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Dataclass hierarchy
# ---------------------------------------------------------------------------

@dataclass
class SourceConfig:
    url: str
    label: str = ""


@dataclass
class XAccountConfig:
    """An X/Twitter account to pull recent posts from via xAI search."""
    handle: str  # e.g. "sawyermerrit" (no @ prefix)
    label: str = ""  # Human-readable name for attribution
    max_posts: int = 10  # Max posts to fetch per run


@dataclass
class LLMConfig:
    provider: str = "xai"
    model: str = "grok-4.3"
    system_prompt_file: str = ""
    digest_prompt_file: str = ""
    podcast_prompt_file: str = ""
    digest_temperature: float = 0.7
    podcast_temperature: float = 0.7
    max_tokens: int = 3500
    podcast_max_tokens: int = 0  # 0 = use max_tokens for both
    min_podcast_words: int = 1500  # Minimum word count to trigger retry
    # Absolute hard floor below which the runner aborts the episode as
    # "clearly broken" (see run_show.py:1580). Network default 600 is
    # tuned for the news-show shape where 600 words ~ 4 minutes — well
    # under what a real episode should ever produce. Specialist shows
    # with structurally thinner content surfaces (env_intel's
    # alt-cadence BC environmental policy beat is the canonical
    # example) historically come in at 700–900 words on a normal day
    # and can dip into the 500s on a narrow news day without the
    # output being "broken" — set their floor lower so a thin-but-
    # legitimate episode ships instead of being skipped.
    min_podcast_word_floor: int = 600
    podcast_chain: bool = False  # Two-stage generation: outline then expand
    # Model used when the primary refuses after educational retry. A
    # different model (or different variant of the same family) often
    # has different refusal thresholds and can succeed where the primary
    # won't. Pointing back at the older 4.20-reasoning ensures the chain
    # actually switches snapshots on a refusal of grok-4.3.
    fallback_model: str = "grok-4.20-reasoning"
    # Synthesizer (weekly newsletter, monthly report, cross-show briefing)
    # defaults. Empty synth_model means "use model".
    synth_model: str = "grok-4.3"
    synth_max_tokens: int = 8000
    synth_temperature: float = 0.4
    # Episode quality reviewer defaults. Fast/cheap variant is appropriate
    # here — reviewer reads a truncated transcript and emits a short score.
    reviewer_model: str = "grok-4-1-fast-non-reasoning"
    reviewer_max_tokens: int = 1500
    reviewer_temperature: float = 0.3


@dataclass
class TTSConfig:
    # Network default since May 2026: Grok TTS with the operator's
    # English voice `kdif6sqjcyiq`, used for every English show on
    # the network for a single consistent host identity. Replaced
    # the prior `b4cusb2omvkz` voice in May 2026.
    # Russian shows (FP/PR) override voice_id to their custom Olya
    # (`0b875ae2`) and language_code to `ru`. No show is on ElevenLabs
    # in production; the legacy fields below remain only for emergency
    # rollback.
    provider: str = "grok"
    voice_id: str = "kdif6sqjcyiq"
    language_code: str = "en"  # BCP-47 (Grok) / ISO 639-1 (ElevenLabs); shows override for non-English
    max_chars: int = 10000
    # ---- Legacy ElevenLabs baseline ----
    # No show overrides ``provider: elevenlabs`` in production. Kept
    # here so emergency rollback is a one-line flip. Grok path ignores.
    model: str = "eleven_flash_v2_5"
    stability: float = 0.5
    similarity_boost: float = 0.75
    style: float = 0.0
    use_speaker_boost: bool = True
    speed: float = 1.0  # Speech speed (0.7–1.2); Flash v2.5 supports this range
    apply_text_normalization: str = "on"  # "auto", "on", or "off"; helps with number/date pronunciation
    # ---- Speech tag wrap (May 13 2026: re-enabled via single-call path) ----
    # The chunk wrap previously got dropped because Grok TTS occasionally
    # voiced "Fast." aloud at section-TTS boundaries (M&A Ep045, May 11).
    # Re-enabled May 13 2026 via the network ``_defaults.yaml`` after the
    # operator asked for whole-script ``<fast>`` energy on all podcasts.
    # The leak-safe implementation pairs the wrap with
    # ``use_section_tts: False`` and a larger ``max_chars`` so each
    # episode synthesises in a single Grok API call — no boundaries, no
    # leak surface. If ``use_section_tts`` is True AND the wrap is set,
    # the wrap will be applied per-section per-chunk and CAN leak (the
    # historical failure mode). The defaults below preserve backwards-
    # compat at the dataclass level; the network-wide flip lives in
    # ``shows/_defaults.yaml``.
    speech_wrap_open: str = ""
    speech_wrap_close: str = ""
    # When True, the runner splits the script at chapter boundaries
    # and synthesises each section as a separate Grok TTS call,
    # stitching transition stings between. When False, the whole
    # script goes through ``synthesize()`` as a single call (no
    # stings, no boundaries — required for whole-script speech wrap
    # to apply safely). The network default in ``_defaults.yaml`` is
    # False as of May 13 2026.
    use_section_tts: bool = True
    # Post-TTS transcription validation (opt-in)
    validate_transcription: bool = False
    whisper_model: str = "base"  # "tiny", "base", "small", "medium"
    whisper_threshold: float = 0.7  # Minimum match score (0.0–1.0)


@dataclass
class AudioConfig:
    music_file: Optional[str] = None
    background_music_file: Optional[str] = None
    transition_sting: Optional[str] = None
    # Music timing — May 13 2026 outro retune (intro shape unchanged
    # from May 12). Operator listened to TST Ep471 and asked for the
    # outro to "let music run by itself for 20 seconds more and fade
    # out" rather than ramping under the final 20 s of voice +
    # sustaining only 5 s + fading 15 s. Outro now starts AFTER voice
    # ends (no pre-voice-end crossfade), gives ~20 s of clearly-
    # audible music alone, then fades.
    #
    # Intro (unchanged May 12 shape):
    #   * intro_duration 10 s — music alone before voice
    #   * overlap_duration 15 s — music sits with voice
    #   * fade_duration 30 s — slow log-fade under voice
    #   * Total intro music presence = 10+15+30 = 55 s
    #
    # Outro (May 13 retune):
    #   * outro_crossfade 0 s — music does NOT ramp under final voice
    #   * outro_duration 30 s — total post-voice music presence
    #   * outro_fade_out_duration 10 s — clean log-fade-out tail
    #   * Resulting shape: 6 s fade-in + ~14 s sustain + 10 s fade-out
    #     ≈ 20 s music "by itself" before fading, matching operator
    #     direction.
    #
    # ``voice_intro_delay`` MUST stay >= ``intro_duration`` so the
    # voice doesn't enter while the music intro is still in its
    # alone-period (10 >= 10 holds).
    intro_duration: float = 10.0
    overlap_duration: float = 15.0
    fade_duration: float = 30.0
    outro_duration: float = 30.0
    outro_fade_out_duration: float = 10.0
    intro_volume: float = 0.6
    overlap_volume: float = 0.5
    fade_volume: float = 0.4
    # ``outro_volume`` matches ``intro_volume`` (May 15 2026) so the
    # post-voice outro stands out clearly from the ducked-and-fading
    # music that was playing during voice. Setting it equal to
    # ``fade_volume`` (the prior default) created the perceptual
    # equivalence operator caught on TST Ep473: "no music outro at
    # all" — the music WAS playing, but at the same level the
    # listener had been hearing it under-voice for the prior 30 s,
    # so they registered no "music is back" transition.
    outro_volume: float = 0.6
    voice_intro_delay: float = 10.0
    outro_crossfade: float = 0.0


@dataclass
class PublishingConfig:
    rss_file: str = "podcast.rss"
    rss_title: str = "Podcast"
    rss_description: str = ""
    rss_summary: str = ""
    rss_link: str = ""
    rss_author: str = "Patrick"
    rss_email: str = "contact@example.com"
    rss_image: str = ""
    rss_category: str = "Technology"
    # Apple Podcasts allows a category + sub-category pair; the
    # sub-category drives the curated charts inside Apple. Operator
    # caught (May 6 2026 audit) every show emitting a single-level
    # category and missing the sub. Per-show YAML supplies the value.
    rss_subcategory: str = ""
    # ``itunes:keywords`` was officially deprecated by Apple but is
    # still indexed by every other major aggregator (Spotify, Pocket
    # Casts, Fountain, Podcast Index). Cheap SEO win — comma-separated
    # list of 5-10 phrases per show.
    rss_keywords: str = ""
    rss_language: str = "en-us"
    guid_prefix: str = "podcast"
    base_url: str = "https://nerranetwork.com"
    audio_subdir: str = "digests"
    summaries_json: str = "digests/summaries.json"
    summaries_podcast_name: str = ""
    player_html: str = ""
    summaries_html: str = ""
    x_enabled: bool = True
    x_env_prefix: str = "X_"
    x_teaser_template: str = ""
    x_hashtags: str = ""
    host_name: str = "Patrick"


@dataclass
class EpisodeConfig:
    prefix: str = "Podcast"
    filename_pattern: str = "{prefix}_Ep{num:03d}_{date:%Y%m%d_%H%M%S}.mp3"
    output_dir: str = "digests"
    mp3_glob: str = "*_Ep*.mp3"


@dataclass
class StorageConfig:
    provider: str = "github"  # "github" (default) or "r2"
    bucket: str = "podcast-audio"
    endpoint_env: str = "R2_ENDPOINT_URL"
    access_key_env: str = "R2_ACCESS_KEY_ID"
    secret_key_env: str = "R2_SECRET_ACCESS_KEY"
    public_base_url: str = ""


@dataclass
class AnalyticsConfig:
    enabled: bool = False
    prefix_url: str = "https://op3.dev/e/"


@dataclass
class NewsletterConfig:
    enabled: bool = False
    platform: str = "buttondown"
    api_key_env: str = "BUTTONDOWN_API_KEY"
    status: str = "about_to_send"  # "about_to_send", "draft", or "scheduled"
    tag: str = ""  # Buttondown tag for per-show subscriber filtering


@dataclass
class SectionMarker:
    pattern: str = ""
    title: str = ""


@dataclass
class ChaptersConfig:
    enabled: bool = True
    section_markers: List[SectionMarker] = field(default_factory=list)


@dataclass
class ContentTrackingConfig:
    """Cross-episode content tracking configuration.

    If ``section_patterns`` is provided, these regex patterns override the
    hardcoded ``SHOW_SECTION_PATTERNS`` registry in ``content_tracker.py``.
    """
    enabled: bool = True
    max_days: int = 14
    section_patterns: dict = field(default_factory=dict)
    quote_author_cooldown_days: int = 30


@dataclass
class SlowNewsConfig:
    """Slow News Day configuration — evergreen segments instead of skipping."""
    enabled: bool = False
    library_file: str = ""          # e.g. "shows/segments/tesla.json"
    max_segments: int = 2           # Max evergreen segments per slow-news episode
    cooldown_days: int = 30         # Don't reuse a segment within this window
    selection_mode: str = "round_robin"  # "round_robin" or "random"
    repeat_trigger_threshold: int = 3  # Cross-episode repeats that trigger slow news
    # Ratio gate added in the May 2026 content audit. Slow-news mode
    # only fires when BOTH the absolute threshold above AND the
    # repeats-as-fraction-of-digest ratio are exceeded. Raised from
    # 0.40 → 0.55 so daily news shows that legitimately revisit 3-6
    # ongoing stories don't fall back to evergreen segments on
    # healthy news days.
    repeat_trigger_ratio: float = 0.55


@dataclass
class ContentFreshnessConfig:
    """Per-show article freshness filter overrides."""
    lookback_days: int = 0          # 0 = use pipeline default (1 or 3 based on episode count)
    similarity_threshold: float = 0.0  # 0.0 = use pipeline default


@dataclass
class YouTubeConfig:
    """Per-show YouTube publishing configuration.

    Network-wide defaults live in ``shows/_defaults.yaml`` under
    ``youtube:``; show YAMLs override individual fields. The synthesized
    voice means every upload sets ``status.containsSyntheticMedia=True``
    (the API field YouTube introduced in October 2024 for AI disclosure).
    """
    enabled: bool = False
    channel: str = "en"                    # "en" or "ru" — picks refresh token
    category_id: int = 28                  # 28 = Science & Tech (sane default)
    default_language: str = "en"
    privacy_status: str = "public"         # "public" | "unlisted" | "private"
    publish_long_form: bool = True
    publish_shorts: bool = True
    short_duration_seconds: float = 55.0
    # Seconds into the final mixed MP3 where the Shorts clip begins.
    # When unset, ``shorts_start_mode`` picks the offset (default ``voice``
    # = ``audio.voice_intro_delay`` only — not intro_duration + delay).
    shorts_start_offset: Optional[float] = None
    # ``voice`` | ``first_chapter`` — see engine.youtube_shorts.
    shorts_start_mode: str = "voice"
    # ``always`` | ``alternate_episodes`` — skip Shorts on odd episode
    # numbers to halve upload quota during phased rollout.
    shorts_upload_schedule: str = "always"
    tags: List[str] = field(default_factory=list)
    synthetic_disclosure: str = ""
    podcast_playlist_id: Optional[str] = None
    # ---- Slideshow imagery (Pexels search) ----
    # Curated, disambiguated search phrases. When non-empty, these are
    # used verbatim and the show's ``keywords:`` list is ignored. This
    # is the safer path for shows whose keywords collide with photography
    # terms — e.g. Tesla "model 3" returns fashion models on Pexels, not
    # cars. Keep entries short, concrete, and always include the show's
    # primary subject (e.g. "tesla supercharger", not "supercharger").
    image_queries: List[str] = field(default_factory=list)
    # Fallback prefix prepended to each ``keywords:`` entry when
    # ``image_queries:`` is empty. Disambiguates collision-prone tokens
    # like "model 3" / "bonds" / "growth". Trailing space is required if
    # you want a space between prefix and keyword (e.g. "tesla ").
    image_query_prefix: str = ""
    # Pexels result safety filter. Any photo whose pexels URL slug or
    # alt text contains one of these substrings (case-insensitive) is
    # discarded. Set per-show to suppress people-only / off-topic
    # results that slip through even disambiguated queries. The default
    # list catches the worst Tesla / news-show offenders; shows whose
    # subject IS people (e.g. a hypothetical "Founders" show) should
    # override with an empty list or a narrower one.
    image_safe_skip_terms: List[str] = field(default_factory=lambda: [
        "topless", "panties", "lingerie", "nude", "bikini",
        "girl-with", "blonde-girl", "adolescent",
        "silhouette-of-woman", "woman-in-spotlight",
        "model-in", "topless-model",
    ])
    # ---- Image provider (May 2026 rollout) ----
    # ``pexels``  — free Pexels search (default; safe / well-tested).
    # ``grok``    — fresh per-episode images via Grok Imagine for both
    #               long-form AND Shorts, with separate prompt sets so
    #               the two formats no longer share imagery (operator's
    #               complaint May 6 2026). Costs ~$0.32 / episode at
    #               the standard ``grok-imagine-image`` model rate.
    # ``hybrid``  — Pexels for long-form, Grok for Shorts. Halfway
    #               option for shows that want unique Shorts content
    #               without paying for long-form re-rendering.
    image_provider: str = "pexels"
    # ``grok-imagine-image`` ($0.02/image, 300 req/min) is the safe
    # default. ``grok-imagine-image-pro`` ($0.07/image, 30 req/min)
    # is the higher-quality tier — use only on a show flagged for
    # quality emphasis since it's 3.5× the cost.
    grok_image_model: str = "grok-imagine-image"
    # Optional one-line tone descriptor injected into every Grok prompt.
    # Defaults to a generic photojournalism cue; shows can override
    # (e.g. UC's narrative tone might want "documentary archival photo").
    grok_image_descriptor: str = "photorealistic news photo"
    # Optional path (relative to repo root) to a text template for the
    # long-form description body. Placeholders: {hook}, {episode_num},
    # {show_name}, {today_str}. When empty, uses digest paragraphs.
    description_prompt_file: str = ""
    # Appended to the description as an operator copy-paste block (YouTube
    # has no API for pinned comments without extra scopes).
    pinned_comment_template: str = ""
    # When true and vertical scene images exist, build a 1080×1920 Shorts
    # thumbnail instead of reusing the 1280×720 long-form thumb.
    shorts_thumbnail_from_scene: bool = True

    # End-screen CTA card on Shorts (May 2026). When enabled, the last
    # ``shorts_end_card_duration_seconds`` of the Shorts MP4 overlay a
    # translucent black panel with a "WATCH FULL EPISODE / Tap Subscribe ↗"
    # CTA — pointing the viewer at YouTube's own Subscribe button on
    # the Shorts player's right rail. Per-show texts let an operator
    # localise (Russian shows, etc.) or A/B different copy without
    # touching engine/video.py.
    shorts_end_card_enabled: bool = True
    shorts_end_card_main_text: str = "WATCH FULL EPISODE"
    shorts_end_card_sub_text: str = "Tap Subscribe ↗"
    shorts_end_card_duration_seconds: float = 3.0

    # Multiple Shorts per episode (May 2026). When > 1, the
    # smart-selector picks the top-N non-overlapping engaging windows
    # from the episode transcript and publishes each as its own
    # Short, with distinct title (taken from each window's opening
    # text) and distinct thumbnail. Default 1 preserves legacy
    # single-Short behaviour. Quota caveat: each Short upload costs
    # 1 600 quota units on the YouTube Data API; the @NerraNetwork
    # channel has 10 000/day total. With Tesla + MAB long+short
    # already at 6 400 (4 uploads × 1 600), only 2 extra Shorts fit
    # before hitting the cap. ``smart`` shorts_start_mode is
    # required: voice / first_chapter modes only know about one
    # offset so they ignore this knob and always produce 1 Short.
    shorts_per_episode: int = 1


@dataclass
class ShowConfig:
    name: str = ""
    slug: str = ""
    description: str = ""
    sources: List[SourceConfig] = field(default_factory=list)
    x_accounts: List[XAccountConfig] = field(default_factory=list)
    keywords: List[str] = field(default_factory=list)
    web_search_queries: List[str] = field(default_factory=list)
    min_articles: int = 3  # Minimum articles before expanding search
    min_articles_skip: int = 3  # Hard cutoff — skip episode if fewer articles
    min_audio_duration: int = 0  # Minimum audio seconds — skip if shorter (0 = disabled)
    max_weekly_cost_usd: float = 0.0  # 0 = no limit; >0 skips episode if 7-day spend exceeds
    llm: LLMConfig = field(default_factory=LLMConfig)
    tts: TTSConfig = field(default_factory=TTSConfig)
    audio: AudioConfig = field(default_factory=AudioConfig)
    publishing: PublishingConfig = field(default_factory=PublishingConfig)
    episode: EpisodeConfig = field(default_factory=EpisodeConfig)
    storage: StorageConfig = field(default_factory=StorageConfig)
    analytics: AnalyticsConfig = field(default_factory=AnalyticsConfig)
    newsletter: NewsletterConfig = field(default_factory=NewsletterConfig)
    chapters: ChaptersConfig = field(default_factory=ChaptersConfig)
    content_tracking: ContentTrackingConfig = field(default_factory=ContentTrackingConfig)
    slow_news: SlowNewsConfig = field(default_factory=SlowNewsConfig)
    content_freshness: ContentFreshnessConfig = field(default_factory=ContentFreshnessConfig)
    youtube: YouTubeConfig = field(default_factory=YouTubeConfig)
    # Sunday weekly-recap mode. When ``true`` and the runner ticks on
    # a Sunday, the show skips the daily news fetch and instead
    # synthesises a recap from the past 7 days of episodes pulled
    # from the content lake. May 2026 schedule overhaul: 7 shows on
    # daily cadence (OV, PT, FF, M&A, MAB, MIT, TST) opt in.
    weekly_recap_on_sunday: bool = False
    # Narrative mode (May 2026 — Unintended Consequences). When
    # ``true``, the runner skips RSS fetch + slow-news fallback +
    # the digest stage and instead pulls the next unproduced topic
    # from ``topic_queue_file`` to feed straight into the podcast
    # prompt. Used for evergreen story-driven shows that don't
    # depend on daily news cycles.
    narrative_mode: bool = False
    topic_queue_file: str = ""


# ---------------------------------------------------------------------------
# Loader
# ---------------------------------------------------------------------------

def _build_sources(raw: list) -> List[SourceConfig]:
    """Convert a list of dicts or strings into SourceConfig objects."""
    sources = []
    for item in raw or []:
        if isinstance(item, str):
            sources.append(SourceConfig(url=item))
        elif isinstance(item, dict):
            sources.append(SourceConfig(url=item.get("url", ""), label=item.get("label", "")))
    return sources


def _build_x_accounts(raw: list) -> List[XAccountConfig]:
    """Convert a list of dicts into XAccountConfig objects."""
    accounts = []
    for item in raw or []:
        if isinstance(item, dict):
            handle = item.get("handle", "").lstrip("@")
            if handle:
                accounts.append(XAccountConfig(
                    handle=handle,
                    label=item.get("label", f"@{handle}"),
                    max_posts=item.get("max_posts", 5),
                ))
    return accounts


def _build_section_markers(raw: list) -> List[SectionMarker]:
    """Convert a list of dicts into SectionMarker objects."""
    markers = []
    for item in raw or []:
        if isinstance(item, dict):
            markers.append(SectionMarker(
                pattern=item.get("pattern", ""),
                title=item.get("title", ""),
            ))
    return markers


def _build_chapters(raw: dict) -> ChaptersConfig:
    """Build a ChaptersConfig from a dict, handling nested section_markers."""
    if not raw or not isinstance(raw, dict):
        return ChaptersConfig()
    markers = _build_section_markers(raw.get("section_markers"))
    enabled = raw.get("enabled", True)
    return ChaptersConfig(enabled=enabled, section_markers=markers)


def _build_nested(cls, raw: dict):
    """Instantiate a dataclass from a dict, ignoring unknown keys."""
    if not raw or not isinstance(raw, dict):
        return cls()
    known = {f.name for f in cls.__dataclass_fields__.values()}
    return cls(**{k: v for k, v in raw.items() if k in known})


def _deep_merge(base: dict, override: dict) -> dict:
    """Deep-merge *override* into *base* (one level of nesting).

    Top-level keys from *override* replace *base*.  For dict-valued keys,
    the inner dicts are merged so that the show can override individual
    fields without losing sibling defaults.
    """
    merged = dict(base)
    for key, value in override.items():
        if (
            key in merged
            and isinstance(merged[key], dict)
            and isinstance(value, dict)
        ):
            merged[key] = {**merged[key], **value}
        else:
            merged[key] = value
    return merged


def load_config(yaml_path: str | Path) -> ShowConfig:
    """Load a show configuration from a YAML file.

    If ``shows/_defaults.yaml`` exists alongside the show config, it is
    loaded first and the show-specific values are deep-merged on top.
    This allows network-wide defaults (storage, TTS tuning, analytics)
    to be defined once instead of repeated in every show YAML.

    Parameters
    ----------
    yaml_path:
        Path to a YAML file (absolute or relative to cwd).

    Returns
    -------
    ShowConfig
        Fully populated config with defaults for any missing fields.
    """
    path = Path(yaml_path)
    if not path.exists():
        raise FileNotFoundError(f"Config file not found: {path}")

    # Load network defaults if available
    defaults_path = path.parent / "_defaults.yaml"
    defaults: dict = {}
    if defaults_path.exists():
        with open(defaults_path, "r", encoding="utf-8") as f:
            defaults = yaml.safe_load(f) or {}

    with open(path, "r", encoding="utf-8") as f:
        show_data = yaml.safe_load(f) or {}

    data = _deep_merge(defaults, show_data)

    config = ShowConfig(
        name=data.get("name", ""),
        slug=data.get("slug", ""),
        description=data.get("description", ""),
        sources=_build_sources(data.get("sources")),
        x_accounts=_build_x_accounts(data.get("x_accounts")),
        keywords=data.get("keywords", []),
        web_search_queries=data.get("web_search_queries", []),
        min_articles=data.get("min_articles", 3),
        min_articles_skip=data.get("min_articles_skip", 3),
        min_audio_duration=int(
            data.get("min_audio_duration")
            or (data.get("audio") or {}).get("min_audio_duration")
            or 0
        ),
        max_weekly_cost_usd=float(data.get("max_weekly_cost_usd", 0.0)),
        llm=_build_nested(LLMConfig, data.get("llm")),
        tts=_build_nested(TTSConfig, data.get("tts")),
        audio=_build_nested(AudioConfig, data.get("audio")),
        publishing=_build_nested(PublishingConfig, data.get("publishing")),
        episode=_build_nested(EpisodeConfig, data.get("episode")),
        storage=_build_nested(StorageConfig, data.get("storage")),
        analytics=_build_nested(AnalyticsConfig, data.get("analytics")),
        newsletter=_build_nested(NewsletterConfig, data.get("newsletter")),
        chapters=_build_chapters(data.get("chapters")),
        content_tracking=_build_nested(ContentTrackingConfig, data.get("content_tracking")),
        slow_news=_build_nested(SlowNewsConfig, data.get("slow_news")),
        content_freshness=_build_nested(ContentFreshnessConfig, data.get("content_freshness")),
        youtube=_build_nested(YouTubeConfig, data.get("youtube")),
        weekly_recap_on_sunday=bool(data.get("weekly_recap_on_sunday", False)),
        narrative_mode=bool(data.get("narrative_mode", False)),
        topic_queue_file=str(data.get("topic_queue_file", "") or ""),
    )
    logger.info("Loaded config for '%s' from %s", config.name, path)
    return config
