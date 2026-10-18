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
    _TRACK_LANGS.clear()
    _META_LANGS = None


# ---------------------------------------------------------------------------
# The site's languages (Oct 18 2026)
# ---------------------------------------------------------------------------
#
# The English front page used to carry the two Russian shows and their
# headlines beside the English ones, and the header's globe offered 中文 while
# no show produced a Chinese track. Both came from the same gap: nothing owned
# the list of languages the site is actually published in. This block does.
#
# A language is a SITE language when a show renders its pages in it
# (``page_lang``) or when a show produces a translated audio track in it
# (``multilingual.languages``, with the ZH approval rule). English is always
# first. Each non-English language gets ONE hub page, ``<lang>/index.html``,
# which is where the English chrome and the header's Language menu send a
# reader; the English homepage lists English shows only.

#: Autonyms — what each language calls itself. The header menu, the hubs and
#: the hreflang/sitemap entries all read this; a language missing here still
#: works (its code is its label) but should be added.
LANGUAGE_AUTONYMS: Dict[str, str] = {
    "en": "English",
    "fr": "Français",
    "ru": "Русский",
    "es": "Español",
    "zh": "中文",
}

_TRACK_LANGS: Dict[str, frozenset] = {}


def track_languages(slug: Optional[str]) -> Optional[frozenset]:
    """The translated audio tracks ``shows/<slug>.yaml`` produces today, or
    ``None`` for a registry-only show (no YAML — "do not filter").

    Reads the loaded config (defaults merged) so a show that enables
    ``multilingual`` without listing languages inherits the network list, as
    the pipeline does. A ZH track needs BOTH ``zh`` in ``languages`` and
    ``zh_approved`` (Oct 9 2026: the ZH tracks were switched off on the
    flagships and their frozen feeds kept a 中文 chip alive for six weeks).
    """
    if not slug:
        return None
    slug = str(slug)
    if slug in _TRACK_LANGS:
        return _TRACK_LANGS[slug]
    path = SHOWS_DIR / f"{slug}.yaml"
    if not path.is_file():
        return None
    try:
        from engine.config import load_config
        cfg = load_config(path)
    except Exception:  # noqa: BLE001 — a bad YAML produces no tracks
        langs: frozenset = frozenset()
    else:
        langs = track_languages_from_config(cfg)
    _TRACK_LANGS[slug] = langs
    return langs


def track_languages_from_config(cfg) -> frozenset:
    """The rule itself, on a loaded ``ShowConfig`` (or anything with a
    ``multilingual`` attribute): enabled tracks, ZH only when approved."""
    ml = getattr(cfg, "multilingual", None)
    if ml is None or not getattr(ml, "enabled", False):
        return frozenset()
    codes = {str(c).strip().lower()
             for c in (getattr(ml, "languages", None) or []) if c}
    if not getattr(ml, "zh_approved", False):
        codes.discard("zh")
    return frozenset(codes)


def site_languages(slugs) -> list:
    """Every language the site is published in, ``en`` first, then sorted.

    *slugs* is the registry's show list. A language counts when a show's
    pages render in it or a show produces an audio track in it — so ``es``
    and ``zh`` drop out by themselves while no show produces them, and a
    show switching a track on adds its language with no code change.
    """
    langs = {DEFAULT_LANG}
    for slug in slugs:
        langs.add(page_lang(slug))
        langs.update(track_languages(slug) or ())
    return sorted(langs, key=lambda c: (c != DEFAULT_LANG, c))


def language_hub_path(lang: str) -> str:
    """Site-relative path of a language's hub page: ``""`` for English (the
    homepage), ``"<lang>/index.html"`` otherwise.

    ``ru/index.html`` is the committed RU root that every EN↔RU hreflang
    pair already names, so the pattern follows it rather than the directory
    form ``/ru/`` (Google ignores an hreflang pair whose href is not the
    page's canonical).
    """
    lang = (lang or DEFAULT_LANG).strip().lower()
    return "" if lang == DEFAULT_LANG else f"{lang}/index.html"


def language_autonym(lang: str) -> str:
    lang = (lang or "").strip().lower()
    return LANGUAGE_AUTONYMS.get(lang, lang)
