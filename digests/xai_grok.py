"""
xAI Grok helper for this repo.

Uses the Responses API (``/v1/responses``) for search tool calls
(x_search, web_search) and the Chat Completions API for plain
generation. The deprecated gRPC SearchParameters path has been removed.
"""

from __future__ import annotations

import os
import logging
from typing import Any, Dict, List, Optional, Tuple

from tenacity import (
    before_sleep_log,
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

logger = logging.getLogger(__name__)

# Capacity-class failures from xAI (429 "model at capacity", 503 during
# incidents) recover on the minutes scale — the OpenAI SDK's built-in
# sub-second retries alone are not enough (July 21 2026: the Tesla X-post
# fetch drew back-to-back 503s on /responses during the same incident
# that empty-digested SpaceX). Mirror engine.generator._call_grok's long
# backoff: 30s -> 60s -> 120s across four attempts.
try:
    from openai import RateLimitError, InternalServerError
    _CAPACITY_ERRORS: tuple = (RateLimitError, InternalServerError)
except ImportError:  # pragma: no cover — openai always present in prod
    _CAPACITY_ERRORS = ()

_capacity_retry = retry(
    stop=stop_after_attempt(4),
    wait=wait_exponential(multiplier=30, min=30, max=120),
    retry=retry_if_exception_type(_CAPACITY_ERRORS),
    before_sleep=before_sleep_log(logger, logging.WARNING),
    reraise=True,
)


@_capacity_retry
def _responses_create(client, **create_kwargs):
    return client.responses.create(**create_kwargs)


@_capacity_retry
def _chat_create(client, **create_kwargs):
    return client.chat.completions.create(**create_kwargs)


def _get_xai_api_key() -> str:
    return (os.getenv("GROK_API_KEY") or os.getenv("XAI_API_KEY") or "").strip()


# ---------------------------------------------------------------------------
# Search-tool usage accounting
# ---------------------------------------------------------------------------
# xAI bills server-side search tools per SOURCE consulted, on top of the
# usual token cost. Several shows run these every day (the per-account X
# fetch alone is one call per configured handle), and none of it reached
# the episode's credit summary — the Responses path returned only the
# text, so ``credit_usage_*.json`` undercounted every search-fetching show.
#
# The fetch layer has no tracker reference (``engine/fetcher`` is called
# long before the episode tracker is threaded through), so usage lands in
# a process-wide accumulator that run_show drains once per episode — the
# same shape ``engine/grok_imagine`` uses for image spend.
_SEARCH_USAGE: Dict[str, Any] = {
    "calls": 0, "sources": 0, "input_tokens": 0, "output_tokens": 0,
}


def _int_attr(obj: Any, *names: str) -> int:
    """First present int-ish attribute/key among *names*, else 0.

    xAI's Responses usage object is not pinned by a public schema and has
    carried both ``num_sources_used`` and ``sources_used`` in the wild, so
    read defensively rather than guessing one name.
    """
    for name in names:
        value = None
        if isinstance(obj, dict):
            value = obj.get(name)
        else:
            value = getattr(obj, name, None)
        if isinstance(value, (int, float)):
            return int(value)
    return 0


def _record_search_usage(resp: Any, tool_count: int) -> None:
    """Accumulate one Responses-API call's billable usage."""
    usage = getattr(resp, "usage", None)
    _SEARCH_USAGE["calls"] += 1
    _SEARCH_USAGE["input_tokens"] += _int_attr(
        usage, "input_tokens", "prompt_tokens")
    _SEARCH_USAGE["output_tokens"] += _int_attr(
        usage, "output_tokens", "completion_tokens")
    sources = _int_attr(usage, "num_sources_used", "sources_used")
    if not sources:
        # Some responses report the count under server_side_tool_use
        # instead of at the usage root.
        nested = getattr(usage, "server_side_tool_use", None)
        sources = _int_attr(nested, "num_sources_used", "sources_used")
    _SEARCH_USAGE["sources"] += sources
    if sources:
        logger.info("Responses API: %d source(s) billed across %d tool(s)",
                    sources, tool_count)


def drain_search_usage() -> Dict[str, int]:
    """Return the accumulated search usage and reset the accumulator.

    Draining (rather than peeking) keeps a long-lived process — the daily
    audit retry path runs several shows back to back — from charging one
    show for another's searches.
    """
    snapshot = {k: int(v) for k, v in _SEARCH_USAGE.items()}
    for key in _SEARCH_USAGE:
        _SEARCH_USAGE[key] = 0
    return snapshot


def grok_generate_text(
    *,
    prompt: str,
    model: str = "grok-4.6",
    temperature: float = 0.7,
    max_tokens: int = 3500,
    timeout_seconds: float = 3600.0,
    enable_web_search: bool = False,
    enable_x_search: bool = False,
    x_handles: Optional[List[str]] = None,
    max_turns: Optional[int] = None,
    cache_key: Optional[str] = None,
) -> Tuple[str, Dict[str, Any]]:
    """Generate text from Grok.

    When search tools are requested, uses the Responses API
    (``client.responses.create``) with ``x_search`` / ``web_search``
    built-in tools.  Otherwise uses Chat Completions.

    *cache_key* (optional) sticky-routes for prompt-cache reuse: Chat
    Completions via ``x-grok-conv-id``, Responses via ``prompt_cache_key``.

    Returns ``(text, meta)``.
    """
    api_key = _get_xai_api_key()
    if not api_key:
        raise RuntimeError("Missing GROK_API_KEY (or XAI_API_KEY).")

    want_search = bool(enable_web_search or enable_x_search)

    if want_search:
        from openai import OpenAI
        client = OpenAI(
            api_key=api_key,
            base_url="https://api.x.ai/v1",
            timeout=timeout_seconds,
        )

        tools: List[Dict[str, Any]] = []
        if enable_x_search:
            x_tool: Dict[str, Any] = {"type": "x_search"}
            if x_handles:
                x_tool["filters"] = {
                    "allowed_x_handles": [h.lstrip("@") for h in x_handles],
                }
            tools.append(x_tool)
        if enable_web_search:
            tools.append({"type": "web_search"})

        logging.info(
            "Responses API: calling %s with %d tools, x_handles=%s",
            model, len(tools), x_handles or "all",
        )

        try:
            create_kwargs: Dict[str, Any] = {
                "model": model,
                "input": [{"role": "user", "content": prompt}],
                "tools": tools,
            }
            if cache_key:
                # Responses API sticky routing (same role as x-grok-conv-id).
                create_kwargs["extra_body"] = {
                    "prompt_cache_key": str(cache_key),
                }
            resp = _responses_create(client, **create_kwargs)
            try:
                _record_search_usage(resp, len(tools))
            except Exception:  # pragma: no cover — accounting is never fatal
                logger.debug("search usage accounting failed", exc_info=True)
            text = getattr(resp, "output_text", "") or ""
            text = text.strip()
            logging.info(
                "Responses API: got %d chars from %s (first 300: %s)",
                len(text), model, text[:300].replace("\n", " "),
            )
            return text, {"provider": "openai_responses", "model": model}

        except Exception as exc:
            logging.error(
                "Responses API failed: %s — %s. Falling back to plain generation.",
                type(exc).__name__, str(exc)[:300],
            )

    # Plain generation: Chat Completions (no search tools).
    from openai import OpenAI
    client = OpenAI(
        api_key=api_key,
        base_url="https://api.x.ai/v1",
        timeout=timeout_seconds,
    )
    create_kwargs = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": temperature,
        "max_tokens": max_tokens,
    }
    if cache_key:
        create_kwargs["extra_headers"] = {"x-grok-conv-id": str(cache_key)}
    resp = _chat_create(client, **create_kwargs)
    text = (resp.choices[0].message.content or "").strip()
    return text, {"provider": "openai_compat", "model": model, "usage": getattr(resp, "usage", None)}
