"""Server-rendered cards for the summaries pages.

Every show's summaries page is built entirely in the browser: the committed
HTML ships a ``<div id="summaries-container">`` holding the words *"Loading
… summaries…"* and a script that fetches the JSON and writes the list. With
JavaScript off, or before the fetch resolves, or for a crawler that does not
execute scripts, the page IS that sentence.

That has been true of ``nerra-daily-summaries.html`` — the archive of the
network's most-visited show — since it was created, and it was deferred twice
because "search engines run JavaScript now". They do, sometimes, on a delay,
with no guarantee, and none of that helps a reader on a train.

So the first :data:`SSR_CARD_LIMIT` cards are rendered at build time. The
script still replaces the whole container on load, which is what makes this
cheap: the server-rendered cards are a floor, not a second implementation to
keep in sync. They carry what a reader needs — date, title, the summary, a
player, a link to the transcript — and deliberately not the interactive
parts (language pills, share buttons, the sticky player), because those need
the script anyway and a dead button is worse than no button.

**The markdown subset matches the client's** ``renderMarkdown`` — headings,
bullets, bold, blockquote hooks, rules — because the same text must not look
like two different documents either side of the fetch. It is a subset on
purpose: no links are auto-linkified here, since the escaped output is what
guarantees the safety of injecting it.
"""

from __future__ import annotations

import html
import json
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

#: How many cards are rendered into the page. Twenty is the whole first
#: screenful and several more, and it is where the size cost stops buying
#: anything: the JSON holds ~30 episodes and the script replaces all of them
#: milliseconds later. Raising it grows every one of ~18 committed pages.
SSR_CARD_LIMIT = 20

_BULLET_RE = re.compile(r"^[-•]\s+")
_RULE_RE = re.compile(r"^(-{3,}|—{3,}|━{3,})$")
_BOLD_RE = re.compile(r"\*\*([^*]+)\*\*")


def _bold(text: str) -> str:
    """``**x**`` -> ``<strong>x</strong>``, on already-escaped text."""
    return _BOLD_RE.sub(r"<strong>\1</strong>", text)


def summary_to_html(markdown: str) -> str:
    """Render the client's markdown subset, server side.

    The input is escaped FIRST and every transformation runs on the escaped
    string, so nothing in a summary can inject markup. That is also why this
    does not linkify: the escaping is the safety property, and rebuilding
    anchors from escaped text is how it gets lost.
    """
    safe = html.escape(markdown or "").replace("\r\n", "\n")
    out: List[str] = []
    in_list = False

    def flush() -> None:
        nonlocal in_list
        if in_list:
            out.append("</ul>")
            in_list = False

    for raw in safe.split("\n"):
        line = raw.strip()

        if not line:
            flush()
            continue

        if _RULE_RE.match(line):
            flush()
            out.append('<hr style="border:none;border-top:1px solid '
                       'var(--nn-border);margin:1rem 0;">')
            continue

        # The hook, which the digests write as a bold blockquote.
        if line.startswith("&gt; "):
            flush()
            hook = _BOLD_RE.sub(r"\1", line[5:])
            out.append(
                '<p style="border-left:3px solid var(--show-color, '
                f'var(--nn-purple));padding-left:0.75rem;font-weight:600;">'
                f"{hook}</p>")
            continue

        for prefix, tag in (("### ", "h3"), ("## ", "h2"), ("# ", "h3")):
            if line.startswith(prefix):
                flush()
                out.append(f"<{tag}>{line[len(prefix):]}</{tag}>")
                break
        else:
            if _BULLET_RE.match(line):
                if not in_list:
                    out.append("<ul>")
                    in_list = True
                out.append(f"<li>{_bold(_BULLET_RE.sub('', line))}</li>")
                continue
            flush()
            out.append(f"<p>{_bold(line)}</p>")

    flush()
    return "".join(out)


#: How much of a summary the combined show-page card shows before the reader
#: follows it to the article. The show page script cuts at the same number,
#: because it replaces this text on load: two lengths would make the card
#: visibly twitch a moment after paint.
CARD_PREVIEW_CHARS = 200

#: Below this a hook is a label, not a sentence — Привет, Русский!'s is one
#: word, its word of the day — so the preview keeps reading past it.
SHORT_HOOK_CHARS = 60

_HOOK_RE = re.compile(r"^>\s*(.+?)\s*$")
_EMPHASIS_RE = re.compile(r"[*_]{1,2}")
_URL_RE = re.compile(r"https?://\S+")
_WS_RE = re.compile(r"\s+")


def _preview_line(raw: str) -> str:
    """One summary line reduced to its plain words, or "" to skip it.

    Skipped: markdown headings (every digest opens on the show's own name,
    which the card already says twice), horizontal rules, and short label
    lines with no sentence in them — ``**Date:** August 23, 2026`` and
    ``**REAL-TIME TSLA price:** $348.95 ▼ $13.91 (3.8%)`` are metadata that
    the page has better places for, and both used to be the first thing the
    summary said.
    """
    line = raw.strip()
    if not line or line.startswith("#") or _RULE_RE.match(line):
        return ""
    hook = _HOOK_RE.match(line)
    if hook:
        line = hook.group(1)
    line = _WS_RE.sub(" ", _EMPHASIS_RE.sub("", _URL_RE.sub("", line))).strip()
    if not line:
        return ""
    # A short "Label: value" with no sentence in it. The terminal-punctuation
    # test reads the END of the line, never anywhere in it: Tesla's price line
    # ends "(3.8%)" and an "is there a full stop" search matched the decimal
    # point, which is how "REAL-TIME TSLA price: $348.95" led the card.
    if (":" in line[:40]
            and not line.rstrip().endswith((".", "!", "?", "\u2026"))
            and len(line.split()) < 10):
        return ""
    return line


def plain_preview(content: str, limit: int = CARD_PREVIEW_CHARS) -> str:
    """The opening of a summary as one line of plain text.

    The digests write their headline as a blockquoted bold line — the hook —
    and it is the sentence the episode was built around, so it leads. A hook
    too short to be a sentence keeps reading into the prose under it; a show
    with no hook at all (the interviews, Nerra Daily) starts from its first
    real line.

    ``show_page.html.j2`` carries the same walk in JavaScript and replaces
    this text on load. The duplication is deliberate and it is the cheap
    half: the alternative is the server rendering one sentence and the script
    swapping in a different one a moment later.
    """
    lines = (content or "").splitlines()
    # A hook is the episode's own headline, written for exactly this job, so
    # everything above it is preamble by definition: the show name, the
    # emoji-and-tagline branding line, the date, the stock price. Four shows'
    # previews used to open on their own branding for want of this line.
    for index, raw in enumerate(lines):
        if _HOOK_RE.match(raw.strip()):
            lines = lines[index:]
            break

    parts: List[str] = []
    for raw in lines:
        line = _preview_line(raw)
        if not line:
            continue
        parts.append(line)
        joined = " ".join(parts)
        if len(joined) >= limit or (
                len(parts) == 1 and len(line) >= SHORT_HOOK_CHARS):
            break
    text = _WS_RE.sub(" ", " ".join(parts)).strip()
    return text[:limit].rstrip() + "..." if len(text) > limit else text


def _display_date(value: str) -> str:
    """``2026-09-21`` -> ``September 21, 2026``; anything else passes through.

    Matches the client's ``formatDate`` so the card does not visibly change
    shape when the script takes over.
    """
    from datetime import datetime

    value = (value or "").strip()
    for fmt in ("%Y-%m-%d", "%B %d, %Y", "%b %d, %Y"):
        try:
            parsed = datetime.strptime(value, fmt)
        except ValueError:
            continue
        return f"{parsed.strftime('%B')} {parsed.day}, {parsed.year}"
    return value


def _records(data: Any) -> List[dict]:
    """The episode list out of either committed summaries shape."""
    if isinstance(data, list):
        return [r for r in data if isinstance(r, dict)]
    if not isinstance(data, dict):
        return []
    for key in ("summaries", "episodes"):
        value = data.get(key)
        if isinstance(value, list):
            return [r for r in value if isinstance(r, dict)]
    for value in data.values():
        if isinstance(value, list):
            return [r for r in value if isinstance(r, dict)]
    return []


def _episode_number(record: dict) -> Optional[int]:
    for key in ("episode_num", "episode"):
        value = record.get(key)
        if isinstance(value, int):
            return value
        if isinstance(value, str) and value.isdigit():
            return int(value)
    return None


def summary_cards(
    json_path,
    show_slug: str,
    *,
    limit: int = SSR_CARD_LIMIT,
) -> List[Dict[str, Any]]:
    """The newest *limit* episodes as template-ready card dicts.

    Returns ``[]`` for a missing, unreadable or empty file — a show with no
    episodes is a real state, and the page keeps its existing empty message
    rather than rendering an empty rail.
    """
    path = Path(json_path)
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return []

    records = _records(data)
    if not records:
        return []

    # The committed files are oldest-first; the page shows newest-first.
    # Sort by episode number where there is one, and otherwise keep document
    # order reversed rather than inventing an ordering from a date string
    # that three shows format differently.
    if all(_episode_number(r) is not None for r in records):
        records = sorted(records, key=_episode_number, reverse=True)
    else:
        records = list(reversed(records))

    cards = []
    for record in records[:max(0, limit)]:
        number = _episode_number(record)
        cards.append({
            "date_raw": record.get("date", ""),
            "date": _display_date(record.get("date", "")),
            "title": (record.get("episode_title") or record.get("title")
                      or "").strip(),
            "summary_html": summary_to_html(
                record.get("content") or record.get("summary") or ""),
            "summary_preview": plain_preview(
                record.get("content") or record.get("summary") or ""),
            "audio_url": (record.get("audio_url") or "").strip(),
            "episode_num": number,
            "blog_url": (f"blog/{show_slug}/ep{number:03d}.html"
                         if isinstance(number, int) else ""),
            "guest": (record.get("guest") or "").strip(),
        })
    return cards
