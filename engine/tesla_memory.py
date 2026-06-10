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

import copy
import json
import logging
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Dict

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
    # deepcopy (not .copy()) so callers that mutate nested dicts (e.g. a
    # brand-new show recording its first narrative update before any file
    # exists) can never corrupt the shared module-level DEFAULT_* templates.
    if not path.exists():
        return copy.deepcopy(default)
    try:
        with path.open("r", encoding="utf-8") as f:
            data = json.load(f)
            # Light migration guard
            if data.get("version", 0) < default.get("version", 1):
                logger.info("Upgrading %s schema", path.name)
            return data
    except Exception as exc:
        logger.warning("Failed to load %s (%s) — using default", path.name, exc)
        return copy.deepcopy(default)


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
    """Produce a highly actionable narrative block for the LLM to create listener value and continuity."""
    programs = tracker.get("programs", {})
    if not programs:
        return ""

    lines = [
        "### TESLA PROGRAM NARRATIVE MEMORY",
        "Use this to give regular listeners a sense of ongoing stories and real progress (or the lack of it).",
        "When a story touches one of these programs, MAKE THE CONTINUITY AUDIBLE — open that story with a",
        "short callback a regular listener recognizes, e.g. 'Remember, the show covered [program] on",
        "[last covered date] — today's news moves that forward because...'. Then answer naturally:",
        "  - Where does today's development fit in the bigger arc for this program?",
        "  - Does it meaningfully move any of the key open questions?",
        "  - What should attentive listeners be watching for next?",
        "If the show covered the same program YESTERDAY, do not re-explain it — say only what is NEW today.",
        "",
        "Tracked programs (with current status and open questions):"
    ]

    for key, prog in programs.items():
        name = prog.get("display_name", key.title())
        status = prog.get("status", "Status not yet tracked.")
        last_ep = prog.get("last_major_update_episode")
        last_date = prog.get("last_major_update_date", "")
        when = f" (status last reviewed: Ep{last_ep}, {last_date})" if last_ep else ""
        # Auto-tracked freshness (June 2026): when the show last actually
        # discussed this program on air — kept current automatically by
        # auto_update_narrative_from_digest, unlike the operator-curated
        # status above.
        ment_ep = prog.get("last_mentioned_episode")
        ment_date = prog.get("last_mentioned_date", "")
        if ment_ep and ment_ep != last_ep:
            when += f" (last covered on air: Ep{ment_ep}, {ment_date})"

        lines.append(f"\n**{name}**{when}")
        lines.append(f"Current status: {status}")

        questions = prog.get("key_open_questions", [])
        if questions:
            lines.append("Key open questions the show is following:")
            for q in questions:
                lines.append(f"  - {q}")

    lines.append("\n--- End of narrative memory ---")
    return "\n".join(lines)


def build_performance_signals_block(perf: Dict[str, Any]) -> str:
    """Produce audience performance signals the LLM can actually use for better emphasis and hooks."""
    signals = perf.get("recent_signals", {})
    if not any(signals.values()):
        return ""

    lines = ["### AUDIENCE PERFORMANCE SIGNALS (use to shape emphasis and hooks)"]
    if signals.get("strong_topics_last_30d"):
        lines.append("Topics that have recently driven strong engagement: " + ", ".join(signals["strong_topics_last_30d"][:5]))
    if signals.get("strong_hook_styles"):
        lines.append("Hook styles that have performed well lately: " + ", ".join(signals["strong_hook_styles"][:3]))
    if signals.get("notes"):
        lines.append(f"Notes: {signals['notes']}")

    lines.append("When a story aligns with a strong recent topic or hook style, consider leading with the most surprising or visual angle if the news supports it.")
    return "\n".join(lines)


def build_theme_context_block(theme_history: Dict[str, Any], lookback_days: int = 30) -> str:
    """Recurring theme signals the LLM can use to decide emphasis and avoid repetition."""
    themes = theme_history.get("recurring_themes", {})
    if not themes:
        return ""

    top = sorted(themes.items(), key=lambda x: x[1], reverse=True)[:6]
    if not top:
        return ""

    lines = ["### RECURRING THEMES (last ~30 days)"]
    lines.append("These themes have been prominent recently. When a story aligns with one, consider whether it deserves extra depth or a connection back to the larger conversation.")
    for theme, count in top:
        lines.append(f"- {theme} (appeared in ~{count} recent episodes)")
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


def update_performance_from_op3(output_dir: Path, op3_show_stats: Dict[str, Any]) -> int:
    """Refresh the performance tracker from real OP3 download data.

    June 10 2026: the performance loop had been DEAD since the memory
    system shipped — ``record_performance_signal`` had zero production
    callers, so the tracker was a hand-edited file that went stale in
    days and ``{tesla_performance_signals_block}`` injected static text
    into every prompt. This closes the loop with the audience data the
    nightly maintenance job already fetches (``api/op3_stats.json``).

    Derives ``strong_topics_last_30d`` from the tracked-program mentions
    in the titles of the most-downloaded recent episodes (titles are
    hook-first, so program detection on them is meaningful), REPLACING
    the previous list wholesale so the signal can't accumulate stale
    entries. Called nightly from ``scripts/update_tesla_performance.py``.

    Returns the number of strong topics recorded.
    """
    episodes = (op3_show_stats or {}).get("episodes") or []
    scored = [
        e for e in episodes
        if isinstance(e, dict) and e.get("title")
    ]
    if not scored:
        logger.info("No OP3 episode data — performance tracker left unchanged")
        return 0

    def _downloads(e: Dict[str, Any]) -> int:
        for key in ("downloads_30d", "downloads_7d", "downloads_all_time"):
            v = e.get(key)
            if isinstance(v, (int, float)) and v > 0:
                return int(v)
        return 0

    scored.sort(key=_downloads, reverse=True)
    top = [e for e in scored[:5] if _downloads(e) > 0]

    narrative = load_narrative_tracker(output_dir)
    display_names = {
        key: prog.get("display_name", key.title())
        for key, prog in narrative.get("programs", {}).items()
    }

    strong_topics: list = []
    top_titles: list = []
    for e in top:
        title = str(e.get("title", ""))
        top_titles.append(f"{title[:80]} ({_downloads(e)} dl)")
        lowered = title.lower()
        for key, pattern in _PROGRAM_MENTION_PATTERNS.items():
            name = display_names.get(key, key)
            if pattern.search(lowered) and name not in strong_topics:
                strong_topics.append(name)

    perf = load_performance_tracker(output_dir)
    signals = perf.setdefault("recent_signals", {})
    signals["strong_topics_last_30d"] = strong_topics[:5]
    signals["top_episodes"] = top_titles
    signals["notes"] = (
        "Auto-derived nightly from OP3 download data "
        "(scripts/update_performance_trackers.py). Topics = tracked programs "
        "mentioned in the hooks of the most-downloaded recent episodes."
    )
    save_performance_tracker(perf, output_dir)
    logger.info(
        "Performance tracker refreshed from OP3: %d strong topics (%s)",
        len(strong_topics), ", ".join(strong_topics) or "none",
    )
    return len(strong_topics)


# Words that carry no Tesla-story signal — generic news-digest vocabulary
# plus the narrative-template vocabulary that polluted the theme history
# before June 2026 (the old code mined bigrams from the TEMPLATE text of
# build_narrative_status_block on every episode, so "open questions" /
# "questions show" / "show following" dominated the history with counts
# in the hundreds while real topics sat in single digits).
_THEME_STOPWORDS = {
    "status", "last", "major", "update", "episode", "date", "open",
    "questions", "question", "show", "following", "mentioned", "current",
    "narrative", "memory", "program", "programs", "tracked", "models",
    "today", "tesla", "story", "stories", "news", "daily", "source",
    "sources", "according", "report", "reports", "reported", "company",
    "week", "month", "year", "time", "first", "this", "that", "with",
    "from", "have", "been", "will", "would", "could", "should", "about",
    "after", "before", "more", "than", "their", "they", "what", "when",
    "where", "which", "while", "into", "over", "under", "between",
    # Generic coverage vocabulary + URL tokens (June 10 2026: "google
    # https" / "announced discussed" bigrams were polluting the history).
    "announced", "discussed", "covered", "https", "http",
}


# Core Tesla program keywords (keep in sync with narrative tracker).
# Counted once per episode when present — these are the curated themes.
_THEME_KEYWORDS = [
    "optimus", "cybercab", "robotaxi", "fsd", "unsupervised",
    "hw5", "ai5", "4680", "structural pack", "giga texas",
    "next gen", "redwood", "megapack", "energy storage", "dojo",
]


def _extract_bigrams(text_lower: str) -> list:
    """Stopword-filtered lowercase bigrams (the theme-mining unit)."""
    words = [
        w for w in re.findall(r"\b[a-z]{4,}\b", text_lower)
        if w not in _THEME_STOPWORDS
    ]
    return [
        f"{words[i]} {words[i + 1]}"
        for i in range(len(words) - 1)
        if len(words[i]) + len(words[i + 1]) + 1 > 8
    ]


def _narrative_prose_bigrams(output_dir: Path) -> set:
    """Bigrams occurring in the narrative tracker's own prose.

    June 10 2026 fix: the digest-only mining fix (June 2026) wasn't
    enough — the narrative status block is injected into every digest
    prompt and the LLM echoes its wording into continuity sentences, so
    tracker prose ("Giga Texas dedicated factory construction
    underway...") was re-mined as a "theme" daily. The signature in the
    history: chains of overlapping bigrams with identical counts
    ("texas dedicated" / "dedicated factory" / "factory construction",
    all 17). Filtering bigrams that appear verbatim in the tracker's
    status/questions/claims text breaks the echo loop; genuinely fresh
    news phrasing never matches tracker prose verbatim.
    """
    tracker = load_narrative_tracker(output_dir)
    texts = []
    for prog in tracker.get("programs", {}).values():
        texts.append(str(prog.get("display_name", "")))
        texts.append(str(prog.get("status", "")))
        texts.extend(str(q) for q in prog.get("key_open_questions", []) or [])
        texts.extend(str(c) for c in prog.get("notable_claims", []) or [])
    return set(_extract_bigrams(" ".join(texts).lower()))


def update_theme_history_from_digest(output_dir: Path, digest_text: str, episode_num: int) -> None:
    """Theme extraction from the just-generated digest CONTENT only.

    June 2026 fix: the previous version also mined bigrams from the
    narrative status block — i.e. from our own prompt TEMPLATE — so the
    same template phrases were re-counted every episode and drowned out
    real topics. Themes now come exclusively from the digest text, with
    a stopword filter for template/news-boilerplate vocabulary AND a
    narrative-prose echo filter (see ``_narrative_prose_bigrams``). The
    polluted entries are scrubbed from existing histories on load.

    Idempotent per episode: re-running on an episode already recorded in
    ``theme_evolution`` is a no-op (Ep505 was double-counted on June 10
    when the pipeline re-ran across a deploy).
    """
    history = load_theme_history(output_dir)
    themes = history.setdefault("recurring_themes", {})
    evolution = history.setdefault("theme_evolution", [])

    if any(e.get("episode") == episode_num for e in evolution):
        logger.info(
            "Theme history already has Ep%s — skipping duplicate mining run",
            episode_num,
        )
        return

    echo_bigrams = _narrative_prose_bigrams(output_dir)

    # One-time scrub of pre-fix noise entries so the polluted counts
    # don't keep outranking real topics forever. Three classes (all
    # exempt curated keywords, whose counts are legitimately
    # keyword-driven):
    #   - keys containing ANY stopword — the current miner filters
    #     stopwords before pairing, so such keys can only be legacy;
    #   - narrative-prose echo bigrams (see _narrative_prose_bigrams);
    #   - leftovers are kept as genuine themes.
    for noise_key in list(themes.keys()):
        if noise_key in _THEME_KEYWORDS:
            continue
        words_in_key = noise_key.split()
        if words_in_key and any(w in _THEME_STOPWORDS for w in words_in_key):
            del themes[noise_key]
        elif noise_key in echo_bigrams:
            del themes[noise_key]

    # Strip URLs before mining — digests carry "Source: https://..."
    # lines whose tokens otherwise become junk bigrams ("google https").
    text_lower = re.sub(r"https?://\S+", " ", digest_text.lower())
    for kw in _THEME_KEYWORDS:
        if kw in text_lower:
            themes[kw] = themes.get(kw, 0) + 1

    # Bigram themes from the DIGEST content (never the template, never
    # tracker-prose echo), so emerging story phrases ("wireless bms",
    # "shanghai exports") get surfaced before they're promoted to
    # tracked keywords.
    for bigram in _extract_bigrams(text_lower):
        if bigram in echo_bigrams or bigram in _THEME_KEYWORDS:
            continue
        themes[bigram] = themes.get(bigram, 0) + 1

    # Keep only top 30 themes to avoid bloat
    sorted_themes = dict(sorted(themes.items(), key=lambda x: x[1], reverse=True)[:30])
    history["recurring_themes"] = sorted_themes
    evolution.append({
        "episode": episode_num,
        "top_themes": list(sorted_themes.keys())[:8]
    })

    save_theme_history(history, output_dir)


# Per-program detection patterns for automatic last-mention tracking.
# Keep in sync with DEFAULT_NARRATIVE_TRACKER program keys.
#
# June 2026: switched from substring tuples to word-boundary regexes.
# The old substring matching advanced FSD freshness on ANY digest
# containing the word "unsupervised" (e.g. a Waymo story), missed
# plural/hyphen variants ("robotaxis", "robo-taxi"), and let several
# programs claim the same sentence. These matches now drive on-air
# continuity callbacks ("last covered on air: ..."), so false positives
# produce wrong spoken lines — precision matters more than recall here.
_PROGRAM_MENTION_PATTERNS: Dict[str, "re.Pattern[str]"] = {
    "optimus": re.compile(r"\boptimus\b"),
    "cybercab_robotaxi": re.compile(r"\bcybercabs?\b|\brobo[-\s]?tax(?:is|i|ies)\b"),
    "fsd_unsupervised": re.compile(r"\bfsd\b|\bfull self[-\s]driving\b"),
    "hw5_ai5": re.compile(r"\bhw5\b|\bai5\b|\bhardware 5\b"),
    "next_gen_vehicle": re.compile(
        r"\bnext[-\s]gen(?:eration)?\b|\bredwood\b|\baffordable (?:model|vehicle|ev)\b"
    ),
    "4680_structural_pack": re.compile(r"\b4680\b|\bstructural (?:battery )?pack\b"),
}


def auto_update_narrative_from_digest(
    output_dir: Path, digest_text: str, episode_num: int, date_str: str,
) -> list:
    """Auto-advance per-program ``last_mentioned`` freshness from a digest.

    June 2026: the narrative tracker was designed for operator-driven
    status updates (scripts/update_tesla_narrative.py) but ran for weeks
    without one — the status block told the LLM "last major update
    Ep475" while the show was on Ep505, so continuity framing went
    stale. This closes the loop WITHOUT touching the operator-curated
    ``status`` text: it only records ``last_mentioned_episode`` /
    ``last_mentioned_date`` when the digest demonstrably discusses a
    tracked program. Returns the list of program keys detected.
    """
    text_lower = (digest_text or "").lower()
    if not text_lower.strip():
        return []

    tracker = load_narrative_tracker(output_dir)
    programs = tracker.get("programs", {})
    mentioned = []
    for key, pattern in _PROGRAM_MENTION_PATTERNS.items():
        prog = programs.get(key)
        if prog is None:
            continue
        if pattern.search(text_lower):
            prog["last_mentioned_episode"] = episode_num
            prog["last_mentioned_date"] = date_str
            mentioned.append(key)

    if mentioned:
        save_narrative_tracker(tracker, output_dir)
        logger.info(
            "Narrative tracker: recorded mentions in Ep%s for %s",
            episode_num, ", ".join(mentioned),
        )
    return mentioned
