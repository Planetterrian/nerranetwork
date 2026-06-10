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


def _heuristic_score(script: str, memory_blocks: Dict[str, Any]) -> Dict[str, float]:
    """Fast heuristic scoring based on observable script properties."""
    if not script:
        return {"narrative_continuity": 0, "listener_value": 0, "engagement_potential": 0}

    text = script.lower()
    word_count = len(script.split())

    # Narrative continuity: count references to memory-style concepts
    memory_keywords = ["since we last", "ongoing", "bigger arc", "progress", "update on", "open question", "as the .* story has"]
    narrative_hits = sum(1 for kw in memory_keywords if re.search(kw, text))
    narrative_score = min(10, narrative_hits * 2 + (3 if "memory" in text or "narrative" in text else 0))

    # Listener value: presence of concrete "why this matters" language + specifics
    value_indicators = ["why this matters", "what this means for", "this moves", "first time", "key question", "watch for"]
    value_hits = sum(1 for ind in value_indicators if ind in text)
    # Reward concrete numbers and named programs
    number_density = len(re.findall(r'\d+', script)) / max(word_count, 1)
    value_score = min(10, value_hits * 1.5 + (number_density * 20))

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

    suggestions = []
    if heuristics["narrative_continuity"] < 6:
        suggestions.append("Increase use of memory blocks for ongoing program continuity and 'where we are now' context.")
    if heuristics["listener_value"] < 6:
        suggestions.append("Add more explicit 'why this matters to owners/fans/investors' framing drawn from tracked programs.")
    if heuristics["engagement_potential"] < 6:
        suggestions.append("Strengthen opening hook and vary sentence rhythm for better audio flow.")
    if heuristics.get("length_substance", 10) < 8:
        suggestions.append("Script is well under the word target — expand thin stories with takeaways/implications instead of trimming coverage.")

    result = {
        "overall": round(overall, 1),
        **heuristics,
        "suggestions": " | ".join(suggestions) if suggestions else "Script shows good listener value characteristics.",
        "version": "1.1-heuristic-length",
    }

    return result