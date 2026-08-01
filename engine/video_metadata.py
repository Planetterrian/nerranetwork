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
    """Trim *text* to ``max_len`` characters, never cutting a word in half.

    Was ``text[: max_len - 3] + "..."``, which produced YouTube titles
    ending mid-word. Delegates to engine.titles so the video path, the
    podcast feed and the website all clip by the same rule — see that
    module for why this is centralised.
    """
    from engine.titles import clip_words
    return clip_words(text, max_len)


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
    # Hook + show won't both fit. Drop the show name before the suffix:
    # "#Shorts" is a classifier hint YouTube reads, so losing it can cost
    # the video its Shorts placement, whereas the show name is already on
    # the channel. Previously the suffix was kept only when the untrimmed
    # hook happened to leave room — a long hook silently dropped #Shorts.
    # Now the suffix is reserved first and the hook clips around it.
    if suffix:
        return f"{_truncate(hook, YOUTUBE_TITLE_MAX - len(suffix) - 1)} {suffix}"
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

def build_pinned_comment_text(
    config, *, hook: str = "", episode_num: int = 0, today_str: str = "",
    rss_link: str = "", audio_url: str = "",
) -> str:
    """Render the show's pinned-comment template, or "" when unset.

    July 18 2026: extracted from the long-form description builder so the
    same text can ALSO be posted as a real channel comment via
    ``engine.youtube.post_video_comment`` (the API cannot pin it — the
    operator pins manually — but the channel's own comment surfaces near
    the top). One template, two surfaces.
    """
    pinned = (getattr(config.youtube, "pinned_comment_template", None) or "").strip()
    if not pinned:
        return ""
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
    return pinned.strip()


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
    footage_attribution: Optional[List[str]] = None,
    optimized_title: Optional[str] = None,
    channel: str = "en",
) -> Dict:
    """Assemble the YouTube metadata payload for a long-form upload.

    Parameters
    ----------
    optimized_title:
        Optional LLM-generated, click-optimized title (from
        ``engine.youtube_titles``). When provided it is used verbatim (capped
        to the YouTube limit) instead of the hook-derived SEO title; the
        hook-based path remains the fallback when it's empty.
    photo_attribution:
        Optional list of one-line photographer credits (e.g. from the
        Pexels slideshow). When non-empty, a "Photos:" block is
        appended to the description above the AI disclosure footer.
    footage_attribution:
        Optional list of one-line b-roll credits (from
        ``engine.gallery_library.broll_attributions_for``). NOT
        cosmetic when present: CC BY-licensed footage (SpaceX YouTube
        back-catalog) legally requires the credit wherever the video
        ships, so this block must survive any description refactor.

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
    # Prefer the LLM-optimized title (click-tuned, separate from the spoken
    # hook). Fall back to the front-loaded keyword-rich hook, then to the
    # generic show + episode + date title.
    if optimized_title and optimized_title.strip():
        title = _truncate(optimized_title.strip(), YOUTUBE_TITLE_MAX)
    elif hook:
        title = _build_seo_title(hook, rss_title)
    else:
        title = _truncate(f"{rss_title} — Ep {episode_num} — {today_str}".strip(),
                          YOUTUBE_TITLE_MAX)

    base_url = getattr(config.publishing, "base_url",
                       "https://nerranetwork.com").rstrip("/")
    rss_link = getattr(config.publishing, "rss_link", "") or base_url
    # Funnel-tagged destination. ``engine.funnel`` owns the campaign
    # taxonomy for the whole network — the previous hand-rolled
    # ``utm_campaign=ep{n}`` carried no show slug, so every show's
    # episode 42 collapsed into one unattributable GA4 row.
    from engine import funnel as _funnel

    utm_link = _funnel.episode_link(
        _funnel.destination_for(config, channel=channel) or rss_link,
        getattr(config, "slug", ""), episode_num,
        channel=channel, kind="long",
        placement=_funnel.PLACEMENT_DESCRIPTION,
    ) or rss_link

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

    # Rotating network-discovery line (gallery / blogs / trackers / …) —
    # metadata-only, no audio. Same date-deterministic surface rotation
    # as the spoken outro and X reply (engine.network_promo).
    discovery_line = ""
    try:
        import datetime as _dt
        from engine.network_promo import pick_featured_surface
        _slug = getattr(config, "slug", "") or ""
        _surface = pick_featured_surface(_slug, _dt.date.today())
        if _surface:
            discovery_line = (
                f"✨ {_surface['x_line'].replace('More from the Nerra Network: ', '')} "
                f"— https://nerranetwork.com/{_surface['url']}"
            )
    except Exception:  # noqa: BLE001 — never block a YouTube upload
        discovery_line = ""

    # Hashtags early: YouTube surfaces the first 3 as clickable topic links
    # above the title. July 2026 — moved above the fold (was buried after
    # body/chapters) so discovery tags aren't lost under "Show more".
    _hashtag_line = ""
    try:
        from engine.shorts_hashtags import extract_hashtags, format_hashtag_line
        _extracted = extract_hashtags(
            hook, show_keywords=list(getattr(config, "keywords", []) or []),
            max_hashtags=5,
        )
        _hashtag_line = format_hashtag_line(_extracted, ("#podcast",))
    except Exception:  # noqa: BLE001 — hashtags must never block an upload
        _hashtag_line = ""

    # What the episode is actually ABOUT, directly under the hook.
    # Previously the first thing after the hook was three promotional
    # link lines, so the topics a viewer (or YouTube's indexer) most
    # needs sat below "Show more" behind boilerplate that is identical
    # on every upload. These headlines are the day's stories, already
    # extracted for the slideshow — no new call, no new cost.
    _topics_block = ""
    try:
        from engine.grok_imagine import extract_story_headlines
        _stories = [
            _truncate(_strip_markdown(s), 110)
            for s in extract_story_headlines(digest_text or "", max_count=5)
        ]
        # Drop a headline that merely restates the hook — the hook is
        # the line immediately above it.
        _hook_key = " ".join((hook or "").lower().split())[:60]
        _stories = [
            s for s in _stories
            if s and " ".join(s.lower().split())[:60] != _hook_key
        ]
        if _stories:
            _topics_block = "In this episode:\n" + "\n".join(
                "• " + s for s in _stories[:4]
            )
    except Exception:  # noqa: BLE001 — never block an upload
        _topics_block = ""

    pieces: List[str] = []
    if hook:
        pieces.append(hook.strip())
    if _hashtag_line:
        pieces.append(_hashtag_line)
    if _topics_block:
        pieces.append(_topics_block)
    pieces.append(show_page_line)
    pieces.append(subscribe_line)
    if discovery_line:
        pieces.append(discovery_line)
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
    if footage_attribution:
        cleaned = [line.strip() for line in footage_attribution
                   if line.strip()]
        if cleaned:
            pieces.append("Footage:\n" + "\n".join(cleaned))
    disclosure = (config.youtube.synthetic_disclosure or "").strip()
    if disclosure:
        pieces.append(disclosure)
    pinned = build_pinned_comment_text(
        config, hook=hook, episode_num=episode_num, today_str=today_str,
        rss_link=rss_link, audio_url=audio_url,
    )
    if pinned:
        pieces.append("—\nSuggested pinned comment:\n" + pinned)

    # Final safety strip — YouTube rejects any description containing
    # ``<`` or ``>`` with HTTP 400 ``invalidDescription``. ``_strip_markdown``
    # already cleans the body, but the hook + chapter titles flow into
    # the description verbatim, so we belt-and-braces strip again here.
    description = "\n\n".join(pieces).strip().replace("<", "").replace(">", "")
    description = _truncate(description, YOUTUBE_DESC_MAX)

    # Per-episode entity tags: prepend the day's specific entities (from the
    # hook) ahead of the show's static tags, so each upload's tag set reflects
    # its actual topic. Applies to any YouTube-enabled show.
    try:
        from engine.shorts_hashtags import extract_entity_phrases
        _entity_tags = extract_entity_phrases(
            hook, show_keywords=list(getattr(config, "keywords", []) or []),
            max_phrases=8,
        )
    except Exception:  # noqa: BLE001 — tags must never block an upload
        _entity_tags = []
    tags = _build_tags(
        _entity_tags + list(config.youtube.tags or []),
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
    optimized_title: Optional[str] = None,
    channel: str = "en",
    variant: str = "",
) -> Dict:
    """Assemble the YouTube metadata payload for a Shorts upload.

    Title gets ``#Shorts`` appended (the most reliable way to get the
    auto-classifier to treat the upload as a Short). The description is
    deliberately brief so the disclosure footer remains visible above
    the "Show more" fold on mobile. *optimized_title* (from
    ``engine.youtube_titles``), when present, is used as the headline in
    place of the spoken hook.
    """
    rss_title = (
        getattr(config.publishing, "rss_title", "")
        or getattr(config, "name", "")
    )
    if optimized_title and optimized_title.strip():
        headline = optimized_title.strip()
    elif hook:
        headline = hook.strip()
    else:
        headline = f"Ep {episode_num} highlight"
    # Same front-loaded builder as long-form; keeps the #Shorts classifier
    # hint even when the headline is long.
    title = _build_seo_title(headline, rss_title, suffix="#Shorts")

    # Hashtags immediately after the headline so the first 3 become
    # clickable topic links above the Shorts title (discovery lever).
    from engine.shorts_hashtags import extract_hashtags, format_hashtag_line
    extracted = extract_hashtags(
        hook,
        show_keywords=list(getattr(config, "keywords", []) or []),
        max_hashtags=5,
    )
    hashtag_line = format_hashtag_line(extracted, ("#Shorts", "#podcast"))

    pieces: List[str] = [headline]
    if hashtag_line:
        pieces.append(hashtag_line)
    if long_form_url:
        pieces.append(f"▶ Full episode: {long_form_url}")
    base_url = getattr(config.publishing, "base_url",
                       "https://nerranetwork.com").rstrip("/")
    rss_link = getattr(config.publishing, "rss_link", "") or base_url
    # Funnel-tagged destination (see engine/funnel.py). ``variant`` rides
    # in the campaign id so the Shorts motion A/B can be read straight
    # out of GA4 without a second join.
    from engine import funnel as _funnel

    utm_link = _funnel.episode_link(
        _funnel.destination_for(config, channel=channel) or rss_link,
        getattr(config, "slug", ""), episode_num,
        channel=channel, kind="short", variant=variant,
        placement=_funnel.PLACEMENT_DESCRIPTION,
    ) or rss_link
    pieces.append(f"🌐 Show page: {rss_link}")
    pieces.append(f"Subscribe to the podcast: {utm_link}")
    disclosure = (config.youtube.synthetic_disclosure or "").strip()
    if disclosure:
        pieces.append(disclosure)

    # Same ``invalidDescription`` defense as build_long_form_metadata —
    # YouTube rejects ``<`` / ``>`` even though Shorts hasn't tripped
    # this in production yet (the headline is the only user-supplied
    # field and hooks rarely contain angle brackets). Belt-and-braces.
    description = "\n\n".join(pieces).strip().replace("<", "").replace(">", "")
    description = _truncate(description, YOUTUBE_DESC_MAX)

    try:
        from engine.shorts_hashtags import extract_entity_phrases
        _entity_tags = extract_entity_phrases(
            hook, show_keywords=list(getattr(config, "keywords", []) or []),
            max_phrases=8,
        )
    except Exception:  # noqa: BLE001
        _entity_tags = []
    tags = _build_tags(
        _entity_tags + list(config.youtube.tags or []) + ["shorts", "podcast clip"],
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
