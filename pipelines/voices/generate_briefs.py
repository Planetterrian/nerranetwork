#!/usr/bin/env python3
"""Daily prep-brief generator (nerra_voices_prep_briefs.yml, 9am PT).

For every interview scheduled in the (now+12h, now+36h) window that has no
brief yet: research the guest (Grok with web search), draft 6-8 likely
questions and the episode thesis, write the ``interview_briefs`` row, email
the brief to the guest, and mark the interview ``briefed``.
"""

from __future__ import annotations

import datetime as dt
import json

from common import (  # noqa: E402  (sys.path bootstrapped in common)
    llm, load_prompt, logger, notify_operator, parse_json_lenient,
    render_email, sb_insert, sb_select, sb_update, send_email,
)


def _window() -> tuple[str, str]:
    now = dt.datetime.now(dt.timezone.utc)
    return ((now + dt.timedelta(hours=12)).isoformat(),
            (now + dt.timedelta(hours=36)).isoformat())


def _application(interview: dict) -> dict:
    rows = sb_select("guest_applications",
                     f"id=eq.{interview['application_id']}")
    if not rows:
        raise RuntimeError(f"interview {interview['id']}: application missing")
    return rows[0]


def generate_brief(interview: dict, app: dict) -> dict:
    links = json.dumps(app.get("links") or {})
    topics = ", ".join(app.get("topics") or [])

    bio_research = llm(
        load_prompt("research_brief.txt",
                    name=app["name"], title=app.get("title", ""),
                    organization=app.get("organization", ""),
                    bio=app.get("bio", ""), topics=topics, links=links),
        temperature=0.3, web_search=True, max_tokens=2500,
    )
    questions_raw = llm(
        load_prompt("question_generation.txt",
                    name=app["name"], bio_research=bio_research,
                    topics=topics),
        temperature=0.6, max_tokens=2000,
    )
    questions = parse_json_lenient(questions_raw)
    thesis = llm(
        load_prompt("episode_thesis.txt",
                    name=app["name"], bio_research=bio_research,
                    topics=topics),
        temperature=0.5, max_tokens=600,
    )

    return sb_insert("interview_briefs", {
        "interview_id": interview["id"],
        "bio_research": bio_research,
        "past_work_summary": bio_research,  # single research pass covers both
        "likely_questions": questions,
        "episode_thesis_draft": thesis,
    })


def email_brief_to_guest(interview: dict, app: dict, brief: dict) -> None:
    when = interview.get("scheduled_at", "")
    html = render_email(
        "voices_prep_brief.j2",
        guest_name=app["name"],
        scheduled_at=when,
        thesis=brief["episode_thesis_draft"],
        questions=brief["likely_questions"],
    )
    send_email(app["email"], "Your Age of AI interview — what Mira will ask", html)
    sb_update("interview_briefs", f"id=eq.{brief['id']}",
              {"sent_to_guest_at": dt.datetime.now(dt.timezone.utc).isoformat()})


def main() -> int:
    lo, hi = _window()
    due = sb_select(
        "interviews",
        f"status=eq.scheduled&scheduled_at=gte.{lo}&scheduled_at=lte.{hi}",
    )
    if not due:
        logger.info("No interviews need briefs in (%s, %s)", lo, hi)
        return 0

    failures = 0
    for interview in due:
        existing = sb_select("interview_briefs",
                             f"interview_id=eq.{interview['id']}")
        if existing:
            logger.info("Interview %s already briefed — skipping", interview["id"])
            continue
        try:
            app = _application(interview)
            brief = generate_brief(interview, app)
            email_brief_to_guest(interview, app, brief)
            sb_update("interviews", f"id=eq.{interview['id']}",
                      {"status": "briefed",
                       "episode_thesis": brief["episode_thesis_draft"]})
            logger.info("Briefed %s (%s)", app["name"], interview["id"])
        except Exception as exc:  # noqa: BLE001 — one bad brief must not block others
            failures += 1
            logger.exception("Brief generation failed for %s", interview["id"])
            notify_operator(
                f"Age of AI: brief generation FAILED for interview "
                f"{interview['id']}: {exc}", critical=True,
            )
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
