#!/usr/bin/env python3
"""Interview firing cron (nerra_voices_fire_interview.yml, every 5 min).

Two duties per tick:

1. **T-2h SMS reminder** — interviews ~2h out get one SMS from Mira's
   caller ID (``reminder_sent_at`` guards the once-only).
2. **Fire** — interviews whose ``scheduled_at`` falls inside the next
   5-minute window: compile Mira's system prompt from the brief, create the
   ``interview_runs`` row, and start the Voximplant scenario with the run id
   as customData.

GitHub cron is best-effort (spec §5.2 note): the firing window is computed
here as [now - grace, now + 5 min] so a delayed tick still fires anything
it missed, and the ``interview_runs`` uniqueness check keeps a double tick
from double-calling the guest.
"""

from __future__ import annotations

import datetime as dt
import json
import os

from common import (  # noqa: E402
    OPERATOR_EMAIL, ROOT, cohost_name, load_prompt, logger, notify_operator,
    operator_phone, render_email, sb_insert, sb_select, sb_update, send_email,
    show_for,
)

FIRE_WINDOW_AHEAD_MIN = 5
FIRE_GRACE_BEHIND_MIN = 30   # cron drift tolerance — never leave a guest
                             # waiting; GitHub delivers */5 crons roughly
                             # hourly under load, so 10 min missed real slots
                             # (July 17 2026). Also gives failed-call retries
                             # room: a no-answer run resets the interview to
                             # briefed and later ticks in this window re-fire.
REMINDER_AHEAD = (dt.timedelta(minutes=105), dt.timedelta(minutes=135))

# Phase 2 co-host (Sept 2026, docs/cohost_phase2_contract.md): Patrick is in
# the room on every interview unless the interview row says host_mode=false.
# The block is tokenised so {{cohost_name}} follows env COHOST_NAME.
COHOST_BLOCK = (
    "CO-HOST: {{cohost_name}}, the network's founder, is in the room as your "
    "co-host. He may interject with a question, a clarification, or to fix a "
    "technical problem. When he speaks, answer him briefly if he asked you "
    "something, otherwise acknowledge in a few words and hand the floor back "
    "to the guest. He is not the interviewee: never interview {{cohost_first}}, "
    "never ask him the lightning round, and keep the guest as the centre of "
    "the conversation. If {{cohost_first}} says 'let's pause' or 'hold on', "
    "stop talking and wait for him."
)


def host_mode_enabled(interview: dict, run: dict | None = None) -> bool:
    """``host_mode`` defaults ON; only an explicit ``false`` disables it."""
    for row in (run, interview):
        if row is not None and row.get("host_mode") is False:
            return False
    return True


def cohost_block(enabled: bool = True) -> str:
    if not enabled:
        return ""
    name = cohost_name()
    return (COHOST_BLOCK.replace("{{cohost_name}}", name)
            .replace("{{cohost_first}}", name.split()[0]))


def host_link(show, interview_id: str) -> str:
    """Patrick's co-host studio link: the guest studio URL + role=host +
    the Worker's ADMIN_TOKEN (GitHub secret ADMIN_TOKEN; the Worker only
    issues host credentials when the token matches)."""
    token = os.environ.get("ADMIN_TOKEN", "").strip()
    if not token:
        raise RuntimeError("ADMIN_TOKEN env var is required for the host link")
    return f"{show.studio_url(interview_id)}&role=host&token={token}"


def notify_host(interview: dict, app: dict, show, *, when: str) -> None:
    """Email + SMS Patrick his co-host link (best-effort, never raises).

    ``when`` is the human phrase for the lead time ("in 2 min", "in about
    2 hours"). Email → OPERATOR_EMAIL (templates/email/voices_host_link.j2);
    SMS → OPERATOR_PHONE when set, from Mira's caller ID.
    """
    guest_name = (app.get("name") or "the guest").strip()
    try:
        url = host_link(show, interview["id"])
    except Exception as exc:  # noqa: BLE001
        logger.warning("Host link not sent for %s: %s", interview["id"], exc)
        notify_operator(show.slack(
            f"co-host link for {guest_name} NOT sent ({exc})"), critical=True)
        return
    try:
        html = render_email(
            "voices_host_link.j2", show=show,
            host_url=url, guest_name=guest_name,
            scheduled_at=interview.get("scheduled_at", ""),
            cohost_name=cohost_name(), when=when,
            interview_id=interview["id"],
        )
        send_email(OPERATOR_EMAIL,
                   f"{show.short_label}: co-host link — {guest_name} {when}",
                   html)
    except Exception:  # noqa: BLE001 — the fire must not fail on this
        logger.exception("Host link email failed (non-fatal)")
    phone = operator_phone()
    if not phone:
        logger.info("OPERATOR_PHONE unset — host link SMS skipped")
        return
    try:
        from voximplant.api_clients.voximplant_client import send_sms
        caller_id = interview.get("caller_id") or os.environ.get(
            "VOXIMPLANT_CALLER_ID", "")
        send_sms(phone, host_sms_text(show, guest_name, url, when),
                 source_number=caller_id or None)
    except Exception:  # noqa: BLE001
        logger.exception("Host link SMS failed (non-fatal)")


def host_sms_text(show, guest_name: str, url: str, when: str) -> str:
    return f"{show.name}: {guest_name} {when}. Your co-host link: {url}"

MIRA_TOOLS = [
    {
        "type": "function",
        "name": "nerra_episode_lookup",
        "description": (
            "Look up the 3 most recent Nerra Network episodes covering a "
            "given topic. Use this when you want to reference what other "
            "Nerra shows have covered on the guest's topic."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "topic": {"type": "string"},
                "show_filter": {"type": "string",
                                "description": "optional show id"},
            },
            "required": ["topic"],
        },
    },
    {
        "type": "function",
        "name": "guest_brief_lookup",
        "description": (
            "Pull the pre-interview research brief on the current guest. "
            "Use this to refresh your memory mid-interview on a specific "
            "topic they wanted to discuss."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "section": {"type": "string",
                            "enum": ["bio", "topics", "past_work",
                                     "predictions"]},
            },
        },
    },
    {
        "type": "function",
        "name": "fact_check_claim",
        "description": (
            "Verify a specific factual claim the guest just made via web "
            "search. Use sparingly — only when the claim is checkable and "
            "verification adds value to the conversation."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "claim": {"type": "string"},
                "context": {"type": "string",
                            "description": "what the guest was discussing"},
            },
            "required": ["claim"],
        },
    },
]


def _now() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc)


def _iso(t: dt.datetime) -> str:
    # Z suffix, not +00:00: these strings go raw into PostgREST query
    # strings, where an unencoded "+" is decoded as a space → 400 (this
    # crashed every fire cron tick until July 17 2026).
    return t.isoformat().replace("+00:00", "Z")


def compile_mira_prompt(interview: dict, app: dict, brief: dict) -> str:
    """Mira's system prompt for this interview, branded for its show.

    The show (name, premise, opening line, closing question) comes from
    ``show_for(interview, app)`` — the ``show`` column on the interview,
    then the application, then the default show for pre-migration rows.
    """
    show = show_for(interview, app)
    questions = brief.get("likely_questions") or []
    q_text = "\n".join(f"- {q.get('question', q) if isinstance(q, dict) else q}"
                       for q in questions)
    return load_prompt(
        "mira_system_prompt.txt",
        show=show,
        show_name=show.name,
        show_premise=show.premise,
        opening_line=show.opening_line,
        closing_question=show.closing_question,
        guest_name=app["name"],
        guest_title=app.get("title", ""),
        guest_organization=app.get("organization", ""),
        episode_thesis=interview.get("episode_thesis")
        or brief.get("episode_thesis_draft", ""),
        guest_brief=brief.get("bio_research", ""),
        likely_questions=q_text,
        cohost_name=cohost_name(),
        cohost_block=cohost_block(host_mode_enabled(interview)),
    )


def send_reminders() -> None:
    lo, hi = _now() + REMINDER_AHEAD[0], _now() + REMINDER_AHEAD[1]
    due = sb_select(
        "interviews",
        "status=eq.briefed&reminder_sent_at=is.null"
        f"&scheduled_at=gte.{_iso(lo)}&scheduled_at=lte.{_iso(hi)}",
    )
    for interview in due:
        try:
            app_rows = sb_select("guest_applications",
                                 f"id=eq.{interview['application_id']}")
            app = app_rows[0] if app_rows else {}
            show = show_for(interview, app)
            # Phase 2: Patrick's T-2h co-host link goes out first (his own
            # SMS/email, never to the guest) — it does not depend on the
            # guest having a phone on file.
            if host_mode_enabled(interview):
                notify_host(interview, app, show, when="in about 2 hours")
            phone = (app.get("phone") or "").strip()
            if not phone:
                logger.warning("Interview %s: no phone — guest reminder skipped",
                               interview["id"])
                sb_update("interviews", f"id=eq.{interview['id']}",
                          {"reminder_sent_at": _iso(_now())})
                continue
            from voximplant.api_clients.voximplant_client import send_sms
            caller_id = interview.get("caller_id") or os.environ.get(
                "VOXIMPLANT_CALLER_ID", "")
            if (interview.get("call_mode") or "webrtc") == "webrtc":
                text = (
                    f"Mira here, from {show.name} (Nerra Network). Your "
                    "interview starts in about two hours. Join from a "
                    "computer in a quiet room (headphones or AirPods "
                    "help a lot): "
                    f"{show.studio_url(interview['id'])} — Mira"
                )
            else:
                text = (
                    f"Mira here, from {show.name} (Nerra Network). Your "
                    "interview starts in about two hours — I'll be calling "
                    f"you from this number ({caller_id}). Find a quiet spot "
                    "and we'll make something great. — Mira"
                )
            send_sms(phone, text, source_number=caller_id or None)
            sb_update("interviews", f"id=eq.{interview['id']}",
                      {"reminder_sent_at": _iso(_now())})
            logger.info("Reminder SMS sent for interview %s", interview["id"])
        except Exception:  # noqa: BLE001 — a reminder failure must not stop firing
            logger.exception("Reminder failed for %s (non-fatal)",
                             interview["id"])


def fire_due_interviews() -> int:
    lo = _now() - dt.timedelta(minutes=FIRE_GRACE_BEHIND_MIN)
    hi = _now() + dt.timedelta(minutes=FIRE_WINDOW_AHEAD_MIN)
    # status=in.(briefed,scheduled): short-notice bookings (inside the daily
    # prep cron's 12-36h lookahead) arrive still `scheduled` with no brief —
    # they get an inline brief below instead of silently never firing
    # (July 2026: booking opened to 24/7 with 15-min notice).
    due = sb_select(
        "interviews",
        f"status=in.(briefed,scheduled)"
        f"&scheduled_at=gte.{_iso(lo)}&scheduled_at=lte.{_iso(hi)}",
    )
    failures = 0
    for interview in due:
        # Idempotency: a delayed/parallel tick must not double-call.
        if sb_select("interview_runs",
                     f"interview_id=eq.{interview['id']}&status=neq.failed"):
            logger.info("Interview %s already has an active run — skipping",
                        interview["id"])
            continue
        show = show_for(interview)
        try:
            app = sb_select("guest_applications",
                            f"id=eq.{interview['application_id']}")[0]
            show = show_for(interview, app)
            brief_rows = sb_select("interview_briefs",
                                   f"interview_id=eq.{interview['id']}")
            if not brief_rows:
                # Short-notice booking: the daily prep cron never saw this
                # interview. Generate the brief inline (same code path as
                # the T-1d workflow) so Mira still calls; the guest gets
                # the prep email immediately instead of a day ahead.
                from generate_briefs import email_brief_to_guest, generate_brief
                logger.warning(
                    "Interview %s due with no brief (short-notice booking) — "
                    "generating inline", interview["id"])
                brief = generate_brief(interview, app)
                try:
                    email_brief_to_guest(interview, app, brief)
                except Exception:  # noqa: BLE001 — email is best-effort here
                    logger.exception("Inline brief email failed (non-fatal)")
                sb_update("interviews", f"id=eq.{interview['id']}",
                          {"status": "briefed",
                           "episode_thesis": brief["episode_thesis_draft"]})
            else:
                brief = brief_rows[0]
            phone = (app.get("phone") or "").strip()
            if not phone:
                raise RuntimeError("guest has no phone number on file")
            caller_id = interview.get("caller_id") or os.environ.get(
                "VOXIMPLANT_CALLER_ID", "")
            if not caller_id:
                raise RuntimeError("no caller_id (set VOXIMPLANT_CALLER_ID)")

            call_mode = (interview.get("call_mode") or "webrtc").strip()
            host_mode = host_mode_enabled(interview)
            run = sb_insert("interview_runs", {
                "interview_id": interview["id"],
                "mira_system_prompt": compile_mira_prompt(interview, app, brief),
                "voice_preset": "ara",
                "tools": MIRA_TOOLS,
                "guest_phone": phone,
                "caller_id": caller_id,
                "scheduled_for": interview["scheduled_at"],
                # Phase 2 co-host: the scenario dials this Voximplant user
                # into the conference (host_user column, migration
                # 20260906_cohost_conference.sql).
                "host_mode": host_mode,
                "host_user": os.environ.get("VOX_HOST_USER", "").strip() or "host",
                **({"status": "awaiting_guest"} if call_mode == "webrtc" else {}),
            })
            if host_mode:
                notify_host(interview, app, show, when="in 2 min")

            if call_mode == "webrtc":
                # WebRTC (default): no outbound dial. The run row is the
                # studio's green light — the guest's browser polls
                # /voices/studio-state, sees ready, and joins; the scenario
                # starts on the inbound call (CallAlerting) and flips the
                # run to in_progress itself.
                logger.info(
                    "Interview %s (run %s, %s) awaiting guest in the studio: "
                    "%s", interview["id"], run["id"], show.slug,
                    show.studio_url(interview["id"]))
                continue

            from voximplant.api_clients.voximplant_client import (
                start_interview_scenario,
            )
            result = start_interview_scenario(run["id"])
            sb_update("interview_runs", f"id=eq.{run['id']}", {
                "status": "fired",
                "fired_at": _iso(_now()),
                "voximplant_session_id": json.dumps(
                    result.get("result", result))[:512],
            })
            sb_update("interviews", f"id=eq.{interview['id']}",
                      {"status": "in_progress"})
            logger.info("Fired interview %s (run %s) for %s",
                        interview["id"], run["id"], app["name"])
        except Exception as exc:  # noqa: BLE001
            failures += 1
            logger.exception("Firing failed for interview %s", interview["id"])
            sb_update("interviews", f"id=eq.{interview['id']}",
                      {"status": "failed"})
            notify_operator(
                show.slack(f"interview {interview['id']} FAILED to fire: {exc}"),
                critical=True,
            )
    return failures


def main() -> int:
    send_reminders()
    return 1 if fire_due_interviews() else 0


if __name__ == "__main__":
    raise SystemExit(main())
