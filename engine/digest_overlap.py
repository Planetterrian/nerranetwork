"""Cross-section duplicate removal for generated digests.

Every daily digest prompt carries an "ABSOLUTE RULE — ZERO STORY OVERLAP"
paragraph, and it does not hold: Tesla Ep592 (2026-09-02) shipped five
X Takeover items whose Source URLs were the same five as Top 12 items
4, 3, 6, 11 and 7; Ep594's Short Spot re-used story 11's URL. Because the
podcast stage writes the digest out almost sentence for sentence
(`engine.script_audit` measures 60-78% verbatim 8-gram overlap on the
flagships), every duplicate in the digest is a duplicate in the audio — a
story told twice ten minutes apart, which is the redundancy listeners
notice first.

This module is the data-side enforcement: parse the digest into item
blocks, and when a later block repeats an earlier one — same Source URL,
or a headline that is the same story in different words — drop the later
block and renumber. The earlier occurrence wins because the digest orders
sections by importance (Top News first). Essay sections with no URL or
bold headline (First Principles, Engineering Deep Dive) are never touched
here; that is the prompt's job, and `script_audit` measures the result.

Deterministic, no LLM call, safe on any text: a digest with no items
returns unchanged.
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import List, Optional, Tuple
from urllib.parse import urlsplit, urlunsplit

from engine.utils import calculate_similarity

logger = logging.getLogger(__name__)

_HEADER_RE = re.compile(r"^\s*#{1,6}\s+(.+?)\s*$")
_URL_RE = re.compile(
    r"(?im)\bSource(?:/Post)?\s*:\s*\[?\s*(https?://[^\s\]\)]+)"
)
_BOLD_RE = re.compile(r"\*\*(.+?)\*\*")
_NUMBERED_RE = re.compile(r"^(\s*)(\d+)\.(\s)")
_LABEL_PREFIXES = (
    "hook", "date", "real-time", "what you need to know", "title",
    "story title", "catchy title",
)
_STOPWORDS = frozenset(
    "the a an and or of to in on for with from by at as is are was were be "
    "been its it this that these those into over after before about than "
    "new says said will has have had not but amid via per".split()
)

# A later item is the same story as an earlier one when its headline shares
# this much of its salient vocabulary, or when the two headlines read as
# near-identical sentences. Both thresholds were set against the committed
# Tesla Ep592 digest (five true duplicates re-headlined for the X Takeover
# section) and the surrounding week (no false positives).
TITLE_JACCARD_THRESHOLD = 0.5
TITLE_SIMILARITY_THRESHOLD = 0.72
# Re-headlined duplicates (Ep592's five X Takeover items carried no Source
# line and fresh headlines) share the BODY's salient vocabulary instead:
# overlap coefficient 0.51-0.72 on the true duplicates against a long tail
# at <=0.3 for unrelated items (160-digest sweep, Aug-Sep 2026).
BODY_OVERLAP_THRESHOLD = 0.5
BODY_MIN_SHARED_TOKENS = 8
MIN_ITEM_CHARS = 40


@dataclass
class DuplicateItem:
    section: str
    title: str
    kept_section: str
    reason: str


@dataclass
class DedupeResult:
    text: str
    removed: List[DuplicateItem] = field(default_factory=list)

    @property
    def count(self) -> int:
        return len(self.removed)


def _canonical_url(url: str) -> str:
    try:
        parts = urlsplit(url.strip().rstrip(".,);"))
    except ValueError:
        return url.strip().lower()
    query = "&".join(
        kv for kv in parts.query.split("&")
        if kv and not kv.lower().startswith(("utm_", "ref=", "src="))
    )
    path = parts.path.rstrip("/")
    host = parts.netloc.lower()
    if host.startswith("www."):
        host = host[4:]
    return urlunsplit((parts.scheme.lower(), host, path, query, ""))


def _salient_tokens(title: str) -> frozenset:
    words = re.findall(r"[a-z0-9][a-z0-9'’-]*", title.lower())
    return frozenset(w for w in words if len(w) >= 3 and w not in _STOPWORDS)


def _item_title(block: str) -> Optional[str]:
    """The bold headline of an item block, or None when the block is not an item."""
    for m in _BOLD_RE.finditer(block):
        raw = m.group(1).strip()
        low = raw.lower().rstrip(":").strip()
        if any(low.startswith(p) for p in _LABEL_PREFIXES):
            continue
        # A bold label that ends the bold span with a colon and carries no
        # headline ("**Current status:**") is not an item title.
        if raw.endswith(":") and len(raw.split()) <= 4:
            continue
        # Drop a trailing ": Source Name" / " - Source" attribution tail
        # so "Title: Teslarati" and "Title" compare equal.
        head = re.split(r"\s*[:\-—]\s*(?=[A-Z@][\w .@'-]{1,40}$)", raw, maxsplit=1)[0]
        return head.strip() or raw
    return None


def _body_tokens(block: str) -> frozenset:
    body = "\n".join(
        line for line in block.split("\n")
        if not re.match(r"\s*Source(?:/Post)?\s*:", line, re.IGNORECASE)
    )
    return _salient_tokens(_BOLD_RE.sub(" ", body))


def _same_story(title_a: str, title_b: str) -> Optional[str]:
    ta, tb = _salient_tokens(title_a), _salient_tokens(title_b)
    if ta and tb and len(ta & tb) >= 3:
        jaccard = len(ta & tb) / len(ta | tb)
        if jaccard >= TITLE_JACCARD_THRESHOLD:
            return f"headline shares {jaccard:.0%} of its salient words"
    sim = calculate_similarity(title_a, title_b)
    if sim >= TITLE_SIMILARITY_THRESHOLD:
        return f"headline {sim:.0%} similar"
    return None


def _same_body(tokens_a: frozenset, tokens_b: frozenset) -> Optional[str]:
    shared = len(tokens_a & tokens_b)
    if shared < BODY_MIN_SHARED_TOKENS or not tokens_a or not tokens_b:
        return None
    overlap = shared / min(len(tokens_a), len(tokens_b))
    if overlap >= BODY_OVERLAP_THRESHOLD:
        return f"body shares {overlap:.0%} of its salient words"
    return None


def _split_blocks(text: str) -> List[str]:
    """Paragraph blocks, additionally split at every numbered-item start.

    Tesla's X Takeover items (and any section the model writes without
    blank lines between items) arrive as ONE paragraph of five ``1. **…**``
    lines; splitting only on blank lines would compare one headline and
    miss the other four.
    """
    out: List[str] = []
    for para in re.split(r"\n[ \t]*\n", text):
        lines = para.split("\n")
        current: List[str] = []
        for line in lines:
            starts_item = _NUMBERED_RE.match(line) and _BOLD_RE.search(line)
            # Section headers also start a block: the templates put the
            # "### Top News" line directly under the hook with no blank
            # line, so it would otherwise hide inside the preamble block.
            if current and (starts_item or _HEADER_RE.match(line)):
                out.append("\n".join(current))
                current = []
            current.append(line)
        if current:
            out.append("\n".join(current))
    return out


_SEPARATOR_RE = re.compile(r"^\s*(?:━+|-{3,}|\*{3,}|_{3,})\s*$")


def _lead_line(block: str) -> Tuple[str, str]:
    """(first meaningful line, the rest) — skipping the ━━━ separator rows
    the digest templates put directly above each section header."""
    lines = block.strip().split("\n")
    while lines and _SEPARATOR_RE.match(lines[0]):
        lines.pop(0)
    if not lines:
        return "", ""
    return lines[0], "\n".join(lines[1:])


def _renumber(blocks: List[str]) -> List[str]:
    """Re-sequence '1. ' item numbers within each header-delimited section."""
    out: List[str] = []
    counter = 0
    for block in blocks:
        first, _ = _lead_line(block)
        if _HEADER_RE.match(first) or _SEPARATOR_RE.match(first or "━"):
            counter = 0
            out.append(block)
            continue
        m = _NUMBERED_RE.match(block)
        if m:
            counter += 1
            block = _NUMBERED_RE.sub(
                lambda mm: f"{mm.group(1)}{counter}.{mm.group(3)}", block, count=1
            )
        out.append(block)
    return out


def dedupe_cross_section_items(
    digest_text: str, *, show_name: str = "digest"
) -> DedupeResult:
    """Drop later items that repeat an earlier item's URL or headline.

    Returns the cleaned text plus a record of what was removed (the caller
    logs it and records the count as a metric). Item numbering is
    re-sequenced within each section after removal.
    """
    if not digest_text or "\n" not in digest_text:
        return DedupeResult(digest_text or "")

    blocks = _split_blocks(digest_text)
    section = ""
    in_sections = False  # items live under a ##/### header, never in the preamble
    seen_urls: dict = {}      # canonical url -> (section, title)
    seen_titles: list = []    # (section, title)
    seen_bodies: list = []    # (section, title, body tokens)
    drop: set = set()
    removed: List[DuplicateItem] = []

    for idx, block in enumerate(blocks):
        stripped = block.strip()
        if not stripped:
            continue
        first_line, body = _lead_line(stripped)
        hm = _HEADER_RE.match(first_line)
        if hm:
            section = hm.group(1).strip()
            in_sections = in_sections or first_line.lstrip().startswith("##")
            # A header block can also carry the section's first item.
            if not body.strip():
                continue
        if not in_sections or len(stripped) < MIN_ITEM_CHARS:
            # The preamble (title, date, price, the bold HOOK sentence) is
            # not an item — the hook is SUPPOSED to be the lead story.
            continue
        title = _item_title(stripped)
        urls = [_canonical_url(u) for u in _URL_RE.findall(stripped)]
        if title is None and not urls:
            continue  # prose paragraph (essay section) — never touched here

        reason = None
        kept_section = ""
        for url in urls:
            if url in seen_urls:
                kept_section = seen_urls[url][0]
                reason = "same source URL"
                break
        if reason is None and title:
            for prior_section, prior_title in seen_titles:
                why = _same_story(prior_title, title)
                if why:
                    kept_section, reason = prior_section, why
                    break
        body_tokens = _body_tokens(stripped)
        if reason is None:
            for prior_section, prior_title, prior_tokens in seen_bodies:
                why = _same_body(prior_tokens, body_tokens)
                if why:
                    kept_section, reason = prior_section, why
                    break

        if reason:
            drop.add(idx)
            removed.append(DuplicateItem(
                section=section, title=(title or urls[0])[:120],
                kept_section=kept_section, reason=reason,
            ))
            continue

        for url in urls:
            seen_urls.setdefault(url, (section, title or ""))
        if title:
            seen_titles.append((section, title))
        seen_bodies.append((section, title or "", body_tokens))

    if not drop:
        return DedupeResult(digest_text)

    kept = [b for i, b in enumerate(blocks) if i not in drop]
    for item in removed:
        logger.warning(
            "[%s] dropped duplicate digest item from '%s' (%s; first told in "
            "'%s'): %r", show_name, item.section, item.reason,
            item.kept_section, item.title[:80],
        )
    return DedupeResult("\n\n".join(_renumber(kept)), removed)


def digest_overlap_summary(result: DedupeResult) -> Tuple[int, str]:
    """(count, one-line summary) for logs and GitHub annotations."""
    if not result.removed:
        return 0, ""
    parts = [f"{d.section or '?'} ← {d.kept_section or '?'}: {d.title[:50]}"
             for d in result.removed]
    return len(result.removed), "; ".join(parts)
