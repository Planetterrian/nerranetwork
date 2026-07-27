"""Apple Podcasts category emission, shared by every feed builder.

Apple allows **two** categories per show — a primary and a secondary — each
with a subcategory where the taxonomy offers one. Both appear on their
respective category pages, so the second is a real discoverability slot
that costs nothing to fill.

Two things worth recording, because both were previously misunderstood
here:

* **Technology has no subcategories.** The comment in
  ``engine/config.py`` attributed the network's single-level categories to
  a missing subcategory, and a May 2026 audit was logged on that basis. In
  fact the five Technology shows (Tesla, SpaceX, Models & Agents, M&A for
  Beginners, First Principles) show one genre in Podcasts Connect because
  Apple's Technology category simply has no children. Nothing was
  misconfigured; there was nothing to add. What those shows lacked was a
  *secondary category*, which is a different field.
* **Subcategories are only valid under their own parent.** Emitting
  ``Technology > Tech News`` would be rejected — ``Tech News`` belongs to
  ``News``. Hence the secondary slot rather than a sub on the primary.

Apple's taxonomy (verified July 2026 against
podcasters.apple.com/support/1691-apple-podcasts-categories) puts
subcategories under Arts, Business, Education, Fiction, Health & Fitness,
Kids & Family, Music, News, Religion & Spirituality, Science, Society &
Culture, Sports and TV & Film — but not Technology, Comedy, Government,
History, Leisure or True Crime.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List

logger = logging.getLogger(__name__)


def category_payload(primary: str, primary_sub: str = "",
                     secondary: str = "", secondary_sub: str = "") -> Any:
    """Build the argument for ``fg.podcast.itunes_category``.

    Returns a single dict when only a primary is configured (preserving the
    previous behaviour byte-for-byte, so existing feeds do not churn), or a
    list of two when a secondary is set. An empty *primary* returns None so
    the caller can skip the call entirely.
    """
    primary = (primary or "").strip()
    if not primary:
        return None

    def _one(cat: str, sub: str) -> Dict[str, str]:
        entry = {"cat": cat}
        if sub:
            entry["sub"] = sub
        return entry

    first = _one(primary, (primary_sub or "").strip())
    second_cat = (secondary or "").strip()
    if not second_cat:
        # Preserve the historic shape: a bare string when there is no sub,
        # so a rebuild of an existing feed produces an identical file and
        # the churn-suppression check keeps it out of the commit.
        return first if first.get("sub") else primary

    if second_cat.lower() == primary.lower():
        logger.warning("Secondary category %r duplicates the primary — ignoring",
                       secondary)
        return first if first.get("sub") else primary

    out: List[Dict[str, str]] = [first, _one(second_cat, (secondary_sub or "").strip())]
    return out


def apply_categories(fg, primary: str, primary_sub: str = "",
                     secondary: str = "", secondary_sub: str = "") -> None:
    """Set the show's categories on a FeedGenerator, best-effort.

    A malformed category must never abort a feed build — the feed is far
    more valuable than the category tag — so a failure is logged and the
    call falls back to the primary alone.
    """
    payload = category_payload(primary, primary_sub, secondary, secondary_sub)
    if payload is None:
        return
    try:
        fg.podcast.itunes_category(payload)
    except Exception as exc:  # noqa: BLE001 — never lose the feed over a tag
        logger.warning("Category %r rejected (%s) — falling back to primary",
                       payload, exc)
        try:
            fg.podcast.itunes_category((primary or "").strip())
        except Exception:  # noqa: BLE001
            logger.warning("Primary category %r also rejected — omitting", primary)
