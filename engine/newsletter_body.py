"""Body-text transforms applied to a daily digest's markdown.

Two stages:

1. ``transform_daily_body`` — markdown-safe transforms applied at the
   canonical-write site in ``run_show.py``. The output is still valid
   markdown (no inline HTML), so the blog reader, RSS show notes, and
   GitHub Pages summary all see the same clean source. Includes:

      - Box-drawing rules → markdown ``---`` (renders fine everywhere)
      - Hook line → markdown blockquote ``> **<text>**`` (visual lift)
      - Source URL shortening (Google News blob → `[Google News](...)`)
      - Bare ``@handle`` → markdown link
      - Omni View "Read more" duplicate-URL dedup

2. ``transform_email_body`` — HTML upgrades layered on top of the
   canonical text inside ``send_show_newsletter``. These would corrupt
   plaintext / blog / RSS surfaces if applied at the canonical stage
   (raw inline HTML showing up in markdown), so they're email-only:

      - Markdown ``---`` rules → styled ``<hr>`` (dark-mode aware)
      - Tesla ``**TSLA today:**`` line → styled stock-watch table
      - Privet vocab list → card-stack table

All transforms are idempotent. They're also applied *after*
``scrub_scaffold`` from ``engine.newsletter_sanitizer`` so labels like
``**Vocabulary List (8-12 words/phrases):**`` are already gone by the
time we run.
"""

from __future__ import annotations

import re
from typing import List


# ---------------------------------------------------------------------------
# Box-drawing horizontal rules → markdown / HTML
# ---------------------------------------------------------------------------

_BOX_RULE_RE = re.compile(r"(?m)^\s*(?:━|─|═){3,}\s*$")
_MD_HR_RE = re.compile(r"(?m)^\s*-{3,}\s*$")


def replace_box_rules_with_md_hr(body: str) -> str:
    """Canonical-stage: box-drawing rules → markdown ``---``.

    Markdown's standard horizontal rule renders cleanly in every
    surface that consumes the canonical .md (blog, RSS show notes,
    GitHub Pages summary). The email pipeline upgrades ``---`` to a
    styled ``<hr>`` later via ``upgrade_md_hr_to_html``.
    """
    if not body:
        return body
    return _BOX_RULE_RE.sub("---", body)


def upgrade_md_hr_to_html(body: str) -> str:
    """Email-stage: markdown ``---`` rules → styled ``<hr>``.

    Outlook Win renders box-drawing characters (━━━) as boxes; even
    plain ``---`` is rendered as a faint thin rule by some clients
    and as nothing by others. Replace with an inline-styled ``<hr>``
    that respects dark mode (overridden in ``_DARK_MODE_STYLE``).
    """
    if not body:
        return body
    return _MD_HR_RE.sub(
        '<hr style="border:none;border-top:1px solid #e2e8f0;'
        'margin:24px 0;" />',
        body,
    )


# ---------------------------------------------------------------------------
# Tesla "REAL-TIME TSLA price:" line → styled stock-watch block
# ---------------------------------------------------------------------------

# Match line variants like:
#   **REAL-TIME TSLA price:** $390.82 ▲ $9.44 (2.5%)
#   **TSLA today:** $390.82 ▼ $9.44 (-2.5%)
# Captures: price (group 1), arrow (group 2), delta_str (group 3).
_TSLA_PRICE_RE = re.compile(
    r"(?im)^\s*\*\*"
    r"(?:REAL-TIME\s+)?TSLA\s+(?:today|price)\s*:?\s*\*\*\s*"
    r"(\$[\d,.]+)\s*"
    r"([▲▼])?\s*"
    r"(\$[\d,.]+(?:\s*\([+-]?[\d.]+%\))?)?\s*$"
)


def render_tsla_price_block(body: str) -> str:
    """Replace the bold-label TSLA price line with a styled stock-watch
    block. Spec §5.3.

    Uses brand-text-tesla class so dark-mode picks the lighter variant.
    """
    if not body:
        return body

    def _sub(match: re.Match) -> str:
        price = match.group(1) or ""
        arrow = match.group(2) or ""
        delta = match.group(3) or ""
        # Up = green, Down = red, no arrow = neutral slate.
        # Operator caught (TST Ep465, May 6 2026) the prior #10b981
        # / #ef4444 pair failing the newsletter contrast hard-block:
        # both clear AA on white but fall to 2.32 / 3.44 on the
        # cream `#fef2f2` price-block surface. Bumped to Tailwind
        # emerald-700 / red-700 so the arrows clear AA on cream.
        if arrow == "▲":
            delta_color = "#047857"  # emerald-700, 5.01:1 on cream
        elif arrow == "▼":
            delta_color = "#b91c1c"  # red-700, 5.91:1 on cream
        else:
            delta_color = "#475569"
        delta_html = ""
        if arrow or delta:
            delta_html = (
                f' <span style="color:{delta_color};font-size:14px;'
                f'font-weight:600;">{arrow} {delta}</span>'.strip()
            )
        # Dark-mode rules in `_DARK_MODE_STYLE` flip ``.surface-tsla``
        # to a dark slate background. Without the class hook the cream
        # `#fef2f2` survives into dark mode and the dark-text override
        # turns the whole block into light-on-light = invisible. Spec
        # v2 follow-up after the May 2 Tesla daily render bug.
        return (
            '<table role="presentation" cellpadding="0" cellspacing="0" '
            'border="0" '
            'class="surface-white" '
            'style="background:#ffffff;margin:0 0 16px;">'
            '<tr><td '
            'class="surface-tsla" '
            'style="padding:10px 14px;border-left:4px solid #E31937;'
            'background:#fef2f2;border-radius:0 6px 6px 0;'
            "font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',"
            'Roboto,Helvetica,Arial,sans-serif;">'
            '<div class="text-muted" '
            'style="font-size:11px;font-weight:700;color:#475569;'
            'text-transform:uppercase;letter-spacing:0.06em;'
            'margin-bottom:2px;">TSLA today</div>'
            '<div class="brand-text-tesla" '
            'style="font-size:18px;font-weight:700;color:#0f172a;'
            'line-height:1.2;">'
            f'{price}{delta_html}'
            '</div>'
            '</td></tr></table>'
        )

    return _TSLA_PRICE_RE.sub(_sub, body)


# ---------------------------------------------------------------------------
# Привет, Русский! vocabulary list → card stack
# ---------------------------------------------------------------------------

# Match a vocab block — consecutive lines like:
#   - Russian (Cyrillic): космос
#     Transliteration: KOS-mos
#     English: space
#     Example sentence: Мы летим в космос.
#     Example translation: We are flying into space.
#     Memory hook: It sounds exactly like the English word "cosmos"…
#
# Indentation varies. We match an opening "- Russian (Cyrillic)" line and
# then the labelled fields that follow until a blank line or the next "-".

_VOCAB_BLOCK_RE = re.compile(
    r"(?m)^\s*[-*]\s*Russian\s*\(Cyrillic\)\s*:\s*(.+?)\s*$"  # cyrillic word
    r"(?:\s*\n\s*Transliteration\s*:\s*(.+?)\s*$)?"
    r"(?:\s*\n\s*English\s*:\s*(.+?)\s*$)?"
    r"(?:\s*\n\s*Example sentence\s*:\s*(.+?)\s*$)?"
    r"(?:\s*\n\s*Example translation\s*:\s*(.+?)\s*$)?"
    r"(?:\s*\n\s*Memory hook\s*:\s*(.+?)\s*$)?"
)


def _vocab_card(
    cyrillic: str,
    transliteration: str = "",
    english: str = "",
    example_ru: str = "",
    example_en: str = "",
    memory_hook: str = "",
) -> str:
    """Render one vocab card as inline-styled HTML."""
    def _esc(s: str) -> str:
        return s.replace("<", "&lt;").replace(">", "&gt;")

    parts: List[str] = []
    parts.append(
        '<table role="presentation" cellpadding="0" cellspacing="0" '
        'border="0" class="card" '
        'style="background:#f8fafc;border-radius:12px;'
        'margin:8px 0;width:100%;">'
        '<tr><td style="padding:14px 16px;'
        "font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',"
        'Roboto,Helvetica,Arial,sans-serif;">'
    )
    parts.append(
        '<table role="presentation" cellpadding="0" cellspacing="0" '
        'border="0">'
        '<tr>'
        f'<td style="font-size:22px;font-weight:700;color:#0f172a;'
        f'line-height:1.2;padding-right:12px;">{_esc(cyrillic)}</td>'
    )
    if transliteration:
        parts.append(
            f'<td class="text-muted" '
            f'style="font-size:12px;color:#475569;font-style:italic;'
            f'vertical-align:baseline;">'
            f'[{_esc(transliteration)}]'
            '</td>'
        )
    parts.append('</tr></table>')
    if english:
        parts.append(
            f'<div style="font-size:14px;color:#334155;margin-top:4px;">'
            f'{_esc(english)}</div>'
        )
    if example_ru:
        gloss = (
            f' <span class="text-muted" style="color:#475569;">— '
            f'{_esc(example_en)}</span>'
            if example_en else ""
        )
        parts.append(
            '<div class="text-muted" '
            'style="font-size:13px;color:#475569;margin-top:8px;'
            'font-style:italic;">'
            f'{_esc(example_ru)}{gloss}'
            '</div>'
        )
    if memory_hook:
        parts.append(
            '<div class="text-muted" '
            'style="font-size:12px;color:#475569;margin-top:8px;'
            'background:#fef3c7;padding:6px 10px;border-radius:6px;'
            'border-left:3px solid #b45309;">'
            f'💡 {_esc(memory_hook)}'
            '</div>'
        )
    parts.append('</td></tr></table>')
    return "".join(parts)


def render_russian_vocab_cards(body: str) -> str:
    """Detect Привет vocab blocks and rewrite them as card stacks.

    Idempotent. If the body has no recognisable vocab block, it's
    returned unchanged.
    """
    if not body or "Russian (Cyrillic):" not in body:
        return body
    out_parts: List[str] = []
    last_end = 0
    for match in _VOCAB_BLOCK_RE.finditer(body):
        out_parts.append(body[last_end:match.start()])
        out_parts.append(
            _vocab_card(
                cyrillic=match.group(1) or "",
                transliteration=(match.group(2) or "").strip(),
                english=(match.group(3) or "").strip(),
                example_ru=(match.group(4) or "").strip(),
                example_en=(match.group(5) or "").strip(),
                memory_hook=(match.group(6) or "").strip(),
            )
        )
        last_end = match.end()
    out_parts.append(body[last_end:])
    return "".join(out_parts)


# ---------------------------------------------------------------------------
# Hook line → blockquote (visual prominence)
# ---------------------------------------------------------------------------

# After ``scrub_scaffold`` strips the ``**HOOK:**`` label, the hook
# becomes a plain paragraph at the top of the digest — visually
# indistinguishable from the body. Promote it to a markdown blockquote
# (``> **<text>**``) so it stands out across every surface (blog
# renders it indented, email wraps it as a styled quote, RSS readers
# show it as a callout). The hook is a single sentence that follows
# the price line and precedes the first horizontal rule.
#
# Match the first non-empty content line that sits between the
# price/header lines and the first ``---`` (or end of body), and
# only if it doesn't already start with ``>`` (idempotent) and isn't
# already a heading / list item / blockquote / table.

# A bold-label line looks like ``**Field name:** value`` — the colon
# inside the bold span is the giveaway. We skip those (they're header
# metadata) and only consider plain prose lines for promotion.
_BOLD_LABEL_LINE_RE = re.compile(r"^\*\*[^*]+:\*\*")
# Markdown bullet (``- foo`` or ``* foo``) — single marker followed by
# whitespace. ``**foo**`` is legitimate bold prose, NOT a bullet, so
# we use a regex (single char + space) instead of ``startswith("*")``.
_BULLET_LINE_RE = re.compile(r"^[-*]\s")
_HOOK_SKIP_PREFIXES = ("#", ">", "1.", "|", "<", "```")
# A line containing inline ``**...**`` bold spans surrounded by other
# prose is a decoration / show subtitle (e.g. Planetterrian's
# ``🌍 **Planetterrian Daily** - Science, Longevity & Health
# Discoveries``), never the hook. The hook itself is plain prose
# without internal bold spans. A line that IS one bold span end-to-end
# (``**Already bold hook**``) is a candidate — that's matched by the
# fullmatch test in ``_is_decorative_subtitle``.
_INLINE_BOLD_RE = re.compile(r"\*\*[^*]+\*\*")
_FULLY_BOLD_RE = re.compile(r"^\*\*[^*]+\*\*$")


def _is_decorative_subtitle(stripped: str) -> bool:
    """A line is a decorative subtitle if it contains a ``**...**``
    bold span but isn't itself one bold span end-to-end."""
    return bool(_INLINE_BOLD_RE.search(stripped)) and not bool(
        _FULLY_BOLD_RE.fullmatch(stripped)
    )


def promote_hook_to_blockquote(body: str) -> str:
    """Wrap the post-scrub hook line in a markdown blockquote.

    The transform finds the first prose line after the header block
    (Date / TSLA today / etc.) and rewrites it as ``> **<text>**``.
    Returns the body unchanged if no plausible hook is found —
    conservative by design.

    Idempotent: skips lines that already start with ``>``.
    """
    if not body:
        return body

    lines = body.split("\n")
    # Skip the title and any leading metadata lines (bold-label or
    # blank). Find the first line that's plain prose.
    for i, raw in enumerate(lines):
        stripped = raw.strip()
        if not stripped:
            continue
        # Skip title (`# Tesla Shorts Time`) and any bold-label header
        # lines (``**TSLA today:** ...``).
        if stripped.startswith("#"):
            continue
        if _BOLD_LABEL_LINE_RE.match(stripped):
            continue
        # Decorative subtitle lines (``🌍 **Planetterrian Daily** -
        # Science, Longevity & Health Discoveries``) — keep walking,
        # the real hook is below them.
        if _is_decorative_subtitle(stripped):
            continue
        # Stop at structural markers — if we hit an HR or a list /
        # heading before any prose, there's no hook to promote.
        if stripped.startswith(_HOOK_SKIP_PREFIXES):
            return body
        if _BULLET_LINE_RE.match(stripped):
            return body
        # Plausible hook — wrap it.
        # Strip any surrounding `**bold**` so we don't end up with
        # ``> **\*\*text\*\***``.
        text = stripped
        if text.startswith("**") and text.endswith("**") and len(text) > 4:
            text = text[2:-2].strip()
        lines[i] = f"> **{text}**"
        return "\n".join(lines)
    return body


# ---------------------------------------------------------------------------
# Public combined transform
# ---------------------------------------------------------------------------

def transform_daily_body(body: str, *, slug: str = "") -> str:
    """Canonical-stage transforms (markdown-safe; no inline HTML).

    Applied at the canonical .md write site in ``run_show.py`` so every
    downstream surface (blog, RSS show notes, GitHub Pages summary,
    email) sees the same source. Order matters:

      1. Box-drawing rules → markdown ``---``
      2. Hook line → markdown blockquote
      3. Shorten Google News tracking URLs in "Source: …" lines
      4. Linkify trailing X/Twitter @handles
      5. Dedup Omni View "Read more" duplicate URLs

    Each transform is a no-op when its trigger pattern isn't present,
    so calling this for every show is safe.
    """
    body = replace_box_rules_with_md_hr(body)
    body = promote_hook_to_blockquote(body)
    body = shorten_source_urls(body)
    body = linkify_x_handles(body)
    if slug == "omni_view":
        body = dedup_read_more_sources(body)
    return body


def transform_email_body(body: str, *, slug: str = "") -> str:
    """Email-only transforms — inline HTML upgrades for layout.

    Applied inside ``send_show_newsletter`` *after* the canonical
    transforms have already run on the source. These produce HTML
    that's only safe inside an email (the canonical .md path can't
    contain raw HTML — Markdown viewers strip or escape it):

      1. Markdown ``---`` → styled ``<hr>`` (dark-mode aware)
      2. Tesla ``**TSLA today:**`` line → styled stock-watch table
      3. Privet vocab list → card-stack table

    Idempotent — repeated runs produce the same HTML output.
    """
    body = upgrade_md_hr_to_html(body)
    if slug == "tesla":
        body = render_tsla_price_block(body)
    if slug == "privet_russian":
        body = render_russian_vocab_cards(body)
    return body


# ---------------------------------------------------------------------------
# X/Twitter @handle linkification
# ---------------------------------------------------------------------------

# The closing line of every TST daily reads:
#   "Let me know your thoughts on today's stories at @teslashortstime."
# Plain text — clicking does nothing in most clients. This transform
# rewrites bare ``@handle`` mentions (in prose context, not inside an
# existing markdown link or URL) to clickable ``[@handle](https://x.com/handle)``.
#
# Conservative match: ``@`` preceded by start-of-string or whitespace,
# 1-15 alphanumeric/underscore chars (X handle limit), not followed by
# another word character. We deliberately don't touch handles that
# already live inside a markdown link target ``](https://x.com/foo)`` or
# inside a URL — the leading-context check rules those out.

_X_HANDLE_RE = re.compile(
    r"(?<![\w/(\[\]])@([A-Za-z0-9_]{1,15})\b"
)


def linkify_x_handles(body: str) -> str:
    """Rewrite bare ``@handle`` mentions as clickable markdown links.

    Idempotent — handles already inside ``[@x](url)`` markdown links
    are skipped because the regex's negative lookbehind blocks the
    ``](`` and ``/`` characters that would precede them.
    """
    if not body or "@" not in body:
        return body

    def _sub(match: re.Match) -> str:
        handle = match.group(1)
        return f"[@{handle}](https://x.com/{handle})"

    return _X_HANDLE_RE.sub(_sub, body)


# ---------------------------------------------------------------------------
# "Source: <long-url>" shortening (post-fetch defense)
# ---------------------------------------------------------------------------

# Match "Source: <url>" emitted by the LLM at the end of a story. The URL
# can be Google News (`news.google.com/rss/articles/CBMi...`) which is
# 200-600 chars, or any other publisher URL with utm_*-style noise.
# Captures (1) the URL itself; we replace the whole "Source: …" tail.
_SOURCE_URL_RE = re.compile(
    r"\s*Source:\s*(https?://[^\s)]+)",
    flags=re.IGNORECASE,
)


def shorten_source_urls(body: str) -> str:
    """Render long bare-URL "Source:" trailers as compact "Source: <domain>"
    markdown links. Spec v2 follow-up after the May 2 Tesla daily showed
    the literal Google News redirect blob `CBMiig...` in the body.

    The fetcher's ``resolve_google_news_url`` canonicalizes URLs at fetch
    time, but (a) cached articles from before that fix landed still have
    the long URLs and (b) network failures during resolution leave the
    original Google-News URL in the article record. This transform is a
    final visual cleanup applied to the rendered body so the email never
    shows the 600-char tracking blob even when the upstream resolver
    bailed.
    """
    if not body or "Source:" not in body:
        return body

    def _sub(match: re.Match) -> str:
        url = match.group(1).rstrip(" ).,;")
        # Extract a human-readable domain.
        try:
            from urllib.parse import urlparse
            host = urlparse(url).netloc
        except Exception:  # noqa: BLE001
            host = ""
        if not host:
            return match.group(0)
        # Strip leading "www."; if it's still Google News after our
        # fetch-time resolver bailed, label it that way explicitly so
        # the reader at least sees what they're getting.
        host = host.lower()
        if host.startswith("www."):
            host = host[4:]
        if host.startswith("news.google."):
            label = "Google News"
        else:
            label = host
        return f" Source: [{label}]({url})"

    return _SOURCE_URL_RE.sub(_sub, body)


# ---------------------------------------------------------------------------
# Omni View "Read more" source-list dedup (spec §2.4)
# ---------------------------------------------------------------------------

# A "Read more" sources block looks like:
#   **Read more (sources):**
#   - [Daily Mail](https://...) — Full details on the threat level
#   - [Daily Mail](https://...) — Information on the suspect
#   - [Daily Mail](https://...) — Background on recent incidents
#
# When all bullets share the same URL we collapse them into one
# bullet (the first description wins) so the reader doesn't see
# three identical links. The LLM prompt now requests genuinely
# different URLs (omni_view_digest.txt §50), but defense-in-depth
# means the regex catches a regression even if the model ignores
# the instruction.

_READ_MORE_BLOCK_RE = re.compile(
    r"(?ms)^(\*\*Read more \(sources\):\*\*\s*\n)((?:\s*[-*][^\n]+\n)+)"
)
_BULLET_LINK_RE = re.compile(
    r"^\s*[-*]\s*\[([^\]]+)\]\(([^)]+)\)([^\n]*)$"
)


def dedup_read_more_sources(body: str) -> str:
    """Collapse Omni View "Read more" bullets with duplicate URLs.

    Idempotent. Empty / no-match input returns unchanged.
    """
    if not body or "Read more (sources):" not in body:
        return body

    def _sub(match: re.Match) -> str:
        header = match.group(1)
        bullets_blob = match.group(2)
        seen: dict = {}
        kept_bullets: List[str] = []
        for line in bullets_blob.splitlines():
            m = _BULLET_LINK_RE.match(line)
            if not m:
                # Pass through unrecognised lines unchanged.
                kept_bullets.append(line)
                continue
            url = m.group(2).strip()
            if url in seen:
                continue
            seen[url] = True
            kept_bullets.append(line)
        return header + "\n".join(kept_bullets) + "\n"

    return _READ_MORE_BLOCK_RE.sub(_sub, body)
