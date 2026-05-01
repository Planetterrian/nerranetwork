"""Episode cost and usage tracking for the podcast generation pipeline.

Provides:
  - create_tracker(): initialize a per-episode usage tracking dict
  - record_llm_usage(): record LLM token usage for a generation step
  - record_tts_usage(): record TTS character count
  - record_x_post(): increment X API post counter
  - save_usage(): finalize costs and write JSON file
"""

import datetime
import json
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

# TTS pricing per 1000 characters, by provider.
# - ElevenLabs Flash v2.5: $0.15/1K chars  (0.5 credits/char × $0.30/1K credits)
# - Grok TTS (xAI /v1/tts): $0.0042/1K chars ($4.20 per 1M chars, ~36× cheaper
#   than ElevenLabs Flash; introduced April 2026, used for the Russian shows
#   since May 2026).
ELEVENLABS_COST_PER_1K_CHARS = 0.15
GROK_TTS_COST_PER_1K_CHARS = 0.0042

TTS_PROVIDER_PRICING = {
    "elevenlabs": ELEVENLABS_COST_PER_1K_CHARS,
    "grok": GROK_TTS_COST_PER_1K_CHARS,
}

# xAI Grok pricing per 1M tokens (input/output).
# Only models actually reachable by the current code are listed — historical
# ids (grok-2, grok-3, grok-3-mini, grok-4.20-0309-*) were pruned April 2026
# once the audit confirmed no live call site resolves to them.
GROK_PRICING = {
    # Grok 4.3 — current network default (released 2026-04-30). Always-on
    # reasoning, 1M context, ~37% cheaper input and ~58% cheaper output
    # than grok-4.20 at the same or better intelligence tier.
    "grok-4.3": {"input_per_1m": 1.25, "output_per_1m": 2.50},
    # Grok 4 (legacy refusal fallback — retained because older
    # credit_usage JSONs still report it, and _estimate_grok_cost may be
    # re-run against them).
    "grok-4": {"input_per_1m": 3.00, "output_per_1m": 15.00},
    # Grok 4.20 — superseded by 4.3 as default but retained because
    # historical credit_usage JSONs reference these ids and the multi-agent
    # variant is still used for the tool-use (web/x_search) path.
    "grok-4.20-non-reasoning": {"input_per_1m": 2.00, "output_per_1m": 6.00},
    "grok-4.20-reasoning": {"input_per_1m": 2.00, "output_per_1m": 6.00},
    "grok-4.20-multi-agent": {"input_per_1m": 2.00, "output_per_1m": 6.00},
    # Dated beta snapshot — still referenced in ~40 historical usage JSONs
    "grok-4.20-beta-0309-non-reasoning": {"input_per_1m": 2.00, "output_per_1m": 6.00},
    # Grok 4.1 Fast — reviewer
    "grok-4-1-fast-non-reasoning": {"input_per_1m": 0.20, "output_per_1m": 0.50},
    "grok-4-1-fast-reasoning": {"input_per_1m": 0.20, "output_per_1m": 0.50},
}


def create_tracker(show_name: str, episode_num: int) -> dict:
    """Create a fresh per-episode usage tracker."""
    return {
        "date": datetime.date.today().isoformat(),
        "show": show_name,
        "episode_number": episode_num,
        "services": {
            "grok_api": {
                "model": "",
                "x_thread_generation": {
                    "prompt_tokens": 0,
                    "completion_tokens": 0,
                    "total_tokens": 0,
                    "estimated_cost_usd": 0.0,
                },
                "podcast_script_generation": {
                    "prompt_tokens": 0,
                    "completion_tokens": 0,
                    "total_tokens": 0,
                    "estimated_cost_usd": 0.0,
                },
                "total_tokens": 0,
                "total_cost_usd": 0.0,
            },
            "tts_api": {
                "provider": "elevenlabs",
                "characters": 0,
                "estimated_cost_usd": 0.0,
            },
            "x_api": {
                "search_calls": 0,
                "post_calls": 0,
                "total_calls": 0,
            },
        },
        "refusal_fallbacks": {
            "count": 0,
            "events": [],  # list of {"stage": ..., "model": ...}
        },
        "total_estimated_cost_usd": 0.0,
    }


def record_refusal_fallback(tracker: dict, stage: str, model: str) -> None:
    """Record that the refusal-fallback model fired for a given stage.

    Spikes in this counter are a cost signal (fallback model may be priced
    differently) and a prompt-regression signal (primary is refusing more
    often). Keeping a structured event log is cheaper than parsing tracker
    step names after the fact.
    """
    rf = tracker.setdefault(
        "refusal_fallbacks", {"count": 0, "events": []}
    )
    rf["count"] = int(rf.get("count", 0)) + 1
    rf.setdefault("events", []).append({"stage": stage, "model": model})


def _estimate_grok_cost(
    model: str, prompt_tokens: int, completion_tokens: int
) -> float:
    """Estimate cost for a Grok API call based on model pricing."""
    pricing = GROK_PRICING.get(model)
    if not pricing:
        return 0.0
    input_cost = (prompt_tokens / 1_000_000) * pricing["input_per_1m"]
    output_cost = (completion_tokens / 1_000_000) * pricing["output_per_1m"]
    return input_cost + output_cost


def record_llm_usage(
    tracker: dict,
    step: str,
    prompt_tokens: int,
    completion_tokens: int,
    estimated_cost_usd: float = 0.0,
    model: str = "",
) -> None:
    """Record LLM token usage for a generation step.

    *step* should be ``"x_thread_generation"`` or
    ``"podcast_script_generation"``.

    If *estimated_cost_usd* is 0 and *model* is provided, cost is
    estimated from the Grok pricing table.
    """
    grok = tracker["services"]["grok_api"]
    if model:
        grok["model"] = model
    if step not in grok:
        grok[step] = {
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "total_tokens": 0,
            "estimated_cost_usd": 0.0,
        }
    grok[step]["prompt_tokens"] += prompt_tokens
    grok[step]["completion_tokens"] += completion_tokens
    grok[step]["total_tokens"] += prompt_tokens + completion_tokens

    if estimated_cost_usd > 0:
        grok[step]["estimated_cost_usd"] += estimated_cost_usd
    elif model:
        grok[step]["estimated_cost_usd"] += _estimate_grok_cost(
            model, prompt_tokens, completion_tokens
        )


def record_tts_usage(
    tracker: dict, characters: int, provider: str = "elevenlabs"
) -> None:
    """Record TTS character usage."""
    tts = tracker["services"]["tts_api"]
    tts["provider"] = provider
    tts["characters"] += characters


def record_x_post(tracker: dict) -> None:
    """Increment the X API post counter."""
    tracker["services"]["x_api"]["post_calls"] += 1


def save_usage(tracker: dict, output_dir: Path) -> Path | None:
    """Finalize cost calculations and write the tracker to a JSON file.

    Returns the path to the saved file, or ``None`` on error.
    """
    try:
        grok = tracker["services"]["grok_api"]
        # Sum up LLM totals
        grok["total_tokens"] = (
            grok["x_thread_generation"]["total_tokens"]
            + grok["podcast_script_generation"]["total_tokens"]
        )
        grok["total_cost_usd"] = (
            grok["x_thread_generation"]["estimated_cost_usd"]
            + grok["podcast_script_generation"]["estimated_cost_usd"]
        )

        x_api = tracker["services"]["x_api"]
        x_api["total_calls"] = x_api["search_calls"] + x_api["post_calls"]

        # TTS cost — rate depends on provider (ElevenLabs vs Grok TTS;
        # Grok is ~36× cheaper per character so the provider switch matters
        # for accurate per-episode cost reporting).
        tts = tracker["services"]["tts_api"]
        provider = tts.get("provider", "elevenlabs")
        rate_per_1k = TTS_PROVIDER_PRICING.get(provider, ELEVENLABS_COST_PER_1K_CHARS)
        tts["estimated_cost_usd"] = (tts["characters"] / 1000) * rate_per_1k

        # Also keep legacy key for backward compatibility (the dashboard
        # historically read `services.elevenlabs_api`; we mirror the tts
        # block under that key regardless of provider so that path keeps
        # working).
        if "elevenlabs_api" not in tracker["services"]:
            tracker["services"]["elevenlabs_api"] = tts

        tracker["total_estimated_cost_usd"] = (
            grok["total_cost_usd"] + tts["estimated_cost_usd"]
        )

        # Write file
        filename = f"credit_usage_{tracker['date']}_ep{tracker['episode_number']:03d}.json"
        filepath = output_dir / filename
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(tracker, f, indent=2)

        # Log summary
        logger.info("=" * 60)
        logger.info("CREDIT USAGE SUMMARY")
        logger.info("=" * 60)
        logger.info(
            "Grok API [%s] (X Thread): %d tokens ($%.4f)",
            grok.get("model", "unknown"),
            grok["x_thread_generation"]["total_tokens"],
            grok["x_thread_generation"]["estimated_cost_usd"],
        )
        logger.info(
            "Grok API [%s] (Podcast): %d tokens ($%.4f)",
            grok.get("model", "unknown"),
            grok["podcast_script_generation"]["total_tokens"],
            grok["podcast_script_generation"]["estimated_cost_usd"],
        )
        logger.info(
            "TTS (%s): %d chars ($%.4f)",
            provider,
            tts["characters"],
            tts["estimated_cost_usd"],
        )
        logger.info(
            "X API: %d calls (search: %d, post: %d)",
            x_api["total_calls"],
            x_api["search_calls"],
            x_api["post_calls"],
        )
        rf = tracker.get("refusal_fallbacks") or {}
        if rf.get("count"):
            logger.warning(
                "Refusal fallback fired %d time(s): %s",
                rf["count"],
                ", ".join(f"{e['stage']}->{e['model']}" for e in rf.get("events", [])),
            )
        logger.info("TOTAL ESTIMATED COST: $%.4f", tracker["total_estimated_cost_usd"])
        logger.info("=" * 60)
        logger.info("Credit usage saved to %s", filepath)

        return filepath

    except Exception as exc:
        logger.error("Failed to save credit usage: %s", exc, exc_info=True)
        return None
