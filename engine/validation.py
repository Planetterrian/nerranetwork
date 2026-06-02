"""Post-generation digest validation for the podcast pipeline.

Catches within-episode problems (section overlap, missing sections, forbidden
content, story count shortfalls) before the digest is sent to TTS.

Usage:
    from engine.validation import validate_digest, ValidationConfig, SectionRule

    config = ValidationConfig(
        section_pairs=[("Top 10", "Takeover")],
        sections=[SectionRule("Top 10", min_items=6)],
        forbidden_patterns=[r"\\$\\d+\\.\\d+\\s*[+\\-]"],
    )
    passed, issues, exact_dups = validate_digest(digest_text, config)
"""

import logging
import re
from collections import Counter
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from engine.utils import calculate_similarity


# Common English phrases that naturally repeat in podcast scripts and
# should never be flagged as repetition loops.
_REPETITION_ALLOWLIST = {
    # Articles / prepositions
    "in the", "of the", "and the", "for the", "on the", "at the",
    "to the", "is the", "is a", "this is", "it is", "that is",
    "one of the", "some of the", "a lot of",
    "going to", "want to", "have to", "need to",
    "according to", "out of", "over the", "from the",
    "in this", "with the", "by the", "that the", "as the",
    # Host attribution (Patrick/host script lines)
    "patrick the", "patrick this", "patrick it", "patrick a",
    "patrick so", "patrick now", "patrick and", "patrick but",
    # Podcast-common phrases
    "this week", "last week", "this year", "last year",
    "this morning", "right now", "let's talk",
    # Language-learning pedagogical phrases (Privet Russian, etc.)
    # These SHOULD repeat in educational content — they're teaching tools.
    "repeat after me", "it sounds like", "that means i",
    "sounds like the", "in russian we", "in russian the",
    "the russian word", "say it with", "try saying it",
    "let's practice", "one more time", "memory hook sounds",
    "hook sounds like", "now let's try",
}


def detect_phrase_repetition(
    text: str,
    *,
    min_phrase_words: int = 3,
    max_phrase_words: int = 6,
    max_allowed_repeats: int = 3,
) -> List[Dict[str, Any]]:
    """Detect phrases repeated excessively in generated text.

    Uses a sliding n-gram window (``min_phrase_words``..``max_phrase_words``)
    and flags any n-gram whose occurrence count exceeds ``max_allowed_repeats``.
    Common English phrases from ``_REPETITION_ALLOWLIST`` are filtered out so
    they never trigger.

    Returns a list of ``{phrase, count, severity}`` dicts sorted by count
    descending.  Severity is ``"critical"`` for 6+ occurrences, ``"warning"``
    for 4-5.  Returns an empty list when nothing exceeds the threshold.
    """
    if not text or not text.strip():
        return []

    # Tokenize: lowercase, strip punctuation, drop empties.
    tokens = [
        re.sub(r"[^\w']+", "", w).lower()
        for w in text.split()
    ]
    tokens = [t for t in tokens if t]
    if len(tokens) < min_phrase_words:
        return []

    # Aggregate n-gram counts across the requested window sizes.
    ngram_counts: Counter = Counter()
    for n in range(min_phrase_words, max_phrase_words + 1):
        if len(tokens) < n:
            break
        for i in range(len(tokens) - n + 1):
            phrase = " ".join(tokens[i : i + n])
            ngram_counts[phrase] += 1

    violations: List[Dict[str, Any]] = []
    seen_phrases: set = set()
    for phrase, count in ngram_counts.most_common():
        if count <= max_allowed_repeats:
            break  # ordered descending — nothing more to find
        if phrase in _REPETITION_ALLOWLIST:
            continue
        # Skip phrases where all tokens are stopword-length (<=3 chars)
        if all(len(t) <= 3 for t in phrase.split()):
            continue
        # Skip phrases contained within an already-reported longer phrase.
        # This prevents a repeated 6-gram from also surfacing as its shorter
        # substrings (same underlying repetition, reported once).
        if any(phrase in longer for longer in seen_phrases):
            continue
        seen_phrases.add(phrase)
        severity = "critical" if count >= 6 else "warning"
        violations.append({
            "phrase": phrase,
            "count": count,
            "severity": severity,
        })

    violations.sort(key=lambda v: v["count"], reverse=True)
    return violations

logger = logging.getLogger(__name__)


@dataclass
class SectionRule:
    """Validation rule for a named section."""
    name: str
    # Regex to locate the section in the digest
    pattern: str = ""
    min_items: int = 0
    max_items: int = 0  # 0 = no max
    # Minimum prose length (chars) for PROSE sections that have no list
    # items (e.g. MAB's "The Big Story" is 8-12 sentences, not bullets).
    # Counting ``**bold**`` items there always returns 0 and falsely trips
    # the structural-retry. 0 = disabled (item-count validation only).
    min_chars: int = 0
    # If True, section is optional (don't flag if missing)
    optional: bool = False


@dataclass
class ValidationConfig:
    """Per-show validation configuration."""
    # Pairs of section names that must not overlap
    section_pairs: List[Tuple[str, str]] = field(default_factory=list)
    # Section rules (count validation)
    sections: List[SectionRule] = field(default_factory=list)
    # Regex patterns that must NOT appear in the podcast script
    forbidden_patterns: List[str] = field(default_factory=list)
    # Overlap similarity threshold for section pairs
    overlap_threshold: float = 0.50
    # Cross-episode similarity threshold
    cross_episode_threshold: float = 0.65


def _extract_items_from_section(text: str, pattern: str) -> List[str]:
    """Extract numbered or bold items from a section matching the pattern."""
    m = re.search(pattern, text, re.DOTALL | re.IGNORECASE)
    if not m:
        return []
    section_text = m.group(1) if m.lastindex else m.group(0)
    # Extract bold headlines as items
    items = []
    for item_match in re.finditer(r"\*{2}([^*]{10,})\*{2}", section_text):
        items.append(item_match.group(1).strip())
    return items


def _extract_section_text(text: str, pattern: str) -> str:
    """Extract raw text of a section."""
    m = re.search(pattern, text, re.DOTALL | re.IGNORECASE)
    if not m:
        return ""
    return (m.group(1) if m.lastindex else m.group(0)).strip()


def check_section_overlap(
    digest_text: str,
    section_pairs: List[Tuple[str, str]],
    section_patterns: Dict[str, str],
    threshold: float = 0.50,
) -> List[str]:
    """Check if any section pair has overlapping stories.

    Returns list of overlap descriptions (empty = no overlaps).
    """
    overlaps = []
    for sec_a_name, sec_b_name in section_pairs:
        pat_a = section_patterns.get(sec_a_name, "")
        pat_b = section_patterns.get(sec_b_name, "")
        if not pat_a or not pat_b:
            continue

        items_a = _extract_items_from_section(digest_text, pat_a)
        items_b = _extract_items_from_section(digest_text, pat_b)

        for a_item in items_a:
            for b_item in items_b:
                sim = calculate_similarity(a_item, b_item)
                if sim >= threshold:
                    overlaps.append(
                        f"'{sec_a_name}' and '{sec_b_name}' share similar story "
                        f"(similarity {sim:.0%}): '{a_item[:60]}...' vs '{b_item[:60]}...'"
                    )
    return overlaps


def check_item_counts(
    digest_text: str,
    sections: List[SectionRule],
) -> List[str]:
    """Verify each section has the expected number of items."""
    issues = []
    for section in sections:
        if not section.pattern:
            continue

        items = _extract_items_from_section(digest_text, section.pattern)

        # Check if section exists at all
        m = re.search(section.pattern, digest_text, re.DOTALL | re.IGNORECASE)
        if not m:
            if not section.optional:
                issues.append(f"Section '{section.name}' is missing from digest")
            continue

        count = len(items)
        if section.min_items and count < section.min_items:
            issues.append(
                f"Section '{section.name}': {count} items (minimum {section.min_items})"
            )
        if section.max_items and count > section.max_items:
            issues.append(
                f"Section '{section.name}': {count} items (maximum {section.max_items})"
            )
        # Prose sections (no list items) are validated by length instead.
        # ``0 chars`` on a mandatory prose section reads as structural and
        # triggers the regenerate; a full section passes silently.
        if section.min_chars:
            prose = _extract_section_text(digest_text, section.pattern)
            n_chars = len(prose)
            if n_chars < section.min_chars:
                issues.append(
                    f"Section '{section.name}': {n_chars} chars (minimum {section.min_chars})"
                )
    return issues


def check_forbidden_content(
    digest_text: str,
    forbidden_patterns: List[str],
) -> List[str]:
    """Check for content that should not appear in the digest."""
    issues = []
    for pattern in forbidden_patterns:
        matches = re.findall(pattern, digest_text, re.IGNORECASE)
        if matches:
            sample = matches[0] if isinstance(matches[0], str) else str(matches[0])
            issues.append(
                f"Forbidden content found ({pattern[:40]}): '{sample[:60]}'"
            )
    return issues


def check_within_episode_duplicates(
    digest_text: str,
    section_patterns: Dict[str, str],
    threshold: float = 0.60,
) -> List[str]:
    """Check for duplicate stories within the same episode across all sections."""
    issues = []
    all_items_by_section: Dict[str, List[str]] = {}

    for sec_name, pattern in section_patterns.items():
        if sec_name in ("headlines", "takeover_headlines"):
            items = _extract_items_from_section(digest_text, pattern)
            all_items_by_section[sec_name] = items

    # Check within each section
    for sec_name, items in all_items_by_section.items():
        for i, item_a in enumerate(items):
            for j, item_b in enumerate(items):
                if j <= i:
                    continue
                sim = calculate_similarity(item_a, item_b)
                if sim >= threshold:
                    issues.append(
                        f"Duplicate within '{sec_name}': "
                        f"'{item_a[:50]}...' and '{item_b[:50]}...' "
                        f"(similarity {sim:.0%})"
                    )
    return issues


def check_cross_episode_repeats(
    digest_text: str,
    recent_headlines: List[str],
    section_patterns: Dict[str, str],
    threshold: float = 0.65,
) -> Tuple[List[str], List[str]]:
    """Check for stories that repeat from recent episodes.

    Returns
    -------
    Tuple of (warning_issues, exact_duplicate_headlines).
    - warning_issues: list of warning strings for near-duplicates (>= threshold)
    - exact_duplicate_headlines: list of headline texts that matched at 100%
      similarity (should be stripped from digest before podcast generation)
    """
    if not recent_headlines:
        return [], []

    issues = []
    exact_duplicates: List[str] = []
    # Extract today's headlines
    headlines_pattern = section_patterns.get("headlines", "")
    if not headlines_pattern:
        return [], []

    today_items = _extract_items_from_section(digest_text, headlines_pattern)

    from engine.utils import norm_headline_for_similarity
    recent_norm = [norm_headline_for_similarity(h) for h in recent_headlines if h]

    for item in today_items:
        norm_item = norm_headline_for_similarity(item)
        for r in recent_norm:
            if not r:
                continue
            sim = calculate_similarity(norm_item, r)
            if sim >= 1.0:
                exact_duplicates.append(item)
                issues.append(
                    f"BLOCKING cross-episode repeat: '{item[:60]}...' is identical "
                    f"to recent story (similarity 100%)"
                )
                break
            elif sim >= threshold:
                issues.append(
                    f"Cross-episode repeat: '{item[:60]}...' similar to recent story "
                    f"(similarity {sim:.0%})"
                )
                break

    return issues, exact_duplicates


def validate_digest(
    digest_text: str,
    config: ValidationConfig,
    section_patterns: Optional[Dict[str, str]] = None,
    recent_headlines: Optional[List[str]] = None,
) -> Tuple[bool, List[str], List[str]]:
    """Master validation function. Returns (passed, issues, exact_duplicates).

    Args:
        digest_text: The generated digest text to validate.
        config: Validation configuration for this show.
        section_patterns: Regex patterns for extracting sections.
        recent_headlines: Headlines from recent episodes for cross-day check.

    Returns:
        Tuple of (passed: bool, issues: list[str], exact_duplicates: list[str]).
        passed is True if no issues were found.
        exact_duplicates contains headlines that matched at 100% similarity
        to recent episodes — callers should strip these before podcast generation.
    """
    if not digest_text:
        return False, ["Empty digest text"], []

    issues: List[str] = []
    exact_duplicates: List[str] = []
    patterns = section_patterns or {}

    # 1. Section overlap check
    if config.section_pairs and patterns:
        overlap_issues = check_section_overlap(
            digest_text, config.section_pairs, patterns, config.overlap_threshold
        )
        issues.extend(overlap_issues)

    # 2. Item count validation
    if config.sections:
        count_issues = check_item_counts(digest_text, config.sections)
        issues.extend(count_issues)

    # 3. Forbidden content
    if config.forbidden_patterns:
        forbidden_issues = check_forbidden_content(digest_text, config.forbidden_patterns)
        issues.extend(forbidden_issues)

    # 4. Within-episode duplicates
    if patterns:
        dup_issues = check_within_episode_duplicates(digest_text, patterns)
        issues.extend(dup_issues)

    # 5. Cross-episode repeats
    if recent_headlines and patterns:
        repeat_issues, exact_duplicates = check_cross_episode_repeats(
            digest_text, recent_headlines, patterns, config.cross_episode_threshold
        )
        issues.extend(repeat_issues)

    if issues:
        logger.warning("Digest validation found %d issue(s):", len(issues))
        for issue in issues:
            logger.warning("  - %s", issue)
    else:
        logger.info("Digest validation passed — no issues found")

    return (len(issues) == 0, issues, exact_duplicates)


# ---------------------------------------------------------------------------
# Pre-built validation configs per show
# ---------------------------------------------------------------------------

def tst_validation_config() -> ValidationConfig:
    """Validation config for Tesla Shorts Time."""
    return ValidationConfig(
        section_pairs=[("headlines", "takeover_headlines")],
        sections=[
            SectionRule(
                name="Top News",
                pattern=(
                    r"(?:📰 \*\*Top (?:10|12) News Items\*\*|### Top (?:10|12) News Items|### Top (?:10|12) News|### Top News)"
                    r"(.*?)"
                    r"(?=━━|## Short Spot|📉|### Tesla First Principles|## Tesla X Takeover|🎙️)"
                ),
                min_items=5,
            ),
            SectionRule(
                name="Short Spot",
                pattern=(
                    r"(?:## Short Spot|📉 \*\*Short Spot\*\*)"
                    r"(.*?)"
                    r"(?=━━|### Tesla First Principles|🧠|### Daily Challenge|💪|$)"
                ),
                min_items=1,
            ),
            SectionRule(
                name="First Principles",
                pattern=(
                    r"(?:###\s*Tesla First Principles|🧠\s*Tesla First Principles|###\s*First Principles)"
                    r"(.*?)"
                    r"(?=━━|### Daily Challenge|💪|$)"
                ),
                min_items=1,
            ),
        ],
        forbidden_patterns=[
            # Stock price in podcast script (not digest — only for POD_PROMPT output)
            # Disabled here since it applies to podcast script, not X thread
        ],
    )


def ff_validation_config() -> ValidationConfig:
    """Validation config for Fascinating Frontiers."""
    return ValidationConfig(
        section_pairs=[],
        sections=[
            SectionRule(
                name="Space Stories",
                pattern=(
                    r"(?:### Top 15 Space|### Top \d+ Space)"
                    r"(.*?)"
                    r"(?=━━|### Cosmic Spotlight|$)"
                ),
                min_items=8,
            ),
            SectionRule(
                name="Cosmic Spotlight",
                pattern=r"(?:### Cosmic Spotlight)(.*?)(?=━━|### Daily Inspiration|$)",
                min_items=1,
            ),
        ],
    )


def pt_validation_config() -> ValidationConfig:
    """Validation config for Planetterrian Daily."""
    return ValidationConfig(
        section_pairs=[],
        sections=[
            SectionRule(
                name="Science Stories",
                pattern=(
                    r"(?:### Top 15 Science|### Top \d+ Science)"
                    r"(.*?)"
                    r"(?=━━|### Planetterrian Spotlight|$)"
                ),
                min_items=8,
            ),
            SectionRule(
                name="Planetterrian Spotlight",
                pattern=r"(?:### Planetterrian Spotlight)(.*?)(?=━━|### Daily Inspiration|$)",
                min_items=1,
            ),
        ],
    )


def ov_validation_config() -> ValidationConfig:
    """Validation config for Omni View."""
    return ValidationConfig(
        section_pairs=[],
        sections=[
            SectionRule(
                name="Top Stories",
                pattern=(
                    r"(?:### Top \d+|### Today's Top)"
                    r"(.*?)"
                    r"(?=━━|### (?:Deep Dive|Closing)|$)"
                ),
                min_items=5,
            ),
        ],
    )


def ei_validation_config() -> ValidationConfig:
    """Validation config for Environmental Intelligence."""
    return ValidationConfig(
        section_pairs=[],
        sections=[
            SectionRule(
                name="Lead Story",
                pattern=(
                    r"(?:### Lead Story|## Lead Story)"
                    r"(.*?)"
                    r"(?=━━|### Regulatory|## Regulatory|$)"
                ),
                min_items=1,
            ),
            SectionRule(
                name="Regulatory & Policy Watch",
                pattern=(
                    r"(?:### Regulatory & Policy Watch|## Regulatory & Policy Watch)"
                    r"(.*?)"
                    r"(?=━━|### Science|## Science|$)"
                ),
                min_items=1,
                optional=True,
            ),
        ],
        forbidden_patterns=[
            r"https?://\S+",  # URLs should not leak into podcast script
        ],
    )


def ma_validation_config() -> ValidationConfig:
    """Validation config for Models & Agents."""
    return ValidationConfig(
        section_pairs=[],
        sections=[
            SectionRule(
                name="Top Story",
                pattern=(
                    r"(?:### Top Story|## Top Story)"
                    r"(.*?)"
                    r"(?=━━|### Model Updates|## Model Updates|$)"
                ),
                # Prose lead story (4-6 sentences), NOT a bullet list. The old
                # min_items=1 counted 0 ``**bold**`` items on a perfectly good
                # prose section and forced a regenerate that shrank the digest
                # (Ep066: 12.9k → 9.0k chars). Validate by length instead.
                min_items=0,
                min_chars=250,
            ),
            SectionRule(
                name="Model Updates",
                pattern=(
                    r"(?:### Model Updates|## Model Updates)"
                    r"(.*?)"
                    r"(?=━━|### Agent|## Agent|$)"
                ),
                min_items=1,
                optional=True,
            ),
        ],
        forbidden_patterns=[
            r"https?://\S+",
        ],
    )


def mab_validation_config() -> ValidationConfig:
    """Validation config for Models & Agents for Beginners."""
    return ValidationConfig(
        section_pairs=[],
        sections=[
            SectionRule(
                name="The Big Story",
                pattern=(
                    r"(?:### The Big Story|## The Big Story)"
                    r"(.*?)"
                    r"(?=━━|### Cool Stuff|## Cool Stuff|### Cool Tools|## Cool Tools|$)"
                ),
                # Prose section (8-12 sentences), NOT a bullet list — validate
                # by length, not ``**bold**`` item count. The old min_items=1
                # always saw 0 items and regenerated the digest on essentially
                # every episode (wasteful + the retry introduced repetition).
                min_items=0,
                min_chars=250,
            ),
        ],
        forbidden_patterns=[
            r"https?://\S+",
        ],
    )


def mi_validation_config() -> ValidationConfig:
    """Validation config for Modern Investing Techniques."""
    return ValidationConfig(
        section_pairs=[],
        sections=[
            SectionRule(
                name="Strategy Spotlight",
                pattern=(
                    r"(?:### Strategy Spotlight|## Strategy Spotlight)"
                    r"(.*?)"
                    r"(?=━━|### Practice Investment|## Practice Investment|$)"
                ),
                min_items=1,
            ),
            SectionRule(
                name="Practice Investment",
                pattern=(
                    r"(?:### Practice Investment|## Practice Investment)"
                    r"(.*?)"
                    r"(?=━━|### Yesterday|## Yesterday|### Tools|$)"
                ),
                min_items=1,
            ),
            SectionRule(
                name="Tools & Techniques",
                pattern=(
                    r"(?:### Tools & Techniques|## Tools & Techniques)"
                    r"(.*?)"
                    r"(?=━━|### Quick Hits|## Quick Hits|$)"
                ),
                min_items=1,
                optional=True,
            ),
            SectionRule(
                name="Quick Hits",
                pattern=(
                    r"(?:### Quick Hits|## Quick Hits)"
                    r"(.*?)"
                    r"(?=━━|### Portfolio|## Portfolio|### Listener|## Listener|$)"
                ),
                min_items=2,
                optional=True,
            ),
            SectionRule(
                name="Listener Challenge",
                pattern=(
                    r"(?:### Listener Challenge|## Listener Challenge)"
                    r"(.*?)"
                    r"(?=━━|### TONE|## TONE|$)"
                ),
                min_items=1,
                optional=True,
            ),
        ],
        forbidden_patterns=[],
    )


def fp_validation_config() -> ValidationConfig:
    """Validation config for Финансы Просто."""
    return ValidationConfig(
        section_pairs=[],
        sections=[
            SectionRule(
                name="Главная тема",
                pattern=(
                    r"(?:### Главная тема|## Главная тема|главная новость)"
                    r"(.*?)"
                    r"(?=━━|### Объясни как подруге|## Объясни как подруге|### Как это работает|## Как это работает|$)"
                ),
                min_items=1,
            ),
            SectionRule(
                name="Объясни как подруге",
                pattern=(
                    r"(?:### Объясни как подруге|## Объясни как подруге)"
                    r"(.*?)"
                    r"(?=━━|### Практические советы|## Практические советы|### Коротко|## Коротко|$)"
                ),
                min_items=1,
            ),
            SectionRule(
                name="Практические советы",
                pattern=(
                    r"(?:### Практические советы|## Практические советы|попробуйте сами)"
                    r"(.*?)"
                    r"(?=━━|### Коротко|## Коротко|### Задание|## Задание|$)"
                ),
                min_items=1,
                optional=True,
            ),
            SectionRule(
                name="Коротко и ясно",
                pattern=(
                    r"(?:### Коротко и ясно|## Коротко и ясно|быстрые новости)"
                    r"(.*?)"
                    r"(?=━━|### Задание|## Задание|на сегодня всё|$)"
                ),
                min_items=1,
                optional=True,
            ),
        ],
        forbidden_patterns=[
        ],
    )


def pr_validation_config() -> ValidationConfig:
    """Validation config for Привет, Русский! (Privet Russian)."""
    return ValidationConfig(
        section_pairs=[],
        sections=[
            SectionRule(
                name="Word of the Day",
                pattern=(
                    r"(?:### Word of the Day|## Word of the Day|word of the day|first word"
                    r"|\*\*Vocabulary List|### Vocabulary|## Vocabulary)"
                    r"(.*?)"
                    r"(?=━━|### Grammar|## Grammar|\*\*Grammar|### Culture|## Culture|$)"
                ),
                min_items=1,
            ),
            SectionRule(
                name="Culture Corner",
                pattern=(
                    r"(?:### Culture Corner|## Culture Corner|culture corner|fun fact)"
                    r"(.*?)"
                    r"(?=━━|### Practice|## Practice|### Quiz|$)"
                ),
                min_items=1,
                optional=True,
            ),
        ],
        forbidden_patterns=[
            r"https?://\S+",
        ],
    )


# Registry mapping show slugs to their validation config factory.
SHOW_VALIDATION_CONFIGS = {
    "tesla": tst_validation_config,
    "tesla_shorts_time": tst_validation_config,
    "fascinating_frontiers": ff_validation_config,
    "planetterrian": pt_validation_config,
    "omni_view": ov_validation_config,
    "env_intel": ei_validation_config,
    "models_agents": ma_validation_config,
    "models_agents_beginners": mab_validation_config,
    "finansy_prosto": fp_validation_config,
    "modern_investing": mi_validation_config,
    "privet_russian": pr_validation_config,
}
