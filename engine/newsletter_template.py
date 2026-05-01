"""Wrap newsletter markdown with a branded HTML hero and footer.

Buttondown renders the ``body`` field as markdown but allows inline
HTML to pass through. We exploit that to wrap each show's
synthesized markdown content with:

  - A hero block at the top (show cover, name, tagline, date pill)
    in the show's brand colour.
  - A footer with "catch up on" CTAs (Listen / Watch on YouTube /
    Read on the blog) plus a tiny Nerra Network credit line.

Email-safe constraints driving the design:

  - Inline styles only — Outlook strips ``<style>`` blocks.
  - Tables for the hero + footer layout (more reliable than
    flexbox/grid in Gmail / Outlook 2019).
  - System font stack for body copy.
  - Hero image served from ``nerranetwork.com`` (already public).
  - All colours hex; no CSS custom properties.
"""

from __future__ import annotations

import datetime
import logging
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


# Network-level fallbacks if a per-show entry is missing a field.
_NETWORK_SITE = "https://nerranetwork.com"
_NETWORK_NAME = "Nerra Network"
_NETWORK_TAGLINE = (
    "Daily AI-narrated podcasts. Editorial by Patrick."
)
_DEFAULT_BRAND = "#7C5CFF"
_DEFAULT_BRAND_DARK = "#4338ca"


def _shows_yaml_dir() -> Path:
    return Path(__file__).resolve().parent.parent / "shows"


def _load_show_branding(slug: str) -> Dict[str, str]:
    """Return the visual + link metadata for a show.

    Pulls primarily from ``generate_html.NETWORK_SHOWS`` (the
    canonical website branding source) and supplements with the YAML
    config for the YouTube playlist URL and newsletter tag. Returns
    safe defaults if anything is missing so the wrapper degrades
    gracefully rather than crashing the send.
    """
    out: Dict[str, str] = {
        "name": slug,
        "tagline": "",
        "show_page": _NETWORK_SITE,
        "summaries_page": _NETWORK_SITE,
        "blog_page": _NETWORK_SITE,
        "cover_url": "",
        "brand_color": _DEFAULT_BRAND,
        "brand_color_dark": _DEFAULT_BRAND_DARK,
        "rss_url": "",
        "youtube_playlist_url": "",
        # Newsletter-specific branding bits. ``short_label`` and ``emoji``
        # feed the subject-line composer; ``newsletter_start_date`` lets
        # us derive a per-show issue number deterministically without
        # storing mutable state.
        "short_label": "",
        "emoji": "",
        "newsletter_start_date": "",
        "requires_financial_disclaimer": "false",
    }

    # Lazy import to avoid pulling jinja into engine layer at import
    # time — generate_html is the website-script layer.
    try:
        from generate_html import NETWORK_SHOWS  # type: ignore
    except Exception as exc:
        logger.warning("Could not import NETWORK_SHOWS: %s", exc)
        NETWORK_SHOWS = {}  # type: ignore

    cfg = (NETWORK_SHOWS or {}).get(slug, {})
    if cfg:
        out["name"] = cfg.get("name", out["name"])
        out["tagline"] = cfg.get("tagline", "")
        out["brand_color"] = cfg.get("brand_color", out["brand_color"])
        out["brand_color_dark"] = cfg.get(
            "brand_color_dark", out["brand_color"]
        )
        if cfg.get("podcast_image"):
            out["cover_url"] = f"{_NETWORK_SITE}/{cfg['podcast_image']}"
        if cfg.get("show_page"):
            out["show_page"] = f"{_NETWORK_SITE}/{cfg['show_page']}"
        if cfg.get("summaries_page"):
            out["summaries_page"] = f"{_NETWORK_SITE}/{cfg['summaries_page']}"
        if cfg.get("rss_file"):
            out["rss_url"] = f"{_NETWORK_SITE}/{cfg['rss_file']}"
        out["blog_page"] = f"{_NETWORK_SITE}/blog/{slug}/index.html"

    # YouTube playlist URL + newsletter branding bits — read straight
    # from the show YAML (with _defaults.yaml as the fallback) so we
    # don't double-source it. Fail-soft if the YAML is missing.
    try:
        import yaml as _yaml

        defaults_path = _shows_yaml_dir() / "_defaults.yaml"
        defaults = (
            _yaml.safe_load(defaults_path.read_text(encoding="utf-8")) or {}
            if defaults_path.exists() else {}
        )

        yaml_path = _shows_yaml_dir() / f"{slug}.yaml"
        data: Dict[str, Any] = {}
        if yaml_path.exists():
            data = _yaml.safe_load(yaml_path.read_text(encoding="utf-8")) or {}

        yt = data.get("youtube") or {}
        playlist_id = (yt.get("podcast_playlist_id") or "").strip()
        if playlist_id:
            out["youtube_playlist_url"] = (
                f"https://www.youtube.com/playlist?list={playlist_id}"
            )

        # Merge newsletter block: per-show overrides defaults.
        nl_default = defaults.get("newsletter") or {}
        nl_show = data.get("newsletter") or {}
        for key in (
            "short_label", "emoji", "newsletter_start_date",
        ):
            val = nl_show.get(key) or nl_default.get(key) or ""
            if val:
                out[key] = str(val)
        # Bool flag: stored as str so the dict stays Dict[str, str].
        flag = nl_show.get(
            "requires_financial_disclaimer",
            nl_default.get("requires_financial_disclaimer", False),
        )
        out["requires_financial_disclaimer"] = "true" if flag else "false"
    except Exception as exc:  # pragma: no cover — defensive
        logger.warning("Could not read newsletter branding for %s: %s", slug, exc)

    return out


def _format_week_pill(week_ending: Optional[datetime.date]) -> str:
    """Pretty week-range string for the hero pill."""
    if week_ending is None:
        week_ending = datetime.date.today()
    week_start = week_ending - datetime.timedelta(days=6)
    if week_start.month == week_ending.month:
        return (
            f"Weekly digest · {week_start.strftime('%b %-d')}–"
            f"{week_ending.strftime('%-d, %Y')}"
        )
    return (
        f"Weekly digest · {week_start.strftime('%b %-d')} – "
        f"{week_ending.strftime('%b %-d, %Y')}"
    )


def _format_date_pill(label: str, date: datetime.date) -> str:
    """Pretty single-date string for the hero pill (daily newsletter)."""
    return f"{label} · {date.strftime('%b %-d, %Y')}"


def _build_hero_html(show: Dict[str, str], pill_text: str) -> str:
    """Render the email's hero block as inline-styled HTML."""
    name = show["name"]
    tagline = show["tagline"]
    cover_url = show["cover_url"]
    brand = show["brand_color"]
    brand_dark = show["brand_color_dark"]

    # Descriptive alt text per WCAG: identifies the show, not the file.
    # Tagline (when present) gives screen-reader users the same context
    # the cover communicates visually.
    alt_text = name
    if tagline:
        alt_text = f"{name} — {tagline}"
    # Strip any double-quotes from alt (guards against odd YAML data
    # breaking the attribute).
    alt_text = alt_text.replace('"', "")
    cover_img = (
        f'<img src="{cover_url}" alt="{alt_text}" '
        f'width="120" height="120" '
        f'style="display:block;border-radius:18px;width:120px;'
        f'height:120px;object-fit:cover;margin:0 auto 16px;'
        f'box-shadow:0 8px 24px rgba(0,0,0,0.25);" />'
        if cover_url else ""
    )

    return (
        f'<table role="presentation" width="100%" cellpadding="0" '
        f'cellspacing="0" border="0" '
        f'style="background:linear-gradient(135deg,{brand} 0%,'
        f'{brand_dark} 100%);">'
        f'<tr><td align="center" '
        f'style="padding:40px 24px 32px;'
        f'font-family:-apple-system,BlinkMacSystemFont,\'Segoe UI\','
        f'Roboto,Helvetica,Arial,sans-serif;">'
        f'{cover_img}'
        f'<h1 style="color:#ffffff;font-size:28px;font-weight:700;'
        f'margin:0 0 8px;line-height:1.2;letter-spacing:-0.01em;">'
        f'{name}</h1>'
        + (
            f'<p style="color:rgba(255,255,255,0.92);font-size:15px;'
            f'margin:0 0 20px;line-height:1.4;max-width:480px;">'
            f'{tagline}</p>'
            if tagline else ""
        )
        + f'<div style="display:inline-block;background:rgba(0,0,0,0.25);'
        f'color:#ffffff;font-size:12px;font-weight:600;'
        f'padding:6px 14px;border-radius:100px;'
        f'letter-spacing:0.04em;text-transform:uppercase;">'
        f'{pill_text}</div>'
        f'</td></tr></table>'
    )


_DARK_MODE_STYLE = """\
<style>
  /* Dark-mode overrides for clients that respect prefers-color-scheme
   * (Apple Mail iOS/macOS, some Outlook versions). Gmail/Outlook 365
   * apply their own algorithmic dark mode and ignore <style>; for those
   * we rely on inline styles on the gradient hero looking acceptable
   * either way (the brand-color background dominates the cell). */
  @media (prefers-color-scheme: dark) {
    body, table, td { background-color:#0f172a !important; }
    body, p, h1, h2, h3, h4, td, span, div { color:#e2e8f0 !important; }
    a { color:#93c5fd !important; }
    /* Soft override on the off-white card backgrounds so they don't
     * shine out against the dark page. */
    table[role=presentation] td[style*='background:#ffffff'],
    table[role=presentation] td[style*='background:#fafafa'],
    table[role=presentation] td[style*='background:#f8fafc'] {
      background-color:#1e293b !important;
    }
  }
</style>
"""


def _build_preheader_html(preheader: str) -> str:
    """Hidden preview-text div for inbox snippets.

    Inboxes show this as the snippet next to the subject line. It must
    be visually hidden (display:none + opacity:0 + max-height:0) but
    present in the DOM so Gmail / Apple Mail picks it up. Trailing
    zero-width-non-joiners pad past short snippets so the inbox doesn't
    bleed body text into the preview.
    """
    if not preheader:
        return ""
    pad = "&nbsp;&zwnj;" * 24
    safe = preheader.replace("<", "&lt;").replace(">", "&gt;")
    return (
        '<div style="display:none;font-size:1px;color:#fafafa;'
        'line-height:1px;max-height:0;max-width:0;opacity:0;overflow:hidden;'
        'mso-hide:all;">'
        f'{safe}{pad}'
        '</div>'
    )


def _build_by_the_numbers_html(
    stats: Optional[List[Dict[str, str]]], brand: str
) -> str:
    """Render up to 3 stat tiles right under the hero, before the body."""
    if not stats:
        return ""
    cells: List[str] = []
    for item in stats[:3]:
        value = (item.get("value") or "").strip()
        label = (item.get("label") or "").strip()
        if not value or not label:
            continue
        v_safe = value.replace("<", "&lt;").replace(">", "&gt;")
        l_safe = label.replace("<", "&lt;").replace(">", "&gt;")
        cells.append(
            f'<td align="center" valign="top" '
            f'style="padding:8px 6px;width:33%;">'
            f'<div style="font-size:22px;font-weight:700;color:{brand};'
            f'line-height:1.1;letter-spacing:-0.01em;">{v_safe}</div>'
            f'<div style="font-size:11px;color:#64748b;'
            f'text-transform:uppercase;letter-spacing:0.06em;'
            f'margin-top:4px;line-height:1.3;">{l_safe}</div>'
            f'</td>'
        )
    if not cells:
        return ""
    return (
        '<table role="presentation" width="100%" cellpadding="0" '
        'cellspacing="0" border="0" '
        'style="background:#ffffff;border-bottom:1px solid #e2e8f0;">'
        '<tr><td align="center" '
        'style="padding:18px 16px;'
        'font-family:-apple-system,BlinkMacSystemFont,\'Segoe UI\','
        'Roboto,Helvetica,Arial,sans-serif;">'
        '<div style="font-size:11px;color:#94a3b8;font-weight:600;'
        'text-transform:uppercase;letter-spacing:0.08em;'
        'margin-bottom:10px;">By the numbers</div>'
        '<table role="presentation" width="100%" cellpadding="0" '
        'cellspacing="0" border="0" style="max-width:480px;margin:0 auto;">'
        f'<tr>{"".join(cells)}</tr>'
        '</table>'
        '</td></tr></table>'
    )


def _build_financial_disclaimer_html() -> str:
    """Styled callout box for shows that discuss financial topics.

    Replaces the old in-prose ``**FINANCIAL DISCLAIMER:**`` line with
    a visually-distinct amber sidebar so it doesn't get lost in the
    body and is unmistakable to subscribers.
    """
    return (
        '<table role="presentation" width="100%" cellpadding="0" '
        'cellspacing="0" border="0" '
        'style="background:#FFF7ED;border-left:4px solid #F59E0B;">'
        '<tr><td '
        'style="padding:12px 16px;'
        'font-family:-apple-system,BlinkMacSystemFont,\'Segoe UI\','
        'Roboto,Helvetica,Arial,sans-serif;'
        'font-size:13px;color:#78350F;line-height:1.5;">'
        '<strong>Heads up:</strong> Educational and entertainment only. '
        'Not financial advice. Any trades discussed are simulated. '
        'Always do your own research.'
        '</td></tr></table>'
    )


def _build_p_s_html(p_s: str, brand: str) -> str:
    """Render the P.S. block between the body and the footer.

    P.S. is one of the most-read elements of any newsletter; we render
    it in its own card with a brand-colored left border so it visually
    separates from the body and footer.
    """
    if not p_s:
        return ""
    safe = p_s.replace("<", "&lt;").replace(">", "&gt;")
    return (
        '<table role="presentation" width="100%" cellpadding="0" '
        'cellspacing="0" border="0" style="background:#ffffff;">'
        '<tr><td '
        'style="padding:8px 24px 24px;'
        'font-family:-apple-system,BlinkMacSystemFont,\'Segoe UI\','
        'Roboto,Helvetica,Arial,sans-serif;">'
        f'<p style="font-size:15px;line-height:1.6;color:#0f172a;'
        f'margin:0;border-left:3px solid {brand};padding:4px 0 4px 14px;">'
        f'<strong style="color:{brand};letter-spacing:0.04em;">P.S.</strong>'
        f'&nbsp;{safe}</p>'
        '</td></tr></table>'
    )


def _strip_repeated_show_title(body_md: str, show_name: str) -> str:
    """Drop a leading ``**<Show> Weekly**`` / ``# <Show>`` line if the LLM
    repeats the show title at the top of the body.

    The branded hero already shows the title in big text, so a body
    that opens with the title again is visual duplication. Idempotent
    with the synthesizer's own strip — safe to call twice.
    """
    if not body_md:
        return body_md
    lines = body_md.lstrip().split("\n")
    first = lines[0].strip()
    show_lower = show_name.lower().strip()
    norm = re.sub(r"^[#*\s_]+|[#*\s_]+$", "", first).lower().strip()
    norm = re.sub(r"\s+(weekly|weekly digest|digest)$", "", norm).strip()
    if norm == show_lower or norm.startswith(show_lower + " "):
        return "\n".join(lines[1:]).lstrip()
    return body_md


_MD_TABLE_HEADER_RE = re.compile(
    r"""
    ^[ \t]*(?:\|[^\n]*\|)[ \t]*\n          # header row (pipe-bounded)
    [ \t]*(?:\|[ \t]*:?-+:?[ \t]*)+\|[ \t]*\n  # separator row (---|---)
    """,
    re.VERBOSE | re.MULTILINE,
)


def _md_table_cells(line: str) -> List[str]:
    """Split a markdown table row into stripped cell strings."""
    # Drop leading/trailing pipes, then split.
    s = line.strip()
    if s.startswith("|"):
        s = s[1:]
    if s.endswith("|"):
        s = s[:-1]
    return [c.strip() for c in s.split("|")]


def _render_md_inline_to_html(text: str) -> str:
    """Convert a small subset of inline markdown to HTML for table cells.

    Handles ``**bold**``, ``*italic*``, and ``[label](url)``. Anything
    else is HTML-escaped. Email-only — keep simple, don't pull a full
    markdown engine into an email-template module.
    """
    escaped = (
        text.replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
    )
    # Links: [label](url)
    escaped = re.sub(
        r"\[([^\]]+)\]\(([^)]+)\)",
        r'<a href="\2" style="color:#2563eb;">\1</a>',
        escaped,
    )
    # Bold
    escaped = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", escaped)
    # Italic
    escaped = re.sub(r"\*([^*]+)\*", r"<em>\1</em>", escaped)
    return escaped


def render_html_table(
    headers: List[str], rows: List[List[str]], *, brand: str = "#7C5CFF"
) -> str:
    """Render a mobile-friendly inline-styled HTML table.

    Email clients vary wildly in their CSS support — we use ``<table>``
    with ``border-collapse:collapse`` (works everywhere), alternating row
    backgrounds for scanability, and a brand-colored header band. Outlook
    2019+ honors ``border-collapse``; older versions degrade gracefully.

    Each cell content is rendered through the small inline-markdown
    helper so ``**bold**`` and links survive the conversion.
    """
    if not headers or not rows:
        return ""
    head_cells = "".join(
        f'<th align="left" '
        f'style="padding:10px 12px;background:{brand};color:#ffffff;'
        f'font-size:12px;font-weight:700;text-transform:uppercase;'
        f'letter-spacing:0.04em;border:1px solid {brand};">'
        f'{_render_md_inline_to_html(h)}</th>'
        for h in headers
    )
    body_rows: List[str] = []
    for i, row in enumerate(rows):
        bg = "#ffffff" if i % 2 == 0 else "#f8fafc"
        cells = "".join(
            f'<td valign="top" '
            f'style="padding:10px 12px;background:{bg};'
            f'border:1px solid #e2e8f0;font-size:14px;'
            f'color:#0f172a;line-height:1.4;">'
            f'{_render_md_inline_to_html(c)}</td>'
            for c in row
        )
        body_rows.append(f"<tr>{cells}</tr>")
    return (
        '<table role="presentation" width="100%" cellpadding="0" '
        'cellspacing="0" border="0" '
        'style="border-collapse:collapse;margin:14px 0;'
        'font-family:-apple-system,BlinkMacSystemFont,\'Segoe UI\','
        'Roboto,Helvetica,Arial,sans-serif;">'
        f'<thead><tr>{head_cells}</tr></thead>'
        f'<tbody>{"".join(body_rows)}</tbody>'
        '</table>'
    )


def convert_md_tables_to_html(body_md: str, *, brand: str = "#7C5CFF") -> str:
    """Replace markdown tables in *body_md* with inline-styled HTML
    tables.

    Outlook 2019, Yahoo, and ProtonMail all render markdown tables
    inconsistently — many strip the formatting entirely. We pre-render
    them to HTML so they survive any client. Non-table markdown is
    untouched (Buttondown's renderer handles it).
    """
    if not body_md or "|" not in body_md:
        return body_md
    out_lines: List[str] = []
    lines = body_md.split("\n")
    i = 0
    while i < len(lines):
        line = lines[i]
        # Cheap pre-check: is this the start of a possible table? It's
        # a header row if it contains pipes AND the next line is a
        # separator row.
        if "|" in line and i + 1 < len(lines):
            sep = lines[i + 1].strip()
            sep_cells = _md_table_cells(sep) if sep.startswith(
                ("|", ":", "-")
            ) else []
            looks_like_sep = bool(sep_cells) and all(
                re.match(r"^:?-+:?$", c) for c in sep_cells
            )
            if looks_like_sep and "|" in line:
                headers = _md_table_cells(line)
                rows: List[List[str]] = []
                j = i + 2
                while j < len(lines) and "|" in lines[j] and lines[j].strip():
                    rows.append(_md_table_cells(lines[j]))
                    j += 1
                # Pad/truncate rows to header width so the rendered
                # HTML stays well-formed even if the LLM emitted ragged
                # rows.
                w = len(headers)
                rows = [r[:w] + [""] * (w - len(r)) for r in rows]
                out_lines.append(render_html_table(headers, rows, brand=brand))
                i = j
                continue
        out_lines.append(line)
        i += 1
    return "\n".join(out_lines)


def episode_blog_url(slug: str, episode_num: int) -> str:
    """Canonical per-episode permalink on nerranetwork.com.

    Pattern: ``https://nerranetwork.com/blog/<slug>/ep<NNN>.html``.
    Locked in by the static site (see ``blog/<slug>/`` directories).
    """
    return f"{_NETWORK_SITE}/blog/{slug}/ep{int(episode_num):03d}.html"


def episode_link_table(
    episodes: List[Dict[str, Any]], slug: str
) -> str:
    """Render a markdown reference table of episode → URL pairs for the
    LLM prompt context.

    Lets the synthesizer instruct the model to use ``[▶ Episode N
    · {date}]({url})`` whenever it cites an episode in body text,
    without the model hallucinating URLs.
    """
    if not episodes:
        return ""
    lines = ["Episode reference (use these exact URLs when citing episodes):"]
    for ep in episodes:
        num = ep.get("episode_num")
        if num is None:
            continue
        url = episode_blog_url(slug, num)
        date_str = ep.get("date", "")
        lines.append(f"- Episode {num} ({date_str}): {url}")
    return "\n".join(lines)


def _build_featured_episode_html(
    featured: Optional[Dict[str, Any]], show: Dict[str, str]
) -> str:
    """Render the "If you only have 10 minutes" block at top of body.

    *featured* is a dict with at least ``episode_num``, ``hook``, and
    ``date``. We compute the listen URL from ``episode_blog_url``.
    Returns an empty string if no featured episode is provided.
    """
    if not featured:
        return ""
    num = featured.get("episode_num")
    hook = (featured.get("hook") or "").strip()
    date_str = featured.get("date", "")
    if num is None or not hook:
        return ""
    brand = show["brand_color"]
    slug = featured.get("show_slug", "")
    listen = featured.get("listen_url") or (
        episode_blog_url(slug, int(num)) if slug else show["show_page"]
    )
    safe_hook = hook.replace("<", "&lt;").replace(">", "&gt;")
    safe_date = (date_str or "").replace("<", "&lt;").replace(">", "&gt;")
    return (
        '<table role="presentation" width="100%" cellpadding="0" '
        'cellspacing="0" border="0" style="background:#ffffff;">'
        '<tr><td '
        'style="padding:20px 24px 8px;'
        'font-family:-apple-system,BlinkMacSystemFont,\'Segoe UI\','
        'Roboto,Helvetica,Arial,sans-serif;">'
        f'<div style="border:1px solid {brand}33;background:{brand}0a;'
        f'border-radius:12px;padding:18px 18px 16px;">'
        '<div style="font-size:11px;font-weight:700;'
        f'color:{brand};letter-spacing:0.08em;'
        'text-transform:uppercase;margin-bottom:6px;">'
        '🎧 If you only have 10 minutes this week'
        '</div>'
        f'<div style="font-size:17px;font-weight:600;color:#0f172a;'
        f'line-height:1.4;margin:0 0 10px;">'
        f'Episode {num} · {safe_hook}'
        '</div>'
        f'<div style="font-size:12px;color:#64748b;margin:0 0 14px;">'
        f'{safe_date}</div>'
        f'<a href="{listen}" '
        f'style="display:inline-block;background:{brand};color:#ffffff;'
        f'text-decoration:none;font-weight:600;font-size:14px;'
        f'padding:8px 16px;border-radius:8px;">'
        '▶ Listen now</a>'
        '</div></td></tr></table>'
    )


def _build_cross_network_html(
    adjacent_shows: Optional[List[Dict[str, Any]]], brand: str
) -> str:
    """Render the "Across the Nerra Network" cross-promo block.

    *adjacent_shows* is a list of dicts:
        ``{"name": ..., "slug": ..., "emoji": ..., "hook": ..., "url": ...}``

    Renders as a styled card list between the body and the footer.
    Empty input → empty string (the block is opt-out by data, not a
    feature flag).
    """
    if not adjacent_shows:
        return ""
    rows: List[str] = []
    for adj in adjacent_shows[:3]:
        name = (adj.get("name") or "").strip()
        emoji = (adj.get("emoji") or "").strip()
        hook = (adj.get("hook") or "").strip()
        url = (adj.get("url") or "").strip()
        if not name or not hook:
            continue
        n_safe = name.replace("<", "&lt;").replace(">", "&gt;")
        h_safe = hook.replace("<", "&lt;").replace(">", "&gt;")
        prefix = f"{emoji} " if emoji else ""
        if url:
            link_open = (
                f'<a href="{url}" '
                f'style="color:#0f172a;text-decoration:none;'
                f'border-bottom:1px solid {brand};">'
            )
            link_close = "</a>"
        else:
            link_open = link_close = ""
        rows.append(
            '<tr><td '
            'style="padding:10px 0;border-top:1px solid #e2e8f0;'
            'font-size:14px;line-height:1.5;color:#334155;">'
            f'<strong style="color:#0f172a;">{prefix}{link_open}'
            f'{n_safe}{link_close}</strong>'
            f'<span style="color:#64748b;"> — {h_safe}</span>'
            '</td></tr>'
        )
    if not rows:
        return ""
    return (
        '<table role="presentation" width="100%" cellpadding="0" '
        'cellspacing="0" border="0" style="background:#f8fafc;">'
        '<tr><td '
        'style="padding:24px;'
        'font-family:-apple-system,BlinkMacSystemFont,\'Segoe UI\','
        'Roboto,Helvetica,Arial,sans-serif;">'
        '<div style="font-size:11px;font-weight:700;color:#64748b;'
        'letter-spacing:0.08em;text-transform:uppercase;margin-bottom:8px;">'
        '🌐 Across the Nerra Network'
        '</div>'
        '<table role="presentation" width="100%" cellpadding="0" '
        'cellspacing="0" border="0">'
        + "".join(rows) +
        '</table>'
        '</td></tr></table>'
    )


def _build_reply_share_html(
    show: Dict[str, str], *, archive_url: str = ""
) -> str:
    """Render a reply-CTA + share-intents row above the footer CTAs.

    Mailto opens a prefilled message. Twitter/LinkedIn/WhatsApp share
    intents point to the archive_url (the show landing page, since
    Buttondown's per-issue archive URL isn't known until after send).
    """
    name = show["name"]
    brand = show["brand_color"]
    target = (archive_url or show["show_page"]).strip()

    # Pre-encode the share intents (URL-encoded query strings).
    import urllib.parse as _u
    share_text = f"I'm reading {name} this week — give it a listen:"
    twitter = (
        "https://twitter.com/intent/tweet?"
        + _u.urlencode({"text": share_text, "url": target})
    )
    linkedin = (
        "https://www.linkedin.com/sharing/share-offsite/?"
        + _u.urlencode({"url": target})
    )
    whatsapp = (
        "https://wa.me/?"
        + _u.urlencode({"text": f"{share_text} {target}"})
    )

    def _chip(href: str, label: str) -> str:
        return (
            f'<a href="{href}" '
            f'style="display:inline-block;color:{brand};text-decoration:none;'
            f'font-weight:600;font-size:13px;padding:6px 12px;'
            f'margin:2px;border:1px solid {brand}55;border-radius:100px;'
            f'background:#ffffff;">{label}</a>'
        )

    return (
        '<table role="presentation" width="100%" cellpadding="0" '
        'cellspacing="0" border="0" style="background:#ffffff;">'
        '<tr><td align="center" '
        'style="padding:8px 16px 20px;'
        'font-family:-apple-system,BlinkMacSystemFont,\'Segoe UI\','
        'Roboto,Helvetica,Arial,sans-serif;color:#475569;">'
        '<p style="font-size:13px;margin:0 0 10px;line-height:1.5;">'
        '💬 <strong>Reply to this email</strong> — Patrick reads every one.'
        '</p>'
        '<div>'
        + _chip(twitter, "Share on X")
        + _chip(linkedin, "Share on LinkedIn")
        + _chip(whatsapp, "Share on WhatsApp")
        + '</div>'
        '</td></tr></table>'
    )


def _build_footer_html(show: Dict[str, str]) -> str:
    """Render the email's footer block as inline-styled HTML."""
    brand = show["brand_color"]
    name = show["name"]

    def _btn(href: str, label: str) -> str:
        if not href:
            return ""
        return (
            f'<a href="{href}" '
            f'style="display:inline-block;background:{brand};'
            f'color:#ffffff;text-decoration:none;font-weight:600;'
            f'font-size:14px;padding:10px 18px;border-radius:8px;'
            f'margin:4px;font-family:-apple-system,BlinkMacSystemFont,'
            f'\'Segoe UI\',Roboto,Helvetica,Arial,sans-serif;">'
            f'{label}</a>'
        )

    listen = _btn(show["show_page"], "▶ Listen to the podcast")
    watch = _btn(show["youtube_playlist_url"], "📺 Watch on YouTube")
    blog = _btn(show["blog_page"], "📝 Read the blog")

    return (
        f'<table role="presentation" width="100%" cellpadding="0" '
        f'cellspacing="0" border="0" '
        f'style="background:#fafafa;border-top:4px solid {brand};">'
        f'<tr><td align="center" '
        f'style="padding:32px 24px;'
        f'font-family:-apple-system,BlinkMacSystemFont,\'Segoe UI\','
        f'Roboto,Helvetica,Arial,sans-serif;color:#0f172a;">'
        f'<p style="font-size:14px;color:#475569;margin:0 0 16px;">'
        f'Catch up on more {name}:'
        f'</p>'
        f'<div style="line-height:1.8;">'
        f'{listen}{watch}{blog}'
        f'</div>'
        f'<p style="font-size:12px;color:#94a3b8;margin:24px 0 4px;'
        f'line-height:1.5;">'
        f'<a href="{_NETWORK_SITE}" '
        f'style="color:#475569;text-decoration:none;font-weight:600;">'
        f'Nerra Network</a> · '
        f'AI-narrated voice (ElevenLabs) · '
        f'Editorial by Patrick'
        f'</p>'
        f'<p style="font-size:11px;color:#cbd5e1;margin:0;line-height:1.5;">'
        f'You\'re receiving this because you subscribed to {name} on '
        f'<a href="{_NETWORK_SITE}" '
        f'style="color:#94a3b8;text-decoration:underline;">'
        f'nerranetwork.com</a>.'
        f'</p>'
        f'</td></tr></table>'
    )


def compute_issue_number(
    slug: str, send_date: Optional[datetime.date] = None
) -> int:
    """Return a deterministic per-show issue number.

    Derived from ``newsletter.newsletter_start_date`` in the show YAML
    so the count survives rebuilds without state files. Falls back to
    1 if the start date is missing or in the future.

    Daily shows that send weekly newsletters tick once per send (i.e.
    ``floor((send_date - start) / 7) + 1``).
    """
    if send_date is None:
        send_date = datetime.date.today()
    show = _load_show_branding(slug)
    raw = show.get("newsletter_start_date") or ""
    if not raw:
        return 1
    try:
        start = datetime.date.fromisoformat(raw)
    except ValueError:
        logger.warning(
            "Bad newsletter_start_date %r for %s; defaulting to issue 1",
            raw, slug,
        )
        return 1
    if send_date < start:
        return 1
    return ((send_date - start).days // 7) + 1


def build_subject_line(
    slug: str, subject_hook: str, *, send_date: Optional[datetime.date] = None
) -> str:
    """Compose the final email subject from a hook + show short label.

    Format: ``"<hook> · <short_label> <emoji>"``. Falls back to the
    full show name if no short label is configured. Hard-capped at
    100 chars to stay within email-client subject limits.
    """
    show = _load_show_branding(slug)
    short = show.get("short_label") or show.get("name") or slug
    emoji = show.get("emoji") or ""

    hook = (subject_hook or "").strip().rstrip(" .,;:")
    if not hook:
        # No hook from the LLM — degrade to a clean date-stamped fallback.
        when = send_date or datetime.date.today()
        hook = f"This week: {when.strftime('%b %-d')}"

    suffix = f" · {short}".rstrip()
    if emoji:
        suffix += f" {emoji}"
    full = f"{hook}{suffix}"
    if len(full) <= 100:
        return full
    # Trim the hook side; never truncate the show short label.
    headroom = 100 - len(suffix) - 1  # -1 for ellipsis
    if headroom < 10:
        # Pathological case: short_label alone is huge. Just trim the
        # whole thing.
        return full[:100]
    return f"{hook[:headroom].rstrip()}…{suffix}"


def wrap_with_branding(
    slug: str,
    markdown_body: str,
    *,
    week_ending: Optional[datetime.date] = None,
    daily_label: Optional[str] = None,
    daily_date: Optional[datetime.date] = None,
    preheader: str = "",
    by_the_numbers: Optional[List[Dict[str, str]]] = None,
    featured_episode: Optional[Dict[str, Any]] = None,
    p_s: str = "",
    adjacent_shows: Optional[List[Dict[str, Any]]] = None,
    show_reply_share: bool = True,
    requires_financial_disclaimer: bool = False,
) -> str:
    """Wrap *markdown_body* with a branded hero, optional middle blocks,
    and footer.

    The result is a single string suitable for Buttondown's email
    body — markdown in the middle is left untouched, and the inline
    HTML at top/bottom passes through Buttondown's renderer.

    Optional middle blocks (rendered top-to-bottom in this order):

      1. Hidden preheader div (inbox preview text)
      2. Hero (cover, name, tagline, date pill)
      3. By-the-numbers stat tiles
      4. Featured-episode "if you only have 10 minutes" block
      5. Financial disclaimer callout
      6. Markdown body
      7. P.S. block
      8. Cross-network "Across the Nerra Network" module
      9. Reply / share row
      10. Footer (CTAs + Nerra Network credit)

    Pass *week_ending* for weekly newsletters; pass *daily_label* +
    *daily_date* for daily episode newsletters. If neither is set,
    the hero pill falls back to today's date.
    """
    show = _load_show_branding(slug)

    if week_ending is not None:
        pill = _format_week_pill(week_ending)
    elif daily_date is not None:
        pill = _format_date_pill(daily_label or "Today", daily_date)
    else:
        pill = _format_week_pill(None)

    preheader_div = _build_preheader_html(preheader)
    hero = _build_hero_html(show, pill)
    stats_block = _build_by_the_numbers_html(
        by_the_numbers, show["brand_color"]
    )
    # Stamp the slug into the featured-episode dict so the block can
    # build the listen URL even if the caller didn't pre-resolve it.
    featured_with_slug = None
    if featured_episode:
        featured_with_slug = dict(featured_episode)
        featured_with_slug.setdefault("show_slug", slug)
    featured_block = _build_featured_episode_html(featured_with_slug, show)
    disclaimer = (
        _build_financial_disclaimer_html()
        if requires_financial_disclaimer else ""
    )
    p_s_block = _build_p_s_html(p_s, show["brand_color"])
    cross_network = _build_cross_network_html(
        adjacent_shows, show["brand_color"]
    )
    reply_share = (
        _build_reply_share_html(show) if show_reply_share else ""
    )
    footer = _build_footer_html(show)

    # Idempotent strip in case the body still has the show title at top.
    body_clean = _strip_repeated_show_title(
        (markdown_body or "").strip(), show["name"]
    )
    # Pre-render any markdown tables in the body to inline HTML so they
    # survive Outlook / Yahoo / ProtonMail. Non-table markdown is left
    # alone for Buttondown's renderer to handle.
    body_clean = convert_md_tables_to_html(
        body_clean, brand=show["brand_color"]
    )

    # Blocks separated by two blank lines so markdown processors treat
    # them as separate sections. Empty blocks contribute nothing. The
    # dark-mode <style> block goes at the very top so any client that
    # respects @media queries picks it up before parsing the body.
    parts = [
        _DARK_MODE_STYLE,
        preheader_div,
        hero,
        stats_block,
        featured_block,
        disclaimer,
        body_clean,
        p_s_block,
        cross_network,
        reply_share,
        footer,
    ]
    return "\n\n".join(p for p in parts if p) + "\n"
