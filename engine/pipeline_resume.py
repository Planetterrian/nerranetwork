"""Resume publish when final MP3 exists but publish marker is missing."""

from __future__ import annotations

import argparse
import datetime
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class ResumePublishState:
    x_thread: str
    hook: str | None
    final_mp3: Path
    audio_duration: float
    digest_md: Path
    extra_context: dict


def load_resume_publish_state(
    config: Any,
    *,
    digests_dir: Path,
    episode_num: int,
    today: datetime.date,
    today_str: str,
    expected_mp3: Path,
    show_slug: str,
    extract_hook,
    load_hook,
) -> ResumePublishState:
    """Load digest + audio from disk for a publish-only retry."""
    digest_md = digests_dir / (
        f"{config.episode.prefix}_Ep{episode_num:03d}_{today:%Y%m%d}.md"
    )
    if not digest_md.exists():
        raise FileNotFoundError(f"Resume publish requires digest: {digest_md}")

    if not expected_mp3.exists():
        raise FileNotFoundError(f"Resume publish requires MP3: {expected_mp3}")

    x_thread = digest_md.read_text(encoding="utf-8")
    hook = extract_hook(x_thread)

    from engine.audio import get_audio_duration

    audio_duration = get_audio_duration(expected_mp3) or 0.0
    extra_context: dict = {}

    hook_module = load_hook(show_slug)
    if hook_module and hasattr(hook_module, "pre_fetch"):
        try:
            extra_context = hook_module.pre_fetch(
                config, episode_num=episode_num, today_str=today_str,
            )
        except Exception as exc:
            logger.warning("Resume: pre_fetch hook failed: %s", exc)

    if show_slug == "tesla":
        from shows.hooks.tesla import scrub_unavailable_tsla_from_digest
        x_thread = scrub_unavailable_tsla_from_digest(x_thread)

    logger.info(
        "Resume publish loaded: digest=%s mp3=%s (%.0fs)",
        digest_md.name, expected_mp3.name, audio_duration,
    )
    return ResumePublishState(
        x_thread=x_thread,
        hook=hook,
        final_mp3=expected_mp3,
        audio_duration=audio_duration,
        digest_md=digest_md,
        extra_context=extra_context,
    )


def should_resume_publish(
    expected_mp3: Path,
    publish_marker: Path,
    *,
    test_mode: bool,
    dry_run: bool,
    force: bool = False,
) -> bool:
    if test_mode or dry_run:
        return False
    if force:
        return expected_mp3.exists()
    return expected_mp3.exists() and not _marker_complete(publish_marker)


def _marker_complete(marker_path: Path) -> bool:
    from engine.publish_marker import is_publish_complete
    return is_publish_complete(marker_path)


def apply_resume_args(args: argparse.Namespace) -> argparse.Namespace:
    """Return args with YouTube skipped on resume (avoid duplicate uploads)."""
    merged = dict(vars(args))
    if not merged.get("resume_youtube"):
        merged["skip_youtube"] = True
    merged["resume_publish"] = True
    return argparse.Namespace(**merged)


def apply_resume_youtube_args(args: argparse.Namespace) -> argparse.Namespace:
    """Publish-only retry: rebuild/upload YouTube without re-running TTS."""
    merged = dict(vars(args))
    merged["skip_youtube"] = False
    merged["resume_youtube"] = True
    merged["resume_publish"] = True
    merged["skip_x"] = True
    merged["skip_newsletter"] = True
    return argparse.Namespace(**merged)


def should_resume_youtube(
    expected_mp3: Path,
    digest_md: Path,
    *,
    test_mode: bool,
    dry_run: bool,
    force: bool = False,
) -> bool:
    if test_mode or dry_run:
        return False
    if force:
        return expected_mp3.exists() and digest_md.exists()
    return expected_mp3.exists() and digest_md.exists()
