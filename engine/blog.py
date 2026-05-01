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
]

# Episode number from filename: ..._Ep414_20260322.md
_EPISODE_RE = re.compile(r"Ep(\d+)")

# Date from filename: ..._20260322.md → (2026, 03, 22)
_FILENAME_DATE_RE = re.compile(r"(\d{4})(\d{2})(\d{2})\.md$")

# Source URLs in digest text
_SOURCE_URL_RE = re.compile(r"Source:\s*(https?://\S+)")

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
                    hook = m.group(1).strip()
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
                                    "**Theme:", "**Тема:", "━", "─", "═", "---", "***")):
                continue
            if all(c in "━─═" for c in stripped):
                continue
            # Found a content paragraph — use it as hook
            # Strip markdown formatting for clean display
            clean = re.sub(r"\*\*(.+?)\*\*", r"\1", stripped)
            clean = re.sub(r"\*(.+?)\*", r"\1", clean)
            clean = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", clean)
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
    # Bare URLs on Source: lines
    text = re.sub(
        r'(Source:\s*)(https?://\S+)',
        lambda m: f'{m.group(1)}<a href="{m.group(2)}" target="_blank" rel="noopener">{_domain_from_url(m.group(2))}</a>',
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
                   show_config: dict | None = None) -> str:
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

    # Final fallback: use show name if no title was extracted from the digest
    if not metadata.get("title"):
        metadata["title"] = show_config["name"]

    jsonld = _build_jsonld(metadata, show_config["name"], blog_url, show_config)

    # Source domains for display
    source_domains = []
    seen_domains = set()
    for url in metadata.get("source_urls", []):
        domain = _domain_from_url(url)
        if domain not in seen_domains:
            seen_domains.add(domain)
            source_domains.append({"url": url, "domain": domain})

    # Load transcript (TTS script) if available — scan digest dir for
    # a *_Ep{NNN}_*_tts.txt file matching this episode number.
    transcript_text = ""
    try:
        _md_path = metadata.get("_md_path")
        if _md_path:
            _digest_dir = Path(_md_path).parent
            _tts_pattern = f"*_Ep{ep_num:03d}_*_tts.txt"
            _tts_files = sorted(_digest_dir.glob(_tts_pattern))
            if _tts_files:
                transcript_text = _tts_files[-1].read_text(encoding="utf-8").strip()
    except Exception:
        pass  # Non-fatal — transcript is optional

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
        "show_page": show_config.get("show_page", ""),
        "summaries_page": show_config.get("summaries_page", ""),
        "blog_index_url": f"../../blog/{show_slug}/index.html",
        "tagline": show_config.get("tagline", ""),
        "transcript": transcript_text,
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
        post["show_color"] = cfg.get("brand_color", "#7C5CFF")

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
