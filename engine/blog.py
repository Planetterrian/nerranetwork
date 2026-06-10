"""Blog post generation from episode digest markdown.

Converts podcast episode digests (markdown) into beautiful static HTML blog
posts with SEO metadata, structured data, and source attribution. Each show
gets its own blog with per-show branding.

Public API:
  - extract_blog_metadata(): parse episode markdown for title, date, etc.
  - clean_digest_for_blog(): strip podcast-only formatting
  - convert_md_to_blog_html(): markdown → semantic HTML body
  - generate_blog_post_html(): full pipeline → rendered HTML page
  - generate_blog_index_html(): listing page for all blog posts
  - generate_blog_rss(): blog-specific RSS feed (no audio)
"""

from __future__ import annotations

import json
import logging
import re
from datetime import datetime
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Metadata extraction
# ---------------------------------------------------------------------------

# Date patterns found in episode markdowns
_DATE_PATTERNS = [
    # **Date:** March 22, 2026
    re.compile(r"\*\*Date:\*\*\s*(.+)"),
    # **Дата:** March 14, 2026  (Russian shows)
    re.compile(r"\*\*Дата:\*\*\s*(.+)"),
]

# Hook patterns
_HOOK_PATTERNS = [
    re.compile(r"\*\*HOOK:\*\*\s*(.+)"),
    re.compile(r"\*\*ЗАГОЛОВОК:\*\*\s*(.+)"),
    re.compile(r"\*\*Theme:\*\*\s*(.+)"),
    re.compile(r"\*\*Тема:\*\*\s*(.+)"),
    # PR #292: ``promote_hook_to_blockquote`` wraps the post-scrub hook
    # as ``> **<text>**``. Match that on its own line so blogs / blog
    # listings still find the right hook after the canonical scrub
    # strips ``**HOOK:**``.
    re.compile(r"^>\s*\*\*([^*]+(?:\*[^*]+)*?)\*\*\s*$"),
]

# Episode number from filename: ..._Ep414_20260322.md
_EPISODE_RE = re.compile(r"Ep(\d+)")

# Date from filename: ..._20260322.md → (2026, 03, 22)
_FILENAME_DATE_RE = re.compile(r"(\d{4})(\d{2})(\d{2})\.md$")

# Source URLs in digest text
# Supports both bare URLs and Markdown links: Source: https://... or Source: [text](https://...)
_SOURCE_URL_RE = re.compile(r"Source:\s*(?:\[.*?\]\()?(https?://[^\s\)]+)")

# Date string → datetime
_DATE_FORMATS = [
    "%B %d, %Y",      # March 22, 2026
    "%b %d, %Y",      # Mar 22, 2026
    "%Y-%m-%d",        # 2026-03-22
]


def extract_blog_metadata(
    md_text: str,
    show_slug: str,
    filename: str,
    file_path: Optional[Path] = None,
) -> dict:
    """Parse episode markdown and return blog metadata dict.

    Returns dict with keys: title, date, date_iso, episode_num, hook,
    source_urls, show_slug, word_count, reading_time_min.
    """
    lines = md_text.split("\n")
    title = ""
    date_str = ""
    hook = ""
    parsed_date: Optional[datetime] = None

    for line in lines[:20]:  # metadata is always in the first ~20 lines
        stripped = line.strip()

        # Title: first heading (# Heading format)
        if not title and stripped.startswith("# "):
            title = stripped[2:].strip()

        # Date
        if not date_str:
            for pat in _DATE_PATTERNS:
                m = pat.search(stripped)
                if m:
                    date_str = m.group(1).strip()
                    break

        # Hook
        if not hook:
            for pat in _HOOK_PATTERNS:
                m = pat.search(stripped)
                if m:
                    raw = m.group(1).strip()
                    # Strip inline HTML (defense — listing template runs
                    # under ``autoescape=False`` and a stray `<table>` from
                    # a legacy episode would tear the page apart).
                    raw = re.sub(r"<[^>]+>", "", raw)
                    hook = raw
                    break

    # Fallback: some digests use **Bold Title** instead of # Heading.
    # Variants seen: **Title**, **# Title — Subtitle**, **TITLE**
    if not title:
        for line in lines[:5]:
            stripped = line.strip()
            # Skip lines that are metadata (HOOK:, Date:, etc.)
            if any(stripped.startswith(p) for p in ("**HOOK:", "**Date:", "**Дата:", "**ЗАГОЛОВОК:", "**Theme:", "**Тема:")):
                continue
            m = re.match(r"^\*\*#?\s*([^*]+?)\*\*\s*$", stripped)
            if m:
                title = m.group(1).strip()
                # Clean up "Title — Subtitle" to just "Title"
                if " — " in title and title.split(" — ")[0].strip():
                    title = title.split(" — ")[0].strip()
                break

    # Parse date string
    if date_str:
        for fmt in _DATE_FORMATS:
            try:
                parsed_date = datetime.strptime(date_str, fmt)
                break
            except ValueError:
                continue

    # Fallback: extract date from filename (e.g., Ep046_20260328.md)
    if not parsed_date:
        fd = _FILENAME_DATE_RE.search(filename)
        if fd:
            try:
                parsed_date = datetime(int(fd.group(1)), int(fd.group(2)), int(fd.group(3)))
                date_str = parsed_date.strftime("%B %d, %Y")
            except ValueError:
                pass

    # Last resort: use file modification time so blog RSS always has a pubDate
    if not parsed_date and file_path is not None:
        try:
            mtime = Path(file_path).stat().st_mtime
            parsed_date = datetime.fromtimestamp(mtime)
            date_str = parsed_date.strftime("%B %d, %Y")
            logger.debug("Using file mtime as date fallback for %s", filename)
        except (OSError, ValueError):
            pass

    # Episode number from filename
    ep_match = _EPISODE_RE.search(filename)
    episode_num = int(ep_match.group(1)) if ep_match else 0

    # Fallback: use hook as title (truncated) — much better than generic show name
    if not title and hook:
        title = hook[:80] + ("..." if len(hook) > 80 else "")

    # Fallback: derive hook from first substantive content paragraph
    if not hook:
        for line in lines:
            stripped = line.strip()
            # Skip blank lines, headings, metadata, separators
            if not stripped or len(stripped) < 20:
                continue
            if stripped.startswith(("#", "**Date:", "**Дата:", "**HOOK:", "**ЗАГОЛОВОК:",
                                    "**Theme:", "**Тема:",
                                    # Tesla price-line variants — never the hook.
                                    "**REAL-TIME TSLA price:", "**TSLA today:",
                                    # Markdown blockquote — already handled by the
                                    # blockquote pattern in _HOOK_PATTERNS; if we
                                    # got here it didn't match (multiline / weird
                                    # formatting) and we should ignore rather than
                                    # leak a literal ">" into the preview.
                                    ">",
                                    # Inline HTML (e.g. legacy Tesla episodes
                                    # whose canonical .md still has the inline
                                    # <table> for the TSLA price block) —
                                    # `autoescape=False` would inject the raw
                                    # HTML into the listing card and break the
                                    # page structure.
                                    "<",
                                    "━", "─", "═", "---", "***")):
                continue
            if all(c in "━─═" for c in stripped):
                continue
            # Lines with internal `**...**` bold are decorations / show
            # subtitles ("🌍 **Planetterrian Daily** - Science, Longevity
            # & Health Discoveries"), never the hook prose. The hook is
            # always plain prose without internal bold spans.
            if re.search(r"\*\*[^*]+\*\*", stripped) and not re.fullmatch(
                r"\*\*[^*]+\*\*", stripped
            ):
                continue
            # Found a content paragraph — use it as hook
            # Strip markdown formatting for clean display
            clean = re.sub(r"\*\*(.+?)\*\*", r"\1", stripped)
            clean = re.sub(r"\*(.+?)\*", r"\1", clean)
            clean = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", clean)
            # Defense-in-depth: drop any inline HTML so legacy episodes
            # whose canonical .md still has raw `<...>` tags can never
            # corrupt the listing page (autoescape=False).
            clean = re.sub(r"<[^>]+>", "", clean)
            hook = clean[:200] + ("..." if len(clean) > 200 else "")
            break

    # Source URLs
    source_urls = _SOURCE_URL_RE.findall(md_text)

    # Word count and reading time
    word_count = len(md_text.split())
    reading_time_min = max(1, round(word_count / 220))

    return {
        "title": title,
        "date": date_str,
        "date_iso": parsed_date.strftime("%Y-%m-%d") if parsed_date else "",
        "date_obj": parsed_date,
        "episode_num": episode_num,
        "hook": hook,
        "source_urls": source_urls,
        "show_slug": show_slug,
        "word_count": word_count,
        "reading_time_min": reading_time_min,
        "filename": filename,
    }


# ---------------------------------------------------------------------------
# Markdown cleaning
# ---------------------------------------------------------------------------

def clean_digest_for_blog(md_text: str) -> str:
    """Strip podcast-specific formatting from digest markdown.

    Removes HOOK: labels, unicode box separators, and other podcast-only
    markers while preserving all substantive content.
    """
    lines = md_text.split("\n")
    cleaned = []
    skip_hook_line = False

    for line in lines:
        stripped = line.strip()

        # Remove unicode box-drawing separators
        if stripped and all(c in "━─═" for c in stripped):
            cleaned.append("")  # blank line as section break
            continue

        # Remove HOOK: / ЗАГОЛОВОК: label prefix but keep the text
        for pat in _HOOK_PATTERNS:
            m = pat.match(stripped)
            if m:
                cleaned.append(f"*{m.group(1)}*")
                skip_hook_line = True
                break
        if skip_hook_line:
            skip_hook_line = False
            continue

        # Remove the trailing social media CTA line
        if stripped.startswith("Hey, let me know what you think"):
            continue
        if stripped.startswith("let me know what you think"):
            continue

        cleaned.append(line)

    return "\n".join(cleaned)


# ---------------------------------------------------------------------------
# Markdown → HTML conversion
# ---------------------------------------------------------------------------

def _slugify(text: str) -> str:
    """Convert heading text to a URL-safe slug for anchor IDs."""
    slug = text.lower()
    slug = re.sub(r"[^\w\s-]", "", slug)
    slug = re.sub(r"[\s_]+", "-", slug)
    slug = re.sub(r"-+", "-", slug)
    return slug.strip("-")


def _md_inline(text: str) -> str:
    """Convert inline markdown (bold, italic, links, code) to HTML."""
    # Inline code (before bold/italic to avoid conflicts)
    text = re.sub(r"`(.+?)`", r"<code>\1</code>", text)
    # Bold
    text = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", text)
    # Italic
    text = re.sub(r"\*(.+?)\*", r"<em>\1</em>", text)
    # Links
    text = re.sub(
        r"\[([^\]]+)\]\(([^)]+)\)",
        r'<a href="\2" target="_blank" rel="noopener">\1</a>',
        text,
    )
    # Bare URLs on Source: / Source/Post: lines — render as hover-card
    # citation pill (Phase 3.4 of the May 2026 audit). The pill shows
    # the publisher domain inline; on hover/focus, a CSS-only popover
    # reveals the full URL so readers can verify provenance without
    # leaving the page or chasing a tab.
    #
    # The "Source/Post:" prefix was added to the catch May 14 2026
    # after operator caught raw Google News redirect URLs (the long
    # ``news.google.com/rss/articles/CBMiyg...?oc=5`` token streams)
    # bleeding into the rendered Short Spot block on the Tesla blog
    # because Short Spot uses ``Source/Post:`` not ``Source:``.
    text = re.sub(
        r'((?:Source/Post|Source):\s*)(https?://\S+)',
        lambda m: m.group(1) + _cite_html(m.group(2)),
        text,
    )
    return text


def _domain_from_url(url: str) -> str:
    """Extract display domain from a URL."""
    try:
        parsed = urlparse(url)
        domain = parsed.netloc
        if domain.startswith("www."):
            domain = domain[4:]
        return domain
    except Exception:
        return url


def _cite_html(url: str) -> str:
    """Render a citation as a hover-card pill.

    The visible chip shows the publisher domain; the popover (revealed
    on hover or keyboard focus by the CSS in templates/blog_post.html.j2)
    shows the full URL. Pure CSS — no JavaScript required.

    ``aria-describedby`` ties the pill to the popover so screen readers
    announce the full URL when the pill receives focus.
    """
    domain = _domain_from_url(url)
    return (
        f'<span class="cite">'
        f'<a class="cite-pill" href="{url}" '
        f'target="_blank" rel="noopener" '
        f'aria-describedby="cite-card">{domain}</a>'
        f'<span class="cite-card" id="cite-card" role="tooltip">{url}</span>'
        f'</span>'
    )


def convert_md_to_blog_html(md_text: str) -> tuple[str, list[dict]]:
    """Convert cleaned markdown to semantic HTML body content.

    Returns (html_body, toc_entries) where toc_entries is a list of
    {"id": "slug", "text": "heading text", "level": 2} dicts.
    """
    lines = md_text.split("\n")
    html_parts: list[str] = []
    toc: list[dict] = []
    in_list = False
    list_type = ""  # "ul" or "ol"
    in_code_block = False
    code_block_lines: list[str] = []
    in_blockquote = False

    def close_list():
        nonlocal in_list, list_type
        if in_list:
            html_parts.append(f"</{list_type}>")
            in_list = False
            list_type = ""

    def close_blockquote():
        nonlocal in_blockquote
        if in_blockquote:
            html_parts.append("</blockquote>")
            in_blockquote = False

    for idx, line in enumerate(lines):
        stripped = line.strip()

        # Fenced code blocks
        if stripped.startswith("```"):
            if in_code_block:
                # Close code block
                from html import escape as _html_escape
                html_parts.append("<pre><code>" + _html_escape("\n".join(code_block_lines)) + "</code></pre>")
                code_block_lines = []
                in_code_block = False
            else:
                close_list()
                close_blockquote()
                in_code_block = True
            continue
        if in_code_block:
            code_block_lines.append(line)
            continue

        if not stripped:
            # Look ahead: don't close the list if the next content line
            # continues the same list type (handles blank-line-separated items).
            if in_list:
                next_stripped = ""
                for future in lines[idx + 1:]:
                    ns = future.strip()
                    if ns:
                        next_stripped = ns
                        break
                if list_type == "ol" and re.match(r"^\d+\.\s+", next_stripped):
                    continue
                if list_type == "ul" and next_stripped.startswith("- "):
                    continue
            close_list()
            close_blockquote()
            continue

        # Blockquotes
        if stripped.startswith("> "):
            close_list()
            if not in_blockquote:
                html_parts.append("<blockquote>")
                in_blockquote = True
            html_parts.append(f"<p>{_md_inline(stripped[2:])}</p>")
            continue
        if stripped == ">":
            # Empty blockquote continuation line
            if not in_blockquote:
                html_parts.append("<blockquote>")
                in_blockquote = True
            continue
        # Close blockquote if we hit non-blockquote content
        close_blockquote()

        # Headings — demoted one level so page h1 stays in the template
        if stripped.startswith("### "):
            close_list()
            text = stripped[4:].strip()
            slug = _slugify(text)
            toc.append({"id": slug, "text": text, "level": 4})
            html_parts.append(f'<h4 id="{slug}">{_md_inline(text)}</h4>')
            continue
        if stripped.startswith("## "):
            close_list()
            text = stripped[3:].strip()
            slug = _slugify(text)
            toc.append({"id": slug, "text": text, "level": 3})
            html_parts.append(f'<h3 id="{slug}">{_md_inline(text)}</h3>')
            continue
        if stripped.startswith("# "):
            close_list()
            text = stripped[2:].strip()
            slug = _slugify(text)
            toc.append({"id": slug, "text": text, "level": 2})
            html_parts.append(f'<h2 id="{slug}">{_md_inline(text)}</h2>')
            continue

        # Horizontal rules
        if stripped.startswith("---") or stripped.startswith("***"):
            close_list()
            html_parts.append("<hr>")
            continue

        # Bullet lists
        if stripped.startswith("- "):
            if not in_list or list_type != "ul":
                close_list()
                html_parts.append("<ul>")
                in_list = True
                list_type = "ul"
            html_parts.append(f"<li>{_md_inline(stripped[2:])}</li>")
            continue

        # Numbered lists
        m = re.match(r"^(\d+)\.\s+(.+)", stripped)
        if m:
            content = m.group(2)
            if not in_list or list_type != "ol":
                close_list()
                html_parts.append("<ol>")
                in_list = True
                list_type = "ol"
            html_parts.append(f"<li>{_md_inline(content)}</li>")
            continue

        # Indented continuation (belongs to previous list item)
        if in_list and line.startswith("   "):
            html_parts.append(f"<p class=\"blog-list-cont\">{_md_inline(stripped)}</p>")
            continue

        # Regular paragraph
        close_list()
        html_parts.append(f"<p>{_md_inline(stripped)}</p>")

    close_list()
    close_blockquote()
    # Close any unclosed code block
    if in_code_block and code_block_lines:
        from html import escape as _html_escape
        html_parts.append("<pre><code>" + _html_escape("\n".join(code_block_lines)) + "</code></pre>")
    return "\n".join(html_parts), toc


# ---------------------------------------------------------------------------
# Schema.org JSON-LD
# ---------------------------------------------------------------------------

def _build_jsonld(metadata: dict, show_name: str, blog_url: str,
                   show_config: dict | None = None,
                   *, transcript_url: str = "", audio_url: str = "") -> str:
    """Build Schema.org JSON-LD: BlogPosting + PodcastEpisode (as array).

    PodcastEpisode enables Google's podcast features in Search results, links
    each episode to its PodcastSeries, and surfaces episode number / duration
    in rich results.
    """
    in_language = "ru" if show_config and show_config.get("slug") in ("finansy_prosto", "privet_russian") else "en"

    blog_posting = {
        "@context": "https://schema.org",
        "@type": "BlogPosting",
        "headline": metadata.get("title", ""),
        "description": metadata.get("hook", ""),
        "datePublished": metadata.get("date_iso", ""),
        "wordCount": metadata.get("word_count", 0),
        "articleSection": show_name,
        "inLanguage": in_language,
        "author": {
            "@type": "Organization",
            "name": show_name,
            "url": "https://nerranetwork.com",
        },
        "publisher": {
            "@type": "Organization",
            "name": "Nerra Network",
            "url": "https://nerranetwork.com",
        },
        "url": blog_url,
        "mainEntityOfPage": blog_url,
    }
    if show_config and show_config.get("podcast_image"):
        blog_posting["image"] = f"https://nerranetwork.com/{show_config['podcast_image']}"
    if show_config and show_config.get("meta_keywords"):
        blog_posting["keywords"] = show_config["meta_keywords"]

    podcast_episode = {
        "@context": "https://schema.org",
        "@type": "PodcastEpisode",
        "name": metadata.get("title", ""),
        "description": metadata.get("hook", ""),
        "datePublished": metadata.get("date_iso", ""),
        "url": blog_url,
        "inLanguage": in_language,
        "episodeNumber": metadata.get("episode_num", 0),
    }
    if show_config:
        podcast_episode["partOfSeries"] = {
            "@type": "PodcastSeries",
            "name": show_config.get("name", show_name),
            "url": f"https://nerranetwork.com/{show_config.get('show_page', '')}",
        }
        if show_config.get("podcast_image"):
            podcast_episode["image"] = f"https://nerranetwork.com/{show_config['podcast_image']}"

    # Transcript + audio (supplied by generate_blog_post_html once the TTS
    # transcript has been loaded). Emitted only when present so the JSON stays
    # tight. This is the single canonical PodcastEpisode for the page.
    if transcript_url:
        podcast_episode["transcript"] = transcript_url
    if audio_url:
        podcast_episode["associatedMedia"] = {"@type": "MediaObject", "contentUrl": audio_url}

    # ``ensure_ascii=False`` so Cyrillic show names ("Финансы Просто",
    # "Привет, Русский!") render as readable Unicode in the page source
    # instead of as ``Фи...`` escape sequences. Better for
    # SEO indexing and shareable copy-paste.
    return json.dumps(
        [blog_posting, podcast_episode], indent=2, ensure_ascii=False
    )


# ---------------------------------------------------------------------------
# High-level generators
# ---------------------------------------------------------------------------

def generate_blog_post_html(
    md_text: str,
    metadata: dict,
    show_config: dict,
    template_env,
    *,
    prev_post: Optional[dict] = None,
    next_post: Optional[dict] = None,
    related_posts: Optional[list] = None,
    youtube_url: str = "",
    youtube_short_url: str = "",
) -> str:
    """Generate a complete blog post HTML page from digest markdown.

    Parameters
    ----------
    md_text : str
        Raw episode digest markdown.
    metadata : dict
        Output of extract_blog_metadata().
    show_config : dict
        Show entry from NETWORK_SHOWS.
    template_env :
        Jinja2 Environment.
    prev_post / next_post :
        Optional metadata dicts for prev/next navigation.
    """
    cleaned = clean_digest_for_blog(md_text)
    body_html, toc = convert_md_to_blog_html(cleaned)

    show_slug = show_config["slug"]
    ep_num = metadata.get("episode_num", 0)
    blog_url = f"https://nerranetwork.com/blog/{show_slug}/ep{ep_num:03d}.html"

    # Per-episode title (SEO): digests lead with a "# <Show Name>" heading, so
    # the extracted title is almost always just the show name — which would make
    # every post's <title>, <h1>, and schema headline identical (terrible for
    # per-episode SEO and discovery). Prefer the unique episode hook whenever the
    # extracted title is empty or is just the show name. Fall back to the show
    # name only when there is no hook either.
    _extracted = (metadata.get("title") or "").strip()
    _hook = (metadata.get("hook") or "").strip()
    _show = show_config["name"]
    # Match the show-name fallback without over-reaching: equality or a
    # leading "# <Show Name> — subtitle" heading. Deliberately NOT a bare
    # substring check, so a genuinely unique title that merely *mentions* the
    # show name mid-sentence keeps its own title.
    _is_show_name = (
        not _extracted
        or _extracted == _show
        or _extracted.startswith(_show)
    )
    if _is_show_name and _hook:
        clipped = _hook[:100].rstrip(" .,;:—-")
        metadata["title"] = clipped + ("…" if len(_hook) > 100 else "")
    elif not _extracted:
        metadata["title"] = _show

    # Source domains for display
    source_domains = []
    seen_domains = set()
    for url in metadata.get("source_urls", []):
        domain = _domain_from_url(url)
        if domain not in seen_domains:
            seen_domains.add(domain)
            source_domains.append({"url": url, "domain": domain})

    # Load transcript (TTS script) if available — scan digest dir for
    # a *_Ep{NNN}_*_tts.txt file matching this episode number. The TTS
    # script carries Grok speech tags ([pause], <emphasis>...</emphasis>,
    # etc.) which the audio engine consumes; readers must never see
    # them — strip before handing to the template.
    transcript_text = ""
    try:
        _md_path = metadata.get("_md_path")
        if _md_path:
            _digest_dir = Path(_md_path).parent
            _tts_pattern = f"*_Ep{ep_num:03d}_*_tts.txt"
            _tts_files = sorted(_digest_dir.glob(_tts_pattern))
            if _tts_files:
                from engine.utils import strip_speech_tags
                _raw = _tts_files[-1].read_text(encoding="utf-8").strip()
                transcript_text = strip_speech_tags(_raw)
    except Exception:
        pass  # Non-fatal — transcript is optional

    # Build JSON-LD now that the transcript is known, so the (single, canonical)
    # PodcastEpisode block can carry the transcript + audio links.
    _transcript_url = f"{blog_url}#transcript" if transcript_text else ""
    _audio_url = metadata.get("audio_url", "")
    jsonld = _build_jsonld(
        metadata, show_config["name"], blog_url, show_config,
        transcript_url=_transcript_url, audio_url=_audio_url,
    )

    template = template_env.get_template("blog_post.html.j2")

    from generate_html import _build_all_shows_list, _path_prefix

    path_key = f"blog/{show_slug}/ep{ep_num:03d}.html"

    context = {
        "path_prefix": _path_prefix(path_key),
        "page_title": f"{metadata['title']} — Ep{ep_num} | {show_config['name']} Blog",
        "meta_description": metadata.get("hook", show_config.get("description", "")),
        "meta_keywords": show_config.get("meta_keywords", ""),
        "theme_color": show_config.get("theme_color", ""),
        "og_image": f"https://nerranetwork.com/{show_config.get('podcast_image', '')}",
        "canonical_url": blog_url,
        "show_color": show_config["brand_color"],
        "show_color_dark": show_config.get("brand_color_dark", show_config["brand_color"]),
        "all_shows": _build_all_shows_list(),
        # Blog-specific
        "show_name": show_config["name"],
        "show_slug": show_slug,
        "podcast_image": show_config.get("podcast_image", ""),
        "episode_title": metadata.get("title", ""),
        "episode_num": ep_num,
        "episode_date": metadata.get("date", ""),
        "episode_date_iso": metadata.get("date_iso", ""),
        "hook": metadata.get("hook", ""),
        "reading_time_min": metadata.get("reading_time_min", 1),
        "word_count": metadata.get("word_count", 0),
        "blog_body": body_html,
        "toc": toc,
        "source_domains": source_domains,
        "source_urls": metadata.get("source_urls", []),
        "jsonld": jsonld,
        "prev_post": prev_post,
        "next_post": next_post,
        "rss_file": show_config.get("rss_file", ""),
        "blog_rss_url": f"https://nerranetwork.com/blog_{show_slug}.rss",
        "show_page": show_config.get("show_page", ""),
        "summaries_page": show_config.get("summaries_page", ""),
        # Public story-tracker page for narrative-memory shows (June 2026
        # review: the tracker page was only linked from the show page —
        # linking it from every episode post turns each post into an
        # entry point to the binge surface).
        "narrative_page": (
            show_config.get("show_page", "").replace(".html", "-narrative.html")
            if show_slug in ("tesla", "models_agents", "fascinating_frontiers", "planetterrian")
            and show_config.get("show_page")
            else ""
        ),
        "blog_index_url": f"../../blog/{show_slug}/index.html",
        "tagline": show_config.get("tagline", ""),
        "transcript": transcript_text,
        # PodcastEpisode JSON-LD fields. These were referenced by the template
        # but never supplied, so url/datePublished/contentUrl/transcript all
        # rendered empty. Populate them from the data we already have. The
        # transcript lives inline on this page, so the transcript URL is this
        # page's #transcript anchor (only when a transcript is actually present).
        "page_url": blog_url,
        "date": metadata.get("date_iso", "") or metadata.get("date", ""),
        "audio_url": metadata.get("audio_url", ""),
        "transcript_url": f"{blog_url}#transcript" if transcript_text else "",
        # Russian shows render UI strings (incl. the AI badge) in Russian.
        "_is_ru": show_slug in ("finansy_prosto", "privet_russian"),
        "related_posts": related_posts or [],
        # Use the show's Buttondown newsletter tag when set in
        # NETWORK_SHOWS — falls back to the display name. Russian
        # shows override this with an ASCII transliteration because
        # Buttondown rejects tags with no ASCII letter/number.
        "newsletter_tag": show_config.get("newsletter_tag")
            or show_config["name"],
        "page_lang": "ru" if show_slug in ("finansy_prosto", "privet_russian") else "en",
        # YouTube cross-posting — when present, the template renders a
        # "Watch on YouTube" button next to the existing podcast/summaries CTAs.
        "youtube_url": youtube_url or metadata.get("youtube_url", ""),
        "youtube_short_url": youtube_short_url or metadata.get("youtube_short_url", ""),
        # For structured data in the blog post template (PodcastEpisode JSON-LD).
        # Falls back gracefully so | tojson never receives Undefined.
        "summary": metadata.get("hook", "") or metadata.get("title", ""),
    }

    return template.render(**context)


def generate_blog_index_html(
    posts: list[dict],
    show_config: dict,
    template_env,
) -> str:
    """Generate a blog index/listing page for a show.

    Parameters
    ----------
    posts : list[dict]
        List of metadata dicts (from extract_blog_metadata), newest first.
    show_config : dict
        Show entry from NETWORK_SHOWS.
    template_env :
        Jinja2 Environment.
    """
    from generate_html import _build_all_shows_list, _path_prefix

    show_slug = show_config["slug"]
    blog_url = f"https://nerranetwork.com/blog/{show_slug}/index.html"
    path_key = f"blog/{show_slug}/index.html"

    template = template_env.get_template("blog_index.html.j2")

    context = {
        "path_prefix": _path_prefix(path_key),
        "page_title": f"{show_config['name']} Blog",
        "meta_description": f"Read all {show_config['name']} episodes as blog posts. {show_config.get('description', '')}",
        "meta_keywords": show_config.get("meta_keywords", ""),
        "theme_color": show_config.get("theme_color", ""),
        "og_image": f"https://nerranetwork.com/{show_config.get('podcast_image', '')}",
        "canonical_url": blog_url,
        "show_color": show_config["brand_color"],
        "show_color_dark": show_config.get("brand_color_dark", show_config["brand_color"]),
        "all_shows": _build_all_shows_list(),
        # Blog index specific
        "show_name": show_config["name"],
        "show_slug": show_slug,
        "podcast_image": show_config.get("podcast_image", ""),
        "tagline": show_config.get("tagline", ""),
        "description": show_config.get("description", ""),
        "posts": posts,
        "blog_rss_url": f"https://nerranetwork.com/blog_{show_slug}.rss",
    }

    return template.render(**context)


def generate_network_blog_index_html(
    posts: list[dict],
    show_configs: dict,
    template_env,
) -> str:
    """Generate the network-wide blog index page aggregating all shows.

    Parameters
    ----------
    posts : list[dict]
        All posts across all shows, each with ``show_slug`` set.
        Will be sorted by date (newest first).
    show_configs : dict
        The full NETWORK_SHOWS dict.
    template_env :
        Jinja2 Environment.
    """
    from datetime import date as _date, datetime as _datetime
    from generate_html import _build_all_shows_list, _path_prefix

    # Sort by date_obj descending; normalize to date for consistent comparison
    def _sort_key(p):
        d = p.get("date_obj")
        if isinstance(d, _datetime):
            return d.date()
        if isinstance(d, _date):
            return d
        return _date.min

    sorted_posts = sorted(posts, key=_sort_key, reverse=True)

    # Enrich posts with show metadata for template rendering
    for post in sorted_posts:
        slug = post.get("show_slug", "")
        cfg = show_configs.get(slug, {})
        post["show_name"] = cfg.get("name", slug)
        post["show_color"] = cfg.get("brand_color", "#6B47FF")

    # Build show filter list (only shows that have posts)
    slugs_with_posts = {p.get("show_slug") for p in sorted_posts}
    shows_for_filter = [
        {"slug": cfg["slug"], "name": cfg["name"], "color": cfg["brand_color"]}
        for cfg in show_configs.values()
        if cfg["slug"] in slugs_with_posts
    ]
    shows_for_filter.sort(key=lambda s: s["name"])

    path_key = "blog/index.html"

    template = template_env.get_template("network_blog_index.html.j2")

    context = {
        "path_prefix": _path_prefix(path_key),
        "page_title": "Nerra Network Blog",
        "meta_description": "The latest articles from all Nerra Network podcast shows.",
        "meta_keywords": "podcast, blog, news, AI, technology, finance",
        "theme_color": "",
        "og_image": "https://nerranetwork.com/assets/nerra-logo-icon.svg",
        "canonical_url": "https://nerranetwork.com/blog/index.html",
        "show_color": "",
        "show_color_dark": "",
        "all_shows": _build_all_shows_list(),
        # Network blog specific
        "posts": sorted_posts,
        "shows": shows_for_filter,
        "blog_rss_url": "https://nerranetwork.com/blog.rss",
    }

    return template.render(**context)


# ---------------------------------------------------------------------------
# Blog RSS regeneration
# ---------------------------------------------------------------------------

# Slug → digest subdirectory (only ``tesla`` differs from its slug).
_DIGEST_DIRS = {
    "tesla": "tesla_shorts_time",
    "omni_view": "omni_view",
    "fascinating_frontiers": "fascinating_frontiers",
    "planetterrian": "planetterrian",
    "env_intel": "env_intel",
    "models_agents": "models_agents",
    "models_agents_beginners": "models_agents_beginners",
    "finansy_prosto": "finansy_prosto",
    "modern_investing": "modern_investing",
    "privet_russian": "privet_russian",
    "unintended_consequences": "unintended_consequences",
}


def blog_rss_item_title(meta: dict, show_name: str) -> str:
    """Title for blog RSS items — prefer hook over generic show-name headings."""
    title = (meta.get("title") or "").strip()
    hook = (meta.get("hook") or "").strip()
    if hook and (not title or title == show_name.strip()):
        return hook[:120] + ("..." if len(hook) > 120 else "")
    return title or hook or show_name


def collect_blog_posts_from_digests(
    show_slug: str,
    show_name: str,
    digest_dir: Path,
    *,
    max_files: int = 200,
) -> list[dict]:
    """Build blog-RSS post dicts from committed episode markdown files."""
    if not digest_dir.is_dir():
        return []

    md_files = sorted(digest_dir.glob("*.md"), reverse=True)[:max_files]
    posts: list[dict] = []
    for md_file in md_files:
        try:
            md_text = md_file.read_text(encoding="utf-8")
            meta = extract_blog_metadata(
                md_text, show_slug, md_file.name, file_path=md_file,
            )
            meta["show_slug"] = show_slug
            meta["title"] = blog_rss_item_title(meta, show_name)
            posts.append(meta)
        except Exception as exc:
            logger.warning("Skipping %s for blog RSS: %s", md_file.name, exc)
    return posts


def regenerate_show_blog_rss(
    show_slug: str,
    show_name: str,
    project_root: Path,
    *,
    channel_image: str = "",
) -> Path | None:
    """Regenerate ``blog_{slug}.rss`` from digest markdown on disk."""
    from engine.publisher import update_blog_rss

    digest_dir = project_root / "digests" / _DIGEST_DIRS.get(show_slug, show_slug)
    posts = collect_blog_posts_from_digests(show_slug, show_name, digest_dir)
    if not posts:
        logger.warning("No blog posts found for %s — skipping blog RSS", show_slug)
        return None

    rss_path = project_root / f"blog_{show_slug}.rss"
    update_blog_rss(
        rss_path,
        posts,
        channel_title=f"{show_name} Blog",
        channel_link=f"https://nerranetwork.com/blog/{show_slug}/",
        channel_description=f"Blog posts from {show_name} podcast episodes.",
        channel_image=channel_image,
        base_url="https://nerranetwork.com",
        show_slug=show_slug,
    )
    return rss_path


def regenerate_network_blog_rss(
    project_root: Path,
    network_shows: dict,
) -> Path | None:
    """Regenerate aggregated ``blog.rss`` across all shows."""
    from engine.publisher import update_blog_rss

    all_posts: list[dict] = []
    for slug, cfg in network_shows.items():
        show_name = cfg.get("name", slug)
        digest_dir = project_root / "digests" / _DIGEST_DIRS.get(slug, slug)
        for meta in collect_blog_posts_from_digests(slug, show_name, digest_dir):
            all_posts.append(meta)

    if not all_posts:
        logger.warning("No posts for network blog RSS")
        return None

    rss_path = project_root / "blog.rss"
    update_blog_rss(
        rss_path,
        all_posts,
        channel_title="Nerra Network — Blog",
        channel_link="https://nerranetwork.com/blog/",
        channel_description="Blog posts from all Nerra Network podcast shows.",
        channel_image="assets/nerra-logo-icon.svg",
        base_url="https://nerranetwork.com",
        sort_by_date=True,
    )
    return rss_path


def regenerate_blog_rss_for_show_slug(
    show_slug: str,
    project_root: Path,
) -> Path | None:
    """Regenerate per-show (+ network) blog RSS using ``NETWORK_SHOWS`` metadata."""
    try:
        from generate_html import NETWORK_SHOWS
    except ImportError:
        logger.warning("generate_html not importable — cannot regenerate blog RSS")
        return None

    if show_slug not in NETWORK_SHOWS:
        return None

    cfg = NETWORK_SHOWS[show_slug]
    per_show = regenerate_show_blog_rss(
        show_slug,
        cfg["name"],
        project_root,
        channel_image=cfg.get("podcast_image", ""),
    )
    regenerate_network_blog_rss(project_root, NETWORK_SHOWS)
    return per_show
