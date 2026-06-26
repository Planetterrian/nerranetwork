"""Short Grok video clips that COMPLEMENT the still-image slideshow.

This is the lightweight, hybrid sibling of :mod:`engine.grok_video`. That module
replaces the whole episode background with generated video (~$40-80/episode at
720p) and was disabled on cost grounds. This module instead generates a SMALL
number of short clips (3-6 s each) that the long-form renderer interleaves
*between* the Grok still images — adding genuine motion at a few high-value
beats. That is the cheap, on-policy fix for YouTube's 2025-2026 penalty against
pure static-image slideshows, at ~$1-3/episode instead of ~$50.

Pilot scope: Tesla + SpaceX (the two most-watched shows). Other shows opt in by
setting ``youtube.video_clips_enabled: true``.

Contract: pure best-effort. No API key, network failure, or a budget timeout
returns an empty :class:`ClipSet`; the caller falls back to the all-stills
slideshow and never blocks the publish. Touches only visuals, never audio
(outside the landmine #17 A/B-listen gate).
"""

from __future__ import annotations

import logging
import os
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional

logger = logging.getLogger(__name__)

# Wall-clock budget for the whole clip step (submit + poll + download). A stuck
# clip must never starve the per-episode pipeline timeout. Env-overridable.
DEFAULT_CLIPS_BUDGET_S = float(os.getenv("GROK_VIDEO_CLIPS_BUDGET_SECONDS", "600"))
_POLL_INTERVAL_S = 4.0


@dataclass
class ClipSet:
    """Result of a short-clip generation run."""
    paths: List[Path] = field(default_factory=list)
    total_cost_usd: float = 0.0
    requested: int = 0
    failures: List[str] = field(default_factory=list)

    def __len__(self) -> int:
        return len(self.paths)


def _api_key() -> str:
    return (os.getenv("GROK_API_KEY") or os.getenv("XAI_API_KEY") or "").strip()


def _short_clip_prompt(context: str, show_config, hook: str, seconds: int) -> str:
    """Compact prompt for one short B-roll clip (no narration, no text)."""
    genre = mood = visual_style = ""
    keywords: List[str] = []
    if show_config is not None and hasattr(show_config, "youtube"):
        yt = show_config.youtube
        genre = getattr(yt, "video_genre", "") or ""
        mood = getattr(yt, "video_mood", "") or ""
        keywords = list(getattr(yt, "video_keywords", []) or [])
        visual_style = getattr(yt, "video_visual_style", "") or ""
    subject = (context or hook or "").strip() or (genre or "technology news")
    kw = ", ".join(keywords[:5])
    return (
        f"A short {seconds}-second cinematic B-roll video clip for a podcast.\n"
        f"Subject: {subject}\n"
        f"Genre: {genre or 'technology news'}. Mood: {mood or 'professional'}.\n"
        f"Visual style: {visual_style or 'cinematic, high production value, dynamic camera movement'}.\n"
        f"Key visual motifs: {kw or subject}.\n"
        "Smooth motion, dramatic natural lighting, sharp focus, vivid color grading. "
        "No text, words, captions, watermarks, logos, or talking heads."
    ).strip()


def generate_short_clips(
    *,
    work_dir: Path,
    episode_num: int,
    contexts: Optional[List[str]] = None,
    hook: str = "",
    show_config=None,
    count: int = 3,
    seconds: int = 5,
    resolution: str = "720p",
    aspect: str = "16:9",
    budget_s: Optional[float] = None,
) -> ClipSet:
    """Generate up to *count* short clips. Returns an (empty-on-failure) ClipSet."""
    count = max(0, min(int(count or 0), 6))
    seconds = max(2, min(int(seconds or 5), 15))
    if count == 0:
        return ClipSet()

    api_key = _api_key()
    if not api_key:
        logger.info("Grok video clips skipped — no GROK_API_KEY/XAI_API_KEY.")
        return ClipSet()

    try:
        from engine.grok_video import (
            VIDEO_COST_USD,
            _check_video_status_once,
            _download_video,
            _extract_video_url,
            _is_terminal_failure,
            _is_terminal_success,
            _request_one_video,
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("Grok video clip helpers unavailable: %s", exc)
        return ClipSet()

    budget = float(budget_s if budget_s is not None else DEFAULT_CLIPS_BUDGET_S)
    deadline = time.monotonic() + budget
    contexts = contexts or []
    clips_dir = work_dir / f"clips_ep{episode_num:03d}"

    result = ClipSet(requested=count)

    # Submit all clips up front so they generate in parallel server-side.
    pending: dict[str, int] = {}  # request_id -> clip index
    for i in range(count):
        ctx = contexts[i % len(contexts)] if contexts else ""
        prompt = _short_clip_prompt(ctx, show_config, hook, seconds)
        try:
            rid = _request_one_video(
                prompt,
                duration_s=seconds,
                api_key=api_key,
                resolution=resolution,
                aspect_ratio=aspect,
            )
            pending[rid] = i
        except Exception as exc:  # noqa: BLE001
            result.failures.append(f"submit clip {i}: {exc}")

    if not pending:
        return result

    # Round-robin poll so one slow clip can't block the others.
    downloaded: dict[int, Path] = {}
    while pending and time.monotonic() < deadline:
        for rid in list(pending):
            try:
                body = _check_video_status_once(rid, api_key=api_key)
            except Exception as exc:  # noqa: BLE001 — transient; retry next loop
                logger.debug("clip status check failed (%s): %s", rid, exc)
                continue
            status = body.get("status", "unknown")
            if _is_terminal_success(status):
                idx = pending.pop(rid)
                url = _extract_video_url(body)
                out = clips_dir / f"clip_{idx}.mp4"
                if url and _download_video(url, out):
                    downloaded[idx] = out
                else:
                    result.failures.append(f"clip {idx}: no/failed download")
            elif _is_terminal_failure(status):
                idx = pending.pop(rid)
                result.failures.append(f"clip {idx}: status={status}")
        if pending and time.monotonic() < deadline:
            time.sleep(_POLL_INTERVAL_S)

    if pending:
        result.failures.append(
            f"{len(pending)} clip(s) unfinished within {budget:.0f}s budget"
        )

    # Preserve submission order so interleaving is deterministic.
    result.paths = [downloaded[i] for i in sorted(downloaded)]
    per_clip = VIDEO_COST_USD.get(resolution, 0.07) * seconds
    result.total_cost_usd = round(per_clip * len(result.paths), 4)
    logger.info(
        "Grok video clips: %d/%d generated (%.2f USD, %d failures)",
        len(result.paths), count, result.total_cost_usd, len(result.failures),
    )
    return result
