"""Build YouTube title / description / tag payloads from existing show data.

Mirrors the role :func:`run_show._build_teaser` plays for X — same data
sources (digest, hook, episode number, chapters), different output. Pure
functions so the unit tests don't need a network or a populated repo.

YouTube enforces three hard limits we respect:

  - Title: 100 characters (we truncate with an ellipsis).
  - Description: 5000 characters (we trim trailing chunks if needed).
  - Combined tag length: 500 characters when joined with commas (we
    drop tags from the tail until we fit).
"""

from __future__ import annotations

import json
import logging
import re
from pathlib import Path
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


YOUTUBE_TITLE_MAX = 100
YOUTUBE_DESC_MAX = 5000
YOUTUBE_TAG_TOTAL_MAX = 500


# ---------------------------------------------------------------------------
# Markdown stripping (matches the spirit of publisher.format_digest_for_x)
# ---------------------------------------------------------------------------

def _strip_markdown(text: str) -> str:
    """Strip the markdown that shows up in our digests.

    Keeps URLs as bare text, removes header markers, bold/italic, and
    inline code fences. Also drops leading blockquote markers and
    strips raw ``<`` / ``>`` characters because YouTube's ``videos.insert``
    API rejects descriptions that contain either character (HTTP 400
    ``invalidDescription``). This was hitting every long-form upload
    in May 2026 because the daily digest opens with a
    ``> **Hook**`` blockquote — bold strip left a literal ``>`` at
    the start of the description, killing the YouTube upload while
    the Shorts upload (which uses a separate metadata path) still
    succeeded.
    """
    if not text:
        return ""
    # Strip code fences first so their contents aren't mis-parsed.
    text = re.sub(r"```.*?```", "", text, flags=re.DOTALL)
    # Headers
    text = re.sub(r"^#+\s+", "", text, flags=re.MULTILINE)
    # Blockquote markers at line start — these are the chief source of
    # stray ``>`` characters in our descriptions (every digest opens
    # with ``> **Hook**``).
    text = re.sub(r"^[ \t]*>[ \t]*", "", text, flags=re.MULTILINE)
    # Bold + italic
    text = re.sub(r"\*\*(.*?)\*\*", r"\1", text)
    text = re.sub(r"(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)", r"\1", text)
    text = re.sub(r"__(.*?)__", r"\1", text)
    # Inline code
    text = re.sub(r"`([^`]+)`", r"\1", text)
    # Markdown links → plain URL
    text = re.sub(r"\[([^\]]+)\]\((https?://[^\)]+)\)", r"\1: \2", text)
    # Final defense-in-depth: drop any remaining ``<`` / ``>`` so
    # YouTube doesn't 400 on stray angle-bracket content (math like
    # ``<2030``, escaped speech tags that survived earlier passes,
    # decorative arrows, etc.).
    text = text.replace("<", "").replace(">", "")
    return text


def _truncate(text: str, max_len: int) -> str:
    """Trim *text* to ``max_len`` characters with an ellipsis if shortened."""
    if len(text) <= max_len:
        return text
    return text[: max_len - 3].rstrip() + "..."


# ---------------------------------------------------------------------------
# Chapter formatting
# ---------------------------------------------------------------------------

def _format_chapter_timestamp(seconds: float) -> str:
    """``H:MM:SS`` for hour-long content, ``MM:SS`` otherwise.

    YouTube requires the **first** chapter to start at ``0:00`` for the
    description-driven chapter feature to activate.
    """
    seconds = max(0, int(seconds))
    h, rem = divmod(seconds, 3600)
    m, s = divmod(rem, 60)
    if h:
        return f"{h}:{m:02d}:{s:02d}"
    return f"{m}:{s:02d}"


def _read_chapters(chapters_path: Optional[Path]) -> List[Dict]:
    """Load a ``chapters_ep*.json`` file. Returns an empty list on error."""
    if not chapters_path or not chapters_path.exists():
        return []
    try:
        data = json.loads(chapters_path.read_text(encoding="utf-8"))
    except Exception as exc:
        logger.warning("Could not read chapters file %s: %s", chapters_path, exc)
        return []
    chapters = data.get("chapters") if isinstance(data, dict) else data
    if not isinstance(chapters, list):
        return []
    return chapters


def _format_chapter_block(chapters: List[Dict]) -> str:
    """Render chapters as the YouTube-compatible ``0:00 Title`` block.

    Returns an empty string when the chapter list is missing, has fewer
    than 2 entries, or doesn't start at 0 — YouTube silently ignores
    chapter blocks that don't meet those rules, so there's no point
    rendering one.
    """
    if not chapters or len(chapters) < 2:
        return ""

    rendered: List[str] = []
    for ch in chapters:
        if not isinstance(ch, dict):
            continue
        title = (ch.get("title") or "").strip()
        start = ch.get("startTime", ch.get("start_time", ch.get("start")))
        if start is None or not title:
            continue
        try:
            start_f = float(start)
        except (TypeError, ValueError):
            continue
        rendered.append(f"{_format_chapter_timestamp(start_f)} {title}")

    # YouTube requires the first stamp to be 0:00.
    if not rendered or not rendered[0].startswith("0:00"):
        return ""
    return "\n".join(rendered)


# ---------------------------------------------------------------------------
# Tag handling
# ---------------------------------------------------------------------------

def _build_tags(
    extra: List[str],
    keywords: List[str],
    *,
    network_tags: List[str],
    max_tags: int = 30,
) -> List[str]:
    """Build a deduped list of tags that fits inside YouTube's 500-char cap."""
    seen = set()
    ordered: List[str] = []
    for tag in list(extra) + list(network_tags) + list(keywords):
        if not tag:
            continue
        clean = str(tag).strip().lower()
        if not clean or clean in seen:
            continue
        seen.add(clean)
        ordered.append(clean)
        if len(ordered) >= max_tags:
            break

    # Trim from the tail while the comma-joined length exceeds the cap.
    while ordered and len(",".join(ordered)) > YOUTUBE_TAG_TOTAL_MAX:
        ordered.pop()
    return ordered


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def build_long_form_metadata(
    config,
    *,
    episode_num: int,
    today_str: str,
    hook: str,
    digest_text: str,
    audio_url: str,
    chapters_path: Optional[Path] = None,
    photo_attribution: Optional[List[str]] = None,
) -> Dict:
    """Assemble the YouTube metadata payload for a long-form upload.

    Parameters
    ----------
    photo_attribution:
        Optional list of one-line photographer credits (e.g. from the
        Pexels slideshow). When non-empty, a "Photos:" block is
        appended to the description above the AI disclosure footer.

    Returns
    -------
    dict
        ``{"title": str, "description": str, "tags": List[str],
        "category_id": int, "default_language": str}``
    """
    rss_title = (
        getattr(config.publishing, "rss_title", "")
        or getattr(config, "name", "")
    )
    title_seed = f"{rss_title} — Ep {episode_num}: {hook}" if hook else (
        f"{rss_title} — Ep {episode_num} — {today_str}"
    )
    title = _truncate(title_seed.strip(), YOUTUBE_TITLE_MAX)

    base_url = getattr(config.publishing, "base_url",
                       "https://nerranetwork.com").rstrip("/")
    rss_link = getattr(config.publishing, "rss_link", "") or base_url
    utm_link = (
        f"{rss_link}{'&' if '?' in rss_link else '?'}"
        f"utm_source=youtube&utm_medium=video&utm_campaign=ep{episode_num}"
    )

    # First few paragraphs of the digest become the description body.
    body_source = _strip_markdown(digest_text or "")
    paragraphs = [p.strip() for p in body_source.split("\n\n") if p.strip()]
    body = "\n\n".join(paragraphs[:4]).strip()

    chapters_block = _format_chapter_block(_read_chapters(chapters_path))

    # Order matters: YouTube only shows the first ~150 chars above the
    # "Show more" fold on mobile, so the subscribe link goes right
    # after the hook so it's always visible. Body/chapters/credits
    # follow.
    show_label = rss_title or getattr(config, "name", "this show")
    subscribe_line = (
        f"🎧 Subscribe to {show_label} on the Nerra Network: {utm_link}"
    )

    pieces: List[str] = []
    if hook:
        pieces.append(hook.strip())
    pieces.append(subscribe_line)
    if body:
        pieces.append(body)
    if chapters_block:
        pieces.append("Chapters:\n" + chapters_block)
    if audio_url:
        pieces.append(f"Direct audio: {audio_url}")
    if photo_attribution:
        cleaned = [line.strip() for line in photo_attribution if line.strip()]
        if cleaned:
            pieces.append("Photos via Pexels:\n" + "\n".join(cleaned))
    disclosure = (config.youtube.synthetic_disclosure or "").strip()
    if disclosure:
        pieces.append(disclosure)

    # Final safety strip — YouTube rejects any description containing
    # ``<`` or ``>`` with HTTP 400 ``invalidDescription``. ``_strip_markdown``
    # already cleans the body, but the hook + chapter titles flow into
    # the description verbatim, so we belt-and-braces strip again here.
    description = "\n\n".join(pieces).strip().replace("<", "").replace(">", "")
    description = _truncate(description, YOUTUBE_DESC_MAX)

    tags = _build_tags(
        list(config.youtube.tags or []),
        list(getattr(config, "keywords", []) or []),
        network_tags=[],  # already merged into youtube.tags via _defaults.yaml
    )

    return {
        "title": title,
        "description": description,
        "tags": tags,
        "category_id": int(config.youtube.category_id or 28),
        "default_language": (config.youtube.default_language or "en").lower(),
    }


def build_short_metadata(
    config,
    *,
    episode_num: int,
    today_str: str,
    hook: str,
    long_form_url: str = "",
) -> Dict:
    """Assemble the YouTube metadata payload for a Shorts upload.

    Title gets ``#Shorts`` appended (the most reliable way to get the
    auto-classifier to treat the upload as a Short). The description is
    deliberately brief so the disclosure footer remains visible above
    the "Show more" fold on mobile.
    """
    rss_title = (
        getattr(config.publishing, "rss_title", "")
        or getattr(config, "name", "")
    )
    headline = hook.strip() if hook else f"Ep {episode_num} highlight"
    title_seed = f"{headline} | {rss_title} #Shorts"
    title = _truncate(title_seed.strip(), YOUTUBE_TITLE_MAX)

    pieces: List[str] = [headline]
    if long_form_url:
        pieces.append(f"Full episode: {long_form_url}")
    base_url = getattr(config.publishing, "base_url",
                       "https://nerranetwork.com").rstrip("/")
    rss_link = getattr(config.publishing, "rss_link", "") or base_url
    utm_link = (
        f"{rss_link}{'&' if '?' in rss_link else '?'}"
        f"utm_source=youtube&utm_medium=shorts&utm_campaign=ep{episode_num}"
    )
    pieces.append(f"Subscribe to the podcast: {utm_link}")
    disclosure = (config.youtube.synthetic_disclosure or "").strip()
    if disclosure:
        pieces.append(disclosure)
    pieces.append("#Shorts #podcast")

    # Same ``invalidDescription`` defense as build_long_form_metadata —
    # YouTube rejects ``<`` / ``>`` even though Shorts hasn't tripped
    # this in production yet (the headline is the only user-supplied
    # field and hooks rarely contain angle brackets). Belt-and-braces.
    description = "\n\n".join(pieces).strip().replace("<", "").replace(">", "")
    description = _truncate(description, YOUTUBE_DESC_MAX)

    tags = _build_tags(
        list(config.youtube.tags or []) + ["shorts", "podcast clip"],
        list(getattr(config, "keywords", []) or []),
        network_tags=[],
    )

    return {
        "title": title,
        "description": description,
        "tags": tags,
        "category_id": int(config.youtube.category_id or 28),
        "default_language": (config.youtube.default_language or "en").lower(),
    }
