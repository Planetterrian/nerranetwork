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


OLD_LEAD_PROMPT = (  # the Oct 11 prompt, verbatim shape, for comparison
    "Search X for replies posted by @grok in the last {h} hours "
    "in which Grok answers a question about: {topics}.\n\n"
    "Choose EXPLANATIONS only — how or why something works, its history, "
    "the engineering, physics or economics behind it, or a comparison of "
    "two programs. Skip price or date predictions, jokes, opinions about a "
    "person, roleplay, image requests, and anything off the topics above.\n\n"
    "Return ONLY a structured list, one block per reply, separated by blank "
    "lines:\n\nLEAD_QUESTION: [the question Grok was answering, in one plain sentence]\n"
    "LEAD_ANSWER: [Grok's reply text]\nLEAD_URL: [https://x.com/grok/status/...]\n"
    "LEAD_DATE: [YYYY-MM-DD]\n\nUp to 4 replies, the most substantive first. "
    "If none qualify, return exactly: NO_LEADS\n"
)


def _text_and_usage(data) -> tuple:
    text = ""
    for i in (data.get("output") or []):
        for c in i.get("content") or []:
            if c.get("type") in ("output_text", "text"):
                text += c.get("text", "")
    u = (data.get("usage") or {}).get("server_side_tool_usage_details") or {}
    return text, u.get("x_search_calls"), u.get("x_posts_fetched")


def compare_lead_prompts(key: str) -> None:
    """Old single-search prompt vs the per-subject prompt, on every show
    with grok_leads on. Counts what parse_leads would keep."""
    import time
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from engine.grok_leads import build_lead_prompt, parse_leads
    shows = {}
    for slug in ("spacex", "tesla", "models_agents", "ai_chips"):
        raw = open(f"shows/{slug}.yaml", encoding="utf-8").read()
        m = re.search(r'^grok_leads:\n(?:  .*\n)*?  topics: "([^"]+)"', raw, re.M)
        if m:
            shows[slug] = m.group(1)
    print("\n=== grok leads: old prompt vs per-subject prompt ===")
    for slug, topics in shows.items():
        for label, prompt in (
                ("old", OLD_LEAD_PROMPT.format(h=48, topics=topics)),
                ("new", build_lead_prompt(topics, 4, 48))):
            t0 = time.time()
            status, data = _post(key, {
                "model": MODEL,
                "tools": [{"type": "x_search", "filters": {"allowed_x_handles": ["grok"]}}],
                "input": [{"role": "user", "content": prompt}]})
            if status != 200 or not isinstance(data, dict):
                print(f"{slug:14s} {label}: HTTP {status} {str(data)[:200]}")
                continue
            text, calls, posts = _text_and_usage(data)
            leads = parse_leads(text)
            print(f"{slug:14s} {label}: {time.time() - t0:5.1f}s | x_search calls {calls} | "
                  f"posts read {posts} | leads kept by parser {len(leads)} | "
                  + "; ".join(lead.get("question", "")[:70] for lead in leads))


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
    compare_lead_prompts(key)
    return 0


if __name__ == "__main__":
    sys.exit(main())
