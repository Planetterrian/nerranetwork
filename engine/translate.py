"""Spoken-delivery translation stage for the multilingual audio pipeline.

Takes a finalized English episode script (and its title/description) and
produces natural, for-the-ear translations via Grok (``grok-latest``), one
call per language. The English script stays the canonical master; these are
derived artifacts that feed the per-language TTS render.

Design notes
------------
- Model id is ``grok-latest`` per the network multilingual convention
  (never a version-pinned string). This is scoped to the translation calls
  only — it does NOT touch the English generation pipeline's ``grok-4.3``.
- Proper nouns / tickers are preserved; a per-language phonetic overrides
  map (``shows/translation_overrides.yaml``) is injected into the prompt as
  guidance AND applied as a post-process safety net (mirrors
  ``engine.utils.fix_phonetic_garbles`` but language-scoped — it never
  touches the English path).
- Prompt placeholders are substituted via ``str.replace`` (not
  ``str.format``) so script content containing literal ``{`` / ``}`` can't
  break substitution.
"""

from __future__ import annotations

import json
import logging
import re
from pathlib import Path
from typing import Dict, Optional, Tuple

import yaml

logger = logging.getLogger(__name__)

# Supported languages: BCP-47 code -> human-readable name for the prompt.
LANGUAGE_NAMES: Dict[str, str] = {
    "fr": "French",
    "ru": "Russian",
    "es": "Spanish",
    "zh": "Simplified Chinese",
}

_TRANSLATION_MODEL = "grok-latest"

_REPO_ROOT = Path(__file__).resolve().parent.parent
_OVERRIDES_PATH = _REPO_ROOT / "shows" / "translation_overrides.yaml"
_PROMPT_PATH = _REPO_ROOT / "shows" / "prompts" / "_shared" / "translation.txt"

_OVERRIDES_CACHE: Optional[Dict[str, Dict[str, str]]] = None


def supported_languages() -> Tuple[str, ...]:
    """Return the BCP-47 codes this stage knows how to localize."""
    return tuple(LANGUAGE_NAMES.keys())


def language_name(lang: str) -> str:
    """Human-readable name for a BCP-47 code (falls back to the code)."""
    return LANGUAGE_NAMES.get(lang, lang)


def _load_overrides() -> Dict[str, Dict[str, str]]:
    """Load the term -> {lang: spelling} overrides map (cached)."""
    global _OVERRIDES_CACHE
    if _OVERRIDES_CACHE is not None:
        return _OVERRIDES_CACHE
    data: Dict[str, Dict[str, str]] = {}
    try:
        raw = yaml.safe_load(_OVERRIDES_PATH.read_text(encoding="utf-8")) or {}
        data = raw.get("overrides", {}) or {}
    except FileNotFoundError:
        logger.info("No translation_overrides.yaml — proceeding with no overrides")
    except Exception as exc:  # noqa: BLE001 — bad YAML shouldn't crash a run
        logger.warning("Failed to load translation overrides: %s", exc)
    _OVERRIDES_CACHE = data
    return data


def overrides_for_language(lang: str) -> Dict[str, str]:
    """Return ``{term: spelling}`` for *lang* (terms with an entry only)."""
    out: Dict[str, str] = {}
    for term, per_lang in _load_overrides().items():
        if isinstance(per_lang, dict) and per_lang.get(lang):
            out[str(term)] = str(per_lang[lang])
    return out


def _format_overrides_block(lang: str) -> str:
    items = overrides_for_language(lang)
    if not items:
        return "(none)"
    return "\n".join(f"- {term} => {spelling}" for term, spelling in items.items())


def apply_overrides(text: str, lang: str) -> str:
    """Post-process: enforce per-language phonetic spellings in *text*.

    Belt-and-suspenders over the prompt instruction. Word-boundary,
    case-insensitive — only rewrites whole-word matches of the English term.
    """
    if not text:
        return text
    items = overrides_for_language(lang)
    for term, spelling in items.items():
        pattern = r"\b" + re.escape(term) + r"\b"
        text = re.sub(pattern, spelling, text)
    return text


def _build_script_prompt(english_script: str, lang: str) -> str:
    template = _PROMPT_PATH.read_text(encoding="utf-8")
    return (
        template
        .replace("{language_name}", language_name(lang))
        .replace("{bcp47}", lang)
        .replace("{phonetic_overrides}", _format_overrides_block(lang))
        .replace("{english_script}", english_script)
    )


def translate_script(
    english_script: str,
    lang: str,
    *,
    model: str = _TRANSLATION_MODEL,
    max_tokens: int = 16000,
) -> str:
    """Localize a full English episode script into *lang* for spoken delivery.

    Returns the translated script (overrides enforced). Raises if *lang* is
    unsupported or the script is empty.
    """
    if lang not in LANGUAGE_NAMES:
        raise ValueError(f"Unsupported language {lang!r}; supported: {supported_languages()}")
    if not (english_script or "").strip():
        raise ValueError("translate_script: empty english_script")

    from digests.xai_grok import grok_generate_text

    prompt = _build_script_prompt(english_script, lang)
    logger.info("Translating script -> %s (%d chars in)", lang, len(english_script))
    text, _meta = grok_generate_text(
        prompt=prompt,
        model=model,
        temperature=0.4,
        max_tokens=max_tokens,
    )
    text = (text or "").strip()
    if not text:
        raise RuntimeError(f"Empty translation returned for {lang}")
    return apply_overrides(text, lang)


def translate_metadata(
    title: str,
    description: str,
    lang: str,
    *,
    model: str = _TRANSLATION_MODEL,
) -> Tuple[str, str]:
    """Translate an episode title + description into *lang*.

    Same spoken/natural register as the script, tuned for the site + search
    reach. Returns ``(title, description)``; on any parse failure falls back
    to the English inputs so the caller always gets usable strings.
    """
    if lang not in LANGUAGE_NAMES:
        raise ValueError(f"Unsupported language {lang!r}")
    title = (title or "").strip()
    description = (description or "").strip()
    if not title and not description:
        return title, description

    from digests.xai_grok import grok_generate_text

    name = language_name(lang)
    prompt = (
        f"Translate this podcast episode title and description into {name} "
        f"(BCP-47 {lang}). Natural and idiomatic for a listing/search page; "
        "keep proper nouns, brand names and tickers (Tesla, SpaceX, TSLA…) "
        "intact. Return ONLY a JSON object with keys \"title\" and "
        "\"description\", no other text.\n\n"
        f"TITLE: {title}\n"
        f"DESCRIPTION: {description}\n"
    )
    try:
        raw, _meta = grok_generate_text(
            prompt=prompt, model=model, temperature=0.4, max_tokens=1200,
        )
        raw = (raw or "").strip()
        # Tolerate a ```json fence around the object.
        m = re.search(r"\{.*\}", raw, re.DOTALL)
        obj = json.loads(m.group(0) if m else raw)
        t = str(obj.get("title") or title).strip()
        d = str(obj.get("description") or description).strip()
        return t, d
    except Exception as exc:  # noqa: BLE001 — metadata is best-effort
        logger.warning("Metadata translation (%s) failed, using English: %s", lang, exc)
        return title, description
