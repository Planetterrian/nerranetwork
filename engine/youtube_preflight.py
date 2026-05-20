"""Pre-flight checks for YouTube-enabled shows."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, List

from engine.youtube_quota import format_quota_warning, estimate_network_daily_units


def validate_youtube_show_ready(
    config: Any,
    project_root: Path,
) -> List[str]:
    """Return fatal misconfiguration issues for an enabled show."""
    issues: List[str] = []
    yt = getattr(config, "youtube", None)
    if not yt or not getattr(yt, "enabled", False):
        return issues

    slug = getattr(config, "slug", "show")
    for name in (
        f"{slug.replace('_', '-')}.jpg",
        f"{slug}.jpg",
    ):
        if (project_root / "assets" / "covers" / name).exists():
            break
    else:
        issues.append(
            f"YouTube enabled but no cover at assets/covers/ for slug={slug}"
        )

    channel = (getattr(yt, "channel", "en") or "en").lower()
    suffix = "RU" if channel == "ru" else "EN"
    cred_vars = (
        "YOUTUBE_CLIENT_ID",
        "YOUTUBE_CLIENT_SECRET",
        f"YOUTUBE_REFRESH_TOKEN_{suffix}",
    )
    missing = [v for v in cred_vars if not os.getenv(v, "").strip()]
    if missing:
        issues.append(
            f"YouTube enabled but missing env vars: {', '.join(missing)}"
        )

    privacy = (getattr(yt, "privacy_status", "public") or "").strip()
    if privacy not in ("public", "unlisted", "private"):
        issues.append(
            f"youtube.privacy_status={privacy!r} must be public, unlisted, or private"
        )

    provider = (getattr(yt, "image_provider", "pexels") or "pexels").lower()
    if provider in ("pexels", "hybrid") and not os.getenv("PEXELS_API_KEY", "").strip():
        issues.append(
            "YouTube image_provider uses Pexels but PEXELS_API_KEY is unset"
        )

    if provider in ("grok", "hybrid") and not (
        os.getenv("GROK_API_KEY", "").strip()
        or os.getenv("XAI_API_KEY", "").strip()
    ):
        issues.append(
            "YouTube image_provider uses Grok Imagine but GROK_API_KEY is unset"
        )

    queries = list(getattr(yt, "image_queries", None) or [])
    if not queries:
        issues.append(
            f"YouTube enabled for {slug} but youtube.image_queries is empty "
            "(required for safe slideshow imagery)"
        )

    return issues


def youtube_network_quota_warning(project_root: Path) -> str | None:
    """Warning when all enabled shows exceed the default daily quota."""
    shows_dir = project_root / "shows"
    if not shows_dir.is_dir():
        return None
    summary = estimate_network_daily_units(shows_dir)
    return format_quota_warning(summary)
