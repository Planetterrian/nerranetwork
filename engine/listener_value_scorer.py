"""
Lightweight Listener Value Scorer for TST (and potentially other shows).

Runs after final podcast script generation but before TTS.
Provides an automated score on dimensions that correlate with listener retention
and satisfaction, with special emphasis on effective use of the Tesla memory system.

This is intentionally lightweight so it can run on every episode without significant cost or latency.
"""

import logging
import re
from typing import Any, Dict

logger = logging.getLogger(__name__)

# Below this the episode is worth a look before publishing.
#
# Calibrated 2026-08-02 against 96 shipped scripts across eight shows:
# it fires on the bottom ~10%. The previous 6.5 was set against the old
# catchphrase-counting scorer and fired on EVERY episode of EVERY show
# (60 sampled runs, range 3.1-6.3, none above the bar) — a gate that
# always fires carries no information and trains the operator to ignore
# it. Re-measure this number if the components change again.
REVIEW_THRESHOLD = 5.7


def _tracked_programs(memory_blocks: Dict[str, Any]) -> set:
    """Program names the show's narrative memory is tracking.

    Pulled out of whatever memory text was injected into the prompt
    (``{narrative_memory_section}`` and friends). Multi-word Title Case
    phrases are the shape program names take in those blocks.
    """
    blob_parts = []
    for value in (memory_blocks or {}).values():
        if isinstance(value, str) and len(value) > 40:
            blob_parts.append(value)
    if not blob_parts:
        return set()
    blob = "\n".join(blob_parts)
    names = set()
    for match in re.findall(r"\b[A-Z][a-zA-Z0-9-]+(?:\s+[A-Z][a-zA-Z0-9-]+)+",
                            blob):
        cleaned = match.strip()
        if 5 <= len(cleaned) <= 40:
            names.add(cleaned)
    return names


def _program_coverage_score(script: str,
                            memory_blocks: Dict[str, Any]) -> float:
    """0-10 for how many tracked programs the script actually covers.

    Returns a NEUTRAL 5.0 when the show has no memory context, rather
    than 0. Scoring absence as failure is why memory-less shows sat
    permanently low on a dimension they cannot express.
    """
    programs = _tracked_programs(memory_blocks)
    if not programs:
        return 5.0
    lowered = (script or "").lower()
    hits = sum(1 for name in programs if name.lower() in lowered)
    return round(min(10.0, hits * 2.5), 1)


def _heuristic_score(script: str, memory_blocks: Dict[str, Any]) -> Dict[str, float]:
    """Fast heuristic scoring based on observable script properties."""
    if not script:
        return {"narrative_continuity": 0, "listener_value": 0, "engagement_potential": 0}

    text = script.lower()
    word_count = len(script.split())

    # ---- Narrative continuity -------------------------------------
    # Measured as: does the script actually talk about the programs the
    # show is TRACKING? Phrase-agnostic on purpose.
    #
    # This used to count stock phrases ("since we last", "update on",
    # "open question"). That rewarded the exact boilerplate the network
    # spends review passes removing, and — because the phrases are
    # cheap — a script could score well by saying them without carrying
    # any continuity at all.
    narrative_score = _program_coverage_score(script, memory_blocks)

    # ---- Listener value -------------------------------------------
    # Concrete specifics, not catchphrases. The old list rewarded
    # "why this matters" / "what this means for" / "watch for" — all
    # three are documented tics ('watch for' 12x is called "a heavier
    # real tic" in engine.generator, and "this matters for" sits in the
    # repetition detector's template-artefact allowlist). An instrument
    # that tells the operator to add banned phrasing is worse than no
    # instrument, so value is now measured by density of the things the
    # shows are actually asked for: figures and named entities.
    number_density = len(re.findall(r"\d", script)) / max(word_count, 1)
    proper_nouns = re.findall(r"\b[A-Z][a-zA-Z0-9-]{2,}\b", script)
    # Sentence-initial capitals aren't evidence of specificity.
    sentence_starts = set(re.findall(r"(?:^|[.!?]\s+)([A-Z][a-zA-Z0-9-]{2,})",
                                     script))
    distinct_entities = {p for p in proper_nouns} - sentence_starts
    entity_density = len(distinct_entities) / max(word_count, 1)
    value_score = min(10.0, number_density * 120 + entity_density * 90)

    # Engagement potential: hook strength, variety, natural flow signals
    hook_quality = 5
    if re.search(r'(surprising|first time|biggest|never before|major shift)', text[:500]):
        hook_quality = 8
    sentence_variety = len(set(len(s.split()) for s in re.split(r'[.!?]', script)[:20])) / 5
    engagement_score = min(10, hook_quality + sentence_variety * 2)

    return {
        "narrative_continuity": round(narrative_score, 1),
        "listener_value": round(value_score, 1),
        "engagement_potential": round(engagement_score, 1),
    }


def score_script(
    script: str,
    show_slug: str = "tesla",
    memory_blocks: Dict[str, Any] | None = None,
    target_words: int = 0,
) -> Dict[str, Any]:
    """
    Score a finished podcast script for listener value.

    Returns a dict with overall score and component scores + suggestions.
    Pass *target_words* (the show's ``min_podcast_words``) to include a
    length-substance component — June 2026: nine of ten Tesla episodes
    shipped 15-35% under target while clustering at the same 3.2 score,
    so shortness was invisible in the metric the dashboard tracks.
    """
    heuristics = _heuristic_score(script or "", memory_blocks or {})

    if target_words and target_words > 0:
        word_count = len((script or "").split())
        # 10 at/above target, linear down; a 65%-of-target script scores 6.5.
        length_score = round(min(10.0, (word_count / target_words) * 10), 1)
        heuristics["length_substance"] = length_score
        overall = (
            heuristics["narrative_continuity"] * 0.30 +
            heuristics["listener_value"] * 0.35 +
            heuristics["engagement_potential"] * 0.20 +
            length_score * 0.15
        )
    else:
        # Legacy weighting for callers that don't pass a target.
        overall = (
            heuristics["narrative_continuity"] * 0.35 +
            heuristics["listener_value"] * 0.40 +
            heuristics["engagement_potential"] * 0.25
        )

    # Suggestions describe the SHAPE of the gap and never quote a phrase
    # to insert — supplying a literal sentence is how every seeded tic in
    # this network's history got started, and the previous wording asked
    # for two phrases that reviews had already banned.
    suggestions = []
    if heuristics["narrative_continuity"] < 6:
        suggestions.append(
            "Few of the tracked programs appear in the script — connect a "
            "story to a program the show is following, in your own words.")
    if heuristics["listener_value"] < 6:
        suggestions.append(
            "Low density of figures and named entities — cite the specific "
            "numbers, dates and program names the sources give.")
    if heuristics["engagement_potential"] < 6:
        suggestions.append("Strengthen opening hook and vary sentence rhythm for better audio flow.")
    if heuristics.get("length_substance", 10) < 8:
        suggestions.append("Script is well under the word target — expand thin stories with takeaways/implications instead of trimming coverage.")

    result = {
        "overall": round(overall, 1),
        **heuristics,
        "suggestions": " | ".join(suggestions) if suggestions else "Script shows good listener value characteristics.",
        # 2.0: catchphrase counting replaced with program coverage +
        # specificity density. Scores are NOT comparable with 1.x history.
        "version": "2.0-coverage-specificity",
    }

    return result