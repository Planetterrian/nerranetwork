"""A five-minute hello two days before the interview (Oct 21 2026).

Six of fifty applications since September set an agenda; the booking email
asks the guest to reply by email instead, and nobody does. The subject a
guest came for is the spine of the hour (Chad Law, Sept 29 2026), and the
cheapest way to learn it is to ask them, out loud, before the day — which
also finds the headphone and echo problems before they are on tape.

This reuses the CLOSING-SESSION machinery exactly: a short ``interviews``
row of its own (``session_kind = 'hello'``, ``hello_for_interview_id`` naming
the interview it precedes), booked by the guest on a Cal.com event type,
fired by the same tick with its own prompt, recorded and transcribed by the
same post-interview job, and then archived — never a package anyone reviews
or an episode anyone hears. Its one product is ``guest_applications.
guest_agenda``, written from the transcript by ``after_hello``.

Python owns three things here; the rest is wiring in files other passes own:

* ``send_hello_invites`` — the invitation, to every interview two to four
  days out whose guest has no agenda yet, once (``interviews.hello_invited_at``).
* ``compile_hello_prompt`` — what Mira is in the hello (the fire step calls
  it when ``session_kind == 'hello'``, the way it calls
  ``compile_closing_prompt`` for a closing).
* ``after_hello`` — the agenda, from the transcript, onto the application;
  the hello's package and row archived (post_interview calls it through
  ``guest_thanks.after_room``).

Wiring that lives elsewhere: the Worker books a ``hello`` event type the way
it books ``closing`` (five minutes, ``session_kind: 'hello'``,
``hello_for_interview_id`` from the matching application); the fire step
compiles this prompt for the kind; the scenario treats a hello like a closing
session for the opening (no show open, no closing round; ``planned_min`` 5).
"""

from __future__ import annotations

import datetime as dt
import html as _html
import os
import re
from typing import Any, Dict, Optional

from common import (  # noqa: E402
    booking_url, llm, load_prompt, logger, mira_signature_html, parse_json_lenient,
    sb_select, sb_update, send_email, show_for,
)

HELLO_MINUTES = 5
INVITE_AHEAD = (dt.timedelta(days=2), dt.timedelta(days=4))


def hello_booking_url(show) -> str:
    """The Cal.com page for the hello: an env override, the show's own field,
    or the closing page's address with its last path word swapped."""
    env = os.environ.get("CALCOM_BOOKING_URL_HELLO", "").strip()
    if env:
        return env
    own = str(getattr(show, "hello_booking_url", "") or "").strip()
    if own:
        return own
    closing = booking_url(show, closing=True)
    return re.sub(r"-closing/?$", "-hello", closing) if "-closing" in closing else closing


def is_hello_session(interview: Optional[dict]) -> bool:
    return (interview or {}).get("session_kind") == "hello"


def has_agenda(app: Dict[str, Any]) -> bool:
    agenda = app.get("guest_agenda") or {}
    if isinstance(agenda, str):
        return bool(agenda.strip())
    return bool(isinstance(agenda, dict) and (agenda.get("topic") or agenda.get("points")))


def invite_email(show, app: Dict[str, Any], interview: Dict[str, Any]) -> tuple:
    e = _html.escape
    name = str(app.get("name") or "").strip()
    first = name.split()[0] if name else "there"
    url = hello_booking_url(show)
    body = (
        f"<p>Hi {e(first)},</p>"
        f"<p>Before we record, I would like five minutes with you — a hello, "
        f"not an interview. We check that we can hear each other properly, and "
        f"you tell me the one thing you most want the hour to reach. That becomes "
        f"the spine of our conversation, in your words rather than mine.</p>"
        f"<p>Pick any five-minute slot that suits you here: "
        f'<a href="{e(url)}">{e(url)}</a>. Headphones help; the same link opens '
        f"the studio when the time comes.</p>"
        f"<p>If you would rather just write it, reply to this with the subject "
        f"and two or three points, and I will take it from there.</p>"
        + mira_signature_html(show)
    )
    return f"Five minutes before we record, {first}?", body


def send_hello_invites(now: Optional[dt.datetime] = None) -> int:
    """Invite every guest whose interview is two to four days out and who has
    no agenda yet. Returns the number sent."""
    now = now or dt.datetime.now(dt.timezone.utc)
    lo, hi = now + INVITE_AHEAD[0], now + INVITE_AHEAD[1]
    rows = sb_select(
        "interviews",
        "status=in.(briefed,scheduled)&session_kind=eq.interview"
        f"&hello_invited_at=is.null&scheduled_for=gte.{lo.isoformat()}"
        f"&scheduled_for=lte.{hi.isoformat()}")
    sent = 0
    for interview in rows:
        try:
            apps = sb_select("guest_applications", f"id=eq.{interview['application_id']}")
            if not apps:
                continue
            app = apps[0]
            if has_agenda(app):
                sb_update("interviews", f"id=eq.{interview['id']}",
                          {"hello_invited_at": now.isoformat(),
                           "hello_skipped_reason": "agenda already set"})
                continue
            show = show_for(interview, app)
            subject, body = invite_email(show, app, interview)
            send_email(str(app.get("email") or ""), subject, body, cc_operator=True)
            sb_update("interviews", f"id=eq.{interview['id']}",
                      {"hello_invited_at": now.isoformat()})
            sent += 1
        except Exception:  # noqa: BLE001 — one guest's invite never costs another's
            logger.exception("hello invite failed for interview %s", interview.get("id"))
    logger.info("hello invites sent: %d", sent)
    return sent


def compile_hello_prompt(interview: Dict[str, Any], app: Dict[str, Any]) -> str:
    show = show_for(interview, app)
    title = str(app.get("title") or "").strip()
    org = str(app.get("organization") or "").strip()
    clause = (f", {title}" if title else "") + (f" at {org}" if org else "")
    return load_prompt("mira_hello_session.txt", show=show,
                       guest_name=app.get("name", ""),
                       guest_role_clause=clause,
                       interview_when=str(interview.get("hello_for_when") or
                                          "in a couple of days"))


_AGENDA_PROMPT = """Below is the transcript of a five-minute hello between Mira, an AI host, and
{guest_name}, two days before their interview. Mira asked what they most want
the hour to reach.

Return JSON only: {{"topic": "<the subject they came for, one line, in their
words where possible>", "points": ["<a point they asked to reach>", ...]}}.
Two to four points, each a thing THEY said they wanted, never a question Mira
asked. If they named nothing, return {{"topic": "", "points": []}}.

Transcript:
{transcript}
"""


def agenda_from_transcript(transcript: str, guest_name: str) -> Dict[str, Any]:
    raw = llm(_AGENDA_PROMPT.format(guest_name=guest_name, transcript=transcript),
              temperature=0.2, max_tokens=600)
    out = parse_json_lenient(raw)
    if not isinstance(out, dict):
        return {"topic": "", "points": []}
    topic = str(out.get("topic") or "").strip()
    points = [str(p).strip() for p in (out.get("points") or []) if str(p).strip()][:4]
    return {"topic": topic, "points": points}


def after_hello(interview: Dict[str, Any], app: Dict[str, Any], transcript: str,
                package: Dict[str, Any]) -> Dict[str, Any]:
    """The hello's one product: the agenda, on the application. The hello's
    package and row are archived; nobody reviews a five-minute hello."""
    agenda = agenda_from_transcript(transcript or "", str(app.get("name") or ""))
    now = dt.datetime.now(dt.timezone.utc).isoformat()
    if agenda["topic"] or agenda["points"]:
        sb_update("guest_applications", f"id=eq.{app['id']}",
                  {"guest_agenda": {**agenda, "updated_at": now, "source": "hello"}})
        logger.info("agenda from the hello: %s (%d points)", agenda["topic"],
                    len(agenda["points"]))
    else:
        logger.info("the hello named no subject; the agenda is unchanged")
    sb_update("editorial_packages", f"id=eq.{package['id']}", {
        "status": "archived",
        "patrick_notes": "Pre-call hello: five minutes before the interview. Its agenda "
                         "is on the application; never published."})
    sb_update("interviews", f"id=eq.{interview['id']}",
              {"status": "archived", "hello_agenda": agenda})
    return agenda


def main() -> int:
    import sys
    what = sys.argv[1] if len(sys.argv) > 1 else "invites"
    if what == "invites":
        return 0 if send_hello_invites() >= 0 else 1
    raise SystemExit(f"unknown command {what!r} (invites)")


if __name__ == "__main__":
    raise SystemExit(main())
