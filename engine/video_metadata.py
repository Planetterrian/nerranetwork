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
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# Repo root — two levels up from engine/
_REPO_ROOT = Path(__file__).resolve().parent.parent


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
    # Defense-in-depth: scrub Grok TTS speech tags before any YouTube
    # surface (title, description, chapter labels) sees the text. The
    # podcast script intentionally carries ``[breath]`` / ``<emphasis>``
    # / etc. for the TTS path; readers should never see them.
    from engine.utils import strip_speech_tags
    text = strip_speech_tags(text)
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
    # Markdown links → keep the LABEL only, drop the URL.
    #
    # Operator caught (Tesla Ep459-465 long-form, May 2-5 2026)
    # YouTube rejecting every Tesla long-form upload with
    # ``invalidDescription``. Tesla digests embed Google News redirect
    # URLs of the form
    # ``https://news.google.com/rss/articles/CBMimgFBVV95cUx...?oc=5``
    # — 200+ char base64-encoded paths. Five such URLs in the body
    # paragraphs trips YouTube's "looks-like-spam" classifier on
    # ``body.snippet.description``. Shorts uploads (which use a
    # separate metadata path with no body content) were unaffected.
    #
    # The chapters block + subscribe link + audio URL still ship
    # clean URLs to listeners; readers don't lose navigation. The
    # source citations remain in the digest .md / blog post / RSS,
    # which is where readers actually click them.
    text = re.sub(r"\[([^\]]+)\]\(https?://[^\)]+\)", r"\1", text)
    # Belt-and-braces: strip any bare URL longer than 80 chars that
    # survived (e.g. a non-markdown raw URL pasted into the digest).
    text = re.sub(r"https?://[^\s)]{80,}", "", text)
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


def _build_seo_title(hook: str, show_name: str, *, suffix: str = "") -> str:
    """Build a search-optimised YouTube title that FRONT-LOADS the hook.

    YouTube weights the first words of a title most heavily for search and
    viewers scan the start, so the keyword-rich episode hook leads — not the
    show name + "Ep N" (which wasted the most valuable real estate and isn't
    searched). Shape: ``"<hook> | <show>[ <suffix>]"``, trimmed to fit
    ``YOUTUBE_TITLE_MAX``. If the hook alone is too long the hook wins (keywords
    matter most) and the show-name tail is dropped; a ``suffix`` like
    ``#Shorts`` (the Shorts classifier hint) is preserved when possible.
    """
    hook = (hook or "").strip().rstrip(".")
    show = (show_name or "").strip()
    suffix = (suffix or "").strip()
    if not hook:
        base = f"{show} {suffix}".strip()
        return _truncate(base, YOUTUBE_TITLE_MAX)
    tail = f" | {show}" if show else ""
    if suffix:
        tail = f"{tail} {suffix}" if tail else f" {suffix}"
    if len(hook) + len(tail) <= YOUTUBE_TITLE_MAX:
        return (hook + tail).strip()
    # Hook + show won't both fit — keep the #Shorts suffix (classifier) if it
    # fits, otherwise the hook alone (truncated). Keywords > show name.
    if suffix and len(hook) + 1 + len(suffix) <= YOUTUBE_TITLE_MAX:
        return f"{hook} {suffix}"
    return _truncate(hook, YOUTUBE_TITLE_MAX)


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

def _load_description_body_from_template(
    config: Any,
    *,
    episode_num: int,
    today_str: str,
    hook: str,
) -> str:
    """Optional YouTube-specific description intro from a prompt file."""
    yt = getattr(config, "youtube", None)
    rel = (getattr(yt, "description_prompt_file", None) or "").strip()
    if not rel:
        return ""
    path = Path(rel)
    if not path.is_file():
        path = _REPO_ROOT / rel
    if not path.exists():
        logger.warning("youtube.description_prompt_file missing: %s", path)
        return ""
    template = path.read_text(encoding="utf-8").strip()
    rss_title = (
        getattr(config.publishing, "rss_title", "")
        or getattr(config, "name", "")
    )
    try:
        body = template.format(
            hook=(hook or "").strip(),
            episode_num=episode_num,
            today_str=today_str,
            show_name=rss_title,
            rss_link=getattr(config.publishing, "rss_link", "") or "",
        )
    except KeyError as exc:
        logger.warning("description template format error: %s", exc)
        return ""
    return _strip_markdown(body)


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
    # SEO: front-load the keyword-rich hook (was "{show} — Ep N: {hook}",
    # which buried the topic behind the show name + episode number).
    if hook:
        title = _build_seo_title(hook, rss_title)
    else:
        title = _truncate(f"{rss_title} — Ep {episode_num} — {today_str}".strip(),
                          YOUTUBE_TITLE_MAX)

    base_url = getattr(config.publishing, "base_url",
                       "https://nerranetwork.com").rstrip("/")
    rss_link = getattr(config.publishing, "rss_link", "") or base_url
    utm_link = (
        f"{rss_link}{'&' if '?' in rss_link else '?'}"
        f"utm_source=youtube&utm_medium=video&utm_campaign=ep{episode_num}"
    )

    template_body = _load_description_body_from_template(
        config,
        episode_num=episode_num,
        today_str=today_str,
        hook=hook,
    )
    if template_body:
        body = template_body
    else:
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
    # Direct, no-frills show-page line at the top of the description.
    # YouTube auto-hyperlinks the URL; keeps the show page one click away
    # for any viewer who scrolls into "Show more". The bare URL (no UTM)
    # is the canonical identity of the show on the network — operators
    # use this URL on flyers, podcast directories, and so on, so it
    # should match exactly when listeners cross-reference. The
    # ``subscribe_line`` below carries the UTM-tracked variant for
    # attribution.
    show_page_line = f"🌐 Show page: {rss_link}"

    pieces: List[str] = []
    if hook:
        pieces.append(hook.strip())
    pieces.append(show_page_line)
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
    # SEO: entity hashtags so YouTube renders the first 3 as clickable topic
    # links above the title (a discovery lever Shorts already had but long-form
    # was missing). Same heuristic extractor as Shorts; static tail "#podcast".
    try:
        from engine.shorts_hashtags import extract_hashtags, format_hashtag_line
        _extracted = extract_hashtags(
            hook, show_keywords=list(getattr(config, "keywords", []) or []),
            max_hashtags=5,
        )
        _hashtag_line = format_hashtag_line(_extracted, ("#podcast",))
        if _hashtag_line:
            pieces.append(_hashtag_line)
    except Exception:  # noqa: BLE001 — hashtags must never block an upload
        pass
    disclosure = (config.youtube.synthetic_disclosure or "").strip()
    if disclosure:
        pieces.append(disclosure)
    pinned = (getattr(config.youtube, "pinned_comment_template", None) or "").strip()
    if pinned:
        try:
            pinned = pinned.format(
                hook=(hook or "").strip(),
                episode_num=episode_num,
                today_str=today_str,
                show_page_url=rss_link,
                full_episode_url=audio_url or "",
            )
        except KeyError:
            pass
        pieces.append("—\nSuggested pinned comment:\n" + pinned)

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
    # Same front-loaded builder as long-form; keeps the #Shorts classifier
    # hint even when the headline is long.
    title = _build_seo_title(headline, rss_title, suffix="#Shorts")

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
    # Show page link near the top — YouTube Shorts descriptions are
    # short by design, so listeners who tap the title or "more" want
    # the show page one click away.
    pieces.append(f"🌐 Show page: {rss_link}")
    pieces.append(f"Subscribe to the podcast: {utm_link}")
    disclosure = (config.youtube.synthetic_disclosure or "").strip()
    if disclosure:
        pieces.append(disclosure)

    # Auto-extract hashtags from the hook so the Shorts description
    # carries the day's entities (Tesla / Cybercab / OpenAI etc.) as
    # search-indexable + above-the-title topic tags. YouTube renders
    # the FIRST 3 hashtags as clickable links above the video title
    # — biggest discovery lever on Shorts after the title itself.
    # Falls back cleanly to the static ``#Shorts #podcast`` line when
    # the hook has nothing extractable.
    from engine.shorts_hashtags import extract_hashtags, format_hashtag_line
    extracted = extract_hashtags(
        hook,
        show_keywords=list(getattr(config, "keywords", []) or []),
        max_hashtags=5,
    )
    pieces.append(format_hashtag_line(extracted, ("#Shorts", "#podcast")))

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
