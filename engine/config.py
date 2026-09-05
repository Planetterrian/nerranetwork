"""Show configuration schema and YAML loader for the podcast pipeline.

Each show is defined by a YAML file under ``shows/``.  The ``load_config()``
function parses the YAML and returns a typed ``ShowConfig`` dataclass.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

import yaml

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Dataclass hierarchy
# ---------------------------------------------------------------------------

@dataclass
class SourceConfig:
    url: str
    label: str = ""
    # When true, the fetch stage reports this feed's newest entry (date +
    # title) into the digest prompt's {campaign_freshness} block even when
    # that entry falls outside the recency window. Powers the Aug 2026
    # offshore_north verified-absence rule: "the team's site was last
    # updated on [date], with [subject]" is checkable; "no news this week"
    # is not. Default false — shows without the flag are untouched.
    freshness_report: bool = False


@dataclass
class XAccountConfig:
    """An X/Twitter account to pull recent posts from via xAI search."""
    handle: str  # e.g. "sawyermerrit" (no @ prefix)
    label: str = ""  # Human-readable name for attribution
    max_posts: int = 10  # Max posts to fetch per run


@dataclass
class LLMConfig:
    provider: str = "xai"
    # grok-4.3 — the 2026-08-18 grok-4.6 upgrade was REVERTED the same
    # day (4.6 digest latency 5-10× 4.3; 7 of 12 shows failed). Future
    # upgrades follow docs/model_upgrade_playbook.md (staged, one show
    # first, latency-gated).
    model: str = "grok-4.3"
    system_prompt_file: str = ""
    digest_prompt_file: str = ""
    podcast_prompt_file: str = ""
    digest_temperature: float = 0.7
    podcast_temperature: float = 0.7
    max_tokens: int = 3500
    podcast_max_tokens: int = 0  # 0 = use max_tokens for both
    min_podcast_words: int = 1500  # Minimum word count to trigger retry
    # Sep 5 2026 delivery review: when this share (0-100) of the finished
    # script's 8-word phrases appears verbatim in the digest, the script
    # stage is re-run ONCE with the copied sentences named and an
    # instruction to write them in spoken English; the rewrite is kept
    # only when it copies less and is not truncated. 0 = off (default;
    # the nine English news shows set it in their YAML). This is a
    # REWRITE gate, not a length lever — it never changes a length target
    # and never fires on word count (the banned podcast-side retry class).
    script_rewrite_gate_overlap_pct: float = 0.0
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
    # July 18 2026 (Omni View realignment): flavor of the podcast-stage
    # expansion retry. "" = legacy behavior (news shows get "cover more
    # stories"; narrative_mode shows get the deepen-the-brief variant).
    # "deepen" = expand by deepening the stories already covered, never
    # adding stories — for news shows whose prompt requires a FIXED story
    # slate, where "cover more stories" would fight the format.
    podcast_expansion_style: str = ""
    # June 2026 (First Principles quality pass): digest-stage analogue of
    # ``podcast_expand_below_target``. When ``digest_expand_below_target`` is
    # true AND the generated digest/brief is under ``min_digest_words``,
    # generate_digest fires ONE deepen-the-brief retry. Opt-in (default 0 /
    # False = byte-for-byte no-op). Added for narrative shows whose brief is
    # the substrate the podcast expands from: FP briefs shipped 848-1116w vs
    # the prompt's 1600 floor, capping the podcast even after the podcast-
    # stage retry. ``min_digest_words`` is the retry trigger, NOT a hard
    # target — set it below the observed grok-4.3 ~1200-1500w plateau so it
    # rescues genuinely-thin briefs without fighting the ceiling.
    min_digest_words: int = 0
    digest_expand_below_target: bool = False
    podcast_chain: bool = False  # Two-stage generation: outline then expand
    # Model used when the primary refuses after educational retry. A
    # different model (or different variant of the same family) often
    # has different refusal thresholds and can succeed where the primary
    # won't. Back on grok-4.20-reasoning with the 2026-08-18 revert —
    # the primary is grok-4.3 again, so 4.3 cannot be its own fallback.
    fallback_model: str = "grok-4.20-reasoning"
    # Podcast SCRIPT stage override (2026-07-31). Empty = use ``model``
    # (byte-identical). Exists so a newer Grok release can be A/B'd on
    # the prose stage of ONE show without touching the facts-first
    # digest/fetch stage: grok-4.5 (2026-07-08) is a large capability
    # jump but measures worse on confident-hallucination benchmarks, so
    # the digest keeps grok-4.3 while a script-stage trial is cheap
    # (~15k tokens/ep). Setting this changes shipped audio — per-show
    # A/B-listen required (landmine #17).
    podcast_model: str = ""
    # Synthesizer (weekly newsletter, monthly report, cross-show briefing)
    # defaults. Empty synth_model means "use model". grok-4.6 since the
    # 2026-08-18 staged trial (staged-grok-46-trial) — mirrors
    # shows/_defaults.yaml.
    synth_model: str = "grok-4.6"
    synth_max_tokens: int = 8000
    synth_temperature: float = 0.4
    # Episode quality reviewer defaults. grok-4.6 since the 2026-08-18
    # staged trial (staged-grok-46-trial) — mirrors shows/_defaults.yaml,
    # including the instrument-change caveat documented there.
    reviewer_model: str = "grok-4.6"
    reviewer_max_tokens: int = 1500
    reviewer_temperature: float = 0.3
    # Optional xAI reasoning depth for models that support it (grok-4.5:
    # low|medium|high). Empty string = omit the parameter (byte-identical
    # to pre-wiring requests on grok-4.3). Do NOT set on digest/podcast
    # paths without an A/B listen when the model change alters prose.
    reasoning_effort: str = ""


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

    # ---- Two-host dialogue mode (July 2026, dp_pod) ----
    # When True, the podcast script is speaker-labeled dialogue (one turn
    # per paragraph, e.g. ``DAN: ...`` / ``PATRICK: ...``) and TTS routes
    # each speaker's turns to that speaker's Grok voice via
    # ``engine.tts_dialogue.synthesize_dialogue``. The three pipeline
    # layers that strip host prefixes are gated on this flag so the
    # labels survive to synthesis. Dialogue mode never applies
    # ``speech_wrap_*`` (per-turn wraps are the historical "Fast." leak
    # shape multiplied by every speaker handoff). Default False is a
    # byte-for-byte no-op for single-host shows.
    dialogue_mode: bool = False
    # Uppercase speaker label -> Grok voice ID, e.g.
    # ``{PATRICK: kdif6sqjcyiq, DAN: 0vscf8u8yrxc}``. ``voice_id`` above
    # stays the single-voice fallback when a script arrives unlabeled.
    dialogue_voices: dict = field(default_factory=dict)
    # Trailing silence (ms) padded onto each speaker turn-group so
    # handoffs breathe instead of crossfading mid-word.
    dialogue_pause_ms: int = 300


@dataclass
class AudioConfig:
    music_file: Optional[str] = None
    background_music_file: Optional[str] = None
    transition_sting: Optional[str] = None
    # ---- Debut full-song outro (July 2026, The DP Pod Ep1) ----
    # When ``debut_song_file`` is set AND the episode number equals
    # ``debut_song_episode``, the full song is appended once after the
    # normal outro (the script's closing introduces it on air). Defaults
    # are a no-op for every show/episode.
    debut_song_file: Optional[str] = None
    debut_song_episode: int = 0
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
    # July 16 2026 — adeclick + afftdn stage in normalize_voice()
    # (measured hiss/tick cleanup; see engine/audio.py
    # _voice_norm_full_cmd docstring). Per-show opt-out:
    # ``audio.voice_denoise: false`` restores the pre-July-16 chain.
    voice_denoise: bool = True


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
    # sub-category drives the curated charts inside Apple. Per-show YAML
    # supplies the value.
    #
    # CORRECTION (July 2026): the May 6 2026 audit noted here that every
    # show emitted a single-level category and was "missing the sub".
    # That was wrong for the Technology shows — Apple's Technology
    # category has NO subcategories, so there was never one to add. They
    # showed a single genre in Podcasts Connect because that is correct.
    # What they actually lacked is a SECOND category (below).
    rss_subcategory: str = ""
    # Apple allows a SECOND category (primary + secondary), each with its
    # own subcategory. The second appears on its own category page, so it
    # is a free discoverability slot. Note Technology has no subcategories
    # at all — see engine/feed_categories.py; a Technology show widens
    # reach via this field, not via rss_subcategory.
    rss_category2: str = ""
    rss_subcategory2: str = ""
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
    # Operator has listened to a ZH sample for THIS show and approved batch
    # Chinese (generate_translations.py's --zh-approved checkpoint). The
    # multilingual workflow reads this per-show instead of passing the flag
    # blanket for every show, which defeated the listen-first gate.
    zh_approved: bool = False
    # Name of the env var holding the cloned Grok voice ID. The ID itself
    # is NEVER stored in YAML/git — it's pasted into ``.env``. The TTS
    # call reads it at runtime and fails loud if unset.
    cloned_voice_env: str = "GROK_CLONED_VOICE_ID"


@dataclass
class VideoPodcastConfig:
    """Opt-in **video podcast** feed for a show (July 2026 pilot).

    Apple Podcasts accepts video episodes through an ordinary RSS
    ``<enclosure>`` (MOV / MP4 / M4V). Its 2026 HLS video experience is
    gated to a short list of hosting partners and does not support
    ``podcast:alternateEnclosure``, so for a self-hoster the MP4 enclosure
    is the *only* route in — and Apple's own guidance is to publish the
    video version as a **separate show**, not to mix formats in one feed.

    So this emits ``<show>_podcast.video.rss`` beside the canonical audio
    feed. The audio feed is never touched: a video-podcast episode is a
    second product built from an asset the network already renders (the
    long-form 1920x1080 MP4 the YouTube stage produces), which is why the
    marginal cost is one R2 upload and zero extra render time.

    **Rendering is decoupled from YouTube publishing.** The MP4 is a
    by-product of the long-form render, which used to be gated on the
    adaptive YouTube policy — so a shorts-only tier silently stopped the
    video feed growing while the audio feed kept publishing daily, and
    Apple de-ranks a dormant feed. ``run_show`` now renders whenever
    *either* product wants the MP4 and uploads to YouTube only when the
    policy says so. The cost on a shorts-only day is render time, not API
    spend: the visual plan is already built by then.

    Fields are declared here (not read via getattr on the raw dict) so
    ``_build_nested`` doesn't silently drop them — see landmine #20.
    """
    enabled: bool = False
    # R2 key prefix for the hosted MP4s, under the same bucket as the
    # episode audio: ``<prefix>/<slug>/<filename>.mp4``. Kept distinct from
    # the audio keyspace so a lifecycle rule can target video alone.
    r2_prefix: str = "video"
    # Channel-title suffix. Apple lists the audio and video shows side by
    # side, so they need to be tellable apart at a glance — and Apple
    # rejects a new show whose title duplicates an existing one, so this is
    # load-bearing rather than cosmetic.
    title_suffix: str = " — Video Edition"
    # Rolling feed window. An episode MP4 is ~40x its MP3, so the video
    # feed carries recent episodes rather than the whole back catalogue.
    # This is a real knob as of the durable index (engine.video_index):
    # before it, summaries' own 30-record truncation capped the feed no
    # matter what was set here, and episodes silently left the feed — which
    # Apple treats as a de-listing.
    max_episodes: int = 30
    # Optional overrides; empty means "derive from publishing.*".
    rss_file: str = ""          # default: <audio rss>.video.rss
    channel_description: str = ""
    channel_image: str = ""


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
    # Buttondown tag DISPLAY NAME. Used for per-show subscriber
    # filtering AND as the subscribe-form checkbox value on every show
    # page / blog post / the network page — subscribers carry tag names,
    # so this must stay human-readable.
    tag: str = ""
    # Optional Buttondown tag IDENTIFIER (e.g. ``sub_tag_…``). When set,
    # the SEND FILTER uses it instead of resolving ``tag`` through
    # Buttondown's hand-edited Tags page, so renaming a tag there cannot
    # silently break the show's send. Never reaches the subscribe form.
    tag_id: str = ""
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
class FunnelConfig:
    """Where a show's published surfaces send people, per channel.

    Read exclusively through :mod:`engine.funnel` (``destination_for`` /
    ``capture_tags``) — the module docstring there explains why every
    funnel link, campaign id and capture tag has exactly one builder.

    ``destinations`` is keyed by YouTube channel token (``en`` / ``ru`` /
    ``fr``) with a ``default`` fallback. Empty = the show page
    (``publishing.rss_link``), i.e. the pre-funnel behaviour.

    ``capture_tag`` is the Buttondown tag a signup from this show's
    landing page carries, so ``scripts/build_funnel.py`` can count
    captures per pilot rather than per network.
    """

    enabled: bool = True
    destinations: dict = field(default_factory=dict)
    capture_tag: str = ""


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
    # Aug 27 2026 (spacex Ep077): when true, chapters come ONLY from the
    # show's section_markers — the auto-segment fallback (which titles
    # inserted chapters with digest headlines / first sentences) is
    # disabled. For shows whose prompts speak a full, fixed section set,
    # headline-titled insertions are listener-facing spam, not navigation.
    known_sections_only: bool = False


@dataclass
class SourceIntegrityConfig:
    """Claim-ledger + verification gate (Aug 2026, engine/claims.py).

    ``enabled`` injects the ledger constraint into digest generation,
    extracts the fenced claims block, verifies it (URL resolves +
    supporting quote appears in the source) and lints citation-shaped
    prose against it — in SHADOW mode: loud warnings + metrics, never a
    blocked episode. ``enforce`` makes the gate BLOCKING (skip before the
    digest is saved / the topic-queue slot is burned). Enforcement rolls
    out per show, narrative shows first — never a network-wide day-one
    flip (model-upgrade-playbook lesson).
    """
    enabled: bool = False
    enforce: bool = False
    # Skip the HTTP source checks (span-anchoring + lint still run). For
    # offline/test runs; production leaves this on.
    verify_sources: bool = True


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
    # Model override for deep-dive runs only (2026-08-19, experiment
    # grok-46-funnel-and-ops). Specials are where depth is the whole
    # point and latency doesn't matter (manual-force, no daily slot), so
    # a show whose daily digest stays on grok-4.3 can run its specials
    # on grok-4.6. Empty = inherit the show's llm.model.
    model: str = ""


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
    # ---- Adaptive publishing policy (July 2026) ----
    # When true (default), the publish stage consults the committed
    # api/youtube_policy.json (nightly, velocity-gated per channel — see
    # scripts/update_youtube_policy.py) and lets it override long-form
    # on/off + Shorts count for this show. The policy never edits YAML and
    # never touches audio (outside landmine #17). Set false per show to pin
    # the YAML publish shape regardless of analytics.
    adaptive_publishing: bool = True
    # Generate a click-optimized long-form title via Grok (separate from the
    # spoken hook) + A/B variants. One cheap LLM call/episode; pure metadata,
    # no audio impact. Set false for a fully deterministic hook-based title.
    optimized_titles: bool = True
    # Burn captions into the long-form PIXELS. Default False: the runner
    # uploads a real caption track for every long-form video, and doing
    # both showed two sets of captions the moment a viewer pressed CC.
    # Shorts are unaffected (they have no caption UI). Set True only for a
    # surface that will not render a sidecar track.
    long_form_burn_in_captions: bool = False
    short_duration_seconds: float = 35.0
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
    # July 18 2026: when the multi-Shorts selector finds fewer than the
    # requested N windows above the threshold, fill the remaining slots
    # with the best non-overlapping sub-threshold windows (score >= 0)
    # instead of shipping fewer Shorts. The requested count is a policy
    # decision; before this, FF shipped 1-of-2 on every July episode.
    shorts_fill_to_requested: bool = True
    # July 31 2026 (operator directive): the FIRST Short on every channel
    # is the episode's opening hook sequence (since the July-30 cold-open
    # pass, t~=0 IS the hook — the strongest editorially-chosen beat).
    # Remaining Shorts keep the smart selector's windows. The hook Short
    # is labeled window="hook" in the video index so the analytics loop
    # can compare it against smart windows. False = pre-directive
    # behavior (spacex pins false until the Shorts motion A/B reads out —
    # flipping it mid-experiment would confound arm position with window
    # choice).
    shorts_first_is_hook: bool = True
    # ``always`` | ``alternate_episodes`` — skip Shorts on odd episode
    # numbers to halve upload quota during phased rollout.
    shorts_upload_schedule: str = "always"
    tags: List[str] = field(default_factory=list)
    synthetic_disclosure: str = ""
    podcast_playlist_id: Optional[str] = None
    # Optional playlist for Shorts. Shorts used to be inserted into
    # ``podcast_playlist_id`` — the playlist YouTube Music ingests as the
    # show's podcast — so every episode added 1-3 vertical 35 s clips as
    # "podcast episodes" beside the real one. Shorts now go here, or
    # nowhere when unset (never into the podcast playlist).
    shorts_playlist_id: Optional[str] = None
    # ---- Russian-dub YouTube (June 2026) ----
    # When true, the decoupled multilingual flow also builds a Russian-dubbed
    # video from the show's auto-generated `ru` audio track (reusing the same
    # gallery scene images) and uploads it to the @NerraRU channel
    # (channel=ru token). English upload is unaffected. Off by default →
    # byte-for-byte no-op. See engine.ru_dub / docs/ru_youtube_dubs.md.
    ru_dub_enabled: bool = False
    # ---- Generalized language dubs (July 2026 — first language: FR) ----
    # Registry languages (engine.lang_dub.DUB_LANGUAGES) this show publishes
    # dubbed videos for, e.g. ``dub_languages: [fr]`` → @NerraFR. Each
    # language needs its channel token (YOUTUBE_REFRESH_TOKEN_<CH>) — the
    # pipeline no-ops cleanly until the operator adds it. RU stays on the
    # bespoke ``ru_dub_enabled`` flag (engine.ru_dub). Empty by default →
    # byte-for-byte no-op.
    dub_languages: List[str] = field(default_factory=list)
    # Per-language playlist ids on the language channels, e.g.
    # ``dub_playlist_ids: {fr: PL...}`` (operator creates + flags each in
    # Studio — landmine #15).
    dub_playlist_ids: Dict[str, str] = field(default_factory=dict)
    # @NerraRU playlist for this show's RU dubs (operator creates + flags it
    # in Studio per landmine #15; uploads still publish without it, warned).
    ru_podcast_playlist_id: Optional[str] = None
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

    # ---- Hybrid short video clips (Phase 4, June 2026) ----
    # Interleave a few SHORT Grok clips among the still slideshow for motion
    # (the cheap fix for YouTube's static-slideshow penalty). Distinct from
    # video_provider="grok" (full-episode replacement, ~$50/ep). When enabled,
    # ~video_clips_count clips of ~video_clip_seconds each are generated via
    # engine.grok_video_clips and mixed in by engine.video.build_long_form_video.
    # Cost ≈ count × seconds × $0.05-0.07. Best-effort: falls back to all-stills
    # on any failure. Default off → byte-for-byte legacy behaviour.
    video_clips_enabled: bool = False
    video_clips_count: int = 3
    video_clip_seconds: int = 5
    video_clips_resolution: str = "720p"

    # ---- Shorts motion A/B (July 2026, SpaceX pilot) ----
    # Operator-requested experiment: on a show that publishes >= 2 Shorts
    # per episode, keep Short #1 exactly as it ships today (Grok Imagine
    # STILLS + Ken Burns) and render Short #2 over Grok Imagine VIDEO
    # clips, so the two motion treatments can be compared on the same
    # episode, same audio, same day, same channel — the only clean way to
    # A/B a format on one channel.
    #
    # Deliberately NOT a revival of `video_clips_enabled` (retired June
    # 2026 for the long-form: ~1/3 clip success at ~$0.35/ep and a render
    # that crowded the 40-min pipeline timeout). The differences that
    # make this safe are the cost ceiling, the wall-clock budget, and the
    # scope: one 35 s Short needs ~3 clips, not a 12-minute slideshow.
    # Any shortfall silently ships the stills variant and records
    # ``fallback`` so the report never credits a video Short that was
    # actually stills. See engine/shorts_ab.py.
    shorts_ab_enabled: bool = False
    # Which Short indexes (0-based) get the video treatment. Everything
    # else stays on stills — the control.
    shorts_ab_video_indexes: List[int] = field(default_factory=lambda: [1])
    shorts_ab_clips: int = 3
    shorts_ab_clip_seconds: int = 5
    shorts_ab_resolution: str = "720p"
    # Hard wall-clock budget for clip generation on ONE Short. The clip
    # step runs after the audio is already published, so overrunning
    # costs a render, never an episode.
    shorts_ab_budget_seconds: float = 420.0
    # Hard per-episode spend ceiling for the experiment. Clips are only
    # requested while the projected spend stays under it.
    shorts_ab_max_cost_usd: float = 1.25
    # Minimum clips that must land before the video variant is used. Below
    # this the Short ships as stills (recorded as a fallback) rather than
    # as a two-clip loop that would misrepresent the treatment.
    shorts_ab_min_clips: int = 2

    # ---- Visual reuse + chapter-aligned scenes (June 2026) ----
    # These gate engine/visual_reuse.py, the composition layer over
    # engine.gallery_library + engine.scene_scheduler. All default ON and
    # all are render/metadata-only (no audio → outside landmine #17);
    # every path is best-effort and degrades to the legacy render.
    #
    # Blend already-generated gallery scenes (pulled from the nerra-gallery
    # R2 bucket via the committed manifest) into the fresh per-episode
    # Grok Imagine sets, ranked by hook/chapter-title relevance. Zero new
    # image-generation cost; caps below bound the download volume.
    gallery_blend_enabled: bool = True
    # July 2026: raised 8 -> 16. Only 4 fresh 16:9 images are generated per
    # episode, and the chapter-aligned scheduler can place up to 24 slots,
    # so a 12-image pool meant every image appeared two to six times in a
    # single episode. Library scenes are already generated and already paid
    # for — the only cost of a bigger pool is R2 download volume during the
    # render, which is free egress. Generating more *fresh* images is the
    # alternative and it is not free: ~$0.02 each across eleven daily shows.
    # Sep 2026: back to 8. With one fresh scene PER STORY (scene briefs)
    # the episode's own imagery covers its chapters; the library only
    # fills gaps, and only with on-topic images (gallery_blend_min_overlap).
    gallery_blend_max_long: int = 8    # 16:9 library scenes per long-form
    # Minimum token overlap (context = hook + chapter titles) a library
    # scene needs to be blended at all; 0 = legacy rank-only behaviour.
    gallery_blend_min_overlap: int = 1
    # ---- Story-driven scene briefs (Sep 2026, engine.scene_briefs) ----
    # One Grok text call per episode writes a concrete visual scene per
    # story; those briefs LEAD the Grok Imagine prompts. False = the
    # deterministic headline-subject briefs (no LLM). Images per episode:
    # one 16:9 scene per story up to scenes_per_episode (was a fixed 4
    # generic images), and short_scenes_per_episode 9:16 scenes.
    scene_briefs_enabled: bool = True
    scenes_per_episode: int = 8
    short_scenes_per_episode: int = 5
    gallery_blend_max_short: int = 6   # 9:16 library scenes per Short
    # Align long-form scene switches with the episode's chapters.json
    # boundaries (engine.scene_scheduler.plan_chapter_schedule) instead of
    # the uniform timer. <2 usable chapters falls back to uniform.
    chapter_aligned_scenes: bool = True
    # Use the episode's first fresh 16:9 scene as the long-form thumbnail
    # base (cover fallback), and render up to `thumbnail_variants` extra
    # composites from OTHER scenes for the operator's Studio
    # "Test & Compare" A/B (uploaded to the gallery R2 bucket, tiny files).
    long_form_thumbnail_from_scene: bool = True
    thumbnail_variants: int = 2
    # Sunday weekly recaps reuse the past week's gallery scenes (both
    # aspects) instead of generating new imagery — the recap summarises
    # stories whose imagery the network already paid for. Requires ≥2
    # pooled images per aspect; below that, generates as usual.
    recap_reuse_scenes: bool = True
    # When Grok Imagine produces <2 usable scenes, fall back to the show's
    # historical gallery scenes before degrading to the static cover.
    gallery_fallback_enabled: bool = True
    # Snap Shorts scene changes to sentence boundaries from the Whisper
    # word-level transcript (engine.scene_scheduler.sentence_cut_times)
    # instead of the flat 7 s grid.
    shorts_sentence_cuts: bool = True
    # Interleave curated evergreen b-roll clips (digests/<dir>/broll.json,
    # published by scripts/build_broll_pool.py) into the long-form
    # slideshow. A clean no-op until the operator publishes a pool.
    evergreen_broll: bool = True
    # How many pool clips one long-form episode uses. The pool is
    # rotated per episode, so this is the WIDTH of each episode's slice,
    # not which clips it gets. Capped by engine.video._MAX_BROLL_CLIPS.
    broll_clips_per_episode: int = 3
    # Fill Shorts backgrounds from the same pool (real footage between
    # the stills, via the motion-A/B's hybrid path). Clean no-op until a
    # pool is published; suppressed automatically while a Shorts motion
    # A/B is enrolled so neither arm changes mid-experiment.
    shorts_broll: bool = True

    # Optional path (relative to repo root) to a text template for the
    # long-form description body. Placeholders: {hook}, {episode_num},
    # {show_name}, {today_str}. When empty, uses digest paragraphs.
    description_prompt_file: str = ""
    # Appended to the description as an operator copy-paste block (YouTube
    # has no API for pinned comments without extra scopes).
    pinned_comment_template: str = ""
    # July 18 2026 (operator-approved): post a real channel comment on each
    # upload via commentThreads.insert — the pinned-comment template on
    # long-form, a "Full episode: <link>" funnel comment on Shorts. The
    # API can't pin it (operator pins manually); a 403 is a graceful no-op.
    auto_comment: bool = True
    # July 18 2026 (operator-approved): thumbnails render a 2-4 word
    # ALL-CAPS punch text (LLM-generated with the title bundle) as the
    # dominant element instead of the full hook sentence. False = legacy
    # hook rendering.
    thumbnail_punch_text: bool = True
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

    # ---- Staggered Shorts publishing (Aug 2026) ----
    # Short #1 publishes with the episode; later Shorts upload PRIVATE with
    # ``status.publishAt`` set to the channel's next optimal slots
    # (engine/shorts_stagger.py), so one episode's Shorts spread through the
    # day instead of competing with each other at publish time. Applies to
    # scheduled AND manual runs. Dataclass default False for backwards
    # compat (the x_cross_promo pattern); the network default lives in
    # shows/_defaults.yaml. Slots map channel → list of UTC hours; empty
    # falls back to engine.shorts_stagger.DEFAULT_SLOT_HOURS_UTC.
    shorts_stagger_enabled: bool = False
    shorts_stagger_slots_utc: Dict[str, list] = field(default_factory=dict)

    # ---- Dub long-form override (Aug 2026, operator-directed) ----
    # Channels whose dub publishes the LONG-FORM video regardless of the
    # adaptive policy's tier (the Shorts count still follows the policy —
    # this pins long on, it never touches the shorts ladder). The RU
    # long-form demotion (~9% retention, July 2026) is the evidence this
    # overrides; registered as the dub-long-form-probe experiment with a
    # readout date in docs/experiments.yaml. e.g. ``[ru, fr]``.
    dub_force_long_channels: List[str] = field(default_factory=list)

    # ---- Shorts progress bar (Aug 2026 render pass) ----
    # Thin animated Nerra-cyan bar across the top of every Short — the
    # standard short-video retention device (visible time remaining).
    # Render-only (no audio, outside landmine #17); opt out per show.
    shorts_progress_bar: bool = True

    # ---- Site-showcase video endings (Aug 2026, operator-directed) ----
    # The closing seconds of every long-form video overlay an outro card
    # composited from COMMITTED screenshots of nerranetwork.com (the
    # show's page + the network home page — engine/promo_card.py), with
    # the URL in Nerra cyan, a localized newsletter line, and a QR to
    # the funnel-tagged show page (utm_content=outro). Shorts end cards
    # additionally paste the network home page's show-grid band as a
    # framed strip (``shorts_end_card_site_panel``). Render/metadata
    # only — outside landmine #17. Best-effort everywhere: missing
    # screenshots or a failed composite ship the legacy ending.
    outro_card_enabled: bool = True
    outro_card_duration_seconds: float = 6.0
    shorts_end_card_site_panel: bool = True

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
    # Story-recurrence memory (Aug 2026): annotate fetched articles that
    # match the ContentTracker's recent-headline window with an inline
    # "already covered — update, don't re-tell" note in the digest
    # prompt's article listing. Data-side, deterministic, no LLM calls
    # (engine/story_recurrence.py). Built after the Fort Bend story ran
    # in 5 of 10 Tesla episodes past three existing dedup layers.
    # Default False; the daily news shows opt in per-YAML.
    story_recurrence: bool = False
    web_search_queries: List[str] = field(default_factory=list)
    # Run web_search_queries on EVERY episode, not only when the on-topic
    # article count falls below min_articles. For shows whose key sources
    # publish no RSS (offshore_north: imoca.org, theoceanrace.com), web
    # search is load-bearing — a healthy RSS count from aggregators must
    # not silence the only route to the primary sources. Default False:
    # every other show keeps the count-gated behavior.
    web_search_always: bool = False
    min_articles: int = 3  # Minimum articles before expanding search
    min_articles_skip: int = 3  # Hard cutoff — skip episode if fewer articles
    # Progressive fetch-window ladder, in hours, widest last. Empty = use
    # the network default (24 → 48 → 72), which is tuned for DAILY shows.
    #
    # A show whose publication interval exceeds the widest stage can never
    # see its own period: Offshore North publishes Monday covering seven
    # days, and on the 2026-08-04 run the 72h ceiling starved it to 6
    # on-topic articles from 2 of 17 feeds. The pipeline only reached 46
    # articles by switching keyword filtering OFF, i.e. by going
    # off-topic, and the resulting digest came out at 596 words against a
    # 1300 target. Set this to cover the show's own cadence.
    fetch_expansion_hours: List[int] = field(default_factory=list)
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
    source_integrity: SourceIntegrityConfig = field(default_factory=SourceIntegrityConfig)
    slow_news: SlowNewsConfig = field(default_factory=SlowNewsConfig)
    content_freshness: ContentFreshnessConfig = field(default_factory=ContentFreshnessConfig)
    youtube: YouTubeConfig = field(default_factory=YouTubeConfig)
    multilingual: MultilingualConfig = field(default_factory=MultilingualConfig)
    video_podcast: VideoPodcastConfig = field(default_factory=VideoPodcastConfig)
    funnel: FunnelConfig = field(default_factory=FunnelConfig)
    # Weekly-summary segment (July 2026). When ``true`` and the runner
    # ticks on a Sunday, the show runs a NORMAL daily episode AND weaves
    # in one short "week in review" segment synthesised from the past 7
    # days of episodes in the content lake. (This replaced the retired
    # full weekly-recap mode, which turned the whole Sunday episode into a
    # look-back.) The daily-cadence news shows (OV, PT, FF, M&A, MAB, MIT,
    # TST, SpaceX) opt in.
    weekly_summary_segment: bool = False
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
            sources.append(SourceConfig(
                url=item.get("url", ""),
                label=item.get("label", ""),
                freshness_report=bool(item.get("freshness_report", False)),
            ))
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
    known_sections_only = bool(raw.get("known_sections_only", False))
    return ChaptersConfig(
        enabled=enabled,
        section_markers=markers,
        known_sections_only=known_sections_only,
    )


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
        story_recurrence=bool(data.get("story_recurrence", False)),
        web_search_queries=data.get("web_search_queries", []),
        web_search_always=bool(data.get("web_search_always", False)),
        min_articles=data.get("min_articles", 3),
        min_articles_skip=data.get("min_articles_skip", 3),
        fetch_expansion_hours=[
            int(h) for h in (data.get("fetch_expansion_hours") or [])
        ],
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
        source_integrity=_build_nested(SourceIntegrityConfig, data.get("source_integrity")),
        slow_news=_build_nested(SlowNewsConfig, data.get("slow_news")),
        content_freshness=_build_nested(ContentFreshnessConfig, data.get("content_freshness")),
        youtube=_build_nested(YouTubeConfig, data.get("youtube")),
        multilingual=_build_nested(MultilingualConfig, data.get("multilingual")),
        video_podcast=_build_nested(VideoPodcastConfig, data.get("video_podcast")),
        funnel=_build_nested(FunnelConfig, data.get("funnel")),
        # Accept the legacy ``weekly_recap_on_sunday`` key as a fallback so any
        # unmigrated YAML keeps working (the field was renamed July 2026 when
        # the full Sunday-recap mode became a small in-episode segment).
        weekly_summary_segment=bool(
            data.get("weekly_summary_segment",
                     data.get("weekly_recap_on_sunday", False))
        ),
        narrative_mode=bool(data.get("narrative_mode", False)),
        topic_queue_file=str(data.get("topic_queue_file", "") or ""),
        deep_dive=_build_nested(DeepDiveConfig, data.get("deep_dive")),
        memory_enabled=bool(data.get("memory_enabled", False)),
    )
    logger.info("Loaded config for '%s' from %s", config.name, path)
    return config
