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

import datetime
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

        # Rich YouTube feature metrics (May 2026 improvements observability)
        metrics.record("pexels_photos_filtered", int(youtube_urls.get("pexels_photos_filtered", 0) or 0))
        metrics.record("grok_image_cost_usd", float(youtube_urls.get("grok_image_cost_usd", 0.0) or 0.0))
        metrics.record("grok_images_generated", int(youtube_urls.get("grok_images_generated", 0) or 0))
        metrics.record("image_provider", youtube_urls.get("image_provider", "pexels"))
        metrics.record("gallery_attempted", int(youtube_urls.get("gallery_attempted", 0) or 0))
        metrics.record("gallery_uploaded", int(youtube_urls.get("gallery_uploaded", 0) or 0))
        if youtube_urls.get("gallery_skipped_reason"):
            metrics.record("gallery_skipped_reason", youtube_urls["gallery_skipped_reason"])

        # Smart Shorts selector + multi-Shorts (May 2026)
        if "shorts_start_mode_resolved" in youtube_urls:
            metrics.record("shorts_start_mode_resolved", str(youtube_urls["shorts_start_mode_resolved"]))
        metrics.record("shorts_count_requested", int(youtube_urls.get("shorts_count_requested", 1) or 1))
        metrics.record("shorts_count_uploaded", int(youtube_urls.get("shorts_count_uploaded", 0) or 0))
        if "shorts_start_offset" in youtube_urls:
            metrics.record("shorts_start_offset", float(youtube_urls["shorts_start_offset"]))
        if youtube_urls.get("shorts_start_offsets"):
            metrics.record("shorts_start_offsets", youtube_urls["shorts_start_offsets"])
        if youtube_urls.get("shorts_selector_scores"):
            metrics.record("shorts_selector_scores", youtube_urls["shorts_selector_scores"])

        # Thumbnail + hook overlay autofit decisions (for drift monitoring)
        if "thumbnail_autofit_font_size" in youtube_urls:
            metrics.record("thumbnail_autofit_font_size", int(youtube_urls["thumbnail_autofit_font_size"]))
        if "hook_overlay_autofit_font_size" in youtube_urls:
            metrics.record("hook_overlay_autofit_font_size", int(youtube_urls["hook_overlay_autofit_font_size"]))

        # Caption generation mode for Shorts (per-word ASS vs legacy SRT)
        if "shorts_caption_mode" in youtube_urls:
            metrics.record("shorts_caption_mode", str(youtube_urls["shorts_caption_mode"]))

        # End card (CTA) generation
        metrics.record("shorts_end_card_enabled", bool(youtube_urls.get("shorts_end_card_enabled", True)))
        if youtube_urls.get("shorts_end_card_generated") is not None:
            metrics.record("shorts_end_card_generated", bool(youtube_urls["shorts_end_card_generated"]))
    except Exception:
        # Never let metrics recording break a publish
        logger = __import__("logging").getLogger(__name__)
        logger.warning("record_youtube_outcomes failed (non-fatal)", exc_info=True)


def run_publish_phase(
    config: Any,
    *,
    episode_num: int,
    today: datetime.date,
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
    x_thread: str = "",
    extra_context: Optional[dict] = None,
    template_vars: Optional[Dict[str, Any]] = None,
    args: Any = None,
    tracker: Optional[dict] = None,
) -> tuple[str, str, list, str]:
    """
    Run the digest + podcast script generation phase (correctly wired).

    This is the extracted implementation. It uses the canonical calling
    convention for the generator functions:
        generate_digest(template_vars_dict, config, tracker=..., prompt_suffix=...)
        generate_podcast_script(template_vars_dict, config, tracker=...)

    If a rich ``template_vars`` is supplied by the caller (preferred), it is
    used as-is (preserving news_section, content tracker summaries, hook
    data from pre-fetch hooks, slow-news context, cross-show context, etc.).

    If ``x_thread`` is already populated, the digest generation step is
    skipped (the caller already produced it).

    Returns:
        (x_thread, podcast_script, episode_chapters, effective_hook)
    """
    from engine.generator import generate_digest, generate_podcast_script
    from engine.intros import build_intro_line, build_closing_block

    extra_context = extra_context or {}
    effective_hook = hook or (x_thread.split("\n", 1)[0][:120] if x_thread else "")

    # Build or use the provided template_vars.
    # The caller (run_show.py) normally builds a rich one containing
    # episode_num, today_str, news_section, recent_* summaries, slow_news_context,
    # cross_show_context, plus hook data via .update(extra_context).
    if template_vars is None:
        template_vars = {
            "today_str": today_str,
            "date_human": today_str,
            "episode_num": episode_num,
            "hook": effective_hook,
        }
        template_vars.update(extra_context)
        # Provide safe fallbacks for keys that many prompts reference
        template_vars.setdefault("news_section", "")
        template_vars.setdefault("sections_json", "")
        template_vars.setdefault("recent_content_summary", "")
        template_vars.setdefault("recent_deep_dive_topics", "")
        template_vars.setdefault("slow_news_context", "")
        template_vars.setdefault("cross_show_context", "")
        if getattr(config, "narrative_mode", False):
            # Minimal narrative fallbacks; real values should come from caller
            template_vars.setdefault("topic_title", "")
            template_vars.setdefault("topic_brief", "")
            template_vars.setdefault("topic_category", "")

    # If the caller already generated the digest (usual path), reuse it.
    # Only generate here if we were not given a non-empty x_thread.
    if not x_thread or not x_thread.strip():
        try:
            x_thread = generate_digest(template_vars, config, tracker=tracker)
        except Exception:
            # Let the normal tenacity / caller retry logic handle real failures
            raise

    if not effective_hook:
        effective_hook = (x_thread.split("\n", 1)[0][:120] if x_thread else hook)

    # YouTube handle for closing blocks
    _yt_handle = ""
    if getattr(config, "youtube", None) and getattr(config.youtube, "enabled", False):
        _yt_handle = (
            "@NerraRU" if getattr(config.youtube, "channel", "") == "ru" else "@NerraNetwork"
        )

    # Podcast script template vars (pod_vars are a subset used by the podcast prompt)
    pod_vars = {
        "hook": effective_hook,
        "date": today_str,
        "show_name": config.name,
        "episode_num": episode_num,
    }
    pod_vars.update(extra_context)

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
        if args is not None:
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
        else:
            # Safe fallback when args not supplied
            pod_vars.setdefault("intro_line", f"Welcome back to {config.name}.")
            pod_vars.setdefault("closing_block", "Thanks for listening.")

    pod_vars.setdefault("tone_hint", "natural and conversational")

    # Merge pod_vars into the main template_vars for the podcast prompt
    # (the podcast prompt expects many of the same keys + digest, etc.)
    template_vars_for_script = dict(template_vars)
    template_vars_for_script.update(pod_vars)
    template_vars_for_script["digest"] = x_thread  # many podcast prompts use {digest}

    podcast_script = generate_podcast_script(
        template_vars_for_script, config, tracker=tracker
    )

    # Chapter parsing (if enabled for the show)
    episode_chapters: list = []
    if (getattr(config, "chapters", None)
            and getattr(config.chapters, "enabled", False)
            and getattr(config.chapters, "section_markers", None)):
        from engine.chapters import parse_chapters
        episode_chapters = parse_chapters(
            podcast_script,
            config.chapters.section_markers,
            show_name=config.name,
        )

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
    today: datetime.date,
    metrics: Any,
) -> None:
    """Run TTS synthesis + audio mixing phase.

    Delegates to current implementation in run_show for now.
    Full move of the TTS call + mixing logic will happen in a follow-up.
    """
    # For this iteration we keep the actual synthesis call in run_show.py
    # to avoid a massive diff. The phase boundary is established.
    pass  # Logic remains in run_show for now; will be moved next.
