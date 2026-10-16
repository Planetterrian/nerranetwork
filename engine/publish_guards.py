"""Publish-time guards for episode surfaces (Oct 16 2026 claims audit).

Four checks the latest show review asked for at publish time:

1. News-show episode pages must render at least one Source URL.
2. Chapter titles must not be mid-sentence fragments (trailing ``…`` /
   continuation openers).
3. The lead story must get its own named chapter when the show uses
   headline-driven chapters (not ``known_sections_only``).
4. Referral / affiliate / gift-link query params are stripped from
   Source hrefs via :func:`engine.url_utils.strip_tracking` (wired in
   ``engine.blog``).

Narrative, interview, and virtual shows are exempt from (1) and (3):
they often have no fetched articles by design (Oct 8 slate review).
"""

from __future__ import annotations

import logging
import re
from typing import List, Optional, Sequence

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


def assert_chapter_titles_whole(chapters: Sequence) -> List[str]:
    """Return titles that fail the mid-sentence guard (empty = pass)."""
    bad: List[str] = []
    for ch in chapters or []:
        title = getattr(ch, "title", None)
        if title is None and isinstance(ch, dict):
            title = ch.get("title", "")
        title = str(title or "")
        # Structural furniture is allowed ("Introduction", "Closing").
        if title.lower() in {"introduction", "closing", "outro", "sign-off"}:
            continue
        if chapter_title_is_fragment(title):
            bad.append(title)
    return bad


def lead_chapter_present(chapters: Sequence, *, hook: str = "") -> bool:
    """True when a chapter after Introduction looks like the lead story.

    Accepts either a title matching the hook (clipped) or any non-furniture
    chapter in the second slot — ``_lead_story_split`` places the lead
    immediately after Introduction.
    """
    titles = []
    for ch in chapters or []:
        title = getattr(ch, "title", None)
        if title is None and isinstance(ch, dict):
            title = ch.get("title", "")
        titles.append(str(title or "").strip())
    if len(titles) < 2:
        return False
    # Opening chapter is Introduction (or equivalent); lead is next.
    second = titles[1]
    if not second or second.lower() in {"introduction", "closing"}:
        return False
    if chapter_title_is_fragment(second):
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
    # No hook to match — presence of a named second chapter is enough.
    return bool(second)


def check_publish_guards(
    *,
    config,
    digest_md: str,
    chapters: Optional[Sequence] = None,
    hook: str = "",
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
                f"{slug}: chapter title(s) cut mid-sentence: "
                + "; ".join(repr(t) for t in bad_titles[:3])
            )
        if show_requires_lead_chapter(config):
            if not lead_chapter_present(chapters, hook=hook):
                failures.append(
                    f"{slug}: lead story has no named chapter "
                    "(expected a chapter after Introduction)"
                )

    return failures
