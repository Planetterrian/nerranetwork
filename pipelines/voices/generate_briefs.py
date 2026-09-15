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
    cohost_name, episode_memory_block, llm, load_prompt, logger, notify_operator,
    parse_json_lenient, render_email, sb_insert, sb_select, sb_update,
    send_email, show_for,
)
from interview_shape import (  # noqa: E402  (after common: it bootstraps sys.path)
    planned_minutes, question_count, shape_block,
)


def _window() -> tuple[str, str]:
    now = dt.datetime.now(dt.timezone.utc)
    # Z suffix, not +00:00 — raw "+" in a PostgREST query string decodes
    # as a space and 400s (same bug as fire_interviews._iso).
    return ((now + dt.timedelta(hours=12)).isoformat().replace("+00:00", "Z"),
            (now + dt.timedelta(hours=36)).isoformat().replace("+00:00", "Z"))


def _application(interview: dict) -> dict:
    rows = sb_select("guest_applications",
                     f"id=eq.{interview['application_id']}")
    if not rows:
        raise RuntimeError(f"interview {interview['id']}: application missing")
    return rows[0]


def prior_record(app: dict) -> str:
    """What this guest said the last time they were on.

    Sept 15 2026. Every guest so far has asked to come back in six months or
    a year, and a return interview is only worth doing if it opens with what
    they actually said — especially anything they put a date on. Empty for a
    first-time guest, which is nearly everyone, and then the brief reads
    exactly as it did before.
    """
    email = (app.get("email") or "").strip().lower()
    if not email:
        return ""
    try:
        rows = sb_select("episode_records",
                         f"guest_email=eq.{email}&order=recorded_on.desc&limit=3")
    except Exception:  # noqa: BLE001 — a brief never waits on the archive
        logger.exception("episode records unavailable (non-fatal)")
        return ""
    if not rows:
        return ""
    out = ["THEY HAVE BEEN ON THIS SHOW BEFORE. Open on what they said then, "
           "and hold them to anything they put a date on — warmly."]
    for row in rows:
        out.append(f"\n{row.get('recorded_on')}: {row.get('summary') or ''}")
        for pred in (row.get("predictions") or [])[:5]:
            due = pred.get("due_on")
            out.append(f"  PREDICTED{' by ' + due if due else ''}: "
                       f"{pred.get('prediction')}"
                       + (f' — their words: "{pred["quote"]}"' if pred.get("quote") else ""))
        for ask in (row.get("follow_ups") or [])[:5]:
            out.append(f"  TO ASK THIS TIME: {ask}")
        for miss in (row.get("unanswered") or [])[:3]:
            out.append(f"  NEVER ANSWERED: {miss}")
    return "\n".join(out)


def generate_brief(interview: dict, app: dict) -> dict:
    show = show_for(interview, app)
    links = json.dumps(app.get("links") or {})
    topics = ", ".join(app.get("topics") or [])

    bio_research = llm(
        load_prompt("research_brief.txt", show=show,
                    name=app["name"], title=app.get("title", ""),
                    organization=app.get("organization", ""),
                    bio=app.get("bio", ""), topics=topics, links=links,
                    prior_record=prior_record(app)),
        temperature=0.3, web_search=True, max_tokens=2500,
    )
    memory = episode_memory_block(show=show)
    minutes = planned_minutes(interview, app)
    questions_raw = llm(
        load_prompt("question_generation.txt", show=show,
                    name=app["name"], bio_research=bio_research,
                    topics=topics, show_memory=memory,
                    question_count=question_count(minutes),
                    minutes=minutes,
                    guest_shape=shape_block(interview, app),
                    prior_record=prior_record(app)),
        temperature=0.6, max_tokens=2000,
    )
    questions = parse_json_lenient(questions_raw)
    thesis = llm(
        load_prompt("episode_thesis.txt", show=show,
                    name=app["name"], bio_research=bio_research,
                    topics=topics, show_memory=memory),
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
    show = show_for(interview, app)
    when = interview.get("scheduled_at", "")
    html = render_email(
        "voices_prep_brief.j2",
        show=show,
        guest_name=app["name"],
        scheduled_at=when,
        interview_id=interview["id"],
        thesis=brief["episode_thesis_draft"],
        questions=brief["likely_questions"],
        closing_question=show.closing_question,
        # Phase 2: tell the guest who is in the room (empty → no paragraph).
        cohost_name=cohost_name() if interview.get("host_mode") is not False else "",
    )
    send_email(app["email"],
               f"Your {show.short_label} interview — what Mira will ask",
               html, cc_operator=True)
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
        show = show_for(interview)
        try:
            app = _application(interview)
            show = show_for(interview, app)
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
                show.slack(f"brief generation FAILED for interview "
                           f"{interview['id']}: {exc}"), critical=True,
            )
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
