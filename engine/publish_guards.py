"""Publish-time guards for episode surfaces (Oct 16 2026 claims audit).

Checks the latest show review asked for at publish time:

1. News-show episode pages must render at least one Source URL.
2. Chapter titles must not be mid-sentence fragments (trailing ``…`` /
   continuation openers).
3. The lead story must get its own named chapter when the show uses
   headline-driven chapters (not ``known_sections_only``).
4. Referral / affiliate / gift-link query params are stripped from
   Source hrefs via :func:`engine.url_utils.strip_tracking` (wired in
   ``engine.blog``).
5. Counterpoint / Both Sides must reference the lead story's entities and
   must not reuse the previous episode's counterpoint opening
   (Oct 16 evening review).
6. Chapter titles must not be raw URL slugs (``tesla-taiwan-megapack-taipei``).
7. The lead chapter must be named after the story — not a generic label
   like ``Top Story``, ``Lead``, or ``The Ten``.

Narrative, interview, and virtual shows are exempt from (1), (3) and (7):
they often have no fetched articles by design (Oct 8 slate review).
"""

from __future__ import annotations

import logging
import re
from typing import List, Optional, Sequence, Set

logger = logging.getLogger(__name__)

# Shows that never go through run_show / have no digest Sources list.
_VIRTUAL_OR_INTERVIEW = frozenset({
    "age_of_ai", "nerra_voices", "nerra_daily",
})

#: Oct 16 2026 (same day): a lesson show teaches from a theme, not from
#: articles, and has no Sources list by design — Привет, Русский! Ep072 and
#: Ep073 would both have been stopped, after the feed was already updated.
_NO_SOURCES_BY_DESIGN = frozenset({"privet_russian"})

_FRAGMENT_ELLIPSIS_RE = re.compile(r"…\s*$")
#: Openers that lean on a sentence before them. Oct 16 2026 (same day): the
#: first list also held "also", "who", "whose", "that", "for" and "still",
#: which named every desk's "Also Today" section, a "WHO warns…" headline and
#: a paper titled "Whose Data, Whose Benchmark?" as fragments — 98 of the 334
#: October episodes would have been stopped, none of them for a cut title.
_CONTINUATION_OPENER_RE = re.compile(
    r"^(?:but|and|so|or|nor|because|which|however|therefore)\b",
    re.I,
)

#: Chapter titles that name the SECTION, not the story (review Oct 15/16).
GENERIC_LEAD_TITLES = frozenset({
    "top story",
    "lead",
    "the lead",
    "the ten",
    "the big story",
    "top news",
    "today's lead story",
    "today's lead",
    "the top story",
})

#: Raw URL-slug chapter titles: lowercase tokens joined by hyphens, no spaces.
_URL_SLUG_TITLE_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+){2,}$")

_COUNTERPOINT_HEADING_RE = re.compile(
    r"^#{2,3}\s+(?:The\s+)?(?:Counterpoint|Both\s+Sides)\b[^\n]*\n",
    re.IGNORECASE | re.MULTILINE,
)
_NEXT_HEADING_RE = re.compile(r"^#{2,3}\s+\S", re.MULTILINE)

#: Tokens too common to count as lead entities.
_STOPWORDS = frozenset({
    "the", "a", "an", "and", "or", "of", "to", "in", "on", "for", "with",
    "from", "by", "at", "as", "is", "are", "was", "were", "be", "been",
    "that", "this", "these", "those", "it", "its", "their", "they", "them",
    "have", "has", "had", "will", "would", "could", "should", "may", "might",
    "about", "into", "over", "after", "before", "than", "then", "also",
    "just", "only", "more", "most", "some", "any", "all", "not", "no",
    "new", "says", "said", "report", "reports", "story", "today", "week",
})


def show_requires_rendered_sources(config) -> bool:
    """True for news shows whose blog Sources panel must not be empty."""
    slug = str(getattr(config, "slug", "") or "")
    if slug in _VIRTUAL_OR_INTERVIEW or slug in _NO_SOURCES_BY_DESIGN:
        return False
    if bool(getattr(config, "narrative_mode", False)):
        return False
    return True


def show_requires_lead_chapter(config) -> bool:
    """True when chapters are headline-driven and the lead should split out."""
    if not show_requires_rendered_sources(config):
        return False
    chapters = getattr(config, "chapters", None)
    if chapters is not None and bool(getattr(chapters, "known_sections_only", False)):
        return False
    return True


def digest_has_rendered_sources(digest_md: str) -> bool:
    """Whether the digest would produce a non-empty Sources panel."""
    from engine.blog import _extract_source_urls
    return bool(_extract_source_urls(digest_md or ""))


def chapter_title_is_fragment(title: str) -> bool:
    """True for clipped mid-sentence titles (ellipsis) or lean-on-previous openers."""
    t = (title or "").strip()
    if not t:
        return True
    if _FRAGMENT_ELLIPSIS_RE.search(t):
        return True
    if _CONTINUATION_OPENER_RE.match(t) and not t.endswith((".", "!", "?")):
        return True
    return False


def chapter_title_is_url_slug(title: str) -> bool:
    """True when *title* looks like a URL path slug, not a human chapter name."""
    t = (title or "").strip()
    if not t or " " in t:
        return False
    return bool(_URL_SLUG_TITLE_RE.match(t))


def lead_title_is_generic(title: str) -> bool:
    """True when the lead chapter is a section label, not the story's name."""
    t = (title or "").strip().lower().rstrip(".:")
    return t in GENERIC_LEAD_TITLES


def assert_chapter_titles_whole(chapters: Sequence) -> List[str]:
    """Return titles that fail the mid-sentence or URL-slug guard (empty = pass)."""
    bad: List[str] = []
    for ch in chapters or []:
        title = getattr(ch, "title", None)
        if title is None and isinstance(ch, dict):
            title = ch.get("title", "")
        title = str(title or "")
        # Structural furniture is allowed ("Introduction", "Closing").
        if title.lower() in {"introduction", "closing", "outro", "sign-off"}:
            continue
        if chapter_title_is_fragment(title) or chapter_title_is_url_slug(title):
            bad.append(title)
    return bad


def _chapter_titles(chapters: Sequence) -> List[str]:
    titles = []
    for ch in chapters or []:
        title = getattr(ch, "title", None)
        if title is None and isinstance(ch, dict):
            title = ch.get("title", "")
        titles.append(str(title or "").strip())
    return titles


def lead_chapter_present(chapters: Sequence, *, hook: str = "") -> bool:
    """True when a chapter after Introduction looks like the lead story.

    Accepts either a title matching the hook (clipped) or any non-furniture,
    non-generic chapter in the second slot — ``_lead_story_split`` places the
    lead immediately after Introduction. Generic labels (``Top Story``,
    ``Lead``, ``The Ten``) fail even when a second chapter exists.
    """
    titles = _chapter_titles(chapters)
    if len(titles) < 2:
        return False
    # Opening chapter is Introduction (or equivalent); lead is next.
    second = titles[1]
    if not second or second.lower() in {"introduction", "closing"}:
        return False
    if chapter_title_is_fragment(second):
        return False
    if lead_title_is_generic(second):
        return False
    if chapter_title_is_url_slug(second):
        return False
    if hook:
        hook_l = hook.lower()
        # Loose: shared content word, or hook prefix in title.
        if second.lower() in hook_l or hook_l[:40] in second.lower():
            return True
        hook_words = {w for w in re.findall(r"[a-z0-9]{4,}", hook_l)}
        title_words = {w for w in re.findall(r"[a-z0-9]{4,}", second.lower())}
        if hook_words and title_words and len(hook_words & title_words) >= 2:
            return True
    # No hook to match — presence of a named (non-generic) second chapter is enough.
    return bool(second)


def extract_counterpoint_body(digest_md: str) -> str:
    """Body of the first Counterpoint / Both Sides section, or ``""``."""
    if not digest_md:
        return ""
    m = _COUNTERPOINT_HEADING_RE.search(digest_md)
    if not m:
        return ""
    rest = digest_md[m.end():]
    end = _NEXT_HEADING_RE.search(rest)
    body = rest[: end.start()] if end else rest
    return body.strip()


def _content_tokens(text: str) -> Set[str]:
    return {
        w for w in re.findall(r"[a-zA-Z][a-zA-Z0-9'-]{3,}", text or "")
        if w.lower() not in _STOPWORDS
    }


def counterpoint_references_lead(
    digest_md: str,
    *,
    hook: str = "",
) -> bool:
    """True when Counterpoint/Both Sides shares entities with the lead/hook.

    Shows without a counterpoint section pass (nothing was promised).
    """
    body = extract_counterpoint_body(digest_md)
    if not body:
        return True
    # Lead = hook + opening block before the counterpoint heading.
    m = _COUNTERPOINT_HEADING_RE.search(digest_md or "")
    lead_text = (digest_md or "")[: m.start()] if m else (digest_md or "")
    if hook:
        lead_text = hook + "\n" + lead_text
    lead_toks = _content_tokens(lead_text)
    cp_toks = _content_tokens(body)
    if not lead_toks or not cp_toks:
        return False
    return len(lead_toks & cp_toks) >= 2


def counterpoint_reused_from_previous(
    digest_md: str,
    previous_digest_md: str,
) -> bool:
    """True when today's counterpoint opens with the previous episode's text."""
    today = extract_counterpoint_body(digest_md)
    prev = extract_counterpoint_body(previous_digest_md)
    if not today or not prev:
        return False
    # Compare the first substantive sentence (normalized).
    def _opener(text: str) -> str:
        chunk = re.split(r"(?<=[.!?])\s+", text.strip(), maxsplit=1)[0]
        return re.sub(r"\s+", " ", chunk).strip().lower()

    a, b = _opener(today), _opener(prev)
    if len(a) < 40 or len(b) < 40:
        return False
    if a == b:
        return True
    # Near-verbatim: shared prefix of 12+ words.
    wa, wb = a.split(), b.split()
    n = 0
    for x, y in zip(wa, wb):
        if x != y:
            break
        n += 1
    return n >= 12


def check_publish_guards(
    *,
    config,
    digest_md: str,
    chapters: Optional[Sequence] = None,
    hook: str = "",
    previous_digest_md: str = "",
) -> List[str]:
    """Return human-readable failure reasons (empty = ok to publish)."""
    failures: List[str] = []
    slug = getattr(config, "slug", "?")

    if show_requires_rendered_sources(config) and not digest_has_rendered_sources(digest_md):
        failures.append(
            f"{slug}: episode page would render with no Sources — "
            "news shows must cite at least one URL before publish"
        )

    if chapters:
        bad_titles = assert_chapter_titles_whole(chapters)
        if bad_titles:
            failures.append(
                f"{slug}: chapter title(s) cut mid-sentence or look like URL slugs: "
                + "; ".join(repr(t) for t in bad_titles[:3])
            )
        if show_requires_lead_chapter(config):
            titles = _chapter_titles(chapters)
            second = titles[1] if len(titles) > 1 else ""
            if lead_title_is_generic(second):
                failures.append(
                    f"{slug}: lead chapter is a generic label {second!r} — "
                    "name it after the story, not 'Top Story'/'Lead'/'The Ten'"
                )
            elif not lead_chapter_present(chapters, hook=hook):
                failures.append(
                    f"{slug}: lead story has no named chapter "
                    "(expected a chapter after Introduction)"
                )

    # Counterpoint / Both Sides: only when the digest has one.
    if extract_counterpoint_body(digest_md):
        if not counterpoint_references_lead(digest_md, hook=hook):
            failures.append(
                f"{slug}: Counterpoint/Both Sides does not reference the lead "
                "story's entities"
            )
        if previous_digest_md and counterpoint_reused_from_previous(
            digest_md, previous_digest_md
        ):
            failures.append(
                f"{slug}: Counterpoint/Both Sides reuses the previous episode's "
                "opening — write today's disagreement, not yesterday's"
            )

    return failures
