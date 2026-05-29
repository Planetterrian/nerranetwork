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
) -> Dict[str, Any]:
    """
    Score a finished podcast script for listener value.

    Returns a dict with overall score and component scores + suggestions.
    """
    heuristics = _heuristic_score(script or "", memory_blocks or {})

    # Simple weighted overall (can be tuned over time)
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

    result = {
        "overall": round(overall, 1),
        **heuristics,
        "suggestions": " | ".join(suggestions) if suggestions else "Script shows good listener value characteristics.",
        "version": "1.0-heuristic",
    }

    return result