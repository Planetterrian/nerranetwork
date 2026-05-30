"""Per-platform post metadata for Shorts (YouTube / Instagram Reels / TikTok).

The video pipeline already builds YouTube title/description/tags
(``engine.video_metadata``). Instagram Reels and TikTok don't take a
title/tags field — they take a single *caption* with hashtags inline, and each
has its own conventions (caption length, how many hashtags read well, what CTA
makes sense). This module produces a ready-to-post caption + hashtag list per
platform from the episode hook + show info, reusing the same entity-derived
hashtags as the YouTube Shorts (``engine.shorts_hashtags``).

It's a pure builder (no I/O, no config import) so it's trivially testable; the
caller passes the show-derived values and persists the result as a
``<short>.social.json`` sidecar.
"""

from __future__ import annotations

from typing import Dict, List, Optional, Sequence

from engine.shorts_hashtags import extract_hashtags

# Conservative caption ceilings (both platforms allow ~2200; keep margin).
_CAPTION_MAX = 2000
# Universal discovery tags appended per platform (deduped against entity tags).
_YT_SUFFIX = ["Shorts", "podcast"]
_IG_SUFFIX = ["Reels", "podcast"]
_TIKTOK_SUFFIX = ["podcast", "fyp"]


def _fmt_tags(tags: Sequence[str]) -> str:
    return " ".join(f"#{t}" for t in tags)


def _merge_tags(entity_tags: Sequence[str], suffix: Sequence[str], cap: int = 8) -> List[str]:
    """Entity tags first, then platform suffix tags, de-duped case-insensitively."""
    out: List[str] = []
    seen = set()
    for t in list(entity_tags) + list(suffix):
        key = t.lower().lstrip("#")
        if key and key not in seen:
            seen.add(key)
            out.append(t.lstrip("#"))
        if len(out) >= cap:
            break
    return out


def _clip(text: str, limit: int = _CAPTION_MAX) -> str:
    if len(text) <= limit:
        return text
    return text[: limit - 1].rstrip() + "…"


def build_social_metadata(
    *,
    hook: str,
    show_name: str,
    show_url: str,
    long_form_url: str = "",
    short_youtube_url: str = "",
    show_keywords: Optional[Sequence[str]] = None,
    is_ru: bool = False,
) -> Dict[str, dict]:
    """Return ready-to-post metadata keyed by platform.

    Keys: ``youtube`` (title/description/tags), ``instagram_reels`` and
    ``tiktok`` (each ``caption`` + ``hashtags``). Captions lead with the hook
    (the unique, attention-grabbing line) so the visible preview is strong.
    """
    hook = (hook or "").strip()
    entity_tags = extract_hashtags(hook, show_keywords=show_keywords, max_hashtags=6)

    listen = long_form_url or short_youtube_url or show_url
    # Localised CTA copy for the Russian shows.
    if is_ru:
        full = "🎧 Полный выпуск и другие серии"
        more = "Слушайте"
    else:
        full = "🎧 Full episode + more"
        more = "Listen"

    # --- Instagram Reels: hook, CTA, then hashtags on their own line ---
    ig_tags = _merge_tags(entity_tags, _IG_SUFFIX, cap=10)
    ig_caption = _clip(
        f"{hook}\n\n{full}: {show_url}\n\n{_fmt_tags(ig_tags)}"
    )

    # --- TikTok: punchier; a few hashtags inline after the hook ---
    tt_tags = _merge_tags(entity_tags, _TIKTOK_SUFFIX, cap=6)
    tt_caption = _clip(f"{hook} {_fmt_tags(tt_tags)}".strip())

    # --- YouTube Shorts: title + description + tags (mirrors video_metadata) ---
    yt_tags = _merge_tags(entity_tags, _YT_SUFFIX, cap=12)
    yt_title = _clip(f"{hook} | {show_name} #Shorts", limit=100)
    yt_desc_lines = [hook, "", f"{more}: {listen}", f"🌐 {show_url}"]
    if long_form_url:
        yt_desc_lines.insert(2, f"▶ Full episode: {long_form_url}")
    yt_description = _clip("\n".join(yt_desc_lines), limit=4500)

    return {
        "youtube": {
            "title": yt_title,
            "description": yt_description,
            "tags": yt_tags,
        },
        "instagram_reels": {
            "caption": ig_caption,
            "hashtags": ig_tags,
        },
        "tiktok": {
            "caption": tt_caption,
            "hashtags": tt_tags,
        },
        "_meta": {
            "hook": hook,
            "show_name": show_name,
            "show_url": show_url,
            "long_form_url": long_form_url,
            "short_youtube_url": short_youtube_url,
        },
    }
