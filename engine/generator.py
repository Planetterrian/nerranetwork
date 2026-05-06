"""LLM interaction module for podcast digest and script generation.

Loads prompt templates from files, fills in template variables, and calls the
xAI/Grok API.  All shows use the OpenAI-compatible endpoint unless tools
(web search / X search) are explicitly requested.
"""

from __future__ import annotations

import logging
import os
import re
from pathlib import Path
from typing import Any, Dict, Optional

from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

# Only retry on transient API errors — permanent errors (KeyError, FileNotFoundError,
# RuntimeError) will fail immediately instead of wasting 3x API credits.
try:
    from openai import APITimeoutError, APIConnectionError, RateLimitError
    _TRANSIENT_ERRORS = (APITimeoutError, APIConnectionError, RateLimitError)
except ImportError:
    # Fallback if openai isn't installed (e.g. in tests)
    _TRANSIENT_ERRORS = (TimeoutError, ConnectionError)

logger = logging.getLogger(__name__)


class LLMRefusalError(RuntimeError):
    """Raised when the LLM refuses to generate content.

    Unlike quality warnings (short text, repetition), a refusal means the LLM
    explicitly declined to produce content.  Continuing the pipeline would waste
    TTS credits synthesising the refusal message into audio.
    """


# Fallback model used when the primary model refuses to generate content
# after educational prompt retry.  A different model often has different
# refusal thresholds and can succeed where the primary model won't.
# Kept for back-compat and for call sites that don't have a config loaded;
# prefer ``config.llm.fallback_model`` where possible. Points at the older
# grok-4.20-reasoning so a refusal switches model family/snapshot rather
# than re-asking the same primary (grok-4.3).
_LLM_FALLBACK_MODEL = "grok-4.20-reasoning"


def _resolve_fallback_model(config) -> str:
    """Return the configured refusal-fallback model, falling back to the module default."""
    return getattr(getattr(config, "llm", None), "fallback_model", "") or _LLM_FALLBACK_MODEL


# ---------------------------------------------------------------------------
# Prompt template loading
# ---------------------------------------------------------------------------

def load_prompt(prompt_file: str, template_vars: Optional[Dict[str, Any]] = None) -> str:
    """Read a prompt template file and fill in ``{placeholder}`` variables.

    Parameters
    ----------
    prompt_file:
        Path to a ``.txt`` file containing the prompt template.  May be
        relative (resolved from cwd) or absolute.
    template_vars:
        Dict of values to substitute into ``{key}`` placeholders.  Uses
        ``str.format_map`` so missing keys raise ``KeyError``.  Pass
        ``None`` to skip substitution (useful for reference-only files).
    """
    path = Path(prompt_file)
    if not path.exists():
        raise FileNotFoundError(f"Prompt file not found: {path}")
    raw = path.read_text(encoding="utf-8")
    if template_vars is not None:
        return raw.format_map(template_vars)
    return raw


# ---------------------------------------------------------------------------
# xAI / Grok API call
# ---------------------------------------------------------------------------

def _get_api_key() -> str:
    return (os.getenv("GROK_API_KEY") or os.getenv("XAI_API_KEY") or "").strip()


def _call_grok(
    prompt: str,
    *,
    model: str = "grok-4.3",
    system_prompt: Optional[str] = None,
    temperature: float = 0.7,
    max_tokens: int = 3500,
    timeout: float = 300.0,
) -> tuple[str, Dict[str, Any]]:
    """Call xAI Grok via the OpenAI-compatible endpoint.

    Returns ``(text, meta)`` where *meta* contains usage info.
    """
    from openai import OpenAI

    api_key = _get_api_key()
    if not api_key:
        raise RuntimeError("Missing GROK_API_KEY (or XAI_API_KEY).")

    client = OpenAI(api_key=api_key, base_url="https://api.x.ai/v1", timeout=timeout)

    messages: list[dict] = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": prompt})

    resp = client.chat.completions.create(
        model=model,
        messages=messages,
        temperature=temperature,
        max_tokens=max_tokens,
    )

    text = resp.choices[0].message.content.strip()
    meta: Dict[str, Any] = {"provider": "openai_compat", "model": model}
    finish_reason = getattr(resp.choices[0], "finish_reason", None)
    meta["finish_reason"] = finish_reason
    if finish_reason == "length":
        logger.warning(
            "LLM response truncated (finish_reason=length, max_tokens=%d) — "
            "output may end mid-sentence",
            max_tokens,
        )
    if hasattr(resp, "usage") and resp.usage:
        meta["usage"] = {
            "prompt_tokens": resp.usage.prompt_tokens,
            "completion_tokens": resp.usage.completion_tokens,
            "total_tokens": resp.usage.total_tokens,
        }
    return text, meta


# ---------------------------------------------------------------------------
# Output validation
# ---------------------------------------------------------------------------

# Patterns that suggest leaked prompt instructions in the output
_INSTRUCTION_LEAK_PATTERNS = [
    r"(?i)^(RULES|NEVER INCLUDE|CONTENT FOCUS|TONE|SCRIPT STRUCTURE)\s*:",
    r"(?i)\{[a-z_]+\}",  # Unfilled template placeholders
    r"(?i)^(Use this exact|Deliver this hook|Narrate EVERY|Here is today)",
    r"(?i)^As an AI",
    r"(?i)^I('m| am) (an AI|a language model|ChatGPT|GPT|Claude)",
]

_MIN_CHARS = {"digest": 200, "podcast_script": 500}

# Patterns that indicate the LLM refused to generate content.
# A refusal is NOT imperfect content — it is explicitly NOT content.
# Continuing would waste TTS credits on garbage audio.
# Apostrophe character class: matches straight (') and curly/smart (\u2019) quotes
_APOS = "['\u2019]"

_REFUSAL_PATTERNS = [
    # English — common LLM refusal phrasings
    f"(?i)\\bI(?:\\s+|{_APOS})(?:cannot|can{_APOS}t|am unable to|m unable to)\\s+(?:create|generate|produce|write)\\s+(?:this|the|an?)\\s+(?:episode|podcast|digest|script|content|briefing|edition|output|segment|show|issue|material)",
    # Catch-all: "I can't produce this" regardless of following noun
    f"(?i)\\bI(?:\\s+|{_APOS})(?:cannot|can{_APOS}t)\\s+(?:create|generate|produce|write)\\s+this\\b",
    f"(?i)\\bI(?:\\s+|{_APOS})(?:apologize|m sorry),?\\s+but\\s+I(?:\\s+|{_APOS})(?:cannot|can{_APOS}t|am unable)",
    f"(?i)\\bI(?:\\s+|{_APOS})(?:cannot|can{_APOS}t)\\s+(?:fulfill|complete|comply with)\\s+(?:this|your)\\s+request",
    # "I must decline" / "I need to decline" — from MIT Ep002 refusal (2026-03-19)
    r"(?i)\bI\s+(?:must|need to)\s+decline\b",
    # "it is impossible to produce" — from MIT Ep002 refusal (2026-03-19)
    r"(?i)\bit\s+is\s+impossible\s+to\s+produce",
    # "I cannot generate today's" — trailing show name variant
    r"(?i)\bI\s+cannot\s+generate\s+today",
    # "Therefore, I cannot" — conclusion-style refusal
    f"(?i)\\btherefore,?\\s+I\\s+(?:cannot|can{_APOS}t)\\b",
    # Russian — from actual Finansy Prosto ep008/ep009 refusals (2026-03-18)
    r"Я\s+не\s+могу\s+(?:создать|подготовить|написать|сгенерировать)",
    r"не\s+предоставляю\s+контент",
    r"Хочешь,?\s+я\s+(?:подожду|покажу)",
    r"(?:пришли|пришлите)\s+(?:их|новый\s+список|другой\s+список|реальные)",
]


# -------------------------------------------------------------------
# Story-level duplication detection
# -------------------------------------------------------------------

# Common English words that carry no story-specific signal
_STOPWORDS = frozenset(
    "the a an and or but in on of to for is it its that this with from by at "
    "as be are was were has have had do does did will would could should can "
    "not no nor so if then than too also just about more most very much how "
    "what when where which who whom whose why all each every some any many "
    "few both other another such only own same into over after before between "
    "through during without because until while these those their them they "
    "you your we our he she his her him one been being get got may might "
    "still even now here there up out off down back well really right going "
    "think know see like make take come go say says said new first last "
    "today according".split()
)


def _detect_story_duplication(text: str, show_name: str) -> int:
    """Detect when the same news story is told more than once in a script.

    Splits the script into story-sized blocks (groups of consecutive
    non-blank lines), extracts *story-signal* words — proper nouns,
    source names, and location-like terms — from each block, and flags
    pairs with high overlap indicating the same story is being retold.

    Returns the number of duplicated story pairs found (added to the
    suspicious-repetition count).
    """
    # Split into blocks of consecutive non-blank lines (roughly story-sized)
    blocks: list[list[str]] = []
    current: list[str] = []
    for line in text.split("\n"):
        stripped = line.strip()
        # Remove "Patrick:" or similar host prefixes for analysis
        stripped = re.sub(r"^\w+:\s*", "", stripped)
        if stripped:
            current.append(stripped)
        elif current:
            blocks.append(current)
            current = []
    if current:
        blocks.append(current)

    # Merge very short blocks (< 3 lines) with the next block — these are
    # usually transitions, not standalone stories
    merged: list[str] = []
    buf: list[str] = []
    for block in blocks:
        buf.extend(block)
        if len(buf) >= 3:
            merged.append(" ".join(buf))
            buf = []
    if buf:
        if merged:
            merged[-1] += " " + " ".join(buf)
        else:
            merged.append(" ".join(buf))

    if len(merged) < 3:
        return 0  # Too few blocks to have meaningful duplication

    # Extract story-signal words: proper nouns, source names, locations,
    # and CamelCase terms.  These carry much stronger signal for story
    # identity than common vocabulary.
    _GENERIC_CAPS = frozenset(
        "The This That These Those What When Where Which Who How Why "
        "And But For Not Now Also Then Here There Just Still Even "
        "According From Some Every Each Most Many They Their Its "
        # Show topics and host names — too common to be story-specific
        "Patrick Tesla Model Three Drive Semi Auto Podcast "
        # Language names — too common in bilingual/learning shows
        "Russian English French Spanish German Chinese Japanese "
        "Indo European Latin Greek Arabic "
        # Language learning host names
        "Olya".split()
    )

    def _story_signals(block_text: str) -> set:
        signals: set[str] = set()
        # Multi-word proper noun phrases (e.g. "Northern Virginia") — strongest signal
        phrase_words: set[str] = set()  # Track words consumed by phrases
        for m in re.finditer(r"[A-Z][a-z]{2,}(?:\s+[A-Z][a-z]{2,})+", block_text):
            # Strip generic words from edges (e.g. "That Northern Virginia" → "Northern Virginia")
            words_in_phrase = [w for w in m.group().split() if w not in _GENERIC_CAPS]
            if len(words_in_phrase) < 2:
                continue
            phrase = " ".join(words_in_phrase)
            signals.add(phrase.lower())
            for w in words_in_phrase:
                phrase_words.add(w.lower())
        # CamelCase source names (e.g. "WhatsUpTesla", "Teslarati")
        for m in re.finditer(r"\b[A-Z][a-z]+(?:[A-Z][a-z]+)+\b", block_text):
            signals.add(m.group().lower())
        # Individual proper nouns not at sentence start — only if not
        # already consumed by a multi-word phrase above
        for m in re.finditer(r"(?<=[a-z] )([A-Z][a-z]{3,})\b", block_text):
            w = m.group()
            if w not in _GENERIC_CAPS and w.lower() not in phrase_words:
                signals.add(w.lower())
        return signals

    block_signals = [_story_signals(b) for b in merged]

    # Skip intro (first block) and outro (last block) — these mention
    # the show name and common phrases that false-positive with stories
    start_idx = 1
    end_idx = len(block_signals) - 1

    # Compare non-adjacent blocks (skip immediate neighbors — adjacent
    # blocks may naturally share a transition sentence)
    dup_count = 0
    seen_pairs: set[tuple[int, int]] = set()
    for i in range(start_idx, end_idx):
        for j in range(i + 2, end_idx):
            if (i, j) in seen_pairs:
                continue
            si, sj = block_signals[i], block_signals[j]
            if len(si) < 2 or len(sj) < 2:
                continue  # Block too small to judge
            overlap = si & sj
            smaller = min(len(si), len(sj))
            ratio = len(overlap) / smaller
            # Two thresholds:
            # - 2+ shared signals at 100% overlap (e.g. "Northern Virginia" + "WhatsUpTesla")
            # - 3+ shared signals at >= 75% overlap (broader match)
            is_dup = (len(overlap) >= 2 and ratio >= 1.0) or (len(overlap) >= 3 and ratio >= 0.75)
            if is_dup:
                seen_pairs.add((i, j))
                sample = sorted(overlap)[:10]
                logger.warning(
                    "Story duplication in podcast script for '%s': "
                    "blocks %d and %d share %d/%d proper-noun signals (%.0f%%) — "
                    "likely the same story retold. Shared: %s",
                    show_name, i + 1, j + 1, len(overlap), smaller,
                    ratio * 100, ", ".join(sample),
                )
                dup_count += 1

    # Cap at 2 — story-level duplication is a softer signal than
    # bigram-level hallucination.  The prompt-level anti-repetition
    # instruction is the primary fix; this detector is a safety net.
    return min(dup_count, 3)


def _validate_llm_output(
    text: str,
    stage: str = "digest",
    show_name: str = "unknown",
    min_podcast_words: int = 0,
) -> int:
    """Validate LLM output quality.

    Logs warnings for quality issues (short text, repetition, leaked
    instructions) so the pipeline can still proceed.  However, raises
    ``LLMRefusalError`` for outright refusals — a refusal is worse than
    no episode because it wastes TTS credits on garbage audio.

    Returns the count of distinct suspicious repetition phrases found
    (bigrams appearing 4+ times).  Callers can use this to decide
    whether to retry with a lower temperature.
    """
    import re

    if not text or not text.strip():
        logger.error(
            "LLM returned EMPTY %s for '%s' — episode will likely be unusable",
            stage, show_name,
        )
        return 0

    # Check for LLM refusals — must come before length checks because
    # refusal messages can be 500-2000 chars (passing min-length thresholds).
    #
    # To avoid false positives (e.g. "I must decline to comment" in podcast
    # narration), only scan the first 500 chars when the output is long enough
    # to be real content (>= 2000 chars).  A genuine refusal is a short
    # message, not a 4000-char podcast script with a stray phrase.
    _REFUSAL_SCAN_LIMIT = 500   # chars from start to scan for refusal phrases
    _REAL_CONTENT_THRESHOLD = 2000  # output above this is likely real content
    refusal_search_text = (
        text[:_REFUSAL_SCAN_LIMIT]
        if len(text.strip()) >= _REAL_CONTENT_THRESHOLD
        else text
    )
    for pattern in _REFUSAL_PATTERNS:
        match = re.search(pattern, refusal_search_text, re.MULTILINE)
        if match:
            logger.error(
                "LLM REFUSED to generate %s for '%s' — matched refusal pattern: %s "
                "(matched text: '%s'). Halting pipeline to prevent TTS credit waste.",
                stage, show_name, pattern, match.group(0)[:100],
            )
            raise LLMRefusalError(
                f"LLM refused to generate {stage} for '{show_name}': "
                f"'{match.group(0)[:200]}'"
            )

    char_count = len(text.strip())
    min_chars = _MIN_CHARS.get(stage, 200)
    if char_count < min_chars:
        logger.warning(
            "LLM %s for '%s' is suspiciously short (%d chars, minimum expected %d)",
            stage, show_name, char_count, min_chars,
        )

    # Check for leaked prompt instructions
    for pattern in _INSTRUCTION_LEAK_PATTERNS:
        if re.search(pattern, text, re.MULTILINE):
            logger.warning(
                "LLM %s for '%s' may contain leaked prompt instructions (matched: %s)",
                stage, show_name, pattern,
            )
            break

    # Check for potential hallucinations — words repeated 4+ times in close
    # proximity often indicate corruption (e.g. "Nano Banana 2" x4)
    #
    # False-positive guard added May 2026: the Tesla Ep459 run flagged
    # "may 02, 2026," (9×), "02, 2026," (7×), "it matters" (11×) and
    # similar — every story timestamp + the prompt-template "this
    # matters for X" pattern. None were hallucinations; they were
    # purely structural artefacts of the digest format. Filter both
    # date-fragment patterns and known prompt-template phrases below
    # before counting toward `_suspicious_count`.
    _DATE_FRAGMENT_RE = re.compile(
        # Matches things like "02, 2026,", "may 02,", "may, 2026,",
        # "02 may," — any combination of an optional month name with
        # a 1-2 digit day-of-month and a 4-digit year, possibly comma-
        # separated. These appear once per story timestamp and trip
        # the detector at high story counts without indicating
        # hallucination.
        r"^"
        r"(?:(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)\w*"
        r"\s*[,]?\s*)?"
        r"(?:\d{1,2}\s*[,]?\s*)?"
        r"(?:(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)\w*"
        r"\s*[,]?\s*)?"
        r"(?:\d{4}\s*[,]?\s*)?"
        r"$",
        re.IGNORECASE,
    )

    def _is_date_fragment(phrase: str) -> bool:
        """True if the phrase is just a date-shape with no content."""
        # Require at least one numeric token (year or day) — otherwise
        # this matches every English word.
        if not any(c.isdigit() for c in phrase):
            return False
        return bool(_DATE_FRAGMENT_RE.match(phrase.strip()))

    _suspicious_count = 0
    words = text.split()
    if len(words) > 50:
        # Scan for any 2-3 word phrase that appears 4+ times
        from collections import Counter
        bigrams = [" ".join(words[i:i+2]).lower() for i in range(len(words) - 1)]
        bigram_counts = Counter(bigrams)
        # Common phrases that naturally repeat in news digests and podcast scripts
        _COMMON_BIGRAMS = {
            # Articles / prepositions
            "the the", "of the", "in the", "to the", "and the", "on the",
            "for the", "is the", "is a", "it's a", "this is", "with the",
            "at the", "by the", "from the", "that the", "has been",
            # Host attribution patterns (e.g. "patrick: the", "host: this")
            "patrick: the", "patrick: this", "patrick: it", "patrick: a",
            "patrick: so", "patrick: now", "patrick: and", "patrick: but",
            "**host:** the", "**host:** this", "**host:** it", "**host:** a",
            # Olya host attribution (Привет, Русский! language learning show)
            "**olya:** the", "**olya:** this", "**olya:** it", "**olya:** a",
            "**olya:** so", "**olya:** now", "**olya:** and", "**olya:** but",
            "**olya:** that", "**olya:** repeat", "**olya:** can",
            "**olya:** let's", "**olya:** ok,", "**olya:** today",
            "olya: the", "olya: this", "olya: it", "olya: that",
            "olya: repeat", "olya: so", "olya: now", "olya: let's",
            # Language learning pedagogical patterns
            "it means", "that means", "which means", "means the",
            "repeat after", "after me.", "after me,", "after me:", "say it",
            "that means,", "[short pause]",
            "in russian", "in english", "the russian", "the english",
            "- russian", "- **russian", "russian (cyrillic):",
            # Structured digest labels (vocabulary lists repeat per word)
            "**example sentence:**", "example sentence:",
            "**example translation:**", "example translation:",
            "**memory hook:**", "memory hook:",
            "**russian (cyrillic):**",
            # Section separators / formatting
            "━━━━━━━━━━ ###", "━━━━━━━━━━━━━━━━━━━━ ###",
            # Article reference patterns
            "according to", "going to", "we're going",
            # Prompt-template artefacts. The "this matters for X" line
            # appears once per story by prompt design, so the bigrams
            # below trip the detector at high story counts even though
            # nothing is hallucinated. Spec v2 follow-up after Ep459.
            "it matters", "matters for", "this matters",
        }
        # Podcast scripts are longer and naturally have more repeated phrases
        _rep_threshold = 5 if stage == "podcast_script" else 4
        for phrase, count in bigram_counts.most_common(5):
            # Skip common phrases
            if phrase in _COMMON_BIGRAMS:
                continue
            # Skip phrases that are mostly stopwords or very short tokens
            tokens = phrase.split()
            if all(len(t) <= 3 for t in tokens):
                continue
            # Skip date-shape fragments — purely structural, not hallucination.
            if _is_date_fragment(phrase):
                continue
            if count >= _rep_threshold:
                _suspicious_count += 1
                logger.warning(
                    "LLM %s for '%s' has suspicious repetition: '%s' appears %d times (possible hallucination)",
                    stage, show_name, phrase, count,
                )

    # Also scan for 3-word phrases (trigrams) — catches patterns like
    # "the question worth" that slip through bigram detection.
    if len(words) > 50:
        trigrams = [" ".join(words[i:i+3]).lower() for i in range(len(words) - 2)]
        trigram_counts = Counter(trigrams)
        _COMMON_TRIGRAMS = {
            "of the the", "in the the", "one of the", "some of the",
            "a lot of", "going to be", "it's going to",
            "according to the", "is going to", "we're going to",
            # Prompt-template artefacts — "this matters for X" appears
            # once per story by prompt design. Spec v2 follow-up after
            # Ep459 flagged "it matters for" 11×.
            "it matters for", "this matters for", "matters for the",
            "matters for tesla", "matters for investors",
            "matters for the", "matters for business",
            # Language learning pedagogical patterns
            "it sounds like", "sounds like the", "the english word",
            "the russian word", "in russian it", "means it is",
            "that means the", "it means the", "which means the",
            "repeat after me", "repeat after me.", "repeat after me,",
            "repeat after me:", "say it with",
            # Structured vocabulary card labels (per-word repetition)
            "- **russian (cyrillic):**", "- russian (cyrillic):",
            "**memory hook:** sounds", "**memory hook:** think",
            "**memory hook:** imagine", "**memory hook:** picture",
            "hook:** sounds like", "hook:** think of",
            "**example sentence:**", "example sentence: the",
            "**example translation:**",
        }
        # Regex patterns for pedagogical trigrams that can't be enumerated
        # (mirrors _PEDAGOGICAL_PATTERNS in review_episodes.py)
        _PEDAGOGICAL_TRIGRAM_PATTERNS = [
            re.compile(r"^\*?\*?\w+:?\*?\*?\s+repeat after"),  # "olya: repeat after"
            re.compile(r"^repeat after \w+"),                    # "repeat after me"
            re.compile(r"^\*?\*?\w+:?\*?\*?\s+that means"),    # "olya: that means"
            re.compile(r"^\*?\*?\w+:?\*?\*?\s+it means"),      # "olya: it means"
            re.compile(r"^means (?:it is|the|i am)"),           # tail fragments
            re.compile(r"^\*\*\w[\w\s]*:\*\*"),                  # bold labels: "**Memory Hook:**"
            re.compile(r"^- \*\*\w"),                            # "- **Russian..." list items
        ]
        for phrase, count in trigram_counts.most_common(5):
            if phrase in _COMMON_TRIGRAMS:
                continue
            tokens = phrase.split()
            if all(len(t) <= 3 for t in tokens):
                continue
            if any(p.match(phrase) for p in _PEDAGOGICAL_TRIGRAM_PATTERNS):
                continue
            # Skip date-shape trigrams (e.g. "may 02, 2026," appearing
            # once per story timestamp). Spec v2 follow-up after Ep459.
            if _is_date_fragment(phrase):
                continue
            if count >= _rep_threshold:
                _suspicious_count += 1
                logger.warning(
                    "LLM %s for '%s' has suspicious trigram repetition: '%s' appears %d times",
                    stage, show_name, phrase, count,
                )

    # Warn if podcast script is too short to fill target duration
    if stage == "podcast_script":
        word_count = len(text.split())
        threshold = min_podcast_words or 1500
        if word_count < threshold:
            logger.warning(
                "Podcast script for '%s' is too short (%d words, target >%d). "
                "Consider regenerating with more depth.",
                show_name, word_count, threshold,
            )

    # Detect story-level duplication — same news story retold in different
    # sections of the podcast script (e.g. school bus story told at lines
    # 7-13 and again at lines 31-35 with different framing).
    if stage in ("digest", "podcast_script"):
        _suspicious_count += _detect_story_duplication(text, show_name)

    return _suspicious_count


def _normalize_for_compare(line: str) -> str:
    """Normalize a line for duplicate comparison.

    Strips host prefixes (``Patrick:``, ``Olya:``), leading/trailing
    whitespace, and common filler phrases so that near-identical
    transition sentences match.
    """
    s = re.sub(r"^\w+:\s*", "", line.strip())
    # Drop minor filler differences ("these days", "this week", etc.)
    s = re.sub(r"\b(these days|this week|right now|at the moment)\b", "", s)
    s = re.sub(r"\s{2,}", " ", s).strip().lower()
    return s


def _dedup_transition_sentences(lines: list[str]) -> list[str]:
    """Remove duplicate transition sentences from a podcast script.

    The LLM sometimes writes a transition tease at the end of one
    paragraph and repeats it (identically or near-identically) as
    the first sentence of the next paragraph.  This function detects
    such duplicates and removes the *first* occurrence (the tease at
    the end of the previous paragraph), keeping the version that opens
    the new topic.

    Works across blank-line paragraph boundaries and also catches
    consecutive non-blank lines that are duplicates.
    """
    if not lines:
        return lines

    # Identify content lines (non-blank) and their normalized forms
    content_indices: list[int] = []
    normalized: dict[int, str] = {}
    for i, line in enumerate(lines):
        if line.strip():
            content_indices.append(i)
            normalized[i] = _normalize_for_compare(line)

    # Find pairs of content lines where the earlier one's last sentence
    # matches the later one.  We check consecutive content lines
    # (which may be separated by blank lines).
    drop_indices: set[int] = set()
    for ci in range(len(content_indices) - 1):
        idx_a = content_indices[ci]
        idx_b = content_indices[ci + 1]
        norm_a = normalized[idx_a]
        norm_b = normalized[idx_b]

        if len(norm_b) < 30:
            continue  # Too short to be a meaningful transition

        # Case 1: entire line A == line B (exact or near-exact)
        if norm_a == norm_b:
            drop_indices.add(idx_a)
            logger.info("Stripped duplicate transition line: %s", lines[idx_a].strip()[:80])
            continue

        # Case 2: line A ends with a sentence that matches line B.
        # Split A into sentences and check if the last one matches B.
        # This handles: "...wearing people down. Speaking of Cyber-cab..."
        sentences_a = re.split(r"(?<=[.!?])\s+", norm_a)
        if len(sentences_a) >= 2:
            last_sentence_a = sentences_a[-1].strip()
            if len(last_sentence_a) >= 30 and _sentence_similar(last_sentence_a, norm_b):
                # Remove the trailing sentence from line A instead of dropping the whole line
                orig_line = lines[idx_a]
                # Find and remove the last sentence from the original line
                orig_sentences = re.split(r"(?<=[.!?])\s+", orig_line.strip())
                if len(orig_sentences) >= 2:
                    lines[idx_a] = " ".join(orig_sentences[:-1])
                    logger.info(
                        "Stripped duplicate trailing transition: %s",
                        orig_sentences[-1][:80],
                    )

    result = [line for i, line in enumerate(lines) if i not in drop_indices]
    return result


def _sentence_similar(a: str, b: str) -> bool:
    """Check if two normalized sentences are similar enough to be duplicates.

    Uses word-level overlap: if >= 80% of the shorter sentence's words
    appear in the longer one, they're considered duplicates.
    """
    words_a = set(a.split())
    words_b = set(b.split())
    if not words_a or not words_b:
        return False
    overlap = words_a & words_b
    smaller = min(len(words_a), len(words_b))
    return len(overlap) / smaller >= 0.80


def _strip_metadata_from_script(script: str) -> str:
    """Remove production metadata that leaked into the podcast script.

    This is a blunt regex pass that runs BEFORE the line-by-line sanitizer
    below.  It catches metadata patterns regardless of line structure.
    """
    patterns_to_remove = [
        # Bracketed production-notes blocks that the LLM copied from the prompt
        r"\[PRODUCTION NOTES[^\]]*\][\s\S]*?\[END PRODUCTION NOTES\]",
        # Standalone word/sentence count references
        r"\b\d{3,4}\s*(?:words?|word count)\b",
        r"\b\d{1,3}\s*(?:sentences?|sentence count)\b",
        r"\bword count[:\s]*\d+\b",
        r"\bscript length[:\s]*\d+\b",
        r"\btarget(?:ing)?\s*\d+\s*words?\b",
        r"\bapproximately\s*\d{3,4}\s*words?\b",
        # Timing targets that leak from prompt structural markers
        r"\btarget:\s*\d+\s*[-–]\s*\d+\s*(?:seconds?|minutes?)\s+of\s+audio\b",
        r"\bproducing\s+(?:a|an)\s+\d+\s*[-–]\s*\d+\s*minute\s+episode\b",
        r"\bthis\s+(?:is\s+)?(?:a|an)\s+\d+\s*[-–]?\s*\d*\s*minute\s+(?:podcast|episode|script)\b",
        # Orphan DO NOT READ ALOUD markers
        r"\[?DO NOT READ ALOUD[^\]]*\]?",
        # Segment labels on their own line (e.g. "[Segment 3: Hook]", "Segment 3:")
        r"^\s*\[?Segment\s*\d*\s*[:-]?\s*[^\]\n]*\]?\s*$",
        # Bracketed section timing markers (e.g. "[Intro — 15 seconds]")
        r"^\s*\[.{3,50}\s*[-–—]\s*\d+\s*[-–]?\s*\d*\s*(?:seconds?|minutes?)\s*\]\s*$",
    ]

    for pattern in patterns_to_remove:
        script = re.sub(pattern, "", script, flags=re.IGNORECASE | re.MULTILINE)

    # Collapse any resulting run of blank lines
    script = re.sub(r"\n{3,}", "\n\n", script)
    return script.strip()


def _sanitize_podcast_script(text: str) -> str:
    """Strip known LLM artifacts that break TTS quality.

    Defense-in-depth: even when prompts forbid these patterns, LLMs
    occasionally include them anyway.  Stripping here prevents them
    from reaching TTS.
    """
    import re

    # First, blunt metadata strip (handles multiline PRODUCTION NOTES blocks etc.)
    text = _strip_metadata_from_script(text)

    lines = text.split("\n")
    cleaned = []
    for line in lines:
        stripped = line.strip()
        # Strip leading markdown formatting (* _ **) for matching purposes
        stripped_md = re.sub(r'^[\s*_`]+', '', stripped)
        # Remove standalone word/character count metadata lines
        if re.match(r"(?i)^\(?\s*(word\s*count|total\s*words|character\s*count)\s*[:：]", stripped_md):
            logger.info("Stripped metadata line from podcast script: %s", stripped[:80])
            continue
        # Russian equivalents
        if re.match(r"(?i)^\(?\s*количество\s*слов\s*[:：]", stripped_md):
            logger.info("Stripped metadata line from podcast script: %s", stripped[:80])
            continue
        # Catch word count/length metadata anywhere in the line (defense-in-depth
        # for spelled-out numbers like "two thousand three hundred eighty-seven")
        if re.search(r"(?i)\b(word\s*count|total\s*words|character\s*count)\s*[:：]", stripped):
            logger.info("Stripped metadata line from podcast script: %s", stripped[:80])
            continue
        # Catch "Target: X words" and duration metadata lines
        if re.search(r"(?i)\btarget\s*:\s*.*\bwords?\b", stripped):
            logger.info("Stripped metadata line from podcast script: %s", stripped[:80])
            continue
        # Catch "approximately X min spoken" metadata lines
        if re.search(r"(?i)\bapproximately\s+.*\bmin(utes?)?\s+(spoken|audio|reading)\b", stripped):
            logger.info("Stripped metadata line from podcast script: %s", stripped[:80])
            continue
        # Strip LLM meta-commentary lines about the script itself
        if re.match(r"(?i)^here'?s?\s+(your|the|my)\s+(expanded|revised|updated|rewritten)\s+script\b", stripped_md):
            logger.info("Stripped LLM meta-commentary from podcast script: %s", stripped[:80])
            continue
        cleaned.append(line)

    # Remove duplicate transition sentences — the LLM sometimes writes a
    # transition tease at the end of one paragraph and then repeats it
    # (identically or near-identically) to open the next paragraph.
    cleaned = _dedup_transition_sentences(cleaned)

    # Strip ``Patrick:`` (or other speaker-prefix) leakage at the
    # start of paragraphs. Operator caught this on TST Ep465 (May 6
    # 2026): the script had ``Patrick: Tesla...`` opening 5 of the
    # news segments — the LLM was treating the prompt's host name
    # as a literal speaker tag. The TTS would then SAY "Patrick" out
    # loud as a name. Stripping here keeps the host's voice
    # consistent without forcing prompts to play whack-a-mole with
    # the model's habit.
    text_joined = "\n".join(cleaned)
    text_joined = re.sub(
        r"(?im)^\s*(?:host|patrick|оля|olya|olia)\s*[:：]\s+",
        "",
        text_joined,
    )
    # Strip consecutive same-sentence duplicates within a single line.
    # Operator caught (Финансы Просто Ep32, May 6 2026) the LLM
    # producing ``Давайте разберёмся! Давайте разберёмся в самых
    # важных финансовых новостях`` — same opener twice in one
    # narration line. The TTS then said it twice, which sounds
    # broken. Match a sentence (ending in . ! ? or Cyrillic
    # equivalents) that immediately repeats verbatim.
    text_joined = re.sub(
        r"([^.!?…\n]+[.!?…])\s+\1(?=\s)",
        r"\1",
        text_joined,
    )
    return text_joined


# ---------------------------------------------------------------------------
# Public generation functions
# ---------------------------------------------------------------------------

def _build_educational_fallback_prompt(
    config,
    template_vars: Dict[str, Any],
) -> str:
    """Build a self-contained educational episode prompt that doesn't need articles.

    When the LLM refuses twice because the news articles aren't relevant enough,
    this prompt asks it to generate a purely educational episode — teaching a
    financial concept from scratch.  This ensures the pipeline always produces
    an episode rather than failing.
    """
    today_str = template_vars.get("today_str", "сегодня")
    # Grab recent deep-dive topics to avoid repetition
    recent_topics = template_vars.get("recent_deep_dive_topics", "")

    # Detect language from config name / description
    is_russian = any(
        c in (config.name or "")
        for c in "абвгдежзиклмнопрстуфхцчшщъыьэюя"
    )

    if is_russian:
        return (
            f"# Финансы Просто — Образовательный выпуск\n"
            f"**Дата:** {today_str}\n\n"
            f"Сегодня — специальный образовательный выпуск. Вместо обзора новостей "
            f"ты проведёшь глубокий мастер-класс по одному важному финансовому понятию "
            f"для русскоговорящих женщин в Канаде (Ванкувер / BC).\n\n"
            f"**ТЕМЫ, КОТОРЫЕ УЖЕ БЫЛИ (выбери ДРУГУЮ):**\n{recent_topics}\n\n"
            f"**ВЫБЕРИ ОДНУ ТЕМУ из этого списка:**\n"
            f"- Как открыть и использовать TFSA — пошагово, от нуля\n"
            f"- RRSP vs TFSA — что выбрать и когда\n"
            f"- FHSA — новый счёт для покупки первого жилья в Канаде\n"
            f"- Как работает ипотека в Канаде — фиксированная vs плавающая ставка\n"
            f"- GIC — гарантированные инвестиции, когда они имеют смысл\n"
            f"- ETF для начинающих — что это и как купить первый\n"
            f"- Как подать налоговую декларацию в Канаде — пошаговое руководство\n"
            f"- Кредитный рейтинг в Канаде — как проверить и улучшить\n"
            f"- Canada Child Benefit (CCB) — как получить максимум\n"
            f"- Как составить семейный бюджет — метод конвертов и приложения\n"
            f"- CPP и OAS — как работает пенсия в Канаде\n"
            f"- Страхование в BC — ICBC, медицинское, страхование жизни\n"
            f"- Как экономить на продуктах в Ванкувере — практические лайфхаки\n"
            f"- RESP — как копить на образование детей\n"
            f"- Что такое инфляция и как защитить сбережения\n\n"
            f"**ФОРМАТ — точно такой же, как обычный выпуск:**\n\n"
            f"# Финансы Просто\n"
            f"**Дата:** {today_str}\n\n"
            f"**ЗАГОЛОВОК:** [Захватывающее название образовательного выпуска. Под 120 символов.]\n\n"
            f"**Что сегодня важного:** 3-4 предложения. Объясни, чему научимся сегодня.\n\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"### Главная тема\n"
            f"Глубокое объяснение выбранного понятия. 10-14 предложений:\n"
            f"- Что это такое — простым языком, с аналогией из жизни\n"
            f"- Как это работает — пошагово\n"
            f"- Почему это важно для вашей семьи\n"
            f"- Конкретные цифры для Ванкувера / BC\n"
            f"- Что можно сделать прямо сейчас\n"
            f"Source: Общее понятие\n\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"### Объясни как подруге\n"
            f"Связанное понятие — 6-8 предложений по методу «подруга спросила».\n"
            f"Source: Общее понятие\n\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"### Практические советы\n"
            f"2-3 конкретных шага, которые можно сделать прямо сейчас.\n"
            f"Source: Общее понятие\n\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"### Коротко и ясно\n"
            f"2-3 интересных финансовых факта, связанных с темой выпуска.\n"
            f"Source: Общее понятие\n\n"
            f"ВЕСЬ текст на РУССКОМ ЯЗЫКЕ. Объём: 800-1200 слов.\n"
            f"Создай выпуск ПРЯМО СЕЙЧАС."
        )
    else:
        # Generic English educational fallback
        show_name = config.name or "the show"
        return (
            f"Today is {today_str}. There were not enough relevant news articles "
            f"for a standard episode of {show_name}.\n\n"
            f"Instead, create a SPECIAL EDUCATIONAL EPISODE. Pick one topic that "
            f"is highly relevant to the show's audience and explain it in depth, "
            f"following the exact same output format as a normal episode.\n\n"
            f"Topics already covered recently (pick a DIFFERENT one):\n"
            f"{recent_topics}\n\n"
            f"Generate the educational episode NOW, in the standard format."
        )


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=15),
    retry=retry_if_exception_type(_TRANSIENT_ERRORS),
)
def generate_digest(
    template_vars: Dict[str, Any],
    config,
    tracker: Optional[dict] = None,
    prompt_suffix: str = "",
) -> str:
    """Generate the news digest text using the show's digest prompt.

    Parameters
    ----------
    template_vars:
        Values to fill into the prompt template (e.g. ``today_str``,
        ``news_section``, ``price``, etc.).
    config:
        A ``ShowConfig`` instance.
    tracker:
        Optional cost-tracking dict (from ``engine.tracking``).
    prompt_suffix:
        Optional text appended to the prompt (e.g. retry instructions
        when a previous attempt was missing required sections).

    Returns
    -------
    str
        The generated digest text.
    """
    prompt = load_prompt(config.llm.digest_prompt_file, template_vars)
    if prompt_suffix:
        prompt += prompt_suffix

    system_prompt = None
    if config.llm.system_prompt_file:
        sp_path = Path(config.llm.system_prompt_file)
        if sp_path.exists():
            system_prompt = sp_path.read_text(encoding="utf-8").strip()

    logger.info("Generating digest for '%s' (model=%s, temp=%.1f) ...",
                config.name, config.llm.model, config.llm.digest_temperature)

    text, meta = _call_grok(
        prompt,
        model=config.llm.model,
        system_prompt=system_prompt,
        temperature=config.llm.digest_temperature,
        max_tokens=config.llm.max_tokens,
    )

    # Retry once with 50% more tokens if the response was truncated
    if meta.get("finish_reason") == "length":
        bumped_tokens = int(config.llm.max_tokens * 1.5)
        logger.warning(
            "Digest truncated at %d tokens — retrying with %d tokens",
            config.llm.max_tokens, bumped_tokens,
        )
        text, meta = _call_grok(
            prompt,
            model=config.llm.model,
            system_prompt=system_prompt,
            temperature=config.llm.digest_temperature,
            max_tokens=bumped_tokens,
        )
        if meta.get("finish_reason") == "length":
            logger.warning(
                "Digest still truncated at %d tokens — proceeding with best effort",
                bumped_tokens,
            )

    if tracker and "usage" in meta:
        try:
            from engine.tracking import record_llm_usage
            record_llm_usage(
                tracker,
                "x_thread_generation",
                meta["usage"].get("prompt_tokens", 0),
                meta["usage"].get("completion_tokens", 0),
                model=config.llm.model,
            )
        except Exception as e:
            logger.warning("Failed to record LLM usage: %s", e)

    logger.info("Digest generated (%d chars, %s tokens)",
                len(text), meta.get("usage", {}).get("total_tokens", "?"))

    # Validate the digest is usable — if the LLM refused, retry up to 2 times
    # with increasingly aggressive overrides before giving up.
    try:
        _rep_count = _validate_llm_output(text, stage="digest", show_name=config.name)
    except LLMRefusalError:
        # --- Retry 1: same prompt + bilingual anti-refusal suffix ---
        logger.warning(
            "LLM refused to generate digest for '%s' — retrying with "
            "anti-refusal override (attempt 1/2) ...", config.name,
        )
        anti_refusal_suffix = (
            "\n\n---\n"
            "CRITICAL OVERRIDE / КРИТИЧЕСКОЕ УКАЗАНИЕ:\n"
            "You MUST produce a complete digest in the format specified above. "
            "Do NOT refuse. Do NOT say you cannot.\n"
            "Ты ОБЯЗАНА создать полный выпуск в указанном формате. "
            "НЕ ОТКАЗЫВАЙСЯ. НЕ говори, что не можешь.\n\n"
            "If the provided articles lack sufficient relevant content, "
            "switch to EDUCATIONAL mode: pick 2-3 financial concepts "
            "relevant to the show's audience and explain them in depth, "
            "following the exact same output format. An educational episode "
            "is always better than no episode.\n"
            "Если статьи недостаточно релевантны — переключись на "
            "ОБРАЗОВАТЕЛЬНЫЙ режим: выбери 2-3 финансовых понятия, важных "
            "для аудитории, и объясни их подробно в том же формате. "
            "Образовательный выпуск ВСЕГДА лучше, чем отказ.\n\n"
            "Generate the digest NOW. Создай обзор ПРЯМО СЕЙЧАС."
        )
        retry_prompt = prompt + anti_refusal_suffix
        text, meta2 = _call_grok(
            retry_prompt,
            model=config.llm.model,
            system_prompt=system_prompt,
            temperature=config.llm.digest_temperature,
            max_tokens=config.llm.max_tokens,
        )
        if tracker and "usage" in meta2:
            try:
                from engine.tracking import record_llm_usage
                record_llm_usage(
                    tracker,
                    "x_thread_generation_retry",
                    meta2["usage"].get("prompt_tokens", 0),
                    meta2["usage"].get("completion_tokens", 0),
                    model=config.llm.model,
                )
            except Exception as e:
                logger.warning("Failed to record retry LLM usage: %s", e)

        logger.info("Retry 1 digest generated (%d chars, %s tokens)",
                    len(text), meta2.get("usage", {}).get("total_tokens", "?"))

        try:
            _rep_count = _validate_llm_output(text, stage="digest", show_name=config.name)
        except LLMRefusalError:
            # --- Retry 2: pure educational episode (no articles needed) ---
            logger.warning(
                "LLM refused again for '%s' — retrying with pure educational "
                "prompt (attempt 2/2) ...", config.name,
            )
            edu_prompt = _build_educational_fallback_prompt(
                config, template_vars,
            )
            text, meta3 = _call_grok(
                edu_prompt,
                model=config.llm.model,
                system_prompt=system_prompt,
                temperature=config.llm.podcast_temperature,  # slightly more creative
                max_tokens=config.llm.max_tokens,
            )
            if tracker and "usage" in meta3:
                try:
                    from engine.tracking import record_llm_usage
                    record_llm_usage(
                        tracker,
                        "x_thread_generation_retry_edu",
                        meta3["usage"].get("prompt_tokens", 0),
                        meta3["usage"].get("completion_tokens", 0),
                        model=config.llm.model,
                    )
                except Exception as e:
                    logger.warning("Failed to record edu retry LLM usage: %s", e)

            logger.info("Retry 2 (educational) digest generated (%d chars, %s tokens)",
                        len(text), meta3.get("usage", {}).get("total_tokens", "?"))
            # Validate — if even the educational fallback refuses, try a
            # different model before giving up.
            try:
                _rep_count = _validate_llm_output(text, stage="digest", show_name=config.name)
            except LLMRefusalError:
                fallback_model = _resolve_fallback_model(config)
                if config.llm.model == fallback_model:
                    raise  # Already using fallback model — nothing left to try
                # --- Retry 3: fallback model with educational prompt ---
                logger.warning(
                    "LLM refused even educational fallback for '%s' — "
                    "trying fallback model '%s' ...",
                    config.name, fallback_model,
                )
                text, meta4 = _call_grok(
                    edu_prompt,
                    model=fallback_model,
                    system_prompt=system_prompt,
                    temperature=config.llm.podcast_temperature,
                    max_tokens=config.llm.max_tokens,
                )
                if tracker:
                    try:
                        from engine.tracking import record_refusal_fallback
                        record_refusal_fallback(tracker, "digest", fallback_model)
                    except Exception:
                        pass
                if tracker and "usage" in meta4:
                    try:
                        from engine.tracking import record_llm_usage
                        record_llm_usage(
                            tracker,
                            "x_thread_generation_retry_fallback_model",
                            meta4["usage"].get("prompt_tokens", 0),
                            meta4["usage"].get("completion_tokens", 0),
                            model=fallback_model,
                        )
                    except Exception as e:
                        logger.warning("Failed to record fallback model LLM usage: %s", e)
                logger.info(
                    "Retry 3 (fallback model) digest generated (%d chars, %s tokens)",
                    len(text), meta4.get("usage", {}).get("total_tokens", "?"),
                )
                # Validate — if fallback model also refuses, let it propagate
                _rep_count = _validate_llm_output(text, stage="digest", show_name=config.name)

    # If the digest has severe repetition (3+ distinct phrases appearing 4+
    # times), retry once with lower temperature to reduce hallucination.
    # Only retry if we haven't already exhausted retries via refusal recovery,
    # and guard against the retry itself being refused.
    if _rep_count >= 3:
        logger.warning(
            "High repetition in digest for '%s' (%d suspicious phrases) — "
            "retrying with lower temperature ...",
            config.name, _rep_count,
        )
        lower_temp = max(0.1, config.llm.digest_temperature * 0.7)
        try:
            text_retry, _ = _call_grok(
                prompt,
                model=config.llm.model,
                system_prompt=system_prompt,
                temperature=lower_temp,
                max_tokens=config.llm.max_tokens,
            )
            _rep_retry = _validate_llm_output(
                text_retry, stage="digest", show_name=config.name,
            )
            if _rep_retry < _rep_count:
                # Guard: don't swap to a drastically shorter retry — it's
                # likely garbage even if it has fewer repetitions.
                if len(text_retry) < len(text) * 0.5:
                    logger.warning(
                        "Repetition retry for '%s' has fewer repetitions but is "
                        "drastically shorter (%d → %d chars) — keeping original",
                        config.name, len(text), len(text_retry),
                    )
                else:
                    logger.info(
                        "Repetition retry improved digest for '%s' (%d → %d suspicious phrases)",
                        config.name, _rep_count, _rep_retry,
                    )
                    text = text_retry
            else:
                logger.warning(
                    "Repetition retry did not improve for '%s' — keeping original",
                    config.name,
                )
        except (LLMRefusalError, Exception) as exc:
            logger.warning(
                "Repetition retry failed for '%s' (%s) — keeping original",
                config.name, exc,
            )

    # Strip near-verbatim duplicate story blocks so the podcast script
    # generator doesn't inherit them.
    text = _strip_duplicate_stories(text, show_name=config.name)

    # Strip the LLM's hallucinated timestamp suffixes from headlines.
    # Operator caught this on TST Ep465 (May 6 2026): the digest ended
    # up with "Tesla Semi Incentives Available Across Multiple States:
    # May 06, 2026, 9:04 AM PDT" repeating in 11 of the headlines.
    # The repetition guard caught it and tried to retry, but the model
    # kept appending the same stamp. Post-processing is the
    # belt-and-braces fix.
    text = _strip_hallucinated_timestamps(text)

    return text


def _strip_duplicate_stories(
    digest_text: str,
    *,
    threshold: float = 0.75,
    show_name: str = "unknown",
) -> str:
    """Remove near-duplicate paragraph blocks from a generated digest.

    Splits the digest into paragraph blocks, compares each pair of
    non-adjacent blocks via ``calculate_similarity``, and drops the LATER
    occurrence when similarity meets or exceeds ``threshold``.  Only blocks
    long enough to represent a story (>= 40 characters) are considered,
    so headers, separators, and short labels are never removed.
    """
    from engine.utils import calculate_similarity

    if not digest_text or not digest_text.strip():
        return digest_text

    blocks = digest_text.split("\n\n")
    drop_indices: set = set()

    for i, block_a in enumerate(blocks):
        if i in drop_indices:
            continue
        a_stripped = block_a.strip()
        if len(a_stripped) < 40:
            continue
        for j in range(i + 2, len(blocks)):  # skip adjacent blocks
            if j in drop_indices:
                continue
            block_b = blocks[j].strip()
            if len(block_b) < 40:
                continue
            sim = calculate_similarity(a_stripped, block_b)
            if sim >= threshold:
                drop_indices.add(j)
                logger.info(
                    "Stripped duplicate story block from '%s' digest "
                    "(similarity %.0f%%): '%s...'",
                    show_name, sim * 100, block_b[:80].replace("\n", " "),
                )

    if not drop_indices:
        return digest_text

    kept = [b for i, b in enumerate(blocks) if i not in drop_indices]
    return "\n\n".join(kept)


# Match the LLM's hallucinated timestamp stamps that appear inside
# headlines. Two shapes seen in production:
#   ": May 06, 2026, 9:04 AM PDT"
#   ": Friday, May 6, 2026 at 9:04 PM"
# The leading ``: `` (or ``: ``-with-space) plus the date+time pattern
# is what we want to strip — keep the headline body, drop the stamp.
_TIMESTAMP_STAMP_RE = re.compile(
    r"""
    \s*[:\-—]\s*                # leading separator (colon, dash, em-dash)
    (?:[A-Z][a-z]+,?\s+)?       # optional weekday like ``Monday,``
    [A-Z][a-z]+\s+\d{1,2},?     # month + day-number
    \s+\d{4}                    # year
    (?:[,\s]+\s*\d{1,2}:\d{2}   # optional hh:mm
       (?:\s*[AP]M)?            # optional AM/PM
       (?:\s+[A-Z]{2,4})?       # optional timezone abbrev like PDT
    )?
    """,
    re.VERBOSE,
)


def _strip_hallucinated_timestamps(text: str) -> str:
    """Strip the LLM's hallucinated ``: May 06, 2026, 9:04 AM PDT``
    suffixes from headlines.

    Tesla's grok-4.3 occasionally pads every Top-N headline with a
    "publication" timestamp it invents from the current date/time
    (operator caught 11 occurrences in TST Ep465 — every Top-10
    item plus the deep-dive). The repetition guard catches it and
    triggers a retry, but the retry often produces the same stamp.
    Post-processing strips the suffix at the end of the digest
    pipeline so downstream consumers (podcast script generation,
    blog rendering, RSS show notes) never see them.

    Conservative — only matches headline-tail stamps, not legitimate
    in-body date references like "On May 6, 2026, Tesla announced..."
    """
    if not text or "20" not in text:
        return text
    cleaned_lines = []
    for line in text.splitlines():
        # Only strip from headline-shaped lines: bullet, numbered,
        # or markdown-bold lines. Leave body prose untouched.
        is_headline = bool(re.match(r"^\s*([-*•]|\d+\.|\*\*)", line))
        if is_headline:
            stripped = _TIMESTAMP_STAMP_RE.sub("", line).rstrip()
            # Don't strip if it'd leave the line empty or just punctuation.
            if stripped and re.search(r"\w", stripped):
                cleaned_lines.append(stripped)
                continue
        cleaned_lines.append(line)
    return "\n".join(cleaned_lines)


def _generate_podcast_outline(
    digest: str,
    config,
    system_prompt: Optional[str] = None,
    tracker: Optional[dict] = None,
) -> str:
    """Generate a story-by-story outline before expanding into a full script.

    This is the first stage of prompt chaining — it produces a structured
    outline that the second call uses as scaffolding for the full script.
    """
    outline_prompt = (
        "Read the digest below and produce a concise story-by-story outline "
        "for a podcast episode.  For each story include:\n"
        "1. Story title (one line)\n"
        "2. Key points to cover (2-3 bullets)\n"
        "3. Suggested angle (business, technology, science, human interest, etc.)\n"
        "4. Transition idea to the next story\n\n"
        "Order stories from most to least important.  Include any special "
        "segments (Spotlight, Counterpoint, First Principles, etc.) if present "
        "in the digest.\n\n"
        f"DIGEST:\n{digest}"
    )

    logger.info("Generating podcast outline for '%s' (chain stage 1) ...", config.name)
    text, meta = _call_grok(
        outline_prompt,
        model=config.llm.model,
        system_prompt=system_prompt,
        temperature=config.llm.digest_temperature,  # Lower temp for planning
        max_tokens=1500,
    )

    if tracker and "usage" in meta:
        try:
            from engine.tracking import record_llm_usage
            record_llm_usage(
                tracker,
                "podcast_outline_generation",
                meta["usage"].get("prompt_tokens", 0),
                meta["usage"].get("completion_tokens", 0),
                model=config.llm.model,
            )
        except Exception as e:
            logger.warning("Failed to record outline LLM usage: %s", e)

    logger.info("Podcast outline generated (%d chars)", len(text))
    return text


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=15),
    retry=retry_if_exception_type(_TRANSIENT_ERRORS),
)
def generate_podcast_script(
    template_vars: Dict[str, Any],
    config,
    tracker: Optional[dict] = None,
) -> str:
    """Generate a podcast script from the show's podcast prompt.

    Parameters
    ----------
    template_vars:
        Values to fill into the podcast prompt template (e.g.
        ``episode_num``, ``digest``, ``today_str``, etc.).
    config:
        A ``ShowConfig`` instance.
    tracker:
        Optional cost-tracking dict.

    Returns
    -------
    str
        The generated podcast script text.
    """
    prompt = load_prompt(config.llm.podcast_prompt_file, template_vars)

    system_prompt = None
    if config.llm.system_prompt_file:
        sp_path = Path(config.llm.system_prompt_file)
        if sp_path.exists():
            system_prompt = sp_path.read_text(encoding="utf-8").strip()

    # Optional prompt chaining: generate an outline first, then expand
    use_chain = getattr(config.llm, "podcast_chain", False)
    if use_chain:
        digest_text = template_vars.get("digest", "")
        outline = _generate_podcast_outline(
            digest_text, config,
            system_prompt=system_prompt,
            tracker=tracker,
        )
        # Prepend the outline to the podcast prompt so the model follows it
        prompt = (
            f"STORY OUTLINE (follow this structure and order):\n{outline}\n\n"
            f"---\n\n{prompt}"
        )
        logger.info("Using prompt chaining for '%s' — outline prepended to podcast prompt",
                     config.name)

    logger.info("Generating podcast script for '%s' (model=%s, temp=%.1f) ...",
                config.name, config.llm.model, config.llm.podcast_temperature)

    # Use podcast-specific max_tokens if configured, otherwise fall back to shared max_tokens
    podcast_tokens = getattr(config.llm, "podcast_max_tokens", 0) or config.llm.max_tokens

    text, meta = _call_grok(
        prompt,
        model=config.llm.model,
        system_prompt=system_prompt,
        temperature=config.llm.podcast_temperature,
        max_tokens=podcast_tokens,
    )

    # Retry once with 50% more tokens if the response was truncated
    if meta.get("finish_reason") == "length":
        bumped_tokens = int(podcast_tokens * 1.5)
        logger.warning(
            "Podcast script truncated at %d tokens — retrying with %d tokens",
            podcast_tokens, bumped_tokens,
        )
        text, meta = _call_grok(
            prompt,
            model=config.llm.model,
            system_prompt=system_prompt,
            temperature=config.llm.podcast_temperature,
            max_tokens=bumped_tokens,
        )
        if meta.get("finish_reason") == "length":
            logger.warning(
                "Podcast script still truncated at %d tokens — proceeding with best effort",
                bumped_tokens,
            )

    if tracker and "usage" in meta:
        try:
            from engine.tracking import record_llm_usage
            record_llm_usage(
                tracker,
                "podcast_script_generation",
                meta["usage"].get("prompt_tokens", 0),
                meta["usage"].get("completion_tokens", 0),
                model=config.llm.model,
            )
        except Exception as e:
            logger.warning("Failed to record LLM usage: %s", e)

    logger.info("Podcast script generated (%d chars, %s tokens)",
                len(text), meta.get("usage", {}).get("total_tokens", "?"))

    min_words = getattr(config.llm, "min_podcast_words", 1500)

    # Use podcast-specific tokens for retries too
    podcast_tokens_for_retry = podcast_tokens

    # Validate the podcast script — recover from refusals with retries
    try:
        _rep_count = _validate_llm_output(text, stage="podcast_script",
                                          show_name=config.name,
                                          min_podcast_words=min_words)
    except LLMRefusalError:
        # --- Retry 1: lower temperature + simplified prompt (just digest) ---
        logger.warning(
            "LLM refused to generate podcast script for '%s' — "
            "retrying with lower temperature (attempt 1/2) ...",
            config.name,
        )
        digest_text = template_vars.get("digest", "")
        simple_prompt = (
            f"You are the host of {config.name}. Read the following digest and "
            f"convert it into a natural, conversational podcast script. "
            f"Speak directly to the listener. Cover every story.\n\n"
            f"DIGEST:\n{digest_text}"
        )
        lower_temp = max(0.3, config.llm.podcast_temperature * 0.6)
        text, meta_r1 = _call_grok(
            simple_prompt,
            model=config.llm.model,
            system_prompt=system_prompt,
            temperature=lower_temp,
            max_tokens=podcast_tokens_for_retry,
        )
        if tracker and "usage" in meta_r1:
            try:
                from engine.tracking import record_llm_usage
                record_llm_usage(
                    tracker, "podcast_script_refusal_retry",
                    meta_r1["usage"].get("prompt_tokens", 0),
                    meta_r1["usage"].get("completion_tokens", 0),
                    model=config.llm.model,
                )
            except Exception:
                pass
        logger.info("Podcast refusal retry 1 generated (%d chars)", len(text))

        try:
            _rep_count = _validate_llm_output(text, stage="podcast_script",
                                              show_name=config.name,
                                              min_podcast_words=min_words)
        except LLMRefusalError:
            # --- Retry 2: fallback model ---
            fallback_model = _resolve_fallback_model(config)
            if config.llm.model == fallback_model:
                raise
            logger.warning(
                "LLM refused podcast script again for '%s' — "
                "trying fallback model '%s' ...",
                config.name, fallback_model,
            )
            text, meta_r2 = _call_grok(
                simple_prompt,
                model=fallback_model,
                system_prompt=system_prompt,
                temperature=lower_temp,
                max_tokens=podcast_tokens_for_retry,
            )
            if tracker:
                try:
                    from engine.tracking import record_refusal_fallback
                    record_refusal_fallback(tracker, "podcast_script", fallback_model)
                except Exception:
                    pass
            if tracker and "usage" in meta_r2:
                try:
                    from engine.tracking import record_llm_usage
                    record_llm_usage(
                        tracker, "podcast_script_refusal_fallback_model",
                        meta_r2["usage"].get("prompt_tokens", 0),
                        meta_r2["usage"].get("completion_tokens", 0),
                        model=fallback_model,
                    )
                except Exception:
                    pass
            logger.info("Podcast refusal retry 2 (fallback model) generated (%d chars)", len(text))
            # If fallback model also refuses, let it propagate
            _rep_count = _validate_llm_output(text, stage="podcast_script",
                                              show_name=config.name,
                                              min_podcast_words=min_words)

    # Retry once if podcast script is catastrophically short (< 50% of
    # target).  Above that, accept the shorter script — fresh content
    # matters more than hitting a word count.
    word_count = len(text.split())
    _retry_threshold = max(600, int(min_words * 0.5))
    if word_count < _retry_threshold:
        logger.warning(
            "Podcast script for '%s' is very short (%d words, retry threshold %d). "
            "Retrying with expansion instructions ...",
            config.name, word_count, _retry_threshold,
        )
        retry_prompt = (
            f"The script you just wrote is only {word_count} words. "
            f"Please rewrite it with more substance:\n"
            f"- Add one missing element per story only if useful: a brief "
            f"listener takeaway, a transition, or a one-sentence why-it-matters\n"
            f"- Do NOT pad existing stories with filler or repeat content\n"
            f"- Do NOT add new stories \u2014 just deepen the existing ones\n"
            f"- Better to stay short than to repeat yourself\n\n"
            f"Here is your short script to expand:\n\n{text}"
        )
        text2, meta2 = _call_grok(
            retry_prompt,
            model=config.llm.model,
            system_prompt=system_prompt,
            temperature=config.llm.podcast_temperature,
            max_tokens=podcast_tokens,
        )

        if tracker and "usage" in meta2:
            try:
                from engine.tracking import record_llm_usage
                record_llm_usage(
                    tracker,
                    "podcast_script_retry",
                    meta2["usage"].get("prompt_tokens", 0),
                    meta2["usage"].get("completion_tokens", 0),
                    model=config.llm.model,
                )
            except Exception as e:
                logger.warning("Failed to record retry LLM usage: %s", e)

        word_count2 = len(text2.split())
        if word_count2 > word_count:
            logger.info(
                "Retry produced longer script for '%s' (%d \u2192 %d words)",
                config.name, word_count, word_count2,
            )
            text = text2
            _rep_count = _validate_llm_output(text, stage="podcast_script",
                                              show_name=config.name,
                                              min_podcast_words=min_words)
        else:
            logger.warning(
                "Retry did not improve script length for '%s' (%d \u2192 %d words), "
                "keeping original",
                config.name, word_count, word_count2,
            )

    # If the script has severe repetition, retry with lower temperature
    if _rep_count >= 3:
        logger.warning(
            "High repetition in podcast script for '%s' (%d suspicious phrases) — "
            "retrying with lower temperature ...",
            config.name, _rep_count,
        )
        lower_temp = max(0.1, config.llm.podcast_temperature * 0.7)
        try:
            text_retry, _ = _call_grok(
                prompt,
                model=config.llm.model,
                system_prompt=system_prompt,
                temperature=lower_temp,
                max_tokens=podcast_tokens,
            )
            _rep_retry = _validate_llm_output(
                text_retry, stage="podcast_script", show_name=config.name,
                min_podcast_words=min_words,
            )
            if _rep_retry < _rep_count:
                # Guard: don't swap to a drastically shorter retry — it's
                # likely garbage even if it has fewer repetitions.
                if len(text_retry) < len(text) * 0.5:
                    logger.warning(
                        "Repetition retry for '%s' has fewer repetitions but is "
                        "drastically shorter (%d → %d chars) — keeping original",
                        config.name, len(text), len(text_retry),
                    )
                else:
                    logger.info(
                        "Repetition retry improved script for '%s' (%d → %d suspicious phrases)",
                        config.name, _rep_count, _rep_retry,
                    )
                    text = text_retry
            else:
                logger.warning(
                    "Repetition retry did not improve for '%s' — keeping original",
                    config.name,
                )
        except (LLMRefusalError, Exception) as exc:
            logger.warning(
                "Repetition retry failed for '%s' (%s) — keeping original",
                config.name, exc,
            )

    # Phrase-level repetition loop detection (e.g. "the kind of" x6).
    # One retry with anti-repetition instructions if any "critical" violation.
    try:
        from engine.validation import detect_phrase_repetition
        reps = detect_phrase_repetition(text)
        critical_reps = [r for r in reps if r["severity"] == "critical"]
        if critical_reps:
            phrases_str = ", ".join(
                f'"{r["phrase"]}" ({r["count"]}x)' for r in critical_reps[:5]
            )
            logger.warning(
                "Repetition loop detected in '%s' podcast script: %s — regenerating once",
                config.name, phrases_str,
            )
            anti_rep_prompt = (
                f"{prompt}\n\n"
                f"IMPORTANT: Avoid repeating the same phrases. The following "
                f"phrases appeared too many times in a previous draft and must "
                f"not be reused: {phrases_str}. Use varied language and different "
                f"transitions throughout the script."
            )
            try:
                text_rr, meta_rr = _call_grok(
                    anti_rep_prompt,
                    model=config.llm.model,
                    system_prompt=system_prompt,
                    temperature=config.llm.podcast_temperature,
                    max_tokens=podcast_tokens,
                )
                if tracker and "usage" in meta_rr:
                    try:
                        from engine.tracking import record_llm_usage
                        record_llm_usage(
                            tracker, "podcast_script_anti_repetition_retry",
                            meta_rr["usage"].get("prompt_tokens", 0),
                            meta_rr["usage"].get("completion_tokens", 0),
                            model=config.llm.model,
                        )
                    except Exception:
                        pass
                reps_rr = detect_phrase_repetition(text_rr)
                critical_rr = [r for r in reps_rr if r["severity"] == "critical"]
                # Guard: don't swap if retry is drastically shorter (likely garbage)
                if not critical_rr and len(text_rr) >= len(text) * 0.5:
                    logger.info(
                        "Anti-repetition retry cleared critical loops for '%s'",
                        config.name,
                    )
                    text = text_rr
                else:
                    logger.warning(
                        "Anti-repetition retry did not clear critical loops for "
                        "'%s' — keeping original (daily review will flag it)",
                        config.name,
                    )
            except Exception as exc:
                logger.warning(
                    "Anti-repetition retry failed for '%s' (%s) — keeping original",
                    config.name, exc,
                )
    except Exception as exc:
        logger.warning("Repetition detection failed for '%s': %s", config.name, exc)

    text = _sanitize_podcast_script(text)
    return text
