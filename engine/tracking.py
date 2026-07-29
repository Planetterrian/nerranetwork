"""Episode cost and usage tracking for the podcast generation pipeline.

Provides:
  - create_tracker(): initialize a per-episode usage tracking dict
  - record_llm_usage(): record LLM token usage for a generation step
  - record_tts_usage(): record TTS character count
  - record_x_post(): increment X API post counter
  - save_usage(): finalize costs and write JSON file
"""

import datetime
import os
import json
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

# TTS pricing per 1000 characters, by provider.
# - ElevenLabs Flash v2.5: $0.15/1K chars  (0.5 credits/char × $0.30/1K credits)
# - Grok TTS (xAI /v1/tts): public list price as of July 2026 is
#   $15.00 per 1M chars ($0.015/1K) — see docs.x.ai Voice pricing.
#   Earlier network tracking used $4.20/M (April–June 2026 promo-era
#   figure); dashboard costs for NEW episodes use the list rate so
#   Mission Control isn't systematically understating TTS spend.
#   Still ~10× cheaper than ElevenLabs Flash ($150/M).
ELEVENLABS_COST_PER_1K_CHARS = 0.15
GROK_TTS_COST_PER_1K_CHARS = 0.015

# Human-readable labels for the recorded LLM steps. The KEYS are frozen
# for back-compat (the dashboard and every historical credit_usage JSON
# use them); only the display label is corrected here.
_STEP_LABELS = {
    "x_thread_generation": "Digest",
    # Output that was generated, billed, and thrown away because it hit
    # max_tokens. A persistently non-zero line here means the show's
    # llm.max_tokens is set below what its prompt actually needs.
    "x_thread_generation_truncated": "Digest (truncated, discarded)",
    "podcast_script_generation_truncated": "Podcast script (truncated, discarded)",
    "x_thread_generation_expansion": "Digest expansion retry",
    "x_thread_generation_retry": "Digest retry",
    "x_thread_generation_retry_edu": "Digest retry (edu)",
    "x_thread_generation_retry_fallback_model": "Digest retry (fallback model)",
    "podcast_outline_generation": "Podcast outline",
    "podcast_script_generation": "Podcast script",
    "podcast_script_retry": "Podcast script retry",
    "podcast_script_refusal_retry": "Podcast script refusal retry",
    "podcast_script_refusal_fallback_model": "Podcast script (fallback model)",
    "podcast_script_anti_repetition_retry": "Podcast anti-repetition retry",
}

TTS_PROVIDER_PRICING = {
    "elevenlabs": ELEVENLABS_COST_PER_1K_CHARS,
    "grok": GROK_TTS_COST_PER_1K_CHARS,
}

# xAI server-side search tools are billed per SOURCE consulted (xAI's
# published Agent Tools rate is $25 per 1,000 sources). Env-overridable
# because it is the one rate here that is not pinned by a model id — if
# xAI moves it, the operator sets XAI_SEARCH_COST_PER_SOURCE rather than
# waiting on a code change. A run that reports no source count costs
# nothing extra beyond its tokens, which is the honest floor.
SEARCH_COST_PER_SOURCE = 0.025

# xAI Grok pricing per 1M tokens (input/output/cached_input).
# Only models actually reachable by the current code are listed — historical
# ids (grok-2, grok-3, grok-3-mini, grok-4.20-0309-*) were pruned April 2026
# once the audit confirmed no live call site resolves to them.
# Cached-input rates (July 2026 docs) apply when usage reports
# prompt_tokens_details.cached_tokens — see _estimate_grok_cost.
GROK_PRICING = {
    # Grok 4.3 — current network default (released 2026-04-30). Always-on
    # reasoning, 1M context. Prefer over 4.5 for daily digests (cheaper +
    # larger context); 4.5 is opt-in for hard agentic paths.
    "grok-4.3": {
        "input_per_1m": 1.25,
        "output_per_1m": 2.50,
        "cached_input_per_1m": 0.20,
    },
    # Grok 4.5 (July 16 2026) — frontier coding/agentic. Higher unit cost,
    # 500k context, reasoning_effort low|medium|high (default high).
    # Wired for selective use; do NOT flip network digest default without
    # a measured A/B (landmine #17 for any prompt-quality change).
    "grok-4.5": {
        "input_per_1m": 2.00,
        "output_per_1m": 6.00,
        "cached_input_per_1m": 0.30,
    },
    # Grok 4 (legacy refusal fallback — retained because older
    # credit_usage JSONs still report it, and _estimate_grok_cost may be
    # re-run against them).
    "grok-4": {"input_per_1m": 3.00, "output_per_1m": 15.00},
    # Grok 4.20 — fully superseded by 4.3 (primary, synth, and tool-use
    # paths all migrated). Pricing entries retained because historical
    # credit_usage JSONs reference these ids; cost re-scoring against
    # those files would silently zero out without these rows.
    # `grok-4.20-reasoning` is also still the configured refusal fallback
    # (genuinely different snapshot from grok-4.3).
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
            # Grok Imagine scene generation. Added July 28 2026 — image
            # spend was the single largest hole in the per-episode
            # figure: grok_imagine.py logged its own cost but nothing
            # ever fed it back to the tracker, so a run that spent
            # ~$0.16 on images reported $0.00 for them.
            "image_api": {
                "provider": "grok-imagine",
                "model": "",
                "images_generated": 0,
                "estimated_cost_usd": 0.0,
            },
            # xAI server-side search tools (x_search / web_search via the
            # Responses API). Billed PER SOURCE consulted on top of
            # tokens. Added July 29 2026 — flagged as uncounted by the
            # July 24 pass and still missing after the July 28 cost fix,
            # so every search-fetching show under-reported its spend.
            "search_api": {
                "provider": "xai",
                "calls": 0,
                "sources": 0,
                "prompt_tokens": 0,
                "completion_tokens": 0,
                "estimated_cost_usd": 0.0,
            },
        },
        # Informational only — render minutes are compute, not a billed
        # API line, but they are the other half of "what did this
        # episode cost" and were invisible before.
        "render": {
            "video_seconds": 0.0,
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
    model: str,
    prompt_tokens: int,
    completion_tokens: int,
    cached_tokens: int = 0,
) -> float:
    """Estimate cost for a Grok API call based on model pricing.

    When *cached_tokens* > 0 and the model row has ``cached_input_per_1m``,
    those tokens are billed at the cached rate and the remainder of
    *prompt_tokens* at the full input rate (xAI prompt-cache accounting).
    """
    pricing = GROK_PRICING.get(model)
    if not pricing:
        return 0.0
    cached = max(0, min(int(cached_tokens or 0), int(prompt_tokens or 0)))
    uncached = max(0, int(prompt_tokens or 0) - cached)
    cached_rate = pricing.get("cached_input_per_1m")
    if cached and cached_rate is not None:
        input_cost = (uncached / 1_000_000) * pricing["input_per_1m"]
        input_cost += (cached / 1_000_000) * float(cached_rate)
    else:
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
    cached_tokens: int = 0,
) -> None:
    """Record LLM token usage for a generation step.

    *step* should be ``"x_thread_generation"`` or
    ``"podcast_script_generation"``.

    If *estimated_cost_usd* is 0 and *model* is provided, cost is
    estimated from the Grok pricing table (including cached-input rates
    when *cached_tokens* is reported).
    """
    grok = tracker["services"]["grok_api"]
    if model:
        grok["model"] = model
    if step not in grok:
        grok[step] = {
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "total_tokens": 0,
            "cached_tokens": 0,
            "estimated_cost_usd": 0.0,
        }
    grok[step]["prompt_tokens"] += prompt_tokens
    grok[step]["completion_tokens"] += completion_tokens
    grok[step]["total_tokens"] += prompt_tokens + completion_tokens
    if cached_tokens:
        grok[step]["cached_tokens"] = (
            int(grok[step].get("cached_tokens", 0) or 0) + int(cached_tokens)
        )
        grok["cached_tokens"] = (
            int(grok.get("cached_tokens", 0) or 0) + int(cached_tokens)
        )

    if estimated_cost_usd > 0:
        grok[step]["estimated_cost_usd"] += estimated_cost_usd
    elif model:
        grok[step]["estimated_cost_usd"] += _estimate_grok_cost(
            model, prompt_tokens, completion_tokens, cached_tokens=cached_tokens
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


def record_image_usage(
    tracker: dict,
    images_generated: int,
    cost_usd: float,
    model: str = "",
    provider: str = "grok-imagine",
) -> None:
    """Record Grok Imagine scene generation.

    ``engine/grok_imagine.py`` already computes the per-batch cost from
    ``MODEL_COST_USD``; this is the missing wire that carries it into
    the episode's credit summary. Callers are additive — a show that
    generates images in several passes (16:9 then 9:16) calls this once
    per pass.
    """
    images = tracker["services"].setdefault(
        "image_api",
        {
            "provider": provider,
            "model": "",
            "images_generated": 0,
            "estimated_cost_usd": 0.0,
        },
    )
    if model:
        images["model"] = model
    images["provider"] = provider
    images["images_generated"] += int(images_generated or 0)
    images["estimated_cost_usd"] += float(cost_usd or 0.0)


def record_search_usage(
    tracker: dict,
    calls: int,
    sources: int,
    prompt_tokens: int = 0,
    completion_tokens: int = 0,
    model: str = "",
) -> None:
    """Record xAI server-side search-tool usage (x_search / web_search).

    ``digests/xai_grok.py`` accumulates this per process because the
    fetch layer has no tracker reference; run_show drains it once per
    episode. Additive — a show that fetches several X accounts drains one
    combined total.

    Token cost is priced through the normal Grok table when *model* is
    known; the per-source fee is the part that was invisible.
    """
    search = tracker["services"].setdefault(
        "search_api",
        {
            "provider": "xai", "calls": 0, "sources": 0,
            "prompt_tokens": 0, "completion_tokens": 0,
            "estimated_cost_usd": 0.0,
        },
    )
    search["calls"] += int(calls or 0)
    search["sources"] += int(sources or 0)
    search["prompt_tokens"] += int(prompt_tokens or 0)
    search["completion_tokens"] += int(completion_tokens or 0)

    try:
        rate = float(
            os.getenv("XAI_SEARCH_COST_PER_SOURCE", "").strip()
            or SEARCH_COST_PER_SOURCE
        )
    except ValueError:
        rate = SEARCH_COST_PER_SOURCE
    cost = int(sources or 0) * rate
    if model and (prompt_tokens or completion_tokens):
        cost += _estimate_grok_cost(model, prompt_tokens, completion_tokens)
    search["estimated_cost_usd"] = round(
        float(search.get("estimated_cost_usd", 0.0) or 0.0) + cost, 6
    )


def record_render_seconds(tracker: dict, seconds: float) -> None:
    """Record video render wall-clock. Informational — never priced."""
    render = tracker.setdefault("render", {"video_seconds": 0.0})
    render["video_seconds"] = round(
        float(render.get("video_seconds", 0.0) or 0.0) + float(seconds or 0.0), 1
    )


def save_usage(tracker: dict, output_dir: Path) -> Path | None:
    """Finalize cost calculations and write the tracker to a JSON file.

    Returns the path to the saved file, or ``None`` on error.
    """
    try:
        grok = tracker["services"]["grok_api"]
        # Sum EVERY recorded step, not just the two original ones.
        #
        # Until July 28 2026 this summed only ``x_thread_generation`` and
        # ``podcast_script_generation`` — so the outline call, every
        # truncation/expansion retry, the anti-repetition retry and the
        # refusal-fallback call were all recorded in the file and then
        # silently dropped from the total. On SpaceX Ep047 that hid 47%
        # of the episode's LLM spend ($0.0269 reported vs $0.0503
        # actually recorded). Retries are exactly the spend an operator
        # needs to see, because they are the part that is fixable.
        steps = [
            (name, value) for name, value in grok.items()
            if isinstance(value, dict) and "estimated_cost_usd" in value
        ]
        grok["total_tokens"] = sum(v.get("total_tokens", 0) or 0 for _, v in steps)
        grok["total_cost_usd"] = sum(
            v.get("estimated_cost_usd", 0.0) or 0.0 for _, v in steps
        )

        x_api = tracker["services"]["x_api"]
        x_api["total_calls"] = x_api["search_calls"] + x_api["post_calls"]

        # TTS cost — rate depends on provider (ElevenLabs vs Grok TTS;
        # Grok is ~36× cheaper per character so the provider switch matters
        # for accurate per-episode cost reporting).
        tts = tracker["services"]["tts_api"]
        # A run that never reached TTS has no recorded provider — label it
        # "none" instead of the legacy "elevenlabs" default, which read as
        # a provider regression on Grok-TTS shows (SpaceX July 21 2026
        # abort log: "TTS (elevenlabs): 0 chars").
        provider = tts.get("provider") or (
            "none" if not tts.get("characters") else "elevenlabs"
        )
        rate_per_1k = TTS_PROVIDER_PRICING.get(provider, ELEVENLABS_COST_PER_1K_CHARS)
        tts["estimated_cost_usd"] = (tts["characters"] / 1000) * rate_per_1k

        # Also keep legacy key for backward compatibility (the dashboard
        # historically read `services.elevenlabs_api`; we mirror the tts
        # block under that key regardless of provider so that path keeps
        # working).
        if "elevenlabs_api" not in tracker["services"]:
            tracker["services"]["elevenlabs_api"] = tts

        images = tracker["services"].get("image_api") or {}
        image_cost = float(images.get("estimated_cost_usd", 0.0) or 0.0)
        search = tracker["services"].get("search_api") or {}
        search_cost = float(search.get("estimated_cost_usd", 0.0) or 0.0)

        tracker["total_estimated_cost_usd"] = (
            grok["total_cost_usd"] + tts["estimated_cost_usd"]
            + image_cost + search_cost
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
        # One line per step. The ``x_thread_generation`` KEY is retained
        # for dashboard/back-compat, but it has always held the DIGEST
        # call — it is written on every run, including the majority of
        # shows that post nothing to X — so the label said "X Thread"
        # on runs with zero X calls. Label from the work, not the key.
        for name, value in sorted(steps, key=lambda kv: -kv[1].get("estimated_cost_usd", 0.0)):
            logger.info(
                "Grok API [%s] (%s): %d tokens ($%.4f)",
                grok.get("model", "unknown"),
                _STEP_LABELS.get(name, name.replace("_", " ")),
                value.get("total_tokens", 0) or 0,
                value.get("estimated_cost_usd", 0.0) or 0.0,
            )
        logger.info(
            "TTS (%s): %d chars ($%.4f)",
            provider,
            tts["characters"],
            tts["estimated_cost_usd"],
        )
        if images.get("images_generated") or image_cost:
            logger.info(
                "Images (%s): %d images ($%.4f)",
                images.get("model") or images.get("provider", "grok-imagine"),
                images.get("images_generated", 0) or 0,
                image_cost,
            )
        if search.get("calls") or search_cost:
            logger.info(
                "Search tools (xAI): %d call(s), %d source(s) ($%.4f)",
                search.get("calls", 0) or 0,
                search.get("sources", 0) or 0,
                search_cost,
            )
        render_seconds = float(
            (tracker.get("render") or {}).get("video_seconds", 0.0) or 0.0
        )
        if render_seconds:
            logger.info(
                "Video render: %.1f min (compute, not billed)", render_seconds / 60
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
