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

import html as _html  # noqa: E402
import os  # noqa: E402

from common import (  # noqa: E402
    OPERATOR_EMAIL, guest_links, llm, load_prompt, notify_operator,
    parse_json_lenient, sb_select, sb_update, send_email,
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


def triage_link() -> str:
    token = os.environ.get("ADMIN_TOKEN", "").strip()
    return ("https://api.nerranetwork.com/voices/admin/triage"
            + (f"?token={token}" if token else ""))


def assessment_email(app: dict, result: dict) -> tuple[str, str]:
    """Subject and body of the note Patrick reads before he approves."""
    show = show_for(app)
    e = _html.escape
    topics = app.get("topics") or []
    if isinstance(topics, str):
        topics = [topics]
    verdict = result["verdict"]
    colour = {"strong": "#166534", "thin": "#991B1B"}.get(verdict, "#92400E")

    def items(label: str, xs: list) -> str:
        if not xs:
            return ""
        return (f"<p><b>{label}</b></p><ul>"
                + "".join(f"<li>{e(x)}</li>" for x in xs) + "</ul>")

    body = (
        f"<p>Hi Patrick,</p>"
        f"<p>A new guest applied to {e(show.name)}: <strong>{e(app.get('name', ''))}</strong>"
        f"{', ' + e(app['title']) if app.get('title') else ''}"
        f"{' at ' + e(app['organization']) if app.get('organization') else ''}."
        f" It arrived {e(provenance(app))}."
        f"{' They asked for you in the room as co-host.' if app.get('wants_cohost') else ''}</p>"
        f"<p style='border-left:4px solid {colour};padding:.6em 1em;margin:1em 0'>"
        f"<b style='color:{colour}'>My read: {e(verdict)}.</b> {e(result['summary'])}</p>"
        + items("What I could find", result["specifics"])
        + items("What I could not", result["concerns"])
        + (f"<p><b>If we have them on, I would open with:</b> {e(result['ask_first'])}</p>"
           if result.get("ask_first") else "")
        + f"<p><em>In their words:</em> {e(str(app.get('bio') or '')[:600])}</p>"
        f"<p><em>Wants to talk about:</em> {e(', '.join(str(t) for t in topics))}</p>"
        f"<p><a href=\"{triage_link()}\">Approve or decline here</a>. If you approve, "
        f"I send the booking link; if you decline, I send them a polite no and copy "
        f"their publicist if they have one. You are copied on both.</p>"
        f"<p>— Mira</p>"
    )
    subject = f"{show.short_label} application: {app.get('name', '')} — my read is {verdict}"
    return subject, body


def screen_one(app: dict) -> dict:
    result = screen(app)
    sb_update("guest_applications", f"id=eq.{app['id']}",
              {"screen": result,
               "screened_at": dt.datetime.now(dt.timezone.utc).isoformat()})
    logger.info("screened %s: %s — %s", app.get("name"), result["verdict"],
                result["summary"])
    show = show_for(app)
    if result["verdict"] == "thin":
        notify_operator(show.slack(
            f"application screened THIN: {app.get('name')} — {result['summary']} "
            f"(concerns: {'; '.join(result['concerns']) or 'none listed'})"))
    if app.get("status") == "pending":
        subject, body = assessment_email(app, result)
        try:
            send_email(OPERATOR_EMAIL, subject, body)
        except Exception:  # noqa: BLE001 — the row has the read; the page shows it
            logger.exception("assessment email failed for %s", app.get("id"))
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
