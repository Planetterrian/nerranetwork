#!/usr/bin/env python3
"""Screen pending guest applications for substance before triage.

Sept 18 2026. Rhett Mikols came through a publicist with a name, a vision and
no work behind either; Mira spent forty-five minutes asking for an instance
that never came, and nothing publishable came out of it. The producer approved
him from a bio and a topic list, which is all the triage page showed.

This reads each pending application once, checks what it can on the open
web, and writes a verdict onto the row: strong, thin or unclear, with the
specifics it found, the concerns it has and the one question to open with.
The triage page shows it beside the Approve button. It is advice for the
person who approves; it never declines anyone by itself.

    python pipelines/voices/screen_applications.py            # all unscreened pending
    python pipelines/voices/screen_applications.py <app id>   # one, even if screened
"""
from __future__ import annotations

import datetime as dt
import json
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from common import (  # noqa: E402
    guest_links, llm, load_prompt, notify_operator, parse_json_lenient,
    sb_select, sb_update,
)
from pipelines.voices.shows import show_for  # noqa: E402

logger = logging.getLogger("nerra.voices.screen")

VERDICTS = ("strong", "thin", "unclear")


def provenance(app: dict) -> str:
    bits = []
    source = (app.get("source") or "form").strip()
    bits.append("through the application form" if source == "form"
                else f"via {source}")
    if app.get("publicist_name") or app.get("publicist_email"):
        who = app.get("publicist_name") or app.get("publicist_email")
        bits.append(f"pitched by a publicist ({who})")
    if app.get("pitch_summary"):
        bits.append(f"pitch: {str(app['pitch_summary'])[:400]}")
    return "; ".join(bits)


def screen(app: dict) -> dict:
    show = show_for(app)
    topics = app.get("topics") or []
    if isinstance(topics, str):
        topics = [topics]
    prompt = load_prompt(
        "screen_application.txt", show=show.slug,
        name=app.get("name", ""), title=app.get("title") or "(none given)",
        organization=app.get("organization") or "(none given)",
        bio=app.get("bio") or "(none given)",
        topics="\n".join(f"- {t}" for t in topics) or "(none given)",
        links=", ".join(f"{l['label']}: {l['url']}" for l in guest_links(app)) or "(none)",
        provenance=provenance(app),
    )
    raw = llm(prompt, temperature=0.2, web_search=True, max_tokens=1500)
    out = parse_json_lenient(raw)
    if not isinstance(out, dict) or out.get("verdict") not in VERDICTS:
        raise ValueError(f"screen returned no verdict: {raw[:200]!r}")
    return {
        "verdict": out["verdict"],
        "summary": str(out.get("summary") or "").strip()[:600],
        "specifics": [str(s)[:300] for s in (out.get("specifics") or [])][:5],
        "concerns": [str(s)[:300] for s in (out.get("concerns") or [])][:5],
        "ask_first": str(out.get("ask_first") or "").strip()[:400],
    }


def screen_one(app: dict) -> dict:
    result = screen(app)
    sb_update("guest_applications", f"id=eq.{app['id']}",
              {"screen": result,
               "screened_at": dt.datetime.now(dt.timezone.utc).isoformat()})
    logger.info("screened %s: %s — %s", app.get("name"), result["verdict"],
                result["summary"])
    if result["verdict"] == "thin":
        show = show_for(app)
        notify_operator(show.slack(
            f"application screened THIN: {app.get('name')} — {result['summary']} "
            f"(concerns: {'; '.join(result['concerns']) or 'none listed'})"))
    return result


def main(argv: list[str]) -> int:
    if len(argv) > 1:
        rows = sb_select("guest_applications", f"id=eq.{argv[1]}")
    else:
        rows = sb_select("guest_applications",
                         "status=eq.pending&screened_at=is.null&order=created_at.asc&limit=20")
    if not rows:
        logger.info("nothing to screen")
        return 0
    failures = 0
    for app in rows:
        try:
            screen_one(app)
        except Exception:  # noqa: BLE001 — one bad screen must not block the rest
            failures += 1
            logger.exception("screen failed for %s", app.get("id"))
    return 1 if failures else 0


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    raise SystemExit(main(sys.argv))
