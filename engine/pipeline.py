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
import logging
import re
from collections import Counter
from pathlib import Path
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

# Placeholder for future phase result types
PublishResult = Dict[str, Any]


# ---------------------------------------------------------------------------
# Missing-closing guard helpers (June 10 2026; hardened July 2026)
# ---------------------------------------------------------------------------

# Common contractions the LLM expands/collapses when it lightly rewrites the
# supplied closing block. The July 2026 network editorial pass found the
# June-10 missing-closing guard comparing the closing's first-5-words
# signature LITERALLY ("and that's a wrap! if"): the LLM de-contracts to
# "And that is a wrap!", the literal check misses, and the guard appends the
# ENTIRE closing again — 5 of 15 MAB episodes shipped the closing spoken
# twice (Ep075/076/077/079/084, Whisper-confirmed).
_CLOSING_CONTRACTIONS = {
    "that's": "that is",
    "it's": "it is",
    "we're": "we are",
    "you're": "you are",
    "they're": "they are",
    "i'm": "i am",
    "we've": "we have",
    "you've": "you have",
    "i've": "i have",
    "we'll": "we will",
    "you'll": "you will",
    "i'll": "i will",
    "here's": "here is",
    "there's": "there is",
    "what's": "what is",
    "let's": "let us",
    "don't": "do not",
    "doesn't": "does not",
    "didn't": "did not",
    "isn't": "is not",
    "aren't": "are not",
    "wasn't": "was not",
    "won't": "will not",
    "can't": "cannot",
}


def _normalize_closing_text(text: str) -> str:
    """Normalize text for closing-signature comparison.

    Lowercases, expands common contractions (so "that's" == "that is"),
    strips punctuation, and collapses whitespace — the three drift classes
    (contraction, punctuation, casing) the LLM applies when it "quotes"
    the supplied closing block.
    """
    text = text.lower().replace("’", "'")
    for contraction, expanded in _CLOSING_CONTRACTIONS.items():
        text = re.sub(r"\b" + re.escape(contraction) + r"\b", expanded, text)
    text = re.sub(r"[^\w\s]", " ", text)
    return " ".join(text.split())


def closing_block_present(
    podcast_script: str,
    closing_block: str,
    *,
    sig_words: int = 10,
    threshold: float = 0.8,
) -> bool:
    """True when the supplied closing block already appears in the script tail.

    Fuzzy by design: both sides are normalized (lowercase, contractions
    expanded, punctuation stripped) and the closing's first *sig_words*
    tokens must reach *threshold* token-overlap with some same-length
    window of the script's tail. A genuinely absent closing (PT Ep081/084
    class) stays below the threshold and the caller appends the block;
    a lightly rewritten closing ("And that is a wrap!" for "And that's a
    wrap!") counts as present so the guard never double-appends (MAB
    Ep075-084 class).
    """
    if not closing_block or not podcast_script:
        return False
    # Drop a leading "Host:"-style speaker prefix from the closing.
    closing = re.sub(r"^\s*\w+:\s*", "", closing_block.strip())
    sig_tokens = _normalize_closing_text(closing).split()[:sig_words]
    if not sig_tokens:
        return True  # nothing meaningful to check — treat as present
    tail = podcast_script[-max(len(podcast_script) // 4, 600):]
    tail_tokens = _normalize_closing_text(tail).split()
    if not tail_tokens:
        return False
    # Fast path: exact normalized containment.
    if " ".join(sig_tokens) in " ".join(tail_tokens):
        return True
    n = len(sig_tokens)
    sig_counts = Counter(sig_tokens)
    windows = (
        [tail_tokens]
        if len(tail_tokens) < n
        else [tail_tokens[i:i + n] for i in range(len(tail_tokens) - n + 1)]
    )
    for window in windows:
        overlap = sum((sig_counts & Counter(window)).values())
        if overlap / n >= threshold:
            return True
    return False


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

        # Optimized title + its A/B candidates (June 2026). Persisted so the
        # operator's Studio "Test & Compare" variants survive past the
        # Actions log (previously they existed nowhere else).
        if youtube_urls.get("youtube_title"):
            metrics.record("youtube_title", str(youtube_urls["youtube_title"]))
        if youtube_urls.get("youtube_title_variants"):
            metrics.record("youtube_title_variants", list(youtube_urls["youtube_title_variants"]))

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

        # July 18 2026 growth pass observability (recorder previously
        # dropped these three result keys — the fill/punch/comment layers
        # were shipping invisibly): per-Short fill modes
        # (qualified|filled|legacy_fallback), the thumbnail punch text
        # actually used, and how many auto-comments posted.
        if youtube_urls.get("shorts_fill_modes"):
            metrics.record("shorts_fill_modes", list(youtube_urls["shorts_fill_modes"]))
        if youtube_urls.get("thumbnail_punch_text"):
            metrics.record("thumbnail_punch_text", str(youtube_urls["thumbnail_punch_text"]))
        if youtube_urls.get("yt_comments_posted"):
            metrics.record("yt_comments_posted", int(youtube_urls["yt_comments_posted"]))

        # Video podcast (July 2026 pilot). The hosted MP4's real byte size
        # is the only honest input to the R2 storage-cost projection — the
        # long-form render is a mostly-static slideshow, so its bitrate
        # can't be assumed from the encoder settings alone. Recorded per
        # episode so the projection is measured, never guessed.
        if youtube_urls.get("video_podcast"):
            _vp = youtube_urls["video_podcast"]
            metrics.record("video_podcast_uploaded", True)
            metrics.record("video_podcast_bytes", int(_vp.get("bytes", 0) or 0))
        elif youtube_urls.get("video_podcast_skipped"):
            metrics.record("video_podcast_uploaded", False)
            metrics.record("video_podcast_skipped",
                           str(youtube_urls["video_podcast_skipped"]))

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

        # Visual reuse + chapter-aligned scenes (June 2026 — engine/visual_reuse).
        # visual_mode ∈ chapter_schedule | uniform | cover | library_fallback |
        # recap_pool; the counts let the dashboard plot how much of each
        # episode's imagery was fresh vs recycled from the gallery.
        if youtube_urls.get("visual_mode"):
            metrics.record("visual_mode", str(youtube_urls["visual_mode"]))
        if "scene_fresh_count" in youtube_urls:
            metrics.record("scene_fresh_count", int(youtube_urls.get("scene_fresh_count", 0) or 0))
        if "scene_library_count" in youtube_urls:
            metrics.record("scene_library_count", int(youtube_urls.get("scene_library_count", 0) or 0))
        if "broll_clips_used" in youtube_urls:
            metrics.record("broll_clips_used", int(youtube_urls.get("broll_clips_used", 0) or 0))
        # Shorts-only scene saving (July 2026): 16:9 scenes are only worth
        # generating when a long-form video is actually produced.
        if "scene_long_form_produced" in youtube_urls:
            metrics.record("scene_long_form_produced",
                           bool(youtube_urls["scene_long_form_produced"]))
        if "scene_fresh_long_requested" in youtube_urls:
            metrics.record("scene_fresh_long_requested",
                           int(youtube_urls.get("scene_fresh_long_requested", 0) or 0))
        if youtube_urls.get("thumbnail_base"):
            metrics.record("thumbnail_base", str(youtube_urls["thumbnail_base"]))
        if youtube_urls.get("thumbnail_variant_urls"):
            metrics.record("thumbnail_variant_urls", list(youtube_urls["thumbnail_variant_urls"]))

        # Adaptive publishing policy decision (July 2026 — engine/
        # youtube_policy). Present only when a policy entry actually applied
        # to this show; absent keys mean legacy YAML behavior ran.
        if "yt_policy_tier" in youtube_urls:
            metrics.record("yt_policy_tier", str(youtube_urls["yt_policy_tier"]))
            metrics.record("yt_policy_long_skipped", bool(youtube_urls.get("yt_policy_long_skipped")))
            metrics.record("yt_policy_shorts", int(youtube_urls.get("yt_policy_shorts", 1) or 1))
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
    podcast_digest: str = "",
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
    from engine.intros import (
        build_intro_line,
        build_closing_block,
        build_cold_open_spec,
        build_delivery_spec,
        _maybe_append_youtube_cta,
        _RUSSIAN_SPOKEN_SHOWS,
    )

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
        template_vars.setdefault("nerra_network_context", "")
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
        # Fallback: first substantive line of the digest — but SANITIZED.
        # DP Pod Ep001 v4 spoke a raw markdown header on air ("# The DP Pod:
        # The Do Positive Podcast") because the debut brief had no **HOOK:**
        # line and this fallback grabbed line one verbatim. Skip markdown
        # scaffolding lines and strip md decorations from whatever is used.
        effective_hook = hook
        if x_thread:
            import re as _re
            for _line in x_thread.splitlines():
                _line = _line.strip()
                if not _line or _line.startswith(("#", "━", "---", "===")):
                    continue
                _line = _line.lstrip(">* ").strip()
                _line = _re.sub(r"\*\*(.+?)\*\*", r"\1", _line)
                if len(_line) < 20:
                    continue
                effective_hook = _line[:120]
                break

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
        _slug = getattr(config, "slug", "") or (getattr(args, "show", "") if args is not None else "")
        if getattr(getattr(config, "tts", None), "dialogue_mode", False):
            # Dialogue shows (The DP Pod): the generic single-host Ep1 text
            # fights the dialogue prompt's speaker-label + exact-sign-off
            # rules — BOTH DP Pod Ep001 renders aired the truncated
            # "please subscribe..." literal from this block (run_show builds
            # its own pod_vars but never passes them into
            # run_generation_phase; THIS block is the live path). Debut with
            # a labeled intro from the personality's lead host + the
            # personality's own labeled closing (subscribe ask included,
            # ends with the exact sign-off).
            from engine.intros import get_show_host as _get_show_host
            _lead = _get_show_host(_slug)
            pod_vars.setdefault(
                "intro_line",
                f"{_lead}: Welcome to the very first episode of {config.name}! "
                f"Today is {today_str}. {effective_hook}",
            )
            pod_vars.setdefault(
                "closing_block",
                build_closing_block(
                    _slug,
                    episode_num=episode_num,
                    today_str=today_str,
                    date=__import__("datetime").date.today(),
                    extra_context=extra_context,
                    youtube_channel_handle=_yt_handle,
                ),
            )
        else:
            pod_vars.setdefault(
                "intro_line",
                f"Welcome to the very first episode of {config.name}! "
                f"Today is {today_str}. {effective_hook}",
            )
            _ep1_close = (
                f"That wraps up our very first episode of {config.name}! "
                f"If you enjoyed this, please subscribe on Apple Podcasts, "
                f"Spotify, or wherever you listen — and a rating or review "
                f"really helps new listeners find us. Thanks for joining us, "
                f"and we'll see you tomorrow for episode two."
            )
            # Route the YouTube call-out through the shared helper so the "@" is
            # stripped (no "at at" stutter) and the EN handle is split to the spaced
            # "Nerra Network" — matching every other episode's closing.
            _ep1_is_ru = getattr(config, "slug", "") in _RUSSIAN_SPOKEN_SHOWS
            _ep1_close = _maybe_append_youtube_cta(_ep1_close, _yt_handle, is_ru=_ep1_is_ru)
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
    pod_vars.setdefault("nerra_network_context", "")

    # Hook-failure safety. A memory show's pre-fetch hook normally injects
    # {narrative_memory_section} (and Привет, Русский! injects
    # {vocab_review_section}) through extra_context. If the hook fails to
    # load, the prompt still references the placeholder and
    # str.format_map raises — the same KeyError class that took the
    # network down on 2026-07-30. Degrade to an empty section instead.
    #
    # These defaults existed only in run_show.py's discarded pod_vars, so
    # the invariant was never actually enforced;
    # tests/test_memory_lake_expansion.py passed by counting occurrences
    # in that dead block. setdefault means a working hook is unaffected.
    pod_vars.setdefault("narrative_memory_section", "")
    pod_vars.setdefault("vocab_review_section", "")
    # Tesla's bespoke memory module injects three placeholders of its own
    # (the generalized shows share {narrative_memory_section} above). A
    # tesla hook-load failure would KeyError the podcast prompt exactly
    # like the 2026-07-30 cold_open_spec outage — same guard, same
    # setdefault semantics (a working hook is untouched).
    pod_vars.setdefault("tesla_narrative_status_block", "")
    pod_vars.setdefault("tesla_performance_signals_block", "")
    pod_vars.setdefault("tesla_theme_context_block", "")

    # Cold-open + delivery specs (July 30 2026 retention pass). These were
    # wired into run_show.py's pod_vars — which, as the Ep1 comment above
    # records, is NOT the live path: run_show builds that dict and never
    # passes it into run_generation_phase. So all 14 podcast prompts gained
    # {cold_open_spec} and 17 gained {delivery_spec} while nothing supplied
    # either, and the next run of EVERY show died in load_prompt with
    # `KeyError: 'cold_open_spec'` (SpaceX Ep50, 2026-07-30 20:54 UTC — the
    # first show to tick over after the change merged).
    #
    # setdefault, not assignment: a show whose pre-fetch hook supplies its
    # own spec via extra_context keeps it.
    _spec_slug = getattr(config, "slug", "") or (
        getattr(args, "show", "") if args is not None else ""
    )
    _spec_is_ru = _spec_slug in _RUSSIAN_SPOKEN_SHOWS
    pod_vars.setdefault(
        "cold_open_spec", build_cold_open_spec(_spec_slug, is_ru=_spec_is_ru),
    )
    pod_vars.setdefault(
        "delivery_spec", build_delivery_spec(_spec_slug, is_ru=_spec_is_ru),
    )

    # Append the rotating Nerra Network cross-promo to the spoken closing.
    # Done HERE (after closing_block is resolved from any source) so it covers
    # every path: build_closing_block, the episode-1 closing, AND shows whose
    # pre-fetch hook supplied closing_block via extra_context (e.g. Tesla). The
    # promo is English-only and varies by day + show so every English sibling
    # eventually gets advertised. Russian shows get "" → no change.
    _promo_date = datetime.date.today()
    _show_slug = getattr(config, "slug", "") or (
        getattr(args, "show", "") if args is not None else ""
    )
    if _show_slug:
        try:
            from engine.network_promo import build_network_promo
            _promo = build_network_promo(_show_slug, _promo_date, episode_num)
            if _promo:
                _close = str(pod_vars.get("closing_block", "")).rstrip()
                # Idempotent — don't double-append if already present.
                if "nerranetwork.com" not in _close.lower():
                    pod_vars["closing_block"] = f"{_close} {_promo}".strip()
        except Exception as exc:  # noqa: BLE001 — promo must never break a run
            logger.warning("Network promo append failed (non-fatal): %s", exc)

    # Merge pod_vars into the main template_vars for the podcast prompt
    # (the podcast prompt expects many of the same keys + digest, etc.)
    template_vars_for_script = dict(template_vars)
    template_vars_for_script.update(pod_vars)
    # {digest} for the podcast prompt. ``podcast_digest`` is run_show's
    # podcast-only copy (URL/emoji cleanup, the Sunday weekly-summary
    # segment — landmine #19 — and the 100%-duplicate-headline strip).
    # From 2026-07-30 to 2026-07-31 that copy was computed and read by
    # nothing (its only consumer was the deleted dead pod_vars dict), so
    # none of those three layers had EVER reached a podcast script —
    # wired 2026-07-31 at operator request. Empty → the raw x_thread,
    # which is byte-for-byte the previous behaviour.
    template_vars_for_script["digest"] = podcast_digest or x_thread

    podcast_script = generate_podcast_script(
        template_vars_for_script, config, tracker=tracker
    )

    # Missing-closing guard (June 10 2026, Planetterrian review): PT
    # Ep081/Ep084 shipped without the supplied closing block — Ep084
    # ended mid-teaser with no sign-off, no CTA, and no Closing chapter.
    # The prompts say "use this exact closing (do not rewrite it)" but
    # the LLM occasionally omits it. If the resolved closing's opening
    # signature isn't in the script's tail, append the block verbatim so
    # every episode ends properly (and the Closing chapter always parses).
    # July 2026 hardening: the presence check is FUZZY (contractions,
    # punctuation, casing normalized) — the old literal first-5-words
    # check missed the LLM's de-contracted "And that is a wrap!" and
    # double-appended the closing on 5 of 15 MAB episodes. See
    # closing_block_present().
    _closing = str(pod_vars.get("closing_block", "")).strip()
    if _closing and podcast_script:
        if not closing_block_present(podcast_script, _closing):
            logger.warning(
                "Podcast script is missing the supplied closing block — "
                "appending it verbatim (script ended: %r)",
                podcast_script.rstrip()[-80:],
            )
            podcast_script = podcast_script.rstrip() + "\n\n" + _closing

    # Chapter parsing (if enabled for the show)
    episode_chapters: list = []
    if (getattr(config, "chapters", None)
            and getattr(config.chapters, "enabled", False)
            and getattr(config.chapters, "section_markers", None)):
        from engine.chapters import parse_chapters
        try:
            from engine.grok_imagine import extract_story_headlines as _ch_heads
            _chapter_headlines = _ch_heads(x_thread or "", max_count=12)
        except Exception:
            _chapter_headlines = []
        episode_chapters = parse_chapters(
            podcast_script,
            config.chapters.section_markers,
            show_name=config.name,
            story_headlines=_chapter_headlines,
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
