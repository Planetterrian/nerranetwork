#!/usr/bin/env python3
"""Probe xAI's x_search tool shapes (Oct 12 2026). Read-only diagnostic.

Why: on the 10-12 slate @SpaceX, @NASASpaceflight and @xai each came back
NO_RECENT_POSTS from the per-account fetch, and the @grok research-desk call
(engine.grok_leads) answered NO_LEADS on all four shows in ~7 s. Both send
``{"type": "x_search", "filters": {"allowed_x_handles": [...]}}`` — the
web_search nesting — and give the search no date window, only the prompt's
"last 24 hours". xAI's public docs name the x_search parameters
(allowed_x_handles, excluded_x_handles, from_date, to_date) without showing
where they sit in a raw Responses request, so this asks the API directly.

For each handle it sends the same prompt with four tool shapes and prints:
HTTP status (an error body verbatim), the number of x_search calls the model
made, the distinct post authors in the answer, and its first characters.
Nothing is written anywhere. Needs GROK_API_KEY (or XAI_API_KEY).
"""
from __future__ import annotations

import datetime as dt
import json
import os
import re
import sys
import urllib.error
import urllib.request

API = "https://api.x.ai/v1/responses"
MODEL = os.getenv("PROBE_MODEL", "grok-4.3")

ACCOUNT_PROMPT = (
    "Search X/Twitter for the most recent posts from @{h} in the last 24 hours.\n\n"
    "Return ONLY a structured list, one block per post:\n"
    "POST_URL: [https://x.com/{h}/status/...]\nPOST_DATE: [YYYY-MM-DD]\n"
    "POST_TEXT: [first 80 characters]\n\n"
    "Up to 5 posts. If none, return exactly: NO_RECENT_POSTS"
)
GROK_PROMPT = (
    "Search X for replies posted by @grok in the last 48 hours in which Grok "
    "answers a question about: SpaceX engineering and history — Starship, "
    "Raptor, Falcon 9, Dragon, Starlink, reusability.\n\n"
    "Return one block per reply:\nLEAD_URL: [https://x.com/grok/status/...]\n"
    "LEAD_QUESTION: [one sentence]\n\nUp to 4. If none qualify, return exactly: NO_LEADS"
)


def _shapes(handle: str, since: str) -> list:
    return [
        ("A filters (current)", {"type": "x_search", "filters": {"allowed_x_handles": [handle]}}),
        ("B top-level", {"type": "x_search", "allowed_x_handles": [handle]}),
        ("C top-level + from_date", {"type": "x_search", "allowed_x_handles": [handle],
                                     "from_date": since}),
        ("D no handle filter", {"type": "x_search"}),
    ]


def _post(key: str, body: dict) -> tuple:
    req = urllib.request.Request(
        API, data=json.dumps(body).encode(),
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=180) as r:
            return r.status, json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode()[:400]
    except Exception as e:  # noqa: BLE001 — a probe reports, never raises
        return -1, f"{type(e).__name__}: {e}"


def _summarise(status, data) -> str:
    if status != 200 or not isinstance(data, dict):
        return f"HTTP {status}: {data}"
    items = data.get("output") or []
    kinds = [i.get("type") for i in items]
    calls = sum(1 for k in kinds if k and "search" in k)
    text = ""
    for i in items:
        for c in i.get("content") or []:
            if c.get("type") in ("output_text", "text"):
                text += c.get("text", "")
    authors = sorted(set(re.findall(r"x\.com/([A-Za-z0-9_]+)/status", text)))
    usage = data.get("usage") or {}
    tools = usage.get("server_side_tool_usage_details") or usage.get("num_server_side_tools_used")
    return (f"HTTP 200 | search calls {calls} | tool usage {tools} | authors {authors} | "
            f"{len(text)} chars | {text[:160]!r}")


def main() -> int:
    key = (os.getenv("GROK_API_KEY") or os.getenv("XAI_API_KEY") or "").strip()
    if not key:
        print("::error::no GROK_API_KEY — nothing probed")
        return 1
    since = (dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=2)).date().isoformat()
    for handle, prompt in (("SpaceX", ACCOUNT_PROMPT.format(h="SpaceX")),
                           ("NASASpaceflight", ACCOUNT_PROMPT.format(h="NASASpaceflight")),
                           ("grok", GROK_PROMPT)):
        print(f"\n=== @{handle} ===")
        for label, tool in _shapes(handle, since):
            status, data = _post(key, {"model": MODEL, "tools": [tool],
                                       "input": [{"role": "user", "content": prompt}]})
            print(f"{label:24s} {_summarise(status, data)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
