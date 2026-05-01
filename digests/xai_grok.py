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


def _get_xai_api_key() -> str:
    return (os.getenv("GROK_API_KEY") or os.getenv("XAI_API_KEY") or "").strip()


def grok_generate_text(
    *,
    prompt: str,
    model: str = "grok-4.3",
    temperature: float = 0.7,
    max_tokens: int = 3500,
    timeout_seconds: float = 3600.0,
    enable_web_search: bool = False,
    enable_x_search: bool = False,
    x_handles: Optional[List[str]] = None,
    max_turns: Optional[int] = None,
) -> Tuple[str, Dict[str, Any]]:
    """Generate text from Grok.

    When search tools are requested, uses the Responses API
    (``client.responses.create``) with ``x_search`` / ``web_search``
    built-in tools.  Otherwise uses Chat Completions.

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
            resp = client.responses.create(
                model=model,
                input=[{"role": "user", "content": prompt}],
                tools=tools,
            )
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
    resp = client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": prompt}],
        temperature=temperature,
        max_tokens=max_tokens,
    )
    text = resp.choices[0].message.content.strip()
    return text, {"provider": "openai_compat", "model": model, "usage": getattr(resp, "usage", None)}
