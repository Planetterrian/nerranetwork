"""Tesla Shorts Time memory and recursive improvement system.

This module provides persistent memory and feedback loops for TST, modeled
on the MIT recursive learning approach but adapted for a daily news/analysis show.

Three main loops are supported:
1. Narrative Memory     — Major Tesla programs (Optimus, Cybercab, FSD, etc.)
2. Performance Feedback — YouTube long-form + Shorts engagement signals
3. Theme Mining         — Recurring patterns extracted from own transcripts/digests

All data lives in digests/tesla_shorts_time/ and is automatically injected
into prompts via the tesla pre-fetch hook.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# Filenames (all live alongside tesla_content_tracker.json)
NARRATIVE_TRACKER_FILENAME = "tesla_narrative_tracker.json"
PERFORMANCE_TRACKER_FILENAME = "tesla_performance_tracker.json"
THEME_HISTORY_FILENAME = "tesla_theme_history.json"


# ---------------------------------------------------------------------------
# Core data models (kept simple and human-editable)
# ---------------------------------------------------------------------------

DEFAULT_NARRATIVE_TRACKER: Dict[str, Any] = {
    "version": 1,
    "last_updated": "",
    "programs": {
        "optimus": {
            "display_name": "Optimus",
            "status": "Early production ramp phase. Giga Texas factory construction advancing.",
            "last_major_update_episode": None,
            "last_major_update_date": "",
            "key_open_questions": [
                "Volume production timeline and cost targets",
                "Human labor displacement economics"
            ],
            "show_confidence": "medium",
            "notable_claims": []
        },
        "cybercab_robotaxi": {
            "display_name": "Cybercab / Robotaxi",
            "status": "Vehicle unveiled. Regulatory and deployment timeline still fluid.",
            "last_major_update_episode": None,
            "last_major_update_date": "",
            "key_open_questions": ["Unsupervised regulatory approval path", "Launch timeline by region"],
            "show_confidence": "low-medium",
            "notable_claims": []
        },
        "fsd_unsupervised": {
            "display_name": "FSD Unsupervised",
            "status": "Supervised FSD expanding. True unsupervised regulatory path remains the gating item.",
            "last_major_update_episode": None,
            "last_major_update_date": "",
            "key_open_questions": ["Regulatory approval in key markets", "HW5/AI5 dependency"],
            "show_confidence": "medium",
            "notable_claims": []
        },
        "hw5_ai5": {
            "display_name": "HW5 / AI5 Hardware",
            "status": "Next-gen inference hardware in development.",
            "last_major_update_episode": None,
            "last_major_update_date": "",
            "key_open_questions": ["Performance targets vs current HW4", "Production timeline"],
            "show_confidence": "medium",
            "notable_claims": []
        },
        "next_gen_vehicle": {
            "display_name": "Next-Gen / Redwood Vehicle",
            "status": "Development ongoing. Significant cost reduction target.",
            "last_major_update_episode": None,
            "last_major_update_date": "",
            "key_open_questions": ["Final price target and launch timing"],
            "show_confidence": "low",
            "notable_claims": []
        },
        "4680_structural_pack": {
            "display_name": "4680 + Structural Battery Pack",
            "status": "Production scaling at Giga Texas and Nevada.",
            "last_major_update_episode": None,
            "last_major_update_date": "",
            "key_open_questions": ["Cost curve and energy density gains"],
            "show_confidence": "medium",
            "notable_claims": []
        }
    }
}

DEFAULT_PERFORMANCE_TRACKER: Dict[str, Any] = {
    "version": 1,
    "last_updated": "",
    "recent_signals": {
        "strong_topics_last_30d": [],
        "strong_hook_styles": [],
        "shorts_winners": [],
        "notes": "Manually or API-populated. Used to bias future hook/segment selection."
    }
}

DEFAULT_THEME_HISTORY: Dict[str, Any] = {
    "version": 1,
    "last_updated": "",
    "recurring_themes": {},
    "theme_evolution": []
}


# ---------------------------------------------------------------------------
# Low-level load/save helpers
# ---------------------------------------------------------------------------

def _load_json(path: Path, default: Dict[str, Any]) -> Dict[str, Any]:
    if not path.exists():
        return default.copy()
    try:
        with path.open("r", encoding="utf-8") as f:
            data = json.load(f)
            # Light migration guard
            if data.get("version", 0) < default.get("version", 1):
                logger.info("Upgrading %s schema", path.name)
            return data
    except Exception as exc:
        logger.warning("Failed to load %s (%s) — using default", path.name, exc)
        return default.copy()


def _save_json(path: Path, data: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    with tmp.open("w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    tmp.replace(path)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def load_narrative_tracker(output_dir: Path) -> Dict[str, Any]:
    path = output_dir / NARRATIVE_TRACKER_FILENAME
    return _load_json(path, DEFAULT_NARRATIVE_TRACKER)


def save_narrative_tracker(tracker: Dict[str, Any], output_dir: Path) -> None:
    path = output_dir / NARRATIVE_TRACKER_FILENAME
    tracker["last_updated"] = datetime.now().isoformat()
    _save_json(path, tracker)


def load_performance_tracker(output_dir: Path) -> Dict[str, Any]:
    path = output_dir / PERFORMANCE_TRACKER_FILENAME
    return _load_json(path, DEFAULT_PERFORMANCE_TRACKER)


def save_performance_tracker(tracker: Dict[str, Any], output_dir: Path) -> None:
    path = output_dir / PERFORMANCE_TRACKER_FILENAME
    tracker["last_updated"] = datetime.now().isoformat()
    _save_json(path, tracker)


def load_theme_history(output_dir: Path) -> Dict[str, Any]:
    path = output_dir / THEME_HISTORY_FILENAME
    return _load_json(path, DEFAULT_THEME_HISTORY)


def save_theme_history(history: Dict[str, Any], output_dir: Path) -> None:
    path = output_dir / THEME_HISTORY_FILENAME
    history["last_updated"] = datetime.now().isoformat()
    _save_json(path, history)


# ---------------------------------------------------------------------------
# Prompt-ready context builders (the important recursive part)
# ---------------------------------------------------------------------------

def build_narrative_status_block(tracker: Dict[str, Any]) -> str:
    """Produce a clean, prompt-friendly block about current major program status."""
    programs = tracker.get("programs", {})
    if not programs:
        return ""

    lines = ["### CURRENT TESLA NARRATIVE STATUS (major active programs)"]
    for key, prog in programs.items():
        name = prog.get("display_name", key.title())
        status = prog.get("status", "Status not yet tracked.")
        last_ep = prog.get("last_major_update_episode")
        last_date = prog.get("last_major_update_date", "")
        when = f" (last discussed Ep{last_ep}, {last_date})" if last_ep else ""
        lines.append(f"- **{name}**: {status}{when}")

    lines.append("\nWhen a news item touches one of these programs, briefly note the update relative to the status above.")
    return "\n".join(lines)


def build_performance_signals_block(perf: Dict[str, Any]) -> str:
    """Produce a short block of recent audience performance signals."""
    signals = perf.get("recent_signals", {})
    if not any(signals.values()):
        return ""

    lines = ["### RECENT AUDIENCE ENGAGEMENT SIGNALS (use to inform emphasis)"]
    if signals.get("strong_topics_last_30d"):
        lines.append("- Strong recent topics: " + ", ".join(signals["strong_topics_last_30d"][:5]))
    if signals.get("strong_hook_styles"):
        lines.append("- High-performing hook patterns: " + ", ".join(signals["strong_hook_styles"][:3]))
    if signals.get("notes"):
        lines.append(f"- Notes: {signals['notes']}")
    return "\n".join(lines)


def build_theme_context_block(theme_history: Dict[str, Any], lookback_days: int = 30) -> str:
    """Lightweight recurring theme summary for freshness + depth decisions."""
    themes = theme_history.get("recurring_themes", {})
    if not themes:
        return ""

    top = sorted(themes.items(), key=lambda x: x[1], reverse=True)[:6]
    if not top:
        return ""

    lines = ["### RECURRING THEMES (last ~30 days — use for context, not repetition)"]
    for theme, count in top:
        lines.append(f"- {theme}: appeared in ~{count} recent episodes")
    return "\n".join(lines)


def get_tesla_memory_context(output_dir: Path) -> Dict[str, str]:
    """One-call helper used by the pre-fetch hook."""
    narrative = load_narrative_tracker(output_dir)
    perf = load_performance_tracker(output_dir)
    themes = load_theme_history(output_dir)

    return {
        "tesla_narrative_status_block": build_narrative_status_block(narrative),
        "tesla_performance_signals_block": build_performance_signals_block(perf),
        "tesla_theme_context_block": build_theme_context_block(themes),
    }


# ---------------------------------------------------------------------------
# Post-episode update helpers (called after successful generation)
# ---------------------------------------------------------------------------

def record_narrative_update(output_dir: Path, program_key: str, new_status: str, episode_num: int, date_str: str) -> None:
    """Lightweight helper for manual or automated narrative updates."""
    tracker = load_narrative_tracker(output_dir)
    if program_key not in tracker["programs"]:
        logger.warning("Unknown narrative program key: %s", program_key)
        return

    prog = tracker["programs"][program_key]
    prog["status"] = new_status
    prog["last_major_update_episode"] = episode_num
    prog["last_major_update_date"] = date_str

    save_narrative_tracker(tracker, output_dir)
    logger.info("Updated narrative tracker for %s (Ep%s)", program_key, episode_num)


def record_performance_signal(output_dir: Path, signal_type: str, value: Any) -> None:
    """Record a performance observation (called manually or from future automation)."""
    perf = load_performance_tracker(output_dir)
    signals = perf.setdefault("recent_signals", {})
    if signal_type == "strong_topic":
        lst = signals.setdefault("strong_topics_last_30d", [])
        if value not in lst:
            lst.append(value)
    elif signal_type == "hook_style":
        lst = signals.setdefault("strong_hook_styles", [])
        if value not in lst:
            lst.append(value)
    save_performance_tracker(perf, output_dir)


# Simple theme mining stub (can be expanded significantly later)
def update_theme_history_from_digest(output_dir: Path, digest_text: str, episode_num: int) -> None:
    """Very lightweight theme extraction from the just-generated digest."""
    history = load_theme_history(output_dir)
    themes = history.setdefault("recurring_themes", {})

    # Extremely simple keyword-based mining (good enough for v1)
    keywords = [
        "optimus", "cybercab", "robotaxi", "fsd", "unsupervised",
        "hw5", "ai5", "4680", "structural pack", "giga texas",
        "next gen", "redwood", "megapack", "energy storage"
    ]

    text_lower = digest_text.lower()
    for kw in keywords:
        if kw in text_lower:
            themes[kw] = themes.get(kw, 0) + 1

    # Keep only top 30 themes to avoid bloat
    sorted_themes = dict(sorted(themes.items(), key=lambda x: x[1], reverse=True)[:30])
    history["recurring_themes"] = sorted_themes
    history.setdefault("theme_evolution", []).append({
        "episode": episode_num,
        "top_themes": list(sorted_themes.keys())[:8]
    })

    save_theme_history(history, output_dir)
