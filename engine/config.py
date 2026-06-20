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
    # June 2026 (Tesla quality pass): when true, the one-shot expansion
    # retry in generate_podcast_script fires whenever the script lands
    # under the FULL min_podcast_words target instead of only near the
    # 60%-of-target skip floor. Costs one extra LLM call on short days.
    podcast_expand_below_target: bool = False
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

    # Tag-leak hard block (quick win from May 2026 full codebase review)
    # When True, scan_transcript() finding any spoken speech tag after Grok TTS
    # causes the pipeline to hard-fail the episode (before audio mix / publish).
    # Default False keeps the historical best-effort behaviour (metric + warning).
    # Per-show override allowed once the detector's false-positive rate is
    # calibrated on real episodes for that voice/show.
    tag_leak_hard_block: bool = False


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
    # Cross-promo reply tweet under the daily teaser (June 2026 growth
    # pass). x_handle is the @handle the show posts as (used for the
    # "Follow @…" line; leave empty to omit the line). x_cross_promo
    # gates the whole reply — false is a byte-for-byte no-op.
    x_handle: str = ""
    x_cross_promo: bool = False
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
class MultilingualConfig:
    """Opt-in multilingual *audio* settings for a show (June 2026).

    When ``enabled``, the post-hoc translation stage
    (``scripts/generate_translations.py`` + ``engine/translate.py``) can
    render alternate-language audio tracks of an already-finalized English
    episode, voiced by the operator's cloned Grok voice. English remains
    the canonical master + site fallback; translations are derived
    artifacts surfaced on the website (never in the canonical podcast RSS).

    Fields are declared here (not read via getattr on the raw dict) so
    ``_build_nested`` doesn't silently drop them — see landmine #20.
    """
    enabled: bool = False
    # When True, the daily pipeline (run_show.py) auto-generates the
    # configured languages for each newly published episode — best-effort
    # and non-blocking (a failure never breaks the English publish). When
    # False, translations are produced only via the manual driver.
    auto: bool = False
    # BCP-47 codes to render. Default empty; the driver also accepts a
    # ``--languages`` override so a show with no block can still be run.
    languages: List[str] = field(default_factory=list)
    # Name of the env var holding the cloned Grok voice ID. The ID itself
    # is NEVER stored in YAML/git — it's pasted into ``.env``. The TTS
    # call reads it at runtime and fails loud if unset.
    cloned_voice_env: str = "GROK_CLONED_VOICE_ID"


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
    # June 10 2026: these fields were set in show YAMLs and read via
    # getattr() on this dataclass — but never DECLARED here, so
    # _build_nested silently dropped them and the getattr defaults always
    # won. Most damaging: requires_financial_disclaimer was always False,
    # so the financial-show newsletters shipped without the disclaimer
    # their YAML requested. (Template paths that read the RAW yaml dict
    # were unaffected — the two access styles had silently diverged.)
    short_label: str = ""
    emoji: str = ""
    newsletter_start_date: str = ""
    requires_financial_disclaimer: bool = False
    length_target_words: int = 0
    adjacent_shows: list = field(default_factory=list)
    network_adjacencies: dict = field(default_factory=dict)


@dataclass
class SectionMarker:
    pattern: str = ""
    title: str = ""
    # Optional positional constraint: "start" = only match in the opening
    # ~10% of the script, "end" = only in the closing ~15%, "" = anywhere.
    # Added June 2026 after the Tesla closing ("find us on X at tesla
    # shorts time") re-matched the case-insensitive Introduction marker on
    # every episode, titling the closing "Introduction" in podcast apps.
    where: str = ""


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
class DeepDiveConfig:
    """Per-episode deep-dive override (May 2026).

    Lets a normally news-driven show (e.g. Modern Investing) produce an
    occasional standalone single-subject deep-dive episode without
    permanently switching to ``narrative_mode``. The runner checks
    ``queue_file`` at the start of each run; if a topic is scheduled for
    today (``date: YYYY-MM-DD``) or flagged ``when: next``, that single
    episode bypasses the news fetch + slow-news + digest-validation path
    and runs off the topic with the deep-dive prompt files, then
    auto-reverts to the normal daily pipeline. A specific topic can also
    be forced on demand via ``run_show.py <show> --deep-dive <id>``,
    regardless of schedule. Queue entries share the
    ``shows/topic_queues`` schema (id / title / brief / produced /
    episode_number / produced_date) plus the optional ``date`` / ``when``
    scheduling keys.
    """
    enabled: bool = False
    queue_file: str = ""            # e.g. "shows/deep_dives/modern_investing.yaml"
    # Prompt overrides used only on a deep-dive run. Empty = fall back to
    # the show's normal llm.*_prompt_file (rarely what you want — a deep
    # dive has a different shape than a daily news episode).
    digest_prompt_file: str = ""    # outline / brief expansion prompt
    podcast_prompt_file: str = ""   # full-script prompt
    system_prompt_file: str = ""    # optional system-prompt override
    # Deep dives want more depth than a daily episode. When > 0, this overrides
    # the show's llm.min_podcast_words for a deep-dive run, so the thin-script
    # retry + length gate push the episode to full length instead of accepting
    # a daily-sized script (MIT Ep059 shipped 1,252 words against a 1,300 daily
    # target — far short of a real deep dive). 0 = inherit the show's value.
    min_podcast_words: int = 0


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
    # Smart-selector noise floor: candidate Shorts windows scoring below
    # this fall back to the legacy voice start. June 10 2026 fix: this
    # field was MISSING from the dataclass, so Tesla's 3.5 YAML override
    # (May 2026 retune) was silently dropped by _build_nested and every
    # episode ran at the 5.0 default — Ep505's "best score 3.0 below
    # threshold 5.0" fallback was this bug, not a quiet news day.
    shorts_min_score_threshold: float = 5.0
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
    # default for new shows. ``grok-imagine-image-quality`` ($0.05/image,
    # 300 req/min; released 2026-04-03, supersedes the old
    # ``grok-imagine-image-pro`` id) is the higher-quality tier the
    # YouTube-image shows opt into via their YAML.
    grok_image_model: str = "grok-imagine-image"
    # Optional one-line tone descriptor injected into every Grok prompt.
    # Defaults to a generic photojournalism cue; shows can override
    # (e.g. UC's narrative tone might want "documentary archival photo").
    grok_image_descriptor: str = "photorealistic news photo"

    # ---- Video generation (June 2026 Grok Video experiment) ----
    # When set to "grok", generates full-length videos from the podcast
    # script instead of still-image slideshows. Pricing: $0.05-0.07/second
    # depending on resolution. Falls back to image slideshow on any failure.
    # When empty/null, uses the image provider path instead.
    video_provider: str = ""
    # Video resolution: "720p" (HD) or "480p" (standard). 720p is YouTube
    # quality; 480p is cheaper but lower quality. Default empty = not used.
    video_resolution: str = ""
    # Aspect ratio for video generation. "16:9" for full-length episodes,
    # "9:16" for Shorts. Default empty = not used.
    video_aspect_ratio: str = ""

    # ---- Show-specific video prompt customization ----
    # Genre/category for the show (e.g., "automotive-tech-news", "aerospace-engineering",
    # "science-space-discovery"). Used to guide Grok's visual generation.
    video_genre: str = ""
    # Emotional mood/tone for the video (e.g., "energetic-professional",
    # "awe-inspiring-technical", "curious-wonder-educational").
    video_mood: str = ""
    # Keywords/topics specific to the show. Injected into video prompts
    # so Grok knows what to visualize (e.g., Tesla cars, rockets, AI concepts).
    video_keywords: List[str] = field(default_factory=list)
    # Multi-line visual style descriptor. Example:
    # "Cinematic product reveals, technical demos, factory automation,
    #  futuristic concept renders, engineering close-ups, real-world EV footage"
    # This provides detailed visual direction to Grok beyond just the genre.
    video_visual_style: str = ""

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

    # ---- Multi-platform distribution (Instagram Reels / TikTok / etc.) ----
    # When true, each published Short additionally gets (1) a "safe-zone"
    # variant MP4 with overlays lifted out of the bottom/right bands that IG
    # Reels and TikTok draw their own UI (caption + action rail) over, and
    # (2) a "<short>.social.json" sidecar carrying per-platform caption +
    # hashtags. Actual posting is handled by engine.social_publisher, which is
    # a clean no-op until the platform API credentials are configured. Default
    # false → YouTube-only behaviour is byte-for-byte unchanged.
    multi_platform_enabled: bool = False
    instagram_enabled: bool = False
    tiktok_enabled: bool = False
    # Safe-zone overlay tuning for the social variant (1080×1920). IG/TikTok
    # cover the bottom ~16% (caption + CTA) and right ~12% (like/share rail).
    # Captions are bottom-centre, so only the vertical margin needs lifting;
    # the URL pill + end-card are dropped (the caption text carries the link).
    social_caption_margin_v: int = 480     # ASS MarginV (px from bottom)
    social_drop_url_pill: bool = True
    social_drop_end_card: bool = True
    # R2 bucket key prefix for ready-to-post social assets (video + sidecar).
    # Empty = keep assets local only (no upload).
    social_r2_prefix: str = ""


@dataclass
class ShowConfig:
    name: str = ""
    slug: str = ""
    description: str = ""
    sources: List[SourceConfig] = field(default_factory=list)
    x_accounts: List[XAccountConfig] = field(default_factory=list)
    # X *sourcing* toggle, independent of X *posting* (publishing.x_enabled).
    # None = inherit x_enabled (back-compat); True/False = explicit override.
    # Lets a non-posting show (e.g. MAB) still read its curated X accounts
    # for content. See engine.fetcher.x_fetch_allowed.
    x_fetch_enabled: Optional[bool] = None
    keywords: List[str] = field(default_factory=list)
    # Case-insensitive regex patterns; articles whose TITLE matches any are
    # dropped at fetch time. For suppressing recurring almanac/evergreen
    # content (moon calendars, planet-visibility roundups, "this day in
    # history") — see engine.utils.drop_excluded_titles.
    exclude_title_patterns: List[str] = field(default_factory=list)
    web_search_queries: List[str] = field(default_factory=list)
    min_articles: int = 3  # Minimum articles before expanding search
    min_articles_skip: int = 3  # Hard cutoff — skip episode if fewer articles
    min_audio_duration: int = 0  # Minimum audio seconds — skip if shorter (0 = disabled)
    max_weekly_cost_usd: float = 0.0  # 0 = no limit; >0 skips episode if 7-day spend exceeds
    # Item 4 stronger breakers (May 2026 review)
    max_weekly_tts_chars: int = 0          # 0 = off; summed from recent metrics_ep*.json
    max_weekly_grok_images: int = 0        # 0 = off
    max_tts_chars_per_episode: int = 0     # hard stop before synthesis (0 = off)
    max_grok_images_per_episode: int = 0   # hard stop before image gen (0 = off)
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
    multilingual: MultilingualConfig = field(default_factory=MultilingualConfig)
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
    # Per-episode deep-dive override (see DeepDiveConfig). Distinct from
    # narrative_mode: the show stays news-driven by default and only a
    # scheduled / forced episode runs as a standalone deep dive.
    deep_dive: DeepDiveConfig = field(default_factory=DeepDiveConfig)
    # Recursive narrative-memory (Phase 3). When true, the show's pre_fetch
    # hook injects a {narrative_memory_section} block (programs + open
    # questions + mined themes) into the digest/podcast prompts, and its
    # post_generate hook mines themes from each episode. Per-show config lives
    # in engine.show_memory.SHOW_MEMORY_CONFIGS. Default false = no-op.
    memory_enabled: bool = False


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
                where=item.get("where", ""),
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
    """Instantiate a dataclass from a dict, ignoring unknown keys.

    Unknown keys are dropped for forward/backward compat, but LOUDLY —
    a silently-ignored knob cost the Tesla smart-Shorts selector a month
    of running at the wrong threshold (the YAML set a field the
    dataclass didn't declare; see YouTubeConfig.shorts_min_score_threshold).
    """
    if not raw or not isinstance(raw, dict):
        return cls()
    known = {f.name for f in cls.__dataclass_fields__.values()}
    unknown = set(raw) - known
    if unknown:
        logger.warning(
            "%s: ignoring unknown config key(s) %s — add the field to the "
            "dataclass in engine/config.py if it's meant to do something",
            cls.__name__, sorted(unknown),
        )
    return cls(**{k: v for k, v in raw.items() if k in known})


def _deep_merge(base: dict, override: dict) -> dict:
    """Deep-merge *override* into *base* (fully recursive).

    This was upgraded from one-level to recursive as part of the
    May 2026 maintainability improvements (item 1 in the review plan).
    """
    merged = dict(base)
    for key, value in override.items():
        if key in merged and isinstance(merged[key], dict) and isinstance(value, dict):
            merged[key] = _deep_merge(merged[key], value)
        else:
            merged[key] = value
    return merged


def discover_show_slugs(shows_dir: Path | None = None) -> list[str]:
    """Centralized discovery of all active show slugs.

    This is the single source of truth for "which shows exist" to eliminate
    the duplication currently spread across run_show.py, generate_dashboard.py,
    archive scripts, scaffold, etc. (part of the larger pipeline extraction
    and maintainability work from the May 2026 review).
    """
    if shows_dir is None:
        shows_dir = Path(__file__).resolve().parent.parent / "shows"

    NON_SHOW = {"pronunciation_map", "network_meta", "scaffold_pending",
                "translation_overrides"}
    slugs: list[str] = []
    for p in sorted(shows_dir.glob("*.yaml")):
        stem = p.stem
        if stem.endswith("_template"):
            continue
        if stem.startswith("_"):
            continue
        if stem in NON_SHOW:
            continue
        slugs.append(stem)
    return slugs


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
        x_fetch_enabled=data.get("x_fetch_enabled"),
        keywords=data.get("keywords", []),
        exclude_title_patterns=data.get("exclude_title_patterns", []),
        web_search_queries=data.get("web_search_queries", []),
        min_articles=data.get("min_articles", 3),
        min_articles_skip=data.get("min_articles_skip", 3),
        min_audio_duration=int(
            data.get("min_audio_duration")
            or (data.get("audio") or {}).get("min_audio_duration")
            or 0
        ),
        max_weekly_cost_usd=float(data.get("max_weekly_cost_usd", 0.0)),
        max_weekly_tts_chars=int(data.get("max_weekly_tts_chars", 0) or 0),
        max_weekly_grok_images=int(data.get("max_weekly_grok_images", 0) or 0),
        max_tts_chars_per_episode=int(data.get("max_tts_chars_per_episode", 0) or 0),
        max_grok_images_per_episode=int(data.get("max_grok_images_per_episode", 0) or 0),
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
        multilingual=_build_nested(MultilingualConfig, data.get("multilingual")),
        weekly_recap_on_sunday=bool(data.get("weekly_recap_on_sunday", False)),
        narrative_mode=bool(data.get("narrative_mode", False)),
        topic_queue_file=str(data.get("topic_queue_file", "") or ""),
        deep_dive=_build_nested(DeepDiveConfig, data.get("deep_dive")),
        memory_enabled=bool(data.get("memory_enabled", False)),
    )
    logger.info("Loaded config for '%s' from %s", config.name, path)
    return config
