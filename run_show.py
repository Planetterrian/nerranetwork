#!/usr/bin/env python3
"""Unified entry point for all podcast shows.

Usage:
    python run_show.py <show_name> [options]

    show_name: tesla | omni_view | fascinating_frontiers | planetterrian | env_intel | models_agents | models_agents_beginners

Options:
    --test              Fetch RSS + generate digest only (no TTS, X posting, or RSS update)
    --dry-run           Print what would happen; no API calls at all
    --skip-x            Everything except X posting
    --skip-podcast      Everything except TTS/audio/RSS update
    --skip-newsletter   Everything except newsletter sending
"""

from __future__ import annotations

import argparse
import datetime
import importlib
import importlib.util
import json
import logging
import os
import re
import signal
import sys
import time
from pathlib import Path

from dotenv import load_dotenv


# ---------------------------------------------------------------------------
# Pipeline timeout — guard against hung API calls or infinite loops.
# Default 15 minutes; override with PIPELINE_TIMEOUT_SECONDS env var.
# ---------------------------------------------------------------------------
_PIPELINE_TIMEOUT = int(os.environ.get("PIPELINE_TIMEOUT_SECONDS", 900))


def _timeout_handler(signum, frame):
    raise SystemExit(f"PIPELINE TIMEOUT: exceeded {_PIPELINE_TIMEOUT}s — aborting to prevent hung CI job")


# Only set alarm on platforms that support it (not Windows)
if hasattr(signal, "SIGALRM"):
    signal.signal(signal.SIGALRM, _timeout_handler)
    signal.alarm(_PIPELINE_TIMEOUT)


# ---------------------------------------------------------------------------
# AI disclosure — appended to every episode's spoken script and RSS metadata
# ---------------------------------------------------------------------------
# Tightened May 2026 (content audit). Previous disclosure was a 35-second
# Patrick-talking-about-Patrick monologue at the close of every episode,
# diluting each show's distinctive sign-off. New disclosure is one
# sentence — just enough to satisfy the AI-disclosure obligation without
# eating the listener's last memory of the show.
_AI_DISCLOSURE = (
    "This episode used AI voice synthesis of my voice — "
    "editorial selection and analysis are my own."
)

_AI_DISCLOSURE_RSS = (
    "AI Disclosure: This podcast is curated by Patrick but uses AI-generated "
    "voice synthesis for audio production."
)

# ---------------------------------------------------------------------------
# Bootstrap
# ---------------------------------------------------------------------------

PROJECT_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT_ROOT))

load_dotenv(PROJECT_ROOT / ".env")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger("run_show")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

_NON_SHOW_YAMLS = {"pronunciation_map"}


def _discover_shows() -> list[str]:
    """Find all show slugs by scanning shows/*.yaml.

    Skips template files, leading-underscore config files
    (e.g. ``_defaults``, ``_blocked_sources``), and named resource files
    in ``_NON_SHOW_YAMLS``.
    """
    shows_dir = PROJECT_ROOT / "shows"
    slugs = []
    for p in sorted(shows_dir.glob("*.yaml")):
        stem = p.stem
        if stem.endswith("_template"):
            continue
        if stem.startswith("_"):
            continue
        if stem in _NON_SHOW_YAMLS:
            continue
        slugs.append(stem)
    return slugs


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run a podcast show pipeline.")
    available = _discover_shows()
    parser.add_argument(
        "show",
        choices=available,
        help="Show to run (discovered from shows/*.yaml)",
    )
    parser.add_argument("--test", action="store_true",
                        help="Fetch + generate digest only (no TTS/X/RSS)")
    parser.add_argument("--dry-run", action="store_true",
                        help="Print plan, make no API calls")
    parser.add_argument("--skip-x", action="store_true",
                        help="Skip X/Twitter posting")
    parser.add_argument("--skip-podcast", action="store_true",
                        help="Skip TTS, audio mixing, and RSS update")
    parser.add_argument("--skip-newsletter", action="store_true",
                        help="Skip newsletter sending")
    parser.add_argument("--skip-youtube", action="store_true",
                        help="Skip YouTube video build + upload")
    parser.add_argument(
        "--resume-publish",
        action="store_true",
        help="Publish only: MP3 + digest on disk, skip fetch/TTS (for mid-publish retries)",
    )
    parser.add_argument(
        "--resume-youtube",
        action="store_true",
        help="YouTube only: MP3 + digest on disk, rebuild/upload videos (skips TTS/RSS/X)",
    )
    return parser.parse_args()


# ---------------------------------------------------------------------------
# Hook loader
# ---------------------------------------------------------------------------

def _load_hook(show_slug: str):
    """Try to import ``shows.hooks.<slug>`` and return the module, or None."""
    hook_path = PROJECT_ROOT / "shows" / "hooks" / f"{show_slug}.py"
    if not hook_path.exists():
        return None
    try:
        spec = importlib.util.spec_from_file_location(
            f"shows.hooks.{show_slug}", hook_path,
        )
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod
    except Exception as exc:
        logger.warning("Failed to load hook for %s: %s", show_slug, exc)
        return None


# ---------------------------------------------------------------------------
# Pronunciation loader
# ---------------------------------------------------------------------------

def _apply_pronunciation(text: str, show_slug: str) -> str:
    """Apply comprehensive pronunciation fixes for TTS readiness.

    Always calls ``prepare_text_for_tts()`` as the baseline — this handles
    URL stripping, emoji removal, number-to-words conversion, acronym
    expansion, and 200+ pronunciation rules.  Per-show hooks can supply
    extra overrides via ``pronunciation_overrides()`` returning a dict with
    optional keys: ``skip_acronyms``, ``extra_acronyms``, ``extra_words``.
    """
    from assets.pronunciation import prepare_text_for_tts

    # Collect per-show overrides from hook (if any)
    skip_acronyms: set = set()
    extra_acronyms: dict = {}
    extra_words: dict = {}

    hook = _load_hook(show_slug)
    if hook and hasattr(hook, "pronunciation_overrides"):
        overrides = hook.pronunciation_overrides()
        skip_acronyms = overrides.get("skip_acronyms", set())
        extra_acronyms = overrides.get("extra_acronyms", {})
        extra_words = overrides.get("extra_words", {})

    text = prepare_text_for_tts(
        text,
        skip_acronyms=skip_acronyms or None,
        extra_acronyms=extra_acronyms or None,
        extra_words=extra_words or None,
    )

    return text


# ---------------------------------------------------------------------------
# Pre-flight validation
# ---------------------------------------------------------------------------

def _preflight_checks(config, *, dry_run: bool = False) -> None:
    """Validate config before any API calls to fail fast on misconfigs.

    In dry-run mode, only checks config structure (not files or env vars).
    """
    if dry_run:
        logger.info("Pre-flight checks skipped (dry-run mode)")
        return

    issues = []

    # Check prompt files exist
    for attr in ("digest_prompt_file", "podcast_prompt_file", "system_prompt_file"):
        path_str = getattr(config.llm, attr, "")
        if path_str and not (PROJECT_ROOT / path_str).exists():
            issues.append(f"Prompt file not found: {path_str}")

    # Check music files exist (skip transition_sting — it's auto-generated at runtime)
    for attr in ("music_file", "background_music_file"):
        path_str = getattr(config.audio, attr, None)
        if path_str and not (PROJECT_ROOT / path_str).exists():
            issues.append(f"Audio file not found: {path_str}")

    # Validate TTS provider name
    if config.tts.provider not in ("elevenlabs", "grok"):
        issues.append(
            f"Unknown TTS provider: {config.tts.provider!r} "
            "(supported: 'elevenlabs', 'grok')"
        )

    # Check critical API key env vars are populated. For TTS, only require
    # the key matching the configured provider — shows on Grok TTS don't
    # need ELEVENLABS_API_KEY and vice versa.
    if config.tts.provider == "elevenlabs" and not os.environ.get("ELEVENLABS_API_KEY"):
        issues.append("ELEVENLABS_API_KEY env var is empty or missing")

    if not (os.environ.get("GROK_API_KEY") or os.environ.get("XAI_API_KEY")):
        issues.append("GROK_API_KEY env var is empty or missing")

    # Validate numeric config bounds
    for attr in ("stability", "similarity_boost", "style"):
        val = getattr(config.tts, attr, None)
        if val is not None and not (0.0 <= val <= 1.0):
            issues.append(f"tts.{attr}={val} is out of range [0.0, 1.0]")
    if config.tts.max_chars is not None and config.tts.max_chars <= 0:
        issues.append(f"tts.max_chars={config.tts.max_chars} must be > 0")
    for attr in ("voice_intro_delay", "intro_duration", "overlap_duration",
                 "fade_duration", "outro_duration", "outro_crossfade",
                 "intro_volume", "overlap_volume", "fade_volume", "outro_volume"):
        val = getattr(config.audio, attr, None)
        if val is not None and val < 0:
            issues.append(f"audio.{attr}={val} must be >= 0")

    # Check R2 storage credentials if R2 is configured
    if getattr(config, "storage", None) and config.storage.provider == "r2":
        for env_attr in ("endpoint_env", "access_key_env", "secret_key_env"):
            env_name = getattr(config.storage, env_attr, "")
            if env_name and not os.environ.get(env_name):
                logger.warning("R2 env var %s (%s) is empty — upload may fail", env_name, env_attr)

    # YouTube preflight — fatal for enabled shows (catch before API spend).
    from engine.youtube_preflight import (
        validate_youtube_show_ready,
        youtube_network_quota_warning,
    )
    issues.extend(validate_youtube_show_ready(config, PROJECT_ROOT))
    yt_cfg = getattr(config, "youtube", None)
    if yt_cfg and getattr(yt_cfg, "enabled", False):
        playlist_id = (
            getattr(yt_cfg, "podcast_playlist_id", "") or ""
        ).strip()
        if not playlist_id:
            logger.warning(
                "YouTube enabled for %s but youtube.podcast_playlist_id "
                "is empty — episodes won't appear in the show's "
                "Podcast playlist on YouTube Music. Set the PL... ID "
                "in shows/%s.yaml after creating the playlist in Studio.",
                config.slug, config.slug,
            )
        quota_warn = youtube_network_quota_warning(PROJECT_ROOT)
        if quota_warn:
            logger.warning(quota_warn)

    # Newsletter preflight — when enabled, validate the status enum
    # before we hit Buttondown with a guaranteed-400 request.
    if config.newsletter.enabled:
        nl_status = (getattr(config.newsletter, "status", "") or "").strip()
        if nl_status and nl_status not in {"about_to_send", "draft", "scheduled"}:
            issues.append(
                f"newsletter.status={nl_status!r} is invalid — "
                "must be about_to_send, draft, or scheduled."
            )

    # Cost circuit breaker: skip episode if 7-day spend exceeds the show's
    # max_weekly_cost_usd (reads the previously committed dashboard JSON).
    max_cost = getattr(config, "max_weekly_cost_usd", 0.0) or 0.0
    if max_cost > 0:
        dashboard_path = PROJECT_ROOT / "api" / "dashboard.json"
        if dashboard_path.exists():
            try:
                import json as _json
                dash = _json.loads(dashboard_path.read_text(encoding="utf-8"))
                cost_rollup = (dash.get("cost_rollup") or {}).get("per_show") or {}
                show_cost = (cost_rollup.get(config.slug) or {}).get("last_7_days") or {}
                spent = float(show_cost.get("total", 0.0))
                if spent >= max_cost:
                    issues.append(
                        f"Cost circuit breaker: {config.slug} spent ${spent:.2f} "
                        f"in the last 7 days (limit ${max_cost:.2f})"
                    )
            except Exception as exc:
                logger.warning("Cost circuit breaker read failed: %s", exc)

    if issues:
        for issue in issues:
            logger.error("Pre-flight check FAILED: %s", issue)
        raise SystemExit(f"Pre-flight validation failed with {len(issues)} issue(s)")

    # Pre-flight LLM ping — 10-token completion against the configured model.
    # Catches model-id deprecations (xAI has rotated dated variants before)
    # before the expensive fetch + generation stages run. Failures here are
    # treated as warnings, not fatal — network blips shouldn't kill the run,
    # but a persistent deprecation will be obvious in the logs.
    try:
        from engine.generator import _call_grok
        _call_grok(
            "ping",
            model=config.llm.model,
            temperature=0.0,
            max_tokens=10,
            timeout=30.0,
        )
        logger.info("Pre-flight LLM ping OK (model=%s)", config.llm.model)
    except Exception as exc:
        logger.warning(
            "Pre-flight LLM ping failed for model=%s: %s (continuing anyway)",
            config.llm.model, exc,
        )

    # Validate newsletter API key if newsletter is enabled — gives a clear
    # early warning instead of failing silently at the end of the pipeline.
    if config.newsletter.enabled:
        nl_key = os.environ.get(config.newsletter.api_key_env, "").strip()
        if not nl_key:
            logger.warning(
                "Newsletter enabled for '%s' but %s not set — emails will be skipped",
                config.name, config.newsletter.api_key_env,
            )
        else:
            try:
                from engine.newsletter import validate_api_key
                if not validate_api_key(nl_key):
                    logger.error(
                        "Newsletter API key validation FAILED for '%s' — "
                        "emails will not be sent this run",
                        config.name,
                    )
            except Exception as exc:
                logger.warning("Newsletter API key validation error: %s", exc)

    logger.info("Pre-flight checks passed")


# ---------------------------------------------------------------------------
# Pipeline
# ---------------------------------------------------------------------------

def run(args: argparse.Namespace) -> None:
    from engine.config import load_config

    # 1. Load config
    config_path = PROJECT_ROOT / "shows" / f"{args.show}.yaml"
    config = load_config(config_path)
    logger.info("=== %s ===", config.name)

    # 1b. Pre-flight validation — catch misconfigs before expensive API calls
    _preflight_checks(config, dry_run=args.dry_run)

    if args.dry_run:
        logger.info("[DRY RUN] Would run full pipeline for '%s'", config.name)
        logger.info("  Sources: %d RSS feeds", len(config.sources))
        logger.info("  LLM: %s (model=%s)", config.llm.provider, config.llm.model)
        logger.info("  TTS: voice=%s, model=%s", config.tts.voice_id, config.tts.model)
        logger.info("  Music: %s", config.audio.music_file or "(none)")
        logger.info("  RSS: %s", config.publishing.rss_file)
        logger.info("  X posting: %s (prefix=%s)",
                     config.publishing.x_enabled, config.publishing.x_env_prefix)
        return

    today = datetime.date.today()
    today_str = today.strftime("%B %d, %Y")
    digests_dir = PROJECT_ROOT / config.episode.output_dir

    def _skip_episode(reason: str, detail: str) -> None:
        """Write a skip marker file and exit with code 2.

        The marker lets the daily review script distinguish intentional skips
        (insufficient articles, duplicate content, etc.) from genuine pipeline
        failures or missed workflow triggers.
        """
        marker_path = digests_dir / f".skip_{today.strftime('%Y%m%d')}.json"
        marker_path.parent.mkdir(parents=True, exist_ok=True)
        marker_data = {
            "date": today.isoformat(),
            "show": config.slug,
            "show_name": config.name,
            "reason": reason,
            "detail": detail,
            "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        }
        try:
            marker_path.write_text(json.dumps(marker_data, indent=2))
            logger.info("Skip marker written: %s (%s)", marker_path.name, reason)
        except OSError as exc:
            logger.warning("Failed to write skip marker: %s", exc)
        sys.exit(2)

    # Initialize pipeline metrics
    from engine.metrics import PipelineMetrics
    metrics = PipelineMetrics(show_slug=config.slug, episode_num=0)  # Updated after ep num known

    # 2. Episode number
    from engine.publisher import get_next_episode_number
    rss_path = PROJECT_ROOT / config.publishing.rss_file
    episode_num = get_next_episode_number(
        rss_path, digests_dir, mp3_glob_pattern=config.episode.mp3_glob,
    )
    logger.info("Episode number: %d", episode_num)
    metrics.episode_num = episode_num

    # 2b. Checkpoint: skip only when today's episode fully published.
    # MP3 alone is NOT sufficient — a prior run may have synthesized
    # audio but failed before RSS / R2 / git commit (May 2026 audit).
    expected_mp3 = digests_dir / config.episode.filename_pattern.format(
        prefix=config.episode.prefix, num=episode_num, date=today,
    )
    from engine.publish_marker import (
        is_publish_complete,
        publish_marker_path,
        write_publish_complete_marker,
    )

    publish_marker = publish_marker_path(digests_dir, today)
    resume_youtube_requested = getattr(args, "resume_youtube", False)
    if (
        is_publish_complete(publish_marker)
        and not args.test
        and not resume_youtube_requested
    ):
        logger.info(
            "Checkpoint: publish complete for %s (marker %s). Skipping.",
            today.isoformat(), publish_marker.name,
        )
        return

    from engine.pipeline_resume import (
        apply_resume_args,
        apply_resume_youtube_args,
        load_resume_publish_state,
        should_resume_publish,
        should_resume_youtube,
    )

    digest_md_path = digests_dir / (
        f"{config.episode.prefix}_Ep{episode_num:03d}_{today:%Y%m%d}.md"
    )
    resume_youtube = should_resume_youtube(
        expected_mp3,
        digest_md_path,
        test_mode=args.test,
        dry_run=args.dry_run,
        force=resume_youtube_requested,
    )
    if resume_youtube_requested and not resume_youtube:
        logger.error(
            "Resume YouTube requires MP3 and digest on disk (%s, %s).",
            expected_mp3.name,
            digest_md_path.name,
        )
        sys.exit(1)

    resume_publish = should_resume_publish(
        expected_mp3,
        publish_marker,
        test_mode=args.test,
        dry_run=args.dry_run,
        force=getattr(args, "resume_publish", False),
    )
    if resume_youtube:
        args = apply_resume_youtube_args(args)
        resume_publish = True
        logger.info(
            "Resume YouTube: rebuilding/uploading videos for %s (skipping TTS).",
            expected_mp3.name,
        )
    elif resume_publish and not getattr(args, "resume_publish", False):
        logger.warning(
            "MP3 %s exists but publish marker missing — resume publish only "
            "(skipping fetch/TTS; YouTube skipped to avoid duplicate uploads).",
            expected_mp3.name,
        )

    # 3. Tracker
    from engine.tracking import create_tracker, save_usage
    tracker = create_tracker(config.name, episode_num)

    # 3b. Initialize content lake database (idempotent — CREATE IF NOT EXISTS)
    try:
        from engine.content_lake import init_db as _init_lake_db
        _init_lake_db()
    except Exception as exc:
        logger.warning("Content lake init failed (non-fatal): %s", exc)

    final_mp3 = None
    audio_duration = 0.0
    x_thread = ""
    hook = None
    digest_md = None
    extra_context: dict = {}
    articles: list = []

    if resume_publish:
        args = apply_resume_args(args)
        try:
            rs = load_resume_publish_state(
                config,
                digests_dir=digests_dir,
                episode_num=episode_num,
                today=today,
                today_str=today_str,
                expected_mp3=expected_mp3,
                show_slug=args.show,
                extract_hook=_extract_hook,
                load_hook=_load_hook,
            )
        except FileNotFoundError as exc:
            logger.error("Resume publish aborted: %s", exc)
            sys.exit(1)
        x_thread = rs.x_thread
        hook = rs.hook
        final_mp3 = rs.final_mp3
        audio_duration = rs.audio_duration
        digest_md = rs.digest_md
        extra_context = rs.extra_context
    else:
        # 4 & 5. Pre-fetch hook + RSS fetch in parallel (concurrent.futures)
        hook_module = _load_hook(args.show)
        extra_context: dict = {}

        from engine.content_tracker import ContentTracker, SHOW_SECTION_PATTERNS
        from engine.utils import deduplicate_by_entity

        # Prefer YAML-provided section patterns; fall back to hardcoded registry
        section_patterns = (
            config.content_tracking.section_patterns
            if config.content_tracking.section_patterns
            else SHOW_SECTION_PATTERNS.get(config.slug, {})
        )
        ct_cfg = config.content_tracking
        content_tracker = ContentTracker(
            config.slug,
            digests_dir,
            quote_author_cooldown_days=getattr(ct_cfg, "quote_author_cooldown_days", 30),
        )
        content_tracker.load()

        feed_dicts = [{"url": s.url, "label": s.label} for s in config.sources]

        from concurrent.futures import ThreadPoolExecutor, as_completed

        def _run_hook():
            if hook_module and hasattr(hook_module, "pre_fetch"):
                logger.info("Running pre-fetch hook for %s ...", args.show)
                return hook_module.pre_fetch(
                    config, episode_num=episode_num, today_str=today_str,
                ) or {}
            return {}

        def _run_fetch():
            min_articles = getattr(config, "min_articles", None) or 3
            return _fetch_with_expansion(
                feed_dicts, config.keywords, content_tracker, min_articles,
                config=config,
            )

        def _run_x_fetch():
            # Skip the X API call if X posting is disabled for this show —
            # before May 12 2026 the fetch ran whenever ``x_accounts`` was
            # configured, regardless of ``x_enabled``, so shows with X
            # posting off still paid for X API calls and ingested X posts
            # that were never used. Operator-caught during the May 12 2026
            # pipeline audit.
            if not config.x_accounts or not config.publishing.x_enabled:
                return []
            from engine.fetcher import fetch_x_posts
            return fetch_x_posts(config.x_accounts, keywords=config.keywords)

        articles = []
        x_posts = []
        rss_fetch_failed = False
        narrative_topic: dict = {}

        # Narrative-mode shows (Unintended Consequences) bypass RSS fetch +
        # slow-news fallback entirely — their input is a curated topic
        # queue, not daily news. Pick the next unproduced topic up-front;
        # if the queue is exhausted, skip the episode rather than producing
        # content with empty inputs.
        if getattr(config, "narrative_mode", False):
            from engine.topic_queue import pick_next_topic
            queue_path = PROJECT_ROOT / config.topic_queue_file
            narrative_topic = pick_next_topic(queue_path) or {}
            if not narrative_topic:
                _skip_episode(
                    "narrative_queue_empty",
                    f"Topic queue {config.topic_queue_file} has no unproduced "
                    f"entries. Append new topics to keep the show running.",
                )
                return  # _skip_episode raises SystemExit, but mypy doesn't know that
            logger.info(
                "Narrative mode: picked topic %r (%s)",
                narrative_topic.get("id"), narrative_topic.get("title"),
            )
            metrics.record("narrative_mode", True)
            metrics.record("narrative_topic_id", narrative_topic.get("id", ""))
            # Skip the fetch threadpool entirely — articles stays [].

        with metrics.stage("fetch_and_dedup"):
            with ThreadPoolExecutor(max_workers=3) as executor:
                hook_future = executor.submit(_run_hook)
                fetch_future = executor.submit(_run_fetch)
                x_fetch_future = executor.submit(_run_x_fetch)

                try:
                    extra_context = hook_future.result(timeout=60)
                except Exception as exc:
                    logger.warning(
                        "Pre-fetch hook failed for %s: %s — continuing without hook data",
                        args.show, exc,
                    )
                    extra_context = {}

                try:
                    articles = fetch_future.result(timeout=120)
                except Exception as exc:
                    logger.error("RSS fetch failed: %s", exc)
                    articles = []
                    # Distinguish a structural fetch failure from a genuine
                    # slow-news day. Without this flag, slow_news mode would
                    # happily ship an evergreen-only episode when feeds are
                    # actually broken, masking the outage from operators.
                    rss_fetch_failed = True

                try:
                    x_posts = x_fetch_future.result(timeout=120)
                    if x_posts:
                        tracker["services"]["x_api"]["search_calls"] = len(x_posts)
                except Exception as exc:
                    logger.warning("X account fetch failed: %s — continuing with RSS only", exc)
                    x_posts = []

        if rss_fetch_failed and not articles and not x_posts:
            _skip_episode(
                "rss_fetch_failed",
                "RSS fetch raised and no fallback content available. "
                "Refusing to ship evergreen filler on a fetch outage.",
            )

        # Merge X posts into articles, deduplicating against existing RSS articles
        if x_posts:
            logger.info("Merging %d X posts from %d account(s) into %d RSS articles",
                         len(x_posts), len(config.x_accounts), len(articles))
            from engine.utils import calculate_similarity
            _X_DEDUP_THRESHOLD = 0.65
            filtered_x = []
            for xp in x_posts:
                xp_title = (xp.get("title") or xp.get("summary") or "")[:200]
                if not xp_title:
                    filtered_x.append(xp)
                    continue
                is_dup = False
                for art in articles:
                    art_title = (art.get("title") or art.get("summary") or "")[:200]
                    if art_title and calculate_similarity(xp_title, art_title) >= _X_DEDUP_THRESHOLD:
                        logger.info("X post deduped against RSS article (%.0f%%): '%s'",
                                    calculate_similarity(xp_title, art_title) * 100,
                                    xp_title[:80])
                        is_dup = True
                        break
                if not is_dup:
                    filtered_x.append(xp)
            skipped = len(x_posts) - len(filtered_x)
            if skipped:
                logger.info("Cross-dedup filtered %d X post(s) that overlapped with RSS articles", skipped)
            articles.extend(filtered_x)
            x_posts = filtered_x  # Update for accurate count below
        logger.info("After fetch + dedup: %d articles (incl. %d X posts)", len(articles), len(x_posts))

        # 5a2. Web search fallback — if articles below quality threshold, try Grok web_search
        web_articles: list = []
        min_quality = getattr(config, "min_articles", 6) or 6
        if len(articles) < min_quality and getattr(config, "web_search_queries", None):
            logger.info(
                "Articles (%d) below quality threshold (%d) — trying web search ...",
                len(articles), min_quality,
            )
            try:
                from engine.fetcher import fetch_web_search_articles
                web_articles = fetch_web_search_articles(
                    config.web_search_queries,
                    keywords=config.keywords,
                )
                if web_articles:
                    from engine.utils import calculate_similarity
                    # Dedup web articles against existing RSS+X articles
                    deduped_web = []
                    for wa in web_articles:
                        wa_title = wa.get("title", "")[:200]
                        is_dup = any(
                            calculate_similarity(wa_title, a.get("title", "")[:200]) >= 0.65
                            for a in articles
                        )
                        if not is_dup:
                            deduped_web.append(wa)
                    logger.info(
                        "Web search: %d articles found, %d after cross-dedup",
                        len(web_articles), len(deduped_web),
                    )
                    articles.extend(deduped_web)
                    web_articles = deduped_web
            except Exception as exc:
                logger.warning("Web search fallback failed (non-fatal): %s", exc)

        logger.info(
            "Content pipeline: %d RSS + %d X + %d web_search = %d total",
            len(articles) - len(x_posts) - len(web_articles),
            len(x_posts), len(web_articles), len(articles),
        )
        metrics.record("article_count", len(articles))

        if not articles and not getattr(config, "narrative_mode", False):
            logger.warning("No articles found even after expanded search. Skipping episode.")
            _skip_episode("no_articles", "No articles found even after expanded search.")

        # Skip episode if digest would be too thin — or activate slow news mode
        skip_threshold = getattr(config, "min_articles_skip", 3) or 3
        slow_news_mode = False
        selected_segs: list = []

        # Helper: query content lake for recently covered topics (for segment selection)
        def _get_covered_topics() -> set:
            try:
                from engine.content_lake import query_show_range
                from datetime import timedelta
                hist = query_show_range(
                    args.show,
                    (today - timedelta(days=30)).isoformat(),
                    today.isoformat(),
                )
                topics: set = set()
                for ep in hist:
                    topics.update(t.lower() for t in ep.get("topics", []))
                return topics
            except Exception as exc:
                logger.warning("Content lake query failed (dedup disabled): %s", exc)
                return set()

        if (
            len(articles) < skip_threshold
            and not getattr(config, "narrative_mode", False)
        ):
            from engine.slow_news import is_slow_news_day, load_segment_library, select_segments

            if is_slow_news_day(len(articles), config):
                logger.info(
                    "Slow news day: %d article(s) below threshold %d — activating evergreen segments",
                    len(articles), skip_threshold,
                )
                library = load_segment_library(config.slow_news.library_file)
                recent_seg_ids = content_tracker.get_recent_segment_ids(
                    days=config.slow_news.cooldown_days,
                )
                selected_segs = select_segments(
                    library,
                    recent_seg_ids,
                    max_segments=config.slow_news.max_segments,
                    mode=config.slow_news.selection_mode,
                    covered_topics=_get_covered_topics(),
                )
                slow_news_mode = True
                metrics.record("slow_news_mode", True)
            else:
                logger.warning(
                    "Only %d article(s) found — below minimum threshold (%d) for a quality episode. Skipping.",
                    len(articles), skip_threshold,
                )
                _skip_episode(
                    "insufficient_articles",
                    f"Only {len(articles)} article(s) found — below minimum threshold ({skip_threshold}).",
                )

        # 5b2. Thin content detection — article count is above skip threshold but
        #      below the quality threshold (min_articles).  Activate slow news mode
        #      to supplement with evergreen segments so the LLM has enough material.
        min_quality = getattr(config, "min_articles", 6) or 6
        if (
            not slow_news_mode
            and len(articles) < min_quality
            and config.slow_news.enabled
        ):
            from engine.slow_news import load_segment_library, select_segments

            logger.warning(
                "Thin content: %d articles (skip threshold %d met, quality "
                "threshold %d not met) — supplementing with evergreen segments",
                len(articles), skip_threshold, min_quality,
            )
            library = load_segment_library(config.slow_news.library_file)
            recent_seg_ids = content_tracker.get_recent_segment_ids(
                days=config.slow_news.cooldown_days,
            )
            selected_segs = select_segments(
                library,
                recent_seg_ids,
                max_segments=config.slow_news.max_segments,
                mode=config.slow_news.selection_mode,
                covered_topics=_get_covered_topics(),
            )
            slow_news_mode = True
            metrics.record("slow_news_mode", True)
            metrics.record("slow_news_trigger", "thin_content")

        # 5c. Pre-dedup cap: high-volume shows (OV with 28 general-news feeds)
        # can fetch 200-300 raw articles.  Pairwise dedup is O(n²), so 288
        # articles → ~41K comparisons → 80s.  Capping at 150 keeps the dedup
        # stage under 30s while still seeing enough variety for quality selection.
        MAX_RAW_BEFORE_DEDUP = 150
        if len(articles) > MAX_RAW_BEFORE_DEDUP:
            logger.info(
                "Pre-dedup cap: %d → %d articles (keeping most recent / highest relevance)",
                len(articles), MAX_RAW_BEFORE_DEDUP,
            )
            articles = articles[:MAX_RAW_BEFORE_DEDUP]

        # 5d. Sort by relevance_score desc to select the best articles for the
        # cap, then restore chronological order for the LLM prompt.  Prompt order
        # influences the model's output format — reordering articles can cause the
        # LLM to break the structured digest template (headings, numbered items).
        articles.sort(
            key=lambda a: (a.get("relevance_score", 0.0), a.get("published_date", "")),
            reverse=True,
        )

        # 5e. Cap article count to prevent prompt bloat and quality degradation.
        # Bumped 25 → 40 (May 2026 operator feedback): every show's digest
        # asks for a Top 12-15 list, plus the Spotlight / Deep Dive
        # sections. A 25-article cap left the LLM nothing to choose from
        # — when 6 of 25 were Google-News-aggregated duplicates of the
        # same story, the surviving 19 barely cleared "Top 15" and the
        # digest shrank to 6-8 substantive items. 40 articles gives the
        # LLM headroom to drop near-duplicates and still hit the 15-item
        # target with diverse angles. Prompt token usage rises ~30%
        # (~1200 extra tokens) but stays well under the 128k context.
        MAX_ARTICLES_FOR_LLM = 40
        if len(articles) > MAX_ARTICLES_FOR_LLM:
            logger.info(
                "Capping articles from %d to %d to prevent prompt bloat",
                len(articles), MAX_ARTICLES_FOR_LLM,
            )
            articles = articles[:MAX_ARTICLES_FOR_LLM]

        # 5f. Restore chronological order for the prompt — LLMs follow the digest
        # format template more reliably when articles appear newest-first by feed,
        # not reordered by an internal score the model doesn't see.
        articles.sort(key=lambda a: a.get("published_date", ""), reverse=True)

        # 6. Build template vars for digest prompt
        # Regex to strip dateline suffixes that RSS sources (e.g. Teslarati)
        # embed in article titles — e.g. "Tesla Model 2 Rises April 12, 2026,
        # 1:54 AM PST".  The published_date field already carries this info.
        _DATELINE_TAIL = re.compile(
            r"\s*(?:January|February|March|April|May|June|July|August|September|"
            r"October|November|December)\s+\d{1,2},?\s+\d{4},?\s+\d{1,2}:\d{2}\s*(?:AM|PM)\s*(?:PST|PDT|EST|EDT|CST|CDT|UTC|GMT)?\s*$",
            re.IGNORECASE,
        )

        news_lines = []
        for i, art in enumerate(articles, 1):
            title = art.get("title", "Untitled")
            title = _DATELINE_TAIL.sub("", title).rstrip(" :—–-")
            desc = art.get("description", "")
            url = art.get("url", "")
            source = art.get("source_name", "Unknown")
            pub = art.get("published_date", "")
            news_lines.append(
                f"{i}. **{title}** — {source}"
                + (f" ({pub})" if pub else "")
                + f"\n   {desc}\n   URL: {url}"
            )
        news_section = "\n\n".join(news_lines)

        # Get content tracker summary for the LLM to avoid cross-episode repetition
        content_tracker_summary = content_tracker.get_summary_for_prompt()
        if content_tracker_summary:
            logger.info("Injecting content tracker summary into LLM prompt (%d chars)", len(content_tracker_summary))

        # Get recent deep dive topics for freshness enforcement
        recent_deep_dives = content_tracker.get_recent_deep_dive_topics(max_items=14)
        if recent_deep_dives:
            deep_dive_topics_text = "\n".join(f"- {t}" for t in recent_deep_dives)
            logger.info("Injecting %d recent deep dive topics into prompt", len(recent_deep_dives))
        else:
            deep_dive_topics_text = "(No previous deep dives — you have full freedom to choose any topic.)"

        template_vars = {
            "today_str": today_str,
            "date_human": today_str,  # alias used by Omni View prompts
            "news_section": news_section,
            "sections_json": news_section,  # alias used by Omni View digest prompt
            "episode_num": episode_num,
            "recent_content_summary": content_tracker_summary,
            "recent_deep_dive_topics": deep_dive_topics_text,
        }
        # Narrative-mode shows feed a topic from the queue into the digest
        # prompt instead of news articles. Stage the topic vars here so the
        # downstream digest prompt template can resolve ``{topic_title}``,
        # ``{topic_brief}``, and ``{topic_category}``. (The actual queue
        # pick + skip-when-empty happens further up — see narrative_mode
        # branch around the fetch stage.)
        if getattr(config, "narrative_mode", False):
            narrative_topic = locals().get("narrative_topic") or {}
            template_vars["topic_title"] = narrative_topic.get("title", "")
            template_vars["topic_brief"] = narrative_topic.get("brief", "")
            template_vars["topic_category"] = narrative_topic.get("category", "")
        # Slow news day context injection
        if slow_news_mode and selected_segs:
            from engine.slow_news import build_slow_news_prompt_context

            # Gather previous angle summaries for freshness enforcement
            previous_angles: dict = {}
            for seg in selected_segs:
                history = content_tracker.get_segment_history(seg["id"], limit=3)
                angles = [h["summary"] for h in history if h.get("summary")]
                if angles:
                    previous_angles[seg["id"]] = angles

            template_vars["slow_news_context"] = build_slow_news_prompt_context(
                articles, selected_segs, config, template_vars, previous_angles,
            )
        else:
            template_vars["slow_news_context"] = ""

        # Cross-show topic awareness from content lake (avoid redundancy across shows)
        try:
            from engine.content_lake import query_all_shows_range
            from datetime import timedelta
            cross_start = (today - timedelta(days=7)).isoformat()
            cross_end = today.isoformat()
            recent_cross = query_all_shows_range(cross_start, cross_end)
            other_show_topics = [
                ep for ep in recent_cross
                if ep.get("show_slug") != args.show and ep.get("headlines")
            ]
            if other_show_topics:
                lines = []
                for ep in other_show_topics[-10:]:  # Last 10 episodes from other shows
                    show_label = ep.get("show_name", ep.get("show_slug", ""))
                    date_label = ep.get("date", "")
                    headlines = ep.get("headlines", [])[:3]
                    if headlines:
                        lines.append(f"- {show_label} ({date_label}): {'; '.join(headlines)}")
                if lines:
                    template_vars["cross_show_context"] = (
                        "Topics recently covered by other Nerra Network shows "
                        "(avoid redundancy):\n" + "\n".join(lines)
                    )
                    logger.info("Injecting cross-show context (%d shows) into digest prompt", len(lines))
            if "cross_show_context" not in template_vars:
                template_vars["cross_show_context"] = (
                    "(No recent cross-network coverage to dedupe against today.)"
                )
        except Exception as exc:
            logger.debug("Cross-show context unavailable (non-fatal): %s", exc)
            template_vars["cross_show_context"] = (
                "(Cross-network context unavailable — proceed without dedupe signal.)"
            )

        # Merge extra context from hooks (e.g. price, change_str, x_posts_section)
        template_vars.update(extra_context)

        # 7. Generate digest
        #
        # Sunday weekly-recap mode (May 2026 schedule overhaul). When the
        # show has ``weekly_recap_on_sunday: true`` and today is Sunday,
        # short-circuit the news-fetch + LLM digest stage by synthesising
        # a digest from the past 7 days of canonical episodes via the
        # content lake. The rest of the pipeline (podcast script gen,
        # TTS, publish) runs unchanged on this synthetic digest, so
        # listeners get the same narrative quality as a daily episode.
        is_weekly_recap = (
            bool(getattr(config, "weekly_recap_on_sunday", False))
            and today.weekday() == 6
        )
        from engine.generator import generate_digest, LLMRefusalError
        if is_weekly_recap:
            logger.info("Sunday weekly-recap mode active for %s.", config.slug)
            from engine.weekly_recap import build_weekly_recap_digest
            x_thread = build_weekly_recap_digest(
                config.slug, config.name, today,
            )
            if not x_thread:
                logger.warning(
                    "Weekly recap could not be synthesised (insufficient "
                    "content lake data) — falling back to daily fetch.",
                )
                is_weekly_recap = False
            else:
                metrics.record("weekly_recap_mode", True)
        if not is_weekly_recap:
            logger.info("Generating digest ...")
            try:
                with metrics.stage("generate_digest"):
                    x_thread = generate_digest(template_vars, config, tracker=tracker)
            except LLMRefusalError as e:
                logger.error("PIPELINE ABORTED: %s", e)
                logger.error(
                    "The LLM refused to generate content. This typically means the news "
                    "sources had insufficient relevant content. Check source feeds and "
                    "consider re-running later."
                )
                save_usage(tracker, digests_dir)
                sys.exit(1)

        # Record episode content in the cross-episode tracker
        if section_patterns:
            _article_urls = [a.get("url", "") for a in articles if a.get("url")]
            _article_titles = [a.get("title", "") for a in articles if a.get("title")]
            content_tracker.record_episode(
                x_thread, section_patterns,
                source_urls=_article_urls,
                source_titles=_article_titles,
            )
            content_tracker.save()

        # Record slow-news segment metadata for cooldown tracking & freshness
        if slow_news_mode and selected_segs:
            import datetime as _dt
            today_iso = _dt.date.today().isoformat()
            for ep in content_tracker.data.get("episodes", []):
                if ep.get("date") == today_iso:
                    ep["slow_news"] = True
                    ep["slow_news_segments"] = [s["id"] for s in selected_segs]
                    ep["slow_news_segment_summaries"] = _extract_segment_summaries(
                        x_thread, selected_segs,
                    )
                    break
            content_tracker.save()
            logger.info(
                "Recorded slow-news segments: %s",
                [s["id"] for s in selected_segs],
            )

        # 7b. Post-generation digest validation — catch structure issues before TTS.
        #      If critical sections are missing, retry digest generation once with an
        #      explicit instruction to include them.
        #
        # Skip entirely when in Sunday weekly-recap mode. Operator caught
        # (May 10 2026) the recap digest produced by ``build_weekly_recap_digest``
        # being silently OVERWRITTEN here: the daily-format validator
        # rejected the recap (missing "Top 10 News Items", "Tesla First
        # Principles", etc. — sections that don't apply on a recap day),
        # the retry path called ``generate_digest`` with the live news
        # template, and the synthesised recap content got replaced by a
        # daily digest from TODAY's news. Six of seven recap-eligible
        # shows shipped daily content on May 10 with the metric still
        # claiming ``weekly_recap_mode: True``. M&A survived only because
        # its validator config didn't enforce conflicting sections. Recaps
        # have their own fixed shape ("This Week's Top Stories") and
        # don't need the daily-format validator's protection.
        from engine.validation import validate_digest as _validate_digest, SHOW_VALIDATION_CONFIGS
        _val_factory = SHOW_VALIDATION_CONFIGS.get(config.slug)
        _exact_dups: list = []  # Populated by validate_digest for 100% cross-episode matches
        if _val_factory and not is_weekly_recap:
            _val_config = _val_factory()
            _recent = content_tracker.get_recent_headlines(days=7)
            _val_passed, _val_issues, _exact_dups = _validate_digest(
                x_thread, _val_config,
                section_patterns=section_patterns,
                recent_headlines=_recent,
            )
            # Near-verbatim within-episode duplicates (>= 80%): strip the later
            # occurrence from the digest and continue rather than aborting the
            # entire episode.  A single repeated story is not worth killing an
            # otherwise good episode — especially when X posts added fresh content.
            _critical_dup_issues = []
            for _issue in _val_issues:
                if "Duplicate within" not in _issue:
                    continue
                _m = re.search(r"similarity\s+(\d+)%", _issue)
                if _m and int(_m.group(1)) >= 80:
                    _critical_dup_issues.append(_issue)
            if _critical_dup_issues:
                logger.warning(
                    "Digest has %d near-verbatim (>=80%%) intra-episode duplicate(s) — "
                    "stripping duplicates and continuing: %s",
                    len(_critical_dup_issues), "; ".join(_critical_dup_issues),
                )
                from engine.generator import _strip_duplicate_stories
                x_thread = _strip_duplicate_stories(
                    x_thread, threshold=0.75, show_name=config.name,
                )
            if not _val_passed:
                # Check for critical missing sections (non-optional)
                _missing = [
                    i for i in _val_issues
                    if "missing from digest" in i.lower()
                ]
                if _missing:
                    logger.warning(
                        "Digest missing %d critical section(s): %s — retrying once ...",
                        len(_missing), "; ".join(_missing),
                    )
                    _section_names = [
                        m.split("'")[1] for m in _missing if "'" in m
                    ]
                    _section_list = ", ".join(_section_names)
                    _retry_suffix = (
                        f"\n\nCRITICAL: Your previous attempt was rejected because "
                        f"it was missing these required sections: {_section_list}. "
                        f"You MUST include ALL sections from the formatting template "
                        f"above. If source material is limited, use the available "
                        f"articles to write those sections with extra depth rather "
                        f"than omitting them. Do NOT skip any section."
                    )
                    try:
                        with metrics.stage("generate_digest_retry"):
                            x_thread_retry = generate_digest(
                                template_vars, config, tracker=tracker,
                                prompt_suffix=_retry_suffix,
                            )
                        # Re-validate
                        _val2_passed, _val2_issues, _exact_dups2 = _validate_digest(
                            x_thread_retry, _val_config,
                            section_patterns=section_patterns,
                            recent_headlines=_recent,
                        )
                        _missing2 = [
                            i for i in _val2_issues
                            if "missing from digest" in i.lower()
                        ]
                        # If the original is very short (likely garbage from a
                        # failed refusal recovery), prefer any substantially
                        # longer retry regardless of section comparison.
                        _orig_is_garbage = len(x_thread) < 2000 and len(x_thread_retry) > len(x_thread) * 3
                        if _orig_is_garbage:
                            logger.info(
                                "Original digest looks like garbage (%d chars) — "
                                "preferring much longer retry (%d chars)",
                                len(x_thread), len(x_thread_retry),
                            )
                            x_thread = x_thread_retry
                            _exact_dups = _exact_dups2
                        elif len(_missing2) < len(_missing):
                            logger.info(
                                "Digest retry improved: %d → %d missing sections",
                                len(_missing), len(_missing2),
                            )
                            x_thread = x_thread_retry
                            _exact_dups = _exact_dups2
                        elif len(x_thread_retry) > len(x_thread):
                            # Same missing sections but retry is longer — prefer
                            # the longer output (less likely to be garbage).
                            logger.info(
                                "Digest retry same sections but longer (%d → %d chars) — using retry",
                                len(x_thread), len(x_thread_retry),
                            )
                            x_thread = x_thread_retry
                            _exact_dups = _exact_dups2
                        else:
                            logger.warning("Digest retry did not improve — keeping original")
                    except LLMRefusalError:
                        # LLM refusal is a permanent failure — don't mask it
                        logger.error("Digest retry refused by LLM — aborting episode")
                        raise
                    except Exception as exc:
                        logger.warning("Digest retry failed: %s — keeping original", exc)
                else:
                    # Check for item-count shortfalls (e.g. "Top News has 3 items, minimum is 5").
                    # These can be genuine content gaps OR formatting mismatches (the LLM
                    # wrote the content but didn't use bold markers for items).  If the
                    # digest is long enough to be real content, treat as a warning rather
                    # than killing the episode.
                    _item_count_issues = [
                        i for i in _val_issues
                        if "has only" in i.lower() or "below minimum" in i.lower()
                           or ("item" in i.lower() and "minimum" in i.lower())
                    ]
                    if _item_count_issues:
                        _digest_char_count = len(x_thread.strip())
                        if _digest_char_count < 1500:
                            # Genuinely thin digest — not enough content
                            logger.error(
                                "Digest has %d item-count shortfall(s) and is short "
                                "(%d chars) — episode too thin to publish: %s",
                                len(_item_count_issues), _digest_char_count,
                                "; ".join(_item_count_issues),
                            )
                            _skip_episode(
                                "thin_episode",
                                f"Digest has {len(_item_count_issues)} item-count shortfall(s) "
                                f"and is short ({_digest_char_count} chars).",
                            )
                        else:
                            # Long enough to be real content — likely a formatting
                            # mismatch rather than missing content.
                            logger.warning(
                                "Digest has %d item-count shortfall(s) but is %d chars "
                                "(likely formatting mismatch, not missing content): %s",
                                len(_item_count_issues), _digest_char_count,
                                "; ".join(_item_count_issues),
                            )

                    # Check for excessive cross-episode repeats — a few follow-ups
                    # are normal, but 3+ identical headlines means the LLM ignored
                    # the content tracker.
                    _repeat_issues = [
                        i for i in _val_issues
                        if "cross-episode repeat" in i.lower()
                    ]
                    metrics.record("cross_episode_repeats", len(_repeat_issues))
                    _repeat_threshold = getattr(config.slow_news, "repeat_trigger_threshold", 3) or 3
                    # Spec v2 follow-up after Tesla Ep459: a daily news show
                    # legitimately revisits 3-6 ongoing stories per day
                    # (Tesla earnings cadence, FSD lawsuit, Cybertruck
                    # production updates) without that meaning "the LLM
                    # ignored the content tracker." Today's run had 6
                    # cross-episode repeats out of 22 articles (27%) — far
                    # under "the digest is mostly recycled" — but the
                    # absolute threshold of 3 still triggered slow-news
                    # fallback, burning ~5 minutes regenerating from
                    # evergreen segments instead of just shipping the
                    # surviving 16 fresh stories. Add a ratio gate: only
                    # fall back when repeats are BOTH above the absolute
                    # threshold AND >=40% of the digest. This lets healthy
                    # news cycles ship; protects against actual tracker-
                    # ignoring runs.
                    total_digest_items = max(1, len(articles))
                    repeat_ratio = len(_repeat_issues) / total_digest_items
                    metrics.record("cross_episode_repeat_ratio", round(repeat_ratio, 3))
                    # Ratio gate raised from 0.40 → 0.55 in the May 2026
                    # content audit. TST/FF/PT were tripping slow-news
                    # mode on 60-87% of episodes despite shipping plenty
                    # of unique stories — the previous gate ate cycles
                    # where, say, 10 of 22 articles overlapped with a
                    # week of Tesla-FSD coverage. 0.55 lets healthy news
                    # cycles ship and only falls back when the digest is
                    # genuinely majority-recycled. Per-show override via
                    # ``slow_news.repeat_trigger_ratio`` for shows that
                    # want to keep tighter constraints.
                    _repeat_ratio_threshold = float(
                        getattr(config.slow_news, "repeat_trigger_ratio", 0.55) or 0.55
                    )
                    if (
                        len(_repeat_issues) >= _repeat_threshold
                        and repeat_ratio >= _repeat_ratio_threshold
                    ):
                        # If slow news mode is available, fall back to it instead
                        # of skipping entirely — the repeat articles are stale but
                        # evergreen segments can fill the episode.
                        if not slow_news_mode and config.slow_news.enabled:
                            from engine.slow_news import (
                                load_segment_library, select_segments,
                                build_slow_news_prompt_context,
                            )
                            logger.warning(
                                "Digest has %d cross-episode repeat(s) — falling back "
                                "to slow news mode with evergreen segments",
                                len(_repeat_issues),
                            )
                            library = load_segment_library(config.slow_news.library_file)
                            recent_seg_ids = content_tracker.get_recent_segment_ids(
                                days=config.slow_news.cooldown_days,
                            )
                            selected_segs = select_segments(
                                library,
                                recent_seg_ids,
                                max_segments=config.slow_news.max_segments,
                                mode=config.slow_news.selection_mode,
                            )
                            slow_news_mode = True
                            metrics.record("slow_news_mode", True)
                            metrics.record("slow_news_trigger", "stale_repeats")

                            # Gather previous angle summaries for freshness
                            previous_angles: dict = {}
                            for seg in selected_segs:
                                history = content_tracker.get_segment_history(seg["id"], limit=3)
                                angles = [h["summary"] for h in history if h.get("summary")]
                                if angles:
                                    previous_angles[seg["id"]] = angles

                            template_vars["slow_news_context"] = build_slow_news_prompt_context(
                                articles, selected_segs, config, template_vars, previous_angles,
                            )

                            # Re-generate digest with slow news context
                            logger.info("Re-generating digest with slow news context ...")
                            try:
                                with metrics.stage("generate_digest_slow_news"):
                                    x_thread = generate_digest(
                                        template_vars, config, tracker=tracker,
                                    )
                            except LLMRefusalError as e:
                                logger.error("Slow news fallback digest refused: %s", e)
                                _skip_episode(
                                    "llm_refusal",
                                    f"Slow news fallback digest refused by LLM: {e}",
                                )
                            except Exception as e:
                                logger.error("Slow news fallback digest failed: %s", e)
                                sys.exit(1)

                            # Extract hook from the regenerated digest
                            hook = _extract_hook(x_thread)
                            if not hook:
                                hook = f"Episode {episode_num}"
                            logger.info("Slow news fallback hook: %s", hook)

                            # Re-record episode content
                            if section_patterns:
                                _article_urls = [a.get("url", "") for a in articles if a.get("url")]
                                _article_titles = [a.get("title", "") for a in articles if a.get("title")]
                                content_tracker.record_episode(
                                    x_thread, section_patterns,
                                    source_urls=_article_urls,
                                    source_titles=_article_titles,
                                )
                                content_tracker.save()
                        else:
                            logger.error(
                                "Digest has %d cross-episode repeat(s) — too many recycled "
                                "stories to publish.",
                                len(_repeat_issues),
                            )
                            _skip_episode(
                                "cross_episode_repeats",
                                f"Digest has {len(_repeat_issues)} cross-episode repeat(s) — "
                                "too many recycled stories.",
                            )

                    logger.warning(
                        "Digest validation found %d issue(s) — continuing (non-blocking)",
                        len(_val_issues),
                    )
        else:
            logger.debug("No validation config for show '%s' — skipping digest validation", config.slug)

        # 7c. Minimum digest length gate — catch LLM garbage (e.g. 319-char responses)
        #     before the pipeline spends TTS credits and publishes a bad episode.
        #     A normal digest is 3000-10000+ chars.  Below 800 chars the LLM clearly
        #     failed to produce a usable episode.
        _MIN_DIGEST_CHARS = 800
        _digest_len = len(x_thread.strip())
        if _digest_len < _MIN_DIGEST_CHARS:
            # Try slow news fallback — the LLM may do better with structured
            # evergreen prompts than with the regular digest template.
            if not slow_news_mode and config.slow_news.enabled:
                logger.warning(
                    "Digest is too short (%d chars, minimum %d) — attempting slow "
                    "news fallback with evergreen segments ...",
                    _digest_len, _MIN_DIGEST_CHARS,
                )
                from engine.slow_news import (
                    load_segment_library, select_segments,
                    build_slow_news_prompt_context,
                )
                try:
                    library = load_segment_library(config.slow_news.library_file)
                    recent_seg_ids = content_tracker.get_recent_segment_ids(
                        days=config.slow_news.cooldown_days,
                    )
                    selected_segs = select_segments(
                        library, recent_seg_ids,
                        max_segments=config.slow_news.max_segments,
                        mode=config.slow_news.selection_mode,
                    )
                    previous_angles: dict = {}
                    for seg in selected_segs:
                        previous_angles[seg["id"]] = content_tracker.get_segment_history(
                            seg["id"], limit=3,
                        )
                    slow_ctx = build_slow_news_prompt_context(
                        articles, selected_segs, config, template_vars, previous_angles,
                    )
                    template_vars["slow_news_context"] = slow_ctx
                    slow_news_mode = True

                    with metrics.stage("generate_digest_llm_fallback"):
                        x_thread = generate_digest(template_vars, config, tracker=tracker)

                    _digest_len = len(x_thread.strip())
                    if _digest_len >= _MIN_DIGEST_CHARS:
                        logger.info(
                            "Slow news fallback produced usable digest (%d chars)",
                            _digest_len,
                        )
                    else:
                        logger.error(
                            "Slow news fallback still too short (%d chars) — aborting",
                            _digest_len,
                        )
                        save_usage(tracker, digests_dir)
                        sys.exit(1)
                except Exception as exc:
                    logger.error(
                        "Slow news fallback failed: %s — aborting", exc,
                    )
                    save_usage(tracker, digests_dir)
                    sys.exit(1)
            else:
                logger.error(
                    "Digest is too short (%d chars, minimum %d) — LLM returned "
                    "garbage. Aborting episode.",
                    _digest_len, _MIN_DIGEST_CHARS,
                )
                save_usage(tracker, digests_dir)
                sys.exit(1)

        # Extract the daily hook (headline) from the digest
        hook = _extract_hook(x_thread)
        if hook:
            logger.info("Hook: %s", hook)
        else:
            logger.warning("No HOOK found in digest — using generic episode title")

        # Log slow news mode but do NOT tag the episode title — slow news
        # episodes should be indistinguishable from regular episodes.
        if slow_news_mode:
            logger.info("Slow news mode active (not tagged in title)")

        # Defense-in-depth: final refusal scan before saving digest
        from engine.generator import _REFUSAL_PATTERNS as _FINAL_REFUSAL_PATTERNS
        for _rpat in _FINAL_REFUSAL_PATTERNS:
            if re.search(_rpat, x_thread):
                logger.error("BLOCKED: Digest contains LLM refusal text (matched: %s)", _rpat[:60])
                raise SystemExit(1)

        # Scrub LLM scaffold + run body transforms ONCE on the canonical
        # digest text. Spec v2 follow-up: previously these passes only ran
        # inside `send_show_newsletter`, so the email subscriber saw the
        # cleaned version but the blog reader, RSS show-notes reader, and
        # GitHub Pages summary saw the raw LLM output (with **HOOK:**,
        # **Date:**, box-drawing rules, **TOPIC SELECTION:**, raw Google
        # News URLs, etc.). Scrubbing here makes the canonical .md the
        # single source of truth for every downstream surface. The
        # newsletter pipeline still re-scrubs as defense-in-depth — both
        # passes are idempotent.
        from engine.newsletter_body import transform_daily_body
        from engine.newsletter_sanitizer import scrub_scaffold
        x_thread = scrub_scaffold(x_thread)
        x_thread = transform_daily_body(x_thread, slug=getattr(config, "slug", ""))
        if args.show == "tesla":
            from shows.hooks.tesla import scrub_unavailable_tsla_from_digest
            x_thread = scrub_unavailable_tsla_from_digest(x_thread)

        # Save digest to file. Strip lone UTF-16 surrogates (the LLM
        # occasionally emits one); ``write_text`` would otherwise abort the
        # whole pipeline on ``UnicodeEncodeError``. See engine.utils.
        from engine.utils import strip_lone_surrogates as _scrub
        digest_md = digests_dir / f"{config.episode.prefix}_Ep{episode_num:03d}_{today:%Y%m%d}.md"
        digest_md.write_text(_scrub(x_thread), encoding="utf-8")
        logger.info("Digest saved: %s", digest_md)

        # Narrative-mode shows: mark the topic as produced in the queue so
        # the next run picks the next entry. Done after the digest is on
        # disk so a mid-pipeline failure doesn't burn a queue slot.
        if (
            getattr(config, "narrative_mode", False)
            and locals().get("narrative_topic")
        ):
            try:
                from engine.topic_queue import mark_topic_produced
                queue_path = PROJECT_ROOT / config.topic_queue_file
                mark_topic_produced(
                    queue_path,
                    topic_id=narrative_topic.get("id", ""),
                    episode_num=episode_num,
                    produced_date=today.isoformat(),
                )
            except Exception as exc:  # noqa: BLE001
                logger.warning(
                    "Failed to mark topic as produced (non-fatal): %s", exc,
                )

        # Post-generation hook (e.g. extract trade picks for Modern Investing tracker)
        if hook_module and hasattr(hook_module, "post_generate"):
            try:
                hook_module.post_generate(config, digest_text=x_thread, episode_num=episode_num)
            except Exception as exc:
                logger.warning("Post-generate hook failed for %s: %s", args.show, exc)

        # Write episode to Content Lake (non-fatal — must never block pipeline)
        _lake_record = None
        try:
            from engine.content_lake import store_episode, EpisodeRecord, extract_entities_and_topics

            _et = extract_entities_and_topics(x_thread, args.show)
            _lang = "ru" if args.show in ("finansy_prosto", "privet_russian") else "en"
            _headlines = [a.get("title", "") for a in articles if a.get("title")]
            _source_urls = [a.get("url", "") for a in articles if a.get("url")]
            _lake_record = EpisodeRecord(
                show_slug=args.show,
                episode_num=episode_num,
                date=today.isoformat(),
                title=hook or f"Episode {episode_num}",
                hook=hook or "",
                digest_md=x_thread,
                podcast_script="",  # Updated after script generation
                summary=x_thread[:500] if x_thread else "",
                headlines=_headlines,
                source_urls=_source_urls,
                entities=_et["entities"],
                topics=_et["topics"],
                word_count=len(x_thread.split()) if x_thread else 0,
                show_name=config.name,
                language=_lang,
            )
            store_episode(_lake_record)
        except Exception as exc:
            logger.warning("Content lake write failed (non-fatal): %s", exc)

        if args.test:
            logger.info("[TEST MODE] Digest generated successfully. Stopping here.")
            print("\n" + "=" * 60)
            if hook:
                print(f"HOOK: {hook}")
                print("-" * 60)
            print(x_thread[:2000])
            if len(x_thread) > 2000:
                print(f"\n... ({len(x_thread)} chars total, truncated)")
            print("=" * 60)
            save_usage(tracker, digests_dir)
            return

        # 8. Generate podcast script (if not skipped)
        final_mp3 = None
        audio_duration = 0.0

        if not args.skip_podcast:
            from engine.generator import generate_podcast_script

            # Strip URLs, emojis, unicode decorations, and other metadata from
            # the digest before feeding it to the podcast script prompt.  The LLM
            # sometimes echoes these through to the script, and TTS reads them
            # aloud.  This is defense-in-depth alongside the prompt instructions.
            clean_digest = _clean_digest_for_podcast(x_thread)

            # Strip exact cross-episode duplicates from the digest so they don't
            # make it into the podcast script.  _exact_dups is populated by
            # validate_digest when a headline matches a recent episode at 100%.
            if _val_factory and _exact_dups:
                for dup_headline in _exact_dups:
                    if dup_headline in clean_digest:
                        # Remove the paragraph containing the duplicate headline
                        import re as _re
                        # Try to remove the full bold-headline block
                        _dup_escaped = _re.escape(dup_headline)
                        _pattern = _re.compile(
                            r'\n[^\n]*\*\*' + _dup_escaped + r'\*\*[^\n]*(?:\n(?![#\n━*])[^\n]*)*',
                            _re.IGNORECASE,
                        )
                        clean_digest_new = _pattern.sub('', clean_digest)
                        if clean_digest_new != clean_digest:
                            logger.info(
                                "Stripped 100%% duplicate headline from podcast digest: '%s'",
                                dup_headline[:60],
                            )
                            clean_digest = clean_digest_new

            if hook:
                effective_hook = hook
            elif getattr(config, "narrative_mode", False):
                # Narrative-mode shows shouldn't fall back to a news framing.
                # The hook is the topic title (or show name) so the LLM has
                # something concrete to anchor the opening to. Logged as a
                # warning so the operator can investigate why digest hook
                # extraction returned empty for a topic-queue-driven show.
                _topic = locals().get("narrative_topic") or {}
                effective_hook = (_topic.get("title") if isinstance(_topic, dict)
                                  else "") or config.name
                logger.warning(
                    "Narrative-mode show %s has no extractable hook — using "
                    "topic title (%r) as the {hook} fallback. Investigate the "
                    "digest output if this happens repeatedly.",
                    config.slug, effective_hook,
                )
            else:
                effective_hook = (
                    f"Here's what's making news in the {config.name} world today."
                )

            pod_vars = {
                "episode_num": episode_num,
                "today_str": today_str,
                "date_human": today_str,  # alias used by Omni View prompts
                "digest": clean_digest,
                "hook": effective_hook,
            }
            # Merge extra context for podcast prompt (e.g. tone_hint, intro_line)
            pod_vars.update(extra_context)

            # Provide default intro_line/closing_block if hook didn't supply them.
            # Uses engine.intros for day-varying, show-specific intros so
            # listeners don't hear the exact same opening every day.
            # Episode 1 gets a special intro — the podcast prompt templates handle
            # the detailed first-episode introduction based on {episode_num}.
            from engine.intros import build_intro_line, build_closing_block, get_show_host
            host = getattr(config.publishing, "host_name", None) or get_show_host(args.show)
            # Pick the YouTube channel handle so the closing line can mention
            # the right channel. Empty string means "don't mention YouTube"
            # (e.g. shows where YouTube publishing isn't enabled yet).
            _yt_handle = ""
            if getattr(config, "youtube", None) and config.youtube.enabled:
                _yt_handle = (
                    "@NerraRU" if config.youtube.channel == "ru" else "@NerraNetwork"
                )
            if episode_num == 1:
                pod_vars.setdefault(
                    "intro_line",
                    f"{host}: Welcome to the very first episode of {config.name}! "
                    f"Today is {today_str}. {effective_hook}",
                )
                _ep1_close = (
                    f"{host}: That wraps up our very first episode of {config.name}! "
                    f"If you enjoyed this, please subscribe on Apple Podcasts, Spotify, "
                    f"or wherever you listen — and a rating or review really helps new "
                    f"listeners find us. "
                    f"I'm {host} in Vancouver. Thanks for joining me on this journey, "
                    f"and I'll see you tomorrow for episode two."
                )
                if _yt_handle:
                    _ep1_close += (
                        f" And if you'd rather watch than listen, find us on YouTube "
                        f"at {_yt_handle} — link's in the show notes."
                    )
                pod_vars.setdefault("closing_block", _ep1_close)
            else:
                pod_vars.setdefault(
                    "intro_line",
                    build_intro_line(
                        args.show,
                        episode_num=episode_num,
                        today_str=today_str,
                        date=today,
                        extra_context=extra_context,
                    ),
                )
                pod_vars.setdefault(
                    "closing_block",
                    build_closing_block(
                        args.show,
                        episode_num=episode_num,
                        today_str=today_str,
                        date=today,
                        extra_context=extra_context,
                        youtube_channel_handle=_yt_handle,
                    ),
                )
            pod_vars.setdefault("tone_hint", "natural and conversational")

            t0 = time.monotonic()
            logger.info("Generating podcast script ...")
            try:
                podcast_script = generate_podcast_script(pod_vars, config, tracker=tracker)
            except LLMRefusalError as e:
                logger.error("PIPELINE ABORTED at podcast script stage: %s", e)
                save_usage(tracker, digests_dir)
                sys.exit(1)
            logger.info("Podcast script generation took %.1fs", time.monotonic() - t0)

            # 8b. Podcast script length check — two-tier gate.
            #     Hard floor (true garbage): abort only when clearly broken.
            #     Soft floor (below target): warn but continue — a shorter fresh
            #     episode is better than no episode.
            _TARGET_WORDS = getattr(config.llm, "min_podcast_words", 1000) or 1000
            # Hard floor is the larger of (a) the per-show absolute
            # floor and (b) 40% of the target word count. Per-show
            # absolute floor defaults to 600 (the network-wide tuning
            # for the news-show shape). Specialist shows with a
            # thinner content surface (env_intel) override it lower
            # so a narrow-news-day episode at ~500 words ships
            # instead of being treated as broken output.
            _FLOOR_FIELD = getattr(config.llm, "min_podcast_word_floor", 600) or 600
            _HARD_FLOOR = max(_FLOOR_FIELD, int(_TARGET_WORDS * 0.4))
            _script_word_count = len(podcast_script.split())
            if _script_word_count < _HARD_FLOOR:
                logger.error(
                    "Podcast script is clearly broken (%d words, hard floor %d) — "
                    "aborting episode.",
                    _script_word_count, _HARD_FLOOR,
                )
                save_usage(tracker, digests_dir)
                sys.exit(1)
            elif _script_word_count < _TARGET_WORDS:
                logger.warning(
                    "Podcast script below target (%d words, target %d) — "
                    "continuing with shorter episode (fresh > long).",
                    _script_word_count, _TARGET_WORDS,
                )
                metrics.record("script_below_target", True)
            # Always log the raw word count + target so post-hoc audits can
            # validate calibration without grepping workflow logs. The May
            # 2026 Phase-3 recalibration was hard to validate post-merge
            # because only the boolean was preserved; the raw counts now
            # let us compute the actual/target ratio over time.
            metrics.record("podcast_script_word_count", _script_word_count)
            metrics.record("podcast_script_target_words", _TARGET_WORDS)

            # 8c. Pre-TTS duration estimate — skip obviously doomed episodes before
            #     burning TTS credits.  ~150 words/minute for podcast speech.
            #     Use a 70% margin to avoid false positives (the audio gate at
            #     step 10 remains the final authority).
            _min_audio = config.min_audio_duration
            if _min_audio:
                _estimated_duration = _script_word_count / 150.0 * 60.0
                if _estimated_duration < _min_audio * 0.7:
                    logger.error(
                        "Script too short for minimum duration: ~%.0fs estimated "
                        "vs %ds minimum (%d words at ~150 wpm). Aborting before TTS.",
                        _estimated_duration, _min_audio, _script_word_count,
                    )
                    save_usage(tracker, digests_dir)
                    sys.exit(1)

            # Update Content Lake with podcast script (non-fatal)
            if _lake_record is not None:
                try:
                    from engine.content_lake import store_episode as _store_ep
                    _lake_record.podcast_script = podcast_script
                    _store_ep(_lake_record)
                except Exception as exc:
                    logger.warning("Content lake script update failed (non-fatal): %s", exc)

            # Clean podcast script: strip speaker prefixes and stage directions
            podcast_script = _clean_podcast_script(podcast_script, host_name=host)

            # Apply pronunciation fixes
            podcast_script = _apply_pronunciation(podcast_script, args.show)

            # Post-pronunciation cleanup: strip metadata that survived in word form
            # (e.g. "(Word count: two thousand four hundred seventy-eight)" after
            # number-to-words conversion made it invisible to earlier regex passes)
            podcast_script = _strip_post_pronunciation_artifacts(podcast_script)

            # Russian-show date Russification — operator caught (Финансы
            # Просто Ep32, May 6 2026) the LLM emitting English-form dates
            # like "May sixth, twenty twenty-six" inside otherwise-Russian
            # sentences. Grok TTS reads the English literally with the
            # Russian voice, which sounds awful. Helper is idempotent and
            # narrowly targeted so it's safe to run on every Russian script.
            if args.show in ("finansy_prosto", "privet_russian"):
                from engine.russian_text import russify_english_dates
                podcast_script = russify_english_dates(podcast_script)

            # Append AI disclosure at the end of the episode
            podcast_script = podcast_script.rstrip() + "\n\n" + _AI_DISCLOSURE

            # Parse chapter markers from the cleaned script (before TTS)
            from engine.chapters import parse_chapters
            episode_chapters = parse_chapters(
                podcast_script,
                config.chapters.section_markers,
                show_name=config.name,
            ) if config.chapters.enabled and config.chapters.section_markers else []

            # Final defense-in-depth: strip any speaker prefixes that survived
            # all prior cleaning passes.  This catches edge cases where the LLM
            # output format, retry expansion, or paragraph breaking unexpectedly
            # places a prefix at a line/sentence start.
            import re as _re
            for _pfx in ("Host:", f"{host}:", "Patrick:", "Ведущая:", "Ведущий:", "Narrator:", "Speaker:"):
                _esc = _re.escape(_pfx)
                podcast_script = _re.sub(r"^" + _esc + r"\s*", "", podcast_script, flags=_re.MULTILINE)
                podcast_script = _re.sub(r"(?<=[.!?])\s+" + _esc + r"\s*", " ", podcast_script)
            podcast_script = _re.sub(r"\n{3,}", "\n\n", podcast_script).strip()

            # Save TTS-ready script for debugging pronunciation/intro issues
            from engine.utils import strip_lone_surrogates as _scrub
            tts_script_path = digests_dir / f"{config.episode.prefix}_Ep{episode_num:03d}_{today:%Y%m%d}_tts.txt"
            tts_script_path.write_text(_scrub(podcast_script), encoding="utf-8")
            logger.info("TTS script saved: %s", tts_script_path)

            # 9. TTS — provider-aware (ElevenLabs default; Grok for Russian shows)
            tts_provider = (config.tts.provider or "elevenlabs").lower()
            tts_ready = False
            if tts_provider == "grok":
                api_key = (
                    os.getenv("GROK_API_KEY") or os.getenv("XAI_API_KEY") or ""
                ).strip()
                if not api_key:
                    logger.error("GROK_API_KEY (or XAI_API_KEY) not set. Skipping TTS.")
                else:
                    from engine.tts import synthesize  # noqa: F401 (import below)
                    # No fail-fast auth ping for Grok TTS — the same key drives
                    # the LLM stage which has already validated upstream. A bad
                    # key would have failed the digest run before we reached TTS.
                    tts_ready = True
            else:
                api_key = (os.getenv("ELEVENLABS_API_KEY") or "").strip()
                if not api_key:
                    logger.error("ELEVENLABS_API_KEY not set. Skipping TTS.")
                else:
                    from engine.tts import synthesize, validate_elevenlabs_auth
                    validate_elevenlabs_auth(api_key)
                    tts_ready = True

            if tts_ready:
                raw_mp3 = digests_dir / f"{config.episode.prefix}_Ep{episode_num:03d}_{today:%Y%m%d}_raw.mp3"
                logger.info("Synthesizing audio ...")
                t0 = time.monotonic()

                # Section-aware TTS: split at chapter boundaries and
                # concatenate with transition stings between sections.
                sting_path = None
                if config.audio.transition_sting:
                    sting_path = PROJECT_ROOT / config.audio.transition_sting

                # ``config.tts.use_section_tts`` is the network-wide opt-in.
                # As of May 13 2026 the default is False — episodes are
                # synthesised as a single Grok TTS call so the network-wide
                # ``<fast>...</fast>`` wrap from ``_defaults.yaml`` is
                # applied exactly once per episode (no chunk/section
                # boundaries that could leak the tag aloud). See landmine
                # #17 + the TTSConfig docstring.
                use_section_tts = (
                    getattr(config.tts, "use_section_tts", True)
                    and episode_chapters
                    and len(episode_chapters) >= 2
                    and sting_path
                )

                if use_section_tts:
                    from engine.chapters import split_script_at_chapters
                    from engine.audio import generate_transition_sting, concatenate_with_stings

                    sections = split_script_at_chapters(podcast_script, episode_chapters)
                    sections = [s for s in sections if s.strip()]

                    # Safety: if sections capture < 80% of the script, something
                    # went wrong with splitting — fall back to single synthesis.
                    sections_total = sum(len(s) for s in sections)
                    if sections_total < len(podcast_script) * 0.8:
                        logger.warning(
                            "Section TTS: sections only contain %d/%d chars (%.0f%%) — "
                            "falling back to single synthesis to avoid truncation",
                            sections_total, len(podcast_script),
                            100 * sections_total / len(podcast_script) if podcast_script else 0,
                        )
                        metrics.record("section_tts_fallback", True)
                        metrics.record("section_tts_coverage_pct", round(
                            100 * sections_total / len(podcast_script), 1,
                        ) if podcast_script else 0)
                        sections = []  # Force fallback to single synthesis below

                    if len(sections) >= 2:
                        logger.info("Section TTS: synthesizing %d sections separately", len(sections))
                        metrics.record("section_tts_fallback", False)
                        metrics.record("section_tts_section_count", len(sections))
                        section_tmp_dir = digests_dir / f"_sections_ep{episode_num:03d}"

                        from engine.tts import synthesize_sections
                        section_files = synthesize_sections(
                            sections,
                            config.tts.voice_id,
                            section_tmp_dir,
                            api_key=api_key,
                            provider=tts_provider,
                            section_prefix=f"sec_ep{episode_num:03d}",
                            max_chars=config.tts.max_chars,
                            model_id=config.tts.model,
                            stability=config.tts.stability,
                            similarity_boost=config.tts.similarity_boost,
                            style=config.tts.style,
                            language_code=config.tts.language_code,
                            speed=config.tts.speed,
                            apply_text_normalization=config.tts.apply_text_normalization,
                            speech_wrap_open=config.tts.speech_wrap_open,
                            speech_wrap_close=config.tts.speech_wrap_close,
                        )

                        generate_transition_sting(sting_path)
                        concatenate_with_stings(
                            section_files, raw_mp3, sting_path=sting_path,
                        )

                        for sf in section_files:
                            try:
                                sf.unlink()
                            except Exception as exc:
                                logger.debug("Failed to clean up temp file %s: %s", sf, exc)
                        try:
                            section_tmp_dir.rmdir()
                        except Exception as exc:
                            logger.debug("Failed to remove temp dir %s: %s", section_tmp_dir, exc)
                    else:
                        # Not enough sections — fall back to single synthesis
                        synthesize(
                            podcast_script, config.tts.voice_id, raw_mp3,
                            api_key=api_key, provider=tts_provider,
                            max_chars=config.tts.max_chars,
                            model_id=config.tts.model, stability=config.tts.stability,
                            similarity_boost=config.tts.similarity_boost,
                            style=config.tts.style,
                            language_code=config.tts.language_code,
                            speed=config.tts.speed,
                            apply_text_normalization=config.tts.apply_text_normalization,
                            speech_wrap_open=config.tts.speech_wrap_open,
                            speech_wrap_close=config.tts.speech_wrap_close,
                        )
                else:
                    synthesize(
                        podcast_script, config.tts.voice_id, raw_mp3,
                        api_key=api_key, provider=tts_provider,
                        max_chars=config.tts.max_chars,
                        model_id=config.tts.model, stability=config.tts.stability,
                        similarity_boost=config.tts.similarity_boost,
                        style=config.tts.style,
                        language_code=config.tts.language_code,
                        speed=config.tts.speed,
                        apply_text_normalization=config.tts.apply_text_normalization,
                        speech_wrap_open=config.tts.speech_wrap_open,
                        speech_wrap_close=config.tts.speech_wrap_close,
                    )

                _tts_duration = time.monotonic() - t0
                logger.info("TTS synthesis took %.1fs", _tts_duration)
                metrics.record("tts_duration_s", round(_tts_duration, 2))
                from engine.tracking import record_tts_usage
                record_tts_usage(tracker, len(podcast_script), provider=config.tts.provider)

                # 9a. Generate transcript from raw TTS audio (non-fatal).
                # Runs FIRST so the Whisper output can also feed the
                # post-TTS validation step below without a second
                # transcribe pass. Before May 12 2026 these two stages
                # each loaded Whisper independently and re-transcribed
                # the same audio — operator-caught during the pipeline
                # audit.
                _transcript_result = None
                try:
                    from engine.transcripts import generate_transcript
                    _lang = "ru" if args.show in ("finansy_prosto", "privet_russian") else "en"
                    _ep_prefix = f"{config.episode.prefix}_Ep{episode_num:03d}_{today:%Y%m%d}"
                    _transcript_result = generate_transcript(
                        raw_mp3, digests_dir, _ep_prefix,
                        model_size=config.tts.whisper_model, language=_lang,
                    )
                except Exception as exc:
                    logger.warning("Transcript generation failed (non-fatal): %s", exc)

                # 9b. Post-TTS transcription validation (opt-in). Reuses the
                # transcript text from 9a when available so Whisper only
                # runs once per episode. Falls back to its own transcribe
                # call if the transcript step couldn't produce text (e.g.
                # faster-whisper missing on the runner).
                if config.tts.validate_transcription:
                    import json as _json
                    from engine.tts_validation import validate_tts_transcription
                    from engine.utils import strip_speech_tags
                    logger.info("Running post-TTS transcription validation...")
                    # Whisper transcribes audio (no tag literals come back), so
                    # we compare against the tag-stripped script — otherwise the
                    # match score is artificially lowered by every [breath] /
                    # <emphasis>...</emphasis> in the reference text.
                    tts_val = validate_tts_transcription(
                        raw_mp3, strip_speech_tags(podcast_script),
                        model_size=config.tts.whisper_model,
                        threshold=config.tts.whisper_threshold,
                        transcription=(
                            _transcript_result.text if _transcript_result else None
                        ),
                    )
                    if tts_val["passed"]:
                        logger.info("TTS validation PASSED (%.1f%% match)", tts_val["match_score"] * 100)
                    else:
                        logger.warning(
                            "TTS validation WARNING: %.1f%% match (threshold %.0f%%)",
                            tts_val["match_score"] * 100,
                            config.tts.whisper_threshold * 100,
                        )
                        for w in tts_val["mismatched_words"][:10]:
                            logger.warning("  Mismatch: expected '%s' → heard '%s'", w["expected"], w["heard"])
                    val_path = digests_dir / f"{config.episode.prefix}_Ep{episode_num:03d}_{today:%Y%m%d}_tts_validation.json"
                    val_path.write_text(_json.dumps(tts_val, indent=2))
                    logger.info("TTS validation report saved: %s", val_path.name)

                # 9c. Tag-leak regression detector — scan the Whisper
                # transcript for tag-as-text bleeds (the May 2026
                # ``<build-intensity>`` regression cost a full network
                # day before being caught by ear). Best-effort: log
                # warning + record metric; never blocks the pipeline.
                # Will flip to hard-block once false-positive rate is
                # calibrated (see audit plan Phase 1.6).
                try:
                    from engine.tag_leak_detector import (
                        scan_transcript, summarize_leaks,
                    )
                    _ep_prefix_t = (
                        f"{config.episode.prefix}_Ep{episode_num:03d}_"
                        f"{today:%Y%m%d}"
                    )
                    _transcript_txt = digests_dir / f"{_ep_prefix_t}_transcript.txt"
                    _leaks = scan_transcript(_transcript_txt)
                    metrics.record("tag_leaks", len(_leaks))
                    if _leaks:
                        logger.warning(
                            "Tag-leak detector flagged %d suspect line(s) in "
                            "%s — %s",
                            len(_leaks),
                            _transcript_txt.name,
                            summarize_leaks(_leaks),
                        )
                        # Record per-pattern counts so the dashboard can
                        # show which leak families are still recurring.
                        _by_pattern: dict = {}
                        for _leak in _leaks:
                            _by_pattern[_leak.pattern_name] = (
                                _by_pattern.get(_leak.pattern_name, 0) + 1
                            )
                        metrics.record("tag_leaks_by_pattern", _by_pattern)
                    else:
                        logger.info("Tag-leak detector: clean transcript.")

                    # Quick-win hard block (May 2026 review): if the show has opted in
                    # via tts.tag_leak_hard_block (default False in _defaults), any
                    # detected spoken tag aborts the episode here (before expensive
                    # audio mix + publish). This is the calibrated "flip to hard"
                    # path the original detector comment anticipated.
                    if getattr(config.tts, "tag_leak_hard_block", False) and _leaks:
                        logger.error(
                            "Tag-leak hard block enabled for %s and %d leak(s) found — "
                            "aborting episode to protect listener experience.",
                            config.name, len(_leaks)
                        )
                        sys.exit(1)
                except Exception as exc:
                    logger.debug("Tag-leak detector failed (non-fatal): %s", exc)

                # 10. Audio mixing
                from engine.audio import get_audio_duration, mix_with_music, normalize_voice

                final_mp3 = digests_dir / f"{config.episode.prefix}_Ep{episode_num:03d}_{today:%Y%m%d}.mp3"

                t0 = time.monotonic()
                if config.audio.music_file:
                    music_path = PROJECT_ROOT / config.audio.music_file
                    if music_path.exists():
                        logger.info("Mixing with music: %s", music_path.name)

                        # Resolve optional background/outro music file
                        bg_music_path = None
                        if config.audio.background_music_file:
                            bg_music_path = PROJECT_ROOT / config.audio.background_music_file

                        mix_with_music(
                            raw_mp3, music_path, final_mp3,
                            intro_duration=int(config.audio.intro_duration),
                            overlap_duration=int(config.audio.overlap_duration),
                            fade_duration=int(config.audio.fade_duration),
                            outro_duration=int(config.audio.outro_duration),
                            intro_volume=config.audio.intro_volume,
                            overlap_volume=config.audio.overlap_volume,
                            fade_volume=config.audio.fade_volume,
                            outro_volume=config.audio.outro_volume,
                            voice_intro_delay=config.audio.voice_intro_delay,
                            background_music_path=bg_music_path,
                            outro_crossfade=config.audio.outro_crossfade,
                            outro_fade_out_duration=getattr(
                                config.audio, "outro_fade_out_duration", 6.0,
                            ),
                        )
                    else:
                        logger.warning("Music file not found: %s — using voice only", music_path)
                        normalize_voice(raw_mp3, final_mp3)
                else:
                    normalize_voice(raw_mp3, final_mp3)

                _mix_duration = time.monotonic() - t0
                logger.info("Audio mixing took %.1fs", _mix_duration)
                metrics.record("audio_mix_duration_s", round(_mix_duration, 2))
                audio_duration = get_audio_duration(final_mp3) or 0.0
                logger.info("Final audio: %s (%.0fs)", final_mp3.name, audio_duration)

                # 10-gate. Skip episode if audio is too short to be a quality episode.
                _min_audio = config.min_audio_duration
                if _min_audio and audio_duration < _min_audio:
                    logger.error(
                        "Audio too short (%.0fs < %ds minimum) — skipping episode.",
                        audio_duration, _min_audio,
                    )
                    final_mp3.unlink(missing_ok=True)
                    _skip_episode(
                        "audio_too_short",
                        f"Audio too short ({audio_duration:.0f}s < {_min_audio}s minimum).",
                    )

                # 10a. Generate chapter data (timestamps + JSON)
                if episode_chapters and audio_duration > 0:
                    from engine.chapters import calculate_timestamps, write_chapters_json

                    # Music intro offset = time before voice starts
                    music_intro_offset = config.audio.voice_intro_delay + config.audio.intro_duration
                    calculate_timestamps(
                        episode_chapters,
                        audio_duration,
                        music_intro_offset=music_intro_offset,
                    )

                    ep_title = f"Ep {episode_num}: {hook}" if hook else f"{config.name} - Episode {episode_num}"
                    chapters_json_path = digests_dir / f"chapters_ep{episode_num:03d}.json"
                    write_chapters_json(
                        episode_chapters,
                        chapters_json_path,
                        episode_title=ep_title,
                    )

                # NOTE: raw MP3 cleanup is deferred until after post-validation
                # passes, so we have recovery if the mix is corrupt (see #20).

    # 10b. Upload to R2 (if configured)
    r2_audio_url = None
    if final_mp3 and final_mp3.exists():
        from engine.storage import upload_episode
        r2_audio_url = upload_episode(final_mp3, config)
        if r2_audio_url:
            logger.info("R2 audio URL: %s", r2_audio_url)
        elif config.storage.provider == "r2":
            logger.error(
                "R2 upload FAILED for '%s' Ep%d — storage.provider is 'r2' "
                "but upload_episode() returned None. Aborting to prevent "
                "publishing an RSS feed that points at a ghost MP3 URL.",
                config.name, episode_num,
            )
            sys.exit(3)

    # 10c. Apply OP3 analytics prefix (if enabled)
    rss_audio_url = r2_audio_url
    if config.analytics.enabled and rss_audio_url:
        from engine.publisher import apply_op3_prefix
        rss_audio_url = apply_op3_prefix(rss_audio_url, config.analytics.prefix_url)
        logger.info("OP3 prefixed URL: %s", rss_audio_url)

    # 10d. Build & upload YouTube videos (long-form + Shorts) BEFORE the
    # RSS / blog / X stages, so the YouTube URL can land in the
    # episode description, blog post, and X teaser.
    _t_yt = time.monotonic()
    chapters_path_for_yt = digests_dir / f"chapters_ep{episode_num:03d}.json"
    youtube_urls = _publish_youtube(
        config,
        episode_num=episode_num,
        today=today,
        today_str=today_str,
        hook=hook or "",
        digest_text=x_thread,
        final_mp3=final_mp3,
        audio_url=r2_audio_url or "",
        chapters_path=chapters_path_for_yt,
        digests_dir=digests_dir,
        args=args,
    )
    youtube_long_url = youtube_urls.get("long_url", "")
    youtube_short_url = youtube_urls.get("short_url", "")
    youtube_pexels_filtered = int(youtube_urls.get("pexels_photos_filtered", 0) or 0)
    if youtube_long_url:
        extra_context["youtube_url"] = youtube_long_url
    if youtube_short_url:
        extra_context["youtube_short_url"] = youtube_short_url
    # Record YouTube publishing outcomes so the dashboard can graph
    # upload success rate per show. We always record these (even on
    # skip/fail) so the dashboard sees zeros instead of missing data.
    try:
        metrics.record(
            "youtube_publish_duration_s",
            round(time.monotonic() - _t_yt, 2),
        )
        metrics.record("youtube_long_form_uploaded", bool(youtube_long_url))
        metrics.record("youtube_short_uploaded", bool(youtube_short_url))
        metrics.record(
            "youtube_enabled",
            bool(getattr(config.youtube, "enabled", False)),
        )
        # Surface upload failure reasons in metrics.json so the operator
        # can diagnose without grepping GitHub Action logs. Most likely
        # culprit when uploads silently fail is YouTube Data API
        # quota exhaustion (10,000 units/day, 1,600 per upload =
        # ~6 uploads/day per channel; the @NerraNetwork channel has
        # 8 English shows × 2 videos = 16 uploads which exceeds quota).
        if youtube_urls.get("long_error"):
            metrics.record("youtube_long_error", youtube_urls["long_error"])
        if youtube_urls.get("short_error"):
            metrics.record("youtube_short_error", youtube_urls["short_error"])
        metrics.record("pexels_photos_filtered", youtube_pexels_filtered)
        # Grok Imagine cost tracking (May 2026). Always recorded so the
        # dashboard can plot $0 for pexels-only runs and the actual
        # spend for grok / hybrid runs.
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

        # Medium item: Record actual quota units consumed this episode for
        # better live visibility (instead of only static estimates).
        try:
            from engine.youtube_quota import estimate_episode_units

            yt_cfg = getattr(config, "youtube", None) or {}
            q = estimate_episode_units(
                publish_long_form=bool(youtube_long_url),
                publish_shorts=bool(youtube_short_url),
                with_thumbnail=True,
                with_playlist=True,
                with_caption_track=bool(youtube_long_url),  # captions only on long form today
            )
            metrics.record("youtube_quota_units_this_episode", q.units)
            metrics.record("youtube_uploads_this_episode", q.uploads)
        except Exception as exc:
            logger.debug("Could not record YouTube quota metrics: %s", exc)
        # Gallery upload outcome (Phase 1 → diagnostics added May 2026).
        # Always recorded so the operator can read the metrics file
        # for the latest episode and tell at a glance whether the
        # gallery R2 bucket is receiving uploads.
        metrics.record(
            "gallery_attempted",
            int(youtube_urls.get("gallery_attempted", 0) or 0),
        )
        metrics.record(
            "gallery_uploaded",
            int(youtube_urls.get("gallery_uploaded", 0) or 0),
        )
        # Smart Shorts segment selection (May 2026): record the chosen
        # offset and which mode resolved to it so the dashboard can
        # surface smart-vs-fallback rate per show.
        if "shorts_start_offset" in youtube_urls:
            metrics.record(
                "shorts_start_offset",
                float(youtube_urls["shorts_start_offset"]),
            )
        if "shorts_start_mode_resolved" in youtube_urls:
            metrics.record(
                "shorts_start_mode_resolved",
                str(youtube_urls["shorts_start_mode_resolved"]),
            )
        # Multi-Shorts counters (May 2026). Single-Short runs still
        # report ``requested=1, uploaded=0/1`` so the dashboard can
        # compute the fallback rate across the network without
        # special-casing the legacy path.
        if "shorts_count_requested" in youtube_urls:
            metrics.record(
                "shorts_count_requested",
                int(youtube_urls.get("shorts_count_requested", 1) or 1),
            )
        if "shorts_count_uploaded" in youtube_urls:
            metrics.record(
                "shorts_count_uploaded",
                int(youtube_urls.get("shorts_count_uploaded", 0) or 0),
            )
        if youtube_urls.get("gallery_skipped_reason"):
            metrics.record(
                "gallery_skipped_reason",
                str(youtube_urls["gallery_skipped_reason"]),
            )
        # Surface the first 5 Grok Imagine failure messages when the
        # provider is grok / hybrid AND the run produced 0 images. Tells
        # the operator WHY the slideshow fell back to the cover (bad
        # API key, model identifier, request format, rate limit, etc.)
        # instead of having to dig through GitHub Actions logs.
        if youtube_urls.get("grok_image_failures"):
            metrics.record(
                "grok_image_failures",
                youtube_urls["grok_image_failures"],
            )
    except Exception:
        pass

    # 11. Update RSS feed
    _t_rss = time.monotonic()
    if final_mp3 and final_mp3.exists():
        from engine.publisher import update_rss_feed
        from engine.audio import format_duration

        if hook:
            episode_title = f"Ep {episode_num}: {hook}"
        else:
            episode_title = f"{config.name} - Episode {episode_num} - {today_str}"
        # Use a short summary for the RSS description (first ~500 chars at sentence boundary)
        # to avoid overwhelming podcast app UIs with the full digest.
        _desc_limit = 500
        if len(x_thread) > _desc_limit:
            _cut = x_thread[:_desc_limit].rfind(". ")
            episode_desc = x_thread[:_cut + 1] + " ..." if _cut > 100 else x_thread[:_desc_limit] + "..."
        else:
            episode_desc = x_thread
        episode_desc = episode_desc.rstrip() + "\n\n" + _AI_DISCLOSURE_RSS
        # If the episode landed on YouTube, surface the watch link in
        # the RSS description so listeners on every podcast app can
        # click through to the video version.
        if youtube_long_url:
            episode_desc += f"\n\n🎬 Watch on YouTube: {youtube_long_url}"

        # If no R2 URL but analytics is enabled, build URL and prefix it
        feed_audio_url = rss_audio_url
        if not feed_audio_url and config.analytics.enabled:
            from engine.publisher import apply_op3_prefix
            raw_url = f"{config.publishing.base_url}/{config.publishing.audio_subdir}/{final_mp3.name}"
            feed_audio_url = apply_op3_prefix(raw_url, config.analytics.prefix_url)
            logger.info("OP3 prefixed URL: %s", feed_audio_url)

        # Build chapters URL for RSS if chapter JSON was written
        chapters_url = None
        chapters_json_ep = digests_dir / f"chapters_ep{episode_num:03d}.json"
        if chapters_json_ep.exists():
            chapters_url = (
                f"{config.publishing.base_url}/{config.publishing.audio_subdir}"
                f"/chapters_ep{episode_num:03d}.json"
            )

        # Build transcript URL for RSS if transcript JSON was written
        transcript_url = None
        _ep_prefix = f"{config.episode.prefix}_Ep{episode_num:03d}_{today:%Y%m%d}"
        transcript_json = digests_dir / f"{_ep_prefix}_transcript.json"
        if transcript_json.exists():
            transcript_url = (
                f"{config.publishing.base_url}/{config.publishing.audio_subdir}"
                f"/{_ep_prefix}_transcript.json"
            )

        # Channel description shape (May 2026 audit): Apple Podcasts /
        # Spotify list pages truncate around 150 characters, so the
        # FIRST sentence has to sell the show. Putting the AI disclosure
        # ahead of (or inline with) the show pitch ate the entire
        # truncation window. Now: show pitch first, AI disclosure
        # appended in parentheses at the end. Apple's full-detail page
        # still shows everything; the listing-card preview shows the
        # punchy line.
        channel_desc_with_disclosure = (
            config.publishing.rss_description.rstrip()
            + "\n\n"
            + _AI_DISCLOSURE_RSS
        )

        logger.info("Updating RSS feed: %s", config.publishing.rss_file)
        update_rss_feed(
            rss_path=rss_path,
            episode_num=episode_num,
            episode_title=episode_title,
            episode_description=episode_desc,
            episode_date=today,
            mp3_filename=final_mp3.name,
            mp3_duration=audio_duration,
            mp3_path=final_mp3,
            base_url=config.publishing.base_url,
            audio_subdir=config.publishing.audio_subdir,
            channel_title=config.publishing.rss_title,
            channel_link=config.publishing.rss_link,
            channel_description=channel_desc_with_disclosure,
            channel_language=config.publishing.rss_language,
            channel_author=config.publishing.rss_author,
            channel_email=config.publishing.rss_email,
            channel_image=config.publishing.rss_image,
            channel_category=config.publishing.rss_category,
            channel_subcategory=getattr(config.publishing, "rss_subcategory", ""),
            channel_keywords=getattr(config.publishing, "rss_keywords", ""),
            guid_prefix=config.publishing.guid_prefix,
            format_duration_func=format_duration,
            audio_url=feed_audio_url,  # Use R2/OP3-prefixed URL if available
            chapters_url=chapters_url,
            transcript_url=transcript_url,
        )

        metrics.record("rss_update_duration_s", round(time.monotonic() - _t_rss, 2))

        # 11b. Notify podcast directories (best-effort, non-blocking).
        # CI no longer duplicates this ping after commit (May 2026 audit).
        from engine.publisher import notify_directories
        rss_url = f"{config.publishing.base_url}/{config.publishing.rss_file}"
        notify_directories(rss_url, show_name=config.publishing.rss_title)

    # 12. Save GitHub Pages summary
    from engine.publisher import save_summary_to_github_pages

    summaries_json = PROJECT_ROOT / config.publishing.summaries_json
    audio_url = r2_audio_url  # Prefer R2 URL
    if not audio_url and final_mp3 and final_mp3.exists():
        audio_url = (
            f"{config.publishing.base_url}/{config.publishing.audio_subdir}/{final_mp3.name}"
        )

    save_summary_to_github_pages(
        summary_text=x_thread,
        summaries_json_path=summaries_json,
        podcast_name=config.publishing.summaries_podcast_name or config.slug,
        episode_num=episode_num,
        episode_title=f"Ep {episode_num}: {hook}" if hook else f"{config.name} - Episode {episode_num} - {today_str}",
        audio_url=audio_url,
        rss_url=f"{config.publishing.base_url}/{config.publishing.rss_file}",
    )

    # 12a. Generate blog post
    try:
        from engine.blog import extract_blog_metadata, generate_blog_post_html
        from generate_html import generate_blog_index, _get_jinja_env, NETWORK_SHOWS as _NS

        if config.slug in _NS:
            _blog_env = _get_jinja_env()
            _blog_meta = extract_blog_metadata(x_thread, config.slug, digest_md.name if digest_md else "", file_path=digest_md)
            _blog_meta["episode_num"] = episode_num
            _blog_html = generate_blog_post_html(
                x_thread, _blog_meta, _NS[config.slug], _blog_env,
                youtube_url=youtube_long_url,
                youtube_short_url=youtube_short_url,
            )
            _blog_dir = PROJECT_ROOT / "blog" / config.slug
            _blog_dir.mkdir(parents=True, exist_ok=True)
            _blog_path = _blog_dir / f"ep{episode_num:03d}.html"
            from engine.utils import strip_lone_surrogates as _scrub
            _blog_path.write_text(_scrub(_blog_html), encoding="utf-8")
            logger.info("Blog post written: %s", _blog_path)

            # Regenerate blog index (per-show + network)
            generate_blog_index(config.slug)
            logger.info("Blog index regenerated for %s", config.slug)

            from generate_html import generate_network_blog_index as _gen_net_blog
            _gen_net_blog()
            logger.info("Network blog index regenerated")

            from engine.blog import regenerate_blog_rss_for_show_slug
            _rss_blog = regenerate_blog_rss_for_show_slug(config.slug, PROJECT_ROOT)
            if _rss_blog:
                logger.info("Blog RSS regenerated: %s", _rss_blog.name)
        else:
            logger.debug("Show %s not in NETWORK_SHOWS, skipping blog generation", config.slug)
    except Exception as exc:
        logger.warning("Blog post generation failed (non-fatal): %s", exc)

    # 12a-pre. Post-run validation (before newsletter/X so bad episodes
    # don't email subscribers or tweet without audio).
    from engine.post_run_validation import run_post_validation
    validation_passed = run_post_validation(
        mp3_path=final_mp3,
        rss_path=rss_path,
        digest_text=x_thread,
        show_name=config.name,
        episode_num=episode_num,
    )
    if not validation_passed:
        logger.error("Post-run validation FAILED — exiting with error code")
        save_usage(tracker, digests_dir)
        sys.exit(1)

    episode_published = bool(final_mp3 and final_mp3.exists())

    # 12b. Send newsletter
    if (
        episode_published
        and config.newsletter.enabled
        and not args.skip_newsletter
    ):
        from engine.newsletter import send_show_newsletter

        try:
            email_id = send_show_newsletter(
                x_thread, config, episode_num, today_str, hook=hook,
            )
        except Exception as exc:  # pragma: no cover — defensive
            email_id = None
            logger.exception("Newsletter send raised: %s", exc)

        # Record the send outcome in metrics.json so the operator can
        # spot a pipeline-wide silent-failure (e.g. May 2026 audit
        # caught all three of OV / Modern Investing / Privet Russian
        # being scaffold-blocked for weeks without a metric to flag
        # it). ``newsletter_email_id`` is None on every blocked path;
        # the bool counter is the easier-to-grep daily signal.
        metrics.record("newsletter_sent", bool(email_id))
        if email_id:
            metrics.record("newsletter_email_id", email_id)

        if email_id:
            logger.info("Newsletter sent: %s", email_id)
        else:
            # send_show_newsletter returns None for several distinct
            # reasons (api key missing, contrast hard-block, scaffold
            # leak, same-day double-send guard, Buttondown rejection,
            # tag filter matched zero subscribers). engine.newsletter
            # logs the SPECIFIC reason at ERROR/WARNING level just
            # above — pointing the operator there is more accurate
            # than guessing here. Operator caught (TST Ep465, May 6
            # 2026) the prior speculative ``tag filter matched zero
            # subscribers OR Buttondown rejected the send`` warning
            # being printed when the actual block was a contrast
            # hard-block, which is plainly logged on the preceding
            # line.
            api_key_env = getattr(
                config.newsletter, "api_key_env", "BUTTONDOWN_API_KEY",
            )
            if not os.getenv(api_key_env, "").strip():
                logger.warning(
                    "Newsletter not sent: %s env var is empty. "
                    "Add the secret in GitHub Actions to enable "
                    "newsletters.", api_key_env,
                )
            else:
                logger.warning(
                    "Newsletter not sent — see the preceding "
                    "engine.newsletter log line for the specific "
                    "reason (contrast block, scaffold leak, send "
                    "guardrail, or Buttondown response).",
                )

    # 13. Post to X
    _t_x = time.monotonic()
    if episode_published and config.publishing.x_enabled and not args.skip_x:
        from engine.publisher import post_to_x
        from engine.tracking import record_x_post

        prefix = config.publishing.x_env_prefix
        consumer_key = os.getenv(f"{prefix}CONSUMER_KEY", "")
        consumer_secret = os.getenv(f"{prefix}CONSUMER_SECRET", "")
        access_token = os.getenv(f"{prefix}ACCESS_TOKEN", "")
        access_token_secret = os.getenv(f"{prefix}ACCESS_TOKEN_SECRET", "")

        if all([consumer_key, consumer_secret, access_token, access_token_secret]):
            teaser = _build_teaser(config, episode_num, today_str, extra_context)
            tweet_url = post_to_x(
                teaser,
                consumer_key=consumer_key,
                consumer_secret=consumer_secret,
                access_token=access_token,
                access_token_secret=access_token_secret,
            )
            if tweet_url:
                record_x_post(tracker)
                logger.info("Posted to X: %s", tweet_url)
        else:
            logger.warning("X credentials missing (prefix=%s). Skipping X post.", prefix)

    if config.publishing.x_enabled:
        metrics.record("x_post_duration_s", round(time.monotonic() - _t_x, 2))

    # 14b. Cleanup raw audio now that validation has passed
    if not args.skip_podcast and final_mp3 and final_mp3.exists():
        raw_mp3_cleanup = digests_dir / f"{config.episode.prefix}_Ep{episode_num:03d}_{today:%Y%m%d}_raw.mp3"
        if raw_mp3_cleanup.exists() and raw_mp3_cleanup != final_mp3:
            raw_mp3_cleanup.unlink(missing_ok=True)
            logger.info("Cleaned up raw audio: %s", raw_mp3_cleanup.name)

    # 15. Save tracking & metrics
    save_usage(tracker, digests_dir)
    try:
        metrics.record("digest_chars", len(x_thread) if x_thread else 0)
        metrics.record("audio_duration_s", audio_duration)
        metrics.save(digests_dir)
        logger.info("Pipeline summary: %s", metrics.summary())
    except Exception as exc:
        logger.warning("Metrics save failed (non-fatal): %s", exc)

    _digest_marker_md = digests_dir / (
        f"{config.episode.prefix}_Ep{episode_num:03d}_{today:%Y%m%d}.md"
    )
    if episode_published or _digest_marker_md.exists():
        write_publish_complete_marker(
            publish_marker,
            show_slug=config.slug,
            episode_num=episode_num,
            date_iso=today.isoformat(),
        )

    logger.info("=== %s complete ===", config.name)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _fetch_with_expansion(
    feed_dicts: list[dict],
    keywords: list[str] | None,
    content_tracker,
    min_articles: int = 3,
    config=None,
) -> list[dict]:
    """Fetch articles with progressive search expansion on slow news days.

    Tries increasingly wider search windows (24h → 48h → 72h) and relaxed
    dedup thresholds until at least *min_articles* survive, or all expansion
    stages are exhausted.  This prevents shows like Env Intel from producing
    empty episodes on days when RSS feeds are sparse.

    Even when the article count technically meets *min_articles*, if fewer
    than 30% of configured feeds produced any articles we treat it as a
    content-thin day and continue expanding to gather more material for the
    LLM to work with.
    """
    from engine.fetcher import fetch_rss_articles
    from engine.utils import deduplicate_by_entity

    total_feeds = len(feed_dicts)
    # Minimum fraction of feeds that should contribute content.  If fewer
    # feeds produce articles, we keep expanding even if count >= min_articles.
    _MIN_FEED_HIT_RATIO = 0.30

    expansion_stages = [
        # (cutoff_hours, similarity_threshold, keyword_filter)
        (24, 0.65, True),    # Normal: last 24h, strict dedup, keywords on
        (48, 0.65, True),    # Expand window to 48h
        (72, 0.55, True),    # Expand to 72h, relax dedup
        (72, 0.55, False),   # Drop keyword filter entirely (broader catch)
    ]

    best_articles: list[dict] = []

    for stage_idx, (cutoff_hours, sim_threshold, use_keywords) in enumerate(expansion_stages):
        kw = keywords if use_keywords else None
        articles = fetch_rss_articles(
            feed_dicts, cutoff_hours=cutoff_hours, keywords=kw,
        )
        logger.info(
            "Fetch (cutoff=%dh, keywords=%s): %d articles",
            cutoff_hours, "on" if use_keywords else "off", len(articles),
        )

        articles = deduplicate_by_entity(articles, max_per_entity=2)
        # Reduce dedup lookback for young shows (< 10 episodes) to avoid
        # over-filtering when the content tracker has very few episodes.
        ep_count = len(content_tracker.data.get("episodes", []))
        _cf = getattr(config, "content_freshness", None)
        lookback_days = (_cf and _cf.lookback_days) or (1 if ep_count < 10 else 3)
        _cf_sim = (_cf and _cf.similarity_threshold) or sim_threshold
        articles = content_tracker.filter_recent_articles(
            articles, similarity_threshold=_cf_sim, days=lookback_days,
        )
        logger.info(
            "After dedup (sim=%.2f): %d articles remain",
            sim_threshold, len(articles),
        )

        # Keep the best result seen so far (most articles)
        if len(articles) > len(best_articles):
            best_articles = articles

        if len(articles) >= min_articles:
            # Check feed diversity — if most feeds returned nothing,
            # we likely have thin content even if count looks okay.
            if total_feeds >= 5 and stage_idx < len(expansion_stages) - 1:
                contributing_feeds = len({
                    a.get("source_name", a.get("feed_url", ""))
                    for a in articles
                })
                feed_hit_ratio = contributing_feeds / total_feeds
                if feed_hit_ratio < _MIN_FEED_HIT_RATIO:
                    logger.warning(
                        "Content-thin day: %d articles from only %d/%d feeds "
                        "(%.0f%% < %.0f%% threshold) — expanding search for "
                        "more material ...",
                        len(articles), contributing_feeds, total_feeds,
                        feed_hit_ratio * 100, _MIN_FEED_HIT_RATIO * 100,
                    )
                    continue
            return articles

        logger.info(
            "Only %d articles (need %d) — expanding search...",
            len(articles), min_articles,
        )

    # Return the best result we found across all stages
    return best_articles


def _extract_segment_summaries(
    digest_text: str, segments: list,
) -> dict:
    """Extract 1-2 sentence angle summaries for each evergreen segment.

    Searches the digest for each segment's title heading and captures the
    first couple of sentences as an angle summary.  This is stored in the
    content tracker so future slow-news prompts can enforce freshness.
    """
    import re

    summaries: dict = {}
    for seg in segments:
        title = seg.get("title", "")
        if not title:
            continue
        # Look for the segment title (possibly surrounded by markdown)
        pattern = re.escape(title)
        match = re.search(
            rf"(?:^|\n)(?:\*{{0,2}}|#+\s*).*{pattern}.*(?:\n|$)(.*?)(?:\n\n|\n#|\n\*\*|\Z)",
            digest_text,
            re.IGNORECASE | re.DOTALL,
        )
        if match:
            text = match.group(1).strip()
            # Take first 1-2 sentences (up to ~200 chars)
            sentences = re.split(r"(?<=[.!?])\s+", text)
            summary = " ".join(sentences[:2])[:200]
            if summary:
                summaries[seg["id"]] = summary
    return summaries


def _extract_hook(digest: str) -> str | None:
    """Extract the **HOOK:** line from a generated digest.

    The digest prompts instruct the LLM to include a line like:
        **HOOK:** Scientists just discovered a new way to...

    Falls back to the first top-of-digest blockquote (``> **<text>**``)
    that appears before any ``###`` section heading. Narrative shows
    (Unintended Consequences) occasionally drop the ``**HOOK:**`` label
    and emit the hook as a leading blockquote instead; without this
    fallback every UC episode after Ep 4 shipped with a generic
    "Episode N — Month DD, YYYY" title in podcast apps.

    Returns the hook text (without the prefix) or *None* if not found.
    """
    import re

    for line in digest.splitlines():
        m = re.match(r"^\s*\*{0,2}HOOK:?\*{0,2}\s*(.+)", line, re.IGNORECASE)
        if m:
            hook = m.group(1).strip()
            # Strip leftover markdown/brackets the LLM sometimes wraps
            hook = re.sub(r"^\[|\]$", "", hook).strip()
            if hook:
                return hook

    # Fallback: leading blockquote before the first ### heading.
    # Matches `> **<text>**` on its own line. Only the first one wins;
    # blockquotes that appear AFTER a section heading are scene-setting
    # narration, not the title.
    for line in digest.splitlines():
        if line.lstrip().startswith("###"):
            break
        m = re.match(r"^\s*>\s*\*{1,3}([^*]{10,300})\*{1,3}\s*$", line)
        if m:
            hook = m.group(1).strip()
            if hook:
                return hook
    return None

def _clean_digest_for_podcast(digest: str) -> str:
    """Strip metadata from a digest before it is fed to the podcast script prompt.

    Removes URLs, emoji, unicode box-drawing characters, ``Source:`` lines,
    markdown formatting, and raw timestamps so the LLM is less likely to echo
    them into the spoken script.  The *content* (titles, summaries, quotes)
    is preserved.
    """
    import re

    lines: list[str] = []
    for line in digest.splitlines():
        # Drop lines that are just separators (━━━, ----, ====, etc.)
        if re.match(r"^[\s━─═\-=]{4,}$", line):
            continue
        # Drop standalone source attribution lines
        if re.match(r"^\s*(Source|Post|Read more)\s*:", line, re.IGNORECASE):
            continue
        # Drop the HOOK line (already extracted; don't echo into podcast script)
        if re.match(r"^\s*\*{0,2}HOOK:?\*{0,2}\s+", line, re.IGNORECASE):
            continue
        # Strip inline URLs  (keeps surrounding text)
        line = re.sub(r"https?://\S+", "", line)
        # Strip markdown link syntax  [text](url) -> text
        line = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", line)
        # Strip markdown bold/italic markers
        line = re.sub(r"\*{1,3}([^*]+)\*{1,3}", r"\1", line)
        # Strip markdown header markers
        line = re.sub(r"^#{1,6}\s+", "", line)
        # Strip emoji and common unicode symbols (broad range)
        line = re.sub(
            r"[\U0001F300-\U0001FAFF\u2600-\u27BF\u2B50\u2B55"
            r"\u25B2\u25BC\u2580-\u259F\u2500-\u257F"
            r"\U0001F900-\U0001F9FF]+",
            "",
            line,
        )
        # Collapse leftover whitespace
        line = re.sub(r"  +", " ", line).strip()
        lines.append(line)

    return "\n".join(lines)


def _clean_podcast_script(script: str, host_name: str = "Patrick") -> str:
    """Strip speaker prefixes (Host:, <host_name>:) and stage directions from podcast script.

    This produces clean text suitable for TTS synthesis.
    """
    import re

    host_prefix = f"{host_name}:"
    # Common speaker/stage-direction prefixes that LLMs generate.
    # These must be stripped so TTS doesn't try to voice them.
    _SPEAKER_PREFIXES = [
        "Host:",
        host_prefix,
        # Russian (Финансы Просто)
        "Ведущая:",
        "Ведущий:",
        # Latin transliterations of Cyrillic host names
        "Olya:",
        "Olga:",
        # Generic
        "Narrator:",
        "Speaker:",
    ]
    parts: list[str] = []
    for line in script.splitlines():
        line = line.strip()
        # Skip stage directions, blank lines, and bracketed notes
        if not line or line.startswith("["):
            continue
        # Skip footer/debug metadata Grok sometimes appends (numeric or word form)
        if re.match(r"(?i)^\(?\s*(word\s*count|total\s*words|character\s*count)\b", line):
            continue
        if re.match(r"(?i)^\(?\s*(approximately\s+)?\d[\d,]*\s+words?\s*\)?$", line):
            continue
        # Skip leaked timing/length targets that the LLM echoes from prompt
        # e.g. "This is a twelve minute podcast", "Target: ninety seconds of audio",
        # "two thousand eight hundred words", "sixty to ninety seconds"
        if re.search(
            r"(?i)\b(word count|script length|target[:\s]+\d|"
            r"\d+\s*[-–]\s*\d+\s*(minute|second|word)|"
            r"producing a \d+|"
            r"at least \d[\d,]*\s*words|"
            r"(thirty|forty|fifty|sixty|seventy|eighty|ninety|hundred|thousand)\s+"
            r"(words?|sentences?)\b)",
            line,
        ):
            continue
        if re.match(r"(?i)^content\s*:\s*$", line):
            break
        # Skip title/episode header lines the LLM occasionally generates
        # before the actual script (e.g. "Tesla Shorts Time Daily – Episode 412 – March 19, 2026"
        # or with word-form numbers after pronunciation: "Episode four hundred twelve")
        if re.match(
            r"(?i)^.{3,50}\s*[-–—,]\s*episode\s+.{1,40}\s*[-–—,]\s*"
            r"(?:January|February|March|April|May|June|July|August|September|October|November|December)\b",
            line,
        ):
            continue
        # Also catch simpler variants: "Show Name, Episode N" at end of line
        # (with optional trailing metadata like "Script (Expanded – X words)")
        if re.match(
            r"(?i)^.{3,50},?\s+episode\s+[\w\s]+[,.]?\s*"
            r"(?:script\b.*)?$",
            line,
        ):
            continue
        # Catch title lines with "(Expanded – X words)" or similar metadata suffix
        if re.search(r"(?i)\b(expanded|rewritten|revised)\s*[-–—]\s*.*\bwords?\b", line):
            continue
        # Drop markdown artifacts
        if line in {"**", "*", "__", "—", "–"}:
            continue
        # Drop leaked prompt instruction lines the LLM may echo
        if re.match(r"(?i)^(RULES|NEVER INCLUDE|CONTENT FOCUS|TONE|SCRIPT STRUCTURE|HOST:)\b", line):
            continue
        if re.match(r"(?i)^(Use this exact|Deliver this hook|Narrate EVERY|Here is today)", line):
            continue
        # Drop LLM preambles from retry/expansion responses
        if re.match(r"(?i)^(here(?:\s*'?s?|\s+is)\s+(your|the|my)\s+(expanded|rewritten|revised|updated)|I'?ve\s+(expanded|rewritten))", line):
            continue
        # Drop source attribution lines that survived earlier cleaning
        if re.match(r"(?i)^\s*source\s*:", line):
            continue
        # Strip speaker prefixes (plain and bold markdown variants)
        text = line
        for prefix in _SPEAKER_PREFIXES:
            if line.startswith(prefix):
                text = line[len(prefix):].strip()
                break
            # Also catch **Host:** bold markdown variants
            bold = f"**{prefix[:-1]}:**"  # e.g. "Host:" → "**Host:**"
            if line.startswith(bold):
                text = line[len(bold):].strip()
                break
        if text:
            parts.append(text)

    joined = "\n\n".join(parts).strip()

    # Defense-in-depth: break wall-of-text paragraphs at sentence boundaries.
    # Grok-4 intermittently produces single mega-paragraphs (500+ chars) per
    # topic instead of natural 1-2 sentence paragraphs.  TTS reads these
    # without pauses, which sounds unnatural.  Split long paragraphs into
    # ~2 sentence chunks so TTS inserts natural breathing pauses.
    joined = _break_long_paragraphs(joined)

    # Second pass: strip any speaker prefixes — both at line/paragraph starts
    # (exposed by _break_long_paragraphs) and mid-sentence (when the LLM puts
    # multiple Host: segments on a single line).
    for prefix in _SPEAKER_PREFIXES:
        escaped = re.escape(prefix)
        # At line/paragraph starts
        joined = re.sub(r"^" + escaped + r"\s*", "", joined, flags=re.MULTILINE)
        # Mid-sentence: "sentence. Host: Next" → "sentence. Next"
        joined = re.sub(r"(?<=[.!?])\s+" + escaped + r"\s*", " ", joined)
    # Collapse blank lines that prefix removal may have created
    joined = re.sub(r"\n{3,}", "\n\n", joined).strip()

    return joined


def _strip_post_pronunciation_artifacts(text: str) -> str:
    """Strip metadata lines that survived pronunciation conversion.

    After ``_apply_pronunciation`` converts numbers to words, lines like
    ``(Word count: 2,478)`` become ``(Word count: two thousand four hundred
    seventy-eight)`` which earlier regex passes couldn't match.  This final
    pass catches them in word form.
    """
    import re
    lines = text.split("\n")
    cleaned = []
    for line in lines:
        stripped = line.strip()
        # Word count in any form (numeric or word)
        if re.match(r"(?i)^\(?\s*(word\s*count|total\s*words|character\s*count)\b", stripped):
            continue
        # "Target: X words" metadata (may have mangled numbers after pronunciation)
        if re.search(r"(?i)\btarget\s*:\s*.*\bwords?\b", stripped):
            continue
        # "approximately X min spoken" metadata
        if re.search(r"(?i)\bapproximately\s+.*\bmin(utes?)?\s+(spoken|audio|reading)\b", stripped):
            continue
        cleaned.append(line)
    return "\n".join(cleaned)


# Sentence-end pattern: period/!/?  followed by two+ spaces or a space before
# a capital letter (catches "sentence. Next sentence" even with single space).
_SENTENCE_SPLIT_RE = None


def _break_long_paragraphs(text: str, max_chars: int = 400) -> str:
    """Split paragraphs longer than *max_chars* at sentence boundaries.

    Keeps paragraphs at roughly 1-3 sentences so TTS produces natural pauses.
    """
    import re

    global _SENTENCE_SPLIT_RE
    if _SENTENCE_SPLIT_RE is None:
        # Split after sentence-ending punctuation followed by a space and
        # uppercase letter (the start of the next sentence).
        _SENTENCE_SPLIT_RE = re.compile(
            r'(?<=[.!?])\s+(?=[A-Z\u0400-\u04FF])'
        )

    out_paragraphs: list[str] = []
    for para in text.split("\n\n"):
        if len(para) <= max_chars:
            out_paragraphs.append(para)
            continue
        # Split into individual sentences
        sentences = _SENTENCE_SPLIT_RE.split(para)
        chunk: list[str] = []
        chunk_len = 0
        for sent in sentences:
            if chunk and chunk_len + len(sent) > max_chars:
                out_paragraphs.append(" ".join(chunk))
                chunk = []
                chunk_len = 0
            chunk.append(sent)
            chunk_len += len(sent) + 1  # +1 for joining space
        if chunk:
            out_paragraphs.append(" ".join(chunk))

    return "\n\n".join(out_paragraphs)


def _publish_youtube(
    config,
    *,
    episode_num: int,
    today: "datetime.date",
    today_str: str,
    hook: str,
    digest_text: str,
    final_mp3: "Path",
    audio_url: str,
    chapters_path: "Path",
    digests_dir: "Path",
    args,
) -> dict:
    """Render long-form + Shorts video assets and upload them to YouTube.

    Returns a ``{"long_url": ..., "short_url": ...}`` dict with whichever
    URLs succeeded; missing keys mean that variant was disabled or
    failed (failures are logged, not raised — this stage must never
    crash a run).
    """
    result: dict = {}

    if getattr(args, "skip_youtube", False):
        logger.info("YouTube publishing skipped (--skip-youtube).")
        return result
    if not getattr(config, "youtube", None) or not config.youtube.enabled:
        logger.info("YouTube publishing disabled in config.")
        return result
    if not final_mp3 or not final_mp3.exists():
        logger.info("YouTube publishing skipped — no final mp3.")
        return result

    # Resolve cover image. We fall back to whatever the show used in the
    # RSS <itunes:image> tag if a local file isn't obvious from the slug.
    cover_path = None
    cover_candidates = [
        PROJECT_ROOT / "assets" / "covers" / f"{config.slug.replace('_', '-')}.jpg",
        PROJECT_ROOT / "assets" / "covers" / f"{config.slug}.jpg",
    ]
    for candidate in cover_candidates:
        if candidate.exists():
            cover_path = candidate
            break
    if cover_path is None:
        logger.warning(
            "YouTube: no cover art under assets/covers/ for slug=%s — skipping.",
            config.slug,
        )
        return result

    from engine.captions import (
        find_transcript_for_episode,
        transcript_to_ass_window,
        transcript_to_srt,
        transcript_to_srt_window,
    )
    from engine.publisher import (
        generate_episode_thumbnail,
        generate_shorts_end_card,
        generate_shorts_thumbnail,
    )
    from engine.video import build_long_form_video, build_short_video
    from engine.youtube_shorts import (
        resolve_shorts_start_offset,
        should_upload_shorts_today,
    )
    from engine.video_metadata import (
        build_long_form_metadata,
        build_short_metadata,
    )
    from engine.visual_assets import fetch_scene_images
    from engine.youtube import (
        add_video_to_playlist,
        get_channel_credentials_from_env,
        upload_video,
    )

    credentials = get_channel_credentials_from_env(config.youtube.channel)
    if credentials is None:
        logger.warning(
            "YouTube credentials missing for channel=%s — skipping upload.",
            config.youtube.channel,
        )
        return result

    work_dir = digests_dir / "youtube_tmp"
    work_dir.mkdir(parents=True, exist_ok=True)
    base_name = final_mp3.stem  # e.g. Tesla_Shorts_Time_Pod_Ep042_20260425
    long_video_path = work_dir / f"{base_name}.mp4"
    short_video_path = work_dir / f"{base_name}_short.mp4"
    thumbnail_path = work_dir / f"{base_name}_thumb.jpg"
    short_thumbnail_path = work_dir / f"{base_name}_short_thumb.jpg"
    show_label = config.publishing.rss_title or config.name

    try:
        generate_episode_thumbnail(
            cover_path,
            episode_num=episode_num,
            date_str=today_str,
            output_path=thumbnail_path,
            hook=hook,
            show_name=show_label,
        )
    except Exception as exc:  # pragma: no cover - thumbnail rendering best-effort
        logger.warning("Long-form thumbnail generation failed: %s", exc)
        thumbnail_path = None  # type: ignore[assignment]

    # ---- Build captions SRT (optional — falls back to no captions) ----
    srt_path = None
    transcript_path = find_transcript_for_episode(
        digests_dir, config.episode.prefix, episode_num, f"{today:%Y%m%d}",
    )
    if transcript_path is not None:
        try:
            srt_candidate = work_dir / f"{base_name}.srt"
            # Whisper transcribes the voice-only raw MP3 (music
            # confuses the segment timestamps), but the long-form
            # video uses the final MP3 that prepends
            # ``voice_intro_delay`` seconds of music. Offset the SRT
            # by exactly that delay so the burned-in captions land
            # on the speech instead of the music intro. See the
            # captions.transcript_to_srt docstring for context.
            _caption_offset = float(
                getattr(config.audio, "voice_intro_delay", 0.0) or 0.0
            )
            transcript_to_srt(
                transcript_path,
                srt_candidate,
                audio_offset_seconds=_caption_offset,
            )
            srt_path = srt_candidate
        except Exception as exc:  # pragma: no cover — best-effort
            logger.warning("Caption generation failed: %s", exc)

    # ---- Resolve scene slideshow ----
    # ``image_provider`` selects between three paths (May 2026 rollout):
    #   pexels  — free Pexels search; same set used for long-form + Shorts
    #   grok    — Grok Imagine generates two distinct sets per episode
    #             (long-form 16:9 + Shorts 9:16) prompted from the hook
    #   hybrid  — Pexels for long-form, Grok for Shorts only
    yt = config.youtube
    image_provider = (getattr(yt, "image_provider", "pexels") or "pexels").lower()

    long_scene_paths = [cover_path]
    short_scene_paths = [cover_path]
    pexels_attribution: list = []
    pexels_filtered = 0
    grok_image_cost = 0.0
    grok_images_generated = 0
    grok_image_failures: list = []
    # Gallery upload counters (Phase 1 → diagnostics added May 2026).
    # Surfaced in per-episode metrics so we can tell from the dashboard
    # whether the gallery R2 bucket is actually receiving uploads or
    # silently no-op'ing on a misconfigured environment.
    gallery_uploaded = 0
    gallery_attempted = 0
    gallery_skipped_reason = ""

    def _run_pexels_path(into_long: bool, into_short: bool):
        nonlocal pexels_attribution, pexels_filtered
        try:
            scene_set = fetch_scene_images(
                work_dir=work_dir,
                episode_num=episode_num,
                keywords=list(getattr(config, "keywords", []) or []),
                fallback_cover=cover_path,
                image_queries=list(getattr(yt, "image_queries", []) or []),
                image_query_prefix=getattr(yt, "image_query_prefix", "") or "",
                safe_skip_terms=list(getattr(yt, "image_safe_skip_terms", []) or []),
            )
            if not scene_set.is_fallback and len(scene_set) >= 2:
                if into_long:
                    nonlocal_paths = scene_set.paths()
                    long_scene_paths[:] = nonlocal_paths
                if into_short:
                    short_scene_paths[:] = scene_set.paths()
                pexels_attribution = scene_set.attribution_lines()
            pexels_filtered = int(getattr(scene_set, "photos_filtered", 0) or 0)
        except Exception as exc:  # pragma: no cover — best-effort
            logger.warning("Pexels scene fetch failed: %s", exc)

    # Pull per-story headlines from the digest once, then reuse for both
    # 16:9 and 9:16 prompt builds. Operator caught (Tesla long-form +
    # Shorts, May 7 2026) every Grok slide rendering the same headline
    # because every prompt previously embedded the lone episode hook.
    # Per-scene headlines = visually diverse slideshow.
    try:
        from engine.grok_imagine import extract_story_headlines as _extract_headlines
        _scene_contexts = _extract_headlines(digest_text or "", max_count=12)
    except Exception:  # pragma: no cover — best-effort
        _scene_contexts = []

    def _run_grok_path(*, aspect: str, label_suffix: str) -> "list[Path]":
        from engine.grok_imagine import (
            build_image_prompts,
            fetch_scene_images_grok,
        )
        nonlocal grok_image_cost, grok_images_generated, grok_image_failures
        try:
            prompts = build_image_prompts(
                hook=hook or "",
                image_queries=list(getattr(yt, "image_queries", []) or []),
                aspect=aspect,
                # 4 prompts per aspect × 2 aspects (16:9 + 9:16) = 8
                # distinct images per episode. Down from 8 per aspect
                # (16 total) — May 12 2026 retune. Each scene now
                # holds ~2 minutes on long-form (vs ~75 s previously),
                # which is fine for podcast-style YouTube where the
                # imagery is decorative B-roll under voice. Halves
                # the Grok Imagine spend on YouTube-enabled shows
                # (Tesla + MAB). Compliance is unaffected — the
                # ``containsSyntheticMedia`` flag is binary.
                count=4,
                show_descriptor=getattr(
                    yt, "grok_image_descriptor", "photorealistic news photo",
                ),
                per_scene_contexts=_scene_contexts,
            )
            result = fetch_scene_images_grok(
                work_dir=work_dir,
                episode_num=episode_num,
                prompts=prompts,
                fallback_cover=cover_path,
                aspect=aspect,
                label_suffix=label_suffix,
                model=getattr(yt, "grok_image_model", "grok-imagine-image"),
            )
            grok_image_cost += result.cost_usd
            grok_images_generated += result.images_generated
            grok_image_failures.extend(result.failures)
            if not result.scene_set.is_fallback and len(result.scene_set) >= 2:
                # Grok-generated images are royalty-free under xAI's
                # terms; we still credit the model in the description
                # so listeners know it's AI-generated imagery.
                pexels_attribution.append(
                    "Imagery generated by Grok Imagine (xAI)."
                )
                _upload_scenes_to_gallery(
                    scene_paths=result.scene_set.paths(),
                    prompts=prompts,
                    aspect=aspect,
                )
                return result.scene_set.paths()
        except Exception as exc:  # pragma: no cover — best-effort
            logger.warning("Grok Imagine scene fetch failed: %s", exc)
        return [cover_path]

    def _upload_scenes_to_gallery(
        *, scene_paths: "list[Path]", prompts: "list[str]", aspect: str,
    ) -> None:
        """Post-step: register each generated scene in the gallery R2 bucket.

        Strictly additive — failure here is logged and swallowed so the
        YouTube publish path is never blocked. Skipped silently when
        gallery R2 env vars (``R2_GALLERY_BUCKET`` etc.) are unset.
        Scene filenames follow ``grok_NN.jpeg`` from
        ``fetch_scene_images_grok``; the ``NN`` is the prompt index, so
        we can pair each image back with its source prompt without
        plumbing extra state.

        Always emits a single summary log line (even on 0 uploads) and
        bumps ``gallery_uploaded`` / ``gallery_attempted`` /
        ``gallery_skipped_reason`` so the per-episode metrics file
        shows the gallery outcome at a glance.
        """
        nonlocal gallery_uploaded, gallery_attempted, gallery_skipped_reason
        try:
            from engine.gallery_uploader import (
                ImageMetadata,
                gallery_config_from_env,
                upload_image,
            )
        except Exception as exc:  # pragma: no cover — import-time soft-fail
            gallery_skipped_reason = f"import_error:{type(exc).__name__}"
            logger.warning("Gallery uploader import failed: %s", exc)
            return

        gconfig = gallery_config_from_env()
        if not gconfig.is_configured:
            gallery_skipped_reason = "unconfigured"
            logger.info(
                "Gallery: skipping upload for ep%s (aspect=%s) — "
                "R2 env vars unset (bucket=%r endpoint=%r access=%s secret=%s)",
                episode_num, aspect,
                gconfig.bucket, gconfig.endpoint_url,
                bool(gconfig.access_key), bool(gconfig.secret_key),
            )
            return

        import re as _re
        intended_use = (
            "social" if (aspect.startswith("9:") or aspect == "vertical") else "segment_card"
        )
        episode_id = f"ep{episode_num:03d}"
        episode_date = today.strftime("%Y-%m-%d")
        episode_title = (
            f"Ep {episode_num}: {hook}".strip(": ") if hook else f"Ep {episode_num}"
        )
        model_id = getattr(yt, "grok_image_model", "grok-imagine-image")

        attempted = 0
        uploaded = 0
        first_failure = ""
        for scene_path in scene_paths:
            attempted += 1
            try:
                image_bytes = Path(scene_path).read_bytes()
            except Exception as exc:  # pragma: no cover — best-effort
                if not first_failure:
                    first_failure = f"read:{type(exc).__name__}:{exc}"
                logger.warning(
                    "Gallery: failed to read %s: %s", scene_path, exc,
                )
                continue

            match = _re.match(r"grok_(\d+)\.", Path(scene_path).name)
            prompt_text = ""
            if match:
                idx = int(match.group(1))
                if 0 <= idx < len(prompts):
                    prompt_text = prompts[idx]

            metadata = ImageMetadata(
                image_id="",  # filled in by upload_image (content hash)
                show_slug=config.slug,
                show_name=config.name,
                episode_id=episode_id,
                episode_title=episode_title,
                episode_date=episode_date,
                prompt=prompt_text,
                model=model_id,
                intended_use=intended_use,
                tags=[config.slug, intended_use, "grok-imagine"],
            )
            result_upload = upload_image(
                image_bytes, metadata, gallery_config=gconfig,
            )
            if result_upload is not None:
                uploaded += 1
            elif not first_failure:
                # upload_image() returns None on any soft failure
                # (R2 error, thumbnail error, missing creds). The
                # specific cause was logged inside the helper; we
                # capture the fact here so the per-episode metrics
                # show a non-empty skipped_reason when uploads silently
                # 0-out (the most operationally hostile failure mode).
                first_failure = "upload_returned_none"

        gallery_attempted += attempted
        gallery_uploaded += uploaded
        if uploaded == 0 and attempted > 0 and not gallery_skipped_reason:
            gallery_skipped_reason = first_failure or "unknown_failure"

        logger.info(
            "Gallery: ep%s aspect=%s attempted=%d uploaded=%d bucket=%s "
            "first_failure=%r",
            episode_num, aspect, attempted, uploaded, gconfig.bucket,
            first_failure or None,
        )

    if image_provider == "grok":
        long_scene_paths = _run_grok_path(aspect="16:9", label_suffix="")
        short_scene_paths = _run_grok_path(aspect="9:16", label_suffix="_short")
    elif image_provider == "hybrid":
        _run_pexels_path(into_long=True, into_short=False)
        short_scene_paths = _run_grok_path(aspect="9:16", label_suffix="_short")
    else:  # pexels (default)
        _run_pexels_path(into_long=True, into_short=True)

    # Shorts thumbnail: vertical crop from cover or first vertical scene.
    shorts_thumb_base = cover_path
    if getattr(yt, "shorts_thumbnail_from_scene", True) and len(short_scene_paths) >= 1:
        shorts_thumb_base = short_scene_paths[0]
    try:
        generate_shorts_thumbnail(
            shorts_thumb_base,
            episode_num=episode_num,
            date_str=today_str,
            output_path=short_thumbnail_path,
            hook=hook,
            show_name=show_label,
        )
    except Exception as exc:  # pragma: no cover
        logger.warning("Shorts thumbnail generation failed: %s", exc)
        short_thumbnail_path = thumbnail_path  # fallback to long-form thumb

    from engine.audio import get_audio_duration as _audio_dur
    try:
        _ep_duration = _audio_dur(str(final_mp3)) or 0.0
    except Exception:
        _ep_duration = 0.0

    # ---- Long-form ----
    long_url = ""
    if config.youtube.publish_long_form:
        try:
            build_long_form_video(
                final_mp3, cover_path, long_video_path,
                scene_paths=long_scene_paths if len(long_scene_paths) >= 2 else None,
                subtitles_path=srt_path,
                show_name=config.name,
            )
            meta = build_long_form_metadata(
                config,
                episode_num=episode_num,
                today_str=today_str,
                hook=hook,
                digest_text=digest_text,
                audio_url=audio_url,
                chapters_path=chapters_path if chapters_path.exists() else None,
                photo_attribution=pexels_attribution,
            )
            upload = upload_video(
                long_video_path,
                credentials=credentials,
                title=meta["title"],
                description=meta["description"],
                tags=meta["tags"],
                category_id=meta["category_id"],
                default_language=meta["default_language"],
                privacy_status=config.youtube.privacy_status,
                thumbnail_path=thumbnail_path,
            )
            long_url = upload.watch_url
            result["long_url"] = long_url
            playlist_id = (
                getattr(config.youtube, "podcast_playlist_id", None) or ""
            ).strip()
            if not playlist_id:
                logger.info(
                    "Podcast playlist ID empty — skipping playlist add."
                )
            else:
                add_video_to_playlist(
                    credentials=credentials,
                    video_id=upload.video_id,
                    playlist_id=playlist_id,
                )
            # Upload the SRT as a real caption track. This is on top of
            # the burned-in captions — gives YouTube the CC button +
            # auto-translation + accessibility search. Best-effort:
            # failures are logged and the run continues.
            if srt_path and srt_path.exists():
                from engine.youtube import upload_caption_track
                lang_code = (config.youtube.default_language or "en").lower()
                track_name = "English" if lang_code == "en" else (
                    "Русский" if lang_code == "ru" else lang_code.upper()
                )
                upload_caption_track(
                    credentials=credentials,
                    video_id=upload.video_id,
                    srt_path=srt_path,
                    language=lang_code,
                    name=track_name,
                )
        except Exception as exc:
            logger.exception("YouTube long-form publish failed: %s", exc)
            # Surface the failure reason in the result dict so the
            # outer pipeline can record it in metrics.json. Without
            # this the only signal was ``youtube_long_form_uploaded:
            # false`` and the operator had to dig through GitHub
            # Action logs to find out why. ``HttpError`` from the
            # google API client carries a structured ``status`` /
            # ``reason`` (quotaExceeded / authError / etc.) — capture
            # both that and the generic str fallback.
            err_type = type(exc).__name__
            # 1000 chars (was 300) — YouTube's invalidDescription
            # carries a ``locationType`` and the offending location at
            # the END of the message; the prior cap was truncating
            # exactly that detail when post-mortem debugging.
            err_msg = str(exc)[:1000]
            err_status = getattr(exc, "status_code", None) or getattr(
                getattr(exc, "resp", None), "status", None
            )
            result["long_error"] = {
                "type": err_type,
                "status": err_status,
                "message": err_msg,
            }

    # ---- Shorts ----
    if config.youtube.publish_shorts and should_upload_shorts_today(
        config, episode_num=episode_num,
    ):
        try:
            duration = float(config.youtube.short_duration_seconds or 55.0)

            # Resolve the "shorts plan" — a list of (start_offset, hook)
            # pairs to publish, one per Short. Legacy single-Short
            # behaviour is the len==1 case of this loop; multiple
            # Shorts requires ``shorts_per_episode > 1`` AND
            # ``shorts_start_mode: smart`` so the top-N selector has
            # something to rank.
            shorts_count_yaml = max(
                1, int(getattr(config.youtube, "shorts_per_episode", 1) or 1)
            )
            mode_resolved = (
                "explicit" if getattr(
                    config.youtube, "shorts_start_offset", None,
                ) is not None
                else (
                    getattr(config.youtube, "shorts_start_mode", None)
                    or "voice"
                )
            )
            shorts_plan: "list[tuple[float, str]]" = []
            if shorts_count_yaml > 1 and mode_resolved == "smart":
                try:
                    from engine.shorts_selector import (
                        pick_top_n_engaging_windows,
                    )
                    voice_offset = float(
                        getattr(config.audio, "voice_intro_delay", 0.0) or 0.0
                    )
                    if transcript_path is not None:
                        windows = pick_top_n_engaging_windows(
                            transcript_path,
                            n=shorts_count_yaml,
                            audio_offset=voice_offset,
                            audio_duration=_ep_duration,
                            window_duration=duration,
                            min_start_final=voice_offset,
                        )
                        shorts_plan = [
                            (
                                w.start_seconds,
                                (w.opening_text or hook).strip() or hook,
                            )
                            for w in windows
                        ]
                except Exception as exc:  # pragma: no cover — best-effort
                    logger.warning(
                        "Multi-Shorts top-N selection failed (%s) — "
                        "falling back to single short", exc,
                    )
                    shorts_plan = []

            if not shorts_plan:
                # Single-Short fallback: legacy resolved offset + the
                # episode-level hook. Same code path as before
                # ``shorts_per_episode`` existed.
                fallback_offset = resolve_shorts_start_offset(
                    config,
                    chapters_path if chapters_path.exists() else None,
                    audio_duration=_ep_duration,
                    transcript_path=transcript_path,
                )
                shorts_plan = [(fallback_offset, hook)]

            # Surface the resolved plan on the result dict. Single-
            # Short fields stay for backwards compatibility with the
            # dashboard / metrics consumers; the list-shaped fields
            # are new and only useful when len(plan) > 1.
            result["shorts_start_offset"] = round(shorts_plan[0][0], 2)
            result["shorts_start_offsets"] = [round(o, 2) for o, _ in shorts_plan]
            result["shorts_start_mode_resolved"] = mode_resolved
            result["shorts_count_requested"] = shorts_count_yaml

            # ---- Pre-loop assets shared across every Short ----
            _yt = config.youtube
            _end_card_enabled = bool(
                getattr(_yt, "shorts_end_card_enabled", True)
            )
            _end_card_main = str(
                getattr(_yt, "shorts_end_card_main_text", "WATCH FULL EPISODE")
            )
            _end_card_sub = str(
                getattr(_yt, "shorts_end_card_sub_text", "Tap Subscribe ↗")
            )
            _end_card_dur = float(
                getattr(_yt, "shorts_end_card_duration_seconds", 3.0) or 3.0
            )
            _end_card_image_path = None
            if _end_card_enabled and thumbnail_path and Path(thumbnail_path).exists():
                try:
                    _end_card_image_candidate = work_dir / f"{base_name}_end_card.png"
                    generate_shorts_end_card(
                        thumbnail_path,
                        _end_card_image_candidate,
                        show_name=config.name,
                        main_text=_end_card_main,
                        sub_text=_end_card_sub,
                    )
                    if _end_card_image_candidate.exists():
                        _end_card_image_path = _end_card_image_candidate
                except Exception as exc:  # pragma: no cover — best-effort
                    logger.warning(
                        "Shorts end-card PNG render failed: %s — "
                        "falling back to drawtext-only end card", exc,
                    )

            _caption_offset = float(
                getattr(config.audio, "voice_intro_delay", 0.0) or 0.0
            )

            # ---- Per-Short loop ----
            short_urls_out: "list[str]" = []
            short_video_ids_out: "list[str]" = []
            short_errors_out: "list[dict]" = []
            multi = len(shorts_plan) > 1
            for short_idx, (this_offset, this_hook) in enumerate(shorts_plan):
                # Filename suffix is empty for the single-Short case so
                # the legacy ``{base}_short.mp4`` path stays exactly the
                # same when ``shorts_per_episode == 1``.
                suffix = f"_{short_idx + 1}" if multi else ""
                this_short_video_path = work_dir / f"{base_name}_short{suffix}.mp4"
                this_short_thumb_path = (
                    work_dir / f"{base_name}_short{suffix}_thumb.jpg"
                    if multi else short_thumbnail_path
                )
                try:
                    # Per-Short thumbnail: cycle through the available
                    # scene images so each Short has a visually
                    # distinct preview in YouTube's grid. Falls back
                    # to the long-form cover for any iteration where
                    # the scene path doesn't exist on disk.
                    if multi or getattr(_yt, "shorts_thumbnail_from_scene", True):
                        _thumb_base = cover_path
                        if short_scene_paths:
                            _thumb_base = short_scene_paths[
                                short_idx % len(short_scene_paths)
                            ]
                        try:
                            generate_shorts_thumbnail(
                                _thumb_base,
                                episode_num=episode_num,
                                date_str=today_str,
                                output_path=this_short_thumb_path,
                                hook=this_hook,
                                show_name=show_label,
                            )
                        except Exception as exc:  # pragma: no cover
                            logger.warning(
                                "Shorts thumbnail #%d failed: %s — "
                                "falling back to long-form thumbnail",
                                short_idx + 1, exc,
                            )
                            this_short_thumb_path = thumbnail_path

                    # Per-Short caption (ASS first, SRT fallback) —
                    # same selection logic as the single-Short path.
                    this_srt_path = None
                    if transcript_path is not None:
                        try:
                            ass_candidate = (
                                work_dir / f"{base_name}_short{suffix}.ass"
                            )
                            transcript_to_ass_window(
                                transcript_path,
                                ass_candidate,
                                window_start_seconds=this_offset,
                                window_duration_seconds=duration,
                                audio_offset_seconds=_caption_offset,
                            )
                            has_word_cues = (
                                ass_candidate.exists()
                                and ass_candidate.stat().st_size > 0
                                and "Dialogue:" in ass_candidate.read_text(
                                    encoding="utf-8", errors="replace",
                                )
                            )
                            if has_word_cues:
                                this_srt_path = ass_candidate
                            else:
                                srt_candidate = (
                                    work_dir / f"{base_name}_short{suffix}.srt"
                                )
                                transcript_to_srt_window(
                                    transcript_path,
                                    srt_candidate,
                                    window_start_seconds=this_offset,
                                    window_duration_seconds=duration,
                                    audio_offset_seconds=_caption_offset,
                                )
                                if srt_candidate.exists() and srt_candidate.stat().st_size > 0:
                                    this_srt_path = srt_candidate
                        except Exception as exc:  # pragma: no cover
                            logger.warning(
                                "Shorts caption #%d generation failed: %s",
                                short_idx + 1, exc,
                            )

                    build_short_video(
                        final_mp3, cover_path, this_short_video_path,
                        start_offset=this_offset,
                        duration=duration,
                        hook=this_hook or None,
                        scene_paths=(
                            short_scene_paths
                            if len(short_scene_paths) >= 2 else None
                        ),
                        show_name=config.name,
                        subtitles_path=this_srt_path,
                        end_card=_end_card_enabled,
                        end_card_main_text=_end_card_main,
                        end_card_sub_text=_end_card_sub,
                        end_card_duration=_end_card_dur,
                        end_card_image_path=_end_card_image_path,
                    )
                    meta = build_short_metadata(
                        config,
                        episode_num=episode_num,
                        today_str=today_str,
                        hook=this_hook,
                        long_form_url=long_url,
                    )
                    upload_thumb = (
                        this_short_thumb_path
                        if this_short_thumb_path and Path(this_short_thumb_path).exists()
                        else thumbnail_path
                    )
                    this_upload = upload_video(
                        this_short_video_path,
                        credentials=credentials,
                        title=meta["title"],
                        description=meta["description"],
                        tags=meta["tags"],
                        category_id=meta["category_id"],
                        default_language=meta["default_language"],
                        privacy_status=config.youtube.privacy_status,
                        thumbnail_path=upload_thumb,
                    )
                    short_urls_out.append(this_upload.watch_url)
                    short_video_ids_out.append(this_upload.video_id)
                    playlist_id = (
                        getattr(config.youtube, "podcast_playlist_id", None) or ""
                    ).strip()
                    if not playlist_id:
                        if short_idx == 0:
                            logger.info(
                                "Podcast playlist ID empty — skipping playlist add."
                            )
                    else:
                        try:
                            add_video_to_playlist(
                                credentials=credentials,
                                video_id=this_upload.video_id,
                                playlist_id=playlist_id,
                            )
                        except Exception as exc:  # pragma: no cover
                            logger.warning(
                                "Playlist add failed for short #%d: %s",
                                short_idx + 1, exc,
                            )
                    # Best-effort cleanup of this Short's MP4 now
                    # that YouTube has the canonical copy.
                    try:
                        if this_short_video_path.exists():
                            this_short_video_path.unlink()
                    except OSError:
                        pass
                except Exception as exc:
                    logger.exception(
                        "YouTube Shorts #%d publish failed: %s",
                        short_idx + 1, exc,
                    )
                    err_type = type(exc).__name__
                    err_msg = str(exc)[:1000]
                    err_status = getattr(exc, "status_code", None) or getattr(
                        getattr(exc, "resp", None), "status", None
                    )
                    short_errors_out.append({
                        "idx": short_idx + 1,
                        "type": err_type,
                        "status": err_status,
                        "message": err_msg,
                    })

            # ---- Aggregate results onto ``result`` ----
            if short_urls_out:
                # Backwards-compat fields (legacy consumers expect a
                # single ``short_url`` / ``short_error``). Plural
                # variants are new and present when len > 1.
                result["short_url"] = short_urls_out[0]
                if multi:
                    result["short_urls"] = short_urls_out
                    result["short_video_ids"] = short_video_ids_out
            result["shorts_count_uploaded"] = len(short_urls_out)
            if short_errors_out:
                result["short_error"] = short_errors_out[0]
                if multi:
                    result["short_errors"] = short_errors_out
        except Exception as exc:
            # Outer try / except that catches setup-stage errors
            # (resolve_shorts_start_offset, plan construction) — the
            # per-Short upload loop already catches and aggregates
            # its own errors, so this rarely fires.
            logger.exception("YouTube Shorts publish failed: %s", exc)
            err_type = type(exc).__name__
            err_msg = str(exc)[:1000]
            err_status = getattr(exc, "status_code", None) or getattr(
                getattr(exc, "resp", None), "status", None
            )
            result["short_error"] = {
                "type": err_type,
                "status": err_status,
                "message": err_msg,
            }

    # Best-effort cleanup of the long-form MP4 (large file; YouTube
    # has the canonical copy now). Per-Short MP4s are cleaned up
    # inside the loop above. Thumbnails are kept on disk for
    # debugging.
    try:
        if long_video_path.exists():
            long_video_path.unlink()
    except OSError:
        pass

    # Surface the Pexels safety-filter count so the caller can record
    # it as a metric. A spike here is the operator's signal that the
    # show's image_queries / safe_skip_terms need tightening.
    result["pexels_photos_filtered"] = pexels_filtered
    # Grok Imagine cost-tracking. Recorded as a metric so the
    # management dashboard can surface monthly spend on per-episode
    # image generation. Zero when image_provider != grok / hybrid.
    result["grok_image_cost_usd"] = round(grok_image_cost, 4)
    result["grok_images_generated"] = grok_images_generated
    if grok_image_failures:
        result["grok_image_failures"] = grok_image_failures[:5]
    result["image_provider"] = image_provider
    # Gallery (Phase 1) upload outcome. Always surfaced so the
    # dashboard can plot "uploaded N / attempted M (reason=…)" per
    # episode and spot a misconfigured bucket immediately.
    result["gallery_attempted"] = gallery_attempted
    result["gallery_uploaded"] = gallery_uploaded
    if gallery_skipped_reason:
        result["gallery_skipped_reason"] = gallery_skipped_reason
    return result


def _append_youtube_line(teaser: str, extra_context: dict) -> str:
    """Append a "Watch on YouTube" line to the teaser when a URL is available.

    Idempotent — never duplicates the line if the teaser already
    references the URL (e.g. when a YAML ``x_teaser_template`` already
    embedded ``{youtube_url}``).
    """
    yt_url = (extra_context.get("youtube_url") or "").strip()
    if not yt_url:
        return teaser
    if yt_url in teaser:
        return teaser
    return f"{teaser}\n🎬 Watch on YouTube: {yt_url}"


def _build_teaser(config, episode_num: int, today_str: str, extra_context: dict) -> str:
    """Build a short X teaser post for the episode.

    If the YAML config has ``x_teaser_template``, it's used as a format string
    with ``{episode_num}``, ``{today_str}``, and any extra_context keys.  Otherwise,
    falls back to the per-show hardcoded templates below.

    A "🎬 Watch on YouTube: <url>" line is appended when
    ``extra_context["youtube_url"]`` is set (set by the pipeline after
    a successful long-form upload).
    """
    # Use YAML template if configured
    template = getattr(config.publishing, "x_teaser_template", "")
    if template:
        fmt_vars = {"episode_num": episode_num, "today_str": today_str, "show_name": config.name}
        fmt_vars.update(extra_context)
        try:
            return _append_youtube_line(template.format(**fmt_vars),
                                        extra_context)
        except (KeyError, IndexError):
            logger.warning("x_teaser_template format failed, falling back to hardcoded")

    slug = config.slug
    if slug == "tesla":
        price_str = ""
        if "price" in extra_context:
            price_str = f" | TSLA ${extra_context['price']}"
        teaser = (
            f"🚀⚡ Tesla Shorts Time Daily — {today_str}{price_str}\n\n"
            f"Episode {episode_num} is live!\n"
            f"🎧 Listen & read: https://nerranetwork.com/tesla-summaries.html"
        )
    elif slug == "omni_view":
        teaser = (
            f"📰⚖️ Omni View — {today_str}\n\n"
            f"Episode {episode_num}: Balanced news perspectives.\n"
            f"🎧 Read & listen: https://nerranetwork.com/omni-view-summaries.html"
        )
    elif slug == "fascinating_frontiers":
        teaser = (
            f"🚀🌌 Fascinating Frontiers — {today_str}\n\n"
            f"Episode {episode_num}: Space & astronomy news.\n"
            f"🎧 Read & listen: https://nerranetwork.com/fascinating-frontiers-summaries.html"
        )
    elif slug == "planetterrian":
        teaser = (
            f"🌍🧬 Planetterrian Daily — {today_str}\n\n"
            f"Episode {episode_num}: Science, longevity & health.\n"
            f"🎧 Read & listen: https://nerranetwork.com/planetterrian-summaries.html"
        )
    else:
        teaser = f"{config.name} Episode {episode_num} — {today_str}"
    return _append_youtube_line(teaser, extra_context)



# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    args = parse_args()
    try:
        run(args)
    except KeyboardInterrupt:
        logger.info("Interrupted.")
        sys.exit(1)
    except Exception:
        logger.exception("Pipeline failed")
        sys.exit(1)
