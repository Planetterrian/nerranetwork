"""
MIT-powered trading strategy.

This module turns the recursive learning data from the MIT podcast into actual trade ideas.
It respects:
- Active lessons (what to do)
- Taught lessons + cooldowns (what to avoid right now)
- Sector exposure from the tracker
- Historically winning patterns
- Current alpha / win rate context
"""

from __future__ import annotations

import logging
from datetime import date, timedelta
from typing import Any, Dict, List

from .mit_context import get_mit_context_for_trading

logger = logging.getLogger(__name__)


def _is_lesson_on_cooldown(lesson_id: str, taught_lessons: Dict[str, Any], cooldown_days: int = 21) -> bool:
    """Check if a lesson was recently taught (within cooldown window)."""
    if not taught_lessons:
        return False
    entry = taught_lessons.get(lesson_id)
    if not entry or not entry.get("last_date"):
        return False
    try:
        last = date.fromisoformat(entry["last_date"])
        return (date.today() - last).days < cooldown_days
    except Exception:
        return False


def generate_trade_ideas(
    symbols_to_consider: List[str],
    market_data: Dict[str, Any],
    mit_context: Dict[str, Any] | None = None,
    max_ideas: int = 3,
) -> List[Dict[str, Any]]:
    """
    Generate trade ideas that respect the MIT recursive learning loop.
    """
    if mit_context is None:
        mit_context = get_mit_context_for_trading()

    active_lessons: List[Dict] = mit_context.get("active_lessons", [])
    taught_lessons: Dict = mit_context.get("taught_lessons", {})
    winning_patterns: List[Dict] = mit_context.get("recent_winning_patterns", [])
    alpha = mit_context.get("alpha_vs_nasdaq", 0.0)
    win_rate = mit_context.get("win_rate", 0.0)

    ideas: List[Dict[str, Any]] = []
    used_symbols: set = set()

    # Build a set of currently "hot" lessons/tags from recent winners
    hot_tags: set = set()
    for trade in winning_patterns:
        tags = trade.get("lesson_tags") or []
        for t in tags:
            hot_tags.add(t)

    # Score each symbol (very basic heuristic version - can be made much smarter later)
    scored: List[tuple[float, str, Dict]] = []

    for symbol in symbols_to_consider:
        if symbol in used_symbols:
            continue

        score = 0.0
        reasons: List[str] = []
        lesson_refs: List[str] = []

        sym_data = market_data.get(symbol, {})
        vol = sym_data.get("recent_volatility", 0.04)  # default ~4% 5-day range

        # 1. Boost if it matches historically winning patterns
        for wp in winning_patterns:
            if wp.get("symbol") == symbol or symbol in str(wp.get("strategy", "")):
                score += 2.8
                reasons.append("Matches recent high-alpha pattern")
                if wp.get("lesson_tags"):
                    lesson_refs.extend(wp["lesson_tags"])

        # 2. Apply active lessons (positive rules)
        for lesson in active_lessons[:5]:
            obs = lesson.get("observation", "").lower()
            adj = lesson.get("adjustment", "").lower()
            if symbol.lower() in obs or symbol.lower() in adj:
                score += 2.0
                reasons.append(f"Aligns with active lesson {lesson.get('id')}")
                lesson_refs.append(lesson.get("id"))

        # 3. Penalize if any taught lesson is on cooldown
        for lid, entry in taught_lessons.items():
            if _is_lesson_on_cooldown(lid, taught_lessons):
                if symbol.lower() in str(entry.get("observation", "")).lower():
                    score -= 4.0
                    reasons.append(f"Hard avoid (cooldown active for lesson {lid})")
                    break
        if any("Hard avoid" in r for r in reasons):
            continue

        # 4. Environment / system health bias
        if alpha > 4 and win_rate > 54:
            score += 1.0
            reasons.append("MIT system has positive edge — modest aggression justified")
        elif alpha < -4:
            score -= 2.0
            reasons.append("MIT system lagging benchmark — raising bar significantly")

        # 5. Volatility adjustment (prefer reasonable volatility, penalize extremes for now)
        if vol > 0.12:
            score -= 1.2
            reasons.append("Very high recent volatility — de-risking")
        elif 0.03 < vol < 0.07:
            score += 0.6
            reasons.append("Favorable volatility regime")

        # 6. Minimum quality threshold
        if score < 2.0:
            continue

        idea = {
            "symbol": symbol,
            "thesis": " | ".join(reasons[:3]) if reasons else "MIT context alignment detected.",
            "confidence": "high" if score >= 3.5 else "medium",
            "suggested_size_pct": min(0.08, 0.04 + (score * 0.01)),
            "lesson_references": list(set(lesson_refs))[:4],
            "mit_score": round(score, 2),
        }
        scored.append((score, symbol, idea))

    # Sort by score and return top N
    scored.sort(reverse=True, key=lambda x: x[0])
    for score, symbol, idea in scored[:max_ideas]:
        ideas.append(idea)
        used_symbols.add(symbol)

    logger.info(f"Generated {len(ideas)} MIT-informed trade ideas (max {max_ideas})")
    return ideas

