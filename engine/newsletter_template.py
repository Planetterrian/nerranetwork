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
_DEFAULT_BRAND = "#6B47FF"
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
    """Render the email's hero block as inline-styled HTML.

    Several fixes ship with the May 2026 newsletter spec v2:

    1. **Date pill is a `<table>` with `bgcolor`, not an inline-block
       `<div>` with rgba()**. Outlook desktop (Word renderer) ignores
       both ``rgba()`` and ``display:inline-block`` on `<div>`s, so the
       pill background was failing — leaving white text on the
       gradient (low-contrast on Финансы pink, M&AB orange, PT blue).
       The new `<table>` pill uses solid ``#0b1220`` (very dark navy),
       which gives ≥7:1 contrast with white text on every brand
       gradient. (Spec §1.1.)

    2. **Cover `<img>` carries inline `color/font-size/font-weight`**
       so the alt-text fallback is readable when images are blocked
       (Outlook desktop default). Without this the alt text inherits
       client defaults — typically near-black — and disappears against
       Tesla red, Omni View navy, etc. (Spec §1.2.)

    3. **VML wrapper for the gradient cell** so Outlook desktop
       renders a solid darker brand colour instead of the gradient's
       transparent default. (Spec §1.5.)
    """
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
        f'box-shadow:0 8px 24px rgba(0,0,0,0.25);'
        # Alt-text fallback styling — visible only when the image
        # itself fails to load. Bright white, bold so it reads against
        # any of the brand gradients.
        f'color:#ffffff;font-size:14px;font-weight:700;" />'
        if cover_url else ""
    )

    # Date / week pill — `<table>` with bgcolor + hex background so
    # Outlook (and any client that strips rgba) renders the dark navy
    # capsule around the white text. The 100-px border-radius is
    # recognised by Apple Mail / Gmail and degrades to a rectangle
    # in Outlook (still readable).
    pill_html = (
        '<table role="presentation" border="0" cellpadding="0" '
        'cellspacing="0" style="margin:0 auto;">'
        '<tr>'
        '<td bgcolor="#0b1220" '
        'style="background-color:#0b1220;color:#ffffff;font-size:12px;'
        'font-weight:600;padding:6px 14px;border-radius:100px;'
        'letter-spacing:0.04em;text-transform:uppercase;'
        "font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',"
        'Roboto,Helvetica,Arial,sans-serif;">'
        f'{pill_text}'
        '</td>'
        '</tr>'
        '</table>'
    )

    # The gradient cell. The VML conditional comments wrap the gradient
    # `<table>` so Outlook desktop falls back to a solid darker brand
    # background; non-Outlook clients ignore the comments and see the
    # gradient.
    return (
        # Outlook gradient fallback (Word renderer doesn't understand
        # CSS gradients). v:rect produces a solid-fill behind the
        # native HTML, which Outlook then composites *over* the
        # original table. We use the darker stop so white text stays
        # readable.
        '<!--[if gte mso 9]>'
        '<v:rect xmlns:v="urn:schemas-microsoft-com:vml" fill="true" '
        'stroke="false" '
        'style="width:600px;mso-position-horizontal:center;">'
        f'<v:fill type="solid" color="{brand_dark}" />'
        '<v:textbox inset="0,0,0,0"><div>'
        '<![endif]-->'
        f'<table role="presentation" width="100%" cellpadding="0" '
        f'cellspacing="0" border="0" bgcolor="{brand_dark}" '
        f'style="background-color:{brand_dark};'
        f'background:linear-gradient(135deg,{brand} 0%,'
        f'{brand_dark} 100%);">'
        f'<tr><td align="center" '
        f'style="padding:40px 24px 32px;'
        f"font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',"
        f'Roboto,Helvetica,Arial,sans-serif;">'
        f'{cover_img}'
        f'<h1 style="color:#ffffff;font-size:28px;font-weight:700;'
        f'margin:0 0 8px;line-height:1.2;letter-spacing:-0.01em;">'
        f'{name}</h1>'
        + (
            f'<p style="color:#ffffff;font-size:15px;'
            f'margin:0 0 20px;line-height:1.4;max-width:480px;'
            f'opacity:0.92;">'
            f'{tagline}</p>'
            if tagline else ""
        )
        + pill_html
        + '</td></tr></table>'
        '<!--[if gte mso 9]>'
        '</div></v:textbox></v:rect>'
        '<![endif]-->'
    )


_DARK_MODE_STYLE = """\
<style>
  /* Newsletter v2 (May 2026): expanded dark-mode stylesheet that
   * targets each brand color individually so contrast hits WCAG AA on
   * the dark surface, plus class hooks for ``preheader``,
   * ``card``, ``surface-*`` so inline-color overrides don't lose the
   * specificity war in Outlook iOS / mobile Gmail.
   *
   * Spec references: §1.3 light-mode contrast swaps, §1.4 dark-mode
   * brand tokens + ``.preheader`` hide.
   */
  body, table, td, p, h1, h2, h3, h4, span, div, a {
    -webkit-text-size-adjust:100%;
    -ms-text-size-adjust:100%;
  }

  @media (prefers-color-scheme: dark) {
    /* Page + table containers — flip the white shells. */
    body, .email-bg, .surface-white, .surface-fafafa, .surface-f8fafc,
    table[role=presentation] td[style*='background:#ffffff'],
    table[role=presentation] td[style*='background:#fafafa'],
    table[role=presentation] td[style*='background:#f8fafc'] {
      background:#0f172a !important;
      background-color:#0f172a !important;
    }

    /* Cards (slightly lifted "panel" surfaces). */
    .card { background:#1e293b !important; background-color:#1e293b !important; }

    /* Primary text on every dark-mode surface. */
    body, p, h1, h2, h3, h4, td, span, div, li {
      color:#e2e8f0 !important;
    }
    /* Secondary / muted text — class-targeted so it doesn't override
     * other usages. */
    .text-muted { color:#94a3b8 !important; }

    /* Links. */
    a, a span { color:#93c5fd !important; }

    /* Brand-color tokens — lighter dark-mode variants for AA contrast
     * on `#1e293b` cards. The original brand colors are preserved in
     * inline styles for light mode; dark mode lifts each one. */
    .brand-text-tesla     { color:#fb7185 !important; }   /* was #E31937 */
    .brand-text-mit       { color:#34d399 !important; }   /* was #047857 */
    .brand-text-omni      { color:#60a5fa !important; }   /* was #0B6FD6 */
    .brand-text-ma        { color:#a78bfa !important; }   /* was #7C3AED */
    .brand-text-mab       { color:#fbbf24 !important; }   /* was #B45309 */
    .brand-text-frontiers { color:#a5b4fc !important; }   /* was #6B47FF */
    .brand-text-envintel  { color:#86efac !important; }   /* was #1B5E20 */
    .brand-text-privet    { color:#a5b4fc !important; }   /* was #4F46E5 */
    .brand-text-finansy   { color:#f9a8d4 !important; }   /* was #BE185D */
    .brand-text-planet    { color:#67e8f9 !important; }   /* was #017A99 */
    .brand-text-uc        { color:#fbbf24 !important; }   /* was #B45309 */

    /* Financial-disclaimer callout background (was cream-amber) and
     * the dark-amber text — flip both for legibility. */
    .brand-text-warn { color:#fbbf24 !important; }
    .surface-warn   { background:#3b2a13 !important; background-color:#3b2a13 !important; }

    /* Tesla price-watch block. The light-mode cream `#fef2f2` has
     * great contrast against `#0f172a` text, but in dark mode the
     * universal text-color override flips text to `#e2e8f0` and
     * cream-on-light-text becomes invisible. Flip the bg too. */
    .surface-tsla   { background:#3b1c1f !important; background-color:#3b1c1f !important; }

    /* Hidden preheader stays hidden in dark mode too. Some Outlook
     * versions ignore display:none from inline styles when dark-mode
     * is active; the !important class hook fixes it. */
    .preheader { display:none !important; }

    /* `<hr>` separators flip from light slate to dark slate. */
    hr { border-top-color:#334155 !important; }
  }
</style>
"""


# ---------------------------------------------------------------------------
# Per-show CSS class for brand-text dark-mode variants
# ---------------------------------------------------------------------------

_SLUG_TO_BRAND_CLASS: Dict[str, str] = {
    "tesla": "brand-text-tesla",
    "modern_investing": "brand-text-mit",
    "omni_view": "brand-text-omni",
    "models_agents": "brand-text-ma",
    "models_agents_beginners": "brand-text-mab",
    "fascinating_frontiers": "brand-text-frontiers",
    "env_intel": "brand-text-envintel",
    "privet_russian": "brand-text-privet",
    "finansy_prosto": "brand-text-finansy",
    "planetterrian": "brand-text-planet",
    "unintended_consequences": "brand-text-uc",
}


def _brand_class(slug: str) -> str:
    """Return the CSS class for *slug*'s brand-text dark-mode token."""
    return _SLUG_TO_BRAND_CLASS.get(slug, "")


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
    # `.preheader` class hooks the dark-mode override (see
    # `_DARK_MODE_STYLE`) — prevents Outlook 2016/2019 from leaking
    # the preview text into the visible body when it ignores
    # ``display:none`` on inline-styled divs.
    return (
        '<div class="preheader" '
        'style="display:none;font-size:1px;color:#fafafa;'
        'line-height:1px;max-height:0;max-width:0;opacity:0;overflow:hidden;'
        'mso-hide:all;">'
        f'{safe}{pad}'
        '</div>'
    )


def _build_by_the_numbers_html(
    stats: Optional[List[Dict[str, str]]], brand: str, slug: str = ""
) -> str:
    """Render up to 3 stat tiles right under the hero, before the body.

    *slug* picks the dark-mode brand-text class (so the value number
    flips to a lighter variant on dark surfaces — see
    ``_DARK_MODE_STYLE``).
    """
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
            f'<div class="{_brand_class(slug)}" '
            f'style="font-size:22px;font-weight:700;color:{brand};'
            f'line-height:1.1;letter-spacing:-0.01em;">{v_safe}</div>'
            f'<div class="text-muted" '
            f'style="font-size:11px;color:#475569;'
            f'text-transform:uppercase;letter-spacing:0.06em;'
            f'margin-top:4px;line-height:1.3;">{l_safe}</div>'
            f'</td>'
        )
    if not cells:
        return ""
    return (
        '<table role="presentation" width="100%" cellpadding="0" '
        'cellspacing="0" border="0" '
        'class="surface-white" '
        'style="background:#ffffff;border-bottom:1px solid #e2e8f0;">'
        '<tr><td align="center" '
        'style="padding:18px 16px;'
        "font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',"
        'Roboto,Helvetica,Arial,sans-serif;">'
        '<div style="font-size:11px;color:#475569;font-weight:600;'
        'text-transform:uppercase;letter-spacing:0.08em;'
        'margin-bottom:10px;">By the numbers</div>'
        '<table role="presentation" width="100%" cellpadding="0" '
        'cellspacing="0" border="0" style="max-width:480px;margin:0 auto;">'
        f'<tr>{"".join(cells)}</tr>'
        '</table>'
        '</td></tr></table>'
    )


def _build_financial_disclaimer_html(language: str = "en") -> str:
    """Styled callout box for shows that discuss financial topics.

    Replaces the old in-prose ``**FINANCIAL DISCLAIMER:**`` line with
    a visually-distinct amber sidebar so it doesn't get lost in the
    body and is unmistakable to subscribers.

    *language* picks the copy: ``"en"`` (default) or ``"ru"`` for
    Финансы Просто. Spec §4.4.
    """
    if language == "ru":
        body = (
            '<strong>Внимание:</strong> Только для образовательных и '
            'развлекательных целей. Это не финансовая консультация. '
            'Все упомянутые сделки — учебные. '
            'Всегда проводите собственное исследование.'
        )
    else:
        body = (
            '<strong>Heads up:</strong> Educational and entertainment only. '
            'Not financial advice. Any trades discussed are simulated. '
            'Always do your own research.'
        )
    return (
        '<table role="presentation" width="100%" cellpadding="0" '
        'cellspacing="0" border="0" '
        'class="surface-warn" '
        'style="background:#FFF7ED;border-left:4px solid #B45309;">'
        '<tr><td '
        'style="padding:12px 16px;'
        "font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',"
        'Roboto,Helvetica,Arial,sans-serif;'
        'font-size:13px;color:#78350F;line-height:1.5;">'
        '<span class="brand-text-warn" style="color:#78350F;">'
        f'{body}'
        '</span>'
        '</td></tr></table>'
    )


def _build_p_s_html(p_s: str, brand: str, slug: str = "") -> str:
    """Render the P.S. block as a high-prominence accent-color callout.

    Phase 3.3 of the May 2026 audit reshaped the P.S. from a muted
    italic aside into a full-width brand-color card with white body
    text and an uppercase "P.S." label. P.S. is consistently one of
    the most-read elements of any newsletter; the muted treatment
    was wasting that engagement. The new shape mirrors Tesla's TSLA
    price block — a single visually loud rectangle the eye is
    drawn to.

    The accent color (#6B47FF after the May 2026 brand bump) clears
    WCAG AA against white body text at >5:1, so the contrast
    validator does not need to relax for this block.
    """
    if not p_s:
        return ""
    safe = p_s.replace("<", "&lt;").replace(">", "&gt;")
    return (
        '<table role="presentation" width="100%" cellpadding="0" '
        'cellspacing="0" border="0" '
        'style="background:#ffffff;">'
        '<tr><td style="padding:12px 24px 24px;">'
        f'<table role="presentation" width="100%" cellpadding="0" '
        f'cellspacing="0" border="0" bgcolor="{brand}" '
        f'class="{_brand_class(slug)}" '
        f'style="background:{brand};border-radius:10px;">'
        '<tr><td style="padding:18px 22px;'
        "font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',"
        'Roboto,Helvetica,Arial,sans-serif;">'
        '<div style="font-size:11px;line-height:1.2;color:#ffffff;'
        'font-weight:700;letter-spacing:0.12em;text-transform:uppercase;'
        'margin:0 0 6px 0;">P.S.</div>'
        f'<p style="font-size:15px;line-height:1.55;color:#ffffff;'
        f'margin:0;font-weight:600;">{safe}</p>'
        '</td></tr></table>'
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
    headers: List[str], rows: List[List[str]], *, brand: str = "#6B47FF"
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


def convert_md_tables_to_html(body_md: str, *, brand: str = "#6B47FF") -> str:
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
    # Card background: solid #f8fafc slate — robust across every email
    # client. Earlier versions used 8-digit hex (`{brand}0a` background,
    # `{brand}33` border) for a brand-tinted look; Outlook desktop's
    # Word renderer strips alpha channels, which made the card render
    # as solid brand-color and the brand-color eyebrow text vanished
    # (brand-on-brand = 1:1 contrast). Solid slate + solid 3px brand
    # left-accent gives the same visual hierarchy and works everywhere.
    return (
        '<table role="presentation" width="100%" cellpadding="0" '
        'cellspacing="0" border="0" '
        'class="surface-white" '
        'style="background:#ffffff;">'
        '<tr><td '
        'style="padding:20px 24px 8px;'
        'font-family:-apple-system,BlinkMacSystemFont,\'Segoe UI\','
        'Roboto,Helvetica,Arial,sans-serif;">'
        f'<div class="card" '
        f'style="background:#f8fafc;border-left:3px solid {brand};'
        f'border-radius:8px;padding:18px 18px 16px;">'
        '<div style="font-size:11px;font-weight:700;'
        f'color:{brand};letter-spacing:0.08em;'
        'text-transform:uppercase;margin-bottom:6px;">'
        '🎧 If you only have 10 minutes this week'
        '</div>'
        f'<div style="font-size:17px;font-weight:600;color:#0f172a;'
        f'line-height:1.4;margin:0 0 10px;">'
        f'Episode {num} · {safe_hook}'
        '</div>'
        f'<div class="text-muted" '
        f'style="font-size:12px;color:#475569;margin:0 0 14px;">'
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
        # Spec §6.1: the show name itself should be clickable, not
        # just the hook text after the em-dash. We wrap both name AND
        # hook in the same anchor so anywhere on the row is a click
        # target — bigger tap surface on mobile.
        if url:
            row_open = (
                f'<a href="{url}" '
                f'style="display:block;color:inherit;text-decoration:none;">'
            )
            row_close = "</a>"
        else:
            row_open = row_close = ""
        rows.append(
            '<tr><td '
            'style="padding:10px 0;border-top:1px solid #e2e8f0;'
            'font-size:14px;line-height:1.5;color:#334155;">'
            f'{row_open}'
            f'<strong style="color:#0f172a;'
            + (f'border-bottom:1px solid {brand};' if url else "")
            + f'">{prefix}{n_safe}</strong>'
            f'<span class="text-muted" style="color:#475569;">'
            f' — {h_safe}</span>'
            f'{row_close}'
            '</td></tr>'
        )
    if not rows:
        return ""
    return (
        '<table role="presentation" width="100%" cellpadding="0" '
        'cellspacing="0" border="0" '
        'class="surface-f8fafc" '
        'style="background:#f8fafc;">'
        '<tr><td '
        'style="padding:24px;'
        "font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',"
        'Roboto,Helvetica,Arial,sans-serif;">'
        '<div class="text-muted" '
        'style="font-size:11px;font-weight:700;color:#475569;'
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
    show: Dict[str, str],
    *,
    archive_url: str = "",
    slug: str = "",
) -> str:
    """Render a reply-CTA + share-intents row above the footer CTAs.

    Russian-language shows (FP/PR) get Russian copy for both the reply
    CTA and the share-intent text — see spec §4.1 / §4.2. The chip
    labels stay in English because that's what the underlying buttons
    do (Share on X, Share on LinkedIn) and the brands are global.

    Mailto opens a prefilled message. Twitter/LinkedIn/WhatsApp share
    intents point to the archive_url (the show landing page, since
    Buttondown's per-issue archive URL isn't known until after send).
    """
    name = show["name"]
    brand = show["brand_color"]
    target = (archive_url or show["show_page"]).strip()

    # Russian-language localization for the reply CTA + share text.
    is_russian = slug in ("finansy_prosto", "privet_russian")
    if is_russian:
        reply_html = (
            '💬 <strong>Ответьте на это письмо</strong> — '
            'Патрик читает каждое.'
        )
        share_text = f'Слушаю «{name}» — рекомендую:'
        share_x_label = "Поделиться в X"
        share_li_label = "Поделиться в LinkedIn"
        share_wa_label = "Поделиться в WhatsApp"
    else:
        reply_html = (
            '💬 <strong>Reply to this email</strong> — '
            'Patrick reads every one.'
        )
        share_text = f"I'm reading {name} this week — give it a listen:"
        share_x_label = "Share on X"
        share_li_label = "Share on LinkedIn"
        share_wa_label = "Share on WhatsApp"

    # Pre-encode the share intents (URL-encoded query strings).
    import urllib.parse as _u
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
        # Border uses a solid neutral slate (#cbd5e1) instead of the
        # brand-color-with-alpha (`{brand}55`) that Outlook desktop
        # strips down to a full-saturation brand border. Solid slate
        # gives the chip clear definition on white in every client
        # without competing with the brand-color text.
        return (
            f'<a href="{href}" '
            f'style="display:inline-block;color:{brand};text-decoration:none;'
            f'font-weight:600;font-size:13px;padding:6px 12px;'
            f'margin:2px;border:1px solid #cbd5e1;border-radius:100px;'
            f'background:#ffffff;">{label}</a>'
        )

    return (
        '<table role="presentation" width="100%" cellpadding="0" '
        'cellspacing="0" border="0" '
        'class="surface-white" '
        'style="background:#ffffff;">'
        '<tr><td align="center" '
        'style="padding:8px 16px 20px;'
        "font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',"
        'Roboto,Helvetica,Arial,sans-serif;color:#475569;">'
        '<p style="font-size:13px;margin:0 0 10px;line-height:1.5;">'
        f'{reply_html}'
        '</p>'
        '<div>'
        + _chip(twitter, share_x_label)
        + _chip(linkedin, share_li_label)
        + _chip(whatsapp, share_wa_label)
        + '</div>'
        '</td></tr></table>'
    )


def _build_view_in_browser_html(archive_url: str) -> str:
    """Top-of-body "View in browser" link for clients that mangle the
    rendered HTML (mostly Outlook desktop with images blocked).

    Spec §7.1. Empty archive_url → empty string (no link, no row).
    """
    if not archive_url:
        return ""
    return (
        '<table role="presentation" width="100%" cellpadding="0" '
        'cellspacing="0" border="0" '
        'class="surface-white" '
        'style="background:#ffffff;">'
        '<tr><td align="center" '
        'style="padding:8px 16px;font-size:11px;'
        "font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',"
        'Roboto,Helvetica,Arial,sans-serif;">'
        '<a class="text-muted" '
        f'href="{archive_url}" '
        'style="color:#475569;text-decoration:underline;">'
        'View this email in your browser'
        '</a>'
        '</td></tr></table>'
    )


def _build_issue_counter_html(
    show: Dict[str, str], issue_number: int, send_date: datetime.date,
    *, slug: str = "",
) -> str:
    """Per-show issue counter rendered just above Buttondown's auto-footer.

    Spec §7.2 / §1.6. Buttondown auto-appends a network-wide counter
    we can't suppress on the current plan; this block overrides it
    visually with the correct per-show count and a properly styled
    color that survives dark mode.
    """
    name = show.get("name") or "Nerra Network"
    is_russian = slug in ("finansy_prosto", "privet_russian")
    if is_russian:
        label = (
            f'Выпуск #{issue_number} · {name} · '
            f'{send_date.strftime("%d.%m.%Y")}'
        )
    else:
        label = (
            f'Issue #{issue_number} · {name} · '
            f'{send_date.strftime("%b %-d, %Y")}'
        )
    return (
        '<table role="presentation" width="100%" cellpadding="0" '
        'cellspacing="0" border="0" '
        'class="surface-fafafa" '
        'style="background:#fafafa;">'
        '<tr><td align="center" '
        'class="text-muted" '
        'style="padding:14px 24px;font-size:12px;color:#475569;'
        "font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',"
        'Roboto,Helvetica,Arial,sans-serif;">'
        f'{label}'
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
        f'class="surface-fafafa" '
        f'style="background:#fafafa;border-top:4px solid {brand};">'
        f'<tr><td align="center" '
        f'style="padding:32px 24px;'
        f"font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',"
        f'Roboto,Helvetica,Arial,sans-serif;color:#0f172a;">'
        f'<p style="font-size:14px;color:#475569;margin:0 0 16px;">'
        f'Catch up on more {name}:'
        f'</p>'
        f'<div style="line-height:1.8;">'
        f'{listen}{watch}{blog}'
        f'</div>'
        # AI-disclosure line — bumped from #94a3b8 (3.0:1 on white) to
        # #475569 (6.4:1) so light-mode hits AA. Spec §1.3.
        # The voice provider is now "Grok TTS (xAI)" for every show
        # except — well, after the May 2026 full migration, every
        # show. Update the disclosure copy accordingly.
        f'<p class="text-muted" '
        f'style="font-size:12px;color:#475569;margin:24px 0 4px;'
        f'line-height:1.5;">'
        f'<a href="{_NETWORK_SITE}" '
        f'style="color:#475569;text-decoration:none;font-weight:600;">'
        f'Nerra Network</a> · '
        f'AI-narrated voice (Grok TTS) · '
        f'Editorial by Patrick'
        f'</p>'
        # Unsubscribe / subscription source — same contrast bump.
        f'<p class="text-muted" '
        f'style="font-size:11px;color:#475569;margin:0;line-height:1.5;">'
        f'You\'re receiving this because you subscribed to {name} on '
        f'<a href="{_NETWORK_SITE}" '
        f'style="color:#475569;text-decoration:underline;">'
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
    slug: str,
    subject_hook: str,
    *,
    send_date: Optional[datetime.date] = None,
    hook_max_chars: int = 90,
    is_daily: bool = False,
) -> str:
    """Compose the final email subject from a hook + show short label.

    Format: ``"<hook> · <short_label> <emoji>"``. Falls back to the
    full show name if no short label is configured. Hard-capped at
    100 chars to stay within email-client subject limits.

    Parameters
    ----------
    hook_max_chars:
        Hard cap applied to the hook portion *before* it's joined with
        the suffix. Dailies pass ``50`` (spec §3) so the show name +
        emoji are never truncated by Gmail's inbox preview. Weeklies
        use the default 90 (most of the 100-char overall budget).
    is_daily:
        When ``True`` and *subject_hook* is empty, the fallback uses a
        daily date-stamped phrasing instead of "This week: …".
    """
    show = _load_show_branding(slug)
    short = show.get("short_label") or show.get("name") or slug
    emoji = show.get("emoji") or ""

    hook = (subject_hook or "").strip().rstrip(" .,;:")
    # Apply the per-call hook cap before the suffix join. Use
    # semantic (word-boundary) truncation rather than hard cut —
    # truncating mid-word ("Scientists map a neural feedba…") looks
    # lazy in inbox previews. We allow up to +5 chars over the cap
    # if the next word boundary is within reach; otherwise we cut
    # at the last word boundary before the cap.
    if hook and len(hook) > hook_max_chars:
        # Look ahead 1-5 chars for a space; if found, cut there.
        extended = hook[:hook_max_chars + 5]
        far_space = extended.rfind(" ", hook_max_chars)
        if far_space > 0:
            hook = hook[:far_space].rstrip(" ,.;:") + "…"
        else:
            # No nearby boundary forward — cut at last word boundary
            # within the cap.
            cut = hook.rfind(" ", 0, hook_max_chars)
            if cut > hook_max_chars - 15:
                # Word boundary exists within last 15 chars before cap.
                hook = hook[:cut].rstrip(" ,.;:") + "…"
            else:
                # Pathological — fall back to original hard cut.
                hook = hook[:hook_max_chars].rstrip(" ,.;:") + "…"
    if not hook:
        # No hook from the LLM — degrade to a clean date-stamped fallback.
        when = send_date or datetime.date.today()
        if is_daily:
            hook = when.strftime("%b %-d update")
        else:
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
    archive_url: str = "",
    issue_number: Optional[int] = None,
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
        by_the_numbers, show["brand_color"], slug
    )
    # Stamp the slug into the featured-episode dict so the block can
    # build the listen URL even if the caller didn't pre-resolve it.
    # Phase 2.4 (May 2026 audit): when the synthesizer doesn't supply
    # a featured episode, auto-fall-back to the most recent episode
    # from this show via the content lake. The featured-episode
    # block is the highest-converting CTA in the newsletter; skipping
    # it on missing-data was a missed opportunity, not a quality gate.
    featured_with_slug = None
    if featured_episode:
        featured_with_slug = dict(featured_episode)
        featured_with_slug.setdefault("show_slug", slug)
    else:
        try:
            from engine.content_lake import query_show_range
            from datetime import date as _date, timedelta as _td
            _today = _date.today()
            _recent = query_show_range(
                slug,
                (_today - _td(days=14)).isoformat(),
                _today.isoformat(),
            ) or []
            if _recent:
                _latest = sorted(
                    _recent,
                    key=lambda e: (e.get("date") or "", e.get("episode_num") or 0),
                    reverse=True,
                )[0]
                featured_with_slug = {
                    "show_slug": slug,
                    "episode_num": _latest.get("episode_num"),
                    "title": _latest.get("hook")
                    or f"Episode {_latest.get('episode_num', '?')}",
                    "hook": _latest.get("hook", ""),
                    "date": _latest.get("date", ""),
                }
        except Exception:  # noqa: BLE001 — best-effort fallback only
            featured_with_slug = None
    featured_block = _build_featured_episode_html(featured_with_slug, show)
    # Russian shows that need the disclaimer (currently only Финансы
    # Просто) get the Cyrillic version. Spec §4.4.
    disclaimer_lang = "ru" if slug == "finansy_prosto" else "en"
    disclaimer = (
        _build_financial_disclaimer_html(disclaimer_lang)
        if requires_financial_disclaimer else ""
    )
    p_s_block = _build_p_s_html(p_s, show["brand_color"], slug)
    cross_network = _build_cross_network_html(
        adjacent_shows, show["brand_color"]
    )
    reply_share = (
        _build_reply_share_html(show, slug=slug)
        if show_reply_share else ""
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

    # Two trust-and-tracking blocks added in spec v2: a "view in
    # browser" link at the very top (clients that mangle the rendered
    # HTML — Outlook desktop with images blocked is the worst case)
    # and a per-show issue counter just before the footer that
    # overrides Buttondown's network-wide counter visually.
    view_in_browser = _build_view_in_browser_html(archive_url)
    issue_counter = ""
    if issue_number is not None:
        send_date = (
            week_ending
            or daily_date
            or datetime.date.today()
        )
        issue_counter = _build_issue_counter_html(
            show, issue_number, send_date, slug=slug,
        )

    # Wrap the body markdown in a ``surface-white`` table so the
    # dark-mode ``<style>`` override flips its background. Without
    # this wrapper Buttondown's markdown→HTML conversion produces
    # bare ``<p>`` tags that the email client renders against its
    # own page background, which on iOS Mail dark mode results in
    # near-black body text (Buttondown default `#0f172a`-ish) against
    # a darkening surface — barely readable. Spec v2 follow-up.
    body_wrapped = ""
    if body_clean.strip():
        body_wrapped = (
            '<table role="presentation" width="100%" cellpadding="0" '
            'cellspacing="0" border="0" '
            'class="surface-white" '
            'style="background:#ffffff;">'
            '<tr><td style="padding:8px 24px;'
            "font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',"
            'Roboto,Helvetica,Arial,sans-serif;'
            'font-size:15px;line-height:1.6;color:#0f172a;">'
            f'{body_clean}'
            '</td></tr></table>'
        )

    # Blocks separated by two blank lines so markdown processors treat
    # them as separate sections. Empty blocks contribute nothing. The
    # dark-mode <style> block goes at the very top so any client that
    # respects @media queries picks it up before parsing the body.
    parts = [
        _DARK_MODE_STYLE,
        preheader_div,
        view_in_browser,
        hero,
        stats_block,
        featured_block,
        disclaimer,
        body_wrapped,
        p_s_block,
        cross_network,
        reply_share,
        footer,
        issue_counter,
    ]
    return "\n\n".join(p for p in parts if p) + "\n"
