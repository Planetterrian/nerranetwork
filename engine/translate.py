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
import unicodedata
from pathlib import Path
from typing import Callable, Dict, Optional, Tuple

import yaml
from tenacity import retry, stop_after_attempt, wait_exponential

logger = logging.getLogger(__name__)

# Supported languages: BCP-47 code -> human-readable name for the prompt.
LANGUAGE_NAMES: Dict[str, str] = {
    "fr": "French",
    "ru": "Russian",
    "es": "Spanish",
    "zh": "Simplified Chinese",
}

_TRANSLATION_MODEL = "grok-latest"


class TranslationError(RuntimeError):
    """A translation came back unusable (empty, too short, or untranslated)."""


class TranslationRefusalError(TranslationError):
    """The model refused to translate — must NOT be rendered to audio."""

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


# ---------------------------------------------------------------------------
# Output validation — never let a refusal / wrong-script / echo reach TTS
# ---------------------------------------------------------------------------

def _collapse_ws(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "")).strip()


def _script_ratio(text: str, predicate: Callable[[str], bool]) -> float:
    """Fraction of alphabetic chars in *text* satisfying *predicate* (0 if none)."""
    alpha = [c for c in text if c.isalpha()]
    if not alpha:
        return 0.0
    return sum(1 for c in alpha if predicate(c)) / len(alpha)


def _is_cyrillic(c: str) -> bool:
    return "CYRILLIC" in unicodedata.name(c, "")


def _is_cjk(c: str) -> bool:
    o = ord(c)
    return 0x4E00 <= o <= 0x9FFF or 0x3400 <= o <= 0x4DBF or 0xF900 <= o <= 0xFAFF


# Minimum target-script ratio for languages whose script differs from English.
# Latin-script targets (fr/es) can't be distinguished from an English echo by
# script alone, so they rely on the echo + length-floor checks instead.
_MIN_SCRIPT_RATIO = {"ru": 0.5, "zh": 0.3}
# A translation shorter than this fraction of the source is almost certainly
# truncated or a stub, not a faithful for-the-ear localization.
_MIN_LENGTH_FRACTION = 0.25


def validate_translation(text: str, lang: str, english_script: str = "") -> str:
    """Return *text* if it's a usable translation, else raise.

    Catches the four real failure modes seen with one-shot LLM translation:
    an empty/blank result, a model refusal (which must never be voiced), an
    untranslated English echo, and a wrong-script result (e.g. ZH that came
    back in Latin letters). Cheap, deterministic, no network.
    """
    t = (text or "").strip()
    if not t:
        raise TranslationError(f"{lang}: empty translation")

    head = t[:500]
    from engine.generator import _REFUSAL_PATTERNS
    for pat in _REFUSAL_PATTERNS:
        m = re.search(pat, head, re.MULTILINE)
        if m:
            raise TranslationRefusalError(f"{lang}: model refused — {m.group(0)[:120]!r}")

    en = (english_script or "").strip()
    if en and len(t) < _MIN_LENGTH_FRACTION * len(en):
        raise TranslationError(
            f"{lang}: translation suspiciously short ({len(t)} vs English {len(en)} chars)"
        )
    if en and _collapse_ws(t) == _collapse_ws(en):
        raise TranslationError(f"{lang}: output identical to English (untranslated echo)")

    floor = _MIN_SCRIPT_RATIO.get(lang)
    if floor is not None:
        predicate = _is_cyrillic if lang == "ru" else _is_cjk
        ratio = _script_ratio(t, predicate)
        if ratio < floor:
            raise TranslationError(
                f"{lang}: expected target-script ratio >= {floor}, got {ratio:.2f} "
                "(translation likely came back in the wrong script)"
            )
    return t


@retry(stop=stop_after_attempt(3),
       wait=wait_exponential(multiplier=2, min=4, max=30),
       reraise=True)
def _generate(prompt: str, model: str, max_tokens: int) -> str:
    """Grok text call with transient-error retry (mirrors the rest of the repo).

    Retries only the API call; output validation happens by the caller, so a
    deterministic refusal isn't retried 3× (it returns text, not an exception).
    """
    from digests.xai_grok import grok_generate_text
    text, _meta = grok_generate_text(
        prompt=prompt, model=model, temperature=0.4, max_tokens=max_tokens,
    )
    return (text or "").strip()


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

    prompt = _build_script_prompt(english_script, lang)
    logger.info("Translating script -> %s (%d chars in)", lang, len(english_script))
    text = _generate(prompt, model, max_tokens)
    # Reject refusals / wrong-script / echoes BEFORE they reach TTS.
    text = validate_translation(text, lang, english_script)
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
        raw = _generate(prompt, model, 1200)
        # Tolerate a ```json fence around the object.
        m = re.search(r"\{.*\}", raw, re.DOTALL)
        obj = json.loads(m.group(0) if m else raw)
        t = str(obj.get("title") or title).strip()
        d = str(obj.get("description") or description).strip()
        return t, d
    except Exception as exc:  # noqa: BLE001 — metadata is best-effort
        logger.warning("Metadata translation (%s) failed, using English: %s", lang, exc)
        return title, description
