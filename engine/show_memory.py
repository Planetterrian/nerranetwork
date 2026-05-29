"""Generalized recursive narrative-memory engine (Phase 3).

This generalizes ``engine.tesla_memory`` so any show can maintain the same
three recursive-improvement loops Tesla Shorts Time pioneered:

1. **Narrative memory**  — major ongoing programs/threads the show tracks
   (status, open questions, confidence, notable claims).
2. **Performance feedback** — engagement signals used to bias emphasis/hooks.
3. **Theme mining** — recurring themes auto-extracted from the show's own
   digests over time.

A show plugs in via a :class:`MemoryConfig` (its slug, a human label for the
prompt block header, a filename prefix, its starter programs, and the keyword
list theme-mining scans for). ``engine.tesla_memory`` is the first consumer —
it wraps this module with Tesla's config so its public API + on-disk format +
rendered block text stay byte-for-byte identical (guarded by
``tests/test_show_memory.py``).

The on-disk trackers live in the show's ``output_dir`` as
``<prefix>_narrative_tracker.json`` / ``<prefix>_performance_tracker.json`` /
``<prefix>_theme_history.json``.
"""

from __future__ import annotations

import copy
import json
import logging
import re
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Per-show configuration
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class MemoryConfig:
    """Everything show-specific about a memory instance.

    slug:           show slug (e.g. "models_agents") — informational.
    label:          uppercase header shown in the narrative prompt block
                    (e.g. "MODELS & AGENTS" -> "### MODELS & AGENTS PROGRAM
                    NARRATIVE MEMORY"). For Tesla this is "TESLA" so the
                    rendered block is byte-identical to the legacy module.
    file_prefix:    prefix for the three JSON tracker filenames.
    default_programs: starter ``programs`` dict for a brand-new narrative
                    tracker (same shape as Tesla's).
    theme_keywords: lowercased substrings theme-mining counts in each digest.
    """
    slug: str
    label: str
    file_prefix: str
    default_programs: Dict[str, Any] = field(default_factory=dict)
    theme_keywords: List[str] = field(default_factory=list)

    # ---- filenames -------------------------------------------------------
    @property
    def narrative_filename(self) -> str:
        return f"{self.file_prefix}_narrative_tracker.json"

    @property
    def performance_filename(self) -> str:
        return f"{self.file_prefix}_performance_tracker.json"

    @property
    def theme_filename(self) -> str:
        return f"{self.file_prefix}_theme_history.json"


# ---------------------------------------------------------------------------
# Default tracker templates (programs are filled from the MemoryConfig)
# ---------------------------------------------------------------------------

def default_narrative_tracker(cfg: MemoryConfig) -> Dict[str, Any]:
    return {
        "version": 1,
        "last_updated": "",
        "programs": copy.deepcopy(cfg.default_programs),
    }


def default_performance_tracker() -> Dict[str, Any]:
    return {
        "version": 1,
        "last_updated": "",
        "recent_signals": {
            "strong_topics_last_30d": [],
            "strong_hook_styles": [],
            "shorts_winners": [],
            # Empty by default so a brand-new show injects no performance block
            # (and thus no noise) until real signals are recorded.
            "notes": "",
        },
    }


def default_theme_history() -> Dict[str, Any]:
    return {
        "version": 1,
        "last_updated": "",
        "recurring_themes": {},
        "theme_evolution": [],
    }


# ---------------------------------------------------------------------------
# Low-level load/save helpers
# ---------------------------------------------------------------------------

def _load_json(path: Path, default: Dict[str, Any]) -> Dict[str, Any]:
    # deepcopy (not .copy()) so callers that mutate nested dicts (e.g. a
    # brand-new show recording its first narrative update before any file
    # exists) can never corrupt a shared default template.
    if not path.exists():
        return copy.deepcopy(default)
    try:
        with path.open("r", encoding="utf-8") as f:
            data = json.load(f)
            if data.get("version", 0) < default.get("version", 1):
                logger.info("Upgrading %s schema", path.name)
            return data
    except Exception as exc:  # noqa: BLE001
        logger.warning("Failed to load %s (%s) — using default", path.name, exc)
        return copy.deepcopy(default)


def _save_json(path: Path, data: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    with tmp.open("w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    tmp.replace(path)


# ---------------------------------------------------------------------------
# Public load/save API
# ---------------------------------------------------------------------------

def load_narrative_tracker(output_dir: Path, cfg: MemoryConfig) -> Dict[str, Any]:
    return _load_json(Path(output_dir) / cfg.narrative_filename, default_narrative_tracker(cfg))


def save_narrative_tracker(tracker: Dict[str, Any], output_dir: Path, cfg: MemoryConfig) -> None:
    tracker["last_updated"] = datetime.now().isoformat()
    _save_json(Path(output_dir) / cfg.narrative_filename, tracker)


def load_performance_tracker(output_dir: Path, cfg: MemoryConfig) -> Dict[str, Any]:
    return _load_json(Path(output_dir) / cfg.performance_filename, default_performance_tracker())


def save_performance_tracker(tracker: Dict[str, Any], output_dir: Path, cfg: MemoryConfig) -> None:
    tracker["last_updated"] = datetime.now().isoformat()
    _save_json(Path(output_dir) / cfg.performance_filename, tracker)


def load_theme_history(output_dir: Path, cfg: MemoryConfig) -> Dict[str, Any]:
    return _load_json(Path(output_dir) / cfg.theme_filename, default_theme_history())


def save_theme_history(history: Dict[str, Any], output_dir: Path, cfg: MemoryConfig) -> None:
    history["last_updated"] = datetime.now().isoformat()
    _save_json(Path(output_dir) / cfg.theme_filename, history)


# ---------------------------------------------------------------------------
# Prompt-ready context builders
# ---------------------------------------------------------------------------

def build_narrative_status_block(tracker: Dict[str, Any], label: str) -> str:
    """Render the narrative-memory block injected into the show's prompt.

    Byte-identical to the legacy Tesla block when ``label == "TESLA"``.
    """
    programs = tracker.get("programs", {})
    if not programs:
        return ""

    lines = [
        f"### {label} PROGRAM NARRATIVE MEMORY",
        "Use this to give regular listeners a sense of ongoing stories and real progress (or the lack of it).",
        "When a story touches one of these programs, include 1-2 natural sentences answering:",
        "  - Where does today's development fit in the bigger arc for this program?",
        "  - Does it meaningfully move any of the key open questions?",
        "  - What should attentive listeners be watching for next?",
        "",
        "Tracked programs (with current status and open questions):",
    ]

    for key, prog in programs.items():
        name = prog.get("display_name", key.title())
        status = prog.get("status", "Status not yet tracked.")
        last_ep = prog.get("last_major_update_episode")
        last_date = prog.get("last_major_update_date", "")
        when = f" (last major update mentioned: Ep{last_ep}, {last_date})" if last_ep else ""

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


def get_memory_context(output_dir: Path, cfg: MemoryConfig) -> Dict[str, str]:
    """One-call helper for hooks. Returns generic-keyed prompt blocks.

    Keys: ``narrative_status_block`` / ``performance_signals_block`` /
    ``theme_context_block``. Empty strings when the trackers are empty, so a
    show that has just enabled memory (no programs/themes yet) injects nothing.
    """
    narrative = load_narrative_tracker(output_dir, cfg)
    perf = load_performance_tracker(output_dir, cfg)
    themes = load_theme_history(output_dir, cfg)
    return {
        "narrative_status_block": build_narrative_status_block(narrative, cfg.label),
        "performance_signals_block": build_performance_signals_block(perf),
        "theme_context_block": build_theme_context_block(themes),
    }


# ---------------------------------------------------------------------------
# Post-episode update helpers
# ---------------------------------------------------------------------------

def record_narrative_update(output_dir: Path, cfg: MemoryConfig, program_key: str,
                            new_status: str, episode_num: int, date_str: str) -> None:
    tracker = load_narrative_tracker(output_dir, cfg)
    if program_key not in tracker.get("programs", {}):
        logger.warning("Unknown narrative program key for %s: %s", cfg.slug, program_key)
        return
    prog = tracker["programs"][program_key]
    prog["status"] = new_status
    prog["last_major_update_episode"] = episode_num
    prog["last_major_update_date"] = date_str
    save_narrative_tracker(tracker, output_dir, cfg)
    logger.info("Updated %s narrative tracker for %s (Ep%s)", cfg.slug, program_key, episode_num)


def record_performance_signal(output_dir: Path, cfg: MemoryConfig, signal_type: str, value: Any) -> None:
    perf = load_performance_tracker(output_dir, cfg)
    signals = perf.setdefault("recent_signals", {})
    if signal_type == "strong_topic":
        lst = signals.setdefault("strong_topics_last_30d", [])
        if value not in lst:
            lst.append(value)
    elif signal_type == "hook_style":
        lst = signals.setdefault("strong_hook_styles", [])
        if value not in lst:
            lst.append(value)
    save_performance_tracker(perf, output_dir, cfg)


def update_theme_history_from_digest(output_dir: Path, cfg: MemoryConfig,
                                     digest_text: str, episode_num: int) -> None:
    """Lightweight theme extraction from the just-generated digest + narrative context."""
    history = load_theme_history(output_dir, cfg)
    themes = history.setdefault("recurring_themes", {})

    text_lower = (digest_text or "").lower()
    for kw in cfg.theme_keywords:
        if kw in text_lower:
            themes[kw] = themes.get(kw, 0) + 1

    # Also extract simple bigram themes from the narrative status block if
    # present (surfaces emerging phrases the show itself is using).
    try:
        tracker = load_narrative_tracker(output_dir, cfg)
        narrative_text = build_narrative_status_block(tracker, cfg.label).lower()
        words = [
            w for w in re.findall(r"\b[a-z]{4,}\b", narrative_text)
            if w not in {"status", "last", "major", "update", "episode", "date"}
        ]
        for i in range(len(words) - 1):
            bigram = f"{words[i]} {words[i+1]}"
            if len(bigram) > 8:
                themes[bigram] = themes.get(bigram, 0) + 1
    except Exception:  # noqa: BLE001
        pass

    sorted_themes = dict(sorted(themes.items(), key=lambda x: x[1], reverse=True)[:30])
    history["recurring_themes"] = sorted_themes
    history.setdefault("theme_evolution", []).append({
        "episode": episode_num,
        "top_themes": list(sorted_themes.keys())[:8],
    })
    save_theme_history(history, output_dir, cfg)


# ---------------------------------------------------------------------------
# Composed prompt section (single placeholder, empty == true no-op)
# ---------------------------------------------------------------------------

_SECTION_INSTRUCTIONS = (
    "MANDATORY CONTINUITY (use, do not read aloud): when a story touches one of the "
    "tracked programs above, add 1-2 natural sentences of where today's development fits "
    "in the ongoing arc and whether it moves any of the key open questions. Treat the "
    "memory as long-term context — surface evolving progress instead of treating each day "
    "in isolation. Never narrate these notes or program names as a list; weave them in."
)


def build_memory_section(output_dir: Path, cfg: MemoryConfig) -> str:
    """Compose the full narrative-memory section for prompt injection.

    Returns a single string (header + non-empty blocks + continuity
    instructions), or ``""`` when nothing is tracked yet. Because it collapses
    to an empty string, a show with memory disabled or with empty trackers
    injects *nothing* — the prompt renders exactly as before.
    """
    ctx = get_memory_context(output_dir, cfg)
    parts = [b for b in (
        ctx["narrative_status_block"],
        ctx["performance_signals_block"],
        ctx["theme_context_block"],
    ) if b]
    if not parts:
        return ""
    header = f"### {cfg.label} NARRATIVE & PERFORMANCE MEMORY (high priority — continuity + listener value)"
    return "\n".join([header, "", *parts, "", _SECTION_INSTRUCTIONS])


# ---------------------------------------------------------------------------
# Generic hook helpers (thin per-show hooks call these)
# ---------------------------------------------------------------------------

# The single template-var key the digest/podcast prompts reference.
SECTION_VAR = "narrative_memory_section"


def memory_pre_fetch(config, slug: str) -> Dict[str, str]:
    """Return ``{SECTION_VAR: <section>}`` for a show's pre_fetch hook.

    Always returns the key (empty string when memory is disabled / unconfigured /
    empty) so the prompt's ``{narrative_memory_section}`` placeholder never
    KeyErrors. Gated on ``config.memory_enabled``.
    """
    if not getattr(config, "memory_enabled", False):
        return {SECTION_VAR: ""}
    cfg = get_config(slug)
    if cfg is None:
        return {SECTION_VAR: ""}
    try:
        out_dir = Path(config.episode.output_dir)
        return {SECTION_VAR: build_memory_section(out_dir, cfg)}
    except Exception as exc:  # noqa: BLE001
        logger.warning("%s memory pre_fetch failed (non-fatal): %s", slug, exc)
        return {SECTION_VAR: ""}


def memory_post_generate(config, slug: str, digest_text: str, episode_num: int) -> None:
    """Mine themes from the just-generated digest into the show's theme history.

    No-op unless ``config.memory_enabled`` and the show is configured.
    """
    if not getattr(config, "memory_enabled", False):
        return
    cfg = get_config(slug)
    if cfg is None:
        return
    try:
        out_dir = Path(config.episode.output_dir)
        update_theme_history_from_digest(out_dir, cfg, digest_text, episode_num)
    except Exception as exc:  # noqa: BLE001
        logger.warning("%s memory post_generate failed (non-fatal): %s", slug, exc)


# ---------------------------------------------------------------------------
# Per-show memory configuration registry
# ---------------------------------------------------------------------------

def get_config(slug: str):
    """Return the MemoryConfig for a show slug, or None if it has none."""
    return SHOW_MEMORY_CONFIGS.get(slug)


def _prog(display_name: str, status: str, questions: List[str], confidence: str = "medium") -> Dict[str, Any]:
    return {
        "display_name": display_name,
        "status": status,
        "last_major_update_episode": None,
        "last_major_update_date": "",
        "key_open_questions": questions,
        "show_confidence": confidence,
        "notable_claims": [],
    }


SHOW_MEMORY_CONFIGS: Dict[str, MemoryConfig] = {
    "models_agents": MemoryConfig(
        slug="models_agents",
        label="MODELS & AGENTS",
        file_prefix="models_agents",
        default_programs={
            "frontier_llms": _prog(
                "Frontier Models",
                "Closed frontier models (GPT, Claude, Gemini, Grok) trading capability and price leads.",
                ["Next frontier release cadence", "Capability gains vs cost trajectory"],
            ),
            "open_weights": _prog(
                "Open-Weight Models",
                "Open-weight families (Llama, Mistral, Qwen, DeepSeek, Gemma) narrowing the gap with closed frontier.",
                ["Open vs closed performance gap", "Licensing / commercial terms"],
            ),
            "agentic_systems": _prog(
                "Agents & Tool Use",
                "Autonomous agents, tool use, and the MCP / interoperability layer maturing.",
                ["Reliability of long-horizon agents", "Standardization of agent/tool protocols"],
                confidence="low-medium",
            ),
            "reasoning_models": _prog(
                "Reasoning Models",
                "Reasoning / 'thinking' models and test-time compute.",
                ["Reasoning cost vs benefit", "Benchmark gains vs real-world value"],
            ),
            "ai_compute": _prog(
                "AI Compute & Inference",
                "AI hardware and inference economics (NVIDIA, custom silicon, falling token costs).",
                ["Inference cost curve", "Compute supply constraints"],
            ),
            "ai_safety_policy": _prog(
                "Safety & Policy",
                "AI safety, evaluation, and regulation.",
                ["US/EU regulatory trajectory", "Evaluation / safety standardization"],
                confidence="low",
            ),
        },
        theme_keywords=[
            "gpt", "claude", "gemini", "grok", "llama", "mistral", "qwen", "deepseek",
            "agent", "mcp", "reasoning", "inference", "fine-tun", "open-weight", "open weight",
            "benchmark", "multimodal", "context window", "rag", "embedding", "nvidia", "gpu",
            "safety", "alignment", "training", "tokens", "open source",
        ],
    ),
    "fascinating_frontiers": MemoryConfig(
        slug="fascinating_frontiers",
        label="FASCINATING FRONTIERS",
        file_prefix="fascinating_frontiers",
        default_programs={
            "starship_mars": _prog(
                "Starship & Mars",
                "SpaceX Starship development and the long path toward Mars.",
                ["Orbital refueling + rapid reuse cadence", "Crewed Mars timeline"],
                confidence="low-medium",
            ),
            "artemis_moon": _prog(
                "Artemis & the Moon",
                "NASA Artemis and the crewed return to the Moon.",
                ["Crewed landing schedule", "Lander + Gateway readiness"],
            ),
            "jwst_exoplanets": _prog(
                "JWST & Exoplanets",
                "JWST observations and exoplanet / atmosphere characterization.",
                ["Biosignature detection prospects", "Early-universe galaxy findings"],
            ),
            "commercial_spaceflight": _prog(
                "Commercial Spaceflight",
                "Commercial LEO, constellations, and private crewed flight.",
                ["Commercial station succession to ISS", "Launch cadence + cost"],
            ),
            "deep_space_probes": _prog(
                "Robotic Exploration",
                "Robotic exploration: Mars rovers, sample return, and outer-planet missions.",
                ["Mars Sample Return path", "Ocean-world (Europa/Enceladus) findings"],
            ),
            "cosmology_astrophysics": _prog(
                "Cosmology & Astrophysics",
                "Cosmology, black holes, gravitational waves, and dark matter/energy.",
                ["Hubble-tension resolution", "Dark matter / energy constraints"],
                confidence="low",
            ),
        },
        theme_keywords=[
            "starship", "spacex", "mars", "artemis", "moon", "lunar", "nasa", "jwst", "webb",
            "exoplanet", "telescope", "rocket", "launch", "orbit", "satellite", "rover",
            "asteroid", "comet", "black hole", "galaxy", "gravitational wave", "dark matter",
            "dark energy", "cosmolog", "probe", "mission", "astronaut", "neutron star",
        ],
    ),
    "planetterrian": MemoryConfig(
        slug="planetterrian",
        label="PLANETTERRIAN",
        file_prefix="planetterrian",
        default_programs={
            "aging_biology": _prog(
                "Aging & Longevity Biology",
                "Cellular aging, senescence, and interventions that target the biology of aging.",
                ["Which interventions translate to humans", "Reliable aging biomarkers"],
                confidence="low-medium",
            ),
            "neuroscience_brain": _prog(
                "Neuroscience & the Brain",
                "Cognition, brain aging, and neurodegeneration.",
                ["Alzheimer's mechanism + therapy progress", "How reversible is brain aging"],
            ),
            "microbiome": _prog(
                "Microbiome",
                "The gut microbiome and its links to health and disease.",
                ["Causation vs correlation", "Therapeutic microbiome modulation"],
                confidence="low",
            ),
            "regenerative_medicine": _prog(
                "Regenerative Medicine",
                "Stem cells, cellular reprogramming, and tissue regeneration.",
                ["Partial-reprogramming safety", "Organ/tissue regeneration timelines"],
                confidence="low",
            ),
            "sleep_metabolic": _prog(
                "Sleep, Circadian & Metabolic Health",
                "Sleep, circadian biology, and metabolic health.",
                ["Sleep's causal role in aging/disease", "Circadian interventions that work"],
            ),
            "genetics_genomics": _prog(
                "Genetics & Genomics",
                "Genetics, gene editing, and the genomics of health.",
                ["In-vivo gene-editing safety/efficacy", "Polygenic risk in practice"],
            ),
        },
        theme_keywords=[
            "aging", "longevity", "senescen", "senolytic", "neuroscience", "brain", "cogniti",
            "alzheimer", "neurodegenerat", "microbiome", "gut", "stem cell", "reprogramming",
            "regenerat", "sleep", "circadian", "metabolic", "genetic", "genom", "gene editing",
            "crispr", "epigenetic", "mitochond", "inflammation", "nutrition", "clinical trial",
        ],
    ),
}

