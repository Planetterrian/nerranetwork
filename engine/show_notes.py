"""A Sources line for the podcast show notes (Sep 24 2026).

The RSS ``<description>`` a listener reads in Apple Podcasts or Spotify
carried the first 500 characters of the digest, the AI disclosure and the
site links — and no source at all. Every ``Source:`` line had been scrubbed
from that copy as leakage. The launch-cohort research put visible sourcing
first among the things that repair trust in AI-produced news (a list of the
sources used offsets the AI label where an explanation does not), and the
blog post already renders one; the feed, where most listeners are, did not.

:func:`sources_footer` builds one compact markdown line from the digest's
``Source:`` links — publisher domains, each linked to the first article
cited from it, in document order, deduplicated by registrable domain, at
most :data:`MAX_SOURCES` — that ``engine.publisher._markdown_to_rss_html``
turns into anchors. No sources, no line. It reads the digest only; it never
touches audio, the claims ledger or the digest itself.

Corrections (Oct 1 2026). The policy pages promised that "substantive
corrections are noted in the next episode's show notes" with nothing behind
the sentence. :func:`corrections_footer` renders the corrections filed
against THIS episode (its description is rewritten on the feed rebuild the
correction triggers) and :func:`carried_corrections_footer` the one-line
"Correction to episode N: …" the NEXT episode's notes carry, both read from
``engine.corrections``. :func:`build_show_notes_extras` is the single call
run_show makes, right after the Sources line; it returns ``""`` on the
ordinary day, so the description is byte-identical until a correction is
filed.
"""

from __future__ import annotations

from pathlib import Path
from typing import List, Tuple, Union
from urllib.parse import urlparse

from engine.blog import _extract_source_urls
from engine.corrections import corrections_for, corrections_to_carry

#: Domains listed per episode. Enough to show the sourcing; short enough
#: that podcast apps show it without a "more" fold of its own.
MAX_SOURCES = 8

#: The label the line opens with, per feed language.
LABELS = {"en": "Sources", "ru": "Источники", "fr": "Sources"}

_SOCIAL_HOSTS = ("x.com", "twitter.com")


def display_domain(url: str) -> str:
    """``https://www.bbc.com/news/…`` -> ``bbc.com``; empty on a bad URL."""
    try:
        host = (urlparse(url).netloc or "").lower().split(":")[0]
    except Exception:  # noqa: BLE001
        return ""
    if host.startswith("www."):
        host = host[4:]
    return host


def source_pairs(digest_md: str, max_sources: int = MAX_SOURCES) -> List[Tuple[str, str]]:
    """``[(domain, url), …]`` in document order, one per domain, publishers
    before social posts (an x.com source is real but is listed last)."""
    seen: set = set()
    publishers: List[Tuple[str, str]] = []
    social: List[Tuple[str, str]] = []
    for url in _extract_source_urls(digest_md or ""):
        dom = display_domain(url)
        if not dom or dom in seen:
            continue
        seen.add(dom)
        (social if dom in _SOCIAL_HOSTS else publishers).append((dom, url))
    return (publishers + social)[:max_sources]


def sources_footer(digest_md: str, *, language: str = "en",
                   max_sources: int = MAX_SOURCES) -> str:
    """One markdown line, or ``""`` when the digest cites nothing."""
    pairs = source_pairs(digest_md, max_sources=max_sources)
    if not pairs:
        return ""
    label = LABELS.get((language or "en").lower()[:2], LABELS["en"])
    return f"{label}: " + " · ".join(f"[{dom}]({url})" for dom, url in pairs)


# ---------------------------------------------------------------------------
# Corrections in the show notes
# ---------------------------------------------------------------------------

#: The label a correction line opens with, per feed language.
CORRECTION_LABELS = {"en": "Correction", "ru": "Исправление", "fr": "Correction"}
#: "Correction to episode N" — the next-episode line, per feed language.
CARRIED_LABELS = {
    "en": "Correction to episode {n}",
    "ru": "Исправление к выпуску {n}",
    "fr": "Correction de l'épisode {n}",
}


def _label(table: dict, language: str) -> str:
    return table.get((language or "en").lower()[:2], table["en"])


def corrections_footer(show_dir: Union[str, Path], episode: int, *,
                       language: str = "en") -> str:
    """The corrections filed against *episode*, one markdown line each, or
    ``""``. This is what the CORRECTED episode's own description carries."""
    lines = []
    for c in corrections_for(show_dir, episode):
        lines.append(f"**{_label(CORRECTION_LABELS, language)} ({c['date']}):** {c['text']}")
    return "\n".join(lines)


def carried_corrections_footer(show_dir: Union[str, Path], episode: int, *,
                               language: str = "en",
                               episode_date: str = "") -> str:
    """The "Correction to episode N: …" lines the NEXT episode's notes carry
    (``engine.corrections.corrections_to_carry`` decides which), or ``""``."""
    lines = []
    for c in corrections_to_carry(show_dir, episode, episode_date or None):
        head = _label(CARRIED_LABELS, language).format(n=c["episode"])
        lines.append(f"**{head}:** {c['text']}")
    return "\n".join(lines)


def build_show_notes_extras(show_dir: Union[str, Path], episode: int, *,
                            language: str = "en", episode_date: str = "") -> str:
    """Everything the show notes carry beyond the digest and the Sources line.

    Today that is the corrections — those filed against this episode and
    those this episode carries for an earlier one. Returns ``""`` when there
    is nothing, so the ordinary description is unchanged. Never raises.
    """
    try:
        parts = [
            corrections_footer(show_dir, episode, language=language),
            carried_corrections_footer(show_dir, episode, language=language,
                                       episode_date=episode_date),
        ]
    except Exception as exc:  # noqa: BLE001 — the notes ship without it
        import logging
        logging.getLogger(__name__).warning(
            "show-notes extras failed (non-fatal): %s", exc)
        return ""
    return "\n".join(p for p in parts if p)


def append_show_notes_extras(description: str, show_dir: Union[str, Path],
                             episode: int, *, language: str = "en",
                             episode_date: str = "") -> str:
    """*description* with :func:`build_show_notes_extras` appended as its own
    paragraph, or *description* unchanged when there is nothing to add."""
    extras = build_show_notes_extras(show_dir, episode, language=language,
                                     episode_date=episode_date)
    if not extras:
        return description
    return (description or "").rstrip() + "\n\n" + extras
