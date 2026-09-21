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
            "audio_url": (record.get("audio_url") or "").strip(),
            "episode_num": number,
            "blog_url": (f"blog/{show_slug}/ep{number:03d}.html"
                         if isinstance(number, int) else ""),
            "guest": (record.get("guest") or "").strip(),
        })
    return cards
