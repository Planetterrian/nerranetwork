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
    OPERATOR_EMAIL, carry_the_show_block, episode_memory_block, guest_agenda_block,
    guest_notes_block, llm, load_prompt,
    logger, notify_operator,
    parse_json_lenient, render_email, sb_insert, sb_select, sb_update,
    send_email, show_for, guest_audio_html, studio_steps_html,
)
from address import first_name  # noqa: E402
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


# Oct 22 2026, Stan Lewis. His application was made from a Cal.com booking:
# a name, a personal Gmail address, a phone number, nothing else. The research
# pass searched "Stan Lewis" for an AI show and found Stanislas "Stan" Polu,
# the ex-OpenAI founder of Dust. The brief, the thesis, the question list
# emailed to him, the subject line in his reminder and Mira's first question
# were all about Polu. Stan is a veteran who mediates for executives; he spent
# the first minutes answering a question meant for someone else.
#
# Two guards. An application with nothing to tell the guest apart from anyone
# else of that name is not researched at all: the guest is asked, by email,
# who they are, and Mira opens by asking. And research whose text never
# names the guest's surname is about someone else and is thrown away.
FREE_MAIL = {"gmail.com", "googlemail.com", "yahoo.com", "hotmail.com", "outlook.com",
             "live.com", "msn.com", "icloud.com", "me.com", "mac.com", "aol.com",
             "proton.me", "protonmail.com", "gmx.com", "ymail.com"}
_NAME_SUFFIX = {"jr", "sr", "ii", "iii", "iv", "phd", "md", "mba", "dr", "esq"}

IDENTITY_UNKNOWN = (
    "IDENTITY NOT CONFIRMED. Nothing in the application tells this guest apart "
    "from anyone else with the same name, so nothing was researched: anything "
    "found would as likely be about someone else. Mira has asked them by email "
    "who they are and what they want to talk about; anything they sent back is "
    "in the guest's notes. Open by asking them, warmly, what they do and what "
    "they came to talk about, and build the hour from their answers. Never "
    "attribute to them work, a company or a career they have not told you "
    "about.")


def _filled(value) -> bool:
    if isinstance(value, dict):
        return any(_filled(v) for v in value.values())
    if isinstance(value, (list, tuple, set)):
        return any(_filled(v) for v in value)
    return bool(str(value or "").strip())


def own_domain(app: dict) -> str:
    """The guest's own email domain, when it is not a free mail service."""
    domain = str(app.get("email") or "").rsplit("@", 1)[-1].strip().lower()
    return "" if (not domain or domain in FREE_MAIL or "@" not in str(app.get("email") or "")) else domain


def identity_anchors(app: dict) -> list:
    """What tells this guest apart from anyone else with the same name."""
    anchors = []
    for key in ("organization", "title", "bio", "topics", "links", "pitch_summary",
                "guest_agenda", "guest_notes"):
        if _filled(app.get(key)):
            anchors.append(key)
    if own_domain(app):
        anchors.append("email_domain")
    return anchors


def surname(name: str) -> str:
    parts = [p.strip(".,").lower() for p in str(name or "").split()]
    parts = [p for p in parts if p and p not in _NAME_SUFFIX]
    return parts[-1] if len(parts) >= 2 else ""


def research_names_guest(research: str, name: str) -> bool:
    """Does the research mention the guest's surname at all? Research about
    "Stan Lewis" that never says "Lewis" is about somebody else."""
    last = surname(name)
    if len(last) < 3:
        return True          # nothing reliable to check against
    return last in str(research or "").lower()


def _identity_unknown_brief(interview: dict, app: dict, why: str) -> dict:
    name = str(app.get("name") or "the guest").strip()
    logger.warning("brief for %s: identity not confirmed (%s); not researched", name, why)
    try:
        show = show_for(interview, app)
        send_email(
            OPERATOR_EMAIL,
            f"{show.short_label}: who is {name}? I have asked them",
            f"<p>Hi Patrick,</p><p>{name}'s interview is booked for "
            f"{when_text(interview.get('scheduled_at', ''))}, and I can't tell who they are: "
            f"{why}. Research on a bare name finds whoever is most famous under it, so I "
            f"have not researched them. I have asked them by email for a few lines and a "
            f"link, and in the room I will open by asking. If you know who they are, add "
            f"a line or a link to their application and the next brief run will use it.</p>"
            f"<p>Mira</p>")
    except Exception:  # noqa: BLE001 — the guest email still goes
        logger.exception("identity alert to Patrick failed (non-fatal)")
    return sb_insert("interview_briefs", {
        "interview_id": interview["id"],
        "bio_research": IDENTITY_UNKNOWN,
        "past_work_summary": IDENTITY_UNKNOWN,
        "likely_questions": [
            {"question": "What do you do, in your own words, and how did you come to it?"},
            {"question": "What did you want to make sure we talk about today?"},
            {"question": "Where is AI showing up in your work right now, if it is?"},
        ],
        "episode_thesis_draft": f"A conversation with {name} about the work they have "
                                f"chosen, in their own words.",
    })


def generate_brief(interview: dict, app: dict) -> dict:
    show = show_for(interview, app)
    links = json.dumps(app.get("links") or {})
    topics = ", ".join(app.get("topics") or [])

    if not identity_anchors(app):
        return _identity_unknown_brief(
            interview, app, "the application has only a name and a personal email "
                            "address, with no organisation, bio, links or topics")
    domain = own_domain(app)
    bio_research = llm(
        load_prompt("research_brief.txt", show=show,
                    name=app["name"], title=app.get("title", ""),
                    organization=app.get("organization", "")
                    or (f"(their email domain is {domain})" if domain else ""),
                    bio=app.get("bio", ""), topics=topics, links=links,
                    prior_record=prior_record(app)),
        temperature=0.3, web_search=True, max_tokens=2500,
    )
    if not research_names_guest(bio_research, app.get("name", "")):
        return _identity_unknown_brief(
            interview, app, f"the research never mentions the name {app.get('name')}, "
                            f"so it found someone else")
    memory = episode_memory_block(show=show)
    minutes = planned_minutes(interview, app)
    questions_raw = llm(
        load_prompt("question_generation.txt", show=show,
                    name=app["name"], bio_research=bio_research,
                    topics=topics, show_memory=memory,
                    question_count=question_count(minutes),
                    minutes=minutes,
                    guest_shape=shape_block(interview, app),
                    # Oct 21 2026: the subject the guest asked for, and what
                    # they wrote before the call, reach the question set — they
                    # had reached only Mira's live prompt, so the prepared set
                    # was written without the subject the guest came for.
                    guest_agenda=guest_agenda_block(app),
                    guest_notes=guest_notes_block(app),
                    prior_record=prior_record(app),
                    carry_the_show=carry_the_show_block(
                        show, exclude_email=app.get("email", ""), app=app)),
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


def when_text(iso: str, guest_tz: str = "") -> str:
    """"Thursday, September 24 at 9:45 AM Pacific Time", with the guest's own
    clock alongside when we know their zone (Sept 30 2026: was UTC)."""
    from pipelines.voices.common import pacific_time
    return pacific_time(iso, guest_tz or None)


def setup_test_url(show, interview_id: str) -> str:
    """The studio page in its day-before test mode (``&test=1``): the
    microphone check and the headphones check, nothing joined or recorded."""
    return f"{show.studio_url(interview_id)}&role=guest&test=1"


CURIOUS_ABOUT_MAX = 3


def curious_about(questions) -> list:
    """The three things Mira is curious about, in her words, for the prep
    email (Oct 21 2026: the brief goes both ways, so the first question is
    not a surprise and the hour has a shape the guest helped choose).

    Written from the question set the brief already carries, with no model
    call: each prepared question's ``why`` line says what it should
    surface; the first three become one sentence each. A set without
    ``why`` lines falls back to the questions themselves."""
    out = []
    for q in questions or []:
        text = ""
        if isinstance(q, dict):
            text = " ".join(str(q.get("why") or q.get("question") or "").split())
        else:
            text = " ".join(str(q or "").split())
        text = text.strip().rstrip(".")
        if not text:
            continue
        if text[:1].isupper() and not text[:2].isupper():
            text = text[0].lower() + text[1:]
        out.append(f"I'm curious about {text}.")
        if len(out) >= CURIOUS_ABOUT_MAX:
            break
    return out


def email_brief_to_guest(interview: dict, app: dict, brief: dict) -> None:
    show = show_for(interview, app)
    html = render_email(
        "voices_prep_brief.j2",
        show=show,
        guest_name=first_name(app),
        when_text=when_text(interview.get("scheduled_at", ""), interview.get("guest_timezone") or ""),
        interview_id=interview["id"],
        studio_link=f"{show.studio_url(interview['id'])}&role=guest",
        # Oct 1 2026: why the computer studio is worth it, and the way in.
        audio_html=guest_audio_html(),
        steps_html=studio_steps_html(f"{show.studio_url(interview['id'])}&role=guest"),
        # Sept 28 2026 (Elliot): a 30-second microphone and headphones test
        # the day before, on the same page, so a quiet microphone is found
        # while there is still time to fix it. Failures email Patrick.
        setup_test_link=setup_test_url(show, interview["id"]),
        # Sept 29 2026 (Chad Law): the points the guest asked to cover, shown
        # back to them so they know Mira has them.
        agenda_points=((app.get("guest_agenda") or {}).get("points") or [])
        if isinstance(app.get("guest_agenda"), dict) else [],
        thesis=brief["episode_thesis_draft"],
        questions=brief["likely_questions"],
        identity_unknown=str(brief.get("bio_research") or "").startswith("IDENTITY NOT CONFIRMED"),
        curious_about=curious_about(brief.get("likely_questions")),
        closing_question=show.closing_question,
    )
    unknown = str(brief.get("bio_research") or "").startswith("IDENTITY NOT CONFIRMED")
    # Oct 22 2026: the guest's name is in the subject. Every guest's brief had
    # the same subject, so in Patrick's copy Gmail threaded Cory's and Jon's
    # together, and a guest's reply could land in a thread about another.
    first = first_name(app)
    send_email(app["email"],
               (f"{first}, before our interview on {show.name}: tell me about you" if unknown else
                f"{first}, what I would like to ask you on {show.name}"),
               html, cc_operator=True, cc=[str(app.get("publicist_email") or "")])
    sb_update("interview_briefs", f"id=eq.{brief['id']}",
              {"sent_to_guest_at": dt.datetime.now(dt.timezone.utc).isoformat(),
               "sent_to": app["email"]})


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
        if (interview.get("session_kind") or "interview") in ("closing", "hello"):
            # Oct 5 2026: a closing session has no brief to send; the guest
            # already knows the subject. Oct 21 2026: nor has a pre-call
            # hello. Marked briefed so the reminders run.
            sb_update("interviews", f"id=eq.{interview['id']}", {"status": "briefed"})
            continue
        existing = sb_select("interview_briefs",
                             f"interview_id=eq.{interview['id']}")
        if existing:
            # Oct 5 2026 (Jon Cheney): a guest who rebooked onto the same row
            # keeps the brief from the first slot, but the booking resets the
            # row to `scheduled`, and the T-2h reminder only looks at
            # `briefed` rows. He got no reminder. The brief stands; the
            # status has to say so.
            if interview.get("status") == "scheduled":
                sb_update("interviews", f"id=eq.{interview['id']}", {"status": "briefed"})
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
    return 1 if (failures + resend_to_new_address()) else 0


def resend_to_new_address() -> int:
    """Send the brief again when the guest's address is not the one it went
    to (a booking moved onto another application, or the guest booked with
    a different email). Interviews in the next 36 hours only."""
    now = dt.datetime.now(dt.timezone.utc)
    hi = (now + dt.timedelta(hours=36)).isoformat().replace("+00:00", "Z")
    lo = now.isoformat().replace("+00:00", "Z")
    rows = sb_select("interviews",
                     f"status=eq.briefed&scheduled_at=gte.{lo}&scheduled_at=lte.{hi}")
    failures = 0
    for interview in rows or []:
        briefs = sb_select("interview_briefs", f"interview_id=eq.{interview['id']}")
        if not briefs or not briefs[0].get("sent_to_guest_at"):
            continue
        try:
            app = _application(interview)
        except Exception:  # noqa: BLE001
            continue
        sent_to = (briefs[0].get("sent_to") or "").strip().lower()
        current = (app.get("email") or "").strip().lower()
        if not current or not sent_to or sent_to == current:
            # No record of the address (briefs sent before Sept 24 2026) is
            # treated as correct: re-mailing every guest once is worse.
            continue
        try:
            email_brief_to_guest(interview, app, briefs[0])
            logger.info("Re-sent brief for %s to %s (was %s)", interview["id"], current, sent_to)
        except Exception as exc:  # noqa: BLE001
            failures += 1
            logger.exception("Brief re-send failed for %s", interview["id"])
            notify_operator(f"prep brief re-send FAILED for interview {interview['id']}: {exc}",
                            critical=True)
    return failures


if __name__ == "__main__":
    raise SystemExit(main())
