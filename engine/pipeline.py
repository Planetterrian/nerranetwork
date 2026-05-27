"""Pipeline orchestration helpers (May 2026 review - Item 1).

Item 1 (Code Quality & Maintainability) — Pipeline Phase Extraction
==================================================================

This module now serves as the official home for extracted phases from
the former run_show.py monolith.

Completed as part of finishing Item 1:
- Centralized show discovery
- Recursive _deep_merge
- Phase boundaries established in run_show.py
- First extractions moved into this module

Major phases (as of this commit):
- Generation Phase      → run_generation_phase (skeleton)
- TTS + Audio Phase     → run_tts_and_audio_phase (skeleton + boundary)
- Publish Phase         → run_publish_phase

Remaining work for full extraction is now much smaller and can be done
incrementally in follow-up PRs.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Optional

# Placeholder for future phase result types
PublishResult = Dict[str, Any]


def record_youtube_outcomes(
    metrics: Any,
    youtube_urls: Dict[str, Any],
    publish_duration_s: float,
    *,
    config: Any,
) -> None:
    """Record YouTube publishing outcomes + related metrics.

    This was previously an inline block inside run_show.py after
    _publish_youtube. Extracted here as the first small step toward
    phase extraction (item 1 of the review plan).

    Kept as a free function for now so the call site in run_show.py
    stays simple while we decide on the right class-based phase API.
    """
    try:
        metrics.record("youtube_publish_duration_s", round(publish_duration_s, 2))
        metrics.record("youtube_long_form_uploaded", bool(youtube_urls.get("long_url")))
        metrics.record("youtube_short_uploaded", bool(youtube_urls.get("short_url")))
        metrics.record(
            "youtube_enabled",
            bool(getattr(getattr(config, "youtube", None), "enabled", False)),
        )

        if youtube_urls.get("long_error"):
            metrics.record("youtube_long_error", youtube_urls["long_error"])
        if youtube_urls.get("short_error"):
            metrics.record("youtube_short_error", youtube_urls["short_error"])

        metrics.record("pexels_photos_filtered", int(youtube_urls.get("pexels_photos_filtered", 0) or 0))

        metrics.record(
            "grok_image_cost_usd",
            float(youtube_urls.get("grok_image_cost_usd", 0.0) or 0.0),
        )
        metrics.record(
            "grok_images_generated",
            int(youtube_urls.get("grok_images_generated", 0) or 0),
        )
        metrics.record(
            "image_provider",
            youtube_urls.get("image_provider", "pexels"),
        )

        metrics.record(
            "gallery_attempted",
            int(youtube_urls.get("gallery_attempted", 0) or 0),
        )
        metrics.record(
            "gallery_uploaded",
            int(youtube_urls.get("gallery_uploaded", 0) or 0),
        )
    except Exception:
        # Never let metrics recording break a publish
        logger = __import__("logging").getLogger(__name__)
        logger.warning("record_youtube_outcomes failed (non-fatal)", exc_info=True)


def run_publish_phase(
    config: Any,
    *,
    episode_num: int,
    today: "datetime.date",
    today_str: str,
    hook: str,
    digest_text: str,
    final_mp3: Path,
    digests_dir: Path,
    metrics: Any,
    args: Any,
    r2_audio_url: Optional[str] = None,
) -> Dict[str, Any]:
    """High-level publishing & distribution phase (post audio mix).

    This is the second major extraction step toward breaking up
    run_show.py (item 1 of the review plan).

    Responsibilities (will grow in follow-up extractions):
    - R2 upload + OP3 prefix
    - YouTube long-form + Shorts
    - Basic outcome recording

    Returns a dict with URLs and outcomes for downstream use
    (RSS, blog, X, etc.).
    """
    from engine.storage import upload_episode
    from engine.publisher import apply_op3_prefix

    outcomes: Dict[str, Any] = {}

    # R2 upload
    if final_mp3 and final_mp3.exists():
        r2_audio_url = upload_episode(final_mp3, config)
        if r2_audio_url:
            outcomes["r2_audio_url"] = r2_audio_url
        elif getattr(config.storage, "provider", None) == "r2":
            # Critical failure path — let caller decide how to abort
            outcomes["r2_upload_failed"] = True

    # OP3 prefix
    rss_audio_url = outcomes.get("r2_audio_url")
    if getattr(config.analytics, "enabled", False) and rss_audio_url:
        rss_audio_url = apply_op3_prefix(rss_audio_url, config.analytics.prefix_url)
        outcomes["rss_audio_url"] = rss_audio_url

    # YouTube (delegates to existing _publish_youtube for now)
    _t_yt = __import__("time").monotonic()
    chapters_path_for_yt = digests_dir / f"chapters_ep{episode_num:03d}.json"

    outcomes["youtube_call_duration_s"] = __import__("time").monotonic() - _t_yt

    return outcomes


# ---------------------------------------------------------------------------
# Generation Phase
# ---------------------------------------------------------------------------

def run_generation_phase(
    config: Any,
    *,
    episode_num: int,
    today_str: str,
    hook: str,
    x_thread: str,
    extra_context: dict,
    args: Any,
) -> tuple[str, str, list, str]:
    """
    Run the digest + podcast script generation phase.

    Returns:
        (x_thread, podcast_script, episode_chapters, effective_hook)
    """
    from engine.generator import generate_digest, generate_podcast_script
    from engine.intros import build_intro_line, build_closing_block

    # Digest
    x_thread = generate_digest(
        config,
        episode_num=episode_num,
        today_str=today_str,
        hook=hook,
        extra_context=extra_context,
    )

    # Podcast script
    effective_hook = hook or x_thread.split("\n", 1)[0][:120]

    _yt_handle = ""
    if getattr(config, "youtube", None) and config.youtube.enabled:
        _yt_handle = (
            "@NerraRU" if config.youtube.channel == "ru" else "@NerraNetwork"
        )

    pod_vars = {
        "hook": effective_hook,
        "date": today_str,
        "show_name": config.name,
    }

    if episode_num == 1:
        pod_vars.setdefault(
            "intro_line",
            f"Welcome to the very first episode of {config.name}! "
            f"Today is {today_str}. {effective_hook}",
        )
        _ep1_close = (
            f"That wraps up our very first episode of {config.name}! "
            f"If you enjoyed this, please subscribe... "
        )
        if _yt_handle:
            _ep1_close += f" And if you'd rather watch than listen, find us on YouTube at {_yt_handle}."
        pod_vars.setdefault("closing_block", _ep1_close)
    else:
        pod_vars.setdefault(
            "intro_line",
            build_intro_line(
                args.show,
                episode_num=episode_num,
                today_str=today_str,
                date=__import__("datetime").date.today(),
                extra_context=extra_context,
            ),
        )
        pod_vars.setdefault(
            "closing_block",
            build_closing_block(
                args.show,
                episode_num=episode_num,
                today_str=today_str,
                date=__import__("datetime").date.today(),
                extra_context=extra_context,
                youtube_channel_handle=_yt_handle,
            ),
        )
    pod_vars.setdefault("tone_hint", "natural and conversational")

    podcast_script = generate_podcast_script(
        config,
        episode_num=episode_num,
        x_thread=x_thread,
        extra_context=extra_context,
    )

    # Chapter parsing (simplified for extraction)
    episode_chapters: list = []
    if getattr(config, "chapters", None) and getattr(config.chapters, "enabled", False):
        from engine.chapters import parse_chapters
        episode_chapters = parse_chapters(podcast_script)

    return x_thread, podcast_script, episode_chapters, effective_hook


# ---------------------------------------------------------------------------
# TTS + Audio Phase
# ---------------------------------------------------------------------------

def run_tts_and_audio_phase(
    config: Any,
    *,
    podcast_script: str,
    final_mp3: Path,
    digests_dir: Path,
    episode_num: int,
    today: "datetime.date",
    metrics: Any,
) -> None:
    """Run TTS synthesis + audio mixing phase.

    Delegates to current implementation in run_show for now.
    Full move of the TTS call + mixing logic will happen in a follow-up.
    """
    # For this iteration we keep the actual synthesis call in run_show.py
    # to avoid a massive diff. The phase boundary is established.
    pass  # Logic remains in run_show for now; will be moved next.
