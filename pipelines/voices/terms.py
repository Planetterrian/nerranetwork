"""Names and terms the speech recogniser gets wrong, put right in the transcript.

Oct 27 2026, Glenn Broder. The transcript he was asked to approve had his own
framework as "cognitive jungle gem", the operating rule he learned as a child
as "Tell Moodic logic", Jensen Huang as "Jensen Wang", "the anecdote for the
problems" where he said antidote, "our matrix" for our metrics, and OpenAI as
"open AI". The cleaning pass is told to fix certain mishearings, but it
rewrites the whole transcript in one reply and gave back Glenn's with five
characters changed; nothing checks what it did or did not do.

So the corrections are made here, as a list of exact replacements that can be
checked one by one:

* ``KNOWN_MISHEARS`` — renderings that are never right (the network's own
  name, the industry's proper nouns the recogniser keeps splitting);
* :func:`glossary_from_app` — the guest's own titles, products and
  organisation from their application, put back in their own capitals
  ("human judgment in the age of AI" -> "Human Judgment in the Age of AI");
* :func:`model_fixes` — one model pass that LISTS mishearings (heard ->
  meant) instead of rewriting the transcript. Every entry must be found
  verbatim, be a few words long, and sound like what it replaces, or it is
  thrown away. The model never touches anything else.

Speaker labels and timestamps are never inside a replacement, so the
transcript keeps its shape for everything downstream (the edit transcript,
the thank-you quotes, the notes).
"""
from __future__ import annotations

import difflib
import json
import logging
import re
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger("nerra.voices.terms")

# (pattern, replacement): renderings that are never what anyone said.
KNOWN_MISHEARS: List[Tuple[str, str]] = [
    (r"\b(?:NARA|Nara|Narra|Nera|Nero)(?=\s+(?:Network|Voices)\b)", "Nerra"),
    (r"\b(?:NARA|Nara|Narra|Nera)\s*Network\.com\b", "nerranetwork.com"),
    (r"\bopen\s?AI\b", "OpenAI"),
    (r"\bOpen\s+AI\b", "OpenAI"),
    (r"\bchat\s?GPT\b", "ChatGPT"),
    (r"\bChat\s+GPT\b", "ChatGPT"),
    (r"\bJensen\s+(?:Wang|Hwang|Huong)\b", "Jensen Huang"),
    (r"\bSam\s+Altmann\b", "Sam Altman"),
    (r"\bAnthropics?\s+Claude\b", "Anthropic's Claude"),
    (r"\bjungle\s+gem\b", "jungle gym"),
    (r"\b(?i:tell[- ]?m(?:oo|u)dic)\b", "Talmudic"),
]

# Words that stay lower case inside a title ("Learn AI Like a Pro").
_SMALL = {"a", "an", "and", "as", "at", "by", "for", "in", "of", "on", "or",
          "the", "to", "with", "like", "from", "into", "vs"}
_TITLE_RUN = re.compile(r"(?:[A-Z][\w'&-]*|AI)(?:\s+(?:[A-Z][\w'&-]*|AI|"
                        + "|".join(sorted(_SMALL)) + r")){1,10}")


def glossary_from_app(app: Optional[Dict[str, Any]]) -> List[str]:
    """The guest's own capitalised names: products, frameworks, books,
    organisation and title phrases from the application, longest first."""
    app = app or {}
    found: List[str] = []
    for field in ("organization", "title", "bio", "name"):
        text = str(app.get(field) or "")
        for m in _TITLE_RUN.finditer(text):
            phrase = m.group(0).strip()
            # Trim small words off the ends ("of AI and" -> "of AI").
            words = phrase.split()
            while words and words[-1].lower() in _SMALL:
                words.pop()
            while words and words[0].lower() in _SMALL:
                words.pop(0)
            if len(words) < 2:
                continue
            caps = sum(1 for w in words if w[:1].isupper())
            if caps < 2:
                continue
            phrase = " ".join(words)
            if phrase not in found:
                found.append(phrase)
    return sorted(found, key=len, reverse=True)


_LINE = re.compile(r"^(\[[\d:]+\]\s*[^:]+:\s*)(.*)$")


def _map_text(transcript: str, fn) -> str:
    """Apply ``fn`` to the spoken text of every line, never to the stamp or
    the speaker label."""
    out = []
    for line in (transcript or "").splitlines():
        m = _LINE.match(line)
        if m:
            out.append(m.group(1) + fn(m.group(2)))
        else:
            out.append(line)
    tail = "\n" if (transcript or "").endswith("\n") else ""
    return "\n".join(out) + tail


def known_fixes(transcript: str, glossary: Optional[List[str]] = None) -> Tuple[str, List[str]]:
    """The fixed list and the guest's own names. Returns (text, changes)."""
    changes: List[str] = []

    def fix(text: str) -> str:
        for pat, rep in KNOWN_MISHEARS:
            new = re.sub(pat, rep, text)
            if new != text:
                changes.append(f"{pat} -> {rep}")
                text = new
        for phrase in glossary or []:
            pat = re.compile(r"\b" + r"\s+".join(map(re.escape, phrase.split())) + r"\b", re.I)

            def canon(m, phrase=phrase):
                if m.group(0) != phrase:
                    changes.append(f"{m.group(0)} -> {phrase}")
                return phrase
            text = pat.sub(canon, text)
        return text
    return _map_text(transcript, fix), changes


MAX_FIXES = 60
MAX_WORDS = 6
MIN_SOUND_ALIKE = 0.34


def _letters(s: str) -> str:
    return re.sub(r"[^a-z]", "", s.lower())


def vet_fixes(transcript: str, proposed: Any) -> List[Tuple[str, str]]:
    """The model's proposals that can be applied safely: found verbatim in a
    line's text, short, actually different, and sounding like what they
    replace (a mishearing, not a rewrite)."""
    if not isinstance(proposed, list):
        return []
    spoken = "\n".join(m.group(2) for m in map(_LINE.match, (transcript or "").splitlines()) if m)
    kept: List[Tuple[str, str]] = []
    for item in proposed[:MAX_FIXES * 2]:
        if not isinstance(item, dict):
            continue
        heard = " ".join(str(item.get("heard") or "").split())
        meant = " ".join(str(item.get("meant") or "").split())
        if not heard or not meant or heard == meant:
            continue
        if len(heard.split()) > MAX_WORDS or len(meant.split()) > MAX_WORDS + 1:
            continue
        if heard not in spoken:
            continue
        if difflib.SequenceMatcher(None, _letters(heard), _letters(meant)).ratio() < MIN_SOUND_ALIKE:
            continue
        if any(heard == h for h, _ in kept):
            continue
        kept.append((heard, meant))
        if len(kept) >= MAX_FIXES:
            break
    return kept


def apply_fixes(transcript: str, fixes: List[Tuple[str, str]]) -> str:
    def fix(text: str) -> str:
        for heard, meant in fixes:
            text = re.sub(r"(?<![\w'])" + re.escape(heard) + r"(?![\w'])", meant, text)
        return text
    return _map_text(transcript, fix)


def model_fixes(transcript: str, app: Dict[str, Any], show=None) -> List[Tuple[str, str]]:
    """One model pass that lists mishearings; vetted before use."""
    from common import llm, load_prompt, parse_json_lenient
    prompt = load_prompt("transcript_mishears.txt", show=show,
                         guest_name=(app or {}).get("name", ""),
                         guest_title=(app or {}).get("title", ""),
                         guest_organization=(app or {}).get("organization", ""),
                         guest_bio=(app or {}).get("bio", ""),
                         transcript=transcript)
    text = llm(prompt, temperature=0.1, max_tokens=4000)
    try:
        proposed = parse_json_lenient(text)
    except Exception:  # noqa: BLE001
        logger.warning("mishearing pass: unreadable reply; none applied")
        return []
    if isinstance(proposed, dict):
        proposed = proposed.get("fixes") or []
    return vet_fixes(transcript, proposed)


def correct_transcript(transcript: str, app: Optional[Dict[str, Any]] = None, show=None,
                       use_model: bool = True) -> Tuple[str, List[str]]:
    """Known mishearings, the guest's own names, then the vetted model list.
    Returns (text, a line per change for the log). Never raises."""
    changes: List[str] = []
    try:
        transcript, changes = known_fixes(transcript, glossary_from_app(app))
    except Exception:  # noqa: BLE001
        logger.exception("known term fixes failed (non-fatal)")
    if use_model:
        try:
            fixes = model_fixes(transcript, app or {}, show)
            if fixes:
                transcript = apply_fixes(transcript, fixes)
                changes += [f"{h} -> {m}" for h, m in fixes]
        except Exception:  # noqa: BLE001
            logger.exception("mishearing pass failed (non-fatal)")
    if changes:
        logger.info("transcript terms corrected: %s", json.dumps(changes)[:2000])
    return transcript, changes
