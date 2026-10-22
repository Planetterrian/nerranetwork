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

Oct 22 2026: a section that tells ONE story in prose, with no bold or
numbered item inside it, is a ``section`` item. The first slate read the
lead story out of the record on Models & Agents, AI Chips and Prediction
Markets (``### Top Story``), Models & Agents for Beginners (``### The Big
Story``) and every deep dive, so the tracker could not see that the story
the hook sold had aired. The lead section takes the episode's hook as its
title; a ``Name: subtitle`` section takes its subtitle; anything else takes
its first sentence. Sections that list, schedule or argue about another
section's story (``_STRUCTURAL_SECTIONS``) are not stories.
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

#: Sections that schedule, list, score or argue about another section's
#: story. They air, but they are not a story of their own, and recording them
#: would hand the recurrence notes a "headline" that matches every day.
_STRUCTURAL_SECTIONS = frozenset({
    "on the calendar", "on the horizon", "the board", "the week's board",
    "evidence ledger", "progress watch", "getting around", "the counterpoint",
    "counterpoint", "community buzz", "market watch", "market pulse",
    "explain like i'm 14", "media-literacy note", "what you need to know",
    "strategy spotlight", "practice investment of the day", "portfolio performance",
    "how it works", "weather", "the tape", "listener challenge", "the lever",
    "do positive dispatch", "plain sailing", "intake", "yesterday's trade",
})
#: Section names that hold the episode's lead story.
_LEAD_SECTIONS = frozenset({"top story", "the big story", "lead", "the lead",
                            "lead story", "today's lead story"})
#: Prose under this many words is a note, not a story.
_SECTION_STORY_MIN_WORDS = 40
_SECTION_TITLE_MAX_WORDS = 16

_BOLD_RE = re.compile(r"\*\*(.+?)\*\*")
_SENTENCE_END_RE = re.compile(r"(?<=[.!?])\s+")
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
    #: ``item`` (developed), ``also_today``, ``heading`` (Omni View),
    #: ``section`` (a section told as one story) or ``essay`` (a narrative
    #: episode told as one story).
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


def _section_story_title(full: str, body: str, hook: str, is_lead: bool) -> str:
    """The title of a section told as one story (see the module docstring)."""
    if is_lead and hook:
        return hook
    if ":" in full:
        sub = full.split(":", 1)[1].strip().strip("*")
        if len(sub.split()) >= 3:
            return _plain(sub)
    text = _plain(re.sub(r"\(?\bSource:.*$", "", body, flags=re.M))
    first = _SENTENCE_END_RE.split(text, maxsplit=1)[0] if text else ""
    words = first.split()
    return " ".join(words[:_SECTION_TITLE_MAX_WORDS]).rstrip(",;:")


def extract_aired_items(digest: str) -> List[AiredItem]:
    """Every story the digest told, in order. See the module docstring."""
    out: List[AiredItem] = []
    hook = _plain(hook_line(digest or ""))
    lead_taken = False
    for full, body in sections(digest or "", full_titles=True):
        title = full.split(":")[0].strip().strip("*")
        low = title.strip().lower()
        if low in _NON_STORY_SECTIONS:
            continue
        if _HEADING_ITEM_RE.match(full):
            out.append(AiredItem(section=title, title=_strip_outlet(_plain(_LEAD_NUM_RE.sub("", full))),
                                 body=body.strip(), urls=urls_in(body), kind="heading"))
            lead_taken = True
            continue
        kind = "also_today" if low == ALSO_TODAY_SECTION.lower() else "item"
        before = len(out)
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
        if len(out) > before:
            lead_taken = True
            continue
        if (not title or low in _STRUCTURAL_SECTIONS or kind == "also_today"
                or any(low.startswith(s + " ") for s in _STRUCTURAL_SECTIONS)):
            continue
        if len(_plain(body).split()) < _SECTION_STORY_MIN_WORDS:
            continue
        lines = [ln for ln in body.splitlines() if ln.strip()]
        if lines and sum(ln.lstrip().startswith(("- ", "* ", "• ")) for ln in lines) * 2 >= len(lines):
            continue  # a list of tips or notes, not one story
        is_lead = low in _LEAD_SECTIONS and not lead_taken
        st = _section_story_title(full, body, hook, is_lead)
        if st:
            out.append(AiredItem(section=title, title=st, body=body.strip(),
                                 urls=urls_in(body), kind="section"))
            lead_taken = True
    # A digest made only of prose sections is a narrative episode: one essay.
    if any(i.kind != "section" for i in out):
        return out
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
