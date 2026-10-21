"""The stories a published digest actually told — one reader for every store.

Oct 21 2026 (review ``docs/reviews/content_lake_and_story_catalog_2026_10_21.md``).
Three stores remembered "what a show covered" and none of them read it from
the digest that shipped:

* the cross-episode tracker recorded every article the PROMPT listed (up to
  60) as covered, so 63-75% of the "ALREADY-COVERED" notes cited stories that
  never aired, and an article a show passed over was blocked from its prompt
  for 45 days;
* the content lake that CI rebuilds from the repo carried no headlines or
  links at all, so the cross-show prompt block never fired;
* nothing durable linked a story across days or shows.

This module is the one definition of an aired item. It reads the shapes the
shows write — a numbered item, a block that opens on a bold head and carries
a link, an Omni View ``### N) Title`` heading — the same shapes
``engine.digest_lint.story_item_count`` counts, so the tracker, the lake, the
story catalog and the ``items_shipped`` metric agree on what a story is. A
narrative episode (no items) is one ``essay`` item: the hook and every link.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import List

from engine.digest_lint import (
    ALSO_TODAY_SECTION,
    _BOLD_HEAD_RE,
    _HEADING_ITEM_RE,
    _NUMBERED_ITEM_RE,
    hook_line,
    items,
    sections,
    urls_in,
)

#: Sections that list links for a reader and tell no story of their own.
_NON_STORY_SECTIONS = frozenset({
    "sources", "read more", "read more (sources)", "further reading",
    "links", "references", "verified claims",
})

_BOLD_RE = re.compile(r"\*\*(.+?)\*\*")
_MD_LINK_RE = re.compile(r"\[([^\]]*)\]\([^)]*\)")
_LEAD_NUM_RE = re.compile(r"^\s*\d+[.)]\s*")
#: A title written ``Title: Outlet`` or ``Title — Outlet``; the tail is an
#: outlet when it is this short.
_OUTLET_TAIL_MAX_WORDS = 6
#: ``**Why This Teaches:** …`` / ``**Confidence Level:** …`` — a field label,
#: not a story (Modern Investing's pick block). A real ``**Title — Outlet:**``
#: head runs longer than this.
_FIELD_LABEL_MAX_WORDS = 4


@dataclass
class AiredItem:
    section: str
    title: str
    body: str
    urls: List[str] = field(default_factory=list)
    #: ``item`` (developed), ``also_today``, ``heading`` (Omni View) or
    #: ``essay`` (a narrative episode told as one story).
    kind: str = "item"

    def as_dict(self) -> dict:
        return {"section": self.section, "title": self.title, "body": self.body,
                "urls": list(self.urls), "kind": self.kind}


def _plain(text: str) -> str:
    text = _MD_LINK_RE.sub(r"\1", text or "")
    text = text.replace("**", "").replace("__", "")
    return re.sub(r"\s+", " ", text).strip()


def _strip_outlet(title: str) -> str:
    for sep in (": ", " — ", " – ", " - "):
        if sep in title:
            head, tail = title.rsplit(sep, 1)
            if head.strip() and len(tail.split()) <= _OUTLET_TAIL_MAX_WORDS and len(head.split()) >= 3:
                return head.strip()
    return title


def is_field_label(head: str) -> bool:
    """``**Label:** value`` with a label of a few words."""
    m = _BOLD_RE.search(_LEAD_NUM_RE.sub("", head or ""))
    if not m:
        return False
    inner = m.group(1).strip()
    return inner.endswith(":") and len(inner.rstrip(":").split()) <= _FIELD_LABEL_MAX_WORDS


def item_title(head: str) -> str:
    """The headline of an item from its first line.

    ``1. **Tesla wins X: Reuters**`` → ``Tesla wins X``; ``**Title — Outlet:**
    sentence`` → ``Title``; a bold head with no title shape falls back to the
    line's opening words."""
    line = _LEAD_NUM_RE.sub("", head or "")
    m = _BOLD_RE.search(line)
    inner = m.group(1) if m else line
    inner = _plain(inner).strip().rstrip(":").strip()
    if not inner:
        inner = _plain(line)
    return _strip_outlet(inner)


def extract_aired_items(digest: str) -> List[AiredItem]:
    """Every story the digest told, in order. See the module docstring."""
    out: List[AiredItem] = []
    for title, body in sections(digest or ""):
        low = title.strip().lower()
        if low in _NON_STORY_SECTIONS:
            continue
        if _HEADING_ITEM_RE.match(title):
            out.append(AiredItem(section=title, title=_strip_outlet(_plain(_LEAD_NUM_RE.sub("", title))),
                                 body=body.strip(), urls=urls_in(body), kind="heading"))
            continue
        kind = "also_today" if low == ALSO_TODAY_SECTION.lower() else "item"
        for block in items(body):
            head = block.splitlines()[0]
            if not (_NUMBERED_ITEM_RE.match(head) or (_BOLD_HEAD_RE.match(head) and urls_in(block))):
                continue
            if is_field_label(head):
                continue
            t = item_title(head)
            if not t:
                continue
            out.append(AiredItem(section=title, title=t, body=block.strip(),
                                 urls=urls_in(block), kind=kind))
    if out:
        return out
    hook = _plain(hook_line(digest or ""))
    if not hook:
        return []
    return [AiredItem(section="", title=hook, body=(digest or "").strip(),
                      urls=urls_in(digest or ""), kind="essay")]


def aired_titles(digest: str) -> List[str]:
    return [i.title for i in extract_aired_items(digest)]


def aired_urls(digest: str) -> List[str]:
    seen, out = set(), []
    for item in extract_aired_items(digest):
        for u in item.urls:
            if u not in seen:
                seen.add(u)
                out.append(u)
    return out


__all__ = ["AiredItem", "extract_aired_items", "aired_titles", "aired_urls", "item_title"]
