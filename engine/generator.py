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

from tenacity import (
    before_sleep_log,
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

# Only retry on transient API errors — permanent errors (KeyError, FileNotFoundError,
# RuntimeError) will fail immediately instead of wasting 3x API credits.
try:
    from openai import APITimeoutError, APIConnectionError, RateLimitError
    _TRANSIENT_ERRORS = (APITimeoutError, APIConnectionError, RateLimitError)
    _RATE_LIMIT_ERRORS = (RateLimitError,)
except ImportError:
    # Fallback if openai isn't installed (e.g. in tests)
    _TRANSIENT_ERRORS = (TimeoutError, ConnectionError)
    _RATE_LIMIT_ERRORS = ()

logger = logging.getLogger(__name__)


class LLMRefusalError(RuntimeError):
    """Raised when the LLM refuses to generate content.

    Unlike quality warnings (short text, repetition), a refusal means the LLM
    explicitly declined to produce content.  Continuing the pipeline would waste
    TTS credits synthesising the refusal message into audio.
    """


class LLMEmptyOutputError(LLMRefusalError):
    """Raised when the LLM returns an empty completion.

    Subclasses ``LLMRefusalError`` so the existing refusal-recovery chains
    (anti-refusal retry → educational prompt → fallback model) engage.
    Before July 21 2026 an empty completion was only logged and flowed
    downstream — the SpaceX run shipped a 0-char digest into the expansion
    retry and the too-short abort path instead of simply retrying the call
    (the empty response was a transient xAI capacity glitch; a 429 followed
    minutes later).
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

# Directive for composing prompts from shared snippets.  Chosen to use angle
# brackets (not ``{...}``) so it survives ``str.format_map`` untouched and never
# collides with template placeholders.  Resolved *before* substitution, so a
# prompt with no directive renders byte-for-byte as before.
#   <<include: _shared/accuracy_rules.txt>>
_INCLUDE_RE = re.compile(r"<<\s*include:\s*([^>]+?)\s*>>")
_MAX_INCLUDE_DEPTH = 10


def _resolve_includes(raw: str, base_dir: Path, _seen: Optional[set] = None, _depth: int = 0) -> str:
    """Recursively expand ``<<include: path>>`` directives.

    Paths are resolved relative to *base_dir* (the directory of the file that
    contains the directive).  Guards against cycles and runaway recursion so a
    malformed shared snippet can never hang the pipeline.
    """
    if "<<include:" not in raw and "<<include :" not in raw and not _INCLUDE_RE.search(raw):
        return raw
    if _depth > _MAX_INCLUDE_DEPTH:
        raise ValueError(f"Prompt include recursion exceeded {_MAX_INCLUDE_DEPTH} levels")
    _seen = _seen or set()

    def _sub(match: "re.Match") -> str:
        rel = match.group(1).strip()
        inc_path = (base_dir / rel).resolve()
        key = str(inc_path)
        if key in _seen:
            raise ValueError(f"Circular prompt include detected: {rel}")
        if not inc_path.exists():
            raise FileNotFoundError(f"Included prompt snippet not found: {rel} (from {base_dir})")
        nested = inc_path.read_text(encoding="utf-8")
        return _resolve_includes(nested, inc_path.parent, _seen | {key}, _depth + 1)

    return _INCLUDE_RE.sub(_sub, raw)


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

    Shared snippets can be composed in via ``<<include: relative/path.txt>>``
    directives (resolved relative to *prompt_file*'s directory, before
    placeholder substitution).  Prompts with no directive are unaffected.
    """
    path = Path(prompt_file)
    if not path.exists():
        raise FileNotFoundError(f"Prompt file not found: {path}")
    raw = path.read_text(encoding="utf-8")
    raw = _resolve_includes(raw, path.parent)
    if template_vars is not None:
        return raw.format_map(template_vars)
    return raw


# ---------------------------------------------------------------------------
# xAI / Grok API call
# ---------------------------------------------------------------------------

def _get_api_key() -> str:
    return (os.getenv("GROK_API_KEY") or os.getenv("XAI_API_KEY") or "").strip()


# Capacity-class 429s from xAI ("model is currently at capacity ... try
# again in a few minutes") need MINUTES of backoff, not the OpenAI SDK's
# sub-second internal retries. Observed July 21 2026 (SpaceX ep039): three
# retries inside 5 seconds, all 429, and the digest retry was abandoned
# while capacity recovered shortly after. Waits: 30s → 60s → 120s between
# four attempts (~3.5 min total) — well inside the pipeline's time budget
# and long enough to ride out a typical capacity dip. Other transient
# errors keep their existing fast retry at the generate_* wrappers.
@retry(
    stop=stop_after_attempt(4),
    wait=wait_exponential(multiplier=30, min=30, max=120),
    retry=retry_if_exception_type(_RATE_LIMIT_ERRORS),
    before_sleep=before_sleep_log(logger, logging.WARNING),
    reraise=True,
)
def _call_grok(
    prompt: str,
    *,
    model: str = "grok-4.3",
    system_prompt: Optional[str] = None,
    temperature: float = 0.7,
    max_tokens: int = 3500,
    timeout: float = 300.0,
    cache_key: Optional[str] = None,
    reasoning_effort: Optional[str] = None,
) -> tuple[str, Dict[str, Any]]:
    """Call xAI Grok via the OpenAI-compatible endpoint.

    Returns ``(text, meta)`` where *meta* contains usage info.

    *cache_key* (optional) is sent as the ``x-grok-conv-id`` HTTP header so
    xAI sticky-routes requests that share a stable system-prompt prefix to
    the same server, maximizing automatic prompt-cache hits (see
    https://docs.x.ai/developers/advanced-api-usage/prompt-caching). When
    omitted the call is unchanged from the pre-caching path.

    *reasoning_effort* (optional: ``low`` / ``medium`` / ``high``) is sent
    only when set — required for meaningful grok-4.5 cost control (default
    high is expensive). Empty/None keeps requests byte-identical for
    models that ignore the field (grok-4.3 daily path).
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

    create_kwargs: Dict[str, Any] = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
    }
    # Sticky routing for prompt-cache reuse. Per-show keys keep digest /
    # podcast / retry calls for the same show on one server so the stable
    # system-prompt prefix can hit cache; different shows stay isolated.
    if cache_key:
        create_kwargs["extra_headers"] = {"x-grok-conv-id": str(cache_key)}
    effort = (reasoning_effort or "").strip().lower()
    if effort in ("low", "medium", "high"):
        create_kwargs["extra_body"] = {
            **(create_kwargs.get("extra_body") or {}),
            "reasoning_effort": effort,
        }

    resp = client.chat.completions.create(**create_kwargs)

    # content can come back None on degraded responses (all-reasoning
    # completions during capacity incidents) — normalize to "" so callers
    # see a clean empty string instead of an AttributeError.
    text = (resp.choices[0].message.content or "").strip()
    meta: Dict[str, Any] = {"provider": "openai_compat", "model": model}
    if cache_key:
        meta["cache_key"] = cache_key
    finish_reason = getattr(resp.choices[0], "finish_reason", None)
    meta["finish_reason"] = finish_reason
    # Only warn on length-truncation when the caller is actually trying
    # to produce content. Pre-flight LLM ping uses max_tokens=10 by
    # design — "truncated" is the expected outcome, not a regression.
    # Threshold of 200 is well below any legitimate digest/podcast
    # completion (smallest digest path uses >= 4000) but above every
    # health-check / classifier call we make today.
    if finish_reason == "length" and max_tokens >= 200:
        logger.warning(
            "LLM response truncated (finish_reason=length, max_tokens=%d) — "
            "output may end mid-sentence",
            max_tokens,
        )
    if hasattr(resp, "usage") and resp.usage:
        usage_meta: Dict[str, Any] = {
            "prompt_tokens": resp.usage.prompt_tokens,
            "completion_tokens": resp.usage.completion_tokens,
            "total_tokens": resp.usage.total_tokens,
        }
        # Prompt-cache telemetry (xAI returns this when a prefix hit).
        # Nested under prompt_tokens_details on Chat Completions; also
        # accept a top-level cached_tokens if the SDK flattens it.
        cached = 0
        details = getattr(resp.usage, "prompt_tokens_details", None)
        if details is not None:
            cached = int(getattr(details, "cached_tokens", 0) or 0)
        if not cached:
            cached = int(getattr(resp.usage, "cached_tokens", 0) or 0)
        if cached:
            usage_meta["cached_tokens"] = cached
            logger.info(
                "Grok prompt cache hit: %d / %d prompt tokens cached (key=%s)",
                cached, usage_meta["prompt_tokens"], cache_key or "-",
            )
        meta["usage"] = usage_meta
    return text, meta


def _show_cache_key(config: Any, stage: str = "") -> Optional[str]:
    """Stable sticky-routing key for a show's Grok Chat Completions calls.

    Format ``nerra-<slug>`` (stage is intentionally omitted so digest,
    podcast, outline, and retry calls share one server affinity and can
    reuse the system-prompt prefix cache). Returns ``None`` when the
    config has no slug so callers without a show identity stay on the
    legacy no-header path.
    """
    slug = getattr(config, "slug", None) or ""
    slug = str(slug).strip()
    if not slug:
        return None
    return f"nerra-{slug}"


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


def _llm_reasoning_effort(config: Any) -> Optional[str]:
    """Return a validated reasoning_effort from config, or None to omit."""
    effort = (
        getattr(getattr(config, "llm", None), "reasoning_effort", "") or ""
    ).strip().lower()
    return effort if effort in ("low", "medium", "high") else None


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
    known_entities: tuple = (),
) -> int:
    """Validate LLM output quality.

    Logs warnings for quality issues (short text, repetition, leaked
    instructions) so the pipeline can still proceed.  However, raises
    ``LLMRefusalError`` for outright refusals — a refusal is worse than
    no episode because it wastes TTS credits on garbage audio.

    Returns the count of distinct suspicious repetition phrases found
    (bigrams appearing 4+ times).  Callers can use this to decide
    whether to retry with a lower temperature.

    ``known_entities`` (the show's YAML ``keywords``) exempts the show's
    own product/entity names from the repetition detector: on Tesla,
    "model y" repeating 7× is the beat, not a hallucination. The July 21
    2026 Ep548 run burned a full lower-temp digest regen on
    'model y'/'the model'/'the model y' flags — and the regen introduced
    a heavier real tic ('watch for' 12×) while "improving" the count.
    """
    import re

    # Non-stopword tokens of the show's own entity keywords. A repeated
    # phrase containing one of these tokens is the show doing its job.
    _entity_tokens = set()
    for _ent in known_entities or ():
        for _tok in str(_ent).lower().split():
            if len(_tok) > 2 and _tok not in _STOPWORDS:
                _entity_tokens.add(_tok)

    def _is_entity_phrase(phrase: str) -> bool:
        return any(t in _entity_tokens for t in phrase.split())

    # Framing the SHOW ITSELF supplies. The narrative-memory block
    # (engine.show_memory) hands the prompt an "open questions" heading
    # per tracked program, so a memory-enabled show naturally says it
    # once per program — SpaceX Ep029/Ep035 tripped the retry purely on
    # "open question" / "open questions" / "whose open questions". Same
    # class as Omni View's steel-man phrases in _COMMON_BIGRAMS, but
    # matched as a family because it appears in several shapes.
    _STRUCTURAL_FRAMING = ("open question",)

    def _is_structural_framing(phrase: str) -> bool:
        return any(frag in phrase for frag in _STRUCTURAL_FRAMING)

    if not text or not text.strip():
        logger.error(
            "LLM returned EMPTY %s for '%s' — treating as retryable failure",
            stage, show_name,
        )
        raise LLMEmptyOutputError(
            f"LLM returned empty {stage} for '{show_name}'"
        )

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
            # Omni View "Steel Man" format (Phase 4): every story states
            # "the strongest case for each side ... rests on ...". With
            # 20-40 stories these per-story framing phrases recur 30-44x and
            # tripped 3 futile digest regenerations (regen can't change a
            # prompt-mandated format) — Ep068 burned ~6 min on this. Treat
            # as structural, like "this matters for". (Genuine monotony of
            # the steel-man framing is a separate prompt concern.)
            "strongest case", "case for", "rests on", "the strongest",
            "they differ", "differ on", "each side",
        }
        # Podcast scripts are longer and naturally have more repeated phrases
        _rep_threshold = 5 if stage == "podcast_script" else 4
        for phrase, count in bigram_counts.most_common(5):
            # Skip common phrases
            if phrase in _COMMON_BIGRAMS:
                continue
            # Bold markdown in a repeated phrase is a structural label/header
            # (e.g. "**what happened (neutral):**", "**steel-man each side:**",
            # "**memory hook:**") — never a hallucination loop, which lives in
            # plain prose. Skip generically so per-story bold labels at high
            # story counts don't trigger futile regenerations.
            if "**" in phrase:
                continue
            # Skip phrases that are mostly stopwords or very short tokens
            tokens = phrase.split()
            if all(len(t) <= 3 for t in tokens):
                continue
            # A bigram needs TWO content words to mean anything. The
            # length-only test above passed "the first" / "the same" /
            # "the work" / "whether the" straight through, and phrases
            # like those were the bulk of the measured false positives —
            # a determiner plus one word carries no information, so
            # repeating it says nothing about hallucination.
            if sum(1 for t in tokens if t not in _STOPWORDS) < 2:
                continue
            # Skip speaker-attribution bigrams (e.g. "host: the", "patrick:
            # this", "olya: now"): the first token is a dialogue label ending
            # in a colon, so the repeat is the script format, not a
            # hallucination. The enumerated allowlist only covered the bold
            # "**host:**" / named "patrick:" forms — a plain "Host:" label
            # (Models & Agents) slipped through and triggered wasteful
            # repetition retries that can't fix a format artifact.
            if tokens and tokens[0].endswith(":"):
                continue
            # Skip date-shape fragments — purely structural, not hallucination.
            if _is_date_fragment(phrase):
                continue
            # Skip the show's own entity names ("model y" on Tesla).
            if _is_entity_phrase(phrase):
                continue
            # Skip framing the show's own memory block supplies.
            if _is_structural_framing(phrase):
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
            # Omni View "Steel Man" per-story framing (Phase 4) — see the
            # bigram allowlist above. Structural, not hallucination.
            "the strongest case", "strongest case for", "rests on the",
            "they differ on", "case for the", "differ on the",
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
            # Bold markdown = structural label/header, never a hallucination
            # loop (see the bigram loop). Skip generically.
            if "**" in phrase:
                continue
            tokens = phrase.split()
            if all(len(t) <= 3 for t in tokens):
                continue
            # Same content-word floor as the bigram pass: a trigram that
            # is one content word padded with function words ("the open
            # question of") describes the show's own framing, not a loop.
            if sum(1 for t in tokens if t not in _STOPWORDS) < 2:
                continue
            # Speaker-attribution trigrams (e.g. "host: the first") are a
            # dialogue-format artifact, not hallucination — see the bigram
            # loop above.
            if tokens and tokens[0].endswith(":"):
                continue
            if any(p.match(phrase) for p in _PEDAGOGICAL_TRIGRAM_PATTERNS):
                continue
            # Skip date-shape trigrams (e.g. "may 02, 2026," appearing
            # once per story timestamp). Spec v2 follow-up after Ep459.
            if _is_date_fragment(phrase):
                continue
            # Skip the show's own entity names ("the model y" on Tesla).
            if _is_entity_phrase(phrase):
                continue
            # Skip framing the show's own memory block supplies.
            if _is_structural_framing(phrase):
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


def _retry_word_count_ok(orig_words: int, retry_words: int,
                         show_floor: int,
                         publication_floor: int = 0,
                         target_floor: int = 0) -> bool:
    """Decide whether a podcast-script retry's word count is healthy
    enough to swap in. Both repetition-retry paths use this gate.

    Three failure modes the gate protects against:

      1. ``Omni View Ep059 (2026-05-23)`` — anti-repetition retry
         replaced an 883-word original with a 555-word "cleaner"
         retry. The retry passed the char-length 0.5× check
         (3870/6163 ≈ 0.63) but then tripped the runner's 600-word
         hard floor and aborted the episode. Floor is enforced
         AFTER the swap, so we have to gate it BEFORE.
      2. Drastic shrinkage even above the floor. A retry that's
         lost 20%+ of word count almost certainly lost real
         content along with the repetition.
      3. ``Tesla Ep500 (2026-06-04)`` — the repetition retry took an
         already-publishable 1128-word script down to 1003 words.
         That cleared the hard-floor gate (1003 > 650), so the swap
         happened, but the dedup pass then trimmed it to 954 — under
         Tesla's 960-word *publication* soft floor — and the flagship
         episode was skipped. Cleaning up repetition is never worth
         turning a shippable episode into a skipped one, so when
         ``publication_floor`` is supplied and the ORIGINAL already
         clears it (with a ~10% dedup margin), the retry must clear it
         too.

    Returns True when ``retry_words`` clears ALL of:
      * 80 % of the original word count,
      * the per-show ``min_podcast_word_floor`` + 50-word margin
        (so the downstream hard-floor check has headroom), AND
      * (when ``publication_floor`` is given and the original was
        already publishable) the publication soft floor + ~10% margin
        for the dedup pass that runs before the runner's skip check.
    """
    threshold = max(int(orig_words * 0.8), show_floor + 50)
    if publication_floor:
        # ~10% margin mirrors ``_podcast_expansion_retry_threshold`` —
        # the dedup pass between here and run_show's skip check trims a
        # few percent off the word count.
        pub_margin = int(publication_floor * 1.1)
        if orig_words >= pub_margin:
            threshold = max(threshold, pub_margin)
    if target_floor and orig_words >= target_floor:
        # SpaceX Ep040 (2026-07-21): the retry swapped a target-compliant
        # 1365-word script for 1219 words (min_podcast_words 1300) — one
        # fewer flagged phrase cost 146 words and shipped a below-target
        # episode. When the ORIGINAL clears the show's word target, the
        # retry must clear it too — never trade length compliance for a
        # marginal repetition improvement.
        threshold = max(threshold, target_floor)
    return retry_words >= threshold


def _podcast_expansion_retry_threshold(
    min_words: int, *, expand_below_target: bool = False,
) -> int:
    """Word count below which ``generate_podcast_script`` triggers a
    one-shot expansion retry.

    This MUST stay at or above ``run_show.py``'s publication soft floor
    (``int(min_words * 0.6)``) so the two checks can't open a dead band:
    a script that clears this bar but falls under the soft floor would be
    accepted here and then silently skipped by the runner, never getting
    an expansion attempt (Tesla Ep493, 2026-05-30 — 874 words cleared the
    old 50%/800-word bar but fell under the 60%/960 soft floor and the
    episode was skipped). The ~10% margin above the soft floor covers the
    dedup pass that runs between generation and the skip check and trims a
    few percent off the count (Ep493 went 874 → 818). ``600`` is the
    network-wide absolute floor.

    *expand_below_target* (June 2026, per-show opt-in via
    ``llm.podcast_expand_below_target``): retry whenever the script is
    under the FULL target, not just near the skip floor. Added for
    Tesla after 9 of 10 episodes shipped 15-35% under the 1600-word
    target (avg 1238 words) with listener-value scores pinned at
    3.2-3.9 — the 66%-of-target threshold meant a 1100-word script
    sailed through unexpanded. Costs one extra LLM call (~$0.03) on
    days the first pass lands short; flagship-worthy.
    """
    if expand_below_target:
        return max(600, int(min_words))
    soft_floor = int(min_words * 0.6)
    return max(600, int(soft_floor * 1.1))


def _build_expansion_retry_prompt(
    word_count: int,
    min_words: int,
    digest: str,
    script: str,
    *,
    narrative: bool = False,
    style: str = "",
) -> str:
    """Build the one-shot expansion-retry prompt for a too-short podcast
    script.

    Three flavors. The default (news) retry expands by COVERING MORE
    STORIES from the day's digest — the right move for a daily news show
    that compressed several stories. ``narrative=True`` shows (First
    Principles, Unintended Consequences) have NO news and exactly ONE
    topic per episode, so "cover more stories" is a dead instruction:
    the model has no second story to add and keeps the same length
    (every below-target FP episode stayed thin despite
    ``podcast_expand_below_target``). For those shows the retry instead
    DEEPENS the single topic's reasoning from the full brief — walk the
    arithmetic out, name specifics, address objections — which is also
    exactly what the narrative prompts already ask for on the first pass.

    ``style="deepen"`` (July 18 2026, Omni View realignment): for news
    shows with a FIXED story slate — the prompt already requires covering
    every briefing story, so "cover more stories" would push the model to
    re-add cut minor items or invent an extra story. The deepen flavor
    expands each existing story with more attributed facts from the
    digest instead, never adding stories beyond the slate. Configured
    per show via ``llm.podcast_expansion_style: deepen``.
    """
    if style == "deepen" and not narrative:
        return (
            f"The script you just wrote is only {word_count} words — it "
            f"under-covers the day's briefing. Rewrite it to at least "
            f"{min_words} words by DEEPENING the stories already covered, "
            f"using the complete digest below:\n"
            f"- Pull more facts, numbers, and NAMED-outlet perspectives from "
            f"the digest into each story you compressed — especially the lead "
            f"and world stories\n"
            f"- Do NOT add stories beyond the briefing's slate, and do NOT "
            f"pad with unattributed analysis, 'this highlights' sentences, "
            f"or rephrased framings\n"
            f"- Do NOT invent facts that are not in the digest, and do not "
            f"repeat any sentence verbatim\n"
            f"- Keep the same intro, closing, and overall structure\n\n"
            f"FULL DIGEST (the source of truth for facts):\n\n{digest}\n\n"
            f"Here is your short script to expand:\n\n{script}"
        )
    if narrative:
        return (
            f"The script you just wrote is only {word_count} words — too short for "
            f"a long-form episode. Rewrite it to at least {min_words} words by "
            f"DEEPENING the reasoning already in the brief below — this episode "
            f"covers ONE subject, so go deeper, do NOT invent a second topic:\n"
            f"- For each step in the brief, walk the reasoning out loud: spell the "
            f"arithmetic out number by number, name the specific parts, materials, "
            f"and processes, and address the obvious 'but what about...' objection\n"
            f"- Turn each compressed sentence of the brief into two or three full "
            f"spoken sentences; every worked example should become several minutes "
            f"of audio\n"
            f"- Preserve the brief's hedging — keep every approximate figure "
            f"approximate, using the brief's own hedge words (never introduce "
            f"a stock hedge phrase of your own; vary hedges naturally)\n"
            f"- Do NOT invent facts, numbers, names, or quotes that are not in the "
            f"brief, and do not repeat any sentence verbatim\n"
            f"- Keep the same intro, closing, and overall structure\n\n"
            f"FULL BRIEF (the source of truth for facts):\n\n{digest}\n\n"
            f"Here is your short script to expand:\n\n{script}"
        )
    return (
        f"The script you just wrote is only {word_count} words — it under-covers "
        f"the day's news. Rewrite it to at least {min_words} words by COVERING "
        f"MORE STORIES AT FULL DEPTH, using the complete digest below:\n"
        f"- Find every story in the digest that your script skipped or compressed "
        f"into one or two sentences, and cover it at 5-7 fact-bearing sentences "
        f"(numbers, names, quotes, sources) drawn from the digest\n"
        f"- Keep the stories you already covered well as they are — do NOT pad "
        f"them with extra commentary, implications, or rephrased points\n"
        f"- Do NOT invent facts that are not in the digest, and do not repeat "
        f"any sentence verbatim\n"
        f"- Keep the same intro, closing, and overall structure\n\n"
        f"FULL DIGEST (the source of truth for facts):\n\n{digest}\n\n"
        f"Here is your short script to expand:\n\n{script}"
    )


_EXPANSION_SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?])\s+")


def _dedup_expansion_sentences(
    script: str,
    *,
    threshold: float = 0.85,
    min_words: int = 6,
) -> tuple:
    """Strip near-duplicate sentences from an expansion-retry script.

    July 2026 (network editorial pass): the ``podcast_expand_below_target``
    retry sometimes "expands" by RE-STATING sentences it already wrote —
    M&A Ep087 shipped verbatim doubled sentences in audio ("Sui deployed
    Seal MPC on mainnet…" twice), and MAB Quick Bits ballooned with
    restatements. This intra-script dedup drops any sentence that is a
    near-duplicate (``calculate_similarity`` >= *threshold*) of an EARLIER
    kept sentence in the same script, preserving order and paragraph
    structure. Sentences shorter than *min_words* words are never dropped
    (and never used as dedup anchors) — short rhetorical beats ("Right?",
    "Let's dig in.") are legitimate repeats.

    Returns ``(deduped_script, removed_count)``.
    """
    from engine.utils import calculate_similarity

    if not script:
        return script, 0

    kept_anchors: list = []
    out_lines: list = []
    removed = 0
    for line in script.split("\n"):
        if not line.strip():
            out_lines.append(line)
            continue
        kept_sentences = []
        for sentence in _EXPANSION_SENTENCE_SPLIT_RE.split(line):
            stripped = sentence.strip()
            if len(stripped.split()) >= min_words:
                if any(
                    calculate_similarity(stripped, prev) >= threshold
                    for prev in kept_anchors
                ):
                    removed += 1
                    continue
                kept_anchors.append(stripped)
            kept_sentences.append(sentence)
        if kept_sentences:
            out_lines.append(" ".join(kept_sentences))
        # A line whose every sentence was a duplicate is dropped entirely.
    deduped = "\n".join(out_lines)
    deduped = re.sub(r"\n{3,}", "\n\n", deduped).strip("\n")
    return deduped, removed


def _build_digest_expansion_retry_prompt(
    word_count: int,
    min_words: int,
    draft: str,
    *,
    narrative: bool = False,
) -> str:
    """Build the one-shot expansion-retry prompt for a too-short digest/brief.

    The digest is the substrate the podcast script expands from, so a thin
    brief caps the episode no matter how well the podcast-stage retry works
    (First Principles briefs shipped 848-1116w against a 1600-word prompt
    floor). ``narrative=True`` shows have exactly ONE topic, so the retry
    DEEPENS the existing segments — walk the arithmetic out number by number,
    name the specific parts/materials/processes, address the obvious
    objection — rather than asking for more stories. Opt-in via
    ``llm.digest_expand_below_target``; mirrors
    ``_build_expansion_retry_prompt`` for the podcast stage.
    """
    if narrative:
        return (
            f"\n\n---\n"
            f"The brief you just wrote is only {word_count} words — too thin to "
            f"produce a full long-form episode (a thin brief always makes a thin "
            f"episode). Rewrite it to at least {min_words} words by DEEPENING the "
            f"reasoning already present — this brief covers ONE subject, so go "
            f"deeper, do NOT invent a second topic:\n"
            f"- Keep the exact same structure, segment markers, and HOOK line\n"
            f"- For each segment, walk the reasoning out further: spell the "
            f"arithmetic out number by number, name the specific parts, materials, "
            f"and processes, and address the obvious 'but what about...' objection\n"
            f"- Preserve every hedge exactly as the brief hedges it — keep "
            f"approximate figures approximate, never swap in a stock hedge "
            f"phrase of your own\n"
            f"- Do NOT fabricate statistics, dates, names, or quotes, and do not "
            f"repeat any sentence verbatim — go deeper, never pad with repetition\n\n"
            f"Here is your short brief to expand:\n\n{draft}"
        )
    return (
        f"\n\n---\n"
        f"The digest you just wrote is only {word_count} words — it under-covers "
        f"the day. Rewrite it to at least {min_words} words by developing each "
        f"item to full depth (more fact-bearing sentences: numbers, names, "
        f"sources) without inventing facts or repeating any sentence verbatim. "
        f"Keep the same structure and headline set.\n"
        f"DEPTH RULES (news digests):\n"
        f"- Prefer FEWER items at FULL depth over many thin high-level summaries. "
        f"If an item only has a title + one sentence of source material, either "
        f"drop it or keep it to 2 sentences — do NOT invent filler.\n"
        f"- For every kept item, extract EVERY concrete fact the source text "
        f"actually provides (numbers, names, quotes, dates, mechanisms). "
        f"High-level restatement without those facts is a failure.\n"
        f"- Where the digest has a licensed deep-dive / first-principles / "
        f"essay section, LENGTHEN THAT SECTION first — it is allowed to use "
        f"your own domain knowledge. Do not pad news items with significance "
        f"sentences ('this matters because…').\n"
        f"- If a narrative-memory / tracked-program block was provided, weave "
        f"at most ONE continuity sentence in the whole digest for items that "
        f"touch those programs (prefer the date / 'yesterday'; never write "
        f"'EpN') — continuity is not padding.\n\n"
        f"Here is your short digest to expand:\n\n{draft}"
    )


def _sanitize_podcast_script(text: str, preserve_speaker_labels: bool = False) -> str:
    """Strip known LLM artifacts that break TTS quality.

    ``preserve_speaker_labels=True`` (dialogue-mode shows, e.g. The DP Pod)
    keeps legitimate ``PATRICK:`` / ``DAN:`` turn labels — the speaker-prefix
    strip below would otherwise silently merge every Patrick turn into the
    other host's voice. Generic scaffolding prefixes (``Host:``) are still
    stripped in that mode.

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
    if preserve_speaker_labels:
        # Dialogue-mode shows: real speaker labels (PATRICK:/DAN:) must
        # survive to engine.tts_dialogue; only strip generic scaffolding.
        text_joined = re.sub(
            r"(?im)^\s*(?:host|narrator|speaker)\s*[:：]\s+",
            "",
            text_joined,
        )
    else:
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

    # Fix chronic LLM brand / show-title / grammar slips (TST "Tela",
    # "Tesla Rati", "Short's Time, daily", "do's the news cycle", etc.).
    # This is the belt-and-braces layer after all the prompt defenses.
    text_joined = _correct_common_llm_text_mistakes(text_joined)

    return text_joined


def _correct_common_llm_text_mistakes(text: str) -> str:
    """Fix chronic LLM generation slips on brands, show titles, and set phrases.

    These are defense-in-depth post-processing fixes. The primary defense is
    strong negative examples + verbatim-copy instructions in the per-show
    prompts (especially the Tesla podcast prompt), but the model still
    occasionally emits:

    - "Tela" for "Tesla"
    - "Tesla Rati" / "Tesla Ratie" for "Teslarati"
    - Mangled show title: "Tela Short's Time, daily", "Tesla Short's Time Daily",
      lowercase "daily", wrong capitalization, etc.
    - Grammar slips in the famous framing line: "neither do's the news cycle"

    Historical incidents:
    - TST Ep489 / Ep490 (and earlier runs): the exact phrases the operator
      reported at the top of the episode.
    - Multiple pre-2026-05 transcripts: "Tesla Rati(e)" splits.

    Called at the end of _sanitize_podcast_script (for the spoken script) and
    at the end of generate_digest (so the .md / blog / RSS / newsletter also
    stay clean). Safe to run multiple times; replacements are idempotent.
    """
    import re

    # --- Tesla family brand names (highest priority) ---
    # Standalone "Tela" (the most common hallucination on TST)
    text = re.sub(r"\bTela\b", "Tesla", text)
    # Split/mangled Teslarati (appears in prompts as an example source)
    text = re.sub(r"\bTesla Rati(e)?\b", "Teslarati", text, flags=re.IGNORECASE)

    # --- TST show title and the famous framing line ---
    # The model has a persistent habit of mangling the exact strings that
    # appear in engine/intros.py personality pools and in this prompt.
    # June 20 2026 review: the spoken brand was aligned to "Tesla Shorts
    # Time" (no "Daily") in the June 10 pass — intros.py show_name dropped
    # it and the podcast prompt bans appending it — so the audio brand
    # matches the Apple/Spotify/website listing for search. But this
    # normalizer predates that decision and was still normalizing TOWARD
    # "Tesla Shorts Time Daily": the LLM re-adds "Daily" every episode (a
    # training habit) and this layer blessed it, so "Tesla Shorts Time
    # Daily" shipped in the spoken intro of 100% of episodes (verified
    # Ep506-516, post-June-10). Targets now DROP the stray "Daily" so the
    # deterministic layer enforces the brand decision instead of fighting
    # it. (Mangled-spelling fixes — Tela / Short's — are preserved.)
    replacements = [
        # The classic framing line (one of the framings in intros.py)
        (r"neither do['’]s the news cycle", "neither does the news cycle"),
        (r"Tela never sleeps", "Tesla never sleeps"),
        # All common manglings of the show name the operator has seen, plus
        # the stray "Daily" the LLM keeps appending — normalize to the exact
        # listing brand "Tesla Shorts Time" (drop "Daily"). Permissive on
        # periods, commas, and sentence breaks ("Tesla Short's time. Daily").
        # Misspellings (Tela / Short's) → always corrected, Daily dropped.
        (r"\bTela Short['’]?s? Time(?:[.,;\s]*[Dd]aily)?\b", "Tesla Shorts Time"),
        (r"\bTesla Short['’]s Time(?:[.,;\s]*[Dd]aily)?\b", "Tesla Shorts Time"),
        # Correctly-spelled name carrying a stray "Daily" → drop only the
        # "Daily" (requires Daily to match, so clean "Tesla Shorts Time"
        # and the lowercase handle "tesla shorts time" are left untouched).
        (r"\bTesla Shorts Time[.,;\s]*[Dd]aily\b", "Tesla Shorts Time"),
        (r"welcome to Tela Short['’]?s? Time(?:[.,;\s]*[Dd]aily)?", "welcome to Tesla Shorts Time"),
    ]
    for pattern, repl in replacements:
        text = re.sub(pattern, repl, text, flags=re.IGNORECASE)

    return text


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


def _record_discarded_call(tracker, step: str, meta: dict, config) -> None:
    """Account for a generation call whose output is about to be thrown away.

    The truncation retries below replace ``text``/``meta`` wholesale, so
    the first call's tokens used to vanish — billed by xAI, absent from
    the episode's credit file. That made the waste unmeasurable: the
    July 2026 improvement plan had to infer it from run logs, and named
    the wrong show (SpaceX, which has never truncated in 45 recorded
    runs; the real offenders are Omni View at 17% and Fascinating
    Frontiers at 6%).

    Recorded under its own step key so it shows up as a distinct line in
    the credit summary rather than inflating the successful call.
    """
    if not tracker or "usage" not in (meta or {}):
        return
    try:
        from engine.tracking import record_llm_usage
        usage = meta["usage"]
        record_llm_usage(
            tracker,
            step,
            usage.get("prompt_tokens", 0),
            usage.get("completion_tokens", 0),
            model=config.llm.model,
            cached_tokens=usage.get("cached_tokens", 0),
        )
    except Exception as exc:  # accounting must never break generation
        logger.warning("Failed to record discarded-call usage: %s", exc)


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

    ep_num = int(template_vars.get("episode_num") or 0)
    if ep_num == 1:
        from engine.first_episode import first_episode_digest_appendix
        appendix = first_episode_digest_appendix(
            ep_num, config.name, show_slug=getattr(config, "slug", ""),
        )
        if appendix:
            prompt += "\n\n" + appendix

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
        cache_key=_show_cache_key(config),
        reasoning_effort=_llm_reasoning_effort(config),
    )

    # Retry once with 50% more tokens if the response was truncated
    if meta.get("finish_reason") == "length":
        bumped_tokens = int(config.llm.max_tokens * 1.5)
        logger.warning(
            "Digest truncated at %d tokens — retrying with %d tokens",
            config.llm.max_tokens, bumped_tokens,
        )
        # Record the DISCARDED call before `meta` is overwritten. Until
        # July 2026 only the retry's usage was tracked, so the thrown-away
        # call was invisible in cost data — which is precisely why the
        # improvement plan could not tell which shows were paying for it
        # (it named SpaceX, which turns out never to truncate). Cost that
        # is not recorded cannot be optimised.
        _record_discarded_call(tracker, "x_thread_generation_truncated", meta, config)
        text, meta = _call_grok(
            prompt,
            model=config.llm.model,
            system_prompt=system_prompt,
            temperature=config.llm.digest_temperature,
            max_tokens=bumped_tokens,
            cache_key=_show_cache_key(config),
            reasoning_effort=_llm_reasoning_effort(config),
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
                cached_tokens=meta["usage"].get("cached_tokens", 0),
            )
        except Exception as e:
            logger.warning("Failed to record LLM usage: %s", e)

    logger.info("Digest generated (%d chars, %s tokens)",
                len(text), meta.get("usage", {}).get("total_tokens", "?"))

    # Validate the digest is usable — if the LLM refused, retry up to 2 times
    # with increasingly aggressive overrides before giving up.
    try:
        _rep_count = _validate_llm_output(
            text, stage="digest", show_name=config.name,
            known_entities=tuple(getattr(config, "keywords", ()) or ()),
        )
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
            "switch to EDUCATIONAL mode: pick 2-3 core concepts from this "
            "show's topic domain that are relevant to the audience and "
            "explain them in depth, following the exact same output format. "
            "An educational episode is always better than no episode.\n"
            "Если статьи недостаточно релевантны — переключись на "
            "ОБРАЗОВАТЕЛЬНЫЙ режим: выбери 2-3 ключевые темы из предметной "
            "области этого шоу, важных для аудитории, и объясни их подробно "
            "в том же формате. "
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
            cache_key=_show_cache_key(config),
            reasoning_effort=_llm_reasoning_effort(config),
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
                    cached_tokens=meta2["usage"].get("cached_tokens", 0),
            )
            except Exception as e:
                logger.warning("Failed to record retry LLM usage: %s", e)

        logger.info("Retry 1 digest generated (%d chars, %s tokens)",
                    len(text), meta2.get("usage", {}).get("total_tokens", "?"))

        try:
            _rep_count = _validate_llm_output(
            text, stage="digest", show_name=config.name,
            known_entities=tuple(getattr(config, "keywords", ()) or ()),
        )
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
                cache_key=_show_cache_key(config),
                reasoning_effort=_llm_reasoning_effort(config),
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
                        cached_tokens=meta3["usage"].get("cached_tokens", 0),
            )
                except Exception as e:
                    logger.warning("Failed to record edu retry LLM usage: %s", e)

            logger.info("Retry 2 (educational) digest generated (%d chars, %s tokens)",
                        len(text), meta3.get("usage", {}).get("total_tokens", "?"))
            # Validate — if even the educational fallback refuses, try a
            # different model before giving up.
            try:
                _rep_count = _validate_llm_output(
            text, stage="digest", show_name=config.name,
            known_entities=tuple(getattr(config, "keywords", ()) or ()),
        )
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
                    cache_key=_show_cache_key(config),
                    reasoning_effort=_llm_reasoning_effort(config),
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
                            cached_tokens=meta4["usage"].get("cached_tokens", 0),
                        )
                    except Exception as e:
                        logger.warning("Failed to record fallback model LLM usage: %s", e)
                logger.info(
                    "Retry 3 (fallback model) digest generated (%d chars, %s tokens)",
                    len(text), meta4.get("usage", {}).get("total_tokens", "?"),
                )
                # Validate — if fallback model also refuses, let it propagate
                _rep_count = _validate_llm_output(
            text, stage="digest", show_name=config.name,
            known_entities=tuple(getattr(config, "keywords", ()) or ()),
        )

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
                cache_key=_show_cache_key(config),
                reasoning_effort=_llm_reasoning_effort(config),
            )
            _rep_retry = _validate_llm_output(
                text_retry, stage="digest", show_name=config.name,
                known_entities=tuple(getattr(config, "keywords", ()) or ()),
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

    # One-shot digest-length expansion retry (opt-in via
    # llm.digest_expand_below_target). The brief is the substrate the podcast
    # expands from, so a thin brief caps the episode even when the podcast-
    # stage retry works. Mirrors generate_podcast_script's expansion retry;
    # narrative shows deepen the single topic, news shows develop more depth.
    # Default off (min_digest_words=0) → byte-for-byte no-op for every other
    # show. Skipped when the digest was rescued by an educational fallback
    # (template_vars may not reflect a normal brief).
    if (
        getattr(config.llm, "digest_expand_below_target", False)
        and getattr(config.llm, "min_digest_words", 0) > 0
    ):
        min_digest_words = int(config.llm.min_digest_words)
        word_count = len(text.split())
        if word_count < min_digest_words:
            logger.info(
                "Digest for '%s' is %d words (< %d target) — firing one-shot "
                "expansion retry", config.name, word_count, min_digest_words,
            )
            expansion_prompt = prompt + _build_digest_expansion_retry_prompt(
                word_count,
                min_digest_words,
                text,
                narrative=bool(getattr(config, "narrative_mode", False)),
            )
            try:
                expanded, meta_exp = _call_grok(
                    expansion_prompt,
                    model=config.llm.model,
                    system_prompt=system_prompt,
                    temperature=config.llm.digest_temperature,
                    max_tokens=config.llm.max_tokens,
                    cache_key=_show_cache_key(config),
                    reasoning_effort=_llm_reasoning_effort(config),
                )
                # Validate the expanded draft is real content, not a refusal.
                _validate_llm_output(
                    expanded, stage="digest", show_name=config.name,
                    known_entities=tuple(getattr(config, "keywords", ()) or ()),
                )
                # July 3 2026 (DP Pod Ep001 v4): the DIGEST retry pads by
                # paraphrase-restatement exactly like the podcast retry did
                # (the debut brief re-told every story beat a second time,
                # and the doubled sentences reached shipped audio). Apply
                # the same intra-script near-duplicate stripper the July
                # network pass added on the podcast side.
                expanded, _dig_dup = _dedup_expansion_sentences(expanded)
                if _dig_dup:
                    logger.warning(
                        "Digest expansion retry for '%s' repeated itself — "
                        "stripped %d near-duplicate sentence(s)",
                        config.name, _dig_dup,
                    )
                expanded_wc = len(expanded.split())
                if expanded_wc > word_count:
                    logger.info(
                        "Digest expansion retry improved '%s' (%d -> %d words)",
                        config.name, word_count, expanded_wc,
                    )
                    text = expanded
                    if tracker and "usage" in meta_exp:
                        try:
                            from engine.tracking import record_llm_usage
                            record_llm_usage(
                                tracker,
                                "x_thread_generation_expansion",
                                meta_exp["usage"].get("prompt_tokens", 0),
                                meta_exp["usage"].get("completion_tokens", 0),
                                model=config.llm.model,
                                cached_tokens=meta_exp["usage"].get("cached_tokens", 0),
            )
                        except Exception as e:
                            logger.warning("Failed to record expansion LLM usage: %s", e)
                else:
                    logger.warning(
                        "Digest expansion retry for '%s' did not lengthen "
                        "(%d -> %d words) — keeping original",
                        config.name, word_count, expanded_wc,
                    )
            except (LLMRefusalError, Exception) as exc:
                logger.warning(
                    "Digest expansion retry failed for '%s' (%s) — keeping original",
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

    # Apply the same brand / show-title / grammar corrections that protect
    # the podcast script. This keeps the .md (blog, RSS show notes, newsletter,
    # GitHub Pages, etc.) consistent with the spoken version.
    text = _correct_common_llm_text_mistakes(text)

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
        max_tokens=2500,
        cache_key=_show_cache_key(config),
        reasoning_effort=_llm_reasoning_effort(config),
    )

    # A truncated outline is worse than none: stage 2 is told to "follow
    # this structure and order", so a mid-story cut silently drops every
    # remaining story from the episode. Fall back to un-chained generation
    # (the full digest is still in the podcast prompt).
    if meta.get("finish_reason") == "length":
        logger.warning(
            "Podcast outline for '%s' was truncated at max_tokens — "
            "dropping the outline (script will follow the digest directly)",
            config.name,
        )
        text = ""

    if tracker and "usage" in meta:
        try:
            from engine.tracking import record_llm_usage
            record_llm_usage(
                tracker,
                "podcast_outline_generation",
                meta["usage"].get("prompt_tokens", 0),
                meta["usage"].get("completion_tokens", 0),
                model=config.llm.model,
                cached_tokens=meta["usage"].get("cached_tokens", 0),
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

    ep_num = int(template_vars.get("episode_num") or 0)
    if ep_num == 1:
        from engine.first_episode import first_episode_podcast_appendix
        appendix = first_episode_podcast_appendix(
            ep_num, config.name, show_slug=getattr(config, "slug", ""),
        )
        if appendix:
            prompt += "\n\n" + appendix

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
        if outline:
            # Prepend the outline to the podcast prompt so the model follows it
            prompt = (
                f"STORY OUTLINE (follow this structure and order):\n{outline}\n\n"
                f"---\n\n{prompt}"
            )
            logger.info("Using prompt chaining for '%s' — outline prepended to podcast prompt",
                         config.name)
        else:
            logger.warning(
                "Outline unavailable for '%s' — generating podcast script "
                "without chaining", config.name,
            )

    # Per-stage model override (2026-07-31): the SCRIPT stage may run
    # a different model than the digest/fetch stage. Motivation: newer
    # Grok releases (grok-4.5, 2026-07-08) write better prose but
    # measure WORSE on confident-hallucination benchmarks, so they are
    # a bad trade for the facts-first digest yet a plausible win for
    # turning an already-verified digest into a script. Empty (the
    # default) = config.llm.model, byte-identical behaviour. Setting
    # it changes shipped audio -> per-show A/B (landmine #17).
    script_model = (getattr(config.llm, "podcast_model", "")
                    or config.llm.model)

    logger.info("Generating podcast script for '%s' (model=%s, temp=%.1f) ...",
                config.name, script_model, config.llm.podcast_temperature)

    # Use podcast-specific max_tokens if configured, otherwise fall back to shared max_tokens
    podcast_tokens = getattr(config.llm, "podcast_max_tokens", 0) or config.llm.max_tokens

    def _script_call(model_id: str):
        return _call_grok(
            prompt,
            model=model_id,
            system_prompt=system_prompt,
            temperature=config.llm.podcast_temperature,
            max_tokens=podcast_tokens,
            cache_key=_show_cache_key(config),
            reasoning_effort=_llm_reasoning_effort(config),
        )

    try:
        text, meta = _script_call(script_model)
    except Exception as exc:
        # A per-stage override names a model this account may not be able
        # to reach — a new release the key is not enrolled for, a
        # retired snapshot, a typo in one show's YAML. The override is an
        # experiment; an experiment must not be able to cost a show its
        # episode. Fall back to the configured default and record it, so
        # a silently-unused override shows up as a metric instead of as
        # an A/B result that never actually ran.
        if script_model == config.llm.model:
            raise
        logger.warning(
            "Script-stage model override '%s' failed (%s: %s) — falling back "
            "to '%s' for this episode",
            script_model, type(exc).__name__, exc, config.llm.model,
        )
        print(
            f"::warning::{getattr(config, 'slug', '?')}: script-stage model "
            f"override '{script_model}' unavailable — episode generated on "
            f"'{config.llm.model}'. The A/B is NOT running; fix or remove "
            f"llm.podcast_model.",
            flush=True,
        )
        script_model = config.llm.model
        text, meta = _script_call(script_model)

    # Retry once with 50% more tokens if the response was truncated
    if meta.get("finish_reason") == "length":
        bumped_tokens = int(podcast_tokens * 1.5)
        logger.warning(
            "Podcast script truncated at %d tokens — retrying with %d tokens",
            podcast_tokens, bumped_tokens,
        )
        # See the digest path: the discarded call is recorded so wasted
        # spend is measurable instead of inferred.
        _record_discarded_call(
            tracker, "podcast_script_generation_truncated", meta, config
        )
        text, meta = _call_grok(
            prompt,
            model=script_model,
            system_prompt=system_prompt,
            temperature=config.llm.podcast_temperature,
            max_tokens=bumped_tokens,
            cache_key=_show_cache_key(config),
            reasoning_effort=_llm_reasoning_effort(config),
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
                model=script_model,
                cached_tokens=meta["usage"].get("cached_tokens", 0),
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
                                          min_podcast_words=min_words,
                                          known_entities=tuple(getattr(config, "keywords", ()) or ()))
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
            model=script_model,
            system_prompt=system_prompt,
            temperature=lower_temp,
            max_tokens=podcast_tokens_for_retry,
            cache_key=_show_cache_key(config),
            reasoning_effort=_llm_reasoning_effort(config),
        )
        if tracker and "usage" in meta_r1:
            try:
                from engine.tracking import record_llm_usage
                record_llm_usage(
                    tracker, "podcast_script_refusal_retry",
                    meta_r1["usage"].get("prompt_tokens", 0),
                    meta_r1["usage"].get("completion_tokens", 0),
                    model=script_model,
                    cached_tokens=meta_r1["usage"].get("cached_tokens", 0),
            )
            except Exception:
                pass
        logger.info("Podcast refusal retry 1 generated (%d chars)", len(text))

        try:
            _rep_count = _validate_llm_output(text, stage="podcast_script",
                                              show_name=config.name,
                                              min_podcast_words=min_words,
                                              known_entities=tuple(getattr(config, "keywords", ()) or ()))
        except LLMRefusalError:
            # --- Retry 2: fallback model ---
            fallback_model = _resolve_fallback_model(config)
            if script_model == fallback_model:
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
                cache_key=_show_cache_key(config),
                reasoning_effort=_llm_reasoning_effort(config),
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
                        cached_tokens=meta_r2["usage"].get("cached_tokens", 0),
                    )
                except Exception:
                    pass
            logger.info("Podcast refusal retry 2 (fallback model) generated (%d chars)", len(text))
            # If fallback model also refuses, let it propagate
            _rep_count = _validate_llm_output(text, stage="podcast_script",
                                              show_name=config.name,
                                              min_podcast_words=min_words,
                                              known_entities=tuple(getattr(config, "keywords", ()) or ()))

    # Retry once if the podcast script is below the publication soft floor.
    # run_show.py skips any episode under 60% of the target word count
    # (its _SOFT_FLOOR), so a script in that band is unpublishable anyway —
    # we should always attempt an expansion rather than accept it and let
    # the runner silently skip the episode. The threshold sits ~10% *above*
    # the soft floor because a dedup pass runs between here and the skip
    # check, trimming a few percent off the count (Tesla Ep493 went
    # 874 → 818 and was skipped without ever getting an expansion attempt —
    # it cleared the old 50%/800-word retry bar but fell under the 60%/960
    # soft floor). Expanding here gives the episode a real chance to clear
    # the floor instead of being thrown away.
    word_count = len(text.split())
    _retry_threshold = _podcast_expansion_retry_threshold(
        min_words,
        expand_below_target=bool(
            getattr(config.llm, "podcast_expand_below_target", False)
        ),
    )
    if word_count < _retry_threshold:
        logger.warning(
            "Podcast script for '%s' is very short (%d words, retry threshold %d). "
            "Retrying with expansion instructions ...",
            config.name, word_count, _retry_threshold,
        )
        # June 2026 fix: the retry used to send the model ONLY its own
        # short script — with no digest, the model couldn't add a single
        # fact, so its only lengthening move was the generic "why this
        # matters" padding the main prompt bans (and the listener-value
        # heuristic penalizes). Include the full digest and flip the
        # instruction to FACT-COVERAGE: expand by covering skipped or
        # compressed stories, not by commenting on covered ones.
        _digest_for_retry = template_vars.get("digest", "")
        # June 10 2026 (First Principles review): narrative shows (FP, UC)
        # have NO "day's news" and exactly ONE topic per episode — the
        # news-framed "cover more stories" retry was a dead path for them
        # (every below-target FP script kept its length, so the
        # ``podcast_expand_below_target`` flag did nothing — Ep002 953w,
        # Ep004 935w both stayed thin). For narrative shows the retry
        # instead DEEPENS the single topic's reasoning from the full brief.
        retry_prompt = _build_expansion_retry_prompt(
            word_count, min_words, _digest_for_retry, text,
            narrative=bool(getattr(config, "narrative_mode", False)),
            style=str(getattr(config.llm, "podcast_expansion_style", "") or ""),
        )
        text2, meta2 = _call_grok(
            retry_prompt,
            model=script_model,
            system_prompt=system_prompt,
            temperature=config.llm.podcast_temperature,
            max_tokens=podcast_tokens,
            cache_key=_show_cache_key(config),
            reasoning_effort=_llm_reasoning_effort(config),
        )

        if tracker and "usage" in meta2:
            try:
                from engine.tracking import record_llm_usage
                record_llm_usage(
                    tracker,
                    "podcast_script_retry",
                    meta2["usage"].get("prompt_tokens", 0),
                    meta2["usage"].get("completion_tokens", 0),
                    model=script_model,
                    cached_tokens=meta2["usage"].get("cached_tokens", 0),
            )
            except Exception as e:
                logger.warning("Failed to record retry LLM usage: %s", e)

        # July 2026 (network editorial pass): the retry sometimes pads by
        # re-stating sentences it already wrote (M&A Ep087 shipped verbatim
        # doubled sentences in audio; MAB Quick Bits ballooned with
        # restatements). Strip intra-script near-duplicates from the
        # expanded script BEFORE deciding whether to accept it, and only
        # accept when the deduped expansion is meaningfully (>=5%) longer
        # than the original \u2014 paraphrase padding stripped back to the
        # original length is not an expansion.
        text2, _dup_removed = _dedup_expansion_sentences(text2)
        if _dup_removed:
            logger.warning(
                "Expansion retry for '%s' repeated itself \u2014 stripped %d "
                "near-duplicate sentence(s) from the expanded script",
                config.name, _dup_removed,
            )
        word_count2 = len(text2.split())
        if word_count2 >= int(word_count * 1.05) and word_count2 > word_count:
            logger.info(
                "Retry produced longer script for '%s' (%d \u2192 %d words%s)",
                config.name, word_count, word_count2,
                f", {_dup_removed} duplicate sentence(s) stripped"
                if _dup_removed else "",
            )
            text = text2
            _rep_count = _validate_llm_output(text, stage="podcast_script",
                                              show_name=config.name,
                                              min_podcast_words=min_words,
                                              known_entities=tuple(getattr(config, "keywords", ()) or ()))
        else:
            logger.warning(
                "Retry did not meaningfully improve script length for '%s' "
                "(%d \u2192 %d words after dedup, <5%% gain), keeping original",
                config.name, word_count, word_count2,
            )

    # Publication-floor re-roll (Aug 2026, Tesla Ep564). When the script is
    # STILL inside the skip band after the expansion retry, the episode is
    # about to be thrown away: run_show skips anything under 60% of target.
    # Tesla lost the whole 2026-08-06 slot this way \u2014 954-word first pass,
    # expansion retry reached only 1119 against the 1200 floor \u2014 and the
    # identical 2026-07-31 skip was recovered by a MANUAL workflow rerun
    # that produced a normal 1500-word script from the same news day. A
    # fresh full-prompt regeneration recovers a low-tail sampling draw far
    # more reliably than asking the model to expand its own short draft
    # (the expansion retry's ledger record is ~10 misses to 1 hit). This is
    # NOT the banned podcast-side length lever: the gate is the publication
    # soft floor (+ the same 10% dedup margin the expansion threshold
    # uses), never the word TARGET, so it cannot fire on a merely
    # below-target script \u2014 it only decides between "an episode ships" and
    # "the day is lost". Costs one extra LLM call, only on would-be-skipped
    # days. The longer candidate wins; a shorter or refused re-roll keeps
    # the original (and the runner's skip gate still has the final say).
    _pub_band = max(600, int(int(min_words * 0.6) * 1.1))
    _current_words = len(text.split())
    if _current_words < _pub_band:
        logger.warning(
            "Podcast script for '%s' is still in the publication skip band "
            "(%d words < %d) after the expansion retry \u2014 re-rolling the full "
            "prompt once (fresh generation) to avoid losing the episode ...",
            config.name, _current_words, _pub_band,
        )
        try:
            text_fresh, meta_fresh = _call_grok(
                prompt,
                model=script_model,
                system_prompt=system_prompt,
                temperature=config.llm.podcast_temperature,
                max_tokens=podcast_tokens,
                cache_key=_show_cache_key(config),
                reasoning_effort=_llm_reasoning_effort(config),
            )
            if tracker and "usage" in meta_fresh:
                try:
                    from engine.tracking import record_llm_usage
                    record_llm_usage(
                        tracker,
                        "podcast_script_floor_reroll",
                        meta_fresh["usage"].get("prompt_tokens", 0),
                        meta_fresh["usage"].get("completion_tokens", 0),
                        model=script_model,
                        cached_tokens=meta_fresh["usage"].get("cached_tokens", 0),
                    )
                except Exception as e:
                    logger.warning("Failed to record re-roll LLM usage: %s", e)
            # A fresh draw can still degenerate into self-restatement —
            # strip intra-script near-duplicates before comparing so a
            # doubled script can't "win" on raw length (same guard the
            # expansion retry uses; a clean script loses nothing here).
            text_fresh, _fresh_dups = _dedup_expansion_sentences(text_fresh)
            if _fresh_dups:
                logger.warning(
                    "Publication-floor re-roll for '%s' repeated itself — "
                    "stripped %d near-duplicate sentence(s)",
                    config.name, _fresh_dups,
                )
            fresh_words = len(text_fresh.split())
            if fresh_words > _current_words:
                # Validate BEFORE accepting \u2014 a refusal raises here and the
                # except below keeps the original draft.
                _rep_count = _validate_llm_output(
                    text_fresh, stage="podcast_script", show_name=config.name,
                    min_podcast_words=min_words,
                    known_entities=tuple(getattr(config, "keywords", ()) or ()),
                )
                logger.info(
                    "Publication-floor re-roll recovered '%s' (%d \u2192 %d "
                    "words)", config.name, _current_words, fresh_words,
                )
                text = text_fresh
            else:
                logger.warning(
                    "Publication-floor re-roll for '%s' was no longer than "
                    "the current draft (%d vs %d words) \u2014 keeping original",
                    config.name, fresh_words, _current_words,
                )
        except Exception as exc:
            logger.warning(
                "Publication-floor re-roll failed for '%s' (%s) \u2014 keeping "
                "original draft", config.name, exc,
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
                model=script_model,
                system_prompt=system_prompt,
                temperature=lower_temp,
                max_tokens=podcast_tokens,
                cache_key=_show_cache_key(config),
                reasoning_effort=_llm_reasoning_effort(config),
            )
            _rep_retry = _validate_llm_output(
                text_retry, stage="podcast_script", show_name=config.name,
                min_podcast_words=min_words,
                known_entities=tuple(getattr(config, "keywords", ()) or ()),
            )
            if _rep_retry < _rep_count:
                # See ``_retry_word_count_ok`` for the OV Ep059
                # incident this guard protects against.
                orig_words = len(text.split())
                retry_words = len(text_retry.split())
                show_floor = (
                    getattr(config.llm, "min_podcast_word_floor", 600) or 600
                )
                # Mirror run_show.py's publication soft floor (int(target*0.6))
                # so the retry can't shorten a publishable script below it.
                pub_floor = int(min_words * 0.6)
                if not _retry_word_count_ok(orig_words, retry_words, show_floor,
                                            publication_floor=pub_floor,
                                            target_floor=min_words):
                    logger.warning(
                        "Repetition retry for '%s' has fewer repetitions but "
                        "would drop word count too far (%d → %d, show floor=%d, "
                        "publication floor=%d) — keeping original",
                        config.name, orig_words, retry_words, show_floor,
                        pub_floor,
                    )
                else:
                    logger.info(
                        "Repetition retry improved script for '%s' (%d → %d "
                        "suspicious phrases, %d → %d words)",
                        config.name, _rep_count, _rep_retry,
                        orig_words, retry_words,
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
                    model=script_model,
                    system_prompt=system_prompt,
                    temperature=config.llm.podcast_temperature,
                    max_tokens=podcast_tokens,
                    cache_key=_show_cache_key(config),
                    reasoning_effort=_llm_reasoning_effort(config),
                )
                if tracker and "usage" in meta_rr:
                    try:
                        from engine.tracking import record_llm_usage
                        record_llm_usage(
                            tracker, "podcast_script_anti_repetition_retry",
                            meta_rr["usage"].get("prompt_tokens", 0),
                            meta_rr["usage"].get("completion_tokens", 0),
                            model=script_model,
                            cached_tokens=meta_rr["usage"].get("cached_tokens", 0),
            )
                    except Exception:
                        pass
                reps_rr = detect_phrase_repetition(text_rr)
                critical_rr = [r for r in reps_rr if r["severity"] == "critical"]
                orig_words = len(text.split())
                retry_words = len(text_rr.split())
                show_floor = (
                    getattr(config.llm, "min_podcast_word_floor", 600) or 600
                )
                pub_floor = int(min_words * 0.6)
                # See ``_retry_word_count_ok`` for the OV Ep059 +
                # Tesla Ep500 incidents this guard protects against
                # (anti-rep retry replaced 883-word original with
                # 555-word retry that tripped the 600-word hard floor;
                # publication_floor stops a retry shortening a
                # publishable script below run_show's skip threshold).
                if not critical_rr and _retry_word_count_ok(
                    orig_words, retry_words, show_floor,
                    publication_floor=pub_floor,
                    target_floor=min_words,
                ):
                    logger.info(
                        "Anti-repetition retry cleared critical loops for '%s' "
                        "(%d → %d words)",
                        config.name, orig_words, retry_words,
                    )
                    text = text_rr
                elif not critical_rr:
                    logger.warning(
                        "Anti-repetition retry for '%s' cleared loops but "
                        "dropped word count too far (%d → %d, show floor=%d) — "
                        "keeping original to avoid hard-floor abort downstream",
                        config.name, orig_words, retry_words, show_floor,
                    )
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

    text = _sanitize_podcast_script(
        text,
        preserve_speaker_labels=getattr(
            getattr(config, "tts", None), "dialogue_mode", False,
        ),
    )
    return text
