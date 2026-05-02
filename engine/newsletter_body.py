"""Body-text transforms applied to a daily newsletter's markdown.

The wrapper (``engine.newsletter_template.wrap_with_branding``) handles
hero / featured-episode / footer / etc. — but the *middle of the email*
is still the raw markdown body produced by the LLM (the digest text).

This module post-processes that body so:

  - Russian vocabulary list (Привет, Русский!) renders as a card stack
    instead of a `field: value` plaintext dump (spec §2.3).
  - Tesla daily's box-drawing horizontal rules become proper ``<hr>``
    HTML separators that respect dark mode (spec §5.2).
  - Tesla's "REAL-TIME TSLA price:" line becomes a styled stock-watch
    block instead of a bold label + raw text (spec §5.3).

The transforms are conservative: they pattern-match a recognisable
shape and only fire when matched. A digest that doesn't contain (e.g.)
the vocab format passes through unchanged.

All transforms are idempotent — running twice produces the same output
as once. They're also applied *after* ``scrub_scaffold`` from
``engine.newsletter_sanitizer`` so labels like ``**Vocabulary List
(8-12 words/phrases):**`` are already gone by the time we run.
"""

from __future__ import annotations

import re
from typing import List


# ---------------------------------------------------------------------------
# Box-drawing horizontal rules → <hr>
# ---------------------------------------------------------------------------

_BOX_RULE_RE = re.compile(r"(?m)^\s*(?:━|─|═){3,}\s*$")


def replace_box_rules_with_hr(body: str) -> str:
    """Replace runs of box-drawing horizontal rules with HTML ``<hr>``.

    The Tesla daily previously rendered ``━━━━━━━━━━━━━━━━━━━━`` as
    section separators. In email those characters are visible literals
    (most fonts don't merge them into a horizontal line) and Outlook
    Win renders them as boxes. Replace with a styled ``<hr>`` that
    respects dark-mode override (set in ``_DARK_MODE_STYLE``).
    """
    if not body:
        return body
    return _BOX_RULE_RE.sub(
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
        if arrow == "▲":
            delta_color = "#10b981"
        elif arrow == "▼":
            delta_color = "#ef4444"
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
            'border-left:3px solid #f59e0b;">'
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
# Public combined transform
# ---------------------------------------------------------------------------

def transform_daily_body(body: str, *, slug: str = "") -> str:
    """Apply every body transform in the right order.

    Order matters:

      1. Box rules → ``<hr>`` (cheapest, fires for everyone)
      2. Shorten Google News tracking URLs in "Source: …" lines
         (universal — every show is potentially affected)
      3. Dedup "Read more" source lists (Omni View — repeated URLs)
      4. TSLA price block (Tesla only)
      5. Russian vocab cards (Привет only)

    Each transform is a no-op when its trigger pattern isn't present,
    so calling this for every show is safe.
    """
    body = replace_box_rules_with_hr(body)
    body = shorten_source_urls(body)
    if slug == "omni_view":
        body = dedup_read_more_sources(body)
    if slug == "tesla":
        body = render_tsla_price_block(body)
    if slug == "privet_russian":
        body = render_russian_vocab_cards(body)
    return body


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
