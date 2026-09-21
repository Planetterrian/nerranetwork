"""One owner for a show's page language.

Before this module the Russian-show set was a literal tuple repeated SEVEN
times: three in ``generate_html.py`` (the summaries page, the show page, and
the network language count) and four in ``engine/blog.py`` (the JSON-LD
``inLanguage``, the ``_is_ru`` template flag, the next-episode placeholder and
``page_lang``). Two consequences, both of the shape this repo keeps paying for:
a registry-only show **could not be Russian at all**, because every copy tested
a hardcoded pair of slugs; and adding a language meant finding all seven copies,
where missing one renders a page in the wrong language and nothing fails.

The language is DERIVED, never duplicated. ``shows/<slug>.yaml`` already carries
``tts.language_code`` — ``ru`` on the two Russian shows, ``en`` inherited from
``shows/_defaults.yaml`` everywhere else — and it is a field the operator
already maintains, so this reads that rather than inventing a second source of
truth. This is the same pattern as ``generate_html._newsletter_tag_for_slug``,
which reads ``newsletter.tag`` out of the same file.

A registry-only show (Nerra Daily) has no show YAML at all, so it may name
``page_lang`` in ``shows/network_meta.yaml``. That key is checked FIRST and is
what lets a future scaffolded show ship in another language without editing
Python. Nothing sets it today, which is why introducing it changed no output.

Verified behaviour-preserving when introduced (2026-09-21): across all 18
registered shows this returns ``ru`` for exactly ``finansy_prosto`` and
``privet_russian`` — the two slugs the seven tuples named.
"""

from __future__ import annotations

from pathlib import Path
from typing import Dict, Optional

ROOT = Path(__file__).resolve().parent.parent
SHOWS_DIR = ROOT / "shows"

#: The language every surface falls back to. A show with no YAML, an
#: unparseable YAML, or no language field is English — which is what the
#: seven hardcoded tuples did for every slug outside the Russian pair.
DEFAULT_LANG = "en"

#: Process-local memo keyed on the slug. ``page_lang`` is called once per blog
#: post (~1,880 on a full regen) plus once per show page, and each miss opens
#: and parses a YAML file, so without this a regen would re-read the same
#: handful of files thousands of times.
_LANG_BY_SLUG: Dict[str, str] = {}

#: Memo for the registry overrides, read once from network_meta.yaml.
_META_LANGS: Optional[Dict[str, str]] = None


def _load_yaml(path: Path) -> dict:
    """Parse a YAML file, or return ``{}`` — a language lookup is never worth
    a crash on a malformed file, and the caller's fallback is English."""
    if not path.exists():
        return {}
    try:
        import yaml
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001 — unreadable YAML means "use the default"
        return {}
    return data if isinstance(data, dict) else {}


def _meta_langs() -> Dict[str, str]:
    """``{slug: lang}`` for shows that declare ``page_lang`` in the registry.

    Only registry-only shows need this: a show with its own YAML gets its
    language from ``tts.language_code`` below.
    """
    global _META_LANGS
    if _META_LANGS is None:
        out: Dict[str, str] = {}
        for slug, meta in _load_yaml(SHOWS_DIR / "network_meta.yaml").items():
            if not isinstance(meta, dict):
                continue
            lang = str(meta.get("page_lang") or "").strip().lower()
            if lang:
                out[str(slug)] = lang
        _META_LANGS = out
    return _META_LANGS


def page_lang(slug: Optional[str]) -> str:
    """The language this show's pages render in (an HTML ``lang`` value).

    Resolution order: an explicit ``page_lang`` in ``shows/network_meta.yaml``,
    then ``tts.language_code`` in ``shows/<slug>.yaml``, then English.
    """
    if not slug:
        return DEFAULT_LANG
    slug = str(slug)
    cached = _LANG_BY_SLUG.get(slug)
    if cached is not None:
        return cached

    lang = _meta_langs().get(slug, "")
    if not lang:
        tts = _load_yaml(SHOWS_DIR / f"{slug}.yaml").get("tts")
        if isinstance(tts, dict):
            lang = str(tts.get("language_code") or "").strip().lower()

    lang = lang or DEFAULT_LANG
    _LANG_BY_SLUG[slug] = lang
    return lang


def is_russian(slug: Optional[str]) -> bool:
    """True when this show's pages render in Russian.

    The seven replaced call sites all asked exactly this question, so they call
    this rather than comparing ``page_lang`` themselves.
    """
    return page_lang(slug) == "ru"


def _reset_cache() -> None:
    """Drop the memos. Tests that write a temporary show YAML need this;
    production resolves each slug once per process."""
    global _META_LANGS
    _LANG_BY_SLUG.clear()
    _META_LANGS = None
