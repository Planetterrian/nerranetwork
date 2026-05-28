"""
MIT Recursive Learning Context Loader for Trading

This module loads the existing MIT podcast data (investment_tracker, lessons, etc.)
and makes it available to a real/paper trading strategy.

It is deliberately kept separate from the podcast generation code.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Dict, List

logger = logging.getLogger(__name__)

# Default path to the podcast's MIT data (read-only for the trading module)
DEFAULT_MIT_DATA_DIR = Path(__file__).resolve().parent.parent / "digests" / "modern_investing"


def load_investment_tracker(data_dir: Path | None = None) -> Dict[str, Any]:
    """Load the latest investment tracker from the MIT podcast data."""
    data_dir = data_dir or DEFAULT_MIT_DATA_DIR
    path = data_dir / "investment_tracker.json"
    if not path.exists():
        logger.warning("MIT investment_tracker.json not found at %s", path)
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        logger.exception("Failed to load investment tracker: %s", exc)
        return {}


def load_lessons_learned(data_dir: Path | None = None) -> List[Dict[str, Any]]:
    """Load active lessons from the MIT recursive ledger."""
    data_dir = data_dir or DEFAULT_MIT_DATA_DIR
    path = data_dir / "lessons_learned.json"
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        entries = data.get("entries", [])
        return [e for e in entries if e.get("status") == "active"]
    except Exception as exc:
        logger.exception("Failed to load lessons_learned: %s", exc)
        return []


def load_taught_lessons(data_dir: Path | None = None) -> Dict[str, Any]:
    """Load the taught lessons with cooldown information."""
    data_dir = data_dir or DEFAULT_MIT_DATA_DIR
    path = data_dir / "taught_lessons.json"
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        logger.exception("Failed to load taught_lessons: %s", exc)
        return {}


def get_mit_context_for_trading(data_dir: Path | None = None) -> Dict[str, Any]:
    """
    Returns a clean dict suitable for a trading decision engine.

    Includes:
    - Current portfolio summary and alpha
    - Active lessons
    - Top performing sectors / strategies (derived)
    - Recent closed trades for pattern recognition
    """
    tracker = load_investment_tracker(data_dir)
    active_lessons = load_lessons_learned(data_dir)
    taught = load_taught_lessons(data_dir)

    summary = tracker.get("summary", {})
    closed_trades = [
        t for t in tracker.get("trades", [])
        if t.get("status") == "closed" and t.get("alpha_pct") is not None
    ]

    # Simple top patterns (can be made much more sophisticated)
    winning_patterns = sorted(
        closed_trades, key=lambda t: t.get("alpha_pct", 0), reverse=True
    )[:5]

    return {
        "summary": summary,
        "active_lessons": active_lessons,
        "taught_lessons": taught.get("lessons", {}),
        "recent_winning_patterns": winning_patterns,
        "alpha_vs_nasdaq": summary.get("cumulative_alpha_vs_nasdaq", 0.0),
        "win_rate": summary.get("win_rate_pct", 0.0),
        "total_trades": summary.get("total_trades", 0),
        "current_streak": summary.get("current_streak", 0),
    }
