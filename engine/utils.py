"""Shared utility functions for the podcast generation pipeline.

Extracted from the 4 show runner scripts to eliminate duplication.
Canonical versions chosen for robustness:
  - env_float/int/bool: from planetterrian.py (handles None, strips whitespace)
  - number_to_words: identical across all 4 scripts
  - calculate_similarity / remove_similar_items: identical across TST/FF/PT
  - norm_headline_for_similarity / filter_articles_by_recent_stories: from TST
"""

import datetime
import logging
import os
import re
from difflib import SequenceMatcher

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Environment variable helpers
# ---------------------------------------------------------------------------

def env_float(name: str, default: float) -> float:
    """Read an env var as a float, returning *default* on missing/invalid."""
    raw = os.getenv(name)
    if raw is None or not str(raw).strip():
        return default
    try:
        return float(str(raw).strip())
    except ValueError:
        logger.warning("Invalid %s='%s' (expected float). Using default %s.", name, raw, default)
        return default


def env_int(name: str, default: int) -> int:
    """Read an env var as an int, returning *default* on missing/invalid."""
    raw = os.getenv(name)
    if raw is None or not str(raw).strip():
        return default
    try:
        return int(str(raw).strip())
    except ValueError:
        logger.warning("Invalid %s='%s' (expected int). Using default %s.", name, raw, default)
        return default


def env_bool(name: str, default: bool) -> bool:
    """Read an env var as a bool, returning *default* on missing/invalid."""
    raw = os.getenv(name)
    if raw is None:
        return default
    v = str(raw).strip().lower()
    if v in {"1", "true", "t", "yes", "y", "on"}:
        return True
    if v in {"0", "false", "f", "no", "n", "off"}:
        return False
    return default


# ---------------------------------------------------------------------------
# Number-to-words converter (for TTS pronunciation)
# ---------------------------------------------------------------------------

def number_to_words(num: float) -> str:
    """Convert numbers to words for better TTS pronunciation.

    Handles integers up to 999,999 and decimals.  Numbers >= 1,000,000
    are returned as their string representation (TTS usually handles those).
    """
    digit_names = [
        "zero", "one", "two", "three", "four",
        "five", "six", "seven", "eight", "nine",
    ]

    def _convert_under_1000(n: int) -> str:
        ones = [
            "", "one", "two", "three", "four", "five", "six", "seven",
            "eight", "nine", "ten", "eleven", "twelve", "thirteen",
            "fourteen", "fifteen", "sixteen", "seventeen", "eighteen",
            "nineteen",
        ]
        tens = [
            "", "", "twenty", "thirty", "forty", "fifty",
            "sixty", "seventy", "eighty", "ninety",
        ]
        if n == 0:
            return "zero"
        if n < 20:
            return ones[n]
        if n < 100:
            return tens[n // 10] + ("-" + ones[n % 10] if n % 10 else "")
        if n < 1000:
            result = ones[n // 100] + " hundred"
            remainder = n % 100
            if remainder:
                result += " " + _convert_under_1000(remainder)
            return result
        return str(n)

    is_negative = num < 0
    num = abs(num)

    # Use string-based decimal extraction to avoid floating-point precision
    # artifacts (e.g. 1.43 → 1.4299999999... → "four two nine nine...").
    _num_str = f"{num:.10f}".rstrip("0").rstrip(".")
    integer_part = int(num)
    if "." in _num_str:
        _dec_str = _num_str.split(".")[1]
        # Limit to 2 significant decimal digits for speech clarity
        _dec_str = _dec_str[:2].rstrip("0")
        decimal_part = float(f"0.{_dec_str}") if _dec_str else 0.0
    else:
        decimal_part = 0.0

    # Integer portion
    if integer_part == 0:
        result = "zero"
    elif integer_part < 1000:
        result = _convert_under_1000(integer_part)
    elif integer_part < 1_000_000:
        thousands = integer_part // 1000
        remainder = integer_part % 1000
        result = _convert_under_1000(thousands) + " thousand"
        if remainder:
            result += " " + _convert_under_1000(remainder)
    else:
        result = str(integer_part)

    # Decimal portion — round to 2 decimal places to prevent floating-point
    # precision artifacts (e.g. 1.4299999999 from 1.43)
    if decimal_part > 0:
        decimal_part = round(decimal_part, 2)
        decimal_str = f"{decimal_part:.10f}".rstrip("0").rstrip(".")
        if "." in decimal_str:
            decimal_digits = decimal_str.split(".")[1]
            decimal_words = " ".join(
                digit_names[int(d)] if d.isdigit() and int(d) < 10 else d
                for d in decimal_digits
            )
            result += " point " + decimal_words

    return ("negative " if is_negative else "") + result


# ---------------------------------------------------------------------------
# Text similarity helpers
# ---------------------------------------------------------------------------

def calculate_similarity(text1: str, text2: str) -> float:
    """Calculate similarity ratio between two texts (0.0 to 1.0)."""
    if not text1 or not text2:
        return 0.0
    text1_norm = " ".join(text1.lower().split())
    text2_norm = " ".join(text2.lower().split())
    return SequenceMatcher(None, text1_norm, text2_norm).ratio()


def remove_similar_items(items, similarity_threshold=0.7, get_text_func=None):
    """Remove similar items from a list based on text similarity.

    Args:
        items: List of items to filter.
        similarity_threshold: Ratio above which items are considered duplicates.
        get_text_func: Callable to extract comparison text from an item.
            Defaults to looking for 'title', 'text', or 'description' keys.

    Returns:
        Filtered list with duplicates removed (first occurrence kept).
    """
    if not items:
        return items

    if get_text_func is None:
        def get_text_func(item):
            if isinstance(item, dict):
                return (
                    item.get("title", "")
                    or item.get("text", "")
                    or item.get("content", "")
                    or item.get("description", "")
                )
            return str(item)

    filtered = []
    for item in items:
        item_text = get_text_func(item)
        if not item_text:
            continue

        is_similar = False
        for accepted_item in filtered:
            accepted_text = get_text_func(accepted_item)
            similarity = calculate_similarity(item_text, accepted_text)
            if similarity >= similarity_threshold:
                is_similar = True
                logger.debug(
                    "Filtered similar item (similarity: %.2f): %s...",
                    similarity,
                    item_text[:50],
                )
                break

        if not is_similar:
            filtered.append(item)

    return filtered


def norm_headline_for_similarity(text: str) -> str:
    """Normalize headline for similarity comparison.

    Strips trailing date patterns, source labels, and extra whitespace so
    that cross-day deduplication compares only the meaningful portion.
    """
    if not text:
        return ""
    # Remove "DD Month, YYYY, HH:MM AM/PM TZ, Source" suffixes
    t = re.sub(
        r"\d{1,2}\s+(?:January|February|March|April|May|June|July|August|"
        r"September|October|November|December)[a-z]*\s*,?\s*\d{4}[^*]*$",
        "",
        text,
        flags=re.IGNORECASE,
    )
    # Remove "DD/MM/YYYY …" suffixes
    t = re.sub(r"\d{1,2}/\d{1,2}/\d{2,4}[^*]*$", "", t)
    t = " ".join(t.lower().split())
    return t.strip()


def filter_articles_by_recent_stories(
    articles: list,
    recent_headlines: list,
    similarity_threshold: float = 0.72,
) -> list:
    """Drop articles whose title is too similar to a recently covered story.

    Used for cross-day deduplication so the same headline doesn't appear in
    consecutive episodes.
    """
    if not recent_headlines or not articles:
        return articles
    filtered = []
    recent_norm = [norm_headline_for_similarity(h) for h in recent_headlines if h]
    for article in articles:
        title = (article.get("title") or "").strip()
        if not title:
            filtered.append(article)
            continue
        norm_title = norm_headline_for_similarity(title)
        is_covered = False
        for r in recent_norm:
            if not r:
                continue
            if calculate_similarity(norm_title, r) >= similarity_threshold:
                is_covered = True
                logger.debug(
                    "Skipping already-covered story (similar to recent): %s...",
                    title[:60],
                )
                break
        if not is_covered:
            filtered.append(article)
    dropped = len(articles) - len(filtered)
    if dropped:
        logger.info(
            "Filtered %d articles that were too similar to recently covered stories",
            dropped,
        )
    return filtered


# ---------------------------------------------------------------------------
# Entity-level deduplication
# ---------------------------------------------------------------------------

def extract_primary_entity(title: str, description: str = "") -> str:
    """Extract the primary subject/entity from a headline.

    Uses simple NLP heuristics to find the most likely subject:
    1. Multi-word capitalised phrases (2-4 words: "SpaceX Starship", "Crew Dragon")
    2. Known pattern compounds ("SpaceX launches Starship" → "SpaceX Starship")
    3. Acronyms / uppercase tokens ("USSF-87", "NASA")
    4. Fallback: first significant capitalised word (skip common title-case words)
    """
    if not title:
        return ""

    # Common words that appear capitalised in headlines but aren't entities
    _STOP_WORDS = {
        "The", "New", "How", "Why", "What", "When", "Where", "Who",
        "First", "Top", "Big", "Major", "Latest", "Breaking", "Just",
        "After", "Before", "More", "Most", "Some", "All", "Every",
        "Could", "Would", "Should", "Will", "May", "Can", "Says",
        "Report", "Study", "Research", "Update", "News", "Daily",
    }

    # Remove source labels and dates at the end
    clean = re.sub(r"\d{1,2}\s+\w+\s+\d{4}.*$", "", title).strip()

    # Find capitalised runs of 1-4 words (proper nouns / named entities)
    runs = re.findall(r"(?:[A-Z][a-zA-Z]+(?:[-\s][A-Z][a-zA-Z]+){0,3})", clean)

    # Filter out runs that are entirely stop words
    filtered_runs = []
    for r in runs:
        words = r.split()
        non_stop = [w for w in words if w not in _STOP_WORDS]
        if non_stop:
            filtered_runs.append(" ".join(non_stop))

    if not filtered_runs:
        # Fallback: try uppercase segments (acronyms like "USSF-87")
        filtered_runs = re.findall(r"[A-Z][A-Z0-9-]{2,}", clean)

    if not filtered_runs:
        return clean[:40]

    # Prefer runs of 2+ words for specificity; fall back to longest single-word run
    multi_word = [r for r in filtered_runs if " " in r or "-" in r]
    if multi_word:
        return multi_word[0]

    # Return the longest single-word entity (more likely to be specific)
    return max(filtered_runs, key=len)


def drop_excluded_titles(articles: list, patterns: list) -> tuple:
    """Drop articles whose title matches any of *patterns*.

    *patterns* are case-insensitive regular expressions. Returns
    ``(kept_articles, dropped_count)``.

    Purpose: suppress recurring almanac / evergreen content that feeds
    republish across episodes and that isn't news — e.g. Fascinating
    Frontiers kept shipping "Full Moon Calendar Lists All 2026 Dates",
    "Venus Jupiter Mercury Shine in June Evening Skies", and
    "Lick Observatory Ownership Transfers on June 1 1888" (caught as
    100%-identical cross-episode repeats but shipped anyway because the
    repeat check is non-blocking). Filtering at fetch time stops them
    reaching the digest. Configured per-show via ``exclude_title_patterns``.
    """
    if not patterns or not articles:
        return articles, 0
    import re
    compiled = []
    for p in patterns:
        try:
            compiled.append(re.compile(p, re.IGNORECASE))
        except re.error as exc:
            logger.warning("Invalid exclude_title_pattern %r: %s", p, exc)
    if not compiled:
        return articles, 0
    kept = []
    dropped = 0
    for art in articles:
        title = art.get("title") or ""
        if any(c.search(title) for c in compiled):
            dropped += 1
            logger.debug("Excluded almanac/evergreen title: %s", title[:80])
            continue
        kept.append(art)
    return kept, dropped


def deduplicate_by_entity(
    articles: list,
    max_per_entity: int = 2,
    entity_similarity_threshold: float = 0.70,
) -> list:
    """Limit articles to max_per_entity per primary entity.

    If 6 articles all cover "Crew-12", only the 2 most distinct survive.
    Also deduplicates by URL.
    """
    if not articles:
        return articles

    # URL dedup first
    seen_urls: set = set()
    url_deduped = []
    for article in articles:
        url = (article.get("url") or article.get("link") or "").strip()
        if url and url in seen_urls:
            logger.debug("Dropping duplicate URL: %s", url[:60])
            continue
        if url:
            seen_urls.add(url)
        url_deduped.append(article)

    # Entity-level dedup
    entity_counts: dict = {}
    filtered = []
    for article in url_deduped:
        title = article.get("title", "")
        desc = article.get("description", "")
        entity = extract_primary_entity(title, desc)
        if not entity:
            filtered.append(article)
            continue

        # Check against existing entities
        matched_entity = None
        for existing_entity in entity_counts:
            if calculate_similarity(entity.lower(), existing_entity.lower()) >= entity_similarity_threshold:
                matched_entity = existing_entity
                break

        if matched_entity:
            if entity_counts[matched_entity] < max_per_entity:
                entity_counts[matched_entity] += 1
                filtered.append(article)
            else:
                logger.debug(
                    "Capping entity '%s' (already %d articles): %s",
                    matched_entity, entity_counts[matched_entity], title[:60],
                )
        else:
            entity_counts[entity] = 1
            filtered.append(article)

    dropped = len(url_deduped) - len(filtered)
    if dropped:
        logger.info(
            "Entity-level dedup removed %d articles (max %d per entity)",
            dropped, max_per_entity,
        )
    return filtered


# ---------------------------------------------------------------------------
# Weekend / low-news detection
# ---------------------------------------------------------------------------

def is_low_news_day() -> bool:
    """Check if today is likely a low-news day (weekend or major holiday)."""
    today = datetime.date.today()
    # Weekend
    if today.weekday() >= 5:
        return True
    # Major US/Canadian holidays (approximate)
    month_day = (today.month, today.day)
    major_holidays = {
        (1, 1),   # New Year's Day
        (7, 1),   # Canada Day
        (7, 4),   # US Independence Day
        (12, 25), # Christmas
        (12, 26), # Boxing Day
    }
    return month_day in major_holidays


def adaptive_cutoff_hours(articles: list, base_hours: int = 24) -> int:
    """Expand the cutoff window if too few articles were found.

    Returns the final cutoff_hours that yielded enough articles, or 72 max.
    """
    if len(articles) >= 5:
        return base_hours
    if base_hours < 48:
        return 48
    if base_hours < 72:
        return 72
    return base_hours


# ---------------------------------------------------------------------------
# Science / content keyword filtering
# ---------------------------------------------------------------------------

SCIENCE_CONTENT_KEYWORDS = [
    "longevity", "anti-aging", "aging", "lifespan", "healthspan",
    "biotechnology", "genetics", "genomics", "CRISPR", "gene therapy",
    "medicine", "medical", "health", "wellness", "nutrition", "diet",
    "research", "study", "clinical trial", "discovery", "breakthrough",
    "science", "scientific", "biotech",
    "cancer", "disease", "treatment", "therapy", "vaccine",
    "brain", "neuroscience", "cognitive", "mental health",
]


def is_science_related(text: str) -> bool:
    """Check if post text contains science/longevity/health keywords."""
    if not text:
        return False

    text_lower = text.lower()
    for keyword in SCIENCE_CONTENT_KEYWORDS:
        if keyword.lower() in text_lower:
            return True

    return False


# ---------------------------------------------------------------------------
# X / Twitter character-limit enforcement
# ---------------------------------------------------------------------------

def enforce_x_char_limit(text: str, max_chars: int = 280) -> str:
    """Ensure text fits within X's 280-char limit (non-subscribed accounts).

    If too long, progressively compress, then truncate with an ellipsis.
    """
    t = (text or "").strip()
    if len(t) <= max_chars:
        return t

    # Collapse excessive blank lines / whitespace first
    t = re.sub(r"[ \t]+\n", "\n", t)
    t = re.sub(r"\n{3,}", "\n\n", t).strip()
    if len(t) <= max_chars:
        return t

    # If still too long, truncate safely
    suffix = "\u2026"
    if max_chars <= len(suffix):
        return suffix[:max_chars]
    return t[: max_chars - len(suffix)].rstrip() + suffix


# ---------------------------------------------------------------------------
# HTTP constants
# ---------------------------------------------------------------------------

# Use a real browser User-Agent. The previous bot UA
# ("PodcastBot/1.0 …") was silently blocked or served empty/challenge
# pages by Cloudflare-fronted publishers (TechCrunch, MIT Tech Review,
# Wired, The Verge, Ars Technica, Reddit), which returned HTTP 200 with
# zero entries — counted as "0 articles, 0 failed" and invisible in the
# logs. A browser UA + Accept header restores those feeds. (May 2026
# MAB sourcing audit — the show had silently collapsed onto Reddit +
# The Decoder because the high-signal AI feeds were all returning 0.)
DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "application/rss+xml, application/atom+xml, application/xml, text/xml, text/html;q=0.9, */*;q=0.8",
}
HTTP_TIMEOUT_SECONDS = 10


# ---------------------------------------------------------------------------
# Speech tag stripping (Grok TTS)
# ---------------------------------------------------------------------------

# Inline tags used by Grok TTS: bracketed single-token directives that
# instruct the speech model to insert non-verbal audio (breath, pause, etc.)
# at that point in the stream. Listed verbatim from the Grok TTS docs:
# https://docs.x.ai/developers/model-capabilities/audio/text-to-speech
_INLINE_SPEECH_TAGS = (
    "pause", "long-pause", "laugh", "cry",
    "sniff", "kiss", "throat-clear",
    "breath", "sigh", "gasp",
)
_INLINE_TAG_PATTERN = re.compile(
    r"\[\s*(?:" + "|".join(re.escape(t) for t in _INLINE_SPEECH_TAGS) + r")\s*\]",
    flags=re.IGNORECASE,
)

# Wrapping tags surround a span of text and modify its delivery (whisper,
# emphasis, etc.). The Grok backend interprets and consumes them; we strip
# them for any non-TTS consumer (blog markdown, RSS show notes, X teaser).
#
# ``build-intensity`` is NOT in Grok's documented tag list — kept here
# only as a defensive scrubber in case it sneaks back into a script.
# (It was briefly part of the network's chunk-send wrap in May 2026
# until Whisper caught Grok speaking "build intensity" out loud — see
# the history block in ``shows/_defaults.yaml`` and landmine #17.)
_WRAPPING_TAGS = (
    "soft", "loud", "whisper",
    "slow", "fast", "high", "low",
    "singing", "emphasis",
    "build-intensity",
)
_WRAPPING_TAG_PATTERN = re.compile(
    r"</?\s*(?:" + "|".join(re.escape(t) for t in _WRAPPING_TAGS) + r")\s*>",
    flags=re.IGNORECASE,
)


def strip_speech_tags(text: str) -> str:
    """Remove Grok TTS speech tags from text.

    Strips inline tags (``[breath]``, ``[pause]``, ``[long-pause]``,
    ``[laugh]``, etc.) and the open/close pair of every wrapping tag
    (``<emphasis>...</emphasis>``, ``<whisper>...</whisper>``, etc. —
    only the brackets are removed; the wrapped text content is preserved
    so the digest reads as written prose).

    Apply at every non-TTS consumer of the podcast script: blog markdown,
    RSS show notes, X teaser, transcript fallback when Whisper isn't
    available, chapter section detection, etc. The TTS path itself
    deliberately keeps the tags so the Grok backend can consume them.

    Idempotent: stripping an already-stripped string is a no-op.
    """
    if not text:
        return text
    out = _INLINE_TAG_PATTERN.sub("", text)
    out = _WRAPPING_TAG_PATTERN.sub("", out)
    # Collapse any double spaces left behind by removed inline tags
    # (e.g. ``"sentence one. [breath] sentence two."`` → two spaces between
    # the period and "sentence two.").
    out = re.sub(r"  +", " ", out)
    # Tighten "tag-eats-newline" cases like ``"... line.\n[breath]\nNext line ..."``
    # which leave a stray double-newline-with-space artifact.
    out = re.sub(r"\n[ \t]+\n", "\n\n", out)
    return out


# ---------------------------------------------------------------------------
# Lone-surrogate scrubbing
# ---------------------------------------------------------------------------
#
# Operator caught (UC + Tesla blog generation, May 7 2026) the daily site
# rebuild aborting with ``UnicodeEncodeError: surrogates not allowed``
# inside ``Path.write_text(encoding="utf-8")``. An LLM-rendered string
# carried a lone UTF-16 surrogate code point (U+D800–U+DFFF), the UTF-8
# encoder refuses them, and a single bad code point then aborted the
# entire blog regeneration — losing every other show's blog post in the
# same run.
#
# The scrubber is the same regex used at every HTML/XML write boundary
# in ``generate_html.py``. Promoted here from that module so every
# component that writes LLM-touched text to disk (digest .md, TTS
# script, blog post HTML, blog RSS feeds) can scrub at the boundary.
_LONE_SURROGATE_RE = re.compile(r"[\ud800-\udfff]")


def strip_lone_surrogates(text: str) -> str:
    """Remove unpaired UTF-16 surrogate code points (U+D800–U+DFFF).

    Properly paired emoji are unaffected — they're a single non-BMP
    code point in Python strings, not two separate surrogates.
    """
    return _LONE_SURROGATE_RE.sub("", text)


# Known phonetic garbles the LLM occasionally writes into scripts despite
# the prompts' pronunciation-guide ban ("nassa" shipped in FF Ep096's
# published transcript; "chwen"/"en-vidia" flagged by the daily audit).
# The TTS mostly pronounces these acceptably, but blog readers and the
# RSS transcript see the garble verbatim. Deterministic restoration is
# safe: these tokens have no legitimate English use (deliberately NO
# space-separated variants like "star mer" — "star merger" collides).
_PHONETIC_GARBLES = {
    "nassa": "NASA",
    "nay-toe": "NATO",
    "chwen": "Qwen",
    "en-vidia": "Nvidia",
    "open-ay-eye": "OpenAI",
    "star-mer": "Starmer",
    # Fascinating Frontiers (June 12 2026 review): the podcast-gen step
    # spelled hard space names phonetically despite the prompt ban — these
    # shipped to TTS as written. "En-sell-uh-dus" → Enceladus (FF Ep048/088/094),
    # "Tee-en-wen" → Tianwen (FF Ep090, e.g. "Tee-en-wen-2"; the regex's
    # trailing \b leaves the "-2" suffix intact → "Tianwen-2").
    "en-sell-uh-dus": "Enceladus",
    "tee-en-wen": "Tianwen",
    # Models & Agents (June 14 2026 review): the podcast-gen step spelled
    # core AI proper nouns phonetically despite the prompt ban — these
    # shipped to TTS *and* into chapter titles (parse_chapters runs after
    # this repair). "An-thropic" alone appeared in nearly every episode
    # (6× in Ep080); the hyphen forces an audible break on the custom
    # voice. The trailing \b leaves possessives/compounds intact:
    # "An-thropic's" → "Anthropic's", "An-thropic-style" → "Anthropic-style",
    # "Lah-mah-swap" → "Llama-swap", "Lah-mah-cpp" → "Llama-cpp".
    "an-thropic": "Anthropic",
    "lah-mah": "Llama",
    "hah-sah-biss": "Hassabis",
    # Tesla Shorts Time (June 20 2026 review): the podcast-gen step spells
    # the show's most-attributed source phonetically as "Tesla-rah-tee"
    # (Teslarati) despite the prompt ban — it shipped to TTS in 25+
    # episodes, including 5 of the last 10 (Ep500/505/512/516), often
    # several times per episode. Whisper of Ep516 audio confirms it voices
    # as a garble ("Tesla had RadT reported"); the hyphens force an audible
    # break on the custom voice. The trailing \b leaves possessives intact
    # ("Tesla-rah-tee's" → "Teslarati's"). Note: only the hyphenated
    # respelling is restored — the correct "Teslarati" never matches.
    "tesla-rah-tee": "Teslarati",
}

_PHONETIC_GARBLE_RE = re.compile(
    r"\b(" + "|".join(re.escape(k) for k in _PHONETIC_GARBLES) + r")\b",
    re.IGNORECASE,
)


def fix_phonetic_garbles(text: str) -> str:
    """Restore canonical spellings for known LLM phonetic garbles.

    Applied to digests and podcast scripts before they reach TTS, the
    blog transcript, and RSS. Detection (loud audit flag) stays in
    review_episodes.py; this is the repair layer.
    """
    if not text:
        return text
    return _PHONETIC_GARBLE_RE.sub(
        lambda m: _PHONETIC_GARBLES[m.group(1).lower()], text,
    )
