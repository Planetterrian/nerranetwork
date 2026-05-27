"""Pipeline orchestration helpers (May 2026 review - item 1).

This module is the future home for extracted phases from the large
`run_show.py` monolith. The goal is incremental, testable extraction
of major stages (fetch/dedup, generation, TTS+audio, publishing,
post-publish) rather than a single big-bang refactor.

For now it contains only lightweight utilities and will grow as
specific phases are carved out with clear interfaces.
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
        pass
